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

import copy, decimal, email, py.test, time, json
import stripe, stripe.resource
from bson.objectid import ObjectId
from pytransact.exceptions import ClientError, LocalisedError
from pytransact.testsupport import BLMTests, Time
from accounting import config, mail, payson, seqr
import members
from members import base64long
import blm.members
from Crypto.PublicKey import DSA
from Crypto.Hash import SHA

from accounting.test.blmsupport import PermissionTests

import decimal

import sys
if sys.version_info < (3,0,0):
    PYT3 = False
else:
    PYT3 =True
    import codecs

class TestProduct(BLMTests):

    def setup_method(self, method):
        super(TestProduct, self).setup_method(method)
        self.org = blm.accounting.Org()

    def test_price(self):
        accounting = blm.accounting.Accounting(org=self.org)
        blm.accounting.Account(number=['1000'], accounting=accounting)
        blm.accounting.Account(number=['2000'], accounting=accounting)
        blm.accounting.Account(number=['3000'], vatPercentage=['25'],
                               accounting=accounting)

        product = blm.members.Product(org=[self.org], name=['foo'])
        assert product.price == [decimal.Decimal(0)]

        product(accountingRules={'1000': '1.50', '2000': '8.50'},
                vatAccount=['3000'])
        assert product.price == [decimal.Decimal('12.50')] # (1.5 + 8.5) + 25%

    def test_no_vat(self):
        product = blm.members.Product(org=[self.org], name=['foo'],
                                      vatAccount=[''])
        assert product.vatAccount == []

    def purchase(self, product, **kw):
        item = blm.members.PurchaseItem(product=product, **kw)
        return blm.members.Purchase(items=[item])

    def test_stock(self):
        # don't keep track of stock if totalStock isn't set
        product = blm.members.Product(name=['unlimited'], org=[self.org])
        assert product.totalStock == []
        assert product.quantitySold == [0]
        assert product.currentStock == []

        self.purchase(product)
        assert product.totalStock == []
        assert product.quantitySold == [1]
        assert product.currentStock == []

        # keep track of stock when it's set
        product = blm.members.Product(name=['limited'], org=[self.org],
                                      totalStock=[5])
        assert product.currentStock == [5]

        self.purchase(product)
        assert product.quantitySold == [1]
        assert product.currentStock == [4]

        self.purchase(product, quantity=2)
        assert product.quantitySold == [3]
        assert product.currentStock == [2]

        self.purchase(product, quantity=2)
        assert product.quantitySold == [5]
        assert product.currentStock == [0]

        failure = py.test.raises(ClientError, self.purchase, product, quantity=2)
        assert failure.value.args[0].message == {
            'code': 'out of stock',
            'product': product.id[0],
            'remaining': 0
            }
        self.commit()

        product = blm.members.Product(name=['renewable'], org=[self.org],
                                      totalStock=[5])
        self.purchase(product)
        assert product.quantitySold == [1] # sanity
        assert product.currentStock == [4] # sanity
        self.commit()

        product, = blm.members.Product._query(name='renewable').run()
        product(totalStock=[10])
        assert product.quantitySold == [1]
        assert product.currentStock == [9]

    def test_delete(self):
        product = blm.members.Product(name=['foo'], org=[self.org])
        product._delete()

        assert not blm.members.Product._query().run()

        # can't delete products that have been sold
        product = blm.members.Product(name=['foo'], org=[self.org])
        pitem = blm.members.PurchaseItem(product=[product])
        py.test.raises(ClientError, product._delete)

        # can't delete products that are currently on display
        product = blm.members.Product(name=['foo'], org=[self.org], available=[True])
        py.test.raises(ClientError, product._delete)

    def test_copy(self):
        product = blm.members.Product(
            name=[u'Räksmörgås'],
            org=[self.org],
            available=[True],
            availableFrom=['2010-01-01'],
            availableTo=['2010-12-31'],
            description=[u'Gôrsmarrig macka'],
            notes=[u'Rödlistade räkor'],
            optionFields=['\x1f'.join('abcde'),
                          '\x1f'.join('fghij')],
            tags=[u'Räkor', u'Mat'],
            totalStock=[42],
            accountingRules={'1000': '10', '2000': '20'},
            image=['imagedata'])
        product.quantitySold = [10]
        product.sold = [True]

        copy, = blm.members.copyProduct([product])

        assert copy.name == [u'Kopia av Räksmörgås']
        assert copy.org == [self.org]
        assert copy.available == [False] # reset to False
        assert copy.availableFrom == ['2010-01-01']
        assert copy.availableTo == ['2010-12-31']
        assert copy.description == [u'Gôrsmarrig macka']
        assert copy.notes == [u'Rödlistade räkor']
        assert copy.optionFields == ['\x1f'.join('abcde'),
                                        '\x1f'.join('fghij')]
        assert copy.tags == [u'Räkor', u'Mat']
        assert copy.totalStock == [42]
        assert copy.quantitySold == [0] # reset to zero
        assert copy.accountingRules == {'1000': decimal.Decimal('10'),
                                        '2000': decimal.Decimal('20')}
        assert copy.image[0].read() == b'imagedata'
        assert copy.sold == [False] # reset to False


class TestProductTags(BLMTests):

    def setup_method(self, method):
        super(TestProductTags, self).setup_method(method)
        self.org = blm.accounting.Org()

    def mkProduct(self, *tags):
        return blm.members.Product(org=[self.org], name=['foo'], tags=tags)

    def tags(self):
        return sorted(tag.tag[0] for tag in
                      blm.members.ProductTag._query(org=self.org).run())

    def test_tagging(self):
        assert not self.tags()

        p1 = self.mkProduct('foo')
        assert self.tags() == ['foo']

        p2 = self.mkProduct('foo', 'bar')
        assert self.tags() == ['bar', 'foo']

        p3 = self.mkProduct('foo', 'baz')
        assert self.tags() == ['bar', 'baz', 'foo']

        self.commit()

        p1, p2, p3 = sorted(blm.members.Product._query().run(),
                            key=lambda toi: toi.id)

        p3._delete()
        assert self.tags() == ['bar', 'foo']

        p2(tags=['bar', 'quz'])
        assert self.tags() == ['bar', 'foo', 'quz']

        p2(tags=['quz'])
        assert self.tags() == ['foo', 'quz']


class TestIzettleProduct(BLMTests):

    def setup_method(self, method):
        super(TestIzettleProduct, self).setup_method(method)
        self.org = blm.accounting.Org()

    def test_update(self):
        product = blm.members.IzettleProduct(org=[self.org], name=['foo'], izPrice=[0],
                                             vatPercentage=[0], productId=['f'*22])
        product.update([{'accountingRules': {'2222': 1001}}])
        assert product.accountingRules == {'2222': decimal.Decimal('10.01')}

        
class TestIzettlePayment(BLMTests):

    def setup_method(self, method):
        super(TestIzettlePayment, self).setup_method(method)
        
        self.org = blm.accounting.Org(subscriptionLevel='subscriber')
        
        self.provider = blm.accounting.IzettleProvider(
            org=self.org,
            series='A',
            account='1000',
            fee_account='1001',
            cash_account='1002'
        )

        self.prod1 = blm.members.IzettleProduct(
            org=[self.org], name=['Kaffe/te'], izPrice=[3],
            vatPercentage=[0], productId=['1'*22],
            accountingRules={'1111': decimal.Decimal('3.00')}
        )
        self.prod2 = blm.members.IzettleProduct(
            org=[self.org], name=['Kaka'], izPrice=[5],
            vatPercentage=[0], productId=['2'*22],
            accountingRules={'2222': decimal.Decimal('2.20'),
                             '2223': decimal.Decimal('2.80')}
        )
        self.prod3 = blm.members.IzettleProduct(
            org=[self.org], name=['Fika klubbhuset'], izPrice=[7],
            vatPercentage=[0], productId=['3'*22],
            accountingRules={'3333': decimal.Decimal('7.00')}
        )
        self.prod4 = blm.members.IzettleProduct(
            org=[self.org], name=[u'Läsk'], izPrice=[11],
            vatPercentage=[0], productId=['4'*22],
            accountingRules={'4444': decimal.Decimal('11.00')}
        )
        self.prod5 = blm.members.IzettleProduct(
            org=[self.org], name=[u'Diskborste'], izPrice=[13],
            vatPercentage=[0], productId=['5'*22],
            accountingRules={'5555': decimal.Decimal('17.00')}
        )
        
        self.accounting = accounting = blm.accounting.Accounting(org=self.org)
        self.account0 = blm.accounting.Account(accounting=accounting, number='1000')
        self.accountfee = blm.accounting.Account(accounting=accounting, number='1001')
        self.accountcash = blm.accounting.Account(accounting=accounting, number='1002')
        self.account1 = blm.accounting.Account(accounting=accounting, number='1111')
        self.account2 = blm.accounting.Account(accounting=accounting, number='2222')
        self.account23 = blm.accounting.Account(accounting=accounting, number='2223')
        self.account3 = blm.accounting.Account(accounting=accounting, number='3333')
        self.account4 = blm.accounting.Account(accounting=accounting, number='4444')
        self.account5 = blm.accounting.Account(accounting=accounting, number='5555')

        description = [u'Kaffe/te, Kaka, Fika klubbhuset, 2 x Läsk']
        amount = 3+5+7+11+11
        self.payment = blm.members.IzettlePayment(
            org=self.org,
            description=description,
            izettle_fee=1,
            amount=amount,
            receipt_number=1,
            transaction_time='14:10:00',
            cashier='Arne Anka',
            last_digits='5555',
            device='uPhone',
            payment_class='card',
            card_type='Plastic dough',
            netto=amount-1,
            paymentProvider=self.provider
        )
        

    def test_product_map(self):
        map, _, accountmap = blm.members.IzettleProduct.product_map(self.org)
        assert map  == {
            'Kaffe/te': [(self.account1, decimal.Decimal(3))],
            'Kaka': [(self.account2, decimal.Decimal('2.2')),
                     (self.account23, decimal.Decimal('2.8'))],
            'Fika klubbhuset': [(self.account3, decimal.Decimal(7))],
            u'Läsk': [(self.account4, decimal.Decimal(11))]
        }
        provider, = blm.accounting.IzettleProvider._query(
            org=self.org, _attrList='account series'.split()).run()
        provideraccount = accountmap[provider.account[0]]
        fee_account = accountmap[provider.fee_account[0]]
        assert provideraccount == self.account0
        assert fee_account == self.accountfee
        
    def test_parse_description(self):
        map, toimap, accountmap = blm.members.IzettleProduct.product_map(self.org)

        result = self.payment.parse_description(map, toimap)
        assert result == [(self.account1, 'Kaffe/te', 1, [], decimal.Decimal(3)),
                          (self.account2, 'Kaka', 1, [], decimal.Decimal('2.2')),
                          (self.account23, 'Kaka', 1, [], decimal.Decimal('2.8')),
                          (self.account3, 'Fika klubbhuset', 1, [], decimal.Decimal(7)),
                          (self.account4, u'Läsk', 2, [], decimal.Decimal(11)*2)]

    def test_suggestVerification(self):
        suggestion, = self.payment.suggestVerification()
            
        assert suggestion['matchedPurchase'] == None
        assert suggestion['valid'] == True
        assert suggestion['balanced'] == True
        assert suggestion['missingAccounts'] == []
        assert suggestion['series'] == 'A'
        assert suggestion['accounting'] == self.accounting.id[0]
        assert suggestion['paymentProvider'] == True
        
        transactions = suggestion['transactions']
        assert transactions == [
            {'account': {'id': self.account0.id[0],
                         'number': u'1000'},
             'amount': {'decimal': decimal.Decimal('37.00'), 'json': 3700},
             'text': u'iZettle (Arne Anka)(1): Kaffe/te, Kaka, Fika klubbhuset, 2 x Läsk'},
            {'account': {'id': self.account1.id[0],
                         'number': u'1111'},
             'amount': {'decimal': decimal.Decimal('-3.00'), 'json': -300},
             'text': u'Kaffe/te'},
            {'account': {'id': self.account2.id[0],
                         'number': u'2222'},
             'amount': {'decimal': decimal.Decimal('-2.20'), 'json': -220},
             'text': u'Kaka'},
            {'account': {'id': self.account23.id[0],
                         'number': u'2223'},
             'amount': {'decimal': decimal.Decimal('-2.80'), 'json': -280},
             'text': u'Kaka'},
            {'account': {'id': self.account3.id[0],
                         'number': u'3333'},
             'amount': {'decimal': decimal.Decimal('-7.00'), 'json': -700},
             'text': u'Fika klubbhuset'},
            {'account': {'id': self.account4.id[0],
                         'number': u'4444'},
             'amount': {'decimal': decimal.Decimal('-22.00'), 'json': -2200},
             'text': u'Läsk (2)'},
            {'account': {'id': self.account0.id[0], 'number': u'1000'},
             'amount': {'decimal': decimal.Decimal('-1.00'), 'json': -100},
             'text': 'iZettle fee'},
            {'account': {'id': self.accountfee.id[0], 'number': u'1001'},
             'amount': {'decimal': decimal.Decimal('1.00'), 'json': 100},
             'text': 'iZettle fee'}
        ]

