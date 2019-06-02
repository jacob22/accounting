# -*- coding: utf-8 -*-

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

import json
import os
import py.test
import accounting.swish
from bson.objectid import ObjectId
from pytransact.testsupport import BLMTests
import members
import blm.accounting, blm.members
import flask
from accounting import config, flask_utils
import pytest
import OpenSSL.crypto


# To create the following two files, download the bundle of test certificates
# from Swish, and run the following commands:
# openssl pkcs12 -in 1231181189.p12 -nodes -out swish.crt.pem
# openssl pkcs12 -in 1231181189.p12 -nocerts -nodes -out swish.key.pem

here = os.path.dirname(__file__)
with open(os.path.abspath(os.path.join(here, 'swish.crt.pem')),'r') as f:
    cert = f.read()
with open(os.path.abspath(os.path.join(here, 'swish.key.pem')),'r') as f:
    pkey = f.read()


def test_find_root_cert():
    type, pem = accounting.swish.find_root_cert(cert)
    assert type == 'test'
    # Don't explode
    OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, pem)


class TestClient(object):

    def setup_method(self, method):
        self.client = accounting.swish.Client('1231181189', cert, pkey,
                                              test=True)

    def test_create_payment(self):
        py.test.skip('Disable Swish tests until certificate mess is sorted')
        with self.client:
            payment = self.client.create_payment(
                provider=ObjectId(),
                purchase=ObjectId(),
                payeePaymentReference='0123456789',
                callbackUrl='https://example.com/api/swishcb/paymentrequests',
                payerAlias='46712345678',
                amount=100,
                currency='SEK',
                message='Kingston USB Flash Drive 8 GB'
            )
            assert payment.id


def test_filter():
    dut = accounting.swish._filter_message
    assert dut('foo') == 'foo'
    assert dut(u'räksmörgås') == u'räksmörgås'
    assert dut(u'abcABC012ÅÄÖåäö:;.,?!()') == u'abcABC012ÅÄÖåäö:;.,?!()'

    # max length 50
    assert dut('a' * 100) == 'a' * 50
    assert dut('no-dash') == 'no dash'
    assert dut('no - dash') == 'no dash'  # remove multiple spaces


class TestSwish(BLMTests):

    def setup_method(self, method):
        super(TestSwish, self).setup_method(method)
        self.org = blm.accounting.Org(subscriptionLevel=['subscriber'],
                                      name=[u'The Org - With a fünny näme'])

        self.provider = blm.accounting.SwishProvider(
            org=[self.org],
            swish_id=['1231181189'],
            cert=[cert],
            pkey=[pkey],
            currency=['SEK']
        )
        self.product = blm.members.Product(org=[self.org], name=['prod'],
                                           accountingRules={'1000': '10.01'})
        self.item = blm.members.PurchaseItem(product=[self.product],
                                             quantity=[2])
        self.purchase = blm.members.Purchase(
            items=[self.item],
            buyerEmail=['bar@text'],
            buyerName=['Bar von Jobbigt Namn'],
            date=[0])
        self.commit()

        self.app = flask.Flask(__name__, template_folder=config.template_dir)
        flask_utils.add_converters(self.app)
        self.app.register_blueprint(accounting.swish.swish_api, url_prefix='/foo')

        @self.app.before_request
        def set_db():
            flask.g.database = self.database

    def test_charge_success(self):
        py.test.skip('Disable Swish tests until certificate mess is sorted')
        config.config.set('accounting', 'baseurl', 'https://test.invalid')

        with self.app.test_client() as client:
            resp = client.post(
                '/foo/charge/%s/%s' % (self.provider.id[0], self.purchase.id[0]),
                data=json.dumps({'phone': '1231181189'}),
                headers={'Content-Type': 'application/json'}
            )
            assert resp.status_code == 200
            data = json.loads(resp.get_data())
            assert data['status'] == 'CREATED'
