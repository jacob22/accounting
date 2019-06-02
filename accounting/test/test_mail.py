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

try:
    import ConfigParser                 #py2
except ImportError:
    import configparser as ConfigParser #py3
    
import dkim
import email.message
import os

from accounting import config
from .. import mail, smtppipe
import codecs
try:
    unicode                     #py2
    py23txt = lambda t, c = 'us-ascii': t
    py23txtc = lambda t, c = 'us-ascii': t.encode(c)
    py23txtu = lambda t, c = 'us-ascii': unicode(t, c)
except NameError:               #py3
    py23txt = lambda t, c = 'us-ascii': str(t, c)
    py23txtc = lambda t, c = 'us-ascii': bytes(t,c)
    py23txtu = lambda t, c = 'us-ascii': t

class SMTP(object):

    local_hostname = 'test'
    _quit = False

    def __init__(self, *args, **kw):
        self._args = args
        self._kw = kw
        self._sendmail = []

    def sendmail(self, *args):
        self._sendmail.append(args)

    def quit(self):
        self._quit = True


class TestMail(object):

    def setup_method(self, method):
        self._smtp = smtppipe.SMTP
        smtppipe.SMTP = self.SMTP
        self.smtps = []
        self.orig_config = config.config
        self.config = config.save()
        config.config.set('accounting', 'smtp_domain', 'example.com')

    def teardown_method(self, method):
        smtppipe.SMTP = self._smtp
        config.restore(self.config)

    def SMTP(self, *args, **kw):
        smtp = SMTP(*args, **kw)
        self.smtps.append(smtp)
        return smtp

    def test_sendmail_dkim(self):
        config.config.set('accounting', 'dkim_privkey', os.path.join(
            os.path.dirname(__file__), 'dkim_test.private'))
        config.config.set('accounting', 'dkim_domain', 'example.org')
        config.config.set('accounting', 'smtp_domain', 'test.example.org')
        config.config.set('accounting', 'smtp_to_filter', '.*@example')

        pubkey = open(os.path.join(
            os.path.dirname(__file__), 'dkim_test.txt'),'rb').read()

        body = u'räksmörgås'
        subject = u'Räksmörgåsar!'
        to = u'"Mr. Räksmörgås" <foo@example>'

        fromaddr, all_rcpts, message = mail.makemail(
            body, subject=subject, to=to)

        mail.sendmail(fromaddr, all_rcpts, message)
        smtp, = self.smtps
        message = smtp._sendmail[0][2]

        assert dkim.verify(message, dnsfunc=lambda *_: pubkey)
        assert b'i=@test.example.org' in message

        fromaddr, all_rcpts, message = mail.makemail(
            body, subject=subject, to=to)

        mail.sendmail(fromaddr, all_rcpts, message, identity='foo')
        smtp = self.smtps[1]
        message = smtp._sendmail[0][2]

        assert dkim.verify(message, dnsfunc=lambda *_: pubkey)
        assert b'i=foo@test.example.org' in message

    def test_makemail(self):
        body = u'räksmörgås'
        subject = u'Räksmörgåsar!'
        to = u'"Mr. Räksmörgås" <foo@example>'

        args = mail.makemail(body, subject=subject, to=to)

        assert len(args) == 3
        assert args[:2] == ('<>', ['foo@example'])
        msg = args[2]

        assert 'foo@example' in msg
        # subject utf-8 and base64 encoded
        assert '=?utf-8?b?UsOka3Ntw7ZyZ8Olc2FyIQ==?=' in msg
        #assert msg.strip().endswith(py23txtc(body, 'utf-8').encode('base64').strip())
        assert msg.strip().endswith(py23txt(codecs.encode(py23txtc(body, 'utf-8'), 'base64').strip()))

    def test_makemail_bcc(self):
        body = u'räksmörgås'
        subject = u'Räksmörgåsar!'
        bcc = u'"Mr. Räksmörgås" <foo@example>'

        args = mail.makemail(body, envfrom='some@place',
                             subject=subject, bcc=bcc)

        assert len(args) == 3
        assert args[:2] == ('some@place', ['foo@example'])
        msg = args[2]
        assert 'foo@example' not in msg
        assert 'Bcc' in msg

    def test_makemail_envfrom(self):
        body = u'räksmörgås'
        subject = u'Räksmörgåsar!'
        to = u'"Mr. Räksmörgås" <foo@example>'
        _from = u'test@other'

        args = mail.makemail(body, envfrom='some@place', _from=_from,
                             subject=subject, to=to)

        assert len(args) == 3
        assert args[:2] == ('some@place', ['foo@example'])
        msg = args[2]
        #import pdb;pdb.set_trace()
        assert 'From: <test@other>' in msg
        #assert 'From:  <test@other>' in msg

    def test_address_filtering(self, monkeypatch):
        config.config.set('accounting', 'smtp_to_filter', '')
        log = []
        monkeypatch.setattr(mail.log, 'warn', lambda *args: log.append(args))
        mail.sendmail('from@test', ['to@test'], 'mail')
        assert self.smtps == []
        assert 'to@test' in log[0]

        log[:] = []

        config.config.set('accounting', 'smtp_to_filter', '.*@openend.se')
        mail.sendmail('from@test', ['to@test'], 'mail')
        assert self.smtps == []
        assert 'to@test' in log[0]

        log[:] = []

        msg = email.message.Message()
        msg['from'] = 'foo@test'
        config.config.set('accounting', 'smtp_to_filter', '.*')
        # xxx hack to make dkim signing work, since the dkim key is for
        # openend.se
        config.config.set('accounting', 'smtp_domain', 'admin.eutaxia.eu')
        mail.sendmail('from@test', ['to@test'], msg.as_string())
        args, = self.smtps[0]._sendmail
        assert args[:2] == ('from@test', ['to@test'])
        assert log == []

    def test_fromaddr_domain(self):
        config.config.set('accounting', 'dkim_privkey', os.path.join(
            os.path.dirname(__file__), 'dkim_test.private'))
        config.config.set('accounting', 'dkim_domain', 'example.org')
        config.config.set('accounting', 'smtp_domain', 'test.example.org')
        config.config.set('accounting', 'smtp_to_filter', '.*')

        msg = email.message.Message()
        msg['from'] = 'foo@test'
        mail.sendmail('from', ['to@test'], msg.as_string())
        args, = self.smtps[-1]._sendmail
        assert args[:2] == ('from@test.example.org', ['to@test'])

        msg = email.message.Message()
        msg['from'] = 'foo@test'
        mail.sendmail('from@bar', ['to@test'], msg.as_string())
        args, = self.smtps[-1]._sendmail
        assert args[:2] == ('from@bar', ['to@test'])

        msg = email.message.Message()
        msg['from'] = 'foo@test'
        mail.sendmail('<>', ['to@test'], msg.as_string())
        args, = self.smtps[-1]._sendmail
        assert args[:2] == ('<>', ['to@test'])

def test_makeAddressHeader():
    addrs = [(u'kalle anka', 'kalle@anka.se'),
             (u'foo@bar', 'foo@bar.com'),
             (u'<>foo,bar', 'foobar@baz.com'),
             (u'räksmörgås', 'raksmorgas@mat.se'),
             (u'電卓', 'dentaku@foo.org')]

    tohdr = mail.makeAddressHeader('To', addrs)

    try:
        unicode
        assert tohdr == 'kalle anka <kalle@anka.se>, "foo@bar" <foo@bar.com>, "<>foo,bar" <foobar@baz.com>,' \
                    ' =?iso-8859-1?q?r=E4ksm=F6rg=E5s?= <raksmorgas@mat.se>, =?utf-8?b?6Zu75Y2T?= <dentaku@foo.org>'
    except NameError:
        assert tohdr == 'kalle anka <kalle@anka.se>, "foo@bar" <foo@bar.com>, "<>foo,bar" <foobar@baz.com>,' \
                    ' =?utf-8?b?csOka3Ntw7ZyZ8Olcw==?= <raksmorgas@mat.se>, =?utf-8?b?6Zu75Y2T?= <dentaku@foo.org>'
