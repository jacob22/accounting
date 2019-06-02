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

from decimal import Decimal
import collections
import copy
import functools
import lxml, lxml.html
import py
import accounting.reports
import members
import blm.members
from accounting.reports import make_sums, year_report_income_sums
import sys
if sys.version_info < (3,0,0):
    PYT3 = False
else:
    PYT3 = True

class MockTransaction(object):
    def __init__(self, amount, transaction_date='2010-01-01'):
        self.amount = [Decimal(amount)]
        self.transaction_date = [transaction_date]

class MockReportItem(object):
    name = ['an account']
    def __init__(self, number, opening_balance, transactions):
        self.number = [number]
        self.opening_balance = [Decimal(opening_balance)]
        self.transactions = transactions

class TestMakeSums(object):

    def test_single(self):

        report_result = [MockReportItem('1000', Decimal('0.00'),
                                        [MockTransaction(Decimal('1.00'))])]
        itemlist, sum_tuple = make_sums(report_result, '1000', '2000')
        assert sum_tuple == (Decimal('0.00'), Decimal('1.00'))
        assert itemlist[0].total == [Decimal('1.00')]

    def test_no_transactions(self):

        report_result = [MockReportItem('1000', Decimal('0.00'),
                                       [])]
        itemlist, section_totals = make_sums(report_result, '1000', '2000')
        assert section_totals == (Decimal('0.00'), Decimal('0.00'))
        assert len(itemlist) == 1
        assert itemlist[0].total == [Decimal('0.00')]

    def test_no_accounts(self):

        report_result = [MockReportItem('1000', Decimal('0.00'),
                                        [])]
        itemlist, section_totals = make_sums(report_result, '1001', '2000')
        assert section_totals == (Decimal('0.00'), Decimal('0.00'))
        assert len(itemlist) == 0

    def test_time_limited(self):

        accounts = [
            MockReportItem('1000', '1.00', [
                    MockTransaction('2.00', '2010-01-01'),
                    MockTransaction('4.00', '2010-02-01'),
                    MockTransaction('8.00', '2010-03-01'),
                    MockTransaction('16.00', '2010-04-01')
            ])
            ]
        # not time limited, for sanity
        itemlist, sum_tuple = make_sums(accounts, '1000', '9999')
        assert len(itemlist) == 1
        assert itemlist[0].opening_balance == [Decimal('1.00')]
        assert sum_tuple == (Decimal('1.00'), Decimal('30.00'))

        # only include items between 2010-02-01 and 2010-03-01 inclusive
        itemlist, sum_tuple = make_sums(accounts, '1000', '9999', '2010-02-01', '2010-03-01')
        #assert itemlist == accounts
        assert sum_tuple == (Decimal('3.00'), Decimal('12.00'))


class TestYearReport(object):

    def test_year_report_income_sums(self):
        args = [[Decimal('1')], [Decimal('2'), Decimal('4')], []]
        assert year_report_income_sums(args) == [Decimal('3'), Decimal('4')]


def test_parse_number_range():

    from accounting.reports import parse_range
    r = parse_range('1-3')
    assert r == ['1', '2', '3']

    r = parse_range('1,2')
    assert r == ['1', '2']

    r = parse_range('1 2')
    assert r == ['1', '2']

    r = parse_range('1, 2')
    assert r == ['1', '2']

    r = parse_range('1-3, 5, 7-9')
    assert r == ['1', '2', '3',
                 '5',
                 '7', '8', '9']

    r = parse_range('1, 3-5   7 random gorp 9')
    assert r == ['1', '3', '4', '5', '7', '9']

    r = parse_range('1 10 100 1000 10000', npat='\d{4}')
    assert r == ['1000']

    r = parse_range("Robert'); DROP TABLE Students; --")
    assert r == []


import flask, os
try:
    import httplib                      #py2
except ImportError:
    from http import client as httplib  #py3
from pytransact.testsupport import BLMTests
from accounting import sie_import
import blm.accounting
from .. import reports

# would be nice if it was possible to test reports without pulling all
# of wsgi...
from bin import wsgi

transdata = collections.namedtuple('transdata', 'account text amount')

