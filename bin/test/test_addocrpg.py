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

import py
from pytransact.testsupport import BLMTests
import accounting.db
import blm.accounting

from .. import addocrpg


class TestAdding(BLMTests):

    def test_addocr(self):
        org1 = blm.accounting.Org(orgnum=['123456-7890'],
                                  subscriptionLevel=['subscriber'])
        pgp1 = blm.accounting.PlusgiroProvider(org=[org1], pgnum_real=['2345'])

        org2 = blm.accounting.Org(orgnum=['234567-8901'],
                                  subscriptionLevel=['subscriber'])
        pgp2a = blm.accounting.PlusgiroProvider(org=[org2], pgnum_real=['2345'])
        pgp2b = blm.accounting.PlusgiroProvider(org=[org2], pgnum_real=['3459'])
        self.commit()

        addocrpg.addocr(self.database, '2345678901', '234-5', '4730500-8')
        self.sync()

        pgp, = blm.accounting.PlusgiroProvider._query(pgnum=['47305008']).run()
        assert pgp.org == [org2]

        # check digit fail
        py.test.raises(ValueError, addocrpg.addocr,
                       self.database, '2345678901', '234-5', '4730500-9')

def test_main(monkeypatch):
    calls = []
    database = object()
    monkeypatch.setattr(accounting.db, 'connect', lambda: database)
    def addocr(db, *args):
        assert db == database
        calls.append(args)
    monkeypatch.setattr(addocrpg, 'addocr', addocr)

    addocrpg.main(['foo', 'bar', 'baz'])
    assert calls == [('foo', 'bar', 'baz')]
