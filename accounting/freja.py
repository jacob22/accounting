# -*- coding: utf-8 -*-
from __future__ import unicode_literals

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

import codecs
import json
import os
import time

try:
    import httplib
    import urllib2
    from urlparse import urljoin
except ImportError:
    from http import client as httplib
    from urllib import request as urllib2
    from urllib.parse import urljoin

import jwt
from pytransact import spickle
import accounting.config

if os.path.isdir('/etc/freja'):
    cert_dir = '/etc/freja'
else:
    cert_dir = os.path.join(os.path.dirname(__file__), 'test', 'freja')

cert = os.path.join(cert_dir, 'openend.cert')
pkey = os.path.join(cert_dir, 'openend.pkey')
jwt_key = os.path.join(cert_dir, 'jwt.pub')


FREJA_TEXT_MAX_LEN = 2048  # empirically obtained


def jsondump(data):
    # do *not* ensure ascii since freja doesn't accept unicode escape
    # sequences
    return json.dumps(data, ensure_ascii=False,
                      separators=(',', ':')).encode('utf8')


def base64decode(data):
    try:
        data = data.encode('ascii')
    except TypeError:
        pass
    return codecs.decode(data, 'base64')


def base64encode(data):
    try:
        data = codecs.encode(data, 'utf8')
    except (TypeError, UnicodeDecodeError):
        pass
    data = codecs.encode(data, 'base64')
    return data.decode('ascii').replace('\n', '')


class HTTPSClientAuthHandler(urllib2.HTTPSHandler):

    def __init__(self, cert, key):
        urllib2.HTTPSHandler.__init__(self)
        self.key = key
        self.cert = cert

    def https_open(self, req):
        # Rather than pass in a reference to a connection class, we pass in
        # a reference to a function which, for all intents and purposes,
        # will behave as a constructor
        return self.do_open(self.getConnection, req)

    def getConnection(self, host, timeout=300):
        return httplib.HTTPSConnection(host, key_file=self.key,
                                       cert_file=self.cert)


def get_payload(ssn, title, text, extra_data=None, expiry=180):

    ssnuserinfo = {
        'country': 'SE',
        'ssn': ssn,
    }

    dataToSign = {
        'text': base64encode(text[:FREJA_TEXT_MAX_LEN])
    }

    if extra_data is None:
        dataToSignType = 'SIMPLE_UTF8_TEXT'
        signatureType = 'SIMPLE'
    else:
        dataToSignType = 'EXTENDED_UTF8_TEXT'
        dataToSign['binaryData'] = base64encode(extra_data)
        signatureType = 'EXTENDED'

    req = {
        'title': title,
        'userInfoType': 'SSN',
        'userInfo': base64encode(jsondump(ssnuserinfo)),
        'expiry': int(time.time() + expiry) * 1000,
        'minRegistrationLevel': 'EXTENDED',
        'dataToSignType': dataToSignType,
        'dataToSign': dataToSign,
        'signatureType': signatureType,
    }

    return b'initSignRequest=' + base64encode(jsondump(req)).encode('ascii')


def request_signature(ssn, title, text, extra_data=None):
    payload = get_payload(ssn, title, text, extra_data)

    opener = urllib2.build_opener(HTTPSClientAuthHandler(cert, pkey))
    url = urljoin(accounting.config.config.get('freja', 'baseurl'),
                  'initSignature')

    request = urllib2.Request(url, payload)
    request.add_header('Content-Type', 'application/x-www-form-urlencoded')
    try:
        response = opener.open(request)
        stream = codecs.getreader('utf8')(response)
        return json.load(stream)
    except urllib2.HTTPError as e:
        print(e.fp.read())
        raise


def get_result(signRef):
    payload = 'getOneSignResultRequest=' + base64encode(jsondump({'signRef': signRef}))
    payload = payload.encode('ascii')

    opener = urllib2.build_opener(HTTPSClientAuthHandler(cert, pkey))
    url = urljoin(accounting.config.config.get('freja', 'baseurl'),
                  'getOneResult')

    request = urllib2.Request(url, payload)
    request.add_header('Content-Type', 'application/x-www-form-urlencoded')
    try:
        stream = codecs.getreader('utf8')(opener.open(request))
        response = json.load(stream)
    except urllib2.HTTPError as e:
        print(e.fp.read())
        raise

    status = response['status']

    if status != 'APPROVED':
        return status, None

    with open(jwt_key) as f:
        details = jwt.decode(response['details'], f.read())

    sigData = jwt.decode(details['signatureData']['userSignature'], verify=False)
    toids = spickle.loads(base64decode(sigData['binaryData']))
    return status, toids


if __name__ == '__main__':
    import sys

    ssn = '197001015465'

    if sys.argv[1] == 'sign':
        response = request_signature(ssn)
        print(response)

    elif sys.argv[1] == 'check':
        response = get_result(sys.argv[2])
        print(response)
