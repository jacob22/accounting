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
from io import BytesIO
try:
    import urllib2
except ImportError:
    from urllib import request as urllib2

import jwt
import accounting.freja


def test_jsondump():
    data = [{'foo': 'bar'}, {'bar': 'baz'}, 'räksmörgås']
    result = accounting.freja.jsondump(data)
    assert result == u'[{"foo":"bar"},{"bar":"baz"},"räksmörgås"]'.encode('utf-8')


def test_base64encode():
    data = ' '.join('räksmörgås' for n in range(10))
    result = accounting.freja.base64encode(data)
    assert result == ('csOka3Ntw7ZyZ8OlcyByw6Rrc23DtnJnw6VzIHLDpGtzbc'
                      'O2cmfDpXMgcsOka3Ntw7ZyZ8OlcyByw6Rrc23DtnJnw6Vz'
                      'IHLDpGtzbcO2cmfDpXMgcsOka3Ntw7ZyZ8OlcyByw6Rrc2'
                      '3DtnJnw6VzIHLDpGtzbcO2cmfDpXMgcsOka3Ntw7ZyZ8Olcw==')


def test_get_payload_without_extradata():
    ssn = '197001015465'
    text = 'Do you like räksmörgås?'
    title = 'A title!'
    result = accounting.freja.get_payload(ssn=ssn, title=title, text=text)
    prefix, data = result.split(b'=', 1)
    assert prefix == b'initSignRequest'
    data = codecs.decode(data, 'base64')
    data = json.loads(data.decode('utf8'))
    assert data['userInfoType'] == 'SSN'
    assert ssn in codecs.decode(data['userInfo'].encode('ascii'),
                                'base64').decode('utf8')


def test_request_signature(monkeypatch):
    ssn = '197001015465'
    title = 'A title!'
    text = 'Do you like räksmörgås?'
    class Opener:
        def __init__(self, handler):
            pass
        def open(self, request):
            return BytesIO(b'{"foo": "bar"}')

    monkeypatch.setattr(urllib2, 'build_opener', Opener)
    result = accounting.freja.request_signature(ssn, title, text)
    assert result == {"foo": "bar"}


def test_get_result_when_started(monkeypatch):
    class Opener:
        def __init__(self, handler):
            pass
        def open(self, request):
            return BytesIO(b'{"status": "STARTED"}')

    monkeypatch.setattr(urllib2, 'build_opener', Opener)
    result = accounting.freja.get_result(signRef='foobar')
    assert result == ('STARTED', None)


def test_get_result_when_approved(monkeypatch):
    class Opener:
        def __init__(self, handler):
            pass
        def open(self, request):
            return BytesIO(b'{"status": "APPROVED", "details": "DETAILS"}')

    monkeypatch.setattr(urllib2, 'build_opener', Opener)

    def jwt_decode(data, key='', verify=True):
        if data == 'DETAILS':
            assert verify
            with open(accounting.freja.jwt_key) as f:
                assert key == f.read()
                return {'status': 'APPROVED',
                        'signatureData': {'userSignature': 'SIGNATURE_DATA'}}
        elif data == 'SIGNATURE_DATA':
            assert key == ''
            assert not verify
            return {'binaryData': 'XVUYNWMxNzYwNGNhNzM1YzM0NGNlOGYzZmRhYS4='}

    monkeypatch.setattr(jwt, 'decode', jwt_decode)

    result = accounting.freja.get_result(signRef='foobar')
    assert result == ('APPROVED', ['5c17604ca735c344ce8f3fda'])
