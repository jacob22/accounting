# -*- coding: utf-8-*-

# Copyright 2019 Open End AB
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

#
# Tests for JsLink
#

import flask, os, py, simplejson, time, urllib
import bson
from bson.objectid import ObjectId
from werkzeug.datastructures import FileStorage, MultiDict

from flask import json

try:
    from cStringIO import StringIO  #py2
except ImportError:
    from io import StringIO         #py3
    
#from Test.ResourceHelper import FakeRequest
from pytransact import spickle
from pytransact.testsupport import ContextTests
from pytransact import mongo as DB
from pytransact import link as Link
from pytransact.object.attribute import BlobVal

import accounting.jslink as JsLink
from accounting import flask_utils

class Fake(object):
    def __init__(self, **kw):
        self.__dict__.update(**kw)

def jslinkTestClient(jslink):
    app = flask.Flask(__name__)
    flask_utils.set_json_encoder(app)
    app.debug = True
    @app.route('/jslink', methods=['GET', 'POST'])
    def render():
        return jslink.render(flask.request)
    return app.test_client()

def invokeRender(jslink, data):
    with jslinkTestClient(jslink) as c:
        return c.post('/jslink', data=json.dumps({'messages': data}),
                      content_type='application/json',
                      charset='utf-8')

def doRequest(jslink, data):
    resp = invokeRender(jslink, data)
    assert resp.status_code == 200
    data = json.loads(resp.data)
    data = data['results']
    assert len(data) == 1
    return data[0]

def doPoll(jslink, clientId):
    data = doRequest(jslink, data=[{
                    'type': 'poll',
                    'clientId' : clientId,
                    }])
    assert len(data) == 1
    return data[0]


class FakeLink(Link.Link):
    def __init__(self, clientId, linkId, **kw):
        self.clientId = clientId
        self.linkId = linkId
        self.link = None
        self.args = kw
        self.params = {}
        self.removed = False

    def run(self):
        self.save(self.params, {})
        # force serialization of blobvals
        bson.BSON.encode(self.args)

    def doUpdate(self, **kw):
        self.update(kw)

    def remove(self):
        self.removed = True


class FakeLinkFactory(object):

    def __init__(self, test=None):
        self.test = test

    def create(self, _name, _clientId, _linkId, **kw):
        link = None
        if _name == 'linkMe':
            link = FakeLink(_clientId, _linkId, **kw)
        if self.test.ctx.database.links.find({'client': _clientId,
                                              'link': _linkId}).count():
            link = FakeLink(_clientId, _linkId, **kw)
        self.test.link = link
        return link

    def iter(self, query={}):
        return iter([])


