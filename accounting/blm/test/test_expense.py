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

import decimal
from pytransact.testsupport import BLMTests
import blm.accounting
import blm.expense


class TestBaseCategory(BLMTests):

    def setup_method(self, method):
        super(TestBaseCategory, self).setup_method(method)
        self.org = blm.accounting.Org()

    def test_createCategory_Category(self):
        cat, = blm.expense.createCategory(
            tocName=['Category'],
            data=[{
                'org': str(self.org.id[0]),
                'name': 'Hydrospanners and transmogrifiers',
                'account': '2000',
            }])
        assert isinstance(cat, blm.expense.Category)
        assert cat.name == ['Hydrospanners and transmogrifiers']
        assert cat.account == ['2000']

    def test_createCategory_CategoryCountable(self):
        cat, = blm.expense.createCategory(
            tocName=['CategoryCountable'],
            data=[{
                'org': str(self.org.id[0]),
                'name': 'Hydrospanners and transmogrifiers',
                'account': '2000',
                'price': 1234,
                'unit': 'lbs'
            }])
        assert isinstance(cat, blm.expense.CategoryCountable)
        assert cat.name == ['Hydrospanners and transmogrifiers']
        assert cat.account == ['2000']
        assert cat.price == [decimal.Decimal('12.34')]
        assert cat.unit == ['lbs']

    def test_createCategory_CategoryOne(self):
        cat, = blm.expense.createCategory(
            tocName=['CategoryOne'],
            data=[{
                'org': str(self.org.id[0]),
                'name': 'Hydrospanners and transmogrifiers',
                'account': '2000',
                'price': 1234,
            }])
        assert isinstance(cat, blm.expense.CategoryOne)
        assert cat.name == ['Hydrospanners and transmogrifiers']
        assert cat.account == ['2000']
        assert cat.price == [decimal.Decimal('12.34')]

    def test_save(self):
        cat = blm.expense.CategoryOne(
            org=[self.org],
            name=['Transmogrifiers and hydrospanners'],
            account=['1000'],
            price=['10.00'])
        cat.save([{
            'name': 'Hydrospanners and transmogrifiers',
            'account': '2000',
            'price': 1234,
        }])
        assert cat.name == ['Hydrospanners and transmogrifiers']
        assert cat.account == ['2000']
        assert cat.price == [decimal.Decimal('12.34')]
