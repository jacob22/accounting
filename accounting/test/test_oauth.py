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

import sys
if sys.version_info < (3,0,0):
    PYT3 = False
else:
    PYT3 = True

try:
    from urllib import urlencode # Pyt2
except ImportError:
    from urllib.parse import urlencode # Pyt3

from .. import oauth
from accounting import config

import hashlib
import flask

class TestAuthProvider(object):
    def setup_method(self, m):
        self.oauth = oauth.OAuth()

    def test_simple(self):
        ap = oauth.AuthProvider(self.oauth,
                                'fakebook', lambda x:x,
                                base_url = 'https://fake',
                                request_token_url = None,
                                access_token_url = None,
                                authorize_url = None,
                                consumer_key = 'KEY',
                                consumer_secret = 'SECRET',
                                )

        assert self.oauth.remote_apps['fakebook'] is ap.app

    def test_authorized_handler_std(self, monkeypatch):
        response = []
        def after_login(resp):
            response.append(resp)
            return resp
        ap = oauth.AuthProvider(self.oauth,
                                'fakebook', after_login,
                                base_url = 'https://fake',
                                request_token_url = None,
                                access_token_url = None,
                                authorize_url = None,
                                consumer_key = 'KEY',
                                consumer_secret = 'SECRET',
                                )

        monkeypatch.setattr(oauth, 'session', {})
        app = flask.Flask(__name__)
        app.secret_key = 'test'
        with app.test_request_context('/?error_reason=fail&error_description=test%20fail') as c:
            ap.app.authorized_response = lambda : {
                'oauth_token' : 'token',
                'oauth_token_secret' : 'token_secret',
                'user_id' : 42,
                'screen_name' : 'Ix'}
            # XXX Bypass oauth wrapper
            res = oauth.AuthProvider.authorized_handler(ap)

        assert response == [res]
        assert res.identity_url == 'oauth://fakebook/42'
        assert res.user_id == 42
        assert res.nickname == 'Ix'

    def test_authorized_handler_login_refused(self, monkeypatch):
        response = []
        def after_login(resp):
            response.append(resp)
            return resp
        ap = oauth.AuthProvider(self.oauth,
                                'fakebook', after_login,
                                base_url = 'https://fake',
                                request_token_url = None,
                                access_token_url = None,
                                authorize_url = None,
                                consumer_key = 'KEY',
                                consumer_secret = 'SECRET',
                                )

        # XXX Bypass oauth wrapper
        app = flask.Flask(__name__)
        app.secret_key = 'test'
        with app.test_request_context('/?error_reason=fail&error_description=test%20fail') as c:
            ap.app.authorized_response = lambda : None
            res = oauth.AuthProvider.authorized_handler(ap)
            assert flask.session['openid_error'] == 'Access denied: fail test fail'

class FakeApp(object):
    def __init__(self):
        self.paths = {}
    def add_url_rule(self, path, endpoint, view_func):
        self.paths[path] = (endpoint, view_func)
    def route(self, path):
        def _(f):
            self.paths[path] = (f.func_name, f)
            return f
        return _

class TestOAuth(object):
    config = {
        'oauth#fakebook' : {
            'base_url': 'https://localhost/baseurl',
            'request_token_url': '',  ### For Pyt3.  Maybe 'https://localhost/request'? /TJo
            'access_token_url': 'https://localhost/access',
            'authorize_url': 'https://localhost/authorize',
            'consumer_key': 'CONSUMER_KEY',
            'consumer_secret': 'CONSUMER_SECRET',
            'request_token_params': 'scope=email'
        }
    }

    def setup_method(self, method):
        for section,settings in self.config.items():
            assert not config.config.has_section(section)
            config.config.add_section(section)
            for k,v in settings.items():
                config.config.set(section, k, v)

    def teardown_method(self, method):
        for section in self.config:
            config.config.remove_section(section)
        oauth.authproviders.clear()

    def test_init(self):
        response = []
        def after_login(resp):
            response.append(resp)

        app = flask.Flask(__name__)
        app.secret_key = b's3kr1t'
        oauth.init(app, '/login/oauth/', after_login)

        urlmap = app.url_map.bind('foo')
        assert urlmap.match('/login/oauth/fakebook')

        with app.test_request_context('/') as c:
            r = oauth.authorize('fakebook')
            if PYT3:
                assert b'%2Flogin%2Foauth%2Ffakebook' in r.response[0]
            else:
                assert '%2Flogin%2Foauth%2Ffakebook' in r.response[0]

    def test_state(self, monkeypatch):
        response = []
        def after_login(resp):
            response.append(resp)

        app = flask.Flask(__name__)
        app.secret_key = b's3kr1t'
        oauth.init(app, '/login/oauth/', after_login)

        urlmap = app.url_map.bind('foo')
        assert urlmap.match('/login/oauth/fakebook')

        with app.test_request_context('/') as c:
            r = oauth.authorize('fakebook')
            random = flask.session['oauth_random']
            state = hashlib.sha256(app.secret_key + random).hexdigest()

            try:
                state = state.encode('ascii')
            except AttributeError:
                pass
            assert state in r.response[0]

            with app.test_request_context(
                    '/login/oauth/fakebook?'+ urlencode(
                        dict(state=state, error_reason='foo',
                             error_description='bar'))) as c:
                flask.session['oauth_random'] = random
                monkeypatch.setattr(oauth.authproviders['fakebook'].app,
                                    'authorized_response', lambda: None)
                r = oauth.authproviders['fakebook'].authorized_handler()
                assert 'foo' in flask.session['openid_error']

        with app.test_request_context('/') as c:
            r = oauth.authorize('fakebook')
            random = flask.session['oauth_random']
            state = hashlib.sha256(app.secret_key + random).hexdigest()

            try:
                state = state.encode('ascii')
            except AttributeError:
                pass
            assert state in r.response[0]

            with app.test_request_context(
                    '/login/oauth/fakebook?'+ urlencode(
                        dict(state='baz', error_reason='foo',
                             error_description='bar'))) as c:
                flask.session['oauth_random'] = random
                monkeypatch.setattr(oauth.authproviders['fakebook'].app,
                                    'authorized_response', lambda: None)
                r = oauth.authproviders['fakebook'].authorized_handler()
                assert 'bad state' in flask.session['openid_error']
