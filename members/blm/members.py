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

from __future__ import absolute_import
from bson.objectid import ObjectId
import codecs, collections, decimal, logging, os, time, json
try:
    from StringIO import StringIO         #py2
except ImportError:
    from io import StringIO #py3

from email.utils import getaddresses
import stripe
from pytransact.iterate import uniq
from pytransact.diff import difference
from pytransact.object.model import *
import pytransact.runtime as ri
import pytransact.queryops as q
from accounting import config, exceptions, luhn, mail, templating, swish
from accounting import izettle_import
from blm import fundamental, accounting
import random
try:
    import urlparse                         #py2
except ImportError:
    from urllib import parse as urlparse    #py3
from Crypto.PublicKey import DSA
from Crypto.Hash import SHA

import sys
if sys.version_info < (3,0,0):
    PYT3 = False
else:
    PYT3 = True

from blm.accounting import currentUserHasRole, requireRoles

log = logging.getLogger('blm.accounting')

date_re = r'\d{4}-\d{2}-\d{2}'  # from accounting.py


class PGNum(String()):

    def on_create(attr, value, toi):
        return list(map(accounting.normalize_pgnum, value))
    on_update = on_create


class StringNotEmpty(String):

    def on_create(attr, value, self):
        return [v for v in value if v]   #filter(None, value)
    on_update = on_create


class ProductTag(TO):

    class tag(String(Quantity(1))):
        pass

    class org(ToiRef(Quantity(1), ToiType(accounting.Org))):
        pass

    def on_create(self):
        self.allowRead = self.org[0].ug

    @staticmethod
    def ensure(org, tags):
        for tag in tags:
            if not ProductTag._query(org=org, tag=tag).run():
                ProductTag(org=org, tag=[tag])

    @staticmethod
    def unregister(org, tags):
        for tag in tags:
            if not Product._query(org=org, tags=tag).run():
                for toi in ProductTag._query(org=org, tag=tag).run():
                    toi._delete()


class IzettleProduct(TO):
    class name(String(Quantity(1))):
        pass

    class variant(String(QuantityMax(1))):
        pass
    
    class archived(Bool()):
        # xxx turn this into a Quantity(1) with default [False] after
        # data conversion

        def on_create(attr, value, toi):
            return value or [False]
        on_update = on_create

    class productId(String(Regexp(r'[\w-]{22}'), Quantity(1))):
        pass

    class org(ToiRef(Quantity(1), Unchangeable(),
                     post=ToiType(accounting.Org))):
        pass

    class accountingRules(DecimalMap()):
        precision = 2

    class vatAccount(StringNotEmpty(QuantityMax(1))):
        pass

    class currentVatAccount(ToiRef(ToiType(accounting.Account),
                                   QuantityMax(1))):
        def on_computation(attr, self):
            if self.vatAccount:
                return accounting.Account._query(
                    accounting=self.org[0].current_accounting,
                    number=self.vatAccount).run()
            return []

    class vat(Decimal(Quantity(1))):

        def on_computation(attr, self):
            try:
                percentage = self.currentVatAccount[0].vatPercentage[0]
            except IndexError:
                vat = decimal.Decimal(0)
            else:
                price = sum(self.accountingRules.values(), decimal.Decimal(0))
                vat = price * percentage / 100
            return [vat]

    class vatPercentage(Decimal(Quantity(1))):
        precision = 2

    class barcode(String(QuantityMax(1))):
        pass

    class customUnit(String(QuantityMax(1))):
        pass
        
    class price(Decimal(Quantity(1))):
        precision = 2
        def on_computation(attr, self):
            price = sum(self.accountingRules.values(), decimal.Decimal('0.00'))
            return [price + self.vat[0]]

    class izPrice(Decimal(QuantityMax(1))):
        precision = 2
        
    def canWrite(self, user, attrName):
        return currentUserHasRole(self, 'storekeepers', user=user)
    
    @method(None)
    def update(self, attributes=Serializable()):
        # [{u'accountingRules': {u'5361': 33333300}}]
        accountingRules = attributes[0]['accountingRules']
        # Convert Ore to kr. 
        accountingRules = {key: decimal.Decimal(value)/100 for (key,value) in accountingRules.items()}
        self.accountingRules=accountingRules

    @requireRoles('storekeepers')
    def on_create(self):
        self.allowRead = self.org[0].ug

    @staticmethod
    def product_map(org):
        cache_key = 'productmap-%s' % org.id[0]
        try:
            return ri.cache[cache_key]
        except KeyError:
            pass

        products = IzettleProduct._query(
            org=org,
            _attrList='name variant customUnit accountingRules izPrice vatAccount'.split()).run()

        accounts = accounting.Account._query(
            accounting=org.current_accounting,
            _attrList='''
                number transactions
                balance opening_balance
                opening_quantity balance_quantity
            '''.split()).run()

        accounttoimap = {toi.number[0]: toi for toi in accounts}

        prodmap = {}
        for product in products:
            if product.price != product.izPrice:
                continue
            p = []
            for accountno, amount in sorted(product.accountingRules.items()):
                # Check that account number is valid in current accunting.
                try:
                    accounttoi = accounttoimap[accountno]
                except KeyError:
                    break
                p.append((accounttoi, amount))
            else:
                if product.variant != []:
                    namevariant = "%s (%s)" % (product.name[0], product.variant[0])
                    prodmap[namevariant] = p
                else:
                    prodmap[product.name[0]] = p

        prodtoimap = {}
        for product in products:
            if product.variant != []:
                namevariant = "%s (%s)" % (product.name[0], product.variant[0])
                prodtoimap[namevariant] = product
            else:
                prodtoimap[product.name[0]] = product
                    
        #provider, = accounting.IzettleProvider._query(
        #    org=org, _attrList='account series'.split()).run()

        #provideraccount = account_by_number[provider.account[0]]
        #providerfeeaccount = account_by_number[provider.fee_account[0]]
                
        result = prodmap, prodtoimap, accounttoimap
        ri.cache[cache_key] = result
        return result

    def sort_name_key(self):
        # Could be done with two stage sorting. 
        if self.variant:
            string1 = self.name[0] + self.variant[0]

        else:
            string1 = self.name[0]

        return string1
    sort_name_attrs = ['name']


@method(None)
def import_izettle_products(org=ToiRef(ToiType(accounting.Org), Quantity(1)),
                            products=Serializable()):
    old_products = IzettleProduct._query(org=org).run()
    op_list = {op.productId[0]:op for op in old_products}
    
    for product in products:
        product = {k:v for (k,v) in product.items() if v != ''}
        try:
            prodtoi = op_list[product['productId']]
        except KeyError:
            prodtoi = IzettleProduct(org=org, **product)
        else:
            prodtoi(**product)


@method(Serializable)
def import_izettle_products_file(org=ToiRef(ToiType(accounting.Org), Quantity(1)),
                                 filedata=String(Quantity(1))):
    if PYT3:
        filedata = filedata[0]  # .encode()
    else:
        filedata = filedata[0].decode('base64')
    file = StringIO(filedata)
    try:
        #parsed_prods = izettle_import.parse_products_xls(file)
        products = [p for p in izettle_import.parse_products_xls(file)]   # list(parsed_prods)
        # If there is a problem in the izettle file it does not get detected until
        # the iterator tries to yeild first object. That needs to happen within a try/except.
        # Without list() the raised error is caught by the for loop below.
    except Exception:
        raise cBlmError('This does not look like an iZettle product file.')
        
    old_products = IzettleProduct._query(org=org).run()
    op_list = {op.productId[0]:op for op in old_products}

    # Find VAT account set for IzettleProvider
    #provider = accounting.IzettleProvider._query(org=org).run()
    #vatAccount = provider.
    
    created = 0
    updated = 0
    for product in products:
        product = {k:v for (k,v) in product.items() if v != ''}
        try:
            prodtoi = op_list[product['productId']]
        except KeyError:
            prodtoi = IzettleProduct(org=org, **product)
            created += 1
        else:
            if 'izPrice' not in product:
                # If you change from fixed price to per purchase entered price
                # then izPrice should be unset in product. 
                product['izPrice'] = []
            prodtoi(**product)
            updated += 1
    return {'created': created, 'updated': updated}


