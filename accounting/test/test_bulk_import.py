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
from pytransact.testsupport import BLMTests
import blm.accounting
from accounting.sie_import import SIEImporter, UnsupportedSIEVersion

def pytest_generate_tests(metafunc):
    # called once per each test function
    if metafunc.cls == TestBulkImport:
        funcarglist = metafunc.cls.params[metafunc.function.__name__]
        argnames = list(funcarglist[0])
        try:
            argnames.remove('__id__')
        except ValueError: pass
        ids=[funcargs.get('__id__', 'argname%s' % i)
                                  for (i, funcargs) in enumerate(funcarglist)]
        metafunc.parametrize(argnames, [[funcargs[name] for name in argnames]
                                        for funcargs in funcarglist],
                             ids = ids)



class TestBulkImport(BLMTests):

    here = os.path.dirname(__file__)

    # leave override empty to use all files in testdir, otherwise
    # enter files to test
    override = []
    testfiles = ['%s/sie/%s' % (here, f) for f in override] or \
                glob.glob('%s/sie/*' % here)
    params = {
        'test_import_sie': [{'filename': filename,
                             '__id__': os.path.basename(filename)}
                            for filename in testfiles]
        }

    def setup_method(self, method):
        super(TestBulkImport, self).setup_method(method)
        self.org = blm.accounting.Org()

    def test_import_sie(self, filename):
        start = time.time()
        print(time.ctime(start), repr(filename))
        importer = SIEImporter(org=[self.org])
        try:
            importer.parseFile(filename)
        except UnsupportedSIEVersion as exc:
            py.test.skip('Unsupported SIE version: %s' % exc.message)
        self.commit()

        # All objects should have been assigned an allowRead
        assert not blm.TO._query(allowRead=q.Empty()).run()
        assert not blm.TO._query(allowRead=q.NotIn(self.org.ug)).run()
        assert blm.TO._query(allowRead=self.org.ug).run()

        assert blm.accounting.Accounting._query().run() == [importer.accounting]

        print(repr(filename), 'took %s seconds' % (time.time() - start))
