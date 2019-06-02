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

import logging
log = logging.getLogger(__name__)

from bson.errors import InvalidId
from bson.objectid import ObjectId
import os
import time
import uuid
import simplejson
import werkzeug
import flask

from pytransact.object.attribute import BlobVal
from pytransact.contextbroker import ContextBroker
from pytransact import link as Link
from pytransact import mongo

try:
    from cStringIO import StringIO
except ImportError:
    from io import StringIO
StringIOs = StringIO, type(StringIO())  #, io.BytesIO


def simpleResponse(code, stream):
    return werkzeug.Response(response=stream, status=code)


class JsLink(object):
    """
    resource to create python endpoint for JsLink callback system
    """
    version = 2
    TOUCH_INTERVAL = 60 * 60

    def __init__(self, linkFactory, registerClient=None, logout=None):
        """
        linkFactory - factory function which takes the request and returns
                      a Link subclass
        """
        self.linkFactory = linkFactory
        self.registerClient = registerClient
        self.logout = logout

    @property
    def database(self):
        return ContextBroker().context.database

    def render(self, request):

        try:
            messages = request.json['messages']
        except (TypeError, KeyError):
            raise werkzeug.exceptions.UnprocessableEntity()

        resp = []
        for msg in messages:
            msgType = msg['type']
            meth = getattr(self, '_msg_%s' % msgType)
            clientId = msg.get('clientId')
            if clientId is not None:
                try:
                    clientId = ObjectId(msg['clientId'])
                except (InvalidId, KeyError):
                    return simpleResponse(403, "Unknown clientId")

            answ = meth(clientId, msg, request)
            resp.append(answ)

        return flask.jsonify(results=resp)

    def _msg_client_deactivate(self, clientId, msg, request):
        log.debug('client deactivate %s', clientId)
        database = self.database
        mongo.remove(database.links, {'client': clientId}, multi=True)
        mongo.remove(database.clients, {'_id': clientId})
        return {'client_deactivate': str(clientId)}

    def _msg_handshake(self, client,  msg, request):
        clientId = mongo.insert(self.database.clients,
                             {'updates': [], 'timestamp': time.time()})
        if self.registerClient:
            self.registerClient(clientId, request)
        return {
            'type' : 'handshake',
            'version' : self.version,
            'clientId' : str(clientId),
            'extraInfo': {}
            }

    def _msg_poll(self, clientId, msg, request):
        log.debug('client poll %s', clientId)
        updated_or_outdated = False
        for link in self.linkFactory.iter({'client': clientId,
                                           'outdatedBy': {'$ne': None}}):
            link.run()
            updated_or_outdated = True

        now = time.time()

        if not updated_or_outdated:
            updated_or_outdated = mongo.find(
                self.database.clients,
                {'_id': clientId,
                 '$or': [{'updates': {'$ne': []}},
                         {'timestamp': {'$lt': now - self.TOUCH_INTERVAL}}]},
                projection=[]).count()

        if updated_or_outdated:
            client = mongo.find_and_modify(self.database.clients,
                                        {'_id': clientId},
                                        {'$set': {'updates': [],
                                                  'timestamp': now}},
                                        projection={'updates'})

            # Only dereference, files should not be deleted yet, as they are
            # used when json serializing.
            # Will be deleted by gridfs garbage collector.
            mongo.update(self.database.blobvals.files,
                      {'metadata.references.value': {'$in': [clientId]}},
                      {'$pull': {'metadata.references.value': clientId}},
                      multi=True)

            return client['updates']
        return []

    def _msg_link(self, client,  msg, request):
        linkId = msg['id']
        log.debug("link start %s %s", client, linkId)

        args = dict([(str(k),v) for (k,v) in msg['args'].items()])
        link = self.linkFactory.create(msg['name'], client, linkId, **args)
        link.run()
        return {'new': linkId}

    def _msg_upload(self, client, msg, request):
        import ntpath
        linkId = msg['id']
        log.debug("link start %s %s", client, linkId)

        args = dict([(str(k),v) for (k,v) in msg['args'].items()])
        value = []
        for fkey, fobj in request.files.iteritems(multi=True):
            if not fobj.filename:
                pos = fobj.tell()
                fobj.seek(0, os.SEEK_END)
                if fobj.tell() == 0:
                    continue
                fobj.seek(pos)
            value.append(BlobVal(fobj, filename=ntpath.basename(fobj.filename),
                                 content_type=fobj.content_type))
        args.setdefault('params',{}).setdefault('args',[]).append(value)

        link = self.linkFactory.create(msg['name'], client, linkId, **args)
        link.run()
        return {'new': linkId}

    def _msg_link_update(self, client,  msg, request):
        linkId = msg['id']
        log.debug("link update %s %s", client, linkId)

        link = self.linkFactory.create(None, client, linkId)
        if link is None:
            return {}

        args = dict([(str(k),v) for (k,v) in msg['args'].items()])
        getattr(link, msg['name'])(**args)
        return {'link_update': linkId}

    def _msg_grant(self, client, msg, request):
        toid = ObjectId(msg['toid'])
        auth = str(uuid.uuid4())
        log.debug('grant %s %s %s', client, toid, auth)
        self.database.grants.insert({'toid': toid, 'auth': auth,
                                     'timestamp': time.time()})
        return {'auth': auth}

    def _msg_link_deactivate(self, client,  msg, request):
        linkId = msg['id']
        coll = self.database.links
        link = self.linkFactory.create(None, client, linkId)
        log.debug("link end %s %s", client, linkId)
        if link:
            link.remove()
            return {'link_deactivate': linkId}
        else:
            return {}

    def _msg_logout(self, client, msg, request):
        if self.logout:
            self.logout(client)
