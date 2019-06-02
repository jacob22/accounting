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

"""
Provide OAuth authentication from various providers
"""
import base64


import sys
if sys.version_info >= (3,0):
    PYT3 = True
    import urllib.parse
else:
    PYT3 = False
    import urlparse

import httplib2
import json
import jwt
import os
import hashlib

import Crypto.PublicKey.RSA

from flask import session, request, url_for, redirect, current_app
from werkzeug import url_quote
from accounting import config
from flask_oauthlib.client import OAuth

import accounting.config
log = accounting.config.getLogger('oauth')


class AuthResponse(object):
    def __init__(self, provider, user_id, fullname=None, nickname=None, email=None):
        self.identity_url = 'oauth://%s/%s' % (provider, user_id)
        self.user_id = user_id
        self.fullname = fullname
        self.nickname = nickname
        self.email = email

class AuthProvider(object):
    def __init__(self, oauth, provider, after_login, jwks_uri=None,
                 userinfo_endpoint='me', **attrs):
        self.userinfo_endpoint = userinfo_endpoint
        self.jwks_uri = jwks_uri
        self.jwks = {}
        self.provider = provider
        self.app = oauth.remote_app(provider, **attrs)
        self.after_login_func = after_login
        #self.authorized_handler = self.app.authorized_handler(self.authorized_handler)
        self.app.tokengetter(self.tokengetter)

    def _json_to_key(self, json):
        def toint(s):
            s = base64.urlsafe_b64decode(s.encode('utf-8'))
            i = 0
            for c in s:
                i <<= 8
                try:
                    c = ord(c)  # Python 2
                except TypeError:
                    pass  # Python 3
                i += c
            try:
                return long(i)  # Python 2
            except NameError:
                return i  # Python 3

        return Crypto.PublicKey.RSA.construct((toint(json['n']), toint(json['e'])))

    def authorize(self, **params):
        session.pop('%s_oauth_token' % self.provider, None) # Clear old auth tokens
        if not self.app.request_token_url: # OAuth 2
            rand = os.urandom(32)
            #            if PYT3:
            #                params['state'] = hashlib.sha256(current_app.secret_key.encode() + rand).hexdigest()
            #            else:
            params['state'] = hashlib.sha256(current_app.secret_key + rand).hexdigest()
            session['oauth_random'] = rand
        else:
            session.pop('oauth_random', None)

        if PYT3:
            return self.app.authorize(callback=self.get_authorized_url(), **params)
        else:
            return self.app.authorize(callback=self.get_authorized_url(), **params)

    def authorized_handler(self):
        if ('state' in request.args or 'oauth_random' in session) and \
           request.args['state'] != hashlib.sha256(
               current_app.secret_key +
               session.pop('oauth_random', '')).hexdigest():
            session['openid_error'] = 'Access denied: bad state'

            return redirect(self.get_current_url())

        resp = self.app.authorized_response()
        if resp is None:
            # XXX Hack to minimze changes
            session['openid_error'] = (
                'Access denied: %s %s' % (request.args['error_reason'],
                                          request.args['error_description']))
            return redirect(self.get_current_url())
        if 'oauth_token' in resp:
            session['%s_oauth_token' % self.provider] = (
                resp['oauth_token'], resp['oauth_token_secret'])
        else:
            session['%s_oauth_token' % self.provider] = (
                resp['access_token'], '')

        if 'screen_name' in resp:
            return self.after_login_func(
                AuthResponse(self.provider, resp['user_id'],
                             nickname=resp.get('screen_name')))

        sub = None
        if self.jwks_uri:
            try:
                _, _, header, _ = jwt.load(resp['id_token'])
            except AttributeError:
                header = jwt.get_unverified_header(resp['id_token'])
            kid = header.get('kid')
            if kid not in self.jwks:
                h = httplib2.Http()
                hdr, content = h.request(self.jwks_uri)
                self.jwks = {}
                for key in json.loads(content.decode('utf-8'))['keys']:
                    self.jwks[key.get('kid')] = key

            if kid:
                keys = [self.jwks[kid]]
            else:
                keys = self.jwks.values()

            data = None
            for key in keys:
                try:
                    _key = self._json_to_key(key)
                    try:
                        data = jwt.decode(resp['id_token'], _key)
                    except TypeError:
                        data = jwt.decode(resp['id_token'],
                                          _key.exportKey(format='PEM'),
                                          audience=self.app.consumer_key)
                except jwt.DecodeError:
                    pass
                else:
                    break

            if not data:
                session['openid_error'] = 'Access denied'
                return redirect(self.get_current_url())

            sub = data['sub']

        # Facebook and Windows Live needs another call to fetch user id
        data = None
        me = self.app.get(self.userinfo_endpoint, data=data)

        email = None
        if 'email' in me.data:
            email = me.data['email']
        elif 'emails' in me.data:
            email = me.data['emails'].get('preferred')
        if 'sub' in me.data:
            if sub and sub != me.data['sub']:
                raise RuntimeError('Authentication error!')
            sub = me.data['sub']
        else:
            sub = me.data['id']
        return self.after_login_func(
            AuthResponse(self.provider, sub,
                         fullname = me.data.get('name'),
                         email = email))

    def tokengetter(self):
        return session.get('%s_oauth_token' % self.provider)

    def get_current_url(self):
        return request.base_url

    def get_authorized_url(self):
        """return the url to redirect authorization to"""
        return url_for('%s/authorized_handler' % self.provider,
                       _external=True)

authproviders = {}
_defaultattrs = {
    'base_url': None, 'request_token_url': None, 'access_token_url': None,
    'authorize_url': None, 'consumer_key': None, 'consumer_secret': None
    }


def init(app, prefix, after_login):
    """
    Set up OAuth authenticators from config file in flask app
    """
    oauth = OAuth()

    for provider in config.config.sections():
        if not provider.startswith('oauth#'):
            continue
        attrs = _defaultattrs.copy()
        attrs.update(config.config.items(provider))
        baseurl = config.config.get('accounting','baseurl')
        if 'request_token_params' in attrs:
            rtp = dict(map(str.strip, kv.split('='))
                       for kv in attrs['request_token_params'].split(','))
            for k,v in rtp.items():
                rtp[k] = v.replace('$baseurl', baseurl)
            attrs['request_token_params'] = rtp
        if 'access_token_params' in attrs:
            rtp = dict(map(str.strip, kv.split('='))
                       for kv in attrs['access_token_params'].split(','))
            attrs['access_token_params'] = rtp

        provider = provider[6:] # strip oauth#
        rapp = AuthProvider(oauth, provider, after_login, **attrs)
        authproviders[provider] = rapp
        if PYT3:
            app.add_url_rule(urllib.parse.urljoin(prefix, provider),
                             '%s/authorized_handler' % provider,
                             rapp.authorized_handler)
        else:
            app.add_url_rule(urlparse.urljoin(prefix, provider),
                             '%s/authorized_handler' % provider,
                             rapp.authorized_handler)

def authorize(provider, **kwargs):
    """
    Prepare for authorization through a given provider
    """

    rapp = authproviders[provider]
    return rapp.authorize(**kwargs)