class ReportTests(BLMTests):

    name = None

    def setup_method(self, method):
        super(ReportTests, self).setup_method(method)
        self.here = os.path.dirname(__file__)
        self.top = os.path.abspath(os.path.join(self.here, '..', '..'))

        self.org = blm.accounting.Org()
        self.user = blm.accounting.User(ugs=self.org.ug)
        self.accounting = blm.accounting.Accounting(org=self.org)

        self.orig_format_amount = accounting.reports.format_amount
        accounting.reports.format_amount = functools.partial(
            accounting.reports.format_amount, create_spans=False)

        wsgi.app.before_request(self._fake_user)

    def _fake_user(self):
        flask.g.user, = blm.accounting.User._query(id=self.user.id).run()

    def teardown_method(self, method):
        super(ReportTests, self).teardown_method(method)
        f = wsgi.app.before_request_funcs[None].pop()
        assert f == self._fake_user

        accounting.reports.format_amount = self.orig_format_amount

    def run_report(self, toi=None, data={}, html=False):
        if toi is None:
            toi = self.accounting

        with wsgi.app.test_client() as c:
            response = c.post('/%s/%s' % (self.name, toi.id[0]),
                              data=data)
        assert response.status_code == 200
        #print response.data     #prints htmldata to screen
        if not html:
            return lxml.etree.fromstring(response.data)
        else:
            return lxml.html.fromstring(response.data)

    def mkAccount(self, n=None, **kw):
        kw.setdefault('accounting', self.accounting)
        if n is not None:
            kw.setdefault('number', str(n))
            kw.setdefault('name', 'Account %s' % n)
        return blm.accounting.Account(**kw)

    def mkVer(self, number=1, series='A', transaction_date='2010-01-01',
              transactions=[]):
        try:
            series, = blm.accounting.VerificationSeries._query(
                accounting=self.accounting, name=series).run()
        except ValueError:
            series = blm.accounting.VerificationSeries(
                accounting=self.accounting, name=series)

        verification = blm.accounting.Verification(
            accounting=self.accounting,
            transaction_date=transaction_date,
            series=series,
            number=number)

        for transaction in transactions:
            account = transaction.account
            if not isinstance(account, blm.TO):
                account, = blm.accounting.Account._query(
                    number=str(account)).run()
            blm.accounting.Transaction(
                verification=verification,
                version=verification.version,
                account=account,
                amount=transaction.amount,
                text=transaction.text)

        return verification


class TestBulk(ReportTests):

    def import_sie(self, fname, org=[]):
        importer = sie_import.SIEImporter(list(org))
        importer.ignoretransactions = False
        importer.parseFile(sie)
        return importer.accounting

    def test_reports(self, monkeypatch):
        #py.test.skip()
        # find smaller test case, perhaps?
        fname = os.path.join(self.here, 'sie', 'sie4.se')
        importer = sie_import.SIEImporter([self.org])
        importer.parseFile(fname)
        toid = str(importer.accounting.id[0])

        self.commit()
        self.sync()

        with wsgi.app.test_client() as c:
            response = c.get('/kontoplan/%s' % toid)
            assert response.status_code == httplib.OK

            response = c.get('/huvudbok/%s' % toid)
            assert response.status_code == httplib.OK

            response = c.get('/balansrakning/%s' % toid)
            assert response.status_code == httplib.OK

            response = c.get('/resultatrakning/%s' % toid)
            assert response.status_code == httplib.OK

            response = c.get('/verifikationslista/%s' % toid)
            assert response.status_code == httplib.OK


class TestKontoplan(ReportTests):

    name = 'kontoplan'

    def test_kontoplan(self):
        accounts = []
        for n in range(1000, 10000, 1000):
            accounts.append(self.mkAccount(n))

        self.commit()

        tree = self.run_report()

        assert len(tree.xpath('//tr/th')) == 3

        rows = tree.xpath('//tr[@class="account"]')
        assert len(rows) == len(accounts)

        for account, row in zip(accounts, rows):
            assert row.findtext('td[@class="number"]') == account.number[0]
            assert row.findtext('td[@class="name"]') == account.name[0]
            assert row.findtext('td[@class="type"]') == account.type[0]


