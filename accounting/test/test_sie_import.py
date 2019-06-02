# -*- coding: utf-8 -*-
from __future__ import unicode_literals

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
    from StringIO import StringIO         #py2
except ImportError:
    from io import BytesIO as StringIO #py3
import glob, os, py, time
from pytransact import queryops as q
from accounting.sie_import import BaseParser, Parser, SIEImporter, \
    UnsupportedSIEVersion, AppendingParser, DoneException
import blm


class TestLowLevelParser(object):
    def setup(self):
        def input(self, s):
            self.s = s
            self.pos = 0
        BaseParser.input = input # Monkeypatch to reduce lines of code

    def test_consume_label(self):
        for s in [b'#APA  \n', b'#APA \n']:
            p = BaseParser()
            p.input(s)
            assert p.consume_label() == b'#APA'
            assert p.getc() == b'\n'
        for s in [b'#APA  X\n', b'#APA X \n']:
            p = BaseParser()
            p.input(s)
            assert p.consume_label() == b'#APA'
            assert p.getc() == b'X'
        
    def test_consume_string(self):
        for s in [b'""\n', b'"" \n']:
            p = BaseParser()
            p.input(s)
            assert p.consume_string() == b''
            assert p.getc() == b'\n'
        for s in [b'"1"\n', b'"1" \n', b'1\n', b'1 \n']:
            p = BaseParser()
            p.input(s)
            assert p.consume_string() == b'1'
            assert p.getc() == b'\n'
        for s in [b'"1ABC"\n', b'"1ABC" \n', b'1ABC\n', b'1ABC \n']:
            p = BaseParser()
            p.input(s)
            assert p.consume_string() == b'1ABC'
            assert p.getc() == b'\n'
        for s in [b'"1ABC" X\n', b'"1ABC" X \n', b'1ABC X\n', b'1ABC  X\n']:
            p = BaseParser()
            p.input(s)
            assert p.consume_string() == b'1ABC'
            assert p.getc() == b'X'
        for s in [b'"1AB\\"C" X\n', b'"1AB\\"C" X \n']:
            p = BaseParser()
            p.input(s)
            assert p.consume_string() == b'1AB"C'
            assert p.getc() == b'X'

    def test_consume_numeric(self):
        for s in [b'""\n', b'"" \n']:
            p = BaseParser()
            p.input(s)
            assert p.consume_numeric() == b''
            assert p.getc() == b'\n'
        for s in [b'"1"\n', b'"1" \n', b'1\n', b'1 \n']:
            p = BaseParser()
            p.input(s)
            assert p.consume_numeric() == b'1'
            assert p.getc() == b'\n'
        for s in [b'"1234"\n', b'"1234" \n', b'1234\n', b'1234 \n']:
            p = BaseParser()
            p.input(s)
            assert p.consume_numeric() == b'1234'
            assert p.getc() == b'\n'
        for s in [b'"1234" X\n', b'"1234" X \n', b'1234 X\n', b'1234  X\n']:
            p = BaseParser()
            p.input(s)
            assert p.consume_numeric() == b'1234'
            assert p.getc() == b'X'
        for s in [b'"1234"{ X\n', b'"1234"{ X \n', b'1234{ X\n', b'1234{  X\n']:
            p = BaseParser()
            p.input(s)
            assert p.consume_numeric() == b'1234'
            assert p.getc() == b'{'

    def test_consume_object_list(self):
        p = BaseParser() 
        p.input(b'{} \n')
        assert p.consume_object_list() == []
        assert p.getc() == b'\n'
        
        p = BaseParser()
        p.input(b'{"" ""} \n')
        assert p.consume_object_list() == [b'', b'']
        assert p.getc() == b'\n'
        
        p = BaseParser()
        p.input(b'{1 2} \n')
        assert p.consume_object_list() == [b'1', b'2']
        assert p.getc() == b'\n'
        
        p = BaseParser()
        p.input(b'{1 2 } \n')
        assert p.consume_object_list() == [b'1', b'2']
        assert p.getc() == b'\n'
        
        p = BaseParser()
        p.input(b'{ 1 2} \n')
        assert p.consume_object_list() == [b'1', b'2']
        assert p.getc() == b'\n'
        
        p = BaseParser()
        p.input(b'{1 "2"} \n')
        assert p.consume_object_list() == [b'1', b'2']
        assert p.getc() == b'\n'
        
        p = BaseParser()
        p.input(b'{1 "2"   } \n')
        assert p.consume_object_list() == [b'1', b'2']
        assert p.getc() == b'\n'

        p = BaseParser()
        p.input(b'{1 "2\\""   } \n')
        assert p.consume_object_list() == [b'1', b'2"']
        assert p.getc() == b'\n'

    def test_param_parsing(self):
        p = BaseParser()
        p.input(b'abc def\n')
        params = p.read_record('T [T]')
        assert len(params) == 2

        p = BaseParser()
        p.input(b'abc\n')
        params = p.read_record('T [T]')
        assert len(params) == 1

        p = BaseParser()
        p.input(b'abc def{1 2} 20120124 123.45 19\n')
        params = p.read_record('T T* L D N I')
        assert params[0] == b'abc'
        assert params[1] == b'def'
        assert isinstance(params[2], list)
        assert len(params[2]) == 2
        assert params[3] == '2012-01-24'
        assert isinstance(params[4], Decimal)
        assert params[4] == Decimal('123.45')
        assert isinstance(params[5], int)
        assert params[5] == 19

        p = BaseParser()
        p.input(b'abc 20120124 123.45\n')
        params = p.read_record('[T] [D] [N]')
        assert params[0] == b'abc'
        assert params[1] == '2012-01-24'
        assert isinstance(params[2], Decimal)
        assert params[2] == Decimal('123.45')