class TestIzettleRebate(BLMTests):
    def setup_method(self, method):
        super(TestIzettleRebate, self).setup_method(method)
        
        self.org = blm.accounting.Org(subscriptionLevel='subscriber')
        
        self.provider = blm.accounting.IzettleProvider(
            org=self.org,
            series='A',
            account='1000',
            fee_account='1111')

        self.accounting = accounting = blm.accounting.Accounting(org=self.org)
        self.account0 = blm.accounting.Account(accounting=accounting, number='1000')
        self.account1 = blm.accounting.Account(accounting=accounting, number='1111')

        self.payment = blm.members.IzettleRebate(
            org=self.org,
            amount=decimal.Decimal('3213.00'),
            transaction_time='14:10:00',
            transaction_type=u'Insättning',
            timespan='2016-08-01 - 2016-08-31',
            paymentProvider=self.provider
        )

    def test_suggestVerification(self):
        suggestion, = self.payment.suggestVerification()
            
        assert suggestion['matchedPurchase'] == None
        assert suggestion['valid'] == True
        assert suggestion['balanced'] == True
        assert suggestion['missingAccounts'] == []
        assert suggestion['series'] == 'A'
        assert suggestion['accounting'] == self.accounting.id[0]
        assert suggestion['paymentProvider'] == True
        
        transactions = suggestion['transactions']
        assert transactions == [
            {'account': {'id': self.account0.id[0],
                         'number': u'1000'},
             'amount': {'decimal': decimal.Decimal('3213.00'), 'json': 321300},
             'text': u'iZettle: Insättning 2016-08-01 - 2016-08-31'},
            {'account': {'id': self.account1.id[0],
                         'number': u'1111'},
             'amount': {'decimal': decimal.Decimal('-3213.00'), 'json': -321300},
             'text': u'iZettle: Insättning 2016-08-01 - 2016-08-31'},
        ]

        
class TestPurchase(BLMTests):

    def setup_method(self, method):
        super(TestPurchase, self).setup_method(method)
        self.config = config.save()
        self.org = blm.accounting.Org(name='ACME', email=['info@acme.com'])
        vc25 = blm.accounting.VatCode(code='10', percentage='25', xmlCode='xml25')
        vc12 = blm.accounting.VatCode(code='11', percentage='12', xmlCode='xml12')

        accounting = blm.accounting.Accounting(org=self.org)
        self.account1234 = blm.accounting.Account(number='1234',
                                                  accounting=accounting)
        self.vatAccount2025 = blm.accounting.Account(number='2025', vatCode='10',
                                                     accounting=accounting)
        self.vatAccount2012 = blm.accounting.Account(number='2012', vatCode='11',
                                                     accounting=accounting)
        self.product1 = blm.members.Product(org=[self.org], name=['foo'],
                                            accountingRules={'1234': '20'},
                                            vatAccount='2025')
        assert self.product1.price == [decimal.Decimal(25)]  # sanity

        self.product2 = blm.members.Product(org=[self.org], name=['bar'],
                                            accountingRules={'1234': '50'},
                                            vatAccount='2012',
                                            optionFields=['\x1f'.join('abcde')],
                                            makeTicket=[True])
        assert self.product2.price == [decimal.Decimal(56)]  # sanity

        self.product3 = blm.members.Product(org=[self.org], name=['baz'],
                                            accountingRules={'1234': '10'})
        assert self.product3.price == [decimal.Decimal(10)]  # sanity

        # Free product
        self.product4 = blm.members.Product(org=[self.org], name=['qux'],
                                            makeTicket=[True])
        assert self.product4.price == [decimal.Decimal(0)]  # sanity

        self.time = Time()

    def teardown_method(self, method):
        super(TestPurchase, self).teardown_method(method)
        config.restore(self.config)
        self.time.restore()

    def test_purchase_method(self):
        result, = blm.members.purchase(
            data=[
                dict(
                    items=[{'product': str(self.product1.id[0]),
                            'price': self.product1.price[0],
                            'quantity': 2,
                            'total': self.product1.price[0] * 2},
                           {'product': str(self.product2.id[0]),
                            'price': self.product2.price[0],
                            'quantity': 1,
                            'options': ['foo'],
                            'total': self.product2.price[0]}
                           ],
                    total=[self.product1.price[0] * 2 + self.product2.price[0]],
                    date=[1000000000],
                )
            ])

        purchase, = blm.members.Purchase._query(id=ObjectId(result['purchase'])).run()

        assert purchase.kind == ['purchase']
        assert purchase.paymentState == ['unpaid']
        assert purchase.date == [1000000000]
        assert purchase.org[0] == self.org
        assert result['invoiceUrl'] == purchase.invoiceUrl[0]

        item1, item2 = purchase.items
        assert item1.product[0] == self.product1
        assert item1.quantity[0] == 2
        assert item1.options == []
        assert item1.price == self.product1.price
        assert item1.total[0] == self.product1.price[0] * 2

        assert item2.product[0] == self.product2
        assert item2.options == ['foo']

        assert purchase.total[0] == (self.product1.price[0] * 2 +
                                     self.product2.price[0])

    def test_costless_purchase_considered_paid(self):
        purchase = blm.members.Purchase(
            org=self.org,
            items=[blm.members.PurchaseItem(product=self.product4)])
        assert purchase.paymentState == ['paid']

    def test_urls(self):
        purchase = blm.members.Purchase(org=self.org)
        invoice = 'http://xyz/invoice/%s/%s' % (purchase.id[0],
                                                purchase.random[0])
        tickets = 'http://xyz/getTickets/%s/%s' % (purchase.id[0],
                                                   purchase.random[0])

        config.config.set('accounting', 'baseurl', 'http://xyz')
        assert purchase.invoiceUrl == [invoice]
        assert purchase.ticketsUrl == [tickets]

        config.config.set('accounting', 'baseurl', 'http://xyz/')
        assert purchase.invoiceUrl == [invoice]
        assert purchase.ticketsUrl == [tickets]

        # support old tois without random attribute
        purchase.random = []

        invoice = 'http://xyz/invoice/%s' % purchase.id[0]
        tickets = 'http://xyz/getTickets/%s' % purchase.id[0]

        config.config.set('accounting', 'baseurl', 'http://xyz')
        assert purchase.invoiceUrl == [invoice]
        assert purchase.ticketsUrl == [tickets]

        config.config.set('accounting', 'baseurl', 'http://xyz/')
        assert purchase.invoiceUrl == [invoice]
        assert purchase.ticketsUrl == [tickets]

    def test_confirmation_email(self, monkeypatch):
        calls = []
        def sendmail(*args, **kw):
            assert kw['identity'] == str(purchase.org[0].id[0])
            calls.append(args)
        monkeypatch.setattr(mail, 'sendmail', sendmail)
        config.config.set('accounting', 'baseurl', 'http://xyz/')
        config.config.set('accounting', 'smtp_domain', 'example.com')
        purchase = blm.members.Purchase(
            items=[blm.members.PurchaseItem(product=self.product1)],
            buyerEmail=['foo@test'])

        purchase.sendConfirmationEmail()

        assert purchase.confirmationEmailSent[0]

        (fromaddr, all_recipients, body), = calls
        assert fromaddr == str(purchase.org[0].id[0])
        assert all_recipients == ['foo@test']
        assert '\nFrom: %s <no-reply@example.com>\n' % (
            purchase.org[0].name[0]) in body
        assert '\nTo: <foo@test>\n' in body
        assert '\nReply-to: %s <%s>\n' % (purchase.org[0].name[0],
                                      purchase.org[0].email[0]) in body
        assert 'X-oe-mailtype: order-confirmation' in body
        body = email.message_from_string(body).get_payload()
        if PYT3:
            body = codecs.decode(body.encode('utf-8'), 'base64').decode()
        else:
            body = body.decode('base64').decode('utf-8')
        assert self.org.name[0] in body
        assert purchase.invoiceUrl[0] in body

    def test_invoice_confirmation_email(self, monkeypatch):
        calls = []
        def sendmail(*args, **kw):
            assert kw['identity'] == str(purchase.org[0].id[0])
            calls.append(args)
        monkeypatch.setattr(mail, 'sendmail', sendmail)
        config.config.set('accounting', 'baseurl', 'http://xyz/')
        config.config.set('accounting', 'smtp_domain', 'example.com')
        purchase = blm.members.Invoice(
            items=[blm.members.PurchaseItem(product=self.product1)],
            buyerEmail=['foo@test'])

        purchase.sendConfirmationEmail()

        assert purchase.confirmationEmailSent[0]

        (fromaddr, all_recipients, body), = calls
        assert fromaddr == str(purchase.org[0].id[0])
        assert all_recipients == ['foo@test']
        assert '\nFrom: %s <no-reply@example.com>\n' % (
            purchase.org[0].name[0]) in body
        assert '\nTo: <foo@test>\n' in body
        assert '\nReply-to: %s <%s>\n' % (purchase.org[0].name[0],
                                      purchase.org[0].email[0]) in body
        assert 'X-oe-mailtype: invoice-confirmation' in body
        body = email.message_from_string(body).get_payload()
        if PYT3:
            body = codecs.decode(body.encode('utf-8'), 'base64').decode()
        else:
            body = body.decode('base64').decode('utf-8')
        assert self.org.name[0] in body
        assert purchase.invoiceUrl[0] in body

    def test_send_reminder_email(self, monkeypatch):
        calls = []
        def sendmail(*args, **kw):
            assert kw['identity'] == str(purchase.org[0].id[0])
            calls.append(args)
        monkeypatch.setattr(mail, 'sendmail', sendmail)
        config.config.set('accounting', 'baseurl', 'http://xyz/')
        config.config.set('accounting', 'smtp_domain', 'example.com')
        purchase = blm.members.Purchase(
            items=[blm.members.PurchaseItem(product=self.product1)],
            buyerEmail=['foo@test'])

        now1 = self.time.time()
        purchase.sendReminderEmail()
        assert purchase.reminderEmailsSent == [now1]

        (fromaddr, all_recipients, body), = calls
        assert fromaddr == str(purchase.org[0].id[0])
        assert all_recipients == ['foo@test']
        assert '\nFrom: %s <no-reply@example.com>\n' % (
            purchase.org[0].name[0]) in body
        assert '\nTo: <foo@test>\n' in body
        assert '\nReply-to: %s <%s>\n' % (purchase.org[0].name[0],
                                      purchase.org[0].email[0]) in body
        assert '\nX-oe-mailtype: purchase-reminder\n' in body
        body = email.message_from_string(body).get_payload()
        if PYT3:
            body = codecs.decode(body.encode('utf-8'), 'base64').decode()
        else:
            body = body.decode('base64').decode('utf-8')
        assert self.org.name[0] in body
        assert purchase.invoiceUrl[0] in body

        self.time.step()
        now2 = self.time.time()
        purchase.sendReminderEmail()
        assert purchase.reminderEmailsSent == [now1, now2]

    def test_validate_org(self):
        org2 = blm.accounting.Org()
        prod3 = blm.members.Product(org=[org2], name=['baz'])
        py.test.raises(ClientError, blm.members.purchase,
            data=[dict(
                    items=[{'product': str(self.product1.id[0])},
                           {'product': str(prod3.id[0])}],
                    total=['27']
                    )])

    def test_update_total(self):
        item1 = blm.members.PurchaseItem(product=[self.product1])
        purchase = blm.members.Purchase(org=[self.org], items=[item1])
        assert purchase.total == [decimal.Decimal('25')]  # 20 + 25%
        item2 = blm.members.PurchaseItem(product=[self.product2],
                                         purchase=[purchase])
        assert purchase.total == [decimal.Decimal('81')]

    def test_validate_total_price(self):
        py.test.raises(ClientError, blm.members.purchase,
            data=[dict(
                    items=[{'product': str(self.product1.id[0]),
                            'price': self.product1.price[0],
                            'quantity': 2,
                            'total': self.product1.price[0] * 2}
                           ],
                    total=['14'])
                  ])

    def test_ocr(self):
        purchase = blm.members.Purchase(org=[self.org])
        assert purchase.ocr[0]

    def test_vat(self):
        purchase = blm.members.Purchase(
            org=self.org,
            items=[blm.members.PurchaseItem(product=self.product1, quantity=2),
                   blm.members.PurchaseItem(product=self.product2, quantity=3),
                   blm.members.PurchaseItem(product=self.product3)])

        # prod 1, tot price = 2 * 25. 25% tax is 2 * 5.
        # prod 2, tot price = 3 * 56. 12% tax is 3 * 6.
        # prod 3, no vat

        assert purchase.vat == [
            ('10', decimal.Decimal('25.00'), decimal.Decimal('10')),
            ('11', decimal.Decimal('12.00'), decimal.Decimal('18'))]

    def test_maketickets(self):
        costly = blm.members.PurchaseItem(product=self.product2, quantity=[2])
        free = blm.members.PurchaseItem(product=self.product4, quantity=[2])
        purchase = blm.members.Purchase(items=[costly, free])

        tickets = purchase.maketickets()  # Create the free tickets
        assert len(tickets) == 2
        t1, t2 = sorted(tickets, key=lambda toi: toi.id[0])
        assert t1.purchaseitem[0] == t2.purchaseitem[0] == free
        assert len(set(t.qrcode[0] for t in tickets)) == 2
        assert len(set(t.barcode[0] for t in tickets)) == 2

        blm.members.Payment(org=[self.org], matchedPurchase=[purchase],
                            amount=purchase.total)

        _t1, _t2 = t1, t2

        tickets = purchase.maketickets()
        assert len(tickets) == 4
        t1, t2, t3, t4 = sorted(tickets, key=lambda toi: toi.id[0])
        assert t1 is _t1 and t2 is _t2
        assert t1.purchaseitem[0] == t2.purchaseitem[0] == free
        assert t3.purchaseitem[0] == t4.purchaseitem[0] == costly
        assert len(set(t.qrcode[0] for t in tickets)) == 4
        assert len(set(t.barcode[0] for t in tickets)) == 4

        assert set(tickets) == set(purchase.maketickets())

    def test_partial_payments(self):
        purchase = blm.members.Purchase(
            items=[blm.members.PurchaseItem(product=self.product1)])
        assert purchase.paymentState == ['unpaid']
        assert purchase.remainingAmount == purchase.total

        payment = blm.members.Payment(matchedPurchase=purchase, amount='10',
                                      org=self.org)
        assert purchase.paymentState == ['partial']
        assert purchase.remainingAmount == [purchase.total[0] - 10]

        payment = blm.members.Payment(matchedPurchase=purchase, amount='7',
                                      org=self.org)
        assert purchase.paymentState == ['partial']
        assert purchase.remainingAmount == [purchase.total[0] - 10 - 7]

        payment = blm.members.Payment(matchedPurchase=purchase, amount='8',
                                      org=self.org)
        assert purchase.paymentState == ['paid']
        assert purchase.remainingAmount == [decimal.Decimal('0')]

    def test_suggestVerification(self):
        purchase = blm.members.Purchase(
            buyerName=['Nissegurra Aktersnurra'],
            items=[
                blm.members.PurchaseItem(product=self.product1),
                blm.members.PurchaseItem(product=self.product2, quantity=2)
            ])
        suggestion = purchase.suggestVerification()
        assert suggestion == {
            'transactions': [
                {'account': None,
                 'text': 'Nissegurra Aktersnurra',
                 'amount': 13700},
                {'account': self.account1234.id[0],
                 'text': 'Nissegurra Aktersnurra, foo',
                 'amount': -2000},
                {'account': self.vatAccount2025.id[0],
                 'text': 'Nissegurra Aktersnurra, foo',
                 'amount': -500},
                {'account': self.account1234.id[0],
                 'text': 'Nissegurra Aktersnurra, bar (2)',
                 'amount': -10000},
                {'account': self.vatAccount2012.id[0],
                 'text': 'Nissegurra Aktersnurra, bar (2)',
                 'amount': -1200},
            ]
        }

    def test_confirmationEmailTemplate(self):
        costly = blm.members.Purchase(
            org=self.org,
            items=[blm.members.PurchaseItem(product=self.product1)])
        assert costly.paymentState == ['unpaid']  # Sanity
        assert costly.confirmationEmailTemplate == ['email/order-confirmation']

        free = blm.members.Purchase(org=self.org)
        assert free.paymentState == ['paid']  # Sanity
        assert free.total == [0]  # Sanity
        assert free.confirmationEmailTemplate == ['email/order-confirmation-free']

    def test_canBeCredited(self):
        purchase = blm.members.Purchase(
            org=self.org,
            items=[blm.members.PurchaseItem(product=self.product1)])

        # Unpaid purchases can not be credited
        assert purchase.paymentState == ['unpaid']
        assert purchase.canBeCredited == [False]

        # Paid payments can be credited
        payment = blm.members.Payment(matchedPurchase=purchase,
                                      amount=purchase.total)
        assert purchase.paymentState == ['paid']
        assert purchase.canBeCredited == [True]

        # ...unless their total is zero
        purchase.total = [0]
        assert purchase.canBeCredited == [False]

        purchase.total = [123]
        assert purchase.canBeCredited == [True]  # Sanity

        # Cancelled purchases can not be credited either
        purchase.cancelled = [True]
        assert purchase.canBeCredited == [False]