class Product(TO):
    class name(String(Quantity(1))):
        pass

    class archived(Bool()):
        # xxx turn this into a Quantity(1) with default [False] after
        # data conversion

        def on_create(attr, value, toi):
            return value or [False]
        on_update = on_create

    class available(Bool(Quantity(1))):
        default = [False]

    class availableFrom(StringNotEmpty(QuantityMax(1))):
        pass

    class availableTo(StringNotEmpty(QuantityMax(1))):
        pass

    class description(String(QuantityMax(1))):
        pass

    class notes(String(QuantityMax(1))):
        pass

    class optionFields(String()):
        # label
        # [beskrivningstext]
        # typ
        # obligatoriskt/valfritt
        # [typmetadata]
        # use \x1f as separator
        pass

    class makeTicket(Bool(Quantity(1))):
        default = [False]

    class tags(String()):

        def on_create(attr, value, toi):
            return [v.strip() for v in value]
        on_update = on_create

    class totalStock(Int(QuantityMax(1), RangeMin(0))):
        pass

    class quantitySold(Int(Quantity(1), RangeMin(0), pre=ReadOnly())):
        default = [0]

    class currentStock(Int(QuantityMax(1), RangeMin(0))):

        def on_computation(attr, self):
            return [tot - self.quantitySold[0] for tot in self.totalStock]

    class org(ToiRef(Quantity(1), Unchangeable(),
                     post=ToiType(accounting.Org))):
        pass

    class accountingRules(DecimalMap()):
        precision = 2

    class vatAccount(StringNotEmpty(QuantityMax(1))):
        pass

    class currentVatAccount(ToiRef(ToiType(accounting.Account),
                                   QuantityMax(1))):
        def on_computation(attr, self):
            return accounting.Account._query(
                accounting=self.org[0].current_accounting,
                number=self.vatAccount).run()

    class vat(Decimal(Quantity(1))):

        def on_computation(attr, self):
            try:
                percentage = self.currentVatAccount[0].vatPercentage[0]
            except IndexError:
                vat = decimal.Decimal(0)
            else:
                price = sum(self.accountingRules.values(), decimal.Decimal(0))
                vat = price * percentage / 100
            return [vat]

    class price(Decimal(Quantity(1))):

        def on_computation(attr, self):
            price = sum(self.accountingRules.values(), decimal.Decimal('0.00'))
            return [price + self.vat[0]]

    class image(Blob(QuantityMax(1))):
        pass

    class hasImage(Bool(Quantity(1))):

        def on_computation(attr, self):
            return [bool(len(self.image))]

    class sold(Bool(Quantity(1), pre=ReadOnly())):
        default = [False]

    @method(ToiRef(ToiType('Product'), Quantity(1)))
    def copy(self):
        return [Product(
            available=[False],
            name=[u'Kopia av %s' % self.name[0]], # xxx transl?
            org=self.org,
            availableFrom=self.availableFrom,
            availableTo=self.availableTo,
            description=self.description,
            notes=self.notes,
            optionFields=self.optionFields,
            tags=self.tags,
            totalStock=self.totalStock,
            accountingRules=self.accountingRules,
            image=self.image)]

    def registerPurchaseItem(self, item):
        self.sold = [True]
        self.quantitySold = [self.quantitySold[0] + item.quantity[0]]
        if self.currentStock and self.currentStock[0] < 0:
            raise exceptions.cJSONError({
                    'code': 'out of stock',
                    'product': self.id[0],
                    'remaining': self.currentStock[0] + item.quantity[0]
                    })

    def canWrite(self, user, attrName):
        return currentUserHasRole(self, 'storekeepers', user=user)

    @requireRoles('storekeepers')
    def on_create(self):
        self.allowRead = self.org[0].ug
        if self.totalStock and not self.currentStock:
            self.currentStock = self.totalStock
        ProductTag.ensure(self.org, self.tags)

    def on_update(self, newAttrValues):
        tags = set(self.tags)
        self._update(newAttrValues)
        ProductTag.ensure(self.org, self.tags)
        ProductTag.unregister(self.org, tags - set(self.tags))

    def on_delete(self):
        if self.available[0]:
            raise cBlmError('You can not delete a product which is being sold.')

        if self.sold[0]:
            raise cBlmError('You can not delete a product which has already '
                            'been sold.')

        tags, self.tags = self.tags[:], []
        ProductTag.unregister(self.org, tags)


@method(ToiRef(ToiType(Product), Quantity(1)))
def copyProduct(product=ToiRef(ToiType(Product), Quantity(1))):
    return product[0].copy()


class BasePurchase(TO):

    class kind(String(Quantity(1), ReadOnly())):
        pass

    class org(ToiRef(ToiType(accounting.Org), post=Quantity(1))):
        pass

    class random(Int(post=Quantity(1))):

        def on_create(attr, value, toi):
            return [random.SystemRandom().getrandbits(32)]

    class invoiceUrl(String()):

        def on_computation(attr, self):
            baseurl = config.config.get('accounting', 'baseurl')
            try:
                url = '/invoice/%s/%s' % (self.id[0], self.random[0])
            except IndexError:
                url = '/invoice/%s' % self.id[0]

            return [urlparse.urljoin(baseurl, url)]

    class ticketsUrl(String()):

        def on_computation(attr, self):
            baseurl = config.config.get('accounting', 'baseurl')
            try:
                url = '/getTickets/%s/%s' % (self.id[0], self.random[0])
            except IndexError:
                url = '/getTickets/%s' % self.id[0]

            return [urlparse.urljoin(baseurl, url)]

    class cancelled(Bool(Quantity(1))):
        default = [False]

    class paymentState(Enum(Quantity(1))):
        values = 'unpaid', 'partial', 'paid', 'credited'
        default = ['unpaid']

    class date(Timestamp(post=Quantity(1))):

        def on_create(attr, value, toi):
            return value or [time.time()]

    class items(Relation()):
        related = 'PurchaseItem.purchase'

    class total(Decimal(post=Quantity(1))):
        precision = 2

    class currency(StringNotEmpty(Regexp(r'[A-Z]{3}'), post=Quantity(1))):
        pass

    class remainingAmount(Decimal(post=Quantity(1))):
        precision = 2
        def on_computation(attr, self):
            return [self.total[0] - sum(toi.amount[0] for toi in
                                        self.matchedPayments)]

    class ocr(String(post=Quantity(1))):
        pass

    class buyerName(String(QuantityMax(1))):
        pass

    class buyerAddress(String(QuantityMax(1))):
        pass

    class buyerPhone(String(QuantityMax(1))):
        pass

    class buyerEmail(String(QuantityMax(1))):
        pass

    class buyerReference(String(QuantityMax(1))):
        pass

    class buyerAnnotation(String(QuantityMax(1))):
        pass

    class paymentTerms(String(QuantityMax(1))):
        pass

    class extraText(String()):
        pass

    class matchedPayments(Relation()):
        relation = 'Payment.matchedPurchase'

    class confirmationEmailSent(Bool(Quantity(1))):
        default = [False]

    class reminderEmailsSent(Timestamp()):
        pass

    class tickets(ToiRef(ToiType('Ticket'))):
        def on_computation(attr, self):
            return Ticket._query(purchaseitem=self.items).run()

    class vat(Serializable()):
        precision = 2

        def on_computation(attr, self):
            vats = collections.defaultdict(decimal.Decimal)
            code2perc = {}
            for item in self.items:
                product = item.product[0]
                if item.vatPercentage:
                    vats[str(item.vatCode[0])] += item.totalVat[0]
                    code2perc[item.vatCode[0]] = item.vatPercentage[0]

            quantifier = decimal.Decimal('0.01')
            result = []
            for code, amount in vats.items():
                result.append((code,
                               code2perc[code].quantize(quantifier),
                               amount.quantize(quantifier)))
            result.sort(key=lambda v: -v[1])
            return result

    @method(None)
    def sendConfirmationEmail(self):
        template = self.confirmationEmailTemplate[0]
        sender =  'no-reply@' + config.config.get('accounting', 'smtp_domain')
        replyto = None
        if self.org[0].email:
            replyto = getaddresses(self.org[0].email)[0][1]
        body, headers = templating.as_mail_data(template,
                                                org=self.org[0],
                                                sender=sender,
                                                replyto=replyto,
                                                purchase=self)

        log.info('Sending confirmation email for %s to %s',
                 self.id[0], self.buyerEmail[0])
        orgid = str(self.org[0].id[0])
        mail.sendmail(*mail.makemail(body, envfrom=orgid, **headers),
                       identity=orgid)
        self.confirmationEmailSent = [True]

    @method(None)
    @requireRoles('accountants', 'storekeepers')
    def sendReminderEmail(self):
        sender =  'no-reply@' + config.config.get('accounting', 'smtp_domain')
        replyto = None
        if self.org[0].email:
            replyto = getaddresses(self.org[0].email)[0][1]
        body, headers = templating.as_mail_data('email/purchase-reminder',
                                                org=self.org[0],
                                                sender=sender,
                                                replyto=replyto,
                                                purchase=self)

        log.info('Sending reminder email for %s to %s',
                 self.id[0], self.buyerEmail[0])
        orgid = str(self.org[0].id[0])
        mail.sendmail(*mail.makemail(body, envfrom=orgid, **headers),
                       identity=orgid)
        self.reminderEmailsSent.append(time.time())

    @method(Serializable())
    def suggestVerification(self):
        transactions = []
        buyer = self.buyerName[0] if self.buyerName else ''

        def fmt_account(number, cache={}):
            try:
                toid = cache[number]
            except KeyError:
                try:
                    toi, = accounting.Account._query(
                        number=number,
                        accounting=self.org[0].current_accounting).run()
                    toid = toi.id[0]
                except ValueError:
                    toid = None
                cache[number] = toid
            return toid

        def fmt_amount(amount):
            return int((amount * 100).quantize(1))

        total = decimal.Decimal(0)
        for item in self.items:
            if item.quantity[0] == 1:
                fmt = '%(product)s'
            else:
                fmt = '%(product)s (%(quantity)s)'

            if buyer:
                fmt = '%(buyer)s, ' + fmt

            for number, amount in sorted(item.accountingRules.items()):
                text = fmt % {'buyer': buyer,
                              'product': item.product[0].name[0],
                              'quantity': item.quantity[0]}

                amount *= item.quantity[0]
                total += amount
                transactions.append({
                        'account': fmt_account(number),
                        'amount': -1 * fmt_amount(amount),
                        'text': text})

            if item.vatAccount:
                amount = item.totalVat[0]
                total += amount
                transactions.append({
                        'account': fmt_account(item.vatAccount[0]),
                        'amount': -1 * fmt_amount(amount),
                        'text': text})

        transactions.insert(0, {
            'account': None,
            'amount': fmt_amount(total),
            'text': buyer,
        })
        return {'transactions': transactions}


    def registerPayment(self, payment=None):
        payments = set(self.matchedPayments) | {payment}
        total = sum(toi.amount[0] for toi in payments if toi is not None)
        if total >= self.total[0]:
            self.paymentState = ['paid']
            self.maketickets()
        elif total > 0:
            self.paymentState = ['partial']

    def addPurchaseItem(self, item):
        self.items = items = list(self.items + [item])
        self.total = [sum(item.total[0] for item in items)]

    def canWrite(self, user, attrName):
        return currentUserHasRole(self, 'accountants', 'storekeepers',
                                  user=user)

    def on_create(self):
        if not self.org:
            self.org = self.items[0].product[0].org

        self.allowRead = self.org[0].ug

        total = 0
        for item in self.items:
            if item.product and item.product[0].org != self.org:
                raise cBlmError('All products must belong to the same '
                                'organisation.')
            total += item.total[0]

        if not self.total:
            self.total = [total]
        elif total != self.total[0]:
            raise cBlmError('Total is incorrect.')
        if not self.currency:
            self.currency = self.org[0].currency

        self.ocr = self.org[0].get_ocr()

    @method(ToiRef(ToiType('Ticket')))
    def maketickets(self):
        result = []
        for item in self.items:
            if item.product and item.product[0].makeTicket[0] and item.paid[0]:
                tickets = Ticket._query(purchaseitem=item).run()
                result.extend(tickets)
                for i in range(item.quantity[0]-len(tickets)):
                    result.append(Ticket(purchaseitem=[item]))

        return result