class TestHuvudbok(ReportTests):

    name = 'huvudbok'

    def test_huvudbok(self):
        acc1000 = self.mkAccount(1000, opening_balance=5)
        acc2000 = self.mkAccount(2000, opening_balance=-5)
        self.commit()

        ver1 = self.mkVer(1, 'A', '2010-01-01', transactions=[
                transdata(1000, 'foo', 10),
                transdata(2000, 'foo', -10)
                ])

        ver2 = self.mkVer(2, 'B', '2010-01-02', transactions=[
                transdata(1000, 'bar', 20),
                transdata(2000, 'bar', -20)
                ])
        self.commit()

        tree = self.run_report()

        acc1000section, = tree.xpath('//tbody[@id="account-1000"]')
        header, = acc1000section.xpath('tr[@class="account-header"]')
        assert header.findtext('td[@class="number"]') == '1000'
        assert header.findtext('td[@class="name"]') == 'Account 1000'
        assert header.findtext('td[@class="amount"]') == '5.00'

        ver1row, ver2row = acc1000section.xpath('tr[@class="verification"]')
        assert ver1row.findtext('td[@class="name"]') == 'A 1'
        assert ver1row.findtext('td[@class="date"]') == '2010-01-01'
        assert ver1row.findtext('td[@class="text"]') == 'foo'
        assert ver1row.findtext('td[@class="debit"]') == '10.00'
        assert ver1row.findtext('td[@class="credit"]') == None
        assert ver1row.findtext('td[@class="balance"]') == '15.00'

        assert ver2row.findtext('td[@class="name"]') == 'B 2'
        assert ver2row.findtext('td[@class="date"]') == '2010-01-02'
        assert ver2row.findtext('td[@class="text"]') == 'bar'
        assert ver2row.findtext('td[@class="debit"]') == '20.00'
        assert ver2row.findtext('td[@class="credit"]') == None
        assert ver2row.findtext('td[@class="balance"]') == '35.00'

        summary, = acc1000section.xpath('tr[@class="account-summary"]')
        summary.findtext('td[@class="debit"]') == '30.00'
        summary.findtext('td[@class="credit"]') == None


        acc2000section, = tree.xpath('//tbody[@id="account-2000"]')
        header, = acc2000section.xpath('tr[@class="account-header"]')
        assert header.findtext('td[@class="number"]') == '2000'
        assert header.findtext('td[@class="name"]') == 'Account 2000'
        assert header.findtext('td[@class="amount"]') == '-5.00'

        ver1row, ver2row = acc2000section.xpath('tr[@class="verification"]')
        assert ver1row.findtext('td[@class="name"]') == 'A 1'
        assert ver1row.findtext('td[@class="date"]') == '2010-01-01'
        assert ver1row.findtext('td[@class="text"]') == 'foo'
        assert ver1row.findtext('td[@class="debit"]') == None
        assert ver1row.findtext('td[@class="credit"]') == '10.00'
        assert ver1row.findtext('td[@class="balance"]') == '-15.00'

        assert ver2row.findtext('td[@class="name"]') == 'B 2'
        assert ver2row.findtext('td[@class="date"]') == '2010-01-02'
        assert ver2row.findtext('td[@class="text"]') == 'bar'
        assert ver2row.findtext('td[@class="debit"]') == None
        assert ver2row.findtext('td[@class="credit"]') == '20.00'
        assert ver2row.findtext('td[@class="balance"]') == '-35.00'

        summary, = acc2000section.xpath('tr[@class="account-summary"]')
        summary.findtext('td[@class="debit"]') == None
        summary.findtext('td[@class="credit"]') == '30.00'

    def test_range_filter(self):
        accounts = [
            self.mkAccount(1000, opening_balance=1),
            self.mkAccount(1001, opening_balance=1),
            self.mkAccount(1002, opening_balance=1),
            self.mkAccount(2000, opening_balance=1),
            ]
        self.commit()

        tree = self.run_report()
        assert len(tree.xpath('//tbody')) == len(accounts)

        tree = self.run_report(data={'filters': '{"accounts": "1000-1099"}'})
        assert len(tree.xpath('//tbody')) == 3
        assert tree.xpath('//tbody[@id="account-1000"]')
        assert tree.xpath('//tbody[@id="account-1001"]')
        assert tree.xpath('//tbody[@id="account-1002"]')
        assert not tree.xpath('//tbody[@id="account-2000"]')

        tree = self.run_report(data={'filters': '{"accounts": "1000,1002"}'})
        assert len(tree.xpath('//tbody')) == 2
        assert tree.xpath('//tbody[@id="account-1000"]')
        assert tree.xpath('//tbody[@id="account-1002"]')


class TestBalansrakning(ReportTests):

    name = 'balansrakning'

    def test_balansrakning(self):
        self.commit()
        self.run_report()


class TestResultatrakning(ReportTests):

    name = 'resultatrakning'

    def test_resultatrakning(self):
        self.commit()
        self.run_report()


class TestVerifikationslista(ReportTests):

    name = 'verifikationslista'

    def test_verifikationslista(self):
        acc1000 = self.mkAccount(1000, opening_balance=5)
        acc2000 = self.mkAccount(2000, opening_balance=-5)
        self.commit()

        ver1 = self.mkVer(1, 'A', '2010-01-01', transactions=[
                transdata(1000, 'foo', 10),
                transdata(2000, 'foo', -10)
                ])
        s1 = ver1.series[0]

        ver2 = self.mkVer(2, 'B', '2010-01-02', transactions=[
                transdata(1000, 'bar', 20),
                transdata(2000, 'bar', -20)
                ])
        self.commit()
        tree = self.run_report()



        assert len(tree.xpath('//tbody')) == 2
        assert tree.xpath('//tbody[@id="verification-%s"]' % ver1.id[0])
        assert tree.xpath('//tbody[@id="verification-%s"]' % ver2.id[0])

        self.commit()
        tree = self.run_report(data={'filters': '{"series": ["%s"]}' % s1.id[0]})
        assert len(tree.xpath('//tbody')) == 1
        assert tree.xpath('//tbody[@id="verification-%s"]' % ver1.id[0])


    def test_verifikationslista_filter(self):
        #tests printing of filterdata in header - test of filtering performed in previous test
        self.accounting.start = ['2010-01-01']   #start end of accounting year
        self.accounting.end = ['2010-12-31']

        acc3000 = self.mkAccount(3000, opening_balance=0)
        acc3000.account_balances['0'].budget[0]=Decimal("300.00")
        previous_year=blm.accounting.AccountBalance(year=-1,  account=acc3000) #This creates a new balance for
        previous_year.balance=[Decimal('333.00')]                                                       # a previous year, attached to the provided account object

        acc3000.account_balances['-1'].balance[0]=Decimal("-299.00") #balance of precious year
        acc1000 = self.mkAccount(1000, opening_balance=5)
        acc1000.account_balances['0'].budget[0]=Decimal("100.00")
        self.commit()

        ver1 = self.mkVer(1, 'B', '2010-01-01', transactions=[
                transdata(3000, 'foo', -100),
                transdata(1000, 'foo', 10)
                ])


        ver2 = self.mkVer(2, 'A', '2010-03-01', transactions=[
                transdata(3000, 'bar', -20),
                transdata(1000, 'bar', 20)
                ])
        s2 = ver2.series[0]  #series to test for

        ver3 = self.mkVer(3, 'B', '2010-03-31', transactions=[
                transdata(3000, 'apa', -10),
                transdata(1000, 'apa', 10)
                ])

        ver4 = self.mkVer(4, 'A', '2010-12-31', transactions=[
                transdata(3000, 'bepa', -20),
                transdata(1000, 'bepa', 20)
                ])

        self.commit()
        #correct syntax for call in reports.py
        #{u'series': [u'53d63ec9dbb7104480000121', u'53d63ededbb71044800004e7'], u'daterange': [u'2012-01-11', None], u'numbers': u'1-2'}
            ##debugcode to see what happens
       ##import pytest
        ##pytest.set_trace()
        ##end debugcode

        data={'filters': '{"daterange": ["2010-03-01","2010-03-31"], "numbers": "1-99", "series" : ["' + str(s2.id[0]) + '"]}'}

        tree=self.run_report(data=data)

       # tree = self.run_report(data={'filters': '{"accounts": "1000-1099"}'})   - example

        acc3000, = tree.xpath('//b[@id="current_year_filter-Daterange"]')
        assert acc3000.findtext(".") == 'Daterange: '

        acc3000, = tree.xpath('//b[@id="current_year_filter-Verification numbers"]')
        assert acc3000.findtext(".") == 'Verification numbers: '

        acc3000, = tree.xpath('//div[@id="verificationnumberfilter"]')
        n, =acc3000.xpath('.//span')
        assert n.text == '1-99'

        acc3000, = tree.xpath('//div[@id="seriesfilter"]')
        b, =acc3000.xpath('.//b')
        assert b.text == 'Series: '
        s, =acc3000.xpath('.//span')
        assert s.text == 'A'