class TestInvoice(BLMTests):

    def setup_method(self, method):
        super(TestInvoice, self).setup_method(method)
        self.org = blm.accounting.Org()
        self.product = blm.members.Product(org=[self.org], name=['A product'],
                                           accountingRules={'1000': '10'})
        assert self.product.price == [decimal.Decimal(10)]  # Sanity
        self.time = Time()

    def teardown_method(self, method):
        super(TestInvoice, self).teardown_method(method)
        self.time.restore()

    def test_invoice(self):
        invoice = blm.members.Invoice(org=[self.org])
        assert invoice.kind == ['invoice']
        assert invoice.sent == [False]
        assert invoice.expiryDate == [time.time() + invoice.expiryDate.expiryPeriod]

        invoice = blm.members.Invoice(org=[self.org], expiryDate=[12])
        assert invoice.expiryDate == [12]

    def test_confirmationEmailTemplate(self):
        costly = blm.members.Invoice(
            org=self.org,
            items=[blm.members.PurchaseItem(product=self.product)])
        assert costly.paymentState == ['unpaid']  # Sanity
        assert costly.confirmationEmailTemplate == ['email/invoice-confirmation']

        free = blm.members.Invoice(org=self.org)
        assert free.paymentState == ['paid']  # Sanity
        assert free.total == [0]  # Sanity
        assert free.confirmationEmailTemplate == ['email/invoice-confirmation-free']

    def test_canBeCredited(self):
        invoice = blm.members.Invoice(org=self.org)

        # Unpaid invoices can be credited
        invoice.paymentState = ['unpaid']
        assert invoice.canBeCredited == [True]

        # Paid invoices can be credited too
        invoice.paymentState = ['paid']
        assert invoice.canBeCredited == [True]

        # Invoices can only be credited once
        invoice.paymentState = ['credited']
        assert invoice.canBeCredited == [False]

        # Invoices with partial payments can not be credited
        invoice.paymentState = ['partial']
        assert invoice.canBeCredited == [False]


class Test_create_purchase_or_invoice(BLMTests):

    def setup_method(self, method):
        super(Test_create_purchase_or_invoice, self).setup_method(method)
        self.org = blm.accounting.Org()
        self.product1 = blm.members.Product(org=self.org, name='Product 1',
                                            accountingRules={'1000': '10'})
        self.other_product = blm.members.Product(org=blm.accounting.Org(),
                                                 name='Other product',
                                                 accountingRules={'1000': '10'})

    def test_whitelist(self):
        sane = {'org': str(self.org.id[0]),
                'items': [{'product': str(self.product1.id[0]),
                           'quantity': 2}],
                'buyerAnnotation': 'this stuff is awesome',
                'total': '20'}

        # sanity
        blm.members.create_purchase_or_invoice(blm.members.Purchase,
                                               [copy.deepcopy(sane)])

        bad_data = {
            'paymentState': ['paid'],
            'cancelled': [True],
            'total': [27],
            'items': [{'product': str(self.other_product.id[0])}]
            }
        for attrName, value in bad_data.items():
            data = copy.deepcopy(sane)
            data[attrName] = value
            with py.test.raises(ClientError):
                blm.members.create_purchase_or_invoice(blm.members.Purchase,
                                                       [data])