class Purchase(BasePurchase):

    class kind(String(Quantity(1), ReadOnly())):
        default = ['purchase']

    class canBeCredited(Bool(Quantity(1))):

        def on_computation(attr, self):
            if self.cancelled[0]:
                return [False]
            if self.paymentState != ['paid']:
                return [False]
            if self.total == [0]:
                return [False]
            return [True]

    class confirmationEmailTemplate(String(Quantity(1))):

        def on_computation(attr, self):
            if self.total == [0]:
                return ['email/order-confirmation-free']
            else:
                return ['email/order-confirmation']

    def on_create(self):
        super(Purchase, self).on_create()
        if self.total[0] == 0:
            self.paymentState = ['paid']


class Invoice(BasePurchase):

    class kind(String(Quantity(1), ReadOnly())):
        default = ['invoice']

    class canBeCredited(Bool(Quantity(1))):

        def on_computation(attr, self):
            return [self.paymentState[0] in ['paid', 'unpaid']]

    class confirmationEmailTemplate(String(Quantity(1))):

        def on_computation(attr, self):
            if self.total == [0]:
                return ['email/invoice-confirmation-free']
            else:
                return ['email/invoice-confirmation']

    class expiryDate(Timestamp(post=Quantity(1))):
        expiryPeriod = 3600 * 24 * 30  # 30 days

        def on_create(attr, value, toi):
            if not value:
                return [time.time() + attr.expiryPeriod]
            return value

    class buyerOrg(ToiRef(ToiType(accounting.Org))):
        pass

    class sent(Bool(Quantity(1))):
        default = [False]

    def on_create(self):
        super(Invoice, self).on_create()
        if self.total[0] == 0:
            self.paymentState = ['paid']


class CreditInvoice(BasePurchase):

    class kind(String(Quantity(1), ReadOnly())):
        default = ['credit']

    class canBeCredited(Bool(Quantity(1))):

        def on_computation(attr, self):
            return [False]

    class credited(ToiRef(ToiType(BasePurchase), Quantity(1))):
        pass

    class originalPayments(ToiRef(ToiType('Payment'))):
        pass

    class refundable(Bool(Quantity(1))):

        def on_computation(attr, self):
            return [len(self.originalPayments) == 1 and
                    any(toi.refundable[0] for toi in self.originalPayments)]

    @method(None)
    def refund(self):
        if len(self.originalPayments) != 1:
            raise cBlmError('Do not know how to refund multiple payments '
                            'securely')
        self.matchedPayments = self.originalPayments[0].refund()
        self.paymentState = ['paid']

    def on_create(self):
        credited = self.credited[0]
        if isinstance(credited, CreditInvoice):
            raise cBlmError('Credit invoices can not be credited.')
        if credited.paymentState == ['credited']:
            raise cBlmError('Invoices can only be credited once.')
        if credited.paymentState == ['partial']:
            raise cBlmError('Partially paid invoices can not be credited.')
        if isinstance(credited, Purchase) and credited.paymentState != ['paid']:
            raise cBlmError('Can not credit unpaid purchases.')

        self.org = credited.org

        if credited.paymentState == ['paid']:
            for item in credited.items:
                newitem = PurchaseItem(
                    purchase=[self],
                    product=item.product,
                    quantity=[-item.quantity[0]],
                    options=item.options)
                newitem.optionFields = item.optionFields
                newitem.accountingRules = item.accountingRules
            self.paymentState = ['unpaid']

        else:
            ###  what to do...
            # for item in credited.items:
            #     newitem = PurchaseItem(
            #         purchase=[self],
            #         product=item.product,
            #         quantity=[decimal.Decimal(0)],
            #         options=item.options)
            #     newitem.optionFields = item.optionFields
            #     newitem.accountingRules = item.accountingRules
            #     newitem.quantity=[-item.quantity[0]]

            self.paymentState = ['paid']
            credited.cancelled = [True]

        # if credited.paymentState == ['paid']:
        #     self.paymentState = ['unpaid']
        # else:
        #     self.paymentState = ['paid']
        credited.paymentState = ['credited']
        self.originalPayments = credited.matchedPayments

        self.buyerName = credited.buyerName
        self.buyerAddress = credited.buyerAddress
        self.buyerEmail = credited.buyerEmail
        self.buyerPhone = credited.buyerPhone

        super(CreditInvoice, self).on_create()


@method(None)
def refundCredited(creditInvoice=ToiRef(ToiType(CreditInvoice), Quantity(1))):
    creditInvoice[0].refund()


