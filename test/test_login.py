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

import os
import py
import logging
import flask
try:
    from cookielib import MozillaCookieJar  # Python 2
except ImportError:
    from http.cookiejar import MozillaCookieJar  # Python 3

from accounting import oauth

try:
    from urlparse import urlparse  # Python 2
except ImportError:
    from urllib.parse import urlparse  # Python 3

try:
    # Python 2
    from urllib2 import (
        HTTPRedirectHandler,
        build_opener,
        HTTPCookieProcessor,
        HTTPError,
    )

except ImportError:
    # Python 3
    from urllib.request import (
        HTTPRedirectHandler,
        build_opener,
        HTTPCookieProcessor,
    )
    from urllib.error import HTTPError


from accounting import config

def setup_module(module):
    if not py.test.config.option.run_integration_tests:
        py.test.skip('Skipping integration tests')
    module._orig_baseurl = config.config.get('accounting','baseurl')
    config.config.set('accounting','baseurl','https://localhost.admin.eutaxia.eu:5000/')

def teardown_module(module):
    config.config.set('accounting','baseurl',module._orig_baseurl)

class TestLogin(object):

    def setup_method(self, method):
        self.app = flask.Flask('test')
        self.app.secret_key = b'gurka'
        oauth.init(self.app, '/login/', self.create_or_login)

    def create_or_login(self, resp):
        return '<h1 class="loggedin"></h1>', 666

    def test_login_generator(self):
        # If this test fails, you may need to regenerate the cookies.
        # See fixcookies.py in this directory.
        for provider in 'google', 'facebook', 'windowslive':
            def foo(provider=provider):
                self.login_test(provider)
            yield provider, foo

    def login_test(self, provider):
        with self.app.test_request_context('https://localhost.admin.eutaxia.eu:5000/login',
                                           base_url='https://localhost.admin.eutaxia.eu:5000/'):
            resp = oauth.authorize(provider)
            assert resp.status_code == 302
            location = resp.headers['Location']
            session_data = dict(flask.session)

        cj = MozillaCookieJar(os.path.join(os.path.dirname(__file__), 'cookies.%s.txt' % provider))
        cj.load()

        class NoRedirectHandler(HTTPRedirectHandler):

            def redirect_request(self, req, fp, code, msg, hdrs, newurl):
                if newurl.startswith('https://localhost.admin.eutaxia.eu:5000/login/%s' % provider):
                    raise HTTPError(req.get_full_url(), code, msg, hdrs, fp)
                return HTTPRedirectHandler.redirect_request(self, req, fp, code, msg, hdrs, newurl)

        opener = build_opener(HTTPCookieProcessor(cj),
                              NoRedirectHandler())

        try:
            res = opener.open(location)
        except HTTPError as err:
            assert err.code == 302
            url = err.hdrs['Location']
            assert url.startswith('https://localhost.admin.eutaxia.eu:5000/login/%s' % provider)
        else:
            if provider == 'windowslive':
                # Unfortunately we can't configure Windows Live to accept two separate
                # redirect URLs
                return
            else:
                assert False, 'Wrong redirect'

        with self.app.test_client() as c:
            with c.session_transaction() as session:
                session.update(session_data)

            query_string = urlparse(url).query
            resp = c.get('/login/%s' % provider, query_string=query_string)
            assert resp.status_code == 666