class TestCrediting(BLMTests):

    def setup_method(self, method):
        super(TestCrediting, self).setup_method(method)
        self.org = blm.accounting.Org(name='ACME', email=['info@acme.com'])
        vc25 = blm.accounting.VatCode(code='10', percentage='25', xmlCode='xml25')
        vc12 = blm.accounting.VatCode(code='11', percentage='12', xmlCode='xml12')

        accounting = blm.accounting.Accounting(org=self.org)
        vatAccount = blm.accounting.Account(number='2025', vatCode='10',
                                            accounting=accounting)
        vatAccount = blm.accounting.Account(number='2012', vatCode='11',
                                            accounting=accounting)
        self.product1 = blm.members.Product(org=[self.org], name=['foo'],
                                            accountingRules={'1234': '20'},
                                            vatAccount='2025')
        assert self.product1.price == [decimal.Decimal(25)]  # sanity
        self.product2 = blm.members.Product(org=[self.org], name=['bar'],
                                            accountingRules={'1234': '50'},
                                            vatAccount='2012',
                                            optionFields=['\x1f'.join('abcde')],
                                            makeTicket=[True])
        assert self.product2.price == [decimal.Decimal(56)]  # sanity
        self.product3 = blm.members.Product(org=[self.org], name=['baz'],
                                            accountingRules={'1234': '10'})
        assert self.product3.price == [decimal.Decimal(10)]  # sanity
        self.time = Time()

    def test_credit_unpaid_invoice(self):
        invoice = blm.members.Invoice(
            buyerName=['Mr. Foo'],
            buyerAddress=['The Street 1'],
            buyerEmail=['foo@test'],
            items=[blm.members.PurchaseItem(product=self.product1),
                   blm.members.PurchaseItem(product=self.product2, quantity=2)])
        invoice.paymentState = ['unpaid']
        self.time.step()

        credit, = blm.members.createCreditInvoice(invoice=[invoice])
        assert invoice.paymentState == ['credited']

        assert credit.credited == [invoice]
        assert credit.org == invoice.org
        assert credit.random != invoice.random
        assert credit.cancelled == [False]
        assert credit.paymentState == ['paid']
        assert credit.date == [self.time]

        assert credit.total != [-invoice.total[0]]
        assert credit.total == [decimal.Decimal('0.00')]

        assert credit.ocr != invoice.ocr
        assert credit.buyerName == invoice.buyerName
        assert credit.buyerAddress == invoice.buyerAddress
        assert credit.buyerPhone == invoice.buyerPhone
        assert credit.buyerEmail == invoice.buyerEmail
        assert credit.matchedPayments == []

        assert len(credit.items) != len(invoice.items)
        assert len(credit.items) == 0

        #   no longer possible to test since credit has no items
        # for inv_item, cred_item in zip(invoice.items, credit.items):
        #     assert cred_item.price == inv_item.price
        #     assert cred_item.product == inv_item.product
        #     assert cred_item.quantity == [-inv_item.quantity[0]]
        #     assert cred_item.total == [decimal.Decimal(0)]  # [-inv_item.total[0]]
        #     assert cred_item.vatCode == inv_item.vatCode
        #     assert cred_item.vatAccount == inv_item.vatAccount
        #     assert cred_item.vatPercentage == inv_item.vatPercentage
        #     assert cred_item.totalVat == [decimal.Decimal(0)]  # [-inv_item.totalVat[0]]
        #     assert cred_item.accountingRules == inv_item.accountingRules
        #     assert cred_item.options == inv_item.options
        #     assert cred_item.optionFields == inv_item.optionFields

    def test_credit_paid_invoice(self):
        invoice = blm.members.Invoice(
            buyerName=['Mr. Foo'],
            buyerAddress=['The Street 1'],
            buyerEmail=['foo@test'],
            items=[blm.members.PurchaseItem(product=self.product1),
                   blm.members.PurchaseItem(product=self.product2, quantity=2)])
        invoice.paymentState = ['paid']
        invoice.matchedPayments = [blm.members.Payment(amount=invoice.total)]
        self.time.step()

        credit, = blm.members.createCreditInvoice(invoice=[invoice])
        assert invoice.paymentState == ['credited']

        assert credit.credited == [invoice]
        assert credit.org == invoice.org
        assert credit.random != invoice.random
        assert credit.cancelled == [False]
        assert credit.paymentState == ['unpaid']
        assert credit.date == [self.time]
        assert credit.total == [-invoice.total[0]]
        assert credit.ocr != invoice.ocr
        assert credit.buyerName == invoice.buyerName
        assert credit.buyerAddress == invoice.buyerAddress
        assert credit.buyerPhone == invoice.buyerPhone
        assert credit.buyerEmail == invoice.buyerEmail
        assert credit.matchedPayments == []
        assert credit.originalPayments == invoice.matchedPayments

        assert len(invoice.items) ==  len(credit.items)
        for inv_item, cred_item in zip(invoice.items, credit.items):
            assert cred_item.price == inv_item.price
            assert cred_item.product == inv_item.product
            assert cred_item.quantity == [-inv_item.quantity[0]]
            assert cred_item.total == [-inv_item.total[0]]
            assert cred_item.vatCode == inv_item.vatCode
            assert cred_item.vatAccount == inv_item.vatAccount
            assert cred_item.vatPercentage == inv_item.vatPercentage
            assert cred_item.totalVat == [-inv_item.totalVat[0]]
            assert cred_item.accountingRules == inv_item.accountingRules
            assert cred_item.options == inv_item.options
            assert cred_item.optionFields == inv_item.optionFields

    def test_credit_partially_paid_invoice(self):
        invoice = blm.members.Invoice(
            buyerName=['Mr. Foo'],
            buyerAddress=['The Street 1'],
            buyerEmail=['foo@test'],
            items=[blm.members.PurchaseItem(product=self.product1),
                   blm.members.PurchaseItem(product=self.product2, quantity=2)])
        invoice.paymentState = ['partial']
        self.time.step()

        with py.test.raises(ClientError):
            # crediting partial payments is unsupported
            blm.members.createCreditInvoice(invoice=[invoice])

    def test_credit_credited_invoice(self):
        invoice = blm.members.Invoice(
            buyerName=['Mr. Foo'],
            buyerAddress=['The Street 1'],
            buyerEmail=['foo@test'],
            items=[blm.members.PurchaseItem(product=self.product1),
                   blm.members.PurchaseItem(product=self.product2, quantity=2)])
        invoice.paymentState = ['credited']

        with py.test.raises(ClientError):
            # you can't credit a credited invoice
            blm.members.createCreditInvoice(invoice=[invoice])

    def test_credit_credit_invoice(self):
        invoice = blm.members.Invoice(
            buyerName=['Mr. Foo'],
            buyerAddress=['The Street 1'],
            buyerEmail=['foo@test'],
            items=[blm.members.PurchaseItem(product=self.product1),
                   blm.members.PurchaseItem(product=self.product2, quantity=2)])

        credit = blm.members.CreditInvoice(credited=invoice)

        with py.test.raises(ClientError):
            # you can't credit a credit invoice
            blm.members.createCreditInvoice(invoice=[credit])

    def test_credit_unpaid_purchase(self):
        purchase = blm.members.Purchase(
            org=self.org,
            items=[blm.members.PurchaseItem(product=self.product1)])
        with py.test.raises(ClientError):
            blm.members.createCreditInvoice(invoice=[purchase])

    def test_refundable(self):
        purchase = blm.members.Invoice(org=self.org)
        credit = blm.members.CreditInvoice(credited=purchase)
        assert credit.refundable == [False]

        purchase = blm.members.Invoice(org=self.org)
        non_refundable_payment = blm.members.Payment()
        purchase.matchedPayments = [non_refundable_payment]
        credit = blm.members.CreditInvoice(credited=purchase)
        assert credit.refundable == [False]

        purchase = blm.members.Invoice(org=self.org)
        refundable_payment = blm.members.SimulatorPayment()
        purchase.matchedPayments = [refundable_payment]
        credit = blm.members.CreditInvoice(credited=purchase)
        assert credit.refundable == [True]

        # Ideally, we should handle this scenario, but we don't know how,
        # so let's say such purchases are non refundable for now
        purchase = blm.members.Invoice(org=self.org)
        purchase.matchedPayments = [non_refundable_payment,
                                    refundable_payment]
        credit = blm.members.CreditInvoice(credited=purchase)
        assert credit.refundable == [False]

    def test_refund(self):
        purchase = blm.members.Invoice(org=self.org)
        refundable_payment = blm.members.SimulatorPayment(
            amount=[20]
        )
        purchase.matchedPayments = [refundable_payment]
        purchase.paymentState = ['paid']

        credit = blm.members.CreditInvoice(credited=purchase)

        assert credit.matchedPayments == []  # sanity
        assert credit.paymentState == ['unpaid']  # sanity
        credit.refund()
        payment, = credit.matchedPayments
        assert payment.amount == [-20]
        assert credit.paymentState == ['paid']

    def test_canBeCredited(self):
        invoice = blm.members.Invoice(org=self.org)
        ci = blm.members.CreditInvoice(org=self.org, credited=invoice)

        # CreditInvoices can never be credited
        assert ci.canBeCredited == [False]


class TestPurchaseItem(BLMTests):

    def setup_method(self, method):
        super(TestPurchaseItem, self).setup_method(method)
        self.org = blm.accounting.Org()
        vatCode = blm.accounting.VatCode(code='10', percentage='15',
                                         xmlCode='blurg')
        self.accounting = blm.accounting.Accounting(org=self.org)
        self.account = blm.accounting.Account(number='2000', vatCode='10',
                                              accounting=self.accounting)
        self.product = blm.members.Product(org=[self.org], name=['foo'],
                                           accountingRules={'1234': '100'},
                                           vatAccount='2000',
                                           optionFields=['\x1f'.join('abcde'),
                                                         '\x1f'.join('fghij')])

    def test_defaults(self):
        item = blm.members.PurchaseItem(product=[self.product], quantity=[2])
        assert item.price == [decimal.Decimal('115')]
        assert item.total == [decimal.Decimal('230')]
        assert item.accountingRules == {'1234': decimal.Decimal('100.00')}
        assert item.vatAccount == ['2000']
        assert item.vatPercentage == [decimal.Decimal('15.00')]
        assert item.vatCode == ['10']

        item = blm.members.PurchaseItem(product=[self.product], quantity=[2],
                                        price=[decimal.Decimal('222')])
        assert item.price == [decimal.Decimal('222')]

        py.test.raises(ClientError, blm.members.PurchaseItem,
                       product=[self.product], total=['1'])

    def test_allOptionsWithValue(self):
        item = blm.members.PurchaseItem(product=[self.product],
                                        options=['', 'foo'])
        assert item.optionFields == ['\x1f'.join('abcde'),
                                     '\x1f'.join('fghij')]
        assert item.allOptionsWithValue == [('a', ''), ('f', 'foo')]

        self.product(optionFields=[])
        assert item.optionFields == ['\x1f'.join('abcde'),
                                     '\x1f'.join('fghij')]
        assert item.allOptionsWithValue == [('a', ''), ('f', 'foo')]

    def test_optionsWithValue(self):
        item = blm.members.PurchaseItem(product=[self.product],
                                        options=['', 'foo'])
        assert item.optionFields == ['\x1f'.join('abcde'),
                                     '\x1f'.join('fghij')]
        assert item.optionsWithValue == [('f', 'foo')]

        self.product(optionFields=[])
        assert item.optionFields == ['\x1f'.join('abcde'),
                                     '\x1f'.join('fghij')]
        assert item.optionsWithValue == [('f', 'foo')]

    def test_without_product(self):
        item = blm.members.PurchaseItem(quantity=[2], price=[decimal.Decimal('123')],
                                        allowRead = self.product.allowRead,
                                        name = ['gurka'])
        assert item.total == [decimal.Decimal('246')]

    def test_free_is_paid(self):
        item = blm.members.PurchaseItem(product=self.product, quantity=[2],
                                        price=[0], name=['gurka'])
        assert item.paid == [True]

    def test_unpaid_purchase_is_unpaid(self):
        item = blm.members.PurchaseItem(product=self.product, quantity=[2],
                                        price=[1], name=['gurka'])
        purchase = blm.members.Purchase(items=[item])
        assert item.paid == [False]

    def test_paid_purchase_is_paid(self):
        item = blm.members.PurchaseItem(product=self.product, quantity=[2],
                                        price=[1], name=['gurka'])
        purchase = blm.members.Purchase(items=[item])
        purchase.paymentState = ['paid']
        assert item.paid == [True]