@method(ToiRef(ToiType(CreditInvoice), Quantity(1)))
def createCreditInvoice(invoice=ToiRef(ToiType(BasePurchase), Quantity(1))):
    if not currentUserHasRole(invoice, 'storekeepers', 'accountants'):
        raise cBlmError('Only accountants and storekeepers may credit invoices')
    with ri.setuid():
        return [CreditInvoice(credited=invoice)]


@method(None)
def sendReminderEmail(purchase=ToiRef(ToiType(BasePurchase), Quantity(1))):
    purchase[0].sendReminderEmail()


class PurchaseItem(TO):

    class purchase(Relation()):
        related = 'BasePurchase.items'

    class product(ToiRef(ToiType(Product))):
        pass

    class name(String(post=Quantity(1))):
        pass

    class price(Decimal(post=Quantity(1))):
        precision = 2

    class quantity(Int(Quantity(1))):
        default = 1

    class total(Decimal(post=Quantity(1))):
        precision = 2

    class accountingRules(DecimalMap()):
        precision = 2

    class vatAccount(StringNotEmpty(QuantityMax(1))):
        pass

    class vatCode(String(QuantityMax(1))):
        pass

    class vatPercentage(Decimal(QuantityMax(1))):
        precision = 2

    class totalVat(Decimal(post=Quantity(1))):
        precision = 2
        default = [0]

    class optionFields(String()):
        pass

    class options(String()):
        pass

    class optionsWithValue(Serializable()):

        def on_computation(attr, self):
            return [(field, value) for (field, value)
                    in self.allOptionsWithValue if value]

    class allOptionsWithValue(Serializable()):

        def on_computation(attr, self):
            result = []
            for field, value in zip(
                (f.split('\x1f', 1)[0] for f in self.optionFields),
                self.options):
                result.append((field, value))
            return result

    class paid(Bool(Quantity(1))):

        def on_computation(attr, self):
            return [self.price == [0] or
                    (self.purchase and
                     self.purchase[0].paymentState == ['paid'])]

    def on_create(self):
        if self.product:
            product = self.product[0]
            self.allowRead = product.org[0].ug

            if not self.price:
                self.price = product.price

            if not self.name:
                self.name = product.name

            self.vatAccount = product.vatAccount
            self.totalVat = product.vat[0] * self.quantity[0]
            try:
                self.vatPercentage = product.currentVatAccount[0].vatPercentage
                self.vatCode = product.currentVatAccount[0].vatCode
            except IndexError:
                pass

            self.optionFields = product.optionFields
            self.accountingRules = product.accountingRules
        else:
            if not self.allowRead:
                raise cBlmError('PurchaseItem would be inaccesible.')

        total = self.price[0] * self.quantity[0]
        if not self.total:
            self.total = [total]
        elif self.total[0] != total:
            raise cBlmError('Total is incorrect.')

        for purchase in self.purchase:
            purchase.addPurchaseItem(self)

        if self.product:
            self.product[0].registerPurchaseItem(self)


def create_purchase_or_invoice(toc, data):
    whitelist = {'org', 'items', 'buyerName', 'buyerAddress', 'buyerPhone',
                 'buyerEmail', 'buyerAnnotation', 'buyerReference', 'date',
                 'expiryDate', 'extraText', 'paymentTerms', 'total'}
    data, = data
    diff = set(data) - whitelist
    if diff:
        raise cAttrPermError(diff.pop(), toc._fullname, None)

    for index, item in enumerate(data['items']):
        data['items'][index] = PurchaseItem(
            product=item['product'],
            quantity=item.get('quantity', PurchaseItem.quantity.default),
            options=item.get('options', []))

    toi = toc(**data)

    if toi.buyerEmail:
        toi.sendConfirmationEmail()

    return toi


@method(Serializable(Quantity(1)))
def invoice(data=Serializable(Quantity(1))):
    invoice = create_purchase_or_invoice(Invoice, data)
    return [{'invoice': str(invoice.id[0]),
             'invoiceUrl': invoice.invoiceUrl[0]}]


@method(Serializable(Quantity(1)))
def purchase(data=Serializable(Quantity(1))):
    purchase = create_purchase_or_invoice(Purchase, data)
    return [{'purchase': str(purchase.id[0]),
             'invoiceUrl': purchase.invoiceUrl[0]}]


class Ticket(TO):
    class purchaseitem(ToiRef(ToiType(PurchaseItem), Quantity(1))):
        pass

    class org(ToiRef(ToiType(accounting.Org), post=Quantity(1))):
        pass

    class name(String(Quantity(1))):
        def on_computation(attr, self):
            return self.purchaseitem[0].name

    class options(Serializable()):
        def on_computation(attr, self):
            return self.purchaseitem[0].optionsWithValue

    class qrcode(String(post=Quantity(1))):
        pass

    class barcode(String(post=Quantity(1))):
        pass

    class random(Int(post=Quantity(1))):
        def on_create(attr, val, self):
            if not val:
                return [random.SystemRandom().getrandbits(32)]
            else:
                return [val[0] & 0xffffffff] # must fit in 32 bits
        on_update = on_create

    class voided(Timestamp):
        pass

    class voidedBy(ToiRef(ToiType(accounting.User))):
        pass

    def canWrite(self, user, attrName):
        return currentUserHasRole(self, 'ticketcheckers', user=user)

    @method(Bool)
    @requireRoles('ticketcheckers')
    def void(self):
        user = ri.getClientUser()
        if self.voided or not user:
            return [False]
        self.voided = [time.time()]
        self.voidedBy = [user]
        return [True]

    @method(None)
    @requireRoles('ticketcheckers')
    def unvoid(self):
        user = ri.getClientUser()
        if not self.voided or not user:
            return
        self.voided = []
        self.voidedBy = []

    def on_create(self):
        self.org = self.purchaseitem[0].product[0].org
        self.allowRead = self.org[0].ug + self.org[0].ticketchecker_ug

        from members import base64long
        # qrcode
        qrcode = urlparse.urljoin(
            config.config.get('accounting', 'baseurl'),
            'ticket/%(ticket)s/%(random)s/%(product)s/' % {
            'ticket' : self.id[0],
            'random' : base64long.encode(self.random[0]),
            'product': self.purchaseitem[0].product[0].id[0]
            })
        key = DSA.construct(json.loads(
                config.config.get('accounting', 'ticket_key')))
        if PYT3:
            h = SHA.new(qrcode.encode('ascii')).digest()
        else:
            h = SHA.new(qrcode).digest()
        k = random.SystemRandom().randint(1, key.q-1)
        sig = tuple(map(base64long.encode, key.sign(h,k)))

        self.qrcode = [qrcode + '%s/%s' % sig]

        self.barcode = ['%040d' % (int(str(self.id[0]),16) << 32 | self.random[0])]

class GiroPaymentFile(TO):

    class fileName(String(Quantity(1))):
        pass

    class data(Blob(Quantity(1))):
        pass

    class state(Enum(Quantity(1))):
        values = 'new', 'processed'
        default = ['new']

    class fileId(String()):
        pass

    class fileType(String()):
        pass

    class timestamp(String()):
        pass

    class seqno(Int(Range(1, 99))):
        pass

    class payments(Relation()):
        related = 'GiroPayment.paymentFile'

    @method(None)
    def match(self):
        for payment in self.payments:
            payment.match()

    @property
    def Parser(self):
        raise NotImplementedError("Subclass must define Parser")

    @property
    def Payment(self):
        raise NotImplementedError("Subclass must define Payment")

    @method(None)
    def process(self):
        parser = self.Parser()

        self.data[0].seek(0)
        for line in self.data[0].readlines():
            parser.parse(line)

        records = parser.records

        self(fileId=[records.file_id],
             timestamp=[records.timestamp])

        log.info('Processing %s', self.fileId[0])

        for account in records.giro_accounts:
            transaction_date = account.transaction_date.strftime('%Y-%m-%d')
            for transaction in account.transactions:
                acctype = {'Bank account': ['account'],
                           'Bank Giro': ['bg']}.get(
                    getattr(transaction, 'payer_account_type', None), [])

                if self.Payment._query(
                        pgnum=account.account,
                        transactionNumber=transaction.transaction_number).run():
                    raise RuntimeError('Duplicate transaction: %s %s',
                                       account.account,
                                       transaction.transaction_number)

                payment = self.Payment(
                    paymentFile=[self],
                    transactionNumber=[transaction.transaction_number],
                    pgnum=[account.account],
                    refs=transaction.customer_refs,
                    amount=[transaction.amount],
                    messages=transaction.messages,
                    transaction_date=transaction_date,
                    payingAccount=transaction.payer_account,
                    payingAccountType=acctype,
                    payingOrgno=transaction.payer_organization_number,
                    )

                if (transaction.sender_names or
                    transaction.sender_addresses or
                    transaction.sender_postal_code or
                    transaction.sender_city or
                    transaction.sender_country_code):
                    payment(
                        payerAddress=PGAddress(
                            allowRead=payment.allowRead, # test me
                            name=transaction.sender_names,
                            address=transaction.sender_addresses,
                            postalCode=transaction.sender_postal_code,
                            city=transaction.sender_city,
                            country=transaction.sender_country_code))


                if (transaction.payer_names or
                    transaction.payer_addresses or
                    transaction.payer_postal_code or
                    transaction.payer_city or
                    transaction.payer_country_code):
                    payment(
                        payingAccountAddress=PGAddress(
                            allowRead=payment.allowRead, # test me
                            name=transaction.payer_names,
                            address=transaction.payer_addresses,
                            postalCode=transaction.payer_postal_code,
                            city=transaction.payer_city,
                            country=transaction.payer_country_code))

        self(state=['processed'])


