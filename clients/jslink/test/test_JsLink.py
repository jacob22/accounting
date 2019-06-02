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

from oejskit.testing import jstests_suite

import py.test

from pytransact import link, commit
from pytransact import testsupport
from accounting.jslink import JsLink
#from Bl.WSGI import JsLink
#from Bl.test import support
#from Test import BlmSupport
#import blm.helpdesk

class TestJsLink(object):

    _connection = _database = None

    def teardown_class(self):
        if self._database:
            testsupport.clean_db(self._database)
        if self._connection:
            self._connection.close()

    @property
    def connection(self):
        if not self._connection:
            self._connection = testsupport.connect()
        return self._connection

    @property
    def database(self):
        if not self._database:
            self._database = self.connection[testsupport.dbname]
        return self._database

    def sync(self):
        sync(self.database)

    jstests_browser_kind = 'any'

    @jstests_suite('test_JsLink_basic.js')
    def test_basic(self, monkeypatch):
        import flask
        import werkzeug.exceptions
        import accounting.flask_utils
        app = flask.Flask('test_app')
        accounting.flask_utils.set_json_encoder(app)

        @app.route('/forbidden')
        def forbidden():
            raise werkzeug.exceptions.Forbidden()

        @app.route('/not_allowed')
        def not_allowed():
            # this code should never be executed, as we do not allow
            # POST to this function
            assert False

        @app.route('/timing_', methods=['POST'])
        def timing_():
            assert flask.request.method == 'POST'
            delta = flask.request.form['delta']
            int(delta) # should not break!
            return delta

        @app.route('/borken', methods=['POST'])
        def borken():
            return '{0,'

        @app.route('/outdated', methods=['POST'])
        def outdated():
            raise werkzeug.exceptions.PreconditionFailed()

        @app.route('/server_error/upload', methods=['POST'])
        def server_error():
            return '{"error": "AN ERROR"}'

        @app.route('/client_bug', methods=['POST'])
        def client_bug():
            return '[[{"type": "gurka"}]]'

        @app.route('/jslink', methods=['GET', 'POST'])
        def jslink():
            jslink = JsLink(linkFactory=link.LinkFactory())
            with commit.CommitContext(self.database):
                result = jslink.render(flask.request)
            return result

        # class TestJsLink(JsLink.JsLink):
        #     def _msg_test(self, clientId, msg, request):
        #         return 'ok'
        #     def _msg_upload(self, clientId, msg, request):
        #         assert request.files
        #         return 'ok'

        # monkeypatch.setattr(JsLink, 'JsLink', TestJsLink)

        return app

    @jstests_suite('test_JsLink_Link.js')
    def test_Link(self, monkeypatch):
        class FakeLink(object):
            def __init__(self, clientId, linkId):
                self.clientId = clientId
                self.linkId = linkId
            def m(self, arg):
                pass
            def deactivate(self):
                pass
            def run(self):
                pass
            def remove(self):
                pass
            def pushback(_self, arg):
                self.database.clients.update(
                    {'_id': _self.clientId},
                    {'$push': {'updates': {'type': 'update',
                                           'id': _self.linkId,
                                           'args': {'arg': arg}}}})
                testsupport.sync(self.database)

        class LinkFactory(object):
            def create(self, name, clientId, linkId, **args):
                return FakeLink(clientId, linkId)
            def iter(_self, spec):
                return []

        monkeypatch.setattr(link, 'LinkFactory', LinkFactory)

        import flask
        import werkzeug.exceptions
        import accounting.flask_utils
        app = flask.Flask('test_app')
        accounting.flask_utils.set_json_encoder(app)

        @app.route('/jslink', methods=['GET', 'POST'])
        def jslink():
            jslink = JsLink(linkFactory=link.LinkFactory())
            with commit.CommitContext(self.database):
                result = jslink.render(flask.request)
            return result

        return app #self.wsgi_app(params=str(self.user.id[0]))