class TestTicket(BLMTests):

    def setup_method(self, method):
        super(TestTicket, self).setup_method(method)
        self.config = config.save()
        self.org = blm.accounting.Org()
        self.product = blm.members.Product(org=[self.org], name=['foo'],
                                           accountingRules={'1234': '27'},
                                           optionFields=['\x1f'.join('abcde'),
                                                         '\x1f'.join('fghij')])
        self.tktproduct = blm.members.Product(org=[self.org], name=['foo'],
                                              accountingRules={'1234': '27'},
                                              optionFields=['\x1f'.join('abcde'),
                                                            '\x1f'.join('fghij')],
                                              makeTicket=[True])
        key = self.key = DSA.generate(512)
        self.baseurl = 'http://xyz'
        config.config.set('accounting', 'baseurl', self.baseurl)
        config.config.set('accounting', 'ticket_key',
                          json.dumps([key.y, key.g, key.p, key.q, key.x]))

    def teardown_method(self, method):
        super(TestTicket, self).teardown_method(method)
        config.restore(self.config)

    def test_ticket(self):
        item = blm.members.PurchaseItem(product=[self.product])

        ticket = blm.members.Ticket(purchaseitem=[item])

        assert ticket.org == [self.org]
        expect_qr = self.baseurl + '/ticket/%(ticket)s/%(random)s/%(product)s/' % {
            'ticket' : ticket.id[0],
            'random' : base64long.encode(ticket.random[0]),
            'product': self.product.id[0]}
        assert ticket.name == item.name
        assert ticket.options == item.optionsWithValue
        assert ticket.qrcode[0].startswith(expect_qr)
        signature = map(base64long.decode, ticket.qrcode[0][len(expect_qr):].split('/'))
        if PYT3:
            h = SHA.new(expect_qr.encode('ascii')).digest()
        else:
            h = SHA.new(expect_qr).digest()
        self.key.verify(h, signature)

        barcode = ticket.barcode[0]
        assert len(barcode) == 40
        if PYT3:
            assert all(map(str.isdigit, barcode))
        else:
            assert all(map(unicode.isdigit, barcode))
        assert ticket.random[0] == int(barcode) & 0xffffffff
        assert int(str(ticket.id[0]),16) == int(barcode) >> 32

    def test_ticket_random32(self):
        item = blm.members.PurchaseItem(product=[self.product])

        ticket = blm.members.Ticket(purchaseitem=[item], random=[0x123456789])

        assert ticket.random == [0x23456789]

        ticket(random=[0x987654321])

        assert ticket.random == [0x87654321]

    def test_ticket_random_change(self):
        item = blm.members.PurchaseItem(product=[self.product])

        ticket = blm.members.Ticket(purchaseitem=[item], random=[0x123456789])
        rand1 = ticket.random[0]

        ticket(random=[])
        assert ticket.random[0] != rand1

class TestPayment(BLMTests):

    def setup_method(self, method):
        super(TestPayment, self).setup_method(method)
        self.org = blm.accounting.Org()
        self.accountant = blm.accounting.User()
        self.member = blm.accounting.User()
        self.org.ug[0](users=[self.accountant, self.member])
        self.org.accountants = [self.accountant]
        self.commit()
        self.org, = blm.accounting.Org._query(id=self.org.id).run()

        self.accounting = blm.accounting.Accounting(org=self.org)
        self.series, = self.accounting.ensureSeries()
        self.account1000 = blm.accounting.Account(number='1000', accounting=self.accounting)
        self.account2000 = blm.accounting.Account(number='2000', accounting=self.accounting)
        self.account3000 = blm.accounting.Account(number='3000', accounting=self.accounting)
        self.account4000 = blm.accounting.Account(number='4000', accounting=self.accounting)
        self.account5000 = blm.accounting.Account(number='5000', accounting=self.accounting,
                                                  vatPercentage='25')

        self.account = self.account1000
        self.provider = blm.accounting.PaymentProvider(
            org=[self.org], series=['A'], account=['1000'])

        self.product1 = blm.members.Product(org=self.org, name='Product 1',
                                            accountingRules={'2000': '150',
                                                             '3000': '50'})
        self.product2 = blm.members.Product(org=self.org, name='Product 2',
                                            accountingRules={'3000': '75',
                                                             '4000': '25'},
                                            vatAccount='5000')

    def test_calc_buyer_descr(self):
        purchase = blm.members.Purchase(org=self.org, buyerName=['Arne Anka'])

        payment = blm.members.Payment(paymentProvider=self.provider)
        assert payment.buyerdescr == []

        payment = blm.members.Payment(paymentProvider=self.provider,
                                      matchedPurchase=purchase)
        assert payment.buyerdescr == ['Arne Anka']

    def test_suggestVerification_unmatched(self):
        payment = blm.members.Payment(paymentProvider=self.provider,
                                      transaction_date=['2010-01-01'],
                                      amount=['100'])
        suggestion, = payment.suggestVerification()
        assert suggestion['paymentProvider'] == True
        assert suggestion['matchedPurchase'] == None
        assert suggestion['valid'] == False
        assert suggestion['balanced'] == False
        assert suggestion['missingAccounts'] == []
        assert suggestion['series'] == 'A'
        assert suggestion['transaction_date'] == '2010-01-01'
        assert suggestion['accounting'] == self.accounting.id[0]

        transaction, = suggestion['transactions']
        assert transaction['account'] == {'id': self.account1000.id[0],
                                          'number': '1000'}
        assert transaction['amount'] == {'decimal': decimal.Decimal('100'),
                                         'json': 10000}

    def test_suggestVerification_matched_balanced_and_valid(self):
        purchase = blm.members.Purchase(
            org=self.org,
            items=[blm.members.PurchaseItem(product=self.product1, quantity=2),
                   blm.members.PurchaseItem(product=self.product2)])

        payment = blm.members.Payment(paymentProvider=self.provider,
                                      matchedPurchase=[purchase],
                                      buyerdescr=['Arne Anka'],
                                      amount=['525'])

        suggestion, = payment.suggestVerification()
        assert suggestion['matchedPurchase'] == purchase
        assert suggestion['valid'] == True
        assert suggestion['balanced'] == True
        assert suggestion['missingAccounts'] == []
        assert suggestion['series'] == 'A'
        assert suggestion['accounting'] == self.accounting.id[0]


        # One transaction that goes into the debit account specified
        # by the provider, and one transaction for each account used
        # in the accounting rules.
        debit_trans, \
            trans_p1_2000, trans_p1_3000, \
            trans_p2_3000, trans_p2_4000, \
            trans_p2_5000 = suggestion['transactions']

        assert debit_trans['account'] == {'id': self.account1000.id[0],
                                          'number': '1000'}
        assert debit_trans['amount'] == {'decimal': decimal.Decimal('525'),
                                         'json': 52500}
        assert debit_trans['text'] == 'Arne Anka'

        assert trans_p1_2000['account'] == {'id': self.account2000.id[0],
                                            'number': '2000'}
        assert trans_p1_2000['amount'] == {'decimal': decimal.Decimal('-300'), # 150 * 2
                                           'json': -30000}
        assert trans_p1_2000['text'] == 'Arne Anka, Product 1 (2)'

        assert trans_p1_3000['account'] == {'id': self.account3000.id[0],
                                            'number': '3000'}
        assert trans_p1_3000['amount'] == {'decimal': decimal.Decimal('-100'), # 50 * 2
                                           'json': -10000}
        assert trans_p1_3000['text'] == 'Arne Anka, Product 1 (2)'

        assert trans_p2_3000['account'] == {'id': self.account3000.id[0],
                                            'number': '3000'}
        assert trans_p2_3000['amount'] == {'decimal': decimal.Decimal('-75'),
                                           'json': -7500}
        assert trans_p2_3000['text'] == 'Arne Anka, Product 2'

        assert trans_p2_4000['account'] == {'id': self.account4000.id[0],
                                            'number': '4000'}
        assert trans_p2_4000['amount'] == {'decimal': decimal.Decimal('-25'),
                                           'json': -2500}
        assert trans_p2_4000['text'] == 'Arne Anka, Product 2'

        assert trans_p2_5000['account'] == {'id': self.account5000.id[0],
                                            'number': '5000'}
        assert trans_p2_5000['amount'] == {'decimal': decimal.Decimal('-25'),
                                           'json': -2500}
        assert trans_p2_5000['text'] == 'Arne Anka, Product 2'


    def test_suggestVerification_matched_balanced_missing_accounts(self):
        self.product1.accountingRules = {'2000': '150', '3001': '50'}
        purchase = blm.members.Purchase(
            org=self.org,
            items=[blm.members.PurchaseItem(product=self.product1)])

        payment = blm.members.Payment(paymentProvider=self.provider,
                                      matchedPurchase=[purchase],
                                      buyerdescr=['Arne Anka'],
                                      amount=['200'])

        suggestion, = payment.suggestVerification()
        assert suggestion['matchedPurchase'] == purchase
        assert suggestion['valid'] == False
        assert suggestion['balanced'] == True
        assert suggestion['missingAccounts'] == ['3001']
        assert suggestion['series'] == 'A'
        assert suggestion['accounting'] == self.accounting.id[0]

        debit_trans, trans_2000, trans_3001 = suggestion['transactions']

        assert debit_trans['account'] == {'id': self.account1000.id[0],
                                          'number': '1000'}
        assert debit_trans['amount'] == {'decimal': decimal.Decimal('200'),
                                         'json': 20000}
        assert debit_trans['text'] == 'Arne Anka'

        assert trans_2000['account'] == {'id': self.account2000.id[0],
                                         'number': '2000'}
        assert trans_2000['amount'] == {'decimal': decimal.Decimal('-150'),
                                        'json': -15000}
        assert trans_2000['text'] == 'Arne Anka, Product 1'

        assert trans_3001['account'] == {'id': None,
                                         'number': '3001'}
        assert trans_3001['amount'] == {'decimal': decimal.Decimal('-50'),
                                        'json': -5000}
        assert trans_3001['text'] == 'Arne Anka, Product 1'

    def test_suggestVerification_no_provider(self):
        purchase = blm.members.Purchase(
            org=self.org,
            items=[blm.members.PurchaseItem(product=self.product1)])

        payment = blm.members.Payment(matchedPurchase=[purchase],
                                      org=self.org,
                                      buyerdescr=['Arne Anka'],
                                      amount=['200'])

        suggestion, = payment.suggestVerification()
        assert suggestion['paymentProvider'] == False
        assert suggestion['matchedPurchase'] == purchase
        assert suggestion['valid'] == False
        assert suggestion['balanced'] == True
        assert suggestion['missingAccounts'] == []
        assert suggestion['series'] == None
        assert suggestion['accounting'] == self.accounting.id[0]

    def test_suggestVerification_empty_provider(self):
        self.provider.series = []
        self.provider.account = []
        purchase = blm.members.Purchase(
            org=self.org,
            items=[blm.members.PurchaseItem(product=self.product1)])

        payment = blm.members.Payment(paymentProvider=self.provider,
                                      matchedPurchase=[purchase],
                                      buyerdescr=['Arne Anka'],
                                      amount=['200'])

        suggestion, = payment.suggestVerification()
        assert suggestion['matchedPurchase'] == purchase
        assert suggestion['valid'] == False
        assert suggestion['balanced'] == True
        assert suggestion['missingAccounts'] == []
        assert suggestion['series'] == None
        assert suggestion['accounting'] == self.accounting.id[0]

    def test_suggestVerification_matched_unbalaneced(self):
        self.product1.accountingRules = {'2000': '100'}

        purchase = blm.members.Purchase(
            org=self.org,
            items=[blm.members.PurchaseItem(product=self.product1)])

        payment = blm.members.Payment(paymentProvider=self.provider,
                                      matchedPurchase=[purchase],
                                      buyerdescr=['Arne Anka'],
                                      amount=['200']) # 100 too much

        suggestion, = payment.suggestVerification()
        assert suggestion['matchedPurchase'] == purchase
        assert suggestion['valid'] == False
        assert suggestion['balanced'] == False
        assert suggestion['missingAccounts'] == []
        assert suggestion['series'] == 'A'
        assert suggestion['accounting'] == self.accounting.id[0]

        debit_trans, trans_2000 = suggestion['transactions']

        assert debit_trans['account'] == {'id': self.account1000.id[0],
                                          'number': '1000'}
        assert debit_trans['amount'] == {'decimal': decimal.Decimal('200'),
                                         'json': 20000}
        assert debit_trans['text'] == 'Arne Anka'

        assert trans_2000['account'] == {'id': self.account2000.id[0],
                                         'number': '2000'}
        assert trans_2000['amount'] == {'decimal': decimal.Decimal('-100'),
                                        'json': -10000}
        assert trans_2000['text'] == 'Arne Anka, Product 1'

    def test_approvePayment(self):
        payment = blm.members.Payment(paymentProvider=self.provider)

        paymentId = str(payment.id[0])
        data = {
            'payment': str(payment.id[0]),
            'transaction_date': '2010-01-01',
            'series': str(self.series.id[0]),
            'transactions': [
                {'amount': '1234',
                 'text': 'Some text',
                 'account': str(self.account.id[0])
                 }
                ]
            }
        self.commit()

        self.ctx.setUser(self.member)
        with py.test.raises(ClientError):
            blm.members.approvePayment([data.copy()])
        self.pushnewctx() # get rid of junk left in context during failed commit

        self.ctx.setUser(self.accountant)

        result = blm.members.approvePayment([data])
        self.commit()

        account, = blm.accounting.Account._query(id=self.account.id).run()

        verId = ObjectId(result[0]['verification'])
        verification, = blm.accounting.Verification._query(id=verId).run()

        assert verification.accounting == [self.accounting]
        assert verification.series == [self.series]
        assert verification.externalRef == [paymentId]
        assert verification.transaction_date == ['2010-01-01']

        transaction, = verification.transactions
        assert transaction.account == [account]
        assert transaction.amount == [decimal.Decimal('12.34')]
        assert transaction.text == ['Some text']

        assert account.balance == [decimal.Decimal('12.34')]

    def test_approvePayments_matching(self):
        purchase1 = blm.members.Purchase(
            org=self.org,
            items=[blm.members.PurchaseItem(product=self.product1)])
        purchase2 = blm.members.Purchase(
            org=self.org,
            items=[blm.members.PurchaseItem(product=self.product2)])
        purchase3 = blm.members.Purchase(
            org=self.org,
            items=[blm.members.PurchaseItem(product=self.product2)])
        purchase5 = blm.members.Purchase(
            org=self.org,
            items=[blm.members.PurchaseItem(product=self.product2)])

        payment1 = blm.members.Payment(paymentProvider=self.provider,
                                       amount=[200],
                                       transaction_date=['2010-01-01'],
                                       matchedPurchase=[purchase1])
        payment2 = blm.members.Payment(paymentProvider=self.provider,
                                       amount=[125],
                                       transaction_date=['2010-01-02'],
                                       matchedPurchase=[purchase2])

        # partial payment, skip silently
        payment3 = blm.members.Payment(paymentProvider=self.provider,
                                       amount=[25],
                                       transaction_date=['2010-01-03'],
                                       matchedPurchase=[purchase3])

        # this payment does not match a purchase, skip silently
        payment4 = blm.members.Payment(paymentProvider=self.provider,
                                       amount=[50],
                                       transaction_date=['2010-01-04'])

        # already approved
        payment5 = blm.members.Payment(paymentProvider=self.provider,
                                       amount=[100],
                                       transaction_date=['2010-01-05'],
                                       matchedPurchase=[purchase5],
                                       approved=[True])
        self.commit()

        self.ctx.setUser(self.member)
        with py.test.raises(ClientError):
            blm.members.approvePayments([payment1])
        self.pushnewctx() # get rid of junk left in context during failed commit

        self.ctx.setUser(self.accountant)

        result = blm.members.approvePayments(
            [payment1, payment2, payment3, payment4, payment5])
        assert result == [payment1, payment2]
        self.commit()

        ver1, ver2 = sorted(blm.accounting.Verification._query().run(),
                            # externalRef = payment id
                            key=lambda t: t.externalRef[0])

        assert ver1.externalRef == [str(payment1.id[0])]
        assert ver1.transaction_date == ['2010-01-01']
        assert len(ver1.transactions) == 3
        assert ver1.transactions[0].account == [self.account1000]
        assert ver1.transactions[0].amount == [decimal.Decimal(200)]
        assert ver1.transactions[1].account == [self.account2000]
        assert ver1.transactions[1].amount == [decimal.Decimal(-150)]
        assert ver1.transactions[2].account == [self.account3000]
        assert ver1.transactions[2].amount == [decimal.Decimal(-50)]

        assert ver2.externalRef == [str(payment2.id[0])]
        assert ver2.transaction_date == ['2010-01-02']
        assert len(ver2.transactions) == 4
        assert ver2.transactions[0].account == [self.account1000]
        assert ver2.transactions[0].amount == [decimal.Decimal(125)]
        assert ver2.transactions[1].account == [self.account3000]
        assert ver2.transactions[1].amount == [decimal.Decimal(-75)]
        assert ver2.transactions[2].account == [self.account4000]
        assert ver2.transactions[2].amount == [decimal.Decimal(-25)]
        assert ver2.transactions[3].account == [self.account5000]
        assert ver2.transactions[3].amount == [decimal.Decimal(-25)]

        # make sure we've tickled the balance recalculation code
        assert self.account1000.balance == [decimal.Decimal(325)]
        assert self.account2000.balance == [decimal.Decimal(-150)]
        assert self.account3000.balance == [decimal.Decimal(-125)]
        assert self.account4000.balance == [decimal.Decimal(-25)]
        assert self.account5000.balance == [decimal.Decimal(-25)]

    def test_generateFakePayment(self):
        provider = blm.accounting.SimulatorProvider(org=self.org)
        purchase = blm.members.Purchase(
            org=self.org,
            items=[blm.members.PurchaseItem(product=self.product1)])


        payment = blm.members.generateFakePayment([provider], [purchase])

        with py.test.raises(LocalisedError):
            # can't use non simulator providers
            blm.members.generateFakePayment([self.provider], [purchase])

        member = blm.accounting.User()
        self.org.ug[0](users=[member])

        self.ctx.setUser(member)
        payment = blm.members.generateFakePayment([provider], [purchase])

        haxxor = blm.accounting.User()
        self.ctx.setUser(haxxor)
        with py.test.raises(ClientError):
            blm.members.generateFakePayment([provider], [purchase])

        org2 = blm.accounting.Org()
        pp2 = blm.accounting.SimulatorProvider(org=org2)

        with py.test.raises(ClientError):
            # don't use providers from other orgs to pay!
            blm.members.generateFakePayment([pp2], [purchase])

    def test_manual_payment(self):
        purchase = blm.members.Purchase(
            org=self.org,
            items=[blm.members.PurchaseItem(product=self.product1)])
        verificationData = {
            'transaction_date': '2010-01-01',
            'series': str(self.series.id[0]),
            'transactions': [
                {'account': str(self.account1000.id[0]), 'text': 'foo',
                 'amount': 20000},
                {'account': str(self.account2000.id[0]), 'text': 'bar',
                 'amount': -15000},
                {'account': str(self.account3000.id[0]), 'text': 'baz',
                 'amount': -5000},
            ]
        }

        payment, = blm.members.manualPayment_ex([purchase], [verificationData])
        assert purchase.paymentState == ['paid']
        assert payment.paymentProvider == self.org.manual_payment_provider

        member = blm.accounting.User()
        self.org.ug[0](users=[member])

        self.ctx.setUser(member)
        payment, = blm.members.manualPayment_ex([purchase], [verificationData])

        haxxor = blm.accounting.User()
        self.ctx.setUser(haxxor)
        with py.test.raises(ClientError):
            blm.members.manualPayment_ex([purchase], [verificationData])