# Ought to be GiroAddress, but keep it to eliminate conversion
class PGAddress(TO):

    class name(String(QuantityMax(2))):
        pass

    class address(String(QuantityMax(2))):
        pass

    class postalCode(String(QuantityMax(1))):
        pass

    class city(String(QuantityMax(1))):
        pass

    class country(String(QuantityMax(1))):
        pass


class Payment(TO):

    class paymentProvider(ToiRef(ToiType(accounting.PaymentProvider),
                                 QuantityMax(1))):
        pass

    class refundable(Bool(Quantity(1))):

        def on_computation(attr, self):
            return [False]

    class org(ToiRef(ToiType(accounting.Org), QuantityMax(1))):
        pass

    class matchedPurchase(Relation(QuantityMax(1))):
        related = 'BasePurchase.matchedPayments'

    class approved(Bool(Quantity(1))):
        default = [False]

    class transaction_date(String(Regexp(date_re), post=Quantity(1))):
        def on_create(attr, value, self):
            if not value:
                value = [time.strftime('%Y-%m-%d')]
            return value

    class amount(Decimal()):
        default = [decimal.Decimal('0.00')]
        precision = 2

    class buyerdescr(String(QuantityMax(1))):
        pass

    class confirmationEmailSent(Bool(Quantity(1))):
        default = [False]

    @method(Serializable(Quantity(1)))
    def suggestVerification(self):
        # This method is used both by the client interface, and the
        # approvePayments BLM method.
        # Thus some data is reported in two formats (string/decimal).
        org = self.org[0]
        suggestion = {
            'transaction_date': self.transaction_date[0],
            'accounting': org.current_accounting[0].id[0]
            }
        try:
            provider = self.paymentProvider[0]
            series = provider.series[0] if provider.series else None
            account = provider.account[0] if provider.account else None
            suggestion['paymentProvider'] = True
        except IndexError:
            series = None
            account = None
            suggestion['paymentProvider'] = False

        suggestion['series'] = series

        buyer = self.buyerdescr[0] if self.buyerdescr else ''

        missing_accounts = set()

        def fmt_account(number, cache={}):
            try:
                data = cache[number]
            except KeyError:
                try:
                    toi, = accounting.Account._query(
                        number=number,
                        accounting=org.current_accounting).run()
                    data = {'id': toi.id[0], 'number': number}
                except ValueError:
                    data = {'id': None, 'number': number}
                    if number:
                        missing_accounts.add(number)
                cache[number] = data
            return data

        def fmt_amount(amount):
            return {'decimal': amount,
                    'json': int((amount * 100).quantize(1))}

        suggestion['transactions'] = transactions = []
        transactions.append({'account': fmt_account(account),
                             'text': buyer,
                             'amount': fmt_amount(self.amount[0])})

        if self.matchedPurchase:
            purchase = self.matchedPurchase[0]
            balanced = self.amount == purchase.total
            for item in purchase.items:
                if item.quantity[0] == 1:
                    fmt = '%(buyer)s, %(product)s'
                else:
                    fmt = '%(buyer)s, %(product)s (%(quantity)s)'

                for number, amount in sorted(item.accountingRules.items()):
                    text = fmt % {'buyer': buyer,
                                  'product': item.product[0].name[0],
                                  'quantity': item.quantity[0]}

                    amount *= -1 * item.quantity[0]
                    transactions.append({
                            'account': fmt_account(number),
                            'amount': fmt_amount(amount),
                            'text': text})
                if item.vatAccount:
                    transactions.append({
                            'account': fmt_account(item.vatAccount[0]),
                            'amount': fmt_amount(-1 * item.totalVat[0]),
                            'text': text})
        else:
            purchase = None
            balanced = False

        suggestion['matchedPurchase'] = purchase
        suggestion['balanced'] = balanced
        suggestion['missingAccounts'] = list(sorted(missing_accounts))
        suggestion['valid'] = all([purchase, balanced, not missing_accounts,
                                   account, series])
        return [suggestion]

    @method(None)
    def sendConfirmationEmail(self, force=Bool(QuantityMax(1))):
        force = any(force)
        if not force and self.confirmationEmailSent[0]:
            # don't send mail if one has already been sent
            return

        try:
            purchase, = self.matchedPurchase
        except ValueError:
            log.warn('Payment %s lacks a matched purchase.', self.id[0])
            return

        kw = {}
        if purchase.paymentState == ['paid']:
            template = 'email/payment-confirmation'
        elif purchase.paymentState == ['partial']:
            template = 'email/partial-payment-confirmation'
            try:
                pgp = accounting.PlusgiroProvider._query(org=self.org).run()
                kw['plusgiro'] = pgp[0].pgnum[0]
            except IndexError:
                pass
        elif purchase.paymentState == ['unpaid']:
            # what to do here?
            return

        sender =  'no-reply@' + config.config.get('accounting',
            'smtp_domain')
        replyto = None
        if self.org[0].email:
            replyto = getaddresses(self.org[0].email)[0][1]

        body, headers = templating.as_mail_data(template,
                                                org=self.org[0],
                                                payment=self,
                                                sender=sender,
                                                replyto=replyto,
                                                purchase=purchase,
                                                **kw)

        log.info('Sending payment confirmation email for %s to %s',
                 self.id[0], purchase.buyerEmail[0])
        orgid = str(self.org[0].id[0])
        mail.sendmail(*mail.makemail(body, envfrom=orgid, **headers),
                       identity=orgid)
        self.confirmationEmailSent = [True]

    def calc_buyerdescr(self):
        if self.matchedPurchase:
            if [bn for bn in self.matchedPurchase[0].buyerName if bn]:    #filter(None, self.matchedPurchase[0].buyerName)
                self.buyerdescr = self.matchedPurchase[0].buyerName

    def canWrite(self, user, attrName):
        return currentUserHasRole(self, 'accountants', user=user)

    def on_create(self):
        if not self.org:
            if self.paymentProvider:
                self.org = self.paymentProvider[0].org
            elif self.matchedPurchase:
                self.org = self.matchedPurchase[0].org

        if self.org:
            self.allowRead = self.org[0].ug

        if self.matchedPurchase:
            self.matchedPurchase[0].registerPayment(self)
            self.calc_buyerdescr()

    def on_update(self, newAttrValues):
        if 'matchedPurchase' in newAttrValues:
            purchases, _ = difference(newAttrValues['matchedPurchase'],
                                      self.matchedPurchase)
        else:
            purchases = []

        self._update(newAttrValues)

        for toi in purchases:
            toi.registerPayment(self)


@method(None)
def sendPaymentConfirmationEmail(payment=ToiRef(ToiType(Payment), Quantity(1))):
    payment[0].sendConfirmationEmail()


# for direct interface:
@method(Serializable(Quantity(1)))
def suggestVerification(payment=ToiRef(ToiType(Payment), Quantity(1))):
    return payment[0].suggestVerification()


