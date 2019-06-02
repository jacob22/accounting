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

import collections
import datetime
import decimal
import flask
import os
import py
import lxml, lxml.html

import suds.client, suds.transport
from flask import json

import sys
if sys.version_info >= (3,0):
    PYT3 = True
    import flask_babel
else:
    PYT3 = False
    import flaskext.babel

from pytransact.testsupport import BLMTests, Fake
import accounting.seqr
from accounting import config
import members

import blm.accounting, blm.members

class TestSeqr(BLMTests):

    def setup_method(self, method):
        super(TestSeqr, self).setup_method(method)
        self.org = blm.accounting.Org(subscriptionLevel=['subscriber'], name=['The Org'])
        self.provider = blm.accounting.SeqrProvider(
            org=self.org,
            #principalId=['8609bf533abf4a20816e8bfe76639521'],
            #password=['N2YFUhKaB1ZSuVF']
            soapUrl=['http://fake.soap.url/?wsdl'],
            principalId=['openend_terminal'],
            password=['123456'],
            currency=['EUR']
        )
        self.product = blm.members.Product(org=[self.org], name=['prod'],
                                           accountingRules={'1000': '10.00'})
        self.product2 = blm.members.Product(org=[self.org], name=['prod2'],
                                           accountingRules={'1000': '15.00'})
        self.item = blm.members.PurchaseItem(product=[self.product],
                                             quantity=[2])
        self.item2 = blm.members.PurchaseItem(product=[self.product2],
                                              quantity=[1])
        self.purchase = blm.members.Purchase(
            items=[self.item, self.item2],
            buyerEmail=['bar@text'],
            buyerName=['Bar von Jobbigt Namn'],
            date=[0])
        self.commit()

        self.app = flask.Flask(__name__, template_folder=config.template_dir)
        if PYT3:
            babel = flask_babel.Babel(self.app)
        else:
            babel = flaskext.babel.Babel(self.app)

        class Faketransport(suds.transport.Transport):

            def open(self, request):
                name = 'seqr_v2' + request.url.split('?')[-1]
                print('Open', request.url, name)
                return open(os.path.join(os.path.dirname(__file__), name),'rb')


        self.service_requests = collections.defaultdict(list)

        class FakeService(object):

            def __init__(self, client):
                self.client = client

            def _validate_context(self, context):
                assert context.clientId == 'Open End AB Eutaxia Admin'
                #assert context.clientReference == 'Eutaxia Admin'
                assert context.clientRequestTimeout == 0
                assert context.initiatorPrincipalId.type == 'TERMINALID'

            def getPaymentStatus(_self, context, invoiceRef):
                _self._validate_context(context)
                self.service_requests['getPaymentStatus'].append(
                    (context, invoiceRef))
                return self.payment_status

            def sendInvoice(_self, context, invoice):
                _self._validate_context(context)
                assert invoice.paymentMode == 'IMMEDIATE_DEBIT'
                assert invoice.acknowledgmentMode == 'NO_ACKNOWLEDGMENT'
                self.service_requests['sendInvoice'].append((context, invoice))
                return self.invoice_resp

            def submitPaymentReceipt(_self, context, ersReference, receiptDoc):
                _self._validate_context(context)
                assert receiptDoc.mimeType == 'text/plain'
                assert receiptDoc.receiptData == ''
                assert receiptDoc.receiptType == ''
                self.service_requests['submitPaymentReceipt'].append((context, ersReference, receiptDoc))
                return self.receipt_resp

            def cancelInvoice(_self, context, invoiceRef):
                _self._validate_context(context)
                self.service_requests['cancelInvoice'].append((context, invoiceRef))
                return self.cancel_resp

            def refundPayment(_self, context, ersReference, invoice):
                _self._validate_context(context)
                self.service_requests['refundPayment'].append((context, ersReference, invoice))
                return self.refund_resp

            def markTransactionPeriod(_self, context, entry):
                self.service_requests['markTransactionPeriod'].append((context, entry))
                return self.transaction_period_resp

        class Client(suds.client.Client):

            def __init__(self, *args, **kw):
                if args[0].startswith('http://'):
                    assert args[0].startswith('http://fake.soap.url/?wsdl')
                kw.update({'transport': Faketransport()})
                suds.client.Client.__init__(self, *args, **kw)
                self.service = FakeService(self)

        self._orig_Client = accounting.seqr.Client
        accounting.seqr.Client = Client
        self.client = Client('seqr_v2?wsdl')

    def teardown_method(self, method):
        super(TestSeqr, self).teardown_method(method)
        accounting.seqr.Client = self._orig_Client


    def test_invoice(self):
        resp = self.invoice_resp = self.client.factory.create('ns0:erswsSendInvoiceResponse')
        resp.resultCode = 0
        resp.invoiceQRCode = 'HTTP://FOO/BAR'

        with self.app.test_request_context('http://baseurl/') as c:
            response = accounting.seqr.invoice(
                self.provider.id[0],
                self.purchase.id[0], 'http://return.test/',
                database=self.database)

            assert response.status_code == 200
            (context, invoice), = self.service_requests['sendInvoice']
            assert invoice.backURL == 'http://return.test/'
            assert invoice.clientInvoiceId == self.purchase.ocr[0]
            assert invoice.issueDate == datetime.datetime(1970, 1, 1, 0, 0)
            assert invoice.title == self.org.name[0]
            assert invoice.totalAmount.value == 35
            assert invoice.totalAmount.currency == 'EUR'

            row1, row2 = invoice.invoiceRows.invoiceRow
            assert row1.itemDescription == 'prod'
            assert row1.itemQuantity == 2
            assert row1.itemTotalAmount.value == 20
            assert row1.itemTotalAmount.currency == 'EUR'
            assert row1.itemUnitPrice.value == 10
            assert row1.itemUnitPrice.currency == 'EUR'

            tree = lxml.html.fromstring(response.data)
            a = tree.cssselect('.seqr-qrcode')[0]
            assert a.attrib['href'] == 'SEQR-DEMO://FOO/BAR'

    def test_invoice_with_error(self):
        resp = self.invoice_resp = self.client.factory.create('ns0:erswsSendInvoiceResponse')
        resp.resultCode = 49
        resp.resultDescription = 'INVALID_INVOICE_DATA'
        resp.invoiceQRCode = 'HTTP://FOO/BAR'

        with self.app.test_request_context('http://baseurl/') as c:
            py.test.raises(accounting.seqr.SeqrError, accounting.seqr.invoice,
                           self.provider.id[0],
                           self.purchase.id[0], 'http://return.test/',
                           database=self.database)

    def test_poll(self):
        resp = self.payment_status = self.client.factory.create('ns0:erswsPaymentStatusResponse')
        resp.resultCode = 0
        resp.resultDescription = "SUCCESS"
        resp.status = "ISSUED"

        with self.app.test_request_context('http://baseurl/') as c:
            response = accounting.seqr.poll(self.database, self.provider.id[0],
                                            self.purchase.id[0], '1234')
            assert 'submitPaymentReceipt' not in self.service_requests
            assert json.loads(response.data)['status'] == 'ISSUED'

        resp.status = 'PAID'
        resp.ersReference = "2014100613463653401022006"
        resp.resultCode = 0
        resp.receipt.paymentDate = datetime.datetime.now()
        resp.receipt.paymentReference = "2014090114515234501131287"
        resp.receipt.invoiceReference = "1409575879561"
        resp.receipt.payerTerminalId = "eb44fc03e6264d2299cbb180cd8d196b"
        resp.receipt.invoice.totalAmount.value = decimal.Decimal(42)

        self.receipt_resp = self.client.factory.create('ns0:submitPaymentReceiptResponse')
        self.receipt_resp.resultCode = 0

        with self.app.test_request_context('http://baseurl/') as c:
            response = accounting.seqr.poll(self.database, self.provider.id[0],
                                            self.purchase.id[0], '1234')
            (context, ersReference, receiptDoc), = self.service_requests['submitPaymentReceipt']
            assert ersReference == "2014100613463653401022006"
            assert json.loads(response.data)['status'] == 'PAID'

        assert blm.members.SeqrPayment._query(matchedPurchase=self.purchase).run()

    def test_cancel(self):
        resp = self.cancel_resp = self.client.factory.create('ns0:cancelInvoiceResponse')
        resp.resultCode = 0
        resp.resultDescription = "SUCCESS"

        with self.app.test_request_context('http://baseurl/') as c:
            response = accounting.seqr.cancel(self.database, self.provider.id[0],
                                              self.purchase.id[0], '1234')
            (context, invoiceRef), = self.service_requests['cancelInvoice']
            assert invoiceRef == '1234'
            assert response.status_code == 302
            assert response.headers['Location'] == self.purchase.invoiceUrl[0]

    def test_refund(self):
        resp = self.refund_resp = self.client.factory.create('ns0:refundPaymentResponse')
        resp.resultCode = 0
        resp.resultDescription = 'SUCCESS'
        resp.ersReference = 'ersref2'

        payment = blm.members.SeqrPayment(
            paymentProvider=self.provider,
            matchedPurchase=self.purchase,
            paymentReference="2014090114515234501131287",
            invoiceReference="1409575879561",
            payerTerminalId="eb44fc03e6264d2299cbb180cd8d196b",
            paymentDate=1413795926,
            ersReference="2014100613463653401022006",
            amount='20')
        self.commit()

        ersref = accounting.seqr.refund(payment.id[0], database=self.database)
        assert ersref == 'ersref2'

        (context, ersReference, invoice), = self.service_requests['refundPayment']
        assert ersReference == payment.ersReference[0]
        assert invoice.title == self.org.name[0]
        assert invoice.totalAmount.value == 35
        assert invoice.totalAmount.currency == 'EUR'

    def test_refund_failed(self):
        resp = self.refund_resp = self.client.factory.create('ns0:refundPaymentResponse')
        resp.resultCode = 99
        resp.resultDescription = 'RECEIVER_ACCOUNT_DOES_NOT_ALLOW_REFUNDS'

        payment = blm.members.SeqrPayment(
            paymentProvider=self.provider,
            matchedPurchase=self.purchase,
            paymentReference="2014090114515234501131287",
            invoiceReference="1409575879561",
            payerTerminalId="eb44fc03e6264d2299cbb180cd8d196b",
            paymentDate=1413795926,
            ersReference="2014100613463653401022006",
            amount='20')
        self.commit()

        err = py.test.raises(accounting.seqr.SeqrError, accounting.seqr.refund,
                             payment.id[0], database=self.database)
        assert err.value.code == 99
        assert err.value.description == 'RECEIVER_ACCOUNT_DOES_NOT_ALLOW_REFUNDS'

        (context, ersReference, invoice), = self.service_requests['refundPayment']
        assert ersReference == payment.ersReference[0]
        assert invoice.title == self.org.name[0]
        assert invoice.totalAmount.value == 35
        assert invoice.totalAmount.currency == 'EUR'


    def test_markTransactionPeriod(self):
        resp = self.transaction_period_resp = self.client.factory.create('ns0:markTransactionPeriodResponse')
        resp.resultCode = 0
        resp.resultDescription = "SUCCESS"

        principalId = 'principalId'
        userId = 9900
        password = 'password'
        terminalId = 'terminalId'

        accounting.seqr.mark_transaction_period(
            self.database, self.provider.id[0], principalId, userId, password,
            terminalId)
        (context, entry), = self.service_requests['markTransactionPeriod']

        assert context.clientId == 'Open End AB Eutaxia Admin'
        assert context.clientRequestTimeout == 0
        assert context.initiatorPrincipalId.type == 'RESELLERUSER'
        assert context.initiatorPrincipalId.id == principalId
        assert context.initiatorPrincipalId.userId == userId
        assert context.password == password

        assert entry.parameter.entry.key == 'TERMINALID'
        assert entry.parameter.entry.value == terminalId