class TestVerifikationslista_andrade(ReportTests):

    name = 'verifikationslista_andrade'

    def test_verifikationslista(self):
        acc1000 = self.mkAccount(1000, opening_balance=5)
        acc2000 = self.mkAccount(2000, opening_balance=-5)
        self.commit()

        ver1 = self.mkVer(1, 'A', '2010-01-01', transactions=[
                transdata(1000, 'foo', 10),
                transdata(2000, 'foo', -10)
                ])
        s1 = ver1.series[0]

        ver2 = self.mkVer(2, 'B', '2010-01-02', transactions=[
                transdata(1000, 'bar', 20),
                transdata(2000, 'bar', -20)
                ])
        self.commit()

        tree = self.run_report()

        assert len(tree.xpath('//tbody')) == 0

        # Get verification2 fresh as it is mangled by commit().
        ver2, = blm.accounting.Verification._query(id=ver2.id).run()
        ver2(transaction_date = ['2038-01-01'])
        self.commit()

        tree = self.run_report()
        assert len(tree.xpath('//tbody')) == 2
        assert tree.xpath('//tbody[@id="verification-%s"]' % ver2.id[0])

        tree = self.run_report(data={'filters': '{"series": ["%s"]}' % s1.id[0]})
        assert len(tree.xpath('//tbody')) == 0


    def test_verifikationslista_filter(self):
        #tests printing of filterdata in header - test of filtering performed in previous test
        self.accounting.start = ['2010-01-01']   #start end of accounting year
        self.accounting.end = ['2010-12-31']

        acc3000 = self.mkAccount(3000, opening_balance=0)
        acc3000.account_balances['0'].budget[0]=Decimal("300.00")
        previous_year=blm.accounting.AccountBalance(year=-1,  account=acc3000) #This creates a new balance for
        previous_year.balance=[Decimal('333.00')]                                                       # a previous year, attached to the provided account object

        acc3000.account_balances['-1'].balance[0]=Decimal("-299.00") #balance of precious year
        acc1000 = self.mkAccount(1000, opening_balance=5)
        acc1000.account_balances['0'].budget[0]=Decimal("100.00")
        self.commit()

        ver1 = self.mkVer(1, 'B', '2010-01-01', transactions=[
                transdata(3000, 'foo', -100),
                transdata(1000, 'foo', 10)
                ])


        ver2 = self.mkVer(2, 'A', '2010-03-01', transactions=[
                transdata(3000, 'bar', -20),
                transdata(1000, 'bar', 20)
                ])
        s2 = ver2.series[0]  #series to test for

        ver3 = self.mkVer(3, 'B', '2010-03-31', transactions=[
                transdata(3000, 'apa', -10),
                transdata(1000, 'apa', 10)
                ])

        ver4 = self.mkVer(4, 'A', '2010-12-31', transactions=[
                transdata(3000, 'bepa', -20),
                transdata(1000, 'bepa', 20)
                ])

        self.commit()
        #correct syntax for call in reports.py
        #{u'series': [u'53d63ec9dbb7104480000121', u'53d63ededbb71044800004e7'], u'daterange': [u'2012-01-11', None], u'numbers': u'1-2'}
            ##debugcode to see what happens
       ##import pytest
        ##pytest.set_trace()
        ##end debugcode

        data={'filters': '{"daterange": ["2010-03-01","2010-03-31"], "numbers": "1-99", "series" : ["' + str(s2.id[0]) + '"]}'}

        tree=self.run_report(data=data)

       # tree = self.run_report(data={'filters': '{"accounts": "1000-1099"}'})   - example

        acc3000, = tree.xpath('//b[@id="current_year_filter-Daterange"]')
        assert acc3000.findtext(".") == 'Daterange: '

        acc3000, = tree.xpath('//b[@id="current_year_filter-Verification numbers"]')
        assert acc3000.findtext(".") == 'Verification numbers: '

        acc3000, = tree.xpath('//div[@id="verificationnumberfilter"]')
        n, =acc3000.xpath('.//span')
        assert n.text == '1-99'

        acc3000, = tree.xpath('//div[@id="seriesfilter"]')
        b, =acc3000.xpath('.//b')
        assert b.text == 'Series: '
        s, =acc3000.xpath('.//span')
        assert s.text == 'A'