class GiroPayment(Payment):

    class paymentFile(Relation(Quantity(1))):
        related = 'GiroPaymentFile.payments'

    class transactionNumber(String(QuantityMax(1))):
        pass

    # XXX Ought to be gironum or so, kept to eliminate conversion
    class pgnum(PGNum(Quantity(1))):
        pass

    # xxx we really want to find the ocr number
    class refs(String()):
        pass

    class messages(String()):
        pass

    class ocr(String(QuantityMax(1))):

        def on_computation(attr, self):
            return self.refs[:1] # xxx verify that this is a sane assumtion

    class payingAccount(String()):
        pass

    class payingAccountType(Enum(QuantityMax(1))):
        values = ['account', 'bg']

    class payingOrgno(String(QuantityMax(1))):
        pass

    class payerAddress(ToiRef(ToiType(PGAddress), QuantityMax(1))):
        pass

    class payingAccountAddress(ToiRef(ToiType(PGAddress), QuantityMax(1))):
        pass

    @method(None)
    def match(self):
        # xxx this query is naive as we're not certain only ocr
        # numbers are present in refs
        if self.paymentProvider:
            purchases = BasePurchase._query(
                org=self.paymentProvider[0].org,
                ocr=self.refs).run()
            assert len(purchases) <= 1
            if self.matchedPurchase and purchases != self.matchedPurchase:
                raise RuntimeError # This shouldn't happen [TM]

            for purchase in purchases:
                if purchase not in self.matchedPurchase:
                    purchase.registerPayment(self)
            self.matchedPurchase = purchases

        if not self.matchedPurchase:
            log.warn('Failed to match Payment %s with Purchase',
                     self.id[0])

        self.calc_buyerdescr()

    def calc_buyerdescr(self):
        if self.matchedPurchase:
            if [bn for bn in self.matchedPurchase[0].buyerName if bn]:    #filter(None, self.matchedPurchase[0].buyerName)
                self.buyerdescr = self.matchedPurchase[0].buyerName
                return
        for address in self.payerAddress + self.payingAccountAddress:
            for name in address.name:
                if name:
                    self.buyerdescr = [name]
                    return

class PGPayment(GiroPayment):

    def on_create(self):
        self.paymentProvider = accounting.PlusgiroProvider._query(
            pgnum=self.pgnum).run()
        super(PGPayment, self).on_create()

class PGPaymentFile(GiroPaymentFile):
    @property
    def Parser(self):
        from members.incoming_payments import PGParser
        return PGParser

    @property
    def Payment(self):
        return PGPayment

class BGPayment(GiroPayment):

    # XXX pgnum for legacy reasons
    def on_create(self):
        self.paymentProvider = accounting.BankgiroProvider._query(
            bgnum=self.pgnum).run()
        super(BGPayment, self).on_create()

class BGPaymentFile(GiroPaymentFile):
    @property
    def Parser(self):
        from members.incoming_payments import BGParser
        return BGParser

    @property
    def Payment(self):
        return BGPayment

class PaysonPayment(Payment):

    class purchaseId(String(Quantity(1))):
        pass

    class senderEmail(String(Quantity(1))):
        pass

    class token(String(Quantity(1))):
        pass

    class receiverFee(Decimal(Quantity(1))):
        pass

    class receiverEmail(String(Quantity(1))):
        pass

    class type(String(Quantity(1))):
        pass

    class refundable(Bool(post=Quantity(1))):

        def on_computation(attr, self):
            return [self.type[0] == 'TRANSFER']

    @method(ToiRef(ToiType(Payment)))
    def refund(self):
        from accounting import payson
        try:
            payson.refund(self)
            return [PaysonPayment(
                    paymentProvider=self.paymentProvider,
                    purchaseId=self.purchaseId,
                    senderEmail=self.senderEmail,
                    token=self.token,
                    receiverFee=[-self.receiverFee[0]],
                    receiverEmail=self.receiverEmail,
                    type=['refund'],
                    buyerdescr=self.buyerdescr,
                    amount=[-self.amount[0]])]
        except payson.PaysonError:
            pass

        raise cBlmError('Payson refund failed')


class SeqrPayment(Payment):

    class refundable(Bool(Quantity(1))):

        def on_computation(attr, self):
            return [True]

    class paymentDate(Timestamp(Quantity(1))):
        pass

    class invoiceReference(String(Quantity(1))):
        pass

    class ersReference(String(Quantity(1))):
        pass

    class paymentReference(String(Quantity(1))):
        pass

    class payerTerminalId(String(QuantityMax(1))):
        pass

    class receiverName(String):
        pass

    @method(ToiRef(ToiType(Payment)))
    def refund(self):
        from accounting import seqr
        try:
            ersReference = seqr.refund(self.id[0])
            return [SeqrPayment(
                paymentProvider=self.paymentProvider,
                ersReference=ersReference,
                paymentReference=self.paymentReference,
                invoiceReference=self.invoiceReference,
                paymentDate=[time.time()],
                buyerdescr=self.buyerdescr,
                amount=[-self.amount[0]])]
        except seqr.SeqrError:
            raise cBlmError('Seqr refund failed')


class StripePayment(Payment):

    class refundable(Bool(Quantity(1))):

        def on_computation(attr, self):
            return [True]

    class json_data(String(QuantityMax(1))):
        pass

    class charge_id(String(Quantity(1))):
        pass

    class currency(String(Quantity(1))):
        pass

    class paymentDate(Timestamp(Quantity(1))):
        pass

    @method(ToiRef(ToiType(Payment)))
    def refund(self):
        access_token = self.paymentProvider[0].access_token[0]
        charge = stripe.Charge.retrieve(self.charge_id[0], api_key=access_token)
        refund = charge.refunds.create()
        return [StripePayment(
            charge_id=[refund.id],
            amount=[-decimal.Decimal(refund.amount) / 100],
            paymentDate=[refund.created],
            currency=[refund.currency.upper()],
            json_data=[json.dumps(refund)],
        )]

@method(ToiRef(ToiType(Purchase)))
def handleStripeInvoice(data=Serializable(Quantity(1)),
                        provider=ToiRef(ToiType(accounting.StripeProvider), Quantity(1))):
    org = provider[0].org[0]
    data = stripe.convert_to_stripe_object(data[0], provider[0].access_token[0])
    invoice = data.data.object.refresh()
    customer = stripe.Customer.retrieve(invoice.customer,
                                        api_key=provider[0].access_token[0])

    items = []
    for lineno, line in enumerate(invoice.lines.data,1):
        data = { 'quantity' : [line.quantity or 1],
                 'total' : [decimal.Decimal(line.amount) / 100],
                 'name' : [line.description or 'line %d' % lineno],
                 'allowRead' : org.ug
                 }
        data['price'] = [data['total'][0] / data['quantity'][0]]
        items.append(PurchaseItem(**data))

    purchase = Purchase(
        org = [org], total = [decimal.Decimal(invoice.total) / 100],
        currency = [invoice.currency.upper()],
        buyerName = [customer.description] if customer.description else [],
        buyerEmail = [customer.email],
        date = [invoice.date],
        paymentState = ['paid' if invoice.paid else 'unpaid'],
        items = items)

    invoice.metadata['toiid'] = str(purchase.id[0])
    invoice.save()

    return [purchase]


@method(ToiRef(ToiType(StripePayment)))
def handleStripeCharge(data=Serializable(Quantity(1)),
                        provider=ToiRef(ToiType(accounting.StripeProvider), Quantity(1))):
    org = provider[0].org[0]
    data = stripe.convert_to_stripe_object(data[0], provider[0].access_token[0])
    charge = data.data.object.refresh()

    if not charge.paid:
        return []

    if StripePayment._query(charge_id=charge.id).run():
        return []

    invoice = charge.get('invoice')
    purchase = []
    if invoice:
        invoice = stripe.Invoice.retrieve(invoice,
                                          api_key=provider[0].access_token[0])
        purchaseid = invoice.metadata.get('toiid')
        if purchaseid:
            purchase = BasePurchase._query(id=ObjectId(purchaseid)).run()

    payment = StripePayment(
        paymentProvider = provider,
        amount=[decimal.Decimal(charge.amount) / 100],
        paymentDate=[charge.created],
        transaction_date=[time.strftime('%Y-%m-%d',
                                        time.localtime(charge.created))], # xxx
        charge_id=[charge.id],
        currency=[charge.currency.upper()],
        json_data=[json.dumps(charge)],
        matchedPurchase=purchase
        )

    return [payment]