import py
from decimal import Decimal
from datetime import date
from pytransact.testsupport import BLMTests

class TestParser(BLMTests):

    def setup_method(self, method):
        super(TestParser, self).setup_method(method)
        self.acc = blm.accounting.Accounting()

    def mkAccount(self, number='1024', name='Kassa'):
        return blm.accounting.Account(number=[number], name=[name],
                                      accounting=[self.acc])

    def test_sie_type(self):
        p = Parser(self.acc)
        py.test.raises(UnsupportedSIEVersion, p.sie_type, '1')
        py.test.raises(UnsupportedSIEVersion, p.sie_type, '2')
        py.test.raises(UnsupportedSIEVersion, p.sie_type, '3')
        p.sie_type('4')  # we support version 4

    def test_address(self):
        p = Parser(self.acc)
        p.address('Sven Svensson', 'Box 21', u'211 20 MALMÖ', '040-123 45')
        assert self.acc.contact == ['Sven Svensson']
        assert self.acc.mail_address == ['Box 21']
        assert self.acc.zip_city == [u'211 20 MALMÖ']
        assert self.acc.telephone == ['040-123 45']

    def test_accounting_period(self):
        p = Parser(self.acc)
        p.accounting_period(0, '2012-01-01', '2012-12-31')
        p.accounting_period(-2, '2010-01-01', '2010-12-31')
        year = self.acc.years['0']
        assert year == ['2012-01-01', '2012-12-31']
        assert self.acc.start == ['2012-01-01']
        assert self.acc.end == ['2012-12-31']

        year = self.acc.years['-2']
        assert year == ['2010-01-01', '2010-12-31']

    def test_accounting_object(self):
        p = Parser(self.acc)
        p.accounting_object('1', '0123', 'Serviceavdelningen')
        obj, = blm.accounting.AccountingObject._query().run()
        assert obj.dimension[0].number == ['1']
        assert obj.dimension[0].accounting[0] == self.acc

    def test_account(self):
        p = Parser(self.acc)
        p.parse(b'#KONTO 1024 "Kassa"\n')
        account, = blm.accounting.Account._query().run()
        assert account.accounting == [self.acc]
        assert account.number == ['1024']
        assert account.name == ['Kassa']

        py.test.raises(ValueError, p.parse, b'#KONTO 1024 "Kassa"\n')

    def test_account2(self):
        p = Parser(self.acc)
        p.account('1024', 'Kassa')
        account, = blm.accounting.Account._query().run()
        assert account.accounting == [self.acc]
        assert account.number == ['1024']
        assert account.name == ['Kassa']

    def test_account_type(self):
        account = self.mkAccount()
        p = Parser(self.acc)
        p.account_type('1024', 'T')
        assert account.type == ['T']

    def test_ver(self):
        dimension = blm.accounting.Dimension._query(number=['1']).run()[0]
        accounting_object = blm.accounting.AccountingObject(
            number=['2'], name=['bar'], dimension=[dimension])
        self.acc.dimensions = [dimension]
        account1910 = self.mkAccount('1910')
        account2640 = self.mkAccount('2640')
        account6250 = self.mkAccount('6250')
        p = Parser(self.acc)
        p.verification('A', 1, '2012-01-24', '', '2012-01-25', 'Gurra')
        p.transaction('1910', [], Decimal('-1000'))
        p.transaction('2640', [], Decimal('200'), '', 'Text1')
        p.transaction('6250', ['1', '2'], Decimal('800'), '', 'Text2')

        v, = blm.accounting.Verification._query().run()
        assert v.accounting == [self.acc]
        assert v.version == [0]
        assert v.series[0].name == ['A']
        assert v.number == [1]
        assert v.transaction_date == ['2012-01-24']
        assert v.registration_date == ['2012-01-25']

        assert len(v.transactions) == 3
        t = v.transactions[0]
        assert t.version == [0]
        assert t.transtype == ['normal']
        assert t.account == [account1910]
        assert t.amount == [Decimal('-1000.00')]
        assert t.text == [u'']
        t = v.transactions[1]
        assert t.version == [0]
        assert t.transtype == ['normal']
        assert t.account == [account2640]
        assert t.amount == [Decimal('200.00')]
        assert t.text == ['Text1']
        t = v.transactions[2]
        assert t.version == [0]
        assert t.transtype == ['normal']
        assert t.account == [account6250]
        assert t.amount == [Decimal('800.00')]
        assert t.text == ['Text2']
        assert t.accounting_objects == [accounting_object]

    def test_sru(self):
        account = self.mkAccount('1910')
        p = Parser(self.acc)
        p.sru('1910', '123')
        assert account.sru == ['123']

    def test_unit(self):
        account = self.mkAccount('1910')
        p = Parser(self.acc)
        p.unit('1910', 'st')
        assert account.unit == ['st']

    def test_layout(self):
        p = Parser(self.acc)
        p.account_layout('Bas1998')
        assert self.acc.layout == ['Bas1998']

    def test_industry_code(self):
        p = Parser(self.acc)
        p.industry_code('82300')
        assert self.acc.industry_code == ['82300']

    def test_dim_subdim(self):
        p = Parser(self.acc)
        p.dim('2', 'Godis')
        dim, = blm.accounting.Dimension._query(number='2').run()
        assert dim.name == ['Godis']
        assert dim.subdim_of == []

        p.sub_dim('6', 'Polkagrisar', '2')
        subdim, = blm.accounting.Dimension._query(number='6').run()
        assert subdim.name == ['Polkagrisar']
        assert subdim.subdim_of == [dim]


        p.dim('21', 'Lokaler')
        p.sub_dim('22', 'Rum', '21')

        dim, = blm.accounting.Dimension._query(number='21').run()
        subdim, = blm.accounting.Dimension._query(number='22').run()

        assert dim.accounting == subdim.accounting == [self.acc]
        assert subdim.subdim_of == [dim]

        assert dim.name == ['Lokaler']
        assert subdim.name == ['Rum']

        p.accounting_object('21', '1', 'Byggnad 1')
        p.accounting_object('22', '11', 'Rum 1')

        ao1, = blm.accounting.AccountingObject._query(number='1').run()
        assert ao1.dimension == [dim]
        assert ao1.name == ['Byggnad 1']

        ao11, = blm.accounting.AccountingObject._query(number='11').run()
        assert ao11.dimension == [subdim]
        assert ao11.name == ['Rum 1']

    def test_opening_balance(self):
        account = self.mkAccount('1910')
        p = Parser(self.acc)
        p.opening_balance(0, '1910', Decimal('123.45'))
        balance = account.account_balances['0']
        assert balance is account
        assert balance.year == [0]
        assert balance.opening_balance == [Decimal('123.45')]
        assert account.opening_balance == [Decimal('123.45')]

        p.opening_balance(-1, '1910', Decimal('1234.45'), Decimal('2.2'))
        balance = account.account_balances['-1']
        assert balance is not account
        assert balance.year == [-1]
        assert balance.opening_balance == [Decimal('1234.45')]
        assert account.opening_balance == [Decimal('123.45')]
        assert balance.opening_quantity == [Decimal('2.2')]

        acctobj = p.accounting_object('1','2','two')
        p.object_opening_balance(-1, '1910', ['1', '2'], Decimal('2123.45'), Decimal('-2.2'))
        assert account.account_balances['-1'] is balance

        obj_balance = balance.object_balance_budgets[0]
        assert obj_balance.accounting_object == [acctobj]
        assert obj_balance.period == ['']
        assert obj_balance.opening_balance == [Decimal('2123.45')]
        assert account.opening_balance == [Decimal('123.45')]
        assert obj_balance.opening_quantity == [Decimal('-2.2')]

        p.object_opening_balance(-2, '1910', ['1', '2'], Decimal('1000'))
        balance = account.account_balances['-2']
        assert balance.object_balance_budgets[0].opening_balance == [Decimal('1000')]

    def test_closing_balance(self):
        account = self.mkAccount('1910')
        p = Parser(self.acc)
        p.closing_balance(-1, '1910', Decimal('123.45'), Decimal('2.2'))
        balance = account.account_balances['-1']
        assert balance.year == [-1]
        assert balance.balance == [Decimal('123.45')]
        assert balance.balance_quantity == [Decimal('2.2')]

        acctobj = p.accounting_object('1','2','two')
        p.object_closing_balance(-1, '1910', ['1', '2'], Decimal('123.45'), Decimal('-2.2'))
        assert account.account_balances['-1'] is balance

        obj_balance = balance.object_balance_budgets[0]
        assert obj_balance.accounting_object == [acctobj]
        assert obj_balance.period == ['']
        assert obj_balance.balance == [Decimal('123.45')]
        assert obj_balance.balance_quantity == [Decimal('-2.2')]

    def test_turnover(self):
        account = self.mkAccount('1910')
        p = Parser(self.acc)
        p.turnover(0, '1910', Decimal('123.45'))
        balance = account.account_balances['0']
        assert balance.year == [0]
        assert balance.balance == [Decimal('123.45')]

        p.turnover(-1, '1910', Decimal('123.45'), Decimal('2.2'))
        balance = account.account_balances['-1']
        assert balance.year == [-1]
        assert balance.balance == [Decimal('123.45')]
        assert balance.balance_quantity == [Decimal('2.2')]

    def test_period_balance(self):
        account = self.mkAccount('1910')
        p = Parser(self.acc)
        p.period_balance(-1, '201303', '1910', [], Decimal('123.45'), Decimal('-2.2'))

        balance = account.account_balances['-1']
        assert balance.year == [-1]

        balancebudget = balance.balance_budgets[0]
        assert balancebudget.period == ['201303']
        assert balancebudget.balance == [Decimal('123.45')]
        assert balancebudget.balance_quantity == [Decimal('-2.2')]

        p.accounting_object('1','2','two')
        p.period_balance(-1, '201303', '1910', ['1', '2'], Decimal('123.45'),
                          Decimal('-2.2'))
        assert balance is account.account_balances['-1']
        objectbalancebudget = balance.object_balance_budgets[0]
        assert objectbalancebudget.period == ['201303']
        assert objectbalancebudget.balance == [Decimal('123.45')]
        assert objectbalancebudget.balance_quantity == [Decimal('-2.2')]

    def test_period_budget(self):
        account = self.mkAccount('1910')
        p = Parser(self.acc)
        p.period_budget(-1, '201303', '1910', [], Decimal('123.45'), Decimal('-2.2'))

        balance = account.account_balances['-1']
        assert balance.year == [-1]

        balancebudget = balance.balance_budgets[0]
        assert balancebudget.period == ['201303']
        assert balancebudget.budget == [Decimal('123.45')]
        assert balancebudget.budget_quantity == [Decimal('-2.2')]

        p.accounting_object('1','2','two')
        p.period_budget(-1, '201303', '1910', ['1', '2'], Decimal('123.45'),
                         Decimal('-2.2'))
        assert balance is account.account_balances['-1']
        objectbalancebudget = balance.object_balance_budgets[0]
        assert objectbalancebudget.period == ['201303']
        assert objectbalancebudget.budget == [Decimal('123.45')]
        assert objectbalancebudget.budget_quantity == [Decimal('-2.2')]

    def test_undefined_account(self):
        p = Parser(self.acc)
        acct = p.get_account('4711')
        assert acct.number == ['4711']
        assert len(p.parse_warnings) == 1
        assert '4711' in p.parse_warnings[0]

    def test_get_accounting_object(self):
        p = Parser(self.acc)
        p.accounting_object('1', '0123', 'Serviceavdelningen')

        obj = p.get_accounting_object('1', '0123')

        assert obj.name == ['Serviceavdelningen']

    def test_get_undefined_acct_object(self):
        p = Parser(self.acc)
        obj = p.get_accounting_object('9999','4711')
        assert obj.number == ['4711']
        assert obj.dimension[0].number == ['9999']
        assert len(p.parse_warnings) == 2
        assert '9999' in p.parse_warnings[0]
        assert '4711' in p.parse_warnings[1]

    def test_subdim_of_undefined(self):
        p = Parser(self.acc)
        dim = p.sub_dim('22', 'Rum', '21')
        assert len(p.parse_warnings) == 1
        assert '21' in p.parse_warnings[0]
        assert dim.subdim_of[0].number == ['21']

    def test_object_of_undefined(self):
        p = Parser(self.acc)
        obj = p.accounting_object('9999', '0123', 'Serviceavdelningen')
        assert len(p.parse_warnings) == 1
        assert '9999' in p.parse_warnings[0]
        assert obj.dimension[0].number == ['9999']


    # Open End Extensions

    def test_closed(self):
        p = Parser(self.acc)
        assert self.acc.closed == [False]  # sanity

        p.closed()
        assert self.acc.closed == [True]

    def test_series(self):
        p = Parser(self.acc)
        p.series('A')
        p.series('B', 'And a descr')

        series = blm.accounting.VerificationSeries._query().run()
        a, b = sorted(series, key=lambda toi: toi.name[0])

        assert a.name == ['A']
        assert a.description == []

        assert b.name == ['B']
        assert b.description == ['And a descr']

        # find existing series
        c = blm.accounting.VerificationSeries(accounting=self.acc, name='C')

        series = p.series('C', 'C descr')
        assert series is c
        assert series.description == ['C descr']

    def test_vatcode(self):
        p = Parser(self.acc)

        blm.accounting.bootstrap()  # Set up vat codes

        p.account('2610', 'Mums!')
        p.vatcode('2610', '05')

        a, = blm.accounting.Account._query().run()

        assert a.vatCode[0] == '05'