class TestSimulatorPayments(BLMTests):

    def setup_method(self, method):
        super(TestSimulatorPayments, self).setup_method(method)
        self.org = blm.accounting.Org(name='ACME', email=['info@acme.com'])
        self.provider = blm.accounting.SimulatorProvider(org=self.org)
        self.product = blm.members.Product(org=[self.org], name=['foo'],
                                           accountingRules={'1234': '100'},
                                           makeTicket=[True])
        self.purchase = blm.members.Purchase(
            org=self.org,
            buyerName=[u'Räksmörgås, Åke'],
            buyerEmail=['foo@test'],
            items=[blm.members.PurchaseItem(product=self.product)])
        # sanity:
        assert self.purchase.total == [decimal.Decimal('100.00')]
        assert self.purchase.paymentState == ['unpaid']

    def test_refund(self):
        payment = blm.members.SimulatorPayment(
            org=self.org,
            paymentProvider=self.provider,
            matchedPurchase=self.purchase,
            amount=10)
        refund, = payment.refund()
        assert refund.org == payment.org
        assert refund.paymentProvider == payment.paymentProvider
        assert refund.allowRead == payment.allowRead
        assert refund.matchedPurchase == []
        assert refund.buyerdescr == payment.buyerdescr
        assert refund.amount == [-payment.amount[0]]


class TestPaysonPayments(BLMTests):

    def setup_method(self, method):
        super(TestPaysonPayments, self).setup_method(method)
        self.org = blm.accounting.Org(name='ACME', email=['info@acme.com'],
                                      subscriptionLevel=['subscriber'])
        self.provider = blm.accounting.PaysonProvider(
            org=self.org,
            apiUserId='foo',
            apiPassword='password',
            receiverEmail='foo@test'
        )
        self.product = blm.members.Product(org=[self.org], name=['foo'],
                                           accountingRules={'1234': '100'},
                                           makeTicket=[True])
        self.purchase = blm.members.Purchase(
            org=self.org,
            buyerName=[u'Räksmörgås, Åke'],
            buyerEmail=['foo@test'],
            items=[blm.members.PurchaseItem(product=self.product)])
        # sanity:
        assert self.purchase.total == [decimal.Decimal('100.00')]
        assert self.purchase.paymentState == ['unpaid']
        self.payment = blm.members.PaysonPayment(
            org=self.org,
            paymentProvider=self.provider,
            matchedPurchase=self.purchase,
            purchaseId='payson-purchase-id',
            senderEmail='bar@test',
            token='token',
            receiverFee=decimal.Decimal(10),
            receiverEmail='foo@test',
            type='TRANSFER')

        self.time = Time()

    def teardown_method(self, method):
        super(TestPaysonPayments, self).teardown_method(method)
        self.time.restore()

    def test_refundable(self):
        assert self.payment.refundable[0]

        non_transfer_payment = blm.members.PaysonPayment(
            org=self.org,
            paymentProvider=self.provider,
            matchedPurchase=self.purchase,
            purchaseId='payson-purchase-id',
            senderEmail='bar@test',
            token='token',
            receiverFee=decimal.Decimal(10),
            receiverEmail='foo@test',
            type='INVOICE')
        assert not non_transfer_payment.refundable[0]

    def test_refund(self, monkeypatch):
        def refund(*args):
            assert args == (self.payment,)
            return True

        monkeypatch.setattr(payson, 'refund', refund)
        refund, = self.payment.refund()

        assert refund.org == self.payment.org
        assert refund.paymentProvider == self.payment.paymentProvider
        assert refund.token == self.payment.token
        assert refund.purchaseId == self.payment.purchaseId
        assert refund.allowRead == self.payment.allowRead
        assert refund.matchedPurchase == []
        assert refund.buyerdescr == self.payment.buyerdescr
        assert refund.amount == [-self.payment.amount[0]]
        assert refund.refundable == [False]
        assert refund.type == ['refund']

    def test_refund_failed(self, monkeypatch):
        def refund(*args):
            assert args == (self.payment.id[0],)
            raise payson.PaysonError(1, 'foo')

        monkeypatch.setattr(payson, 'refund', refund)
        py.test.raises(ClientError, self.payment.refund)


