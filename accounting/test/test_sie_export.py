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

import os
from pytransact.testsupport import BLMTests
from accounting.sie_export import sie_export, remove_dashes_from_date, \
print_program_name, print_format, print_sietype, print_orgtype, print_org_id, \
print_orgnum, print_industry_code, print_address, print_orgname, \
print_taxation_year, \
print_layout, print_currency, print_account, print_sru, print_unit, \
print_account_type, print_dim, print_subdim, print_accounting_object, \
print_opening_balance, print_closing_balance, print_turnover, \
print_verification, print_transaction

import blm
from decimal import Decimal

import pytest


class TestSIEExport(BLMTests):

    def setup_method(self, method):
        super(TestSIEExport, self).setup_method(method)
        self.acc = blm.accounting.Accounting()

    def mkAccount(self, number='1024', name='Kassa', account_type='T'):
        return blm.accounting.Account(number=[number], name=[name],
                                      sru=['555'], type=[account_type],
                                      unit=['st'], accounting=[self.acc])

    def mkDim(self, number='1', name=u'Kostnadsställe', subdim_of=None):
        if subdim_of:
            return blm.accounting.Dimension(number=[number], name=[name],
                                            accounting=[self.acc],
                                            subdim_of=[subdim_of])
        else:
            return blm.accounting.Dimension(number=[number], name=[name],
                                            accounting=[self.acc])

    def mkAccountingObject(self, dim, number='5', name='Byggnad'):

        return blm.accounting.AccountingObject(number=[number], name=[name],
                                               dimension=[dim])

    def mkAccountBalance(self, account, year=-1, opening_balance=Decimal('321.00'),
                         balance=Decimal('456.01'),
                         balance_quantity=Decimal('2.2')):
        return blm.accounting.AccountBalance(
            account=[account],
            year=[year],
            opening_balance=[opening_balance],
            balance=[balance],
            balance_quantity=[balance_quantity])

    def mkSeries(self, name='A'):
        for series in blm.accounting.VerificationSeries._query(name=name).run():
            return series
        return blm.accounting.VerificationSeries(name=[name],
                                                 accounting=[self.acc])

    def mkVerification(self, transactions, series=u'A', number=1,
                       transaction_date=u'2013-04-26',
                       text=u'Räksmörgåsen "Räkan"',
                       registration_date=u'2013-04-28', signature=u'Gurra'):
        return blm.accounting.Verification(
            accounting=[self.acc],
            transactions=transactions,
            series=[self.mkSeries(series)],
            number=[number],
            transaction_date=[transaction_date],
            text=[text],
            registration_date=[registration_date],
            signature=[signature])

    def mkTrans(self, account, ver, transtype='normal', amount=Decimal(10),
                quantity=Decimal(15), text=u'Räksmörgåsen "Räkan"',
                signature=u'Gurra', transaction_date=u'2012-11-14',
                accounting_objects=None):
        assert accounting_objects is None
        """We don't implement these yet, when we do some tests will need
           to be changed"""
        return blm.accounting.Transaction(
            account=[account],
            verification = ver,
            version=ver.version,
            transtype=[transtype],
            amount=[amount],
            quantity=[quantity],
            text=[text],
            signature=[signature],
            transaction_date=[transaction_date]
            )

    def test_remove_dashes_from_date(self):
        date = "2012-12-04"
        assert remove_dashes_from_date(date) == "20121204"

    def test_print_program_name(self):
        assert print_program_name() == u'#PROGRAM "Eutaxia Admin" "Version X.Y"\n'
    def test_print_format(self):
        assert print_format() == u'#FORMAT "PC8"\n'

    def test_sietype(self):
        assert print_sietype() == u'#SIETYP 4\n'

    def test_orgtype(self):
        self.acc = blm.accounting.Accounting(orgtype='I')
        assert print_orgtype(self.acc) == u'#FTYP "I"\n'

    def test_org_id(self):
        org = blm.accounting.Org()
        accounting = blm.accounting.Accounting(org=[org])
        assert print_org_id(accounting) == '#FNR "' + str(org.id[0]) + '"\n'

    def test_orgnum(self):
        self.acc= blm.accounting.Accounting(orgnum='857203-3689')
        # could be orgnum, acquisitionnum, activitynum
        # but we don't implement the last 2 as of now in the class Accounting

        assert print_orgnum(self.acc) == u'#ORGNR "857203-3689"\n'

    def test_industry_code(self):
        self.acc = blm.accounting.Accounting(industry_code='12345')
        assert print_industry_code(self.acc) == u'#BKOD "12345"\n'

    def test_address(self):
        self.acc = blm.accounting.Accounting(
            contact='Anders Kontaktperson', mail_address='Storgatan 666',
            zip_city='00000 Ort', telephone='+46 123456')

        assert print_address(self.acc) ==  u'#ADRESS "Anders Kontaktperson" "Storgatan 666" "00000 Ort" "+46 123456"\n'

        self.acc = blm.accounting.Accounting(contact='Anders Kontaktperson',
                                             mail_address='', zip_city='',
                                             telephone='+46 123456')

        assert print_address(self.acc) ==  u'#ADRESS "Anders Kontaktperson" "" "" "+46 123456"\n'

    def test_orgname(self):
        self.acc = blm.accounting.Accounting(orgname='My Society')
        assert print_orgname(self.acc) == u'#FNAMN "My Society"\n'

    def test_taxation_year(self):
        self.acc = blm.accounting.Accounting(taxation_year='2011')
        assert print_taxation_year(self.acc) == u'#TAXAR "2011"\n'

    def test_layout(self):
        # good field
        self.acc = blm.accounting.Accounting(layout='BAS96')
        assert print_layout(self.acc) == u'#KPTYP "BAS96"\n'

        # no field
        self.acc = blm.accounting.Accounting()
        assert print_layout(self.acc) == u'#KPTYP "BAS95"\n'

        # field in the BAS2xxx format
        self.acc = blm.accounting.Accounting(layout='BAS2007')
        assert print_layout(self.acc) == u'#KPTYP "EUBAS97"\n'

        # bad field.  What should really happen here?
        self.acc = blm.accounting.Accounting(layout='XXXX')
        assert print_layout(self.acc) == u'#KPTYP "XXXX not in BAS95, BAS96, EUBAS97, NE2007 or BAS2xxx"\n'

    def test_currency(self):
        self.acc = blm.accounting.Accounting(currency='NOK')
        assert print_currency(self.acc) == u'#VALUTA "NOK"\n'
        self.acc = blm.accounting.Accounting()
        assert print_currency(self.acc) == u'#VALUTA "SEK"\n'

    def test_account(self):
        account = self.mkAccount()
        assert print_account(account) == u'#KONTO 1024 "Kassa"\n'

    def test_account_type(self):
        account = self.mkAccount()
        assert print_account_type(account) == u'#KTYP 1024 T\n'

    def test_unit(self):
        account = self.mkAccount()
        assert print_unit(account) == u'#ENHET 1024 "st"\n'

    def test_sru(self):
        account = self.mkAccount()
        assert print_sru(account) == u'#SRU 1024 555\n'

    def test_dim(self):
        dim = self.mkDim()
        assert print_dim(dim) == u'#DIM 1 "Kostnadsställe"\n'

    def test_underdim(self):
        dim = self.mkDim()
        subdim = self.mkDim(number='2', name=u'Kostnadsbärare',
                            subdim_of=dim)
        assert print_subdim(subdim) == u'#UNDERDIM 2 "Kostnadsbärare" 1\n'

    def test_accounting_object(self):
        dim = self.mkDim()
        obj = self.mkAccountingObject(dim)
        assert print_accounting_object(obj) == u'#OBJEKT 1 5 "Byggnad"\n'

    def test_opening_balance(self):
        account = self.mkAccount()
        bal = self.mkAccountBalance(account)
        assert (print_opening_balance(account.number[0], bal) ==
                u'#IB -1 1024 321.00\n')

    def test_closing_balance(self):
        account = self.mkAccount()
        bal = self.mkAccountBalance(account)
        assert (print_closing_balance(account.number[0], bal) ==
                u'#UB -1 1024 456.01 2.20000000000000000000\n')

    def test_turnover(self):
        account = self.mkAccount(number='3010',
            name='Medlemsavgifter', account_type='I')
        bal = self.mkAccountBalance(account)
        assert (print_turnover(account.number[0], bal) ==
                u'#RES -1 3010 456.01 2.20000000000000000000\n')
        # 20 decimal places is crazy, but do we know that 1 is enough?

    def test_verification(self):
        ver = self.mkVerification([])
        assert (print_verification(ver) ==
                u'#VER A 1 20130426 "Räksmörgåsen \\"Räkan\\"" "20130428" "Gurra"\n')

    def test_transaction(self):
        account = self.mkAccount()
        ver = self.mkVerification([])
        trans = self.mkTrans(account, ver, "normal")
        assert (print_transaction(trans) ==
                u'#TRANS 1024 {} 10.00 20121114 "Räksmörgåsen \\"Räkan\\"" 15.00000000000000000000 "Gurra"\n')
        #20 decimal places is crazy, but we don't know what the best # is yet.

    def test_added_transaction(self):
        account = self.mkAccount()
        ver = self.mkVerification([])
        trans = self.mkTrans(account, ver, "added")
        assert (print_transaction(trans) ==
                u'#RTRANS 1024 {} 10.00 20121114 "Räksmörgåsen \\"Räkan\\"" 15.00000000000000000000 "Gurra"\n'
                u'#TRANS 1024 {} 10.00 20121114 "Räksmörgåsen \\"Räkan\\"" 15.00000000000000000000 "Gurra"\n')
        #20 decimal places is crazy, but we don't know what the best # is yet.

    def test_deleted_transaction(self):
        account = self.mkAccount()
        ver = self.mkVerification([])
        trans = self.mkTrans(account, ver, "deleted")
        assert (print_transaction(trans) ==
                u'#BTRANS 1024 {} 10.00 20121114 "Räksmörgåsen \\"Räkan\\"" 15.00000000000000000000 "Gurra"\n')
        #20 decimal places is crazy, but we don't know what the best # is yet.


from accounting.sie_import import SIEImporter
try:
    import StringIO             #py2
except ImportError:
    from io import StringIO     #py3
import codecs
class TestImported(BLMTests):
    """Do tests on an imported file"""

    def setup_method(self, method):
        super(TestImported, self).setup_method(method)
        here = os.path.dirname(__file__)
        imp = SIEImporter()
        imp.parseFile(os.path.join(here, 'sie', 'typ4.se'))
        self.acc = imp.accounting
        self.acc.org = [blm.accounting.Org()]

    def test_export(self, tmpdir):
        with codecs.open(str(tmpdir.join('export_output')), 'w', 'cp437') as fp:
            sie_export(fp, self.acc)