class TestArsrapport(ReportTests):

    name = 'arsrapport'

    def test_arsrapport(self):
        self.commit()
        self.run_report()

    def test_arsrapport_daterange(self):
        #Tests first and last date as well as sums
         acc3000 = self.mkAccount(3000, opening_balance=0)
         acc1000 = self.mkAccount(1000, opening_balance=5)
         self.commit()

         ver1 = self.mkVer(1, 'A', '2010-01-01', transactions=[
                transdata(3000, 'foo', -10),
                transdata(1000, 'foo', 10)
                ])

         ver2 = self.mkVer(2, 'B', '2010-12-31', transactions=[
                transdata(3000, 'bar', -20),
                transdata(1000, 'bar', 20)
                ])
         self.commit()
         tree = self.run_report()

         ##acc1000section, = tree.xpath('//tr[@id="account-1000"]')

         acc3000, = tree.xpath('//td[@id="current_year-3000"]')
         assert acc3000.findtext(".") == '30'
         """
         header, = acc1000section.xpath('tr[@class="account-header"]')
         assert header.findtext('td[@class="number"]') == '1000'
         assert header.findtext('td[@class="name"]') == 'Account 1000'
         assert header.findtext('td[@class="amount"]') == '5.00'
         """

class TestPeriodrapport(ReportTests):

    name = 'periodrapport'


    def test_periodrapport(self):
        #skipped due to failing .... causes internal server error
        #Report without data causes failure.
        #py.test.skip()
        self.commit()
        self.run_report()

    def test_periodrapport_single_account_sums(self):

        self.accounting.start = ['2010-01-01']   #start end of accounting year
        self.accounting.end = ['2010-12-31']

        acc3000 = self.mkAccount(3000, opening_balance=0)
        acc3000.account_balances['0'].budget[0]=Decimal("300.00")
        previous_year=blm.accounting.AccountBalance(year=-1,  account=acc3000) #This creates a new balance for
        previous_year.balance=[Decimal('333.00')]                                                       # a previous year, attached to the provided account object

        acc3000.account_balances['-1'].balance[0]=Decimal("-299.00") #balance of precious year
        acc1000 = self.mkAccount(1000, opening_balance=5)
        acc1000.account_balances['0'].budget[0]=Decimal("100.00")
        self.commit()

        ver1 = self.mkVer(1, 'A', '2010-01-01', transactions=[
                transdata(3000, 'foo', -100),
                transdata(1000, 'foo', 10)
                ])

        ver2 = self.mkVer(2, 'B', '2010-03-01', transactions=[
                transdata(3000, 'bar', -20),
                transdata(1000, 'bar', 20)
                ])

        ver3 = self.mkVer(3, 'A', '2010-03-31', transactions=[
                transdata(3000, 'apa', -10),
                transdata(1000, 'apa', 10)
                ])

        ver4 = self.mkVer(4, 'B', '2010-12-31', transactions=[
                transdata(3000, 'bepa', -20),
                transdata(1000, 'bepa', 20)
                ])

        self.commit()
        #tree=self.run_report(data={'filters': '{"daterange": ["2010-03-01","2010-03-31"]}'},  filtername="Period")
        #tree=self.run_report(data={'filters': '{"daterange": ["2010-03-01","2010-03-31"],
        #                                                                   "series": ['A']}'})
       # tree = self.run_report(data={'filters': '{"accounts": "1000-1099"}'})
        tree=self.run_report(data={'filters': '{"daterange": ["2010-03-01","2010-03-31"]}'})

        acc3000, = tree.xpath('//b[@id="current_year_period_filter-Daterange"]')
        assert acc3000.findtext(".") == 'Daterange: '  #just testing for text

        acc3000,  = tree.xpath('//td[@id="current_year_budget-3000"]')
        assert acc3000.findtext(".") == '300'  #budget for year

        acc3000, = tree.xpath('//td[@id="previous_year_balance-3000"]')
        assert acc3000.findtext(".") == '299'  #why is this shown as negative in the report while the above is shown positive


        acc3000, = tree.xpath('//td[@id="current_year_period_only-3000"]')
        assert acc3000.findtext(".") == '30'  #accumulated for period

        acc3000, = tree.xpath('//td[@id="current_year_start_to_period_end-3000"]')
        assert acc3000.findtext(".") == '130'  #accumulated for year start to period end

    def test_periodrapport_multiple_accounts_sums(self):
        self.accounting.start = ['2010-01-01']   #start end of accounting year
        self.accounting.end = ['2010-12-31']

        acc3000 = self.mkAccount(3000, opening_balance=0)
        acc3000.account_balances['0'].budget[0]=Decimal("300.00")
        previous_year=blm.accounting.AccountBalance(year=-1,  account=acc3000) #This creates a new balance for
        previous_year.balance=[Decimal('333.00')]                                                       # a previous year, attached to the provided account object
        acc3000.account_balances['-1'].balance[0]=Decimal("-299.00") #balance of precious year

        acc3001 = self.mkAccount(3001, opening_balance=0)
        acc3001.account_balances['0'].budget[0]=Decimal("301.00")
        previous_year=blm.accounting.AccountBalance(year=-1,  account=acc3001) #This creates a new balance for
        previous_year.balance=[Decimal('666.00')]                                                       # a previous year, attached to the provided account object
        acc3001.account_balances['-1'].balance[0]=Decimal("-399.00") #balance of precious year

        acc1000 = self.mkAccount(1000, opening_balance=5)
        acc1000.account_balances['0'].budget[0]=Decimal("100.00")

        self.commit()

        ver1 = self.mkVer(1, 'A', '2010-01-01', transactions=[
                transdata(3000, 'foo', -100),
                transdata(1000, 'foo', 10)
                ])

        ver2 = self.mkVer(2, 'B', '2010-03-01', transactions=[
                transdata(3000, 'bar', -20),
                transdata(1000, 'bar', 20)
                ])

        ver3 = self.mkVer(3, 'A', '2010-03-31', transactions=[
                transdata(3000, 'apa', -10),
                transdata(1000, 'apa', 10)
                ])

        ver4 = self.mkVer(4, 'B', '2010-12-31', transactions=[
                transdata(3000, 'bepa', -20),
                transdata(1000, 'bepa', 20)
                ])

        ver5 = self.mkVer(5, 'A', '2010-01-01', transactions=[
                transdata(3001, 'foo', -100),
                transdata(1000, 'foo', 10)
                ])

        ver6 = self.mkVer(6, 'B', '2010-03-01', transactions=[
                transdata(3001, 'bar', -20),
                transdata(1000, 'bar', 20)
                ])

        ver7 = self.mkVer(7, 'A', '2010-03-31', transactions=[
                transdata(3001, 'apa', -10),
                transdata(1000, 'apa', 10)
                ])

        ver8 = self.mkVer(8, 'B', '2010-12-31', transactions=[
                transdata(3001, 'bepa', -20),
                transdata(1000, 'bepa', 20)
                ])

        self.commit()
        tree=self.run_report(data={'filters': '{"daterange": ["2010-03-01","2010-03-31"]}'})
       # tree = self.run_report(data={'filters': '{"accounts": "1000-1099"}'})

        accs3000, = tree.xpath('//td[@id="current_year_budget_sums"]')
        assert accs3000.findtext(".") == '601'  #budget for year

        accs3000, = tree.xpath('//td[@id="previous_year_balance_sums"]')
        assert accs3000.findtext(".") == '698'  #why is this shown as negative in the report while the above is shown positive


        accs3000, = tree.xpath('//td[@id="current_year_period_only_sums"]')
        assert accs3000.findtext(".") == '60'  #accumulated for period

        accs3000, = tree.xpath('//td[@id="current_year_start_to_period_end_sums"]')
        assert accs3000.findtext(".") == '260'  #accumulated for year start to period end

        #print dir(tree),  tree.xpath("//Period")[0].findtext(".")


    def test_filter_name_and_values_shown(self):

        self.accounting.start = ['2010-01-01']   #start end of accounting year
        self.accounting.end = ['2010-12-31']

        acc3000 = self.mkAccount(3000, opening_balance=0)
        acc3000.account_balances['0'].budget[0]=Decimal("300.00")
        previous_year=blm.accounting.AccountBalance(year=-1,  account=acc3000) #This creates a new balance for
        previous_year.balance=[Decimal('333.00')]                                                       # a previous year, attached to the provided account object

        acc3000.account_balances['-1'].balance[0]=Decimal("-299.00") #balance of precious year
        acc1000 = self.mkAccount(1000, opening_balance=5)
        acc1000.account_balances['0'].budget[0]=Decimal("100.00")
        self.commit()

        ver1 = self.mkVer(1, 'A', '2010-01-01', transactions=[
                transdata(3000, 'foo', -100),
                transdata(1000, 'foo', 10)
                ])

        ver2 = self.mkVer(2, 'B', '2010-03-01', transactions=[
                transdata(3000, 'bar', -20),
                transdata(1000, 'bar', 20)
                ])

        ver3 = self.mkVer(3, 'A', '2010-03-31', transactions=[
                transdata(3000, 'apa', -10),
                transdata(1000, 'apa', 10)
                ])

        ver4 = self.mkVer(4, 'B', '2010-12-31', transactions=[
                transdata(3000, 'bepa', -20),
                transdata(1000, 'bepa', 20)
                ])

        self.commit()
        tree=self.run_report(data={'filters': '{"daterange": ["2010-03-01","2010-03-31"]}'})
       # tree = self.run_report(data={'filters': '{"accounts": "1000-1099"}'})

        acc3000, = tree.xpath('//b[@id="current_year_period_filter-Daterange"]')
        assert acc3000.findtext(".") == 'Daterange: '  #just testing for text

        acc3000, = tree.xpath('//td[@id="current_year_budget-3000"]')
        assert acc3000.findtext(".") == '300'  #budget for year

        acc3000, = tree.xpath('//td[@id="previous_year_balance-3000"]')
        assert acc3000.findtext(".") == '299'  #why is this shown as negative in the report while the above is shown positive


        acc3000, = tree.xpath('//td[@id="current_year_period_only-3000"]')
        assert acc3000.findtext(".") == '30'  #accumulated for period

        acc3000, = tree.xpath('//td[@id="current_year_start_to_period_end-3000"]')
        assert acc3000.findtext(".") == '130'  #accumulated for year start to period end


