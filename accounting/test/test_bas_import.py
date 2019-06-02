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

from accounting.bas_import import BASImporter
import py, xlrd
try:
    from StringIO import StringIO   #py2
except ImportError:
    from io import StringIO         #py3
    
from decimal import Decimal
from datetime import date
from pytransact.testsupport import BLMTests
import blm

class FakeWorkbook(object):
    def __init__(self, fname):
        pass

class FakeSheet(object):
    def __init__(self, rows):
        self.rows = rows
        self.nrows = len(rows)

    def row(self, idx):
        return self.rows[idx]

class FakeCell(object):
    def __init__(self, ctype, value):
        self.ctype = ctype
        self.value = value

class TestBASImporter(BLMTests):
    def test_parser(self, monkeypatch):
        monkeypatch.setattr(xlrd, 'open_workbook', lambda *a: FakeWorkbook(*a))
        importer = BASImporter('test', 'foo', {'1234': '10'})

        importer.xlrd.sheets = lambda: [FakeSheet(
                [[FakeCell(xlrd.XL_CELL_NUMBER, 11.0),
                 FakeCell(xlrd.XL_CELL_NUMBER, 1234.0), FakeCell(xlrd.XL_CELL_TEXT, 'testkonto')]]
                )]

        importer.parse()

        coa, = blm.accounting.ChartOfAccounts._query().run()
        assert len(coa.accounts) == 1
        assert coa.accounts[0].number == ['1234']
        assert coa.accounts[0].name == ['testkonto']
        assert coa.accounts[0].vatCode == ['10']