class TestSeqrPayments(BLMTests):

    def setup_method(self, method):
        super(TestSeqrPayments, self).setup_method(method)
        self.org = blm.accounting.Org(name='ACME', email=['info@acme.com'],
                                      subscriptionLevel=['subscriber'])
        self.provider = blm.accounting.SeqrProvider(
            org=self.org,
            principalId='principalid',
            password='password',
        )
        self.product = blm.members.Product(org=[self.org], name=['foo'],
                                           accountingRules={'1234': '100'},
                                           makeTicket=[True])
        self.purchase = blm.members.Purchase(
            org=self.org,
            buyerName=[u'Räksmörgås, Åke'],
            buyerEmail=['foo@test'],
            items=[blm.members.PurchaseItem(product=self.product)])
        # sanity:
        assert self.purchase.total == [decimal.Decimal('100.00')]
        assert self.purchase.paymentState == ['unpaid']
        self.payment = blm.members.SeqrPayment(
            org=self.org,
            paymentProvider=self.provider,
            matchedPurchase=self.purchase,
            paymentDate=0,
            invoiceReference='invoiceref',
            ersReference='ersref',
            paymentReference='paymentref',
            payerTerminalId='terminalid',
            receiverName='receivername',
            amount=10)

        self.time = Time()

    def teardown_method(self, method):
        super(TestSeqrPayments, self).teardown_method(method)
        self.time.restore()

    def test_refund(self, monkeypatch):
        def refund(*args):
            assert args == (self.payment.id[0],)
            return 'ersref2'

        monkeypatch.setattr(seqr, 'refund', refund)
        refund, = self.payment.refund()

        assert refund.org == self.payment.org
        assert refund.paymentProvider == self.payment.paymentProvider
        assert refund.payerTerminalId == []
        assert refund.ersReference == ['ersref2']
        assert refund.allowRead == self.payment.allowRead
        assert refund.matchedPurchase == []
        assert refund.paymentDate == [self.time()]
        assert refund.buyerdescr == self.payment.buyerdescr
        assert refund.amount == [-self.payment.amount[0]]

    def test_refund_failed(self, monkeypatch):
        def refund(*args):
            assert args == (self.payment.id[0],)
            raise seqr.SeqrError(1, 'foo')

        monkeypatch.setattr(seqr, 'refund', refund)
        py.test.raises(Exception, self.payment.refund)


class TestStripePayments(BLMTests):

    def setup_method(self, method):
        super(TestStripePayments, self).setup_method(method)
        self.org = blm.accounting.Org(name='ACME', email=['info@acme.com'],
                                      subscriptionLevel=['subscriber'])
        self.provider = blm.accounting.StripeProvider(
            org=self.org, access_token=['access_token'], currency=['EUR'])
        self.product = blm.members.Product(org=[self.org], name=['foo'],
                                           accountingRules={'1234': '100'},
                                           makeTicket=[True])
        self.purchase = blm.members.Purchase(
            org=self.org,
            buyerName=[u'Räksmörgås, Åke'],
            buyerEmail=['foo@test'],
            items=[blm.members.PurchaseItem(product=self.product)])
        # sanity:
        assert self.purchase.total == [decimal.Decimal('100.00')]
        assert self.purchase.paymentState == ['unpaid']
        self.payment = blm.members.StripePayment(
            org=[self.org],
            paymentProvider=[self.provider],
            matchedPurchase=[self.purchase],
            paymentDate=[1],
            currency=['EUR'],
            charge_id=['charge-id'],
            amount=['27.42'])

    def test_refund(self, monkeypatch):
        def refund():
            refund = stripe.resource.Refund()
            refund.update(dict(
                id='refund-id',
                amount=2742,
                currency='eur',
                created=2,
                charge='charge-id',
            ))
            return refund

        @staticmethod
        def retrieve(id, api_key):
            assert api_key == self.provider.access_token[0]
            assert id == 'charge-id'
            charge = stripe.Charge()
            charge.update(dict(
                id=id,
                created=1,
                amount=2742,
                currency='eur',
            ))
            class refunds(object): pass
            charge.refunds = refunds()
            charge.refunds.create = refund
            return charge

        monkeypatch.setattr(stripe.Charge, 'retrieve', retrieve)

        refund_payment, = self.payment.refund()

        assert refund_payment.charge_id == ['refund-id']
        assert refund_payment.amount == [decimal.Decimal('-27.42')]
        assert refund_payment.currency == ['EUR']
        assert refund_payment.paymentDate == [2]
        assert refund_payment.json_data

    def test_handleStripeInvoice(self, monkeypatch):
        event = {
            "id": "evt_15lCxbGwBXZNMVzOpi8QTFWE",
            "created": 1427522299,
            "livemode": False,
            "type": "invoice.created",
            "data": {
            "object": {
            "date": 1427125273,
            "id": "in_15jXfxGwBXZNMVzOFjiAPM5D",
            "period_start": 1427125157,
            "period_end": 1427125273,
            "lines": {
            "data": [
            {
            "id": "sub_5xtLYpoHehBSH9",
            "object": "line_item",
            "type": "subscription",
            "livemode": True,
            "amount": 4200,
            "currency": "sek",
            "proration": False,
            "period": {
            "start": 1430379852,
            "end": 1432971852
            },
            "subscription": None,
            "quantity": 1,
            "plan": {
            "interval": "month",
            "name": "Test plan",
            "created": 1426508070,
            "amount": 4200,
            "currency": "sek",
            "id": "test_plan",
            "object": "plan",
            "livemode": False,
            "interval_count": 1,
            "trial_period_days": None,
            "metadata": {
            },
            "statement_descriptor": None
            },
            "description": None,
            "discountable": True,
            "metadata": {
            }
            }
            ],
            "total_count": 1,
            "object": "list",
            "url": "/v1/invoices/in_15jXfxGwBXZNMVzOFjiAPM5D/lines"
            },
            "subtotal": 4200,
            "total": 4200,
            "customer": "cus_5siYkZlxniAMpu",
            "object": "invoice",
            "attempted": True,
            "closed": True,
            "forgiven": False,
            "paid": True,
            "livemode": False,
            "attempt_count": 1,
            "amount_due": 4200,
            "currency": "sek",
            "starting_balance": 0,
            "ending_balance": 0,
            "next_payment_attempt": None,
            "webhooks_delivered_at": None,
            "charge": "ch_15jXfxGwBXZNMVzOeWIAqsE3",
            "discount": None,
            "application_fee": None,
            "subscription": "sub_5vOSXTPzl0KIPx",
            "tax_percent": None,
            "tax": None,
            "metadata": {
            },
            "statement_descriptor": None,
            "description": None,
            "receipt_number": None }
            },
            "object": "event",
            "pending_webhooks": 2,
            "request": None,
            "api_version": "2015-02-18"
            }

        customers = { "cus_5siYkZlxniAMpu" :
                      stripe.convert_to_stripe_object(
            {
            "object": "customer",
  "created": 1426508107,
  "id": "cus_5siYkZlxniAMpu",
  "livemode": False,
  "description": "test customer 1",
  "email": "test@openend.se",
  "delinquent": False,
  "metadata": {
  },
  "subscriptions": {
    "object": "list",
    "total_count": 1,
    "has_more": False,
    "url": "/v1/customers/cus_5siYkZlxniAMpu/subscriptions",
    "data": [
      {
        "id": "sub_5vOSXTPzl0KIPx",
        "plan": {
          "interval": "month",
          "name": "Test plan",
          "created": 1426508070,
          "amount": 4200,
          "currency": "sek",
          "id": "test_plan",
          "object": "plan",
          "livemode": False,
          "interval_count": 1,
          "trial_period_days": None,
          "metadata": {
          },
          "statement_descriptor": None
        },
        "object": "subscription",
        "start": 1427125273,
        "status": "active",
        "customer": "cus_5siYkZlxniAMpu",
        "cancel_at_period_end": False,
        "current_period_start": 1427125273,
        "current_period_end": 1429803673,
        "ended_at": None,
        "trial_start": None,
        "trial_end": None,
        "canceled_at": None,
        "quantity": 1,
        "application_fee_percent": None,
        "discount": None,
        "tax_percent": None,
        "metadata": {
        }
      }
    ]
  },
  "discount": None,
  "account_balance": 0,
  "currency": "sek",
  "sources": {
    "object": "list",
    "total_count": 1,
    "has_more": False,
    "url": "/v1/customers/cus_5siYkZlxniAMpu/sources",
    "data": [
      {
        "id": "card_15gx8BGwBXZNMVzO8JTimOA8",
        "object": "card",
        "last4": "4242",
        "brand": "Visa",
        "funding": "credit",
        "exp_month": 3,
        "exp_year": 2016,
        "country": "US",
        "name": None,
        "address_line1": None,
        "address_line2": None,
        "address_city": None,
        "address_state": None,
        "address_zip": None,
        "address_country": None,
        "cvc_check": "pass",
        "address_line1_check": None,
        "address_zip_check": None,
        "dynamic_last4": None,
        "metadata": {
        },
        "customer": "cus_5siYkZlxniAMpu"
      }
    ]
  },
  "default_source": "card_15gx8BGwBXZNMVzO8JTimOA8"
} , 'foo')
        }

        monkeypatch.setattr(stripe.resource.APIResource, 'refresh',
                            lambda self: self)
        monkeypatch.setattr(stripe.Customer, 'retrieve',
                            staticmethod(lambda custid, *args, **kw: customers.get(custid)))
        monkeypatch.setattr(stripe.Invoice, 'save', lambda s: event['data']['object'].update(s))

        purchase, = blm.members.handleStripeInvoice([event], [self.provider])
        assert purchase.org == [self.org]
        assert purchase.total == [decimal.Decimal(42)]
        assert purchase.buyerName == ['test customer 1']
        assert purchase.paymentState == ['paid']
        purchaseitem = purchase.items[0]
        assert purchaseitem.total == [decimal.Decimal(42)]


    #def test_handleStripeCharge(self, monkeypatch):
        charge_event = {
            "id": "evt_15lCxbGwBXZNMVzOpi8QTFWE",
            "created": 1427522299,
            "livemode": False,
            "type": "charge.succeeded",
            "data": {
            "object": {
              "id": "ch_15jXfxGwBXZNMVzOeWIAqsE3",
              "object": "charge",
              "created": 1427125273,
              "livemode": False,
              "paid": True,
              "status": "succeeded",
              "amount": 4200,
              "currency": "sek",
              "refunded": False,
              "source": {
                "id": "card_15gx8BGwBXZNMVzO8JTimOA8",
                "object": "card",
                "last4": "4242",
                "brand": "Visa",
                "funding": "credit",
                "exp_month": 3,
                "exp_year": 2016,
                "country": "US",
                "name": None,
                "address_line1": None,
                "address_line2": None,
                "address_city": None,
                "address_state": None,
                "address_zip": None,
                "address_country": None,
                "cvc_check": None,
                "address_line1_check": None,
                "address_zip_check": None,
                "dynamic_last4": None,
                "metadata": {
                },
                "customer": "cus_5siYkZlxniAMpu"
              },
              "captured": True,
              "balance_transaction": "txn_15PAH8GwBXZNMVzOtWIXmBeO",
              "failure_message": None,
              "failure_code": None,
              "amount_refunded": 0,
              "customer": "cus_5siYkZlxniAMpu",
              "invoice": "in_15jXfxGwBXZNMVzOFjiAPM5D",
              "description": None,
              "dispute": None,
              "metadata": {
              },
              "statement_descriptor": None,
              "fraud_details": {
              },
              "receipt_email": None,
              "receipt_number": None,
              "shipping": None,
              "application_fee": None,
              "refunds": {
                "object": "list",
                "total_count": 0,
                "has_more": False,
                "url": "/v1/charges/ch_15jXfxGwBXZNMVzOeWIAqsE3/refunds",
                "data": [

                ]
              }
            }
            },
            "object": "event",
            "pending_webhooks": 2,
            "request": None,
            "api_version": "2015-02-18"
            }

        monkeypatch.setattr(stripe.Invoice, 'retrieve',
                            staticmethod(lambda *args, **kw: stripe.convert_to_stripe_object(event['data']['object'], 'foo')))

        payment, = blm.members.handleStripeCharge([charge_event], [self.provider])
        assert payment.amount == [decimal.Decimal(42)]
        assert payment.matchedPurchase == [purchase]

