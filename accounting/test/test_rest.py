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

from bson.objectid import ObjectId
import decimal, json, os, py
try:
    import httplib                      #py2
except ImportError:
    from http import client as httplib  #py3
import flask

from .. import rest
from pytransact.testsupport import BLMTests, Time
from pytransact.queryops import *
from accounting import flask_utils
import accounting.invoke
import members

from .wsgisupport import WSGITests
import blm.fundamental, blm.accounting, blm.members


class FakeRequest(object):

    def __init__(self, values=None, headers=None):
        self.values = values or {}
        self.headers = headers or {}


class TestRouter(BLMTests):

    def setup_method(self, method):
        super(TestRouter, self).setup_method(method)
        self.router = rest.Router(self.database)

    def test_purchase(self, monkeypatch):
        def invoke(rq, database, user, blmname, method):
            assert rq is request
            assert database == self.database
            assert user is None
            assert blmname == 'members'
            assert method == 'purchase'
            return 'result'

        request = object()
        monkeypatch.setattr(accounting.invoke, 'invoke', invoke)

        result = self.router.route('purchase', request)
        assert result == 'result'

    def test_Product_fields(self):
        org = blm.accounting.Org()
        p1 = blm.members.Product(org=org, name='p1', available=True)
        self.commit()

        rq = FakeRequest(values=dict(org=str(org.id[0])))
        result = self.router.do_Product(rq)
        assert result
        data = json.loads(result)
        expect = {
            str(p1.id[0]): {
                u'currentStock': [],
                u'description': [],
                u'hasImage': [False],
                u'id': [str(p1.id[0])],
                u'name': [u'p1'],
                u'optionFields': [],
                u'price': [0],
                u'tags': []
                }
            }
        assert data == expect

    def test_Product_selection(self):
        org = blm.accounting.Org()
        p1 = blm.members.Product(org=org, name='p1', available=True)
        p2 = blm.members.Product(org=org, name='p2', available=True,
                                 availableFrom=['2010-01-01'])
        p3 = blm.members.Product(org=org, name='p3', available=True,
                                 availableTo=['2010-01-31'])
        p4 = blm.members.Product(org=org, name='p4', available=True,
                                 availableFrom=['2010-01-01'],
                                 availableTo=['2010-01-31'])
        p5 = blm.members.Product(org=org, name='p5', available=False)
        self.commit()

        p1, p2, p3, p4, p5 = [toi.id[0] for toi in [p1, p2, p3, p4, p5]]

        def mktime(arg):
            return time.mktime(time.strptime(arg, '%Y-%m-%d'))

        def request():
            rq = FakeRequest(values=dict(org=str(org.id[0])))
            return {ObjectId(key) for key in
                    json.loads(self.router.do_Product(rq))}

        with Time(now=mktime('2009-12-31')):
            data = request()
            assert data == {p1, p3}

        with Time(now=mktime('2010-02-01')):
            data = request()
            assert data == {p1, p2}

        with Time(now=mktime('2010-01-01')):
            data = request()
            assert data == {p1, p2, p3, p4}

        with Time(now=mktime('2010-01-31')):
            data = request()
            assert data == {p1, p2, p3, p4}


class RestApiTests(WSGITests):

    def setup_method(self, method):
        super(RestApiTests, self).setup_method(method)
        self.user = blm.accounting.APIUser()
        self.org = blm.accounting.Org(name='ACME Inc.')
        self.org.ug[0].users = [self.user]
        self.other_org = blm.accounting.Org()
        self.commit()

        self.app = flask.Flask('test')
        self.setup_wsgi()
        self.app.register_blueprint(rest.rest_api)

    def get(self, client, uri, **kw):
        resp = client.get(uri, **kw)
        assert resp.status_code == httplib.OK
        try:
            data = resp.data.decode('utf-8')
        except AttributeError:
            data = resp.data
        return json.loads(data)

    def post(self, client, uri, expect=httplib.OK, **kw):
        kw.setdefault('content_type', 'application/json')
        response = client.post(uri, **kw)
        assert response.status_code == expect
        try:
            try:
                data = response.data.decode('utf-8')
            except AttributeError:
                data = response.data
            response.json = json.loads(data)
        except (AttributeError, ValueError):    #py3 version raises AttributeError?
            pass
        return response

    def assert_not_found(self, client, uri):
        resp = client.get(uri)
        assert resp.status_code == httplib.NOT_FOUND


