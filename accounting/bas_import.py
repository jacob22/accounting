#!/usr/bin/env python
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
from datetime import datetime

import logging, xlrd, re
from accounting import db
from pytransact import blm, commit
from blm import fundamental, accounting


class BASImporter(object):
    def __init__(self, name, fname, vatCodes, replace=False):
        self.name = name
        self.replace = replace
        self.vatCodes = vatCodes
        self.xlrd = xlrd.open_workbook(fname)

    def parse(self):
        coa = blm.accounting.ChartOfAccounts._query(name=self.name).run()
        if coa:
            if not self.replace:
                raise RuntimeError('%s already exists' % self.name)
            coa, = coa
        else:
            coa = blm.accounting.ChartOfAccounts(name=[self.name])

        for acc in coa.accounts:
            acc._delete()

        accts = []
        for sheet in self.xlrd.sheets():
            for row_idx in range(sheet.nrows):
                celliter = iter(sheet.row(row_idx))
                for cell in celliter:
                    if (cell.ctype == xlrd.XL_CELL_NUMBER and
                        cell.value >= 1000 and cell.value <= 9999):
                        acctno = '%.0f' % cell.value # XXX They are floats!
                        descrcell = next(celliter)
                        if descrcell.ctype != xlrd.XL_CELL_TEXT:
                            continue
                        acctdescr = descrcell.value
                        accts.append(blm.accounting.AccountTemplate(
                                number = [acctno],
                                name = [acctdescr],
                                vatCode = self.vatCodes.get(acctno, [])
                                ))

        coa(accounts=accts)

class COAImporter(object):
    def __init__(self, name, fname, replace=False):
        self.name = name
        self.replace = replace
        self.f = file(fname)

    def parse(self):
        coa = blm.accounting.ChartOfAccounts._query(name=self.name).run()
        if coa:
            if not self.replace:
                raise RuntimeError('%s already exists' % self.name)
            coa, = coa
        else:
            coa = blm.accounting.ChartOfAccounts(name=[self.name])

        for acc in coa.accounts:
            acc._delete()

        accts = []
        for line in self.f:
            line = line.decode('utf-8')
            if not all(map(unicode.isdigit, line[:4])):
                # skip lines not starting with 4 digits
                continue
            try:
                acctno, _type, vatCode, acctdescr = map(unicode.strip, line.split('\t'))
            except ValueError:
                print(repr(line))
                raise
            _type = [t for t in [_type] if t]   #filter(None, [_type])
            vatCode = [vc for vc in [vatCode] if vc]    # filter(None, [vatCode])
            accts.append(blm.accounting.AccountTemplate(
                number = [acctno],
                name = [acctdescr],
                vatCode = vatCode,
                type = _type
                ))

        coa(accounts=accts)

if __name__ == '__main__':
    import bson, locale, sys
    database = db.connect()
    if not (2 < len(sys.argv) < 5):
        sys.stderr.write('Usage: %s <display name> <filename> [replace]\n' % sys.argv[0])
        sys.exit(1)

    name, fname = sys.argv[1:3]
    name = unicode(name, locale.getpreferredencoding())
    replace = bool(filter(lambda x: x.lower() == 'replace', sys.argv[3:]))

    sys.stdout.write('Importing %s ' % fname)
    sys.stdout.flush()
    interested = bson.objectid.ObjectId()
    with commit.CommitContext(database) as ctx:
        ctx.setMayChange(True)
        if fname.endswith('.xls'):
            importer = BASImporter(name, fname, replace)
        else:
            importer = COAImporter(name, fname, replace)
        importer.parse()
        ctx.runCommit([], interested=interested)
    result, errors = commit.wait_for_commit(database, interested=interested)
    assert not errors
    sys.stdout.write('done, created: %s\n' % name)
