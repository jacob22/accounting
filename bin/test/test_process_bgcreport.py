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

import datetime, os, shutil
import pymongo
from pytransact.testsupport import DBTests, BLMTests
from accounting import db, config
from .. import process_bgcreport
import blm
import tempfile

root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


class TestMain(DBTests):

    def test_main(self, monkeypatch):
        calls = []
        monkeypatch.setattr(db, 'connect', lambda: self.database)
        def process_file(database, fname):
            assert database.name == self.database.name
            assert database.read_preference == pymongo.ReadPreference.PRIMARY
            calls.append(fname)
        monkeypatch.setattr(process_bgcreport, 'process_file', process_file)
        progname = 'process_bgcreports'
        process_bgcreport.main([progname, '/foo/bar/baz'])
        assert calls == ['/foo/bar/baz']


class TestProcessBgcReport(BLMTests):

    def setup_method(self, method):
        super(TestProcessBgcReport, self).setup_method(method)
        self.config = config.save()

    def teardown_method(self, method):
        super(TestProcessBgcReport, self).teardown_method(method)
        config.restore(self.config)

    def test_process_file(self, tmpdir):
        tmpdir = str(tmpdir)
        archive = os.path.join(tmpdir, 'archive')
        os.mkdir(archive)
        sourcefn = 'BFEP2.ULBLB.source'
        source = os.path.join(tmpdir, sourcefn)
        config.config.set('bankgiro', 'archive', str(archive))
        config.config.set('bgwatcher', 'incoming', str(source))
        test = os.path.join(root, 'accounting', 'blm', 'test', 'LB',
                            'LBut-test_parseBankgiroResponse.txt')

        shutil.copy(test, source)

        process_bgcreport.process_file(self.database, str(source))

        bgcReport, = blm.accounting.BgcReport._query().run()
        assert bgcReport.filename == [sourcefn]

        # spool -> archive mv has moved to bgwatcher.py  # Test needs fixing
        #assert not os.path.exists(source)
        #assert os.path.exists(os.path.join(archive, sourcefn))
        #assert open(os.path.join(archive, sourcefn)).read() == open(test, 'r').read()
