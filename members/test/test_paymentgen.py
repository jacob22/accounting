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
    
from pytransact.testsupport import BLMTests
import blm.members

from .. import paymentgen


def test_fixedWidth():
    @paymentgen.fixedWidth
    def foo(out):
        out.write('foo')
        out.write('bar')
        out.write('baz')

    out = StringIO()
    foo(out=out)

    out.seek(0)
    lines = out.readlines()
    for line in lines:
        assert line[-1] == '\n'
        assert len(line[:-1]) == 80

    assert [line.strip() for line in lines] == ['foo', 'bar', 'baz']


class TestPaymentGenerator(BLMTests):

    def setup_method(self, method):
        super(TestPaymentGenerator, self).setup_method(method)
        self.org = blm.accounting.Org(subscriptionLevel=['subscriber'])
        self.pgp = blm.accounting.PlusgiroProvider(org=self.org, pgnum=['1234-5674'])

        self.product1 = blm.members.Product(
            name=['Gadget'],
            org=[self.org],
            accountingRules={'3100': '10.00'})

        self.product2 = blm.members.Product(
            name=['Thing'],
            org=[self.org],
            accountingRules={'3200': '20.00'})

    def test_generate_pg_transaction(self):
        purchase = blm.members.Purchase(
            items=[blm.members.PurchaseItem(product=self.product1),
                   blm.members.PurchaseItem(product=self.product2,
                                            quantity=2,
                                            options=['foo'])])
        self.commit()

        purchase, = blm.members.Purchase._query(id=purchase.id[0]).run()

        fh = StringIO()
        price, lines = paymentgen.generate_pg_transaction(purchase, 1, out=fh)
        assert price == 5000
        assert lines == 1  # number of lines

        transaction_no = '1' * 17
        bg_no = ' ' * 8
        spare = ' ' * 3

        lines = fh.getvalue().splitlines()

        expect = '''\
20{0:<35}{1:0>15}{2}{3}{4}
'''.format(purchase.ocr[0], price, transaction_no, bg_no, spare)

        result = fh.getvalue()
        assert result == expect

    def test_generate_pg_transactions(self):
        purchase = blm.members.Purchase(
            items=[blm.members.PurchaseItem(product=self.product1),
                   blm.members.PurchaseItem(product=self.product2,
                                            quantity=2,
                                            options=['foo'])])
        self.commit()

        purchase, = blm.members.Purchase._query(id=purchase.id[0]).run()
        purchase.partial_payments = 2

        fh = StringIO()
        
        price, lines = paymentgen.generate_pg_transaction(purchase, 1, out=fh)
        assert price == 5000
        assert lines == 2  # number of lines

        # transaction_no = '1' * 17
        bg_no = ' ' * 8
        spare = ' ' * 3

        lines = fh.getvalue().splitlines()

        expect = '''\
20{0:<35}{1:0>15}{2}{3}{4}
'''.format(purchase.ocr[0], price // 2, '11111111111111111', bg_no, spare)
        expect += '''\
20{0:<35}{1:0>15}{2}{3}{4}
'''.format(purchase.ocr[0], price // 2, '11111111111111121', bg_no, spare)

        result = fh.getvalue()
        assert result == expect

    def test_generate_pg(self, monkeypatch):
        def generate_pg_transaction(purchase, transaction_number, out):
            assert transaction_number == 27
            assert purchase is transactions[0]
            out.write('TRANSACTION')
            return 27, 1
        monkeypatch.setattr(paymentgen, 'generate_pg_transaction', generate_pg_transaction)

        fh = StringIO()
        transactions = [object()]
        num_lines = paymentgen.generate_pg(self.pgp, transactions,
                                           date='20130101', start_tid=27, out=fh)
        assert num_lines == 3

        lines = fh.getvalue().splitlines()
        assert len(lines) == 3

        assert lines[0].strip() == '10{0:<36}SEK20130101'.format('12345674')
        assert lines[1].strip() == 'TRANSACTION'

        tnum = len(transactions)
        total = 27
        assert lines[-1].strip() == '90{0:0>8}{1:0>17}20130101001'.format(tnum, total)

    def test_generate_pg_file(self, monkeypatch):
        def generate_pg(org, purchases, date, start_tid, out):
            assert start_tid == 42
            out.write('PG')
            return 1

        monkeypatch.setattr(paymentgen, 'generate_pg', generate_pg)

        TotalIN_ID = '{0:<12}'.format(paymentgen.TotalIN_ID)

        purchases = [object()]

        #            YYYYMMDDHHMMSS
        timestamp = '20130101040001'

        fh = StringIO()
        paymentgen.generate_pg_file(self.pgp, purchases, timestamp,
                                    file_id=27, start_tid=42, out=fh)

        lines = fh.getvalue().splitlines()
        assert len(lines) == 3

        assert lines[0] == '{0:<80}'.format(
            '00TI00000027  2013010104000100000001TL1TOTALIN-T')

        assert lines[1].strip() == 'PG'

        num_lines = 3
        spare = ' ' * 63
        assert lines[2] == '{0:<80}'.format('99000000000000003')
