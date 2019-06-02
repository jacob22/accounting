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

import os, py, pyinotify, shutil, signal, subprocess, sys, tempfile, time
from accounting import config, mail
from .. import pgwatcher


class FakeEvent(object):

    dir = False
    mask = pyinotify.IN_CLOSE_WRITE
    maskname = pyinotify.EventsCodes.maskname(mask)
    wd = 1

    def __init__(self, pathname):
        self.pathname = pathname
        self.path = os.path.dirname(pathname)
        self.name = os.path.basename(pathname)


class TestPGWatcher(object):

    notifier = None
    term_handler = None

    def setup_method(self, method):
        self.tempdir = tempfile.mkdtemp()

    def teardown_method(self, method):
        if self.notifier:
            self.notifier.stop()
        if self.term_handler:
            signal.signal(signal.SIGTERM, term_handler)
        shutil.rmtree(self.tempdir)

    def test_process_file(self, monkeypatch):
        config.config.set('pgwatcher', 'spool', '/foo/spool')
        config.config.set('pgwatcher', 'processor', '/bin/processor.py')
        calls = []
        def move(src, dst):
            calls.append([src, dst])
        def check_call(args, **kw):
            calls.append((args, kw))

        monkeypatch.setattr(shutil, 'move', move)
        monkeypatch.setattr(subprocess, 'check_call', check_call)

        pgwatcher.process_file('/foo/bar/baz')

        assert len(calls) == 2

        src, dst = calls[0]
        assert src == '/foo/bar/baz'
        assert dst == '/foo/spool/baz'

        (cmd, arg), kw = calls[1]
        assert cmd == '/bin/processor.py'
        assert arg == '/foo/spool/baz'
        assert kw == dict(stdout=sys.stdout, stderr=sys.stderr)

    def test_process_file_fail(self, monkeypatch):
        config.config.set('pgwatcher', 'spool', '/foo/spool')
        config.config.set('pgwatcher', 'processor', '/bin/processor.py')
        calls = []
        def move(src, dst):
            calls.append([src, dst])
        def check_call(args, **kw):
            calls.append((args, kw))
            raise subprocess.CalledProcessError(1, 'whatever')
        def send_failure_mail(source):
            calls.append(('failure', source))

        monkeypatch.setattr(shutil, 'move', move)
        monkeypatch.setattr(subprocess, 'check_call', check_call)
        monkeypatch.setattr(pgwatcher, 'send_failure_mail', send_failure_mail)

        pgwatcher.process_file('/foo/bar/baz')

        assert len(calls) == 3
        assert calls[-1][0] == 'failure'
        assert '/foo/bar/baz' in calls[-1][1]

    def test_send_failure_mail(self, monkeypatch):
        config.config.set('pgwatcher', 'failure_mails', 'foo@test')
        calls = []
        def sendmail(fromaddr, all_recipients, data):
            calls.append((fromaddr, all_recipients, data))

        monkeypatch.setattr(mail, 'sendmail', sendmail)
        pgwatcher.send_failure_mail('/foo/bar/baz')

        (fromaddr, all_recipients, data), = calls
        assert all_recipients == ['foo@test']

    def test_check_spool(self, tmpdir, monkeypatch):
        spool = tmpdir.mkdir('spool')
        foo = spool.join('foo').ensure()
        bar = spool.join('bar').ensure()

        config.config.set('pgwatcher', 'spool', str(spool))

        calls = []
        monkeypatch.setattr(pgwatcher, 'send_failure_mail', calls.append)

        pgwatcher.check_spool()

        assert len(calls) == 1
        assert 'foo' in calls[0]
        assert 'bar' in calls[0]

    def test_check_directory(self, tmpdir, monkeypatch):
        incoming = tmpdir.mkdir('incoming')
        foo = incoming.join('foo').ensure()
        bar = incoming.join('bar').ensure()

        config.config.set('pgwatcher', 'incoming', str(incoming))

        calls = []
        monkeypatch.setattr(pgwatcher, 'process_file', calls.append)

        pgwatcher.check_directory()
        assert set(calls) == {str(foo), str(bar)}

    def test_handle_event(self, monkeypatch):
        calls = []
        monkeypatch.setattr(pgwatcher, 'process_file', calls.append)

        event = FakeEvent('/foo/bar/baz')
        pgwatcher.handle_event(event)
        assert calls == ['/foo/bar/baz']

    def test_setup_watcher(self, tmpdir):
        incoming = str(tmpdir.mkdir('incoming'))
        config.config.set('pgwatcher', 'incoming', incoming)

        watcher = pgwatcher.setup_watcher()

        files = []
        def callback(event):
            with open(event.pathname, 'r') as f:
                data = f.read()
            files.append(data)

        self.notifier = pyinotify.ThreadedNotifier(watcher, callback)
        self.notifier.start()

        with open(os.path.join(incoming, 'foo'), 'w') as f:
            f.write('foo')
            time.sleep(0.1)  # paranoia, make sure file isn't read too early
            f.write('bar')

        with open(os.path.join(incoming, 'bar'), 'w') as f:
            f.write('bar')
            time.sleep(0.1)
            f.write('foo')

        while len(files) < 2:
            time.sleep(0.01)

        foo, bar = files
        assert foo == 'foobar'
        assert bar == 'barfoo'

        self.notifier.stop()
        self.notifier = None

    def test_setup_notifier(self, monkeypatch):
        watcher = object()
        class Notifier(object):
            def __init__(self, *args):
                self.args = args
        monkeypatch.setattr(pyinotify, 'Notifier', Notifier)
        notifier = pgwatcher.setup_notifier(watcher)

        assert notifier.args == (watcher, pgwatcher.handle_event)

    def test_run(self):
        config.config.set('pgwatcher', 'pidfile', '/foo/bar/baz.pid')
        config.config.set('pgwatcher', 'watcherlog_base',
                          self.tempdir + '/watcher')
        class Notifier(object):
            def loop(self):
                self.called = True
        notifier = Notifier()
        pgwatcher.run(notifier)
        assert notifier.called
        os.path.exists(os.path.join(self.tempdir, 'watcher.log'))
        os.path.exists(os.path.join(self.tempdir, 'watcher.err'))

    def test_setup_term_handler(self):
        self.term_handler = pgwatcher.setup_term_handler()
        py.test.raises(SystemExit, os.kill, os.getpid(), signal.SIGTERM)

    def test_main(self, monkeypatch):
        watcher = object()
        notifier = object()

        calls = []
        def check_spool():
            calls.append('check_spool')
        def check_directory():
            calls.append('check_directory')
        def setup_watcher():
            calls.append('setup_watcher')
            return watcher
        def setup_notifier(arg):
            assert arg is watcher
            calls.append('setup_notifier')
            return notifier
        def setup_term_handler():
            calls.append('setup_term_handler')
        def run(arg):
            assert arg is notifier
            calls.append('run')

        monkeypatch.setattr(pgwatcher, 'check_spool', check_spool)
        monkeypatch.setattr(pgwatcher, 'check_directory', check_directory)
        monkeypatch.setattr(pgwatcher, 'setup_watcher', setup_watcher)
        monkeypatch.setattr(pgwatcher, 'setup_notifier', setup_notifier)
        monkeypatch.setattr(pgwatcher, 'setup_term_handler', setup_term_handler)
        monkeypatch.setattr(pgwatcher, 'run', run)

        pgwatcher.main()
        assert calls == ['check_spool', 'check_directory', 'setup_watcher',
                         'setup_notifier', 'setup_term_handler', 'run']
