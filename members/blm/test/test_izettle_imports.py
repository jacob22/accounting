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

import os, copy, decimal, email, py.test, time, json
from bson.objectid import ObjectId
from pytransact.exceptions import ClientError, LocalisedError
from pytransact.testsupport import BLMTests, Time
from accounting import config, mail, payson, seqr
import members
from members import base64long
import blm.members

from accounting.test.blmsupport import PermissionTests

import sys
if sys.version_info < (3,0,0):
    PYT3 = False
else:
    PYT3 = True
    import codecs


class TestImportIzettlePayments(BLMTests):
    def setup_method(self, method):
        super(TestImportIzettlePayments, self).setup_method(method)
        self.org = blm.accounting.Org(subscriptionLevel='subscriber')
        self.accounting = accounting = blm.accounting.Accounting(org=self.org)
        self.account1000 = blm.accounting.Account(accounting=accounting, number='1000')
        self.account2000 = blm.accounting.Account(accounting=accounting, number='2000')
        self.account3000 = blm.accounting.Account(accounting=accounting, number='3000')
        self.account4000 = blm.accounting.Account(accounting=accounting, number='4000')
        self.account5000 = blm.accounting.Account(accounting=accounting, number='5000')
        self.pp = blm.accounting.IzettleProvider(org=self.org, account='1000', series='A',
                                                 fee_account='4000', cash_account='5000')

    def test_import_products(self):
        # read products file
        ppath = os.path.join(os.path.dirname(__file__), '../../../misc/izettle/variantproducts.xls') 
        with open(ppath, 'rb') as f:
            if PYT3:
                pxlsstring = codecs.encode(f.read(), 'base64')
                pxlsstring = pxlsstring.decode()
            else:
                pxlsstring = f.read().encode('base64')
        # import products via blm metod
        blm.members.import_izettle_products_file([self.org], [pxlsstring])
        self.commit()

        product_price, = blm.members.IzettleProduct._query(org=self.org, name='2 h').run()
        assert product_price.izPrice == [decimal.Decimal('100.00')]

        product_noprice, = blm.members.IzettleProduct._query(org=self.org, name='4 h').run()
        assert product_noprice.izPrice == []

    def test_import_products_newer(self):
        # read products file
        ppath = os.path.join(os.path.dirname(__file__), '../../../misc/izettle/izettle_product_export_2017-04-12.xls') 
        with open(ppath, 'rb') as f:
            if PYT3:
                pxlsstring = codecs.encode(f.read(), 'base64')
                pxlsstring= pxlsstring.decode()
            else:
                pxlsstring = f.read().encode('base64')
        # import products via blm metod
        blm.members.import_izettle_products_file([self.org], [pxlsstring])
        self.commit()

        product_price, = blm.members.IzettleProduct._query(org=self.org, name='2 h').run()
        assert product_price.izPrice == [decimal.Decimal('100.00')]

        product_noprice, = blm.members.IzettleProduct._query(org=self.org, name='4 h').run()
        assert product_noprice.izPrice == [decimal.Decimal('200.00')]
        

    def test_import_transactions(self):
        # read file
        path = os.path.join(os.path.dirname(__file__), '../../../misc/izettle/transactions-light2.xls')
        with open(path, 'rb') as f:
            if PYT3:
                xlsstring = codecs.encode(f.read(), 'base64')
                xlsstring = xlsstring.decode()
            else:
                xlsstring = f.read().encode('base64')
        # import file via blm metod
        blm.members.import_izettle_payments([self.org], [os.path.basename(path)], [xlsstring])
        self.commit()
        # do search
        payments = blm.members.IzettlePayment._query(org=self.org, receipt_number=7925).run()
        # check a certain payment exists
        assert payments[0].amount == [decimal.Decimal('60.00')]
        assert payments[0].netto == [decimal.Decimal('58.35')]
        assert payments[0].izettle_fee == [decimal.Decimal('1.65')]
        assert payments[0].description == [u'Kaffe/te, Kaka, Fika klubbhuset, 2 x Läsk']
        assert payments[0].paymentProvider == [self.pp]

        initial = len(blm.members.IzettlePayment._query(org=self.org).run())
        blm.members.import_izettle_payments([self.org], [os.path.basename(path)], [xlsstring])
        assert initial == len(blm.members.IzettlePayment._query(org=self.org).run())

    def test_import_transactions_newer(self):
        # read file
        path = os.path.join(os.path.dirname(__file__), '../../../misc/izettle/iZettle-Report-2017-03-13-2017-04-12.xls')
        with open(path, 'rb') as f:
            if PYT3:
                xlsstring = codecs.encode(f.read(), 'base64')
                xlsstring = xlsstring.decode()
            else:
                xlsstring = f.read().encode('base64')
        # import file via blm metod
        blm.members.import_izettle_payments([self.org], [os.path.basename(path)], [xlsstring])
        self.commit()
        # do search
        payments = blm.members.IzettlePayment._query(org=self.org, receipt_number=8209).run()
        # check a certain payment exists
        assert payments[0].amount == [decimal.Decimal('40.00')]
        assert payments[0].netto == [decimal.Decimal('38.90')]
        assert payments[0].izettle_fee == [decimal.Decimal('1.10')]
        assert payments[0].description == [u'2 x Fika klubbhuset']
        assert payments[0].paymentProvider == [self.pp]

        initial = len(blm.members.IzettlePayment._query(org=self.org).run())
        blm.members.import_izettle_payments([self.org], [os.path.basename(path)], [xlsstring])
        assert initial == len(blm.members.IzettlePayment._query(org=self.org).run())

    def test_izettle_verifications(self):
        # read products file
        #ppath = os.path.join(os.path.dirname(__file__), '../../../misc/izettle/products.xls')
        ppath = os.path.join(os.path.dirname(__file__), '../../../misc/izettle/izettle_product_export_2017-04-12.xls') 
        with open(ppath, 'rb') as f:
            if PYT3:
                pxlsstring = codecs.encode(f.read(), 'base64')
                pxlsstring = pxlsstring.decode()
            else:
                pxlsstring = f.read().encode('base64')
        # import products via blm metod
        blm.members.import_izettle_products_file([self.org], [pxlsstring])
        self.commit()

        # Add accounting rules to products
        for product in blm.members.IzettleProduct._query(org=self.org).run():
            if product.izPrice:
                product.accountingRules = {'2000': product.izPrice[0]}
        self.commit()

        # read transactions file
        tpath = os.path.join(os.path.dirname(__file__), '../../../misc/izettle/transactions-light2.xls')
        with open(tpath, 'rb') as f:
            if PYT3:
                txlsstring = codecs.encode(f.read(), 'base64')
                txlsstring = txlsstring.decode()
            else:
                txlsstring = f.read().encode('base64')
        # import transactions via blm metod
        blm.members.import_izettle_payments([self.org], [os.path.basename(tpath)], [txlsstring])
        self.commit()

        # Check verifications created from the import
        assert 105 == len(blm.members.IzettlePayment._query(org=self.org).run())
        assert 7 == len(blm.members.IzettlePayment._query(org=self.org, approved=False).run())
        assert 4 == len(blm.members.IzettleRebate._query(org=self.org, approved=True).run())
        assert 102 == len(blm.accounting.Verification._query(accounting=self.accounting).run())

        # Check purchase matches refund of the same.
        ver_purch, = blm.accounting.Verification._query(accounting=self.accounting, number=97).run()
        ver_refund, = blm.accounting.Verification._query(accounting=self.accounting, number=98).run()
        for tp, tr in zip(ver_purch.transactions, ver_refund.transactions):
            assert tp.account[0].number[0] == tr.account[0].number[0]
            if not tp.text[0] == tr.text[0]:
                assert tp.text[0] == u'iZettle (Uthyrningen NPK)(4161): 2 x Läsk, 3 h'
                assert tr.text[0] == u'iZettle (Uthyrningen NPK)(4162): 2 x Läsk, 3 h'
            assert tp.amount[0] == -tr.amount[0]

        # Test iZettle rebate
        ver_reb, = blm.accounting.Verification._query(accounting=self.accounting, number=100).run()
        t1, t2 = ver_reb.transactions
        
        assert t1.text[0] == u'iZettle: Insättning 2016-07-01 - 2016-07-31'
        assert t1.account[0].number[0] == '1000'
        assert t1.amount[0] == decimal.Decimal('2161.58')
                     
        assert t2.text[0] == u'iZettle: Insättning 2016-07-01 - 2016-07-31'
        assert t2.account[0].number[0] == '4000'
        assert t2.amount[0] == decimal.Decimal('-2161.58')

                