class SwishPayment(Payment):

    class refundable(Bool(Quantity(1))):

        def on_computation(attr, self):
            return [True]

    class paymentReference(String(QuantityMax(1))):
        pass

    class swishId(String(QuantityMax(1))):
        pass

    class payerAlias(String(Quantity(1))):
        pass

    class currency(String(Quantity(1))):
        pass

    class json_data(String(QuantityMax(1))):
        pass

    @method(ToiRef(ToiType(Payment)))
    def refund(self):
        import accounting.swish
        provider = self.paymentProvider[0]
        with accounting.swish.Client.from_toi(provider) as client:
            payment = client.refund(
                id=self.id[0],
                payerPaymentReference=str(self.id[0]),
                originalPaymentReference=self.paymentReference[0],
                payeeAlias=self.payerAlias[0],
                amount=str(self.amount[0].quantize(decimal.Decimal('1.00'))),
                currency=self.currency[0])
        return [
            SwishPayment(
                paymentProvider=self.paymentProvider,
                swishId=[payment.id],
                payerAlias=self.paymentProvider[0].swish_id,
                currency=self.currency,
                buyerdescr=self.buyerdescr,
                amount=[-self.amount[0]]
            )
        ]


@method(ToiRef(ToiType(SwishPayment)))
def handleSwishPayment(provider=ToiRef(ToiType(accounting.SwishProvider), Quantity(1)),
                       purchase=ToiRef(ToiType(BasePurchase), Quantity(1)),
                       data=Serializable(Quantity(1)),):
    org = provider[0].org[0]
    data, = data
    payment = swish.Payment.from_dict(data)

    if SwishPayment._query(swishId=payment.id).run():
        return []

    if payment.status == 'PAID':
        print('creating swish payment')
        toi = SwishPayment(
            paymentProvider=provider,
            swishId=[payment.id],
            payerAlias=[payment.payerAlias],
            paymentReference=[payment.paymentReference],
            amount=[payment.amount],
            transaction_date=[time.strftime('%Y-%m-%d',
                                            time.localtime(payment.datePaid))],
            currency=[payment.currency],
            json_data=[json.dumps(data)],
            matchedPurchase=purchase,
        )
        return [toi]


class IzettlePayment(Payment):

    # paymentProvider inherited
    
    # transaction_date inherited

    class transaction_time(String(Quantity(1))):
        pass
    
    class receipt_number(Int(Quantity(1))):
        pass

    # amount inherited

    class izettle_fee(Decimal(Quantity(1))):
        default = [decimal.Decimal('0.00')]
        precision = 2

    class netto(Decimal(Quantity(1))):
        # amount - izettle_fee = netto
        default = [decimal.Decimal('0.00')]
        precision = 2

    class payment_class_text(String(QuantityMax(1))):
        pass

    class payment_class(Enum(post=Quantity(1))):
        values = ('card', 'cash')
        default = ['card']

    class is_return(Bool(post=Quantity(1))):
        # True if the money goes to the buyer
        default = [False]
    
    class card_type(String(Quantity(1))):
        pass

    class last_digits(String(Quantity(1))):
        pass

    class cashier(String(Quantity(1))):
        pass

    class device(String(Quantity(1))):
        pass

    class description(String(QuantityMax(1))):
        pass

    def parse_description(self, products, prodtoimap):
        # products = {'Kaka': {acctoi: decimal.Decimal, acctoi2: decimal.Decimal}}
            
        shoppinglist = []
        for item in self.description[0].split(','):
            item = item.strip()
            if item in products:
                customUnit = prodtoimap[item].customUnit
                for acctoi, amount in products[item]:
                    shoppinglist.append((acctoi, item, 1, customUnit, amount))
                continue
            try:
                (nr, times, item) = item.split(' ', 2)
            except ValueError:
                return []
            if item in products:
                if times != 'x':
                    return []
                # We hope selling fractions of custom unit is expressed in a
                # way parsable as Decimal. 
                nr = decimal.Decimal(nr)
                customUnit = prodtoimap[item].customUnit
                for acctoi, amount in products[item]:
                    shoppinglist.append((acctoi, item, nr, customUnit, amount*nr))
        return shoppinglist

    
    @method(Serializable())
    def suggestVerification(self):
        # This method is used both by the client interface, and the
        # approvePayments BLM method.
        # Thus some data is reported in two formats (string/decimal).
        org = self.org[0]
        productmap, prodtoimap, accounttoimap = IzettleProduct.product_map(org)
                    
        accounting = None
        for rule in productmap.values():
            for account, _ in rule:
                accounting = account.accounting[0]
                break
            if accounting:
                break
        else:
            accounting = org.current_accounting[0]

        suggestion = {
            'transaction_date': self.transaction_date[0],
            'accounting': accounting.id[0]
            }
        try:
            provider = self.paymentProvider[0]
            series = provider.series[0] if provider.series else None
            card_account = provider.account[0] if provider.account else None
            card_accounttoi = accounttoimap[card_account]
            cash_account = provider.cash_account[0] if provider.cash_account else None
            cash_accounttoi = accounttoimap[cash_account]
            fee_account = provider.fee_account[0] if provider.fee_account else None
            fee_accounttoi = accounttoimap[fee_account]
            suggestion['paymentProvider'] = True
        except IndexError:
            series = None
            card_account = None
            card_accounttoi = None
            cash_account = None
            cash_accounttoi = None
            fee_account = None
            fee_accounttoi = None
            suggestion['paymentProvider'] = False

        suggestion['series'] = series
        suggestion['matchedPurchase'] = None

        text = "iZettle (%s)(%s): %s" % (self.cashier[0], self.receipt_number[0], self.description[0])

        transactions = []
        
        if self.payment_class[0] == 'card':
            cardtrans = {
                'account': {'id': card_accounttoi.id[0],
                            'number': card_accounttoi.number[0]},
                'text': text,
                'amount': {'decimal': self.amount[0], 'json': int(self.amount[0]*100)}
            }
            transactions.append(cardtrans)
        elif self.payment_class[0] == 'cash':
            cashtrans = {
               'account': {'id': cash_accounttoi.id[0],
                            'number': cash_accounttoi.number[0]},
               'text': text,
               'amount': {'decimal': self.amount[0], 'json': int(self.amount[0]*100)}
            }
            transactions.append(cashtrans)

        for acctoi, descr, count, customUnit, amount in self.parse_description(productmap, prodtoimap):
            account = {
                'id': acctoi.id[0],
                'number': acctoi.number[0]
            }

            if customUnit != []:
                customUnit = customUnit[0]
            else:
                customUnit = ''
            
            if count == 1:
                text = descr
            else:
                text = "%s (%d%s)" % (descr, count, customUnit)
                #text = "%s (%d)" % (descr, count)

            if self.is_return[0]:
                amount = -amount
            
            amount = {
                'decimal': -amount,
                'json': -int(amount*100)
            }
            
            transaction = {
                'account': account,
                'amount': amount,
                'text': text
            }
            
            transactions.append(transaction)
            
        try:
            fee = self.izettle_fee[0]
            assert fee != decimal.Decimal('0.0')
        except (KeyError, AssertionError):
            pass
        else:
            reducesale = {
                'account': {'id': card_accounttoi.id[0],
                            'number': card_accounttoi.number[0]},
                'text': 'iZettle fee',
                'amount': {'decimal': -fee, 'json': -int(fee*100)}
            }
            transactions.append(reducesale)
            increasefee = {
                'account': {'id': fee_accounttoi.id[0],
                            'number': fee_accounttoi.number[0]},
                'text': 'iZettle fee',
                'amount': {'decimal': fee, 'json': int(fee*100)}
            }
            transactions.append(increasefee)

        balanced = sum(t['amount']['decimal'] for t in transactions) == 0

        suggestion['transactions'] = transactions
        suggestion['valid'] = bool(balanced and series)
        suggestion['balanced'] = balanced
        suggestion['missingAccounts'] = []

        return [suggestion]

    