class TestJsLink(ContextTests):

    now = 1

    def time(self):
        return self.now

    class ObjectEncoder(json.JSONEncoder):
        def default(self, o):
            if isinstance(o, ObjectId):
                return str(o)
            raise ValueError

    def setup_method(self, method):
        super(TestJsLink, self).setup_method(method)
        self.linkFactory = FakeLinkFactory()

    def test_simple(self):
        jslink = JsLink.JsLink(lambda x:None)

    def test_handshake_with_register(self, monkeypatch):
        calls = []
        def register(client, request):
            calls.append(client)

        jslink = JsLink.JsLink(lambda x:None, registerClient=register)

        monkeypatch.setattr(time, 'time', self.time)

        data = doRequest(jslink, data=[{"type": "handshake"}])

        clientId = data['clientId']
        assert data['extraInfo'] == {}

        assert calls == [ObjectId(clientId)]

        self.sync()
        client = DB.find_one(self.database.clients)
        assert str(client['_id']) == clientId
        assert client['timestamp'] == 1
        assert client['updates'] == []

    def test_empty_poll(self, monkeypatch):
        jslink = JsLink.JsLink(self.linkFactory)

        data = doRequest(jslink, data=[{"type": "handshake"}])

        assert data['clientId']

        clientId = data['clientId']

        # _command = jslink.database.command
        # def command(*args, **kw):
        #     # we want to make sure no mongodb query during this poll
        #     # demands to speak to the primary
        #     assert kw.get('_use_master') == False
        #     return _command(*args, **kw)

        # monkeypatch.setattr(jslink.database, 'command', command)

        data = doRequest(jslink, data=[{
                        'type': 'poll',
                        'clientId' : clientId,
                        }])

        assert data == []

    def test_non_empty_poll(self):
        jslink = JsLink.JsLink(self.linkFactory)

        data = doRequest(jslink, data=[{"type": "handshake"}])

        assert data['clientId']

        clientId = ObjectId(data['clientId'])

        val = BlobVal('bar')
        val.addref(clientId)
        val.large_blob = 2

        DB.update(self.ctx.database.clients,
                  {'_id': clientId},
                  {'$set': {'updates': [{'foo': 42, 'bar': val}]}})
        self.sync()

        assert DB.find(self.database.blobvals.files,
                       {'metadata.references.value': {'$in': [clientId]}}).count() == 1

        data = doRequest(jslink, data=[{
                'type': 'poll',
                'clientId' : str(clientId),
                }])
        self.sync()

        assert data == [{'foo': 42,
                         'bar': {'size': 3,
                                 'content_type': None,
                                 'filename': None}}]
        assert DB.find(self.database.blobvals.files,
                       {'metadata.references.value': {'$in': [clientId]}}).count() == 0

    def test_bad_clientId(self):
        jslink = JsLink.JsLink(self.linkFactory)

        #req = FakeRequest("/jslink")

        clientId = 'Unknown_client_ID'

        resp = invokeRender(jslink, data=[{
                        'type': 'poll',
                        'clientId' : clientId,
                        }])

        assert resp.status_code == 403

    def test_poll_reruns_outdated_links(self, monkeypatch):
        links = []
        class LinkFactory():
            class Link(object):
                def __init__(self, clientId, linkId):
                    self.clientId = clientId
                    self.linkId = linkId
                    self.ran = False
                def run(_self):
                    DB.update(self.ctx.database.clients,
                              {'_id': ObjectId(clientId)},
                              {'$push': {'updates': {'update': _self.linkId}}})

                    _self.ran = True

            def create(name, clientId, linkId):
                links.append(self.Link(clientId, linkId))
                return links[-1]

            def iter(_self, query):
                assert query['outdatedBy']
                assert query['client'] == ObjectId(clientId)
                _links = [_self.Link(link['client'], link['link']) for link in
                          self.ctx.database.links.find(query)]
                links.extend(_links)
                return _links

        jslink = JsLink.JsLink(LinkFactory())
        data = doRequest(jslink, data=[{"type": "handshake"}])
        clientId = data['clientId']

        DB.update(self.ctx.database.clients,
                  {'_id': ObjectId(clientId)},
                  {'$set': {'updates': [{'foo': 42}]}})
        DB.insert(self.ctx.database.links, {'client': ObjectId(clientId),
                                            'link': 1,
                                            'outdatedBy': None})
        DB.insert(self.ctx.database.links, {'client': ObjectId(clientId),
                                            'link': 2,
                                            'outdatedBy': ObjectId()})
        self.sync()

        data = doRequest(jslink, data=[{
                'type': 'poll',
                'clientId' : clientId,
                }])

        assert data == [{'foo': 42}, {'update': 2}]
        assert len(links) == 1
        assert links[0].linkId == 2
        assert links[0].ran

    def test_poll_touches_timestamp(self, monkeypatch):
        class LinkFactory(object):
            def iter(self, spec):
                return []
        jslink = JsLink.JsLink(LinkFactory())

        now = 1
        monkeypatch.setattr(time, 'time', lambda : now)

        data = doRequest(jslink, data=[{"type": "handshake"}])
        clientId = data['clientId']
        self.sync()

        timestamp = self.ctx.database.clients.find_one(
            {'_id': ObjectId(clientId)})['timestamp']
        assert timestamp == 1 # sanity, set by handshake

        now = 2

        doRequest(jslink, data=[{'type': 'poll',
                                 'clientId' : clientId}])
        self.sync()
        timestamp = self.ctx.database.clients.find_one(
            {'_id': ObjectId(clientId)})['timestamp']
        assert timestamp == 1 # untouched

        now += jslink.TOUCH_INTERVAL

        doRequest(jslink, data=[{'type': 'poll',
                                 'clientId' : clientId}])
        self.sync()
        timestamp = self.ctx.database.clients.find_one(
            {'_id': ObjectId(clientId)})['timestamp']
        assert timestamp == now # touched


