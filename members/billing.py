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

from bson.objectid import ObjectId
from email.utils import formataddr, parseaddr
try:
    from cStringIO import StringIO
except ImportError:
    from io import StringIO
    from io import BytesIO
import decimal, json, logging, os, re, string, sys
from pytransact.context import ReadonlyContext
from pytransact.commit import CommitContext, ChangeToi, CreateToi, CallBlm, \
    wait_for_commit
from pytransact import queryops as q
from accounting import jsonserialization, templating
import accounting.db, accounting.config, accounting.mail
from members.invoice import make_invoice

import blm.accounting
import blm.members

log = accounting.config.getLogger('billing')


INTERVALS = 100, 500, 1000, 5000#, sys.maxint
PRICES = 200, 200, 400, 800#, 1600

templates = os.path.abspath(os.path.join(os.path.dirname(__file__), '..',
                                         'templates'))

class Billing(object):

    OE_ORGNUM = blm.accounting.Org._oeOrgNum
    _products = None
    _subscription = None

    def connect(self):
        self.db = accounting.db.connect()

    @property
    def subscription(self):
        if self._subscription is None:
            with ReadonlyContext(self.db) as ctx:
                openend, = blm.accounting.Org._query(orgnum=self.OE_ORGNUM).run()
                self._subscription = str(blm.members.Product._query(
                        org=openend, notes='subscription').run()[0].id[0])
        return self._subscription

    @property
    def products(self):
        if self._products is None:
            with ReadonlyContext(self.db) as ctx:
                openend, = blm.accounting.Org._query(orgnum=self.OE_ORGNUM).run()
                self._products = []
                for toi in blm.members.Product._query(
                    org=[openend], notes=q.RegEx('^plusgiro ')).run():
                    limit = decimal.Decimal(toi.notes[0][len('plusgiro '):])
                    self._products.append((limit, str(toi.id[0])))
                self._products.sort()
        return self._products

    def bootstrap_products(self, intervals=INTERVALS, prices=PRICES):
        option = '\x1f'.join(['Period', '', 'text', '0', ''])
        with CommitContext(self.db) as ctx:
            openend, = blm.accounting.Org._query(orgnum=self.OE_ORGNUM).run()

            if not blm.members.Product._query(notes='subscription').run():
                ops = [CreateToi(
                        'members.Product', None,
                        {'org': [openend],
                         'notes': ['subscription'],
                         'name': [u'Grundtjänst'],
                         'optionFields': [option],
                         'accountingRules': {'1000': decimal.Decimal(200)}})]
                for limit, price in zip(intervals, prices):
                    ops.append(CreateToi(
                            'members.Product', None,
                            {'org': [openend],
                             'notes': ['plusgiro %s' % limit],
                             'name': [u'Upp till %s inbetalningar' %
                                      limit],
                             'optionFields': [option],
                             'accountingRules': {
                                    '1000': decimal.Decimal(price)}}))

                ops.append(CreateToi(
                        'members.Product', None,
                        {'org': [openend],
                         'notes': ['plusgiro Infinity'],
                         'name': [u'Massa inbetalningar'],
                         'optionFields': [option]}))

                interested = ObjectId()
                ctx.runCommit(ops, interested=interested)
                result, error = wait_for_commit(self.db, interested)
                if error:
                    raise error

    _except = {
        ObjectId('528e4e68323ab1324d000000'): u'Fuskcon',
        ObjectId('528caec4ba5b3b1331000000'): u'Testorganisation',
        ObjectId('5195faac61b6d448c0000000'): u'R\xe4ksm\xf6rg\xe5sar AB',
        ObjectId('5294c76649afe47060000000'): u'Sebastians hemliga klubb',
        ObjectId('5224a752a8d2247964000000'): u'test',
        ObjectId('52e950241238870c29000000'): u'Bollklubben IF',
        ObjectId('523071c6323ab107ea000001'): u'Jacobs Testorganisation',
        ObjectId('524c16ffe52fc64d86000000'): u'Open End',
        ObjectId('52e17d78323ab16817000000'): u'Dohse demo',
        ObjectId('528e07bc261cdc5f76000000'): u'Laura Testing',
        ObjectId('544eef2b8302231ec9000000'): u'Demo x',
        ObjectId('542174bda9371b6a37000009'): u'Europython Society',
        }

    def iter_orgs(self):
        with ReadonlyContext(self.db):
            for org in blm.accounting.Org._query(
                id=q.NotIn(set(self._except)),
                subscriptionLevel=q.NotEmpty()).run():
                yield org.id[0]

    ignored_providers = (blm.accounting.SimulatorProvider,
                         blm.accounting.ManualProvider)

    def handle_org(self, orgid, year):
        with CommitContext(self.db) as ctx:
            org, = blm.accounting.Org._query(id=orgid).run()
            subscriptionLevel = org.subscriptionLevel[:]
            invoiceAttrs = {
                'buyerName': org.name[:],
                'buyerEmail': org.email[:],
                'buyerPhone': org.phone[:],
                'buyerAddress': org.address[:],
                'buyerOrg': [orgid]
                }

            openend, = blm.accounting.Org._query(orgnum=self.OE_ORGNUM).run()
            providers = blm.accounting.PaymentProvider._query(org=org).run()
            providers = [toi for toi in providers if not isinstance(toi, self.ignored_providers)]  #filter(lambda toi: not isinstance(toi, self.ignored_providers), providers)
            start, end = (s % year for s in ('%s-01-01', '%s-12-31'))
            payments = blm.members.Payment._query(
                paymentProvider=providers,
                transaction_date=q.Between(start, end)).run()
            supplierinvoices = blm.accounting.SupplierInvoice._query(
                org=org,
                automated=True,
                accounted=True,
                transaction_date=q.Between(start, end)).run()
            chargeables = len(payments) + len(supplierinvoices)

            toInvoice = [self.subscription]
            if providers:
                for limit, product in self.products:
                    toInvoice.append(product)
                    if chargeables <= limit:
                        break

            for invoice in blm.members.Invoice._query(
                    org=openend, buyerOrg=[orgid], _attrList=['items']).run():
                for item in invoice.items:
                    if dict(item.optionsWithValue).get('Period') == year:
                        try:
                            toInvoice.remove(item.product[0])
                        except ValueError:
                            log.warn("We have alreaedy invoiced for %s (%s) "
                                     "when we shouldn't have.",
                                     item.product[0].name[0],
                                     item.product[0].id[0])

            if toInvoice:
                invoiceId = ObjectId()
                invoiceAttrs['org'] = [openend]
                ops = [CreateToi('members.Invoice', invoiceId, invoiceAttrs)]
                for productId in toInvoice:
                    product, = blm.members.Product._query(id=productId).run()
                    options = []
                    for optionField in product.optionFields:
                        if optionField.split('\x1f')[0] == 'Period':
                            options.append(year)
                        else:
                            options.append('')

                    ops.append(CreateToi('members.PurchaseItem', None,
                                         {'purchase': [invoiceId],
                                          'product': [product],
                                          'options': options}))

                interested = ObjectId()
                ctx.runCommit(ops, interested=interested)
                result, error = wait_for_commit(ctx.database,
                                                interested=interested)
                if error:
                    raise error

    def iter_invoices(self):
        with ReadonlyContext(self.db):
            openend, = blm.accounting.Org._query(orgnum=self.OE_ORGNUM).run()
            for invoice in blm.members.Invoice._query(sent=[False],
                                                      org=[openend]).run():
                yield invoice.id[0]

    def send_invoice(self, toid):
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from email.mime.application import MIMEApplication

        fromaddr = accounting.config.config.get(
            'billing', 'fromaddr')

        with CommitContext(self.db) as ctx:
            invoice, = blm.members.Invoice._query(id=toid).run()
            name = ''
            if invoice.buyerName:
                name = invoice.buyerName[0]
            if invoice.buyerEmail:
                to = parseaddr(invoice.buyerEmail[0])[1]
            else:
                buyer = invoice.buyerOrg
                if buyer:
                    buyer = buyer[0]
                else:
                    buyer = 'unknown'
                log.warn('Org %s (%s) has no email! No invoice sent!', name, buyer)
                return
            url = invoice.invoiceUrl[0]
            try:
                pdf = BytesIO()     #py3
            except NameError:
                pdf = StringIO()    #py2
            org = invoice.org[0]

            pgprovider = blm.accounting.PlusgiroProvider._query(
                org=org, pgnum=q.NotEmpty()).run()

            pgnum = pgprovider[0].pgnum[0] if pgprovider else ''
            #import pdb;pdb.set_trace()
            make_invoice(pdf, invoice, org, pgnum, None)

            body, headers = templating.as_mail_data('subscription', url=url)

            message = MIMEMultipart()
            for header, value in headers.items():
                message[header] = value
            message['From'] = accounting.mail.makeAddressHeader(
                'From', [(org.name[0], org.email[0])])
            message['To'] = accounting.mail.makeAddressHeader(
                'To', [(name, to)])
            message.attach(MIMEText(body, _charset='utf-8'))
            attachment = MIMEApplication(pdf.getvalue(), 'pdf')
            attachment.add_header('Content-Disposition', 'attachment', filename='faktura.pdf')
            message.attach(attachment)

            log.info('Sending invoice to %s', to)
            accounting.mail.sendmail(fromaddr, [to], message.as_string())

            op = ChangeToi(invoice, {'sent': [True]})
            interested = ObjectId()
            ctx.runCommit([op], interested=interested)
            result, error = wait_for_commit(ctx.database, interested=interested)
            if error:
                raise error

    def process(self, year):
        for orgid in self.iter_orgs():
            self.handle_org(orgid, year)
        for invoiceid in self.iter_invoices():
            self.send_invoice(invoiceid)
