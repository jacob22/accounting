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

try:
    from StringIO import StringIO   #py2
except ImportError:
    from io import StringIO         #py3
import datetime, decimal, os, py
from pytransact.testsupport import BLMTests, Fake
from members import incoming_payments, paymentgen
import blm.members

here = os.path.dirname(__file__)
root = os.path.abspath(os.path.join(here, '..', '..'))

class TestImportPGPaymentFile(BLMTests):

    def test_from_example(self):
        fname = 'total_in_bas_exempelfil.txt'
        with open(os.path.join(root, 'test', fname), 'rb') as f:
            data = f.read()

        pf = blm.members.PGPaymentFile(fileName=[fname], data=[data])
        self.commit()

        pf, = blm.members.PGPaymentFile._query(id=pf.id[0]).run()
        assert pf.fileName == [fname]
        assert pf.data[0].read() == data
        assert pf.state == ['new']

        pf.process()
        self.commit()

        pf, = blm.members.PGPaymentFile._query(id=pf.id).run()

        assert pf.fileName == [fname]
        assert pf.state == ['processed']
        assert pf.fileId == ['TI222222' +
                             '20111025041330123456' + '1' ]
        assert pf.timestamp == ['20111025041330123456']

        assert len(pf.payments) == 9 # 8 regular, 1 reverse

        payment = pf.payments[0]
        assert payment.pgnum == ['10181']
        assert '38952344444' in payment.refs # ocr...
        assert payment.ocr == ['38952344444']
        assert payment.transactionNumber == ['22222333334444451']
        assert payment.amount == [decimal.Decimal('3025.50')]
        assert payment.messages == ['FAKTURANR:38952344444',
                                    'INTERN REF:  9780858',
                                    'FAKTURANR:38952345678',
                                    '38952145778ABC']
        assert payment.payingAccount == ['1234567']
        assert payment.payingAccountType == ['account']
        assert payment.payingOrgno == ['9999999999']

        accAddress = payment.payingAccountAddress[0]
        assert accAddress.name == ['TESTBOLAGET AB']
        assert accAddress.address == ['GATAN 12']
        assert accAddress.postalCode == ['12345']
        assert accAddress.city == ['TESTSTAD']

        payment = pf.payments[2]
        payerAddress = payment.payerAddress[0]
        assert payerAddress.name == ['TESTFABRIKEN AB']
        assert payerAddress.address == ['GATAN 22']
        assert payerAddress.postalCode == ['11111']
        assert payerAddress.city == ['TESTVIKEN']

        # This test doesn't belong here really, but run the .match()
        # code just to make sure it doesn't explode on unrecognized
        # payments as TestMatchPayments doesn't have a test for that
        # a.t.m.
        pf.match()

    def test_fail(self):
        data = 'random gorp\n' * 10

        pf = blm.members.PGPaymentFile(fileName=['some name'], data=[data])
        py.test.raises(Exception, pf.process)

        assert pf.state == ['new']

    def test_block_duplicate_transactions(self):
        fname = 'total_in_bas_exempelfil.txt'
        with open(os.path.join(root, 'test', fname), 'rb') as f:
            data = f.read()

        pf = blm.members.PGPaymentFile(fileName=[fname], data=[data])
        pf.process()
        self.commit()

        data = data.replace(b'00TI222222', b'00TI222223', 1)

        dup = blm.members.PGPaymentFile(fileName=[fname], data=[data])
        py.test.raises(RuntimeError, dup.process)