class TestJsLinkCalls(ContextTests):

    now = 1

    def time(self):
        return self.now

    def setup_method(self, method):
        super(TestJsLinkCalls, self).setup_method(method)

        self.jslink = JsLink.JsLink(FakeLinkFactory(self), logout=self.logout)
        data = doRequest(self.jslink, data=[{"type": "handshake"}])
        self.clientId = data['clientId']

    def logout(self, clientId):
        self.loggedout = clientId

    def test_link(self):
        data = doRequest(self.jslink, data=[{
            'type': 'link',
            'args' : {'test':'foo'},
            'id' : 42,
            'name' : 'linkMe',
            'clientId' : self.clientId,
            }])
        assert data == {'new': 42}

        self.link.update({'foo': 'bar'})
        self.sync()
        data = doPoll(self.jslink, self.clientId)
        assert data['args'] == {'foo':'bar'}

        # defunct link id
        data = doRequest(self.jslink, data=[{
            'type': 'link_update',
            'args' : {'foo':'bar', 'apa':'bepa'},
            'id' : 99,
            'name' : 'doUpdate',
            'clientId' : self.clientId,
            }])
        assert data == {}

        data = doRequest(self.jslink, data=[{
            'type': 'link_update',
            'args' : {'foo':'bar', 'apa':'bepa'},
            'id' : 42,
            'name' : 'doUpdate',
            'clientId' : self.clientId,
            }])
        assert data == {'link_update': 42}
        self.sync()

        data = doPoll(self.jslink, self.clientId)
        assert data['args'] == {'foo':'bar', 'apa':'bepa'}

        # defunct link id
        data = doRequest(self.jslink, data=[{
            'type': 'link_deactivate',
            'args' : {},
            'id' : 99,
            'name' : 'deactivate',
            'clientId' : self.clientId,
            }])
        assert data == {}

        data = doRequest(self.jslink, data=[{
            'type': 'link_deactivate',
            'args' : {},
            'id' : 42,
            'name' : 'deactivate',
            'clientId' : self.clientId,
            }])
        assert data == {'link_deactivate': 42}
        self.sync()

        assert not DB.find_one(self.ctx.database.links,
                               {'client': self.clientId, 'link': 42})
        assert self.link.removed

    def test_upload(self):
        py.test.skip()
        #req = FakeRequest("/jslink")
        files = MultiDict(
            [('attachments', FileStorage(
                        filename='c://foo\\bar/apa.txt', # IE bug
                        content_type='text/plain',
                        stream=StringIO('some content here'))),
             ('attachments', FileStorage(
                        filename='',
                        content_type='application/octet-stream',
                        stream=StringIO('')))])

        files['message'] = json.dumps(
            [{'type': 'upload',
             'args' : {'params': {'args': [['foo']] } },
             'id' : 42,
             'name' : 'linkMe',
             'clientId' : self.clientId,
             }])

        data = doRequest(self.jslink, data=files)

        assert data == {'new': 42}

        assert len(self.link.args['params']['args']) == 2
        files = self.link.args['params']['args'][1]
        assert len(files) == 1
        assert isinstance(files[0], BlobVal)
        assert files[0].filename == 'apa.txt'
        assert files[0].content_type == 'text/plain'
        assert files[0].getvalue() == 'some content here'

    def test_upload_unicode(self):
        py.test.skip()
        #req = FakeRequest("/jslink")
        files = MultiDict(
            [('filearg', FileStorage(filename=u'/u/user/åäö.txt',
                                     content_type='text/plain',
                                     stream=StringIO('some content here')))])

        files['message'] = json.dumps(
            [{'type': 'upload',
             'args' : {'params': {'args': [['foo']] } },
             'id' : 42,
             'name' : 'linkMe',
             'clientId' : self.clientId,
              }])

        data = doRequest(self.jslink, **files)
        assert data == {'new': 42}

        assert len(self.link.args['params']['args']) == 2
        files = self.link.args['params']['args'][1]
        assert len(files) == 1
        assert files[0].filename == u'åäö.txt'
        assert files[0].content_type == 'text/plain'
        assert files[0].getvalue() == 'some content here'

    def test_client_shutdown(self):
        data = doRequest(self.jslink, data=[{
            'type': 'link',
            'args' : {'test':'foo'},
            'id' : 42,
            'name' : 'linkMe',
            'clientId' : self.clientId,
            }])
        self.sync()
        assert DB.find_one(self.ctx.database.links,
                           {'client': ObjectId(self.clientId), 'link': 42})
        assert DB.find_one(self.ctx.database.clients,
                           {'_id': ObjectId(self.clientId)})

        answer = doRequest(self.jslink, data=[{
                        'type': 'client_deactivate',
                        'clientId' : self.clientId,
                        }])
        assert answer == {'client_deactivate': self.clientId}
        self.sync()

        assert not DB.find_one(self.ctx.database.links,
                               {'client': ObjectId(self.clientId), 'link': 42})
        assert not DB.find_one(self.ctx.database.clients,
                               {'_id': ObjectId(self.clientId)})

    def test_logout(self):
        data = doRequest(self.jslink, data=[{
                        'type': 'logout',
                        'clientId' : self.clientId,
                        }])
        assert str(self.loggedout) == self.clientId

    def test_grant(self, monkeypatch):
        monkeypatch.setattr(time, 'time', self.time)
        toid = ObjectId()
        data = doRequest(self.jslink, data=[{
                        'type': 'grant',
                        'clientId': self.clientId,
                        'toid': str(toid)}])
        self.sync()

        assert len(data) == 1
        auth = data['auth']

        assert DB.find_one(self.ctx.database.grants, {'auth': auth, 'toid': toid,
                                                      'timestamp': 1})