class TestProductRestApi(RestApiTests):

    def setup_method(self, method):
        super(TestProductRestApi, self).setup_method(method)
        self.user.roles.append('storekeepers')
        self.commit()

    def test_status_not_found(self):
        with self.app.test_client() as c:
            self.assert_not_found(c, '/product/status/%s' % ObjectId())

    def test_product_status(self):
        product = blm.members.Product(name='Foo', org=self.org)
        self.commit()
        with self.app.test_client() as c:
            data = self.get(c, '/product/status/%s' % product.id[0])
            assert data == {
                'result': {
                    'id': str(product.id[0]),
                    'name': 'Foo',
                    'description': None,
                    'accountingRules': {},
                    'price': '0.00',
                    'vatAccount': None
                    }
                }

    def test_product_create_success(self):
        with self.app.test_client() as c:
            params = dict(name='Foo',
                          description='Foo foos the foo',
                          totalStock=27,
                          accountingRules={'1000': '30.00',
                                           '2000': '40.00'},
                          vatAccount='3000',
                          )
            resp = self.post(c, '/product/create', data=json.dumps(params))
            toid = resp.json['result']['id']
            self.sync()
            product, = blm.members.Product._query(id=toid).run()
            assert product.name == ['Foo']
            assert product.description == ['Foo foos the foo']
            assert product.totalStock == [27]
            assert product.accountingRules == {'1000': decimal.Decimal('30.00'),
                                               '2000': decimal.Decimal('40.00')}
            assert product.vatAccount == ['3000']

    def test_product_create_forbidden(self):
        with self.app.test_client() as c:
            params = dict(org=str(self.other_org.id[0]), name='Foo')
            resp = self.post(c, '/product/create', data=json.dumps(params),
                             expect=httplib.FORBIDDEN)

    def test_product_update_success(self):
        product = blm.members.Product(name='Bar', org=self.org)
        self.commit()
        with self.app.test_client() as c:
            params = dict(name='Foo',
                          description='Foo foos the foo',
                          totalStock=27,
                          accountingRules={'1000': '30.00',
                                           '2000': '40.00'},
                          vatAccount='3000',
                          )
            resp = self.post(c, '/product/update/%s' % product.id[0],
                             data=json.dumps(params))
            toid = resp.json['result']['id']
            assert toid == str(product.id[0])
            self.sync()
            product, = blm.members.Product._query(id=toid).run()
            assert product.name == ['Foo']
            assert product.description == ['Foo foos the foo']
            assert product.totalStock == [27]
            assert product.accountingRules == {'1000': decimal.Decimal('30.00'),
                                               '2000': decimal.Decimal('40.00')}
            assert product.vatAccount == ['3000']

    def test_product_update_hack(self):
        otherorg = blm.accounting.Org()
        product = blm.members.Product(name='Bar', org=self.org)
        self.commit()
        with self.app.test_client() as c:
            params = dict(org=str(otherorg.id[0]))
            resp = self.post(c, '/product/update/%s' % product.id[0],
                             data=json.dumps(params), expect=httplib.FORBIDDEN)

    def test_product_delete_success(self):
        product = blm.members.Product(name='Foo', org=self.org)
        self.commit()
        with self.app.test_client() as c:
            response = self.post(c, '/product/delete/%s' % product.id[0])
            assert response.json == {'result': {'id': str(product.id[0])}}
        self.sync()
        assert not blm.members.Product._query(id=product.id[0]).run()