class TestPaymentMails(BLMTests):

    def setup_method(self, method):
        super(TestPaymentMails, self).setup_method(method)
        self.config = config.save()
        self.org = blm.accounting.Org(name='ACME', email=['info@acme.com'])
        self.product = blm.members.Product(org=[self.org], name=['foo'],
                                           accountingRules={'1234': '100'},
                                           makeTicket=[True])
        self.purchase = blm.members.Purchase(
            org=self.org,
            buyerName=[u'Räksmörgås, Åke'],
            buyerEmail=['foo@test'],
            items=[blm.members.PurchaseItem(product=self.product)])
        # sanity:
        assert self.purchase.total == [decimal.Decimal('100.00')]
        assert self.purchase.paymentState == ['unpaid']

        self.mails = []
        def sendmail(*args, **kw):
            self.mails.append((args, kw))
        self._orig_sendmail = mail.sendmail
        mail.sendmail = sendmail

        config.config.set('accounting', 'baseurl', 'http://xyz/')
        config.config.set('accounting', 'smtp_domain', 'example.com')

    def teardown_method(self, method):
        super(TestPaymentMails, self).teardown_method(method)
        mail.sendmail = self._orig_sendmail
        config.restore(self.config)

    def _check_payment_mail(self, type, payment):
        assert payment.confirmationEmailSent == [False]  # sanity
        payment.sendConfirmationEmail()

        if type == 'full':
            if PYT3:
                subject = ('\nSubject: =?utf-8?q?Betalningsbekr=C3=A4ftelse_/'
                           '_Payment_acknowledgement_-_ACME?=\n')
            else:
                subject = ('\nSubject: =?utf-8?q?Betalningsbekr=C3=A4ftelse_/'
                           '_Payment_acknowledgement_-?=\n =?utf-8?q?_ACME?=\n')
        else:
            subject = ('\nSubject: =?utf-8?q?Bekr=C3=A4ftelse_delbetalning_/'
                       '_Partial_payment_-_ACME?=\n')

        ((fromaddr, all_recipients, content), kw), = self.mails
        assert fromaddr == str(payment.org[0].id[0])
        assert all_recipients == ['foo@test']
        if PYT3:
            assert '\nTo: =?utf-8?b?UsOka3Ntw7ZyZ8Olcywgw4VrZQ==?= <foo@test>\n' in content
        else:
            assert '\nTo: =?iso-8859-1?q?R=E4ksm=F6rg=E5s=2C_=C5ke?= <foo@test>\n' in content
        assert '\nFrom: %s <no-reply@example.com>\n' % (
            payment.org[0].name[0]) in content
        assert '\nReply-to: %s <%s>\n' % (
            payment.org[0].name[0], payment.org[0].email[0]) in content
        assert kw['identity'] == str(payment.org[0].id[0])
        assert 'X-oe-mailtype: %s-payment-confirmation' % type in content
        assert subject in content

        body = email.message_from_string(content).get_payload()
        if PYT3:
            body = codecs.decode(body.encode('utf-8'), 'base64').decode('utf-8')
        else:
            body = body.decode('base64').decode('utf-8')
        assert self.purchase.invoiceUrl[0] in body
        assert payment.confirmationEmailSent == [True]

        # ensure regular jinja2 rendering works
        payment.confirmationEmailSent = [False]
        payment.sendConfirmationEmail() # don't explode

    def test_match_with_purchase_fully_paid(self):
        payment = blm.members.Payment(
            org=[self.org],
            matchedPurchase=[self.purchase],
            amount = ['100.00'])
        assert self.purchase.paymentState == ['paid']
        assert self.purchase.tickets  # not empty
        self._check_payment_mail('full', payment)

        self.mails = []
        payment.sendConfirmationEmail() # nop when confirmationEmailSent is True
        assert self.mails == []

    def test_match_with_purchase_partial_payment(self):
        payment = blm.members.Payment(
            org=[self.org],
            matchedPurchase=[self.purchase],
            amount = ['50.00'])
        assert self.purchase.paymentState == ['partial']
        assert not self.purchase.tickets  # empty - partial payment
        self._check_payment_mail('partial', payment)
        self.mails = []

        payment = blm.members.Payment(
            org=[self.org],
            matchedPurchase=[self.purchase],
            amount = ['40.00'])
        assert self.purchase.paymentState == ['partial']
        assert not self.purchase.tickets  # empty - partial payment
        self._check_payment_mail('partial', payment)
        self.mails = []

        payment = blm.members.Payment(
            org=[self.org],
            matchedPurchase=[self.purchase],
            amount = ['10.00']) # finally!
        assert self.purchase.paymentState == ['paid']
        assert self.purchase.tickets  # not empty - paid in full now
        self._check_payment_mail('full', payment)
        self.mails = []

    def test_no_match(self, monkeypatch):
        payment = blm.members.Payment(
            org=[self.org],
            amount = ['50.00'])
        payment.sendConfirmationEmail()
        assert self.mails == []


class TestReadPermissions(BLMTests):

    def test_permissions(self):
        org = blm.accounting.Org()
        pp = blm.accounting.PaymentProvider(org=org)
        ug = org.ug[0]

        product = blm.members.Product(org=[org], name=['foo'], tags=['foo'], makeTicket=[True])
        assert product.allowRead == [ug]

        tag, = blm.members.ProductTag._query(org=[org], tag=['foo']).run()
        assert tag.allowRead == [ug]

        item = blm.members.PurchaseItem(product=[product])
        assert item.allowRead == [ug]

        purchase = blm.members.Purchase(org=[org], items=[item])
        assert purchase.allowRead == [ug]

        payment = blm.members.Payment(paymentProvider=[pp], matchedPurchase=[purchase])
        assert payment.allowRead == [ug] # match by pgnum

        tickets = purchase.maketickets()
        assert tickets[0].allowRead == [ug] + org.ticketchecker_ug


class TestAccountantPermissions(PermissionTests):

    def setup_method(self, method):
        super(TestAccountantPermissions, self).setup_method(method)
        self.accountant = blm.accounting.User()
        self.member = blm.accounting.User()
        self.other = blm.accounting.User()
        self.org = blm.accounting.Org()
        self.org.ug[0].users = [self.accountant, self.member]
        self.org.accountants = [self.accountant]

        self.commit()
        self.accountant = blm.accounting.User._query(id=self.accountant).run()[0]
        self.member = blm.accounting.User._query(id=self.member).run()[0]
        self.other = blm.accounting.User._query(id=self.other).run()[0]
        self.org = blm.accounting.Org._query(id=self.org).run()[0]

    def test_payment(self):
        payment = blm.members.Payment(org=self.org)
        self.commit()
        payment._clear()
        self.check(payment,
                   params=None,
                   edit=dict(approved=[True]),
                   allow=self.accountant, deny=self.member)

    def test_credit_invoice(self):
        # same test as the one in TestStoreKeeperPermissions, but with accountants
        product = blm.members.Product(name=['foo'], org=self.org)
        invoice = blm.members.Invoice(
            items=[blm.members.PurchaseItem(product=product)])
        self.commit()
        invoice, = blm.members.Invoice._query().run()

        self.ctx.setUser(self.member)
        with py.test.raises(ClientError):
            blm.members.createCreditInvoice([invoice])

        self.ctx.setUser(self.accountant)
        blm.members.createCreditInvoice([invoice])  # don't explode


class TestStoreKeeperPermissions(PermissionTests):

    def setup_method(self, method):
        super(TestStoreKeeperPermissions, self).setup_method(method)
        self.storekeeper = blm.accounting.User()
        self.member = blm.accounting.User()
        self.other = blm.accounting.User()
        self.org = blm.accounting.Org()
        self.org.ug[0].users = [self.storekeeper, self.member]
        self.org.storekeepers = [self.storekeeper]

        self.commit()
        self.storekeeper = blm.accounting.User._query(id=self.storekeeper).run()[0]
        self.member = blm.accounting.User._query(id=self.member).run()[0]
        self.other = blm.accounting.User._query(id=self.other).run()[0]
        self.org = blm.accounting.Org._query(id=self.org).run()[0]

    def test_product(self):
        self.check(blm.members.Product,
                   params=dict(org=self.org, name='The product'),
                   edit=dict(name='The product with a better name'),
                   allow=[self.storekeeper], deny=[self.member, self.other])

        self.check_delete(blm.members.Product,
                          params=dict(org=self.org, name='The product'),
                          allow=[self.storekeeper],
                          deny=[self.member, self.other])

    def test_purchase(self):
        product = blm.members.Product(org=self.org, name='Product')
        purchase = blm.members.Purchase(
            items=[blm.members.PurchaseItem(product=product)])
        self.commit()

        purchase._clear()
        self.check(purchase, params=None, edit=dict(cancelled=False),
                   allow=[self.storekeeper], deny=[self.member, self.other])

    def test_credit_invoice(self):
        # same test as the one in TestAccountantPermissions, but with storekeepers
        product = blm.members.Product(name=['foo'], org=self.org)
        invoice = blm.members.Invoice(
            items=[blm.members.PurchaseItem(product=product)])
        self.commit()
        invoice, = blm.members.Invoice._query().run()

        self.ctx.setUser(self.member)
        with py.test.raises(ClientError):
            blm.members.createCreditInvoice([invoice])

        self.ctx.setUser(self.storekeeper)
        blm.members.createCreditInvoice([invoice])  # don't explode


class TestTicketCheckerPermissions(PermissionTests):

    def setup_method(self, method):
        super(TestTicketCheckerPermissions, self).setup_method(method)
        self.ticketchecker = blm.accounting.User()
        self.member = blm.accounting.User()
        self.other = blm.accounting.User()
        self.org = blm.accounting.Org()
        self.org.ug[0].users = [self.member]
        self.org.ticketchecker_ug[0].users = [self.ticketchecker]

        self.commit()
        self.ticketchecker = blm.accounting.User._query(id=self.ticketchecker).run()[0]
        self.member = blm.accounting.User._query(id=self.member).run()[0]
        self.other = blm.accounting.User._query(id=self.other).run()[0]
        self.org = blm.accounting.Org._query(id=self.org).run()[0]

        self.product = blm.members.Product(org=self.org, makeTicket=True,
                                           name='Product')
        self.item = blm.members.PurchaseItem(product=self.product)

    def test_void_unvoid(self):
        ticket = blm.members.Ticket(purchaseitem=self.item)
        self.commit()
        ticket._clear()

        self.check(ticket.void, params={}, edit=None,
                   allow=[self.ticketchecker], deny=[self.member, self.other])


class TestUpgrade(BLMTests):

    def setup_method(self, method):
        super(TestUpgrade, self).setup_method(method)
        oe = blm.accounting.Org(orgnum=blm.accounting.Org._oeOrgNum)

    def test_reentrant(self):
        blm.members.upgrade()  # don't explode
        blm.members.upgrade()  # reentrant
