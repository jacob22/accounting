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

import sys
if sys.version_info < (3,0,0):
    PYT3 = False
else:
    PYT3 = True
import datetime, os, shutil
import pymongo
from pytransact.testsupport import DBTests, BLMTests
from accounting import db, config, mail
from .. import process_payments
import blm.members
import members.paymentgen

root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


class TestMain(DBTests):

    def test_main(self, monkeypatch):
        calls = []
        monkeypatch.setattr(db, 'connect', lambda: self.database)
        def process_file(database, fname):
            assert database.name == self.database.name
            assert database.read_preference == pymongo.ReadPreference.PRIMARY
            calls.append(fname)
        monkeypatch.setattr(process_payments, 'process_file', process_file)
        progname = 'process_payments'
        process_payments.main([progname, '/foo/bar/baz'])
        assert calls == ['/foo/bar/baz']


class TestProcessPayments(BLMTests):

    def setup_method(self, method):
        super(TestProcessPayments, self).setup_method(method)
        self.config = config.save()

    def teardown_method(self, method):
        super(TestProcessPayments, self).teardown_method(method)
        config.restore(self.config)

    def test_process_file(self, tmpdir):
        archive = tmpdir.mkdir('archive')
        config.config.set('plusgiro', 'archive', str(archive))
        test = os.path.join(root, 'members', 'test',
                            'total_in_bas_exempelfil.txt')
        source = str(tmpdir.join('source'))

        shutil.copy(test, source)

        process_payments.process_file(self.database, str(source))

        pf, = blm.members.PGPaymentFile._query().run()
        assert pf.fileName == ['source']

        assert not os.path.exists(source)
        assert os.path.exists(str(archive.join('source')))

        assert archive.join('source').read('rb') == open(test, 'rb').read()

        # xxx test .match()

    def test_multiple_partial_payments(self, monkeypatch, tmpdir):
        monkeypatch.setattr(mail, 'sendmail', lambda *args, **kw: None)
        org = blm.accounting.Org(name=['ACME'],
                                 subscriptionLevel=['subscriber'])
        provider = blm.accounting.PlusgiroProvider(org=[org], pgnum=['42-2'])
        product = blm.members.Product(org=[org], name=['foo'],
                                      accountingRules={'1234': '100'})

        archive = tmpdir.mkdir('archive')
        config.config.set('plusgiro', 'archive', str(archive))

        purchase = blm.members.Purchase(
            items=[blm.members.PurchaseItem(product=[product])],
            buyerEmail='noone@openend.se')

        self.commit()

        provider, = blm.accounting.PlusgiroProvider._query().run()
        purchase, = blm.members.Purchase._query().run()
        purchase.partial_payments = 2

        source = tmpdir.join('source')
        with open(str(source), 'w') as f:
            members.paymentgen.generate_pg_file(
                provider, [purchase],
                datetime.datetime.now().strftime('%Y%m%d%H%M%S'),
                file_id=1, start_tid=1, out=f)

        process_payments.process_file(self.database, str(source))
        pf, = blm.members.PGPaymentFile._query().run()
        assert pf.fileName == ['source']

        purchase, = blm.members.Purchase._query().run()
        assert purchase.paymentState == ['paid']