class TestSIEImporter(BLMTests):

    def test_markes_as_imported(self):
        org = blm.accounting.Org()
        importer = SIEImporter(org=[org])
        importer.parse(StringIO(b'#FLAGGA 0\n\n'))
        assert importer.accounting.imported[0]


class TestAppendingParser(BLMTests):

    def setup_method(self, method):
        super(TestAppendingParser, self).setup_method(method)
        self.acc = blm.accounting.Accounting()
        self.account1000 = self.mkAccount('1000')
        self.account2000 = self.mkAccount('2000')

        self.series = blm.accounting.VerificationSeries(name='A',accounting=self.acc)
        self.ver1 = blm.accounting.Verification(series=self.series,number=1,accounting=self.acc)


    def mkAccount(self, number='1024', name='Kassa'):
        return blm.accounting.Account(number=[number], name=[name],
                                      accounting=[self.acc])

    def test_simple(self):
        p = AppendingParser(self.acc)

        f = b'''#FLAGGA	0
            #PROGRAM	"Test pre Eutaxia Admin"
            #FORMAT	PC8
            #GEN	20181120	
            #SIETYP	4
            #PROSA	
            #FTYP	
            #FNR	
            #ORGNR	
            #ADRESS	skipped
            #BKOD	skipped
            #FNAMN	"Test pre Eutaxia AB"
            #RAR	0
            #KONTO	9999	skipped
            #VER	B	2	20080301	bla bla blah	20080302	AR
            {
                #TRANS	1000	{}	100.00	""	""	3	AR
                #TRANS	2000	{}	-100.00	""	""	3	AR
            }
            
            '''
        for line in f.splitlines(keepends=True)[1:]:
            line = line.lstrip()
            # if line.startswith(b'#TRANS'):
            #     import pdb;pdb.set_trace()

            print(line)
            try:
                p.parse(line)
            except DoneException:
                pass

        v1,v2 = blm.accounting.Verification._query().run()
        assert v2.number == [2]
        assert v1 is self.ver1
        assert len(v2.transactions) == 2
        print(blm.accounting.Account._query().run())
        assert not blm.accounting.Account._query(number='9999').run()