class IzettleRebate(Payment):

    # paymentProvider inherited
    
    # transaction_date inherited

    class transaction_time(String(Quantity(1))):
        pass
    
    # amount inherited

    class transaction_type(String(Quantity(1))):
        pass

    class timespan(String(QuantityMax(1))):
        pass

    @method(Serializable())
    def suggestVerification(self):
        # This method is used both by the client interface, and the
        # approvePayments BLM method.
        # Thus some data is reported in two formats (string/decimal).
        org = self.org[0]
        productmap, _, accounttoimap = IzettleProduct.product_map(org)
                    
        accounting = org.current_accounting[0]

        suggestion = {
            'transaction_date': self.transaction_date[0],
            'accounting': accounting.id[0]
            }
        try:
            provider = self.paymentProvider[0]
            series = provider.series[0] if provider.series else None
            card_account = provider.account[0] if provider.account else None
            card_accounttoi = accounttoimap[card_account]
            fee_account = provider.fee_account[0] if provider.fee_account else None
            fee_accounttoi = accounttoimap[fee_account]
            suggestion['paymentProvider'] = True
        except IndexError:
            series = None
            card_account = None
            card_accounttoi = None
            fee_account = None
            fee_accounttoi = None
            suggestion['paymentProvider'] = False

        suggestion['series'] = series
        suggestion['matchedPurchase'] = None

        text = "iZettle: %s %s" % (self.transaction_type[0], self.timespan[0])
        
        transactions = [
            {
                'account': {'id': card_accounttoi.id[0],
                            'number': card_accounttoi.number[0]},
                'text': text,
                'amount': {'decimal': self.amount[0], 'json': int(self.amount[0]*100)}
            },
            {
                'account': {'id': fee_accounttoi.id[0],
                            'number': fee_accounttoi.number[0]},
                'text': text,
                'amount': {'decimal': -self.amount[0], 'json': -int(self.amount[0]*100)}
            }
        ]

        balanced = sum(t['amount']['decimal'] for t in transactions) == 0

        suggestion['transactions'] = transactions
        suggestion['valid'] = bool(balanced and series)
        suggestion['balanced'] = balanced
        suggestion['missingAccounts'] = []

        return [suggestion]
        
    

    
@method(None)
def import_izettle_payments(org=ToiRef(ToiType(accounting.Org), Quantity(1)),
                            filename=String(Quantity(1)),
                            filedata=String(Quantity(1))):
    from accounting import izettle_import
    org, = org
    if PYT3:
        filedata = filedata[0]  # .encode()
    else:
        filedata = filedata[0].decode('base64')
    try:
        transactions, rebates = izettle_import.parse_transactions(filedata)
    except Exception:
        raise cBlmError('This does not look like an iZettle transactions file.')

    provider, = accounting.IzettleProvider._query(
        org=org, _attrList='account cash_account fee_account series'.split()).run()
    old_payments = IzettlePayment._query(
        org=org,
        receipt_number=q.In([t['receipt_number'] for t in transactions]),
        _attrList=['receipt_number']).run()
    old_receipts = set(op.receipt_number[0] for op in old_payments)
    
    old_rebates = IzettleRebate._query(org=org,
                                          _attrList=['timespan']).run()
    old_rebate_timespans = set(rebate.timespan[0] for rebate in old_rebates)

    org._preload('current_accounting ug'.split())

    with ri.cache.set({accounting.Account.updateBalance.DELAY: set()}) as cache:
        payments = []
        for t in transactions:
            if int(t['receipt_number']) not in old_receipts:
                paytoi = IzettlePayment(org=org,
                                        paymentProvider=provider,
                                        **t)
                payments.append(paytoi)

        for rebate in rebates:
            if rebate['timespan'] not in old_rebate_timespans:
                rebtoi = IzettleRebate(org=org,
                                       paymentProvider=provider,
                                       **rebate)
                payments.append(rebtoi)
            
        approvePayments(payments)
        accounts = cache[accounting.Account.updateBalance.DELAY]

    for account in accounts:
        account.updateBalance()

    # Save record of upload
    TransactionsUpload(org=org, filename=filename, filedata=filedata, resultingPayments=len(payments))
    
    return {'created': len(payments)}


class SimulatorPayment(Payment):

    class refundable(Bool(Quantity(1))):

        def on_computation(attr, self):
            return [True]

    @method(ToiRef(ToiType(Payment)))
    def refund(self):
        return [SimulatorPayment(
            org=self.org,
            paymentProvider=self.paymentProvider,
            buyerdescr=self.buyerdescr,
            amount=[-self.amount[0]])]


@method(Serializable(Quantity(1)))
def approvePayment(data=Serializable(Quantity(1))):
    data, = data
    paymentId = data.pop('payment')
    payment, = Payment._query(id=paymentId).run()
    payment.approved = [True]
    provider = payment.paymentProvider[0]
    acc = provider.org[0].current_accounting

    verification = accounting.Verification(
        accounting=acc,
        series=data['series'],
        externalRef=[str(paymentId)],
        transaction_date=[data['transaction_date']])

    for transData in data['transactions']:
        accounting.Transaction(
            verification=[verification],
            version=[0],
            amount=[decimal.Decimal(transData['amount']) / 100],
            text=[transData['text']],
            account=accounting.Account._query(
                id=ObjectId(transData['account'])).run()
            )

    return [{'success': True, 'verification': str(verification.id[0])}]


@method(ToiRef(ToiType(Payment)))
def approvePayments(payments=ToiRef(ToiType(Payment))):
    approved = []
    for payment in payments:
        if payment.approved[0]:
            continue

        suggestion, = payment.suggestVerification()

        if not suggestion['valid']:
            continue

        series, = accounting.VerificationSeries._query(
            name=suggestion['series'],
            accounting=suggestion['accounting']).run()

        verification = accounting.Verification(
            accounting=suggestion['accounting'],
            series=series,
            externalRef=list(map(str, payment.id)),
            transaction_date=suggestion['transaction_date'],
            )

        for transData in suggestion['transactions']:
            accounting.Transaction(
                verification=verification,
                version=0,
                amount=transData['amount']['decimal'],
                text=transData['text'],
                account=transData['account']['id'])

        payment.approved = [True]
        approved.append(payment)
    return approved


@method(ToiRef(ToiType(Payment), Quantity(1)))
def generateFakePayment(
    paymentProvider=ToiRef(ToiType(accounting.SimulatorProvider), Quantity(1)),
    purchase=ToiRef(ToiType(BasePurchase), Quantity(1)),
    amount=Decimal(QuantityMax(1))):
    if not currentUserHasRole(paymentProvider[0], 'members'):
        raise cBlmError('Permission denied')
    if paymentProvider[0].org[0] != purchase[0].org[0]:
        raise cBlmError('Illegal arguments')
    with ri.setuid():
        payment = Payment(paymentProvider=paymentProvider,
                          matchedPurchase=purchase,
                          amount=amount or purchase[0].total)
        payment.calc_buyerdescr()
    return [payment]


@method(ToiRef(ToiType(Payment), Quantity(1)))
def manualPayment(
    purchase=ToiRef(ToiType(BasePurchase), Quantity(1))):
    if not currentUserHasRole(purchase[0], 'members'):
        raise cBlmError('Permission denied')
    with ri.setuid():
        provider = purchase[0].org[0].get_manual_payment_provider()
        payment = Payment(paymentProvider=provider,
                          matchedPurchase=purchase,
                          amount=purchase[0].total)
        payment.calc_buyerdescr()
    return [payment]


# xxx rename me when accounting-client ui is committed
@method(ToiRef(ToiType(Payment), Quantity(1)))
def manualPayment_ex(
    purchase=ToiRef(ToiType(BasePurchase), Quantity(1)),
    verificationData=Serializable(Quantity(1))):
    if not currentUserHasRole(purchase[0], 'members'):
        raise cBlmError('Permission denied')
    with ri.setuid():
        provider = purchase[0].org[0].get_manual_payment_provider()
        payment = Payment(paymentProvider=provider,
                          matchedPurchase=purchase,
                          amount=purchase[0].total)
        payment.calc_buyerdescr()
        data = {}
        data.update(verificationData[0])
        data['payment'] = payment.id[0]
        approvePayment([data])
    return [payment]


class TransactionsUpload(TO):

    class org(ToiRef(Quantity(1), ToiType(accounting.Org))):
        pass
    
    class filename(String(Quantity(1))):
        pass

    class uploadTime(Timestamp(post=Quantity(1))):
        def on_create(attr, value, toi):
            return value or [time.time()]

    class filedata(Blob(Quantity(1))):
        pass

    class resultingPayments(Int(Quantity(1))):
        pass

    @requireRoles('accountants')
    def on_create(self):
        self.allowRead = self.org[0].ug

    @staticmethod
    def sort_uploadTime_key(self):
        return self['uploadTime'][0]
    sort_uploadTime_attrs = ['uploadTime']



@method(None)
def upgrade():
    log.info('Upgrading members BLM')