class TestVatReport(ReportTests):

    name = 'vatreport'

    def setup_method(self, method):
        super(TestVatReport, self).setup_method(method)
        self.acc1920 = self.mkAccount(1920, name='Plusgiro')
        self.acc2611 = self.mkAccount(2611, name='Moms, 25%', vatCode='10')
        self.acc3000 = self.mkAccount(3000, name=u'Försäljning')
        self.commit()

    def test_vat_report(self):
        self.mkVer(1, transactions=[
                transdata(1920, 'Expensive stuff', 1000),
                transdata(2611, 'Expensive stuff',  200),
                transdata(3000, 'Expensive stuff',  800),
                ])

        self.mkVer(2, transactions=[
                transdata(1920, 'Cheap stuff', 100),
                transdata(2611, 'Cheap stuff',  20),
                transdata(3000, 'Cheap stuff',  80),
                ])
        self.commit()

        tree = self.run_report(html=True)

        td_code, = tree.cssselect('td.vatCode')
        assert td_code.text_content() == '10'

        td_amount, = tree.cssselect('td.amount')
        assert td_amount.text_content() == '220.00'


class TestSalesReport(ReportTests):

    name = 'salesreport'

    def test_sales_report(self):
        product = blm.members.Product(org=self.org, name='Stuff')
        pi1 = blm.members.PurchaseItem(product=product)
        pi2 = blm.members.PurchaseItem(product=product)
        purchase = blm.members.Purchase(items=[pi1, pi2])
        self.commit()

        tree = self.run_report(toi=product, html=True)
        row1, row2 = tree.cssselect('tbody tr')


