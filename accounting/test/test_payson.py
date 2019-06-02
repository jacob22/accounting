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

import py
import decimal
import flask
try:
    import httplib                  #py2
except ImportError:
    import http.client as httplib   #py3
import payson
try:
    from urllib.parse import urlencode as urlencode     #py3
except ImportError:
    from urllib import urlencode as urlencode           #py2
import time
import werkzeug.datastructures
from pytransact.testsupport import BLMTests, Fake
import accounting.config, accounting.payson, accounting.mail
import members

import blm.accounting, blm.members


class TestPayson(BLMTests):

    def setup_method(self, method):
        super(TestPayson, self).setup_method(method)

        class FakePaysonApi(object):

            apis = []

            def __init__(self, apiUserId, apiPassword):
                self.apiUserId = apiUserId
                self.apiPassword = apiPassword
                self.apis.append(self)

            def pay(self, **kw):
                self.paid = kw
                return Fake(
                    forward_pay_url='http://forward.pay.url/',
                    success=True)

            def validate(self, requestdata):
                self.validated = requestdata
                return True

            def payment_details(self, token):
                return self.details

            def payment_update(_self, token, action):
                _self.payment_update_params = token, action
                return self.payment_update_result
        self.FakePaysonApi = FakePaysonApi
        self.payment_update_result = True

        self.org = blm.accounting.Org(subscriptionLevel=['subscriber'], name=['The Org'])
        self.provider = blm.accounting.PaysonProvider(org=self.org,
                                                      apiUserId=['123'],
                                                      apiPassword=['1234-5678-90ab-cdef'],
                                                      receiverEmail=['foo@test'])
        self.product = blm.members.Product(org=[self.org], name=['prod'], accountingRules={'1000': '10.00'})
        self.item = blm.members.PurchaseItem(product=[self.product], quantity=[2])
        self.purchase = blm.members.Purchase(items=[self.item],
                                             buyerEmail=['bar@text'],
                                             buyerName=['Bar von Jobbigt Namn'])
        self.commit()

        self.confopts = {}
        for spec in (('payson', 'ipn_notification_baseurl'),
                     ('accounting', 'baseurl')):
            section, option = spec
            self.confopts[spec] = accounting.config.config.get(section, option)

    def teardown_method(self, method):
        super(TestPayson, self).teardown_method(method)
        for (section, option), value in self.confopts.items():
            accounting.config.config.set(section, option, value)

    def test_pay(self, monkeypatch):
        monkeypatch.setattr(payson, 'PaysonApi', self.FakePaysonApi)

        accounting.config.config.set('payson', 'ipn_notification_baseurl', '')
        accounting.config.config.set('accounting', 'baseurl', 'http://confbaseurl/')

        app = flask.Flask(__name__)
        @app.route('/invoice/<purchase>/<random>')
        def invoice(purchase, random):
            return  ''

        with app.test_request_context('http://baseurl/') as c:
            response = accounting.payson.pay(self.database, self.provider.id[0],
                                             self.purchase.id[0], 'http://return.test/')
            assert response.headers['Location'] == 'http://forward.pay.url/'

        api, = self.FakePaysonApi.apis
        assert api.apiUserId == '123'
        assert api.apiPassword == '1234-5678-90ab-cdef'

        receiver, = api.paid.pop('receiverList')

        assert api.paid == {
            'returnUrl': 'http://return.test/',
            'cancelUrl': 'http://return.test/',
            'ipnNotificationUrl': 'http://confbaseurl/paysonipn',
            'memo': 'Betalning till The Org',
            'senderEmail': 'bar@text',
            'senderFirstName': 'Bar',
            'senderLastName': 'Namn',
            'trackingId': str(self.purchase.id[0]),
            'custom': str(self.provider.id[0])
            }

        assert receiver.email == 'foo@test'
        assert receiver.amount == decimal.Decimal('20.00')

        self.FakePaysonApi.apis = []
        accounting.config.config.set('payson', 'ipn_notification_baseurl', 'http://myipnurl/')
        with app.test_request_context('http://baseurl/') as c:
            result = accounting.payson.pay(self.database, self.provider.id[0],
                                           self.purchase.id[0], 'http://return.test/')

        api, = self.FakePaysonApi.apis
        assert api.paid['ipnNotificationUrl'] == 'http://myipnurl/paysonipn'

    def test_ipn(self, monkeypatch):
        monkeypatch.setattr(payson, 'PaysonApi', self.FakePaysonApi)

        mails = []
        def sendmail(*args, **kw):
            mails.append((args, kw))
        monkeypatch.setattr(accounting.mail, 'sendmail', sendmail)

        ipn = {'HASH': u'5d65d7a5de76ffc2847a1abb0b320e44',
               'currencyCode': u'SEK',
               'custom': u'"%s"' % self.provider.id[0], # json!
               'fundingList.fundingConstraint(0).constraint': u'BANK',
               'fundingList.fundingConstraint(1).constraint': u'CREDITCARD',
               'purchaseId': u'3702021',
               'receiverFee': u'14.2500',
               'receiverList.receiver(0).amount': u'375.00',
               'receiverList.receiver(0).email': u'testagent-1@payson.se',
               'senderEmail': u'micke+payson@openend.se',
               'status': u'COMPLETED',
               'token': u'f11f26ad-4d6f-45a0-a3fe-be7be4089463',
               'trackingId': str(self.purchase.id[0]),
               'type': u'TRANSFER'}

        ipnquery = urlencode(ipn)

        response = ipn.copy()
        response['responseEnvelope.ack'] = 'SUCCESS'
        response['responseEnvelope.timestamp'] = time.strftime('%Y-%m-%dT%H:%M:%S')
        response['responseEnvelope.correlationId'] = 'foo'

        self.FakePaysonApi.details = payson.PaymentDetailsResponse(response)

        app = flask.Flask(__name__)
        with app.test_request_context('/', method='POST', data=ipnquery,
                                      content_type='application/x-www-form-urlencoded') as c:
            flask.request.parameter_storage_class = werkzeug.datastructures.ImmutableOrderedMultiDict
            content, status = accounting.payson.payson_ipn(flask.request, self.database)
            assert content == ''
            assert status == httplib.NO_CONTENT

        assert len(self.FakePaysonApi.apis) == 2
        ipnApi, detailsApi = self.FakePaysonApi.apis
        assert ipnApi.validated == ipnquery

        payment, = blm.members.PaysonPayment._query().run()
        assert payment.paymentProvider == [self.provider]
        assert payment.matchedPurchase == [self.purchase]
        assert payment.amount == [decimal.Decimal('375.00')]
        assert payment.purchaseId == ['3702021']
        assert payment.senderEmail == ['micke+payson@openend.se']
        assert payment.token == ['f11f26ad-4d6f-45a0-a3fe-be7be4089463']
        assert payment.receiverFee == [decimal.Decimal('14.2500')]
        assert payment.receiverEmail == ['testagent-1@payson.se']
        assert payment.type == ['TRANSFER']


        # identical second ipn notification
        with app.test_request_context('/', method='POST', data=ipnquery,
                                      content_type='application/x-www-form-urlencoded') as c:
            flask.request.parameter_storage_class = werkzeug.datastructures.ImmutableOrderedMultiDict
            content, status = accounting.payson.payson_ipn(flask.request, self.database)
            assert content == ''
            assert status == httplib.NO_CONTENT

        # don't create a new payment
        assert blm.members.PaysonPayment._query().run() == [payment]
        assert len(mails) == 1

    def test_refund(self, monkeypatch):
        monkeypatch.setattr(payson, 'PaysonApi', self.FakePaysonApi)
        payment = blm.members.PaysonPayment(
            paymentProvider=[self.provider],
            matchedPurchase=[self.purchase],
            amount=self.purchase.total,
            purchaseId=[str(self.purchase.id[0])],
            senderEmail=['foo@bar.test'],
            token=['f11f26ad-4d6f-45a0-a3fe-be7be4089463'],
            receiverFee=[decimal.Decimal('10.00')],
            receiverEmail=['bar@foo.test'],
            type=['TRANSFER'])
        self.commit()

        result = accounting.payson.refund(payment, database=self.database)
        api, = self.FakePaysonApi.apis
        assert api.payment_update_params == (payment.token[0], 'REFUND')
        assert result == True

    def test_refund_fail(self, monkeypatch):
        monkeypatch.setattr(payson, 'PaysonApi', self.FakePaysonApi)
        self.payment_update_result = False
        payment = blm.members.PaysonPayment(
            paymentProvider=[self.provider],
            matchedPurchase=[self.purchase],
            amount=self.purchase.total,
            purchaseId=[str(self.purchase.id[0])],
            senderEmail=['foo@bar.test'],
            token=['f11f26ad-4d6f-45a0-a3fe-be7be4089463'],
            receiverFee=[decimal.Decimal('10.00')],
            receiverEmail=['bar@foo.test'],
            type=['TRANSFER'])
        self.commit()

        py.test.raises(accounting.payson.PaysonError, accounting.payson.refund, payment,
                       database=self.database)
        api, = self.FakePaysonApi.apis
        assert api.payment_update_params == (payment.token[0], 'REFUND')