class TestImportBGPaymentFile(BLMTests):

    def test_from_example(self):
        fname = 'bginbetalningar_exempelfil_1.txt'
        with open(os.path.join(root, 'test', fname), 'rb') as f:
            data = f.read()

        pf = blm.members.BGPaymentFile(fileName=[fname], data=[data])
        self.commit()

        pf, = blm.members.BGPaymentFile._query(id=pf.id[0]).run()
        assert pf.fileName == [fname]
        assert pf.data[0].read() == data
        assert pf.state == ['new']

        pf.process()
        self.commit()

        pf, = blm.members.BGPaymentFile._query(id=pf.id).run()

        assert pf.fileName == [fname]
        assert pf.state == ['processed']
        assert pf.fileId == ['20040525173035010331']
        assert pf.timestamp == ['20040525173035010331']

        assert len(pf.payments) == 7

        payment = pf.payments[0]
        assert payment.pgnum == ['9912346']
        assert '665869' in payment.refs # ocr...
        #assert payment.ocr == ['38952344444']
        assert payment.transactionNumber == ['000120000018']
        assert payment.amount == [decimal.Decimal('1800.00')]
        assert payment.messages == ['Betalning med extra refnr 665869 657375 665661',
                                    '665760']
        assert payment.payingAccount == ['3783511']
        #assert payment.payingAccountType == ['account']
        assert payment.payingOrgno == ['5500001234']

        #accAddress = payment.payingAccountAddress[0]
        #assert accAddress.name ==
        #assert accAddress.address == ['GATAN 12']
        #assert accAddress.postalCode == ['12345']
        #assert accAddress.city == ['TESTSTAD']
        payerAddress = payment.payerAddress[0]
        assert payerAddress.name == [u'Kalles Plåt AB']
        assert payerAddress.address == [u'Storgatan 2']
        assert payerAddress.postalCode == [u'12345']
        assert payerAddress.city == [u'Storåker']

        payment = pf.payments[3]
        assert '525865' in payment.refs # ocr...
        assert payment.ocr == ['525865']

        # This test doesn't belong here really, but run the .match()
        # code just to make sure it doesn't explode on unrecognized
        # payments as TestMatchPayments doesn't have a test for that
        # a.t.m.
        pf.match()

    def test_fail(self):
        data = 'random gorp\n' * 10

        pf = blm.members.BGPaymentFile(fileName=['some name'], data=[data])
        py.test.raises(Exception, pf.process)

        assert pf.state == ['new']

    def test_block_duplicate_transactions(self):
        fname = 'bginbetalningar_exempelfil_2.txt'
        with open(os.path.join(root, 'test', fname), 'rb') as f:
            data = f.read()

        pf = blm.members.BGPaymentFile(fileName=[fname], data=[data])
        pf.process()
        self.commit()

        #data = data.replace('00TI222222', '00TI222223', 1)

        dup = blm.members.BGPaymentFile(fileName=[fname], data=[data])
        py.test.raises(RuntimeError, dup.process)


class TestMatchPayments(BLMTests):

    def setup_method(self, method):
        super(TestMatchPayments, self).setup_method(method)
        self.org = blm.accounting.Org(subscriptionLevel=['subscriber'])
        self.pgp = blm.accounting.PlusgiroProvider(org=self.org, pgnum=['1234-5674'])

        self.product1 = blm.members.Product(
            org=[self.org],
            name=['Product #1'],
            available=[True],
            accountingRules={'1000': decimal.Decimal('10.00'),
                             '2500': decimal.Decimal('25.00')})

    def test_simple(self):
        blm.members.Purchase(
            items=[blm.members.PurchaseItem(product=self.product1)])
        self.commit()

        purchases = blm.members.Purchase._query().run()
        purchase, = purchases

        timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')

        out = StringIO()
        paymentgen.generate_pg_file(self.pgp, purchases, timestamp, 1, 1, out=out)

        pf = blm.members.PGPaymentFile(fileName=['foo.txt'], data=[out.getvalue()])
        pf.process()
        self.commit()

        paymentFile, = blm.members.PGPaymentFile._query().run()
        assert len(paymentFile.payments) == 1

        payment, = paymentFile.payments
        # sanity
        assert payment.paymentProvider == [self.pgp]
        assert payment.amount == [decimal.Decimal('35.00')]
        assert payment.refs == purchase.ocr
        assert payment.matchedPurchase == []

        paymentFile.match()
        purchase, = blm.members.Purchase._query().run()
        assert payment.matchedPurchase == [purchase]
        assert purchase.paymentState == ['paid']
