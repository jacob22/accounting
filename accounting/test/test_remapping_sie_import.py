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

import glob, os, py, time
from pytransact import queryops as q
from accounting.remapping_sie_import import RemappingParser as Parser
from accounting.remapping_sie_import import build_mapping
from accounting.sie_import import SIEImporter
import blm

import py
from decimal import Decimal
from datetime import date
from pytransact.testsupport import BLMTests

import pytest

class TestParser(BLMTests):

    def setup_method(self, method):
        super(TestParser, self).setup_method(method)
        self.acc = blm.accounting.Accounting()
        self.mapping = {'1024': '9999',
                        '1910': '1911',
                        '2640': '2641',
                        '6250': '6251',}

    def mkAccount(self, number='9999', name='Kassa'):
        return blm.accounting.Account(number=[number], name=[name],
                                      accounting=[self.acc])

    def test_address(self):
        p = Parser(self.acc, self.mapping)
        p.address('Sven Svensson', 'Box 21', u'211 20 MALMÖ', '040-123 45')
        assert self.acc.contact == ['Sven Svensson']
        assert self.acc.mail_address == ['Box 21']
        assert self.acc.zip_city == [u'211 20 MALMÖ']
        assert self.acc.telephone == ['040-123 45']

    def test_accounting_period(self):
        p = Parser(self.acc, self.mapping)
        p.accounting_period(0, '2012-01-01', '2012-12-31')
        p.accounting_period(-2, '2010-01-01', '2010-12-31')
        year = self.acc.years['0']
        assert year == ['2012-01-01', '2012-12-31']
        assert self.acc.start == ['2012-01-01']
        assert self.acc.end == ['2012-12-31']

        year = self.acc.years['-2']
        assert year == ['2010-01-01', '2010-12-31']

    def test_accounting_object(self):
        p = Parser(self.acc, self.mapping)
        p.accounting_object('1', '0123', 'Serviceavdelningen')
        obj, = blm.accounting.AccountingObject._query().run()
        assert obj.dimension[0].number == ['1']
        assert obj.dimension[0].accounting[0] == self.acc

    def test_account(self):
        p = Parser(self.acc, self.mapping)
        p.parse(b'#KONTO 1024 "Kassa"\n')
        account, = blm.accounting.Account._query().run()
        assert account.accounting == [self.acc]
        assert account.number == ['9999']
        assert account.name == ['Kassa']

        py.test.raises(ValueError, p.parse, b'#KONTO 1024 "Kassa"\n')

    def test_account2(self):
        p = Parser(self.acc, self.mapping)
        p.account('1024', 'Kassa')
        account, = blm.accounting.Account._query().run()
        assert account.accounting == [self.acc]
        assert account.number == ['9999']
        assert account.name == ['Kassa']

    def test_account_type(self):
        account = self.mkAccount()
        p = Parser(self.acc, self.mapping)
        p.account_type('1024', 'T')
        assert account.type == ['T']

    def test_ver(self):
        dimension = blm.accounting.Dimension._query(number=['1']).run()[0]
        accounting_object = blm.accounting.AccountingObject(
            number=['2'], name=['bar'], dimension=[dimension])
        self.acc.dimensions = [dimension]
        account1910 = self.mkAccount('1911')
        account2640 = self.mkAccount('2641')
        account6250 = self.mkAccount('6251')
        p = Parser(self.acc, self.mapping)
        p.verification('A', 1, '2012-01-24', '', '2012-01-25', 'Gurra')
        p.transaction('1910', [], Decimal('-1000'))
        p.transaction('2640', [], Decimal('200'), '', 'Text1')
        p.transaction('6250', ['1', '2'], Decimal('800'), '', 'Text2')

        v, = blm.accounting.Verification._query().run()
        assert v.accounting == [self.acc]
        assert v.series[0].name == ['A']
        assert v.number == [1]
        assert v.transaction_date == ['2012-01-24']
        assert v.registration_date == ['2012-01-25']

        assert len(v.transactions) == 3
        t = v.transactions[0]
        assert t.transtype == ['normal']
        assert t.account == [account1910]
        assert t.amount == [Decimal('-1000.00')]
        assert t.text == [u'']
        t = v.transactions[1]
        assert t.transtype == ['normal']
        assert t.account == [account2640]
        assert t.amount == [Decimal('200.00')]
        assert t.text == ['Text1']
        t = v.transactions[2]
        assert t.transtype == ['normal']
        assert t.account == [account6250]
        assert t.amount == [Decimal('800.00')]
        assert t.text == ['Text2']
        assert t.accounting_objects == [accounting_object]

    def test_sru(self):
        account = self.mkAccount('1911')
        p = Parser(self.acc, self.mapping)
        p.sru('1910', '123')
        assert account.sru == ['123']

    def test_unit(self):
        account = self.mkAccount('1911')
        p = Parser(self.acc, self.mapping)
        p.unit('1910', 'st')
        assert account.unit == ['st']

    def test_layout(self):
        p = Parser(self.acc, self.mapping)
        p.account_layout('Bas1998')
        assert self.acc.layout == ['Bas1998']

    def test_industry_code(self):
        p = Parser(self.acc, self.mapping)
        p.industry_code('82300')
        assert self.acc.industry_code == ['82300']

    def test_dim_subdim(self):
        p = Parser(self.acc, self.mapping)
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
        account = self.mkAccount('1911')
        p = Parser(self.acc, self.mapping)
        p.opening_balance(0, '1910', Decimal('123.45'))
        balance = account.account_balances['0']
        assert balance.year == [0]
        assert balance.opening_balance == [Decimal('123.45')]
        assert account.opening_balance == [Decimal('123.45')]

        p.opening_balance(-1, '1910', Decimal('1234.45'), Decimal('2.2'))
        balance = account.account_balances['-1']
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

    def test_closing_balance(self):
        account = self.mkAccount('1911')
        p = Parser(self.acc, self.mapping)
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
        account = self.mkAccount('1911')
        p = Parser(self.acc, self.mapping)
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
        account = self.mkAccount('1911')
        p = Parser(self.acc, self.mapping)
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
        account = self.mkAccount('1911')
        p = Parser(self.acc, self.mapping)
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


class TestMapping(object):
    def test_mapping(self):
        here = os.path.dirname(__file__)
        with open(here + '/../../misc/npk_remapping') as fp:
            mapping = build_mapping(fp)
        assert mapping['1011'] == '1911'
        assert mapping['8999'] == '8999'

class TestMappedImport(BLMTests):
    #pytest.skip()

    def setup_method(self, method):
        super(TestMappedImport, self).setup_method(method)
        self.org = blm.accounting.Org()

    def test_import_sie(self):
        here = os.path.dirname(__file__)
        filename = here + '/../../misc/npk2012.se'
        print(time.ctime(time.time()), repr(filename))
        with open(here + '/../../misc/npk_remapping') as fp:
            mapping = build_mapping(fp)
        importer = SIEImporter(org=[self.org], mapping=mapping)
        importer.parseFile(filename.encode('utf-8'))
        self.commit()

        # All objects should have been assigned an allowRead
        assert not blm.TO._query(allowRead=q.Empty()).run()
        assert not blm.TO._query(allowRead=q.NotIn(self.org.ug)).run()
        assert blm.TO._query(allowRead=self.org.ug).run()

        assert blm.accounting.Accounting._query().run() == [importer.accounting]
