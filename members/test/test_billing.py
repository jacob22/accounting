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

import decimal, json, py
try:
    import StringIO
except ImportError:
    from io import StringIO
import email
from bson.objectid import ObjectId
from pytransact.context import ReadonlyContext
from pytransact.commit import CommitContext, wait_for_commit
from pytransact import queryops as q
from pytransact import testsupport
import members.billing

from accounting import mail

import accounting.db, accounting.config
import blm.accounting, blm.members


class TestBilling(testsupport.BLMTests):

    def mkPayment(self, **kw):
        return blm.members.Payment(**kw)

    def mkTestData(self, payments=1):
        org = blm.accounting.Org(
            name=['The Org'],
            orgnum=['111111-1111'],
            subscriptionLevel=['subscriber', 'pg'],
            email=['foo@example'],
            phone=['555-12345'],
            address=['The Street 1\n123 45 The City'],
            )
        provider = blm.accounting.PaymentProvider(org=org)

        pmnts = []
        for n in range(1, payments+1):
            payment = self.mkPayment(
                paymentProvider=provider,
                transaction_date=['2010-01-%02d' % n],
                amount=['100.00'])
            pmnts.append(payment)

        return org, provider, pmnts

    def mkBilling(self):
        billing = members.billing.Billing()
        billing.connect()
        return billing

    def test_bootstrap_products(self):
        openend = blm.accounting.Org(orgnum='556609-2473')
        self.commit()

        billing = self.mkBilling()
        billing.bootstrap_products()
        self.sync()

        subscription, = blm.members.Product._query(notes='subscription').run()
        a, = blm.members.Product._query(notes='plusgiro 100').run()
        b, = blm.members.Product._query(notes='plusgiro 500').run()
        c, = blm.members.Product._query(notes='plusgiro 1000').run()
        d, = blm.members.Product._query(notes='plusgiro 5000').run()
        e, = blm.members.Product._query(notes='plusgiro Infinity').run()

        assert subscription.accountingRules.values() == [decimal.Decimal('200')]
        assert a.accountingRules.values() == [decimal.Decimal('200')]
        assert b.accountingRules.values() == [decimal.Decimal('200')]
        assert c.accountingRules.values() == [decimal.Decimal('400')]
        assert d.accountingRules.values() == [decimal.Decimal('800')]

        assert subscription.org == a.org == b.org == c.org == d.org == [openend]

    def test_build_pricelist(self):
        openend = blm.accounting.Org(orgnum='556609-2473')
        toids = [ObjectId() for x in range(4)]
        blm.members.Product(id=toids[0], org=openend, notes='subscription', name='foo')
        blm.members.Product(id=toids[1], org=openend, notes='plusgiro 10', name='foo')
        blm.members.Product(id=toids[2], org=openend, notes='plusgiro 20', name='foo')
        blm.members.Product(id=toids[3], org=openend, notes='plusgiro Infinity', name='foo')
        self.commit()

        billing = self.mkBilling()

        toids = [str(t) for t in toids]     #map(str, toids)

        assert billing.subscription == toids[0]
        assert billing.products == [
            (decimal.Decimal(10), toids[1]),
            (decimal.Decimal(20), toids[2]),
            (decimal.Decimal('Infinity'), toids[3])
            ]

    def test_iter_orgs(self):
        org_sbx = blm.accounting.Org()
        org_pay1 = blm.accounting.Org(subscriptionLevel=['subscriber'])
        org_pay2 = blm.accounting.Org(subscriptionLevel=['subscriber'])
        org_exc = blm.accounting.Org(subscriptionLevel=['subscriber'])
        self.commit()

        billing = self.mkBilling()
        billing._except = {org_exc.id[0]}
        orgids = set(billing.iter_orgs())
        assert orgids == set(o.id[0] for o in [org_pay1, org_pay2])

    def test_handle_org_no_pg(self):
        openend = blm.accounting.Org(orgnum='556609-2473')
        org = blm.accounting.Org(
            name=['The Org'],
            orgnum=['111111-1111'],
            subscriptionLevel=['subscriber'],
            email=['foo@example']
            )
        self.commit()

        billing = self.mkBilling()
        billing.bootstrap_products(intervals=[1, 2, 3], prices=[10, 20, 30])
        billing.handle_org(org.id[0], '2010')

        invoice, = blm.members.Invoice._query(buyerOrg=org).run()
        assert invoice.buyerName == ['The Org']
        assert invoice.buyerEmail == ['foo@example']

        item, = invoice.items
        assert item.product[0].notes == ['subscription']
        assert dict(item.optionsWithValue)['Period'] == '2010'

    def test_handle_org_pg(self, monkeypatch):
        openend = blm.accounting.Org(orgnum='556609-2473')
        org, provider, payments = self.mkTestData(payments=2)
        # too old
        self.mkPayment(
            paymentProvider=provider,
            transaction_date=['2009-12-31'],
            amount=['100.00'])
        # too new
        self.mkPayment(
            paymentProvider=provider,
            transaction_date=['2011-01-01'],
            amount=['100.00'])
        self.commit()

        billing = self.mkBilling()
        billing.bootstrap_products(intervals=[1, 2, 3], prices=[10, 20, 30])

        subscription, = blm.members.Product._query(notes='subscription').run()
        interval1, = blm.members.Product._query(notes='plusgiro 1').run()
        interval2, = blm.members.Product._query(notes='plusgiro 2').run()
        interval3, = blm.members.Product._query(notes='plusgiro 3').run()

        billing.handle_org(org.id[0], '2010')

        invoices = []
        invoice, = blm.members.Invoice._query(buyerOrg=org.id).run()
        invoices.append(invoice.id[0])
        assert invoice.buyerName == ['The Org']
        assert invoice.buyerEmail == ['foo@example']

        items = sorted(invoice.items, key=lambda toi: toi.id)
        assert items[0].product == [subscription]
        assert dict(items[0].optionsWithValue)['Period'] == '2010'
        assert items[1].product == [interval1]
        assert dict(items[1].optionsWithValue)['Period'] == '2010'
        assert items[2].product == [interval2]
        assert dict(items[2].optionsWithValue)['Period'] == '2010'

        self.mkPayment(
            paymentProvider=provider,
            transaction_date=['2010-02-01'],
            amount=['100.00'])
        self.commit()

        billing.handle_org(org.id[0], '2010')

        invoice, = blm.members.Invoice._query(buyerOrg=org.id,
                                              id=q.NotIn(invoices)).run()
        invoices.append(invoice.id[0])
        assert invoice.buyerName == ['The Org']
        assert invoice.buyerEmail == ['foo@example']

        items = sorted(invoice.items, key=lambda toi: toi.id)
        assert items[0].product == [interval3]

        billing.handle_org(org.id[0], '2010')
        # no new invoices
        assert len(blm.members.Invoice._query(buyerOrg=org.id).run()) == 2

        # 2011
        billing.handle_org(org.id[0], '2011')
        self.sync()
        invoice, = blm.members.Invoice._query(buyerOrg=org.id,
                                             id=q.NotIn(invoices)).run()
        assert invoice.buyerName == ['The Org']
        assert invoice.buyerEmail == ['foo@example']
        subscription_item, interval1_item = invoice.items
        assert subscription_item.product == [subscription]
        assert dict(subscription_item.optionsWithValue)['Period'] == '2011'
        assert interval1_item.product == [interval1]
        assert dict(interval1_item.optionsWithValue)['Period'] == '2011'

    def test_iter_invoices(self):
        openend = blm.accounting.Org(orgnum='556609-2473')
        otherorg = blm.accounting.Org(orgnum='111111-1111')

        invoice1 = blm.members.Invoice(org=[openend])
        invoice2 = blm.members.Invoice(org=[openend])
        invoice3 = blm.members.Invoice(org=[otherorg])
        invoice4 = blm.members.Invoice(org=[openend], sent=[True])
        self.commit()

        billing = self.mkBilling()
        assert set(billing.iter_invoices()) == {invoice1.id[0], invoice2.id[0]}

    def test_send_invoice(self, monkeypatch):
        openend = blm.accounting.Org(name='Open End', orgnum='556609-2473',
                                     email=['vlad@openend.se'],
                                     subscriptionLevel=['subscriber'])
        pgp = blm.accounting.PlusgiroProvider(org=openend, pgnum='123455')
        invoice = blm.members.Invoice(
            org=[openend],
            buyerName=['Klubben Klubb'],
            buyerEmail=['klubb@example'])
        self.commit()

        calls = []
        def sendmail(*args):
            calls.append(args)

        monkeypatch.setattr(mail, 'sendmail', sendmail)
        accounting.config.config.set('accounting', 'baseurl', 'http://foo.bar/')
        accounting.config.config.set('billing', 'fromaddr', 'foo@bar.baz')

        billing = self.mkBilling()
        #import pdb;pdb.set_trace()
        billing.send_invoice(invoice.id[0])

        (fromaddr, to, body), = calls
        msg = email.message_from_string(body)

        assert fromaddr == 'foo@bar.baz'
        assert invoice.invoiceUrl[0] in msg.get_payload()[0].get_payload(
            decode=True).decode('utf-8')
        assert to == ['klubb@example']

        invoice, = blm.members.Invoice._query(id=invoice.id[0]).run()
        assert invoice.sent == [True]

    def test_process(self):
        oid1, oid2 = ObjectId(), ObjectId()
        iid1, iid2 = ObjectId(), ObjectId()

        def iter_orgs():
            return oid1, oid2

        def iter_invoices():
            return iid1, iid2

        calls = []
        def handle_org(orgid, year):
            assert year == '2010'
            calls.append(('org', orgid))

        def send_invoice(iid):
            calls.append(('invoice', iid))

        billing = self.mkBilling()
        billing.iter_orgs = iter_orgs
        billing.handle_org = handle_org
        billing.iter_invoices = iter_invoices
        billing.send_invoice = send_invoice

        billing.process('2010')

        assert calls == [
            ('org', oid1),
            ('org', oid2),
            ('invoice', iid1),
            ('invoice', iid2)
            ]