class TestInvoiceRestApi(RestApiTests):

    def setup_method(self, method):
        super(TestInvoiceRestApi, self).setup_method(method)
        self.user.roles.append('invoicesenders')
        self.user.roles.append('storekeepers')
        self.commit()

    def test_status_not_found(self):
        invoice = blm.members.Invoice(org=self.other_org)
        self.commit()
        with self.app.test_client() as c:
            self.assert_not_found(c, '/invoice/status/%s' % ObjectId())
            self.assert_not_found(c, '/invoice/status/%s' % invoice.id[0])

    def test_status(self):
        invoice = blm.members.Invoice(org=[self.org])
        invoice.paymentState = ['unpaid']
        self.commit()

        with self.app.test_client() as c:
            data = self.get(c, '/invoice/status/%s' % invoice.id[0])
            assert data == {
                'result': {
                    'id': str(invoice.id[0]),
                    'invoiceUrl': invoice.invoiceUrl[0],
                    'paymentState': 'unpaid',
                    'ocr': invoice.ocr[0]
                    }
                }

    def test_list_with_query_params(self):
        invoices = [blm.members.Invoice(org=[self.org]) for invoice in
                    range(3)]
        self.commit()

        with self.app.test_client() as c:
            params = '&'.join('id=%s' % invoice.id[0] for invoice in invoices)
            data = self.get(c, '/invoice/list?%s' % params)
            expect = {
                'result': [
                    {
                        'id': str(invoice.id[0]),
                        'invoiceUrl': invoice.invoiceUrl[0],
                        'paymentState': 'paid',
                        'ocr': invoice.ocr[0]
                    } for invoice in invoices
                ]
            }
            assert data == expect

    def test_create_with_existing_product_success(self):
        prod = blm.members.Product(org=self.org, name='The Product',
                                   accountingRules={'1000': '10'})
        self.commit()

        with self.app.test_client() as c:
            params = dict(org=str(self.org.id[0]),
                          buyerName='Mr. Smith',
                          buyerAddress='2 High Street\n1234 Sunnydale',
                          buyerPhone='123 456 789',
                          buyerEmail='smith@test',
                          expiryDate=1500000000,
                          buyerAnnotation='This stuff will be so awesome!',
                          buyerReference='Mr. Smith, 123 456 789',
                          paymentTerms='You must pay!',
                          items=[{
                              'product': str(prod.id[0]),
                              'quantity': 2,
                              'options': ['Foo bar baz']
                          }],
                          )
            resp = self.post(c, '/invoice/create', data=json.dumps(params))
            toid = resp.json['result']['id']
            self.sync()
            invoice, = blm.members.Invoice._query(id=toid).run()
            assert invoice.buyerName == ['Mr. Smith']
            assert invoice.buyerAddress == ['2 High Street\n1234 Sunnydale']
            assert invoice.buyerPhone == ['123 456 789']
            assert invoice.buyerEmail == ['smith@test']
            assert invoice.expiryDate == [1500000000]
            assert invoice.buyerAnnotation == ['This stuff will be so awesome!']
            assert invoice.buyerReference == ['Mr. Smith, 123 456 789']
            assert invoice.paymentTerms == ['You must pay!']

            item, = invoice.items
            assert item.product == [prod]
            assert item.quantity == [2]
            assert item.total == [decimal.Decimal('20.00')]
            assert item.options == ['Foo bar baz']

    def test_credit_invoice(self):
        prod = blm.members.Product(org=self.org, name='The Product',
                                   accountingRules={'1000': '10'})
        invoice = blm.members.Invoice(
            items=[blm.members.PurchaseItem(product=prod)])
        self.commit()

        with self.app.test_client() as c:
            params = dict(invoice=str(invoice.id[0]))
            resp = self.post(c, '/invoice/credit/%s' % invoice.id[0])
            toid = resp.json['result']['id']
            self.sync()
            credit, = blm.members.CreditInvoice._query(id=toid).run()
            assert credit.credited == [invoice]