class TestAccountspayableReport(ReportTests):

    name = 'accountspayable_report'

    def test_accountspayable_report(self):
        #self.org = blm.accounting.Org(subscriptionLevel='subscriber') In super setup_method.
        #self.accounting = blm.accounting.Accounting(org=self.org)
        self.account1000 = blm.accounting.Account(accounting=self.accounting, number='1000')
        self.account2000 = blm.accounting.Account(accounting=self.accounting, number='2000')
        self.account3000 = blm.accounting.Account(accounting=self.accounting, number='3000')
        self.account4000 = blm.accounting.Account(accounting=self.accounting, number='4000')
        self.series = blm.accounting.VerificationSeries(accounting=self.accounting, name='A')
        self.provider = blm.accounting.SupplierInvoiceProvider(org=self.org, series='A', account='3000', bank_account='4000')

        self.invoice1 = {
            u'bankaccount': u'',
            u'invoiceNumber': u'',
            u'invoiceDate': u'2017-03-08',
            u'amount': 5000,
            u'transferDate': u'2017-05-06',
            u'invoiceType': u'debit',
            u'pgnum': u'',
            u'invoiceIdentifierType': u'ocr',
            u'transferMethod': u'bgnum',
            u'message': u'',
            u'ocr': u'56897456986',
            u'recipient': u'Mottagar1 AB',
            u'dueDate': u'2018-03-25',
            u'bgnum': u'8888885',
            u'regVerificationVersion': 1,
            u'regVerificationLines': [
                {
                    u'text': u'purchases going up',
                    u'account': str(self.account2000.id[0]),
                    u'amount': 5000,
                    u'version': 1
                },
                {
                    u'amount': -5000,
                    u'account': str(self.account3000.id[0]),
                    u'text': u'Supplier debt credit account going up',
                    u'version': 1
                }
            ]
        }
        self.invoice2 = {
            u'bankaccount': u'',
            u'invoiceNumber': u'12356986799',
            u'invoiceDate': u'2017-04-08',
            u'amount': 4000,
            u'transferDate': u'2017-05-03',
            u'invoiceType': u'debit',
            u'pgnum': u'',
            u'invoiceIdentifierType': u'invoiceNumber',
            u'transferMethod': u'bgnum',
            u'message': u'Leverans två',
            u'ocr': u'',
            u'recipient': u'Mottagar2 AB',
            u'dueDate': u'2018-04-25',
            u'bgnum': u'8888885',
            u'regVerificationVersion': 1,
            u'regVerificationLines': [
                {
                    u'text': u'asdfasdf',
                    u'account': str(self.account1000.id[0]),
                    u'amount': 4000,
                    u'version': 1
                },
                {
                    u'amount': -4000,
                    u'account': str(self.account3000.id[0]),
                    u'text': u'n\xe5gotannat',
                    u'version': 1
                }
            ]
        }

        r1, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[copy.deepcopy(self.invoice1)])
        si1 = r1['supplierInvoice']
        r2, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[copy.deepcopy(self.invoice2)])
        si2 = r2['supplierInvoice']
        supInvList = [si1, si2]
        result = blm.accounting.setSIState(org=[self.org], supInvList=supInvList, newstate=['paid'])
        result, = blm.accounting.createTransferVerification(org=[self.org], supInvList=supInvList)
        supInvList = result['accounted']
        self.commit()
        self.sync()

        tree = self.run_report(self.accounting, html=True)
        row1, row2 = tree.cssselect('tbody tr')

        td_ver, = row1.cssselect('td.verifications')
        assert td_ver.text_content().split() == ['A2', 'A3']
        td_debit, = row1.cssselect('td.debit')
        assert td_debit.text_content() == '40.00'
        td_ver, = row2.cssselect('td.verifications')
        assert td_ver.text_content().split() == ['A1', 'A3']


