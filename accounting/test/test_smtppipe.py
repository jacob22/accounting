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

from .. import smtppipe
try:
    from StringIO import StringIO             #py2
except ImportError:
    from io import StringIO    #py3
import py

class TestPipeSocket(object):
    def test_simple(self):
        rp = StringIO('teststring')
        wp = StringIO()

        ps = smtppipe.PipeSocket(rp, wp)

        assert ps.makefile() is ps

        ps.sendall('foo')

        assert wp.getvalue() == 'foo'

        line = ps.readline(4)

        assert line == 'test'
        line = ps.readline()
        assert line == 'string'

        ps.close()

        py.test.raises(ValueError, wp.tell)
        py.test.raises(ValueError, rp.tell)

class TestSMTP(object):
    def test_simple(self, monkeypatch):

        pipes = []
        readdata = [b'220-foo\n', b'220 bar\n']
        class FakePipe(object):
            def __init__(self, *a, **kw):
                self.readdata = iter(readdata)
                self.writedata = []
                pipes.append(self)
                self.stdin = self
                self.stdout = self
                self.args = (a, kw)

            def readline(self, size=-1):
                try:
                    return next(self.readdata)
                except StopIteration:
                    return ''

            def write(self, data):
                self.writedata.append(data)

            def close(self):
                pass

        monkeypatch.setattr(smtppipe.subprocess, 'Popen', FakePipe)

        sp = smtppipe.SMTP() #'/my/test/sendmail')

        assert not pipes

        code, msg = sp.connect()

        assert code == 220
        assert msg == b'foo\nbar'

        assert pipes[-1].args[0] == ('/usr/sbin/sendmail -bs',)

        sp = smtppipe.SMTP('/my/test/sendmail')
        assert pipes[-1].args[0] == ('/my/test/sendmail',)