class TestAccountspayablePaymentJournal(ReportTests):

    name = 'accountspayable_paymentjournal'

    def test_accountspayable_paymentjournal(self):
        self.account1000 = blm.accounting.Account(accounting=self.accounting, number='1000')
        self.account2000 = blm.accounting.Account(accounting=self.accounting, number='2000')
        self.account3000 = blm.accounting.Account(accounting=self.accounting, number='3000')
        self.account4000 = blm.accounting.Account(accounting=self.accounting, number='4000')
        self.series = blm.accounting.VerificationSeries(accounting=self.accounting, name='A')
        self.provider = blm.accounting.SupplierInvoiceProvider(org=self.org, series='A', account='3000', bank_account='4000')

        self.invoice1 = {
            u'bankaccount': u'',
            u'invoiceNumber': u'',
            u'invoiceDate': u'2017-03-08',
            u'amount': 5000,
            u'transferDate': u'2017-05-06',
            u'invoiceType': u'debit',
            u'pgnum': u'',
            u'invoiceIdentifierType': u'ocr',
            u'transferMethod': u'bgnum',
            u'message': u'',
            u'ocr': u'56897456986',
            u'recipient': u'Mottagar1 AB',
            u'dueDate': u'2018-03-25',
            u'bgnum': u'8888885',
            u'regVerificationVersion': 1,
            u'regVerificationLines': [
                {
                    u'text': u'purchases going up',
                    u'account': str(self.account2000.id[0]),
                    u'amount': 5000,
                    u'version': 1
                },
                {
                    u'amount': -5000,
                    u'account': str(self.account3000.id[0]),
                    u'text': u'Supplier debt credit account going up',
                    u'version': 1
                }
            ]
        }
        self.invoice2 = {
            u'bankaccount': u'',
            u'invoiceNumber': u'12356986799',
            u'invoiceDate': u'2017-04-08',
            u'amount': 4000,
            u'transferDate': u'2017-05-03',
            u'invoiceType': u'debit',
            u'pgnum': u'',
            u'invoiceIdentifierType': u'invoiceNumber',
            u'transferMethod': u'bgnum',
            u'message': u'Leverans två',
            u'ocr': u'',
            u'recipient': u'Mottagar2 AB',
            u'dueDate': u'2018-04-25',
            u'bgnum': u'8888885',
            u'regVerificationVersion': 1,
            u'regVerificationLines': [
                {
                    u'text': u'asdfasdf',
                    u'account': str(self.account1000.id[0]),
                    u'amount': 4000,
                    u'version': 1
                },
                {
                    u'amount': -4000,
                    u'account': str(self.account3000.id[0]),
                    u'text': u'n\xe5gotannat',
                    u'version': 1
                }
            ]
        }

        r1, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[copy.deepcopy(self.invoice1)])
        si1 = r1['supplierInvoice']
        r2, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[copy.deepcopy(self.invoice2)])
        si2 = r2['supplierInvoice']
        self.commit()
        supInvList = [si1, si2]
        self.sync()
        toilist = [str(si1.id[0]), str(si2.id[0])]
        print(toilist)

        tree = self.run_report(self.accounting, html=True)
        #row1, row2 = tree.cssselect('tbody tr')

        # td_ver, = row1.cssselect('td.verifications')
        # assert td_ver.text_content().split() == ['2', '3']
        # td_debit, = row1.cssselect('td.debit')
        # assert td_debit.text_content() == '40.00'
        # td_ver, = row2.cssselect('td.verifications')
        # assert td_ver.text_content().split() == ['1', '3']
