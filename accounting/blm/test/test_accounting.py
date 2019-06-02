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

import bson, email, py, os, time, uuid
from dateutil.relativedelta import relativedelta
from datetime import datetime, date, timedelta
from decimal import Decimal
try:
    from itertools import izip_longest                  #py2
except ImportError:
    from itertools import zip_longest as izip_longest   #py3
from pytransact import commit, contextbroker, exceptions, mongo, queryops
from pytransact.exceptions import ClientError
from pytransact.testsupport import BLMTests, Time
from pytransact.object import model
import pytransact.runtime as ri
from accounting import config, mail, sie_import
import blm
import OpenSSL.crypto
from accounting import luhn
import copy
import pytest
import random
import string
import codecs
from accounting import bankgiro, plusgiro

from accounting.test.blmsupport import PermissionTests
import sys
if sys.version_info <(3,0) :
    PYT3 = False                     #py2
    py23txtu = lambda t: unicode(t)
    py23txtuc = lambda t, c: unicode(t,c)
else:               #py3
    PYT3 =True
    py23txtu = lambda t: t
    py23txtuc = lambda t, c: str(t,c)

class TestRoles(BLMTests):

    roles = [ 'admins', 'accountants', 'storekeepers', 'ticketcheckers', 'members',
              'invoicesenders' ]

    def test_user(self):
        org = blm.accounting.Org()
        user = blm.accounting.User()

        assert not blm.accounting.currentUserHasRole(org, *self.roles, user=user)

        org.ug[0].users = [user]

        assert blm.accounting.currentUserHasRole(org, *self.roles, user=user)


    def test_apiuser(self):
        org = blm.accounting.Org()
        apiu = blm.accounting.APIUser()

        roles = ['admins', 'accountants', 'ticketcheckers', 'members', ]

        assert not blm.accounting.currentUserHasRole(org, *roles, user=apiu)

        org.ug[0].users = [apiu]

        assert not blm.accounting.currentUserHasRole(org, *roles, user=apiu)

        for role in ['invoicesenders', 'storekeepers']:
            assert blm.accounting.currentUserHasRole(org, role, user=apiu)

        apiu.roles = ['admins']
        assert blm.accounting.currentUserHasRole(org, 'admins', user=apiu)

        org2 = blm.accounting.Org()
        assert not blm.accounting.currentUserHasRole(org2, 'invoicesenders', user=apiu)


class TestClient(BLMTests):

    def test_create(self):
        client = blm.accounting.Client(name=['foo'])

    def test_relation(self):
        client = blm.accounting.Client()
        ug = blm.accounting.UG(users=[client])

    def test_stop_privilege_escalation(self):
        client = blm.accounting.Client()
        self.commit()
        self.ctx.setUser(client)
        py.test.raises(exceptions.ClientError, client, super=[True])

class TestUser(BLMTests):

    def test_create(self):
        user = blm.accounting.User(name=['foo'], emailAddress=['foo@example'])

    def test_relation(self):
        user = blm.accounting.User()
        ug = blm.accounting.UG(users=[user])

    def test_stop_privilege_escalation(self):
        user = blm.accounting.User()
        self.commit()
        self.ctx.setUser(user)
        py.test.raises(exceptions.ClientError, user, super=[True])

    def test_openid_permissions(self):
        user1 = blm.accounting.User()
        self.commit()
        user1 = blm.accounting.User._query(id=user1).run()[0]
        self.ctx.setUser(user1)
        user1(openid=['foo'])
        assert user1.openid == ['foo']

        user2 = blm.accounting.User()
        self.commit()
        self.ctx.setUser(user2)
        py.test.raises(ClientError, user1, openid=['bar'])


class TestAPIUser(BLMTests):

    def test_create(self):
        u = blm.accounting.APIUser()
        assert uuid.UUID(u.key[0])

    def test_newkey(self):
        u = blm.accounting.APIUser()
        key = u.key[0]

        u.newkey()
        assert u.key[0] != key

    def test_createAPIUser(self):
        org = blm.accounting.Org()
        key = blm.accounting.createAPIUser(org=[org])
        assert org.apikey == key

        with py.test.raises(exceptions.ClientError):
            # max one api user per org for now
            blm.accounting.createAPIUser(org=[org])


class TestInvitation(BLMTests):

    def test_create(self, monkeypatch):
        monkeypatch.setattr(mail, 'sendmail', lambda *a, **kw: None)
        org = blm.accounting.Org(name=['foo inc.'], orgnum=['123456-7890'])
        invite = blm.accounting.Invitation(org=[org], emailTo=['foo@bar.com'])

        assert invite.emailTo == ['foo@bar.com']
        assert invite.inviteCode[0]
        assert invite.org == [org]
        assert invite.accepted == [False]
        assert invite.groups

    def test_invite(self, monkeypatch):
        user = blm.accounting.User(name=[u'Gösta Bössa'], emailAddress=['foo@example'])
        config.config.set('accounting', 'smtp_domain', 'test')

        calls = []
        def makemail(body, **headers):
            calls.append((body, headers))
            return 1, 2, 3
        def sendmail(*args, **kw):
            assert args == (1, 2, 3)
            assert kw['identity'] == str(user.id[0])
            calls.append('sendmail')

        monkeypatch.setattr(mail, 'makemail', makemail)
        monkeypatch.setattr(mail, 'sendmail', sendmail)

        self.ctx.setUser(user)

        org = blm.accounting.Org(name=[u'Räksmörgåsar AB'], orgnum=['123456-7890'])
        result = org.invite(['bar@example.com'], ['storekeeper'])
        invite = blm.accounting.Invitation._query(org=org).run()
        assert result == invite
        assert len(invite) == 1
        assert invite[0].groups == ['storekeepers']

        (body, headers), sendmail = calls
        assert sendmail == 'sendmail'
        assert invite[0].inviteCode[0] in body
        assert headers['envfrom'] == str(org.id[0])
        if PYT3:
            # email.formataddr will convert (in blm.accounting.Invitation) to string values
            # suitable for RFC 2822 headers.
            # Thus we need to check against those strings.
            assert headers['Reply-to'] == '=?utf-8?b?R8O2c3RhIELDtnNzYQ==?= <foo@example>'
            assert headers['From'] == '=?utf-8?b?R8O2c3RhIELDtnNzYQ==?= <noreply@test>'
        else:
            assert headers['Reply-to'] == u'Gösta Bössa <foo@example>'
            assert headers['From'] == u'Gösta Bössa <noreply@test>'
        assert u'Räksmörgåsar AB' in body

    def test_accept(self, monkeypatch):
        monkeypatch.setattr(mail, 'sendmail', lambda *a, **kw: None)
        org = blm.accounting.Org(name=['ACME'])
        inv1 = blm.accounting.Invitation(org=[org], emailTo=['foo@example'],
                                         groups=['admins'])
        inv2 = blm.accounting.Invitation(org=[org], emailTo=['foo@example'],
                                         groups=['admins'])
        user1 = blm.accounting.User()

        for inv in inv1, inv2:
            for _ in range(2): # reentrant when called with same user
                inv.accept([user1])
                assert user1 in org.members
                assert user1 in org.admins
                assert inv.accepted == [True]
                assert inv.acceptedBy == [user1]
                assert org.ug[0] in user1.allowRead
                # When accepting multiple invitations to the same Org,
                # do not add org to user's UG more than once
                assert user1.ugs[:].count(org.ug[0]) == 1
                assert user1.allowRead[:].count(org.ug[0]) == 1

        # can't use invitation by other user, though
        user2 = blm.accounting.User()
        py.test.raises(exceptions.ClientError, inv.accept, [user2])


class TestPaymentProvider(BLMTests):

    def test_series_sanitation(self):
        org = blm.accounting.Org()
        ppd = blm.accounting.PaymentProvider(org=org, series=[''])
        assert ppd.series == []

        ppd = blm.accounting.PaymentProvider(org=org, series=['P'])
        assert ppd.series == ['P']

        ppd(series=[''])
        assert ppd.series == []

    def test_delete(self):
        import members
        import blm.members

        org = blm.accounting.Org()
        ppd1 = blm.accounting.PaymentProvider(org=org)
        ppd2 = blm.accounting.PaymentProvider(org=org)
        payment1 = blm.members.Payment(paymentProvider=ppd1)
        payment2 = blm.members.Payment(paymentProvider=ppd2)

        self.commit()

        ppd1, = blm.accounting.PaymentProvider._query(id=ppd1.id).run()
        ppd1._delete()

        self.commit()

        payments = blm.members.Payment._query().run()
        payments.sort(key=lambda toi: toi.id)
        assert payments[1].paymentProvider == [ppd2]
        assert payments[0].paymentProvider == []


class TestPlusgiroProvider(BLMTests):
    def test_require_subscriber(self):
        org = blm.accounting.Org()
        py.test.raises(ClientError, blm.accounting.PlusgiroProvider, org=org)

    def test_normalize_pgnum(self):
        org = blm.accounting.Org(subscriptionLevel=['subscriber'])
        ppd = blm.accounting.PlusgiroProvider(org=org, pgnum=['1234566'])
        assert ppd.pgnum == ['1234566']
        ppd(pgnum=['2345676'])
        assert ppd.pgnum == ['2345676']

        ppd = blm.accounting.PlusgiroProvider(org=org, pgnum=['123456-6'])
        assert ppd.pgnum == ['1234566']
        ppd(pgnum=['234567-6'])
        assert ppd.pgnum == ['2345676']

        ppd = blm.accounting.PlusgiroProvider(org=org, pgnum=['12 34 56 - 6'])
        assert ppd.pgnum == ['1234566']


class TestBankgiroProvider(BLMTests):
    def test_require_subscriber(self):
        org = blm.accounting.Org()
        py.test.raises(ClientError, blm.accounting.BankgiroProvider, org=org)

    def test_normalize_bgnum(self):
        org = blm.accounting.Org(subscriptionLevel=['subscriber'])
        ppd = blm.accounting.BankgiroProvider(org=org, bgnum=['1234566'])
        assert ppd.bgnum == ['1234566']
        ppd(bgnum=['2345676'])
        assert ppd.bgnum == ['2345676']

        ppd = blm.accounting.BankgiroProvider(org=org, bgnum=['123-4566'])
        assert ppd.bgnum == ['1234566']
        ppd(bgnum=['234-5676'])
        assert ppd.bgnum == ['2345676']

        ppd = blm.accounting.BankgiroProvider(org=org, bgnum=['123 - 4566'])
        assert ppd.bgnum == ['1234566']


class TestPaysonProvider(BLMTests):

    def test_create(self):
        org = blm.accounting.Org(subscriptionLevel=['subscriber'])
        blm.accounting.PaysonProvider(org=org, apiUserId=['foo'], apiPassword=['bar'], receiverEmail=['baz'])

    def test_require_subscriber(self):
        org = blm.accounting.Org()
        py.test.raises(ClientError, blm.accounting.PaysonProvider, org=org, apiUserId=['foo'], apiPassword=['bar'], receiverEmail=['baz'])


class TestSeqrProvider(BLMTests):

    def test_create(self):
        org = blm.accounting.Org(subscriptionLevel=['subscriber'])
        blm.accounting.SeqrProvider(org=org, principalId=['foo'], password=['bar'])

    def test_require_subscriber(self):
        org = blm.accounting.Org()
        py.test.raises(ClientError, blm.accounting.SeqrProvider,
                       org=org, principalId=['foo'], password=['bar'])


class TestStripeProvider(BLMTests):

    def test_create(self):
        org = blm.accounting.Org(subscriptionLevel=['subscriber'])
        blm.accounting.StripeProvider(org=org, access_token=['stripe'])

    def test_require_subscriber(self):
        org = blm.accounting.Org()
        py.test.raises(ClientError, blm.accounting.StripeProvider,
                       org=org, access_token=['foo'])


class TestSwishProvider(BLMTests):

    certs = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'test')

    cert = os.path.join(certs, 'swish.crt.pem')
    pkey = os.path.join(certs, 'swish.key.pem')

    def setup_method(self, method):
        super(TestSwishProvider, self).setup_method(method)
        self.org = blm.accounting.Org(subscriptionLevel=['subscriber'],
                                      name=[u'Räksmörgåsar AB'],
                                      email=[u'shrimps@example'],
                                      orgnum=['1234567890'])

    def test_create(self):
        with open(self.cert) as f:
            cert = f.read()
        with open(self.pkey) as f:
            pkey = f.read()
        provider = blm.accounting.SwishProvider(org=self.org,
                                                swish_id=self.org.orgnum,
                                                cert=cert, pkey=pkey)
        assert provider.cert[0] == cert
        assert provider.pkey[0] == pkey

    def test_normalize_id(self):
        provider = blm.accounting.SwishProvider(org=self.org,
                                                swish_id='123 339 93 26')
        assert provider.swish_id == ['1233399326']


    def test_create_with_automatic_pkey_generation(self):
        provider = blm.accounting.SwishProvider(org=self.org,
                                                swish_id=self.org.orgnum)

        assert OpenSSL.crypto.load_privatekey(OpenSSL.crypto.FILETYPE_PEM,
                                              provider.pkey[0])

    def test_use_test_pkey_with_test_id(self):
        provider = blm.accounting.SwishProvider(org=self.org,
                                                swish_id='1231181189')
        key = OpenSSL.crypto.load_privatekey(OpenSSL.crypto.FILETYPE_PEM,
                                             provider.pkey[0])
        pem = OpenSSL.crypto.dump_privatekey(OpenSSL.crypto.FILETYPE_PEM,
                                             key)
        with open(self.pkey) as f:
            test_key = OpenSSL.crypto.load_privatekey(
                OpenSSL.crypto.FILETYPE_PEM, f.read())
            test_pem = OpenSSL.crypto.dump_privatekey(
                OpenSSL.crypto.FILETYPE_PEM, test_key)
            assert pem == test_pem

    def test_cert_sanity_checking(self):
        provider = blm.accounting.SwishProvider(org=self.org,
                                                swish_id='1231181189')
        with open(self.cert) as f:
            provider(cert=[f.read()])  # don't explode

        py.test.raises(ClientError, provider, cert=['not a valid certificate'])

    def test_csr(self):
        provider = blm.accounting.SwishProvider(org=self.org,
                                                swish_id=self.org.orgnum)
        csr = OpenSSL.crypto.load_certificate_request(
            OpenSSL.crypto.FILETYPE_PEM, provider.csr[0])
        assert csr.get_subject().organizationName == u'Räksmörgåsar AB'
        assert csr.get_subject().emailAddress == u'shrimps@example'
        pkey = OpenSSL.crypto.load_privatekey(OpenSSL.crypto.FILETYPE_PEM,
                                              provider.pkey[0])
        if hasattr(OpenSSL.crypto, 'dump_publickey'):
            pems = [OpenSSL.crypto.dump_publickey(OpenSSL.crypto.FILETYPE_PEM, k)
                    for k in [csr.get_pubkey(), pkey]]
            assert pems[0] == pems[1]

    def test_require_subscriber(self):
        org = blm.accounting.Org()
        py.test.raises(ClientError, blm.accounting.SwishProvider,
                       org=org, swish_id=org.orgnum)

    def test_not_after(self):
        with open(self.cert) as f:
            provider = blm.accounting.SwishProvider(
                org=self.org, swish_id='1231181189', cert=[f.read()])
        assert provider.cert_expires == [1589438114]


class TestOrg(BLMTests):

    def test_create(self):
        user = blm.accounting.User()
        self.ctx.setUser(user)

        org = blm.accounting.Org(name=['foo inc.'], orgnum=['1234567890'])
        ug, = org.ug
        assert ug.users == [user]
        assert org.members == [user]
        assert org.orgnum == ['123456-7890']

    def test_members(self):
        client = blm.accounting.Client()
        apiuser = blm.accounting.APIUser()
        user = blm.accounting.User()

        org = blm.accounting.Org(name=['foo inc.'], orgnum=['1234567890'])
        org.ug[0].users = [client, user, apiuser]
        assert org.members == [user]

    def test_permissions(self):
        user = blm.accounting.User(name=['u1'])
        user2 = blm.accounting.User(name=['u2'])
        org = blm.accounting.Org()
        org.ug[0](users = [user, user2])

        assert org.permissions == []

        with ri.setuid(user):
            assert org.permissions == ['members']

        org.admins = [user]

        assert org.permissions == []

        userlist = [{
            'id': str(user.id[0]),
            'name': 'u1',
            'ugs': [str(ug.id[0]) for ug in user.ugs],
            'roles': ['admin', 'member']
            }, {
            'id': str(user2.id[0]),
            'name': 'u2',
            'ugs': [str(ug.id[0]) for ug in user2.ugs],
            'roles': ['member']
            }]
        for i in org.userpermissions:
            assert i in userlist

        with ri.setuid(user):
            assert set(org.permissions) == {'admins', 'members'}

    def test_updateMemberRoles(self):
        org = blm.accounting.Org()
        admin = blm.accounting.User(name=['admin'], ugs=org.ug)
        user1 = blm.accounting.User(name=['u1'], ugs=org.ug)
        user2 = blm.accounting.User(name=['u2'], ugs=org.ug)
        org.admins = [admin]
        self.commit()

        org, = blm.accounting.Org._query().run()
        assert set(org.members) == {admin, user1, user2}  # sanity

        with ri.setuid(admin):
            blm.accounting.updateMemberRoles(
                org=[org],
                roleData=[{'id': user1.id[0], 'roles': ['admin', 'accountant',
                                                        'payer',
                                                        'storekeeper',
                                                        'ticketchecker']},
                          {'id': user2.id[0], 'roles': ['member']}])
            self.commit()

        assert set(org.admins) == {admin, user1}
        assert set(org.members) == {admin, user1, user2}
        assert org.payers == [user1]
        assert org.accountants == [user1]
        assert org.storekeepers == [user1]
        assert org.ticketcheckers == [user1]
        assert set(org.members) == {admin, user1, user2}
        assert org.ticketchecker_ug[0].users == [user1]

        with ri.setuid(admin):
            py.test.raises(exceptions.ClientError, blm.accounting.updateMemberRoles,
                org=[org],
                roleData=[{'id': user1.id[0], 'roles': ['nosuchrole']}])

        with ri.setuid(user2):
            # only admins can change roles
            py.test.raises(exceptions.ClientError, blm.accounting.updateMemberRoles,
                org=[org],
                roleData=[{'id': user2.id[0], 'roles': ['admin']}])

        blm.accounting.updateMemberRoles(
            org=[org],
            roleData=[{'id': user1.id[0], 'roles': ['ticketchecker']}])
        assert user1 not in org.members
        assert user1 not in org.ug[0].users

        with py.test.raises(exceptions.ClientError):
            # must have at least one role
            blm.accounting.updateMemberRoles(
                org=[org],
                roleData=[{'id': user1.id[0], 'roles': []}])

        blm.accounting.updateMemberRoles(
            org=[org],
            roleData=[{'id': user1.id[0], 'roles': ['accountant']}])
        assert user1 in org.members

        with ri.setuid(admin):
            with py.test.raises(exceptions.ClientError):
                # at least one admin is required in an org
                blm.accounting.updateMemberRoles(
                    org=[org],
                    roleData=[{'id': admin.id[0], 'roles': ['member']}])


    def test_openend_ab_is_unique(self):
        blm.accounting.Org(name=['Open End'], orgnum=['556609-2473'])
        py.test.raises(exceptions.ClientError, blm.accounting.Org, name=['foo inc.'], orgnum=['556609-2473'])

        org2 = blm.accounting.Org(name=['foo inc.'], orgnum=['111111-1111'])
        py.test.raises(exceptions.ClientError, org2, orgnum=['556609-2473'])

    def test_datapropagation(self):
        org = blm.accounting.Org()
        acc_prev = blm.accounting.Accounting(org=[org], start=['2010-01-01'])
        acc_curr = blm.accounting.Accounting(org=[org], start=['2011-01-01'])

        assert org.current_accounting == [acc_curr]

        org(name=['foo inc.'])
        assert org.name == ['foo inc.'] # don't forget to invoke ._update()
        assert acc_curr.orgname == ['foo inc.']
        assert acc_prev.orgname == []

        org(orgnum=['123456-7890'])
        assert org.orgnum == ['123456-7890']
        assert acc_curr.orgnum == ['123456-7890']
        assert acc_prev.orgnum == []

    def test_subscribe(self):
        org = blm.accounting.Org()
        acc = blm.accounting.Accounting(org=org)
        blm.accounting.subscribe([org], ['subscriber'])
        assert org.subscriptionLevel == ['subscriber']

        # 'pg' level is deprecated
        #blm.accounting.subscribe([org], ['pg'])
        #assert org.subscriptionLevel == ['subscriber', 'pg']

    def test_get_ocr(self, monkeypatch):
        year = '2013'
        def strftime(s):
            assert s == '%Y'
            return year
        monkeypatch.setattr(time, 'strftime', strftime)

        org = blm.accounting.Org()
        assert org.ocrYearReset == [3]
        assert org.ocrCounter == [1]
        ocr, = org.get_ocr()
        assert ocr == '10355'
        assert org.ocrCounter == [2]

        ocr, = org.get_ocr()
        assert ocr == '11353'

        year = '2014'
        ocr, = org.get_ocr()
        assert ocr == '10454'
        assert org.ocrYearReset == [4]
        assert org.ocrCounter == [2]

    def test_get_ocr_rapidly(self):
        org = blm.accounting.Org()
        self.commit()

        pids = []

        parallel = 20

        for i in range(parallel):
            pid = os.fork()
            if not pid:
                try:
                    self.pushnewctx()
                    op = commit.CallToi(org.id[0], 'get_ocr', [])
                    interested = str(i)
                    self.ctx.runCommit([op], interested=interested)
                    result, error = commit.wait_for_commit(self.database,
                                                           interested)
                    print(result)
                finally:
                    os._exit(0)
            else:
                pids.append(pid)

        for pid in pids:
            os.waitpid(pid, 0)

        self.sync()
        org._clear()
        assert org.ocrCounter == [1 + parallel]

    def test_removeMembers(self):
        org = blm.accounting.Org(name=['foo inc.'], orgnum=['1234567890'])

        user1 = blm.accounting.User(name=['user1'], ugs=org.ug)
        user2 = blm.accounting.User(name=['user2'], ugs=org.ug)
        org.admins = [user1, user2]
        self.commit()

        hacker = blm.accounting.User(name=['hacker'])
        self.ctx.setUser(hacker)

        # can't modify orgs we're not a member of
        py.test.raises(ClientError, blm.accounting.removeMembers, [org], [user1])

        self.ctx.setUser(user2)
        org, = blm.accounting.Org._query(id=org.id[0]).run()

        user1, = blm.accounting.User._query(name='user1').run()
        user2, = blm.accounting.User._query(name='user2').run()

        result = blm.accounting.removeMembers([org], [user1])
        assert len(result)
        assert result == org.userpermissions
        assert org.ug[0].users == [user2]
        assert user1 not in org.admins

        # can't remove the last member
        py.test.raises(ClientError, blm.accounting.removeMembers, [org], [user2])

        user3 = blm.accounting.User(name=['user3'], ugs=org.ug)
        org.admins.append(user3)
        result = blm.accounting.removeMembers([org], [user2])
        assert result == []  # Empty when removing self
        assert len(org.userpermissions)

    def test_manual_payment_provider(self):
        org = blm.accounting.Org()
        mpp = org.get_manual_payment_provider()
        assert [mpp] == org.manual_payment_provider

        mpp2 = org.get_manual_payment_provider()
        assert [mpp2] == org.manual_payment_provider
        assert mpp is mpp2


class TestOrgRemoval(BLMTests):

    day = 3600 * 24
    week = day * 7

    def setup_method(self, method):
        super(TestOrgRemoval, self).setup_method(method)
        self.org = blm.accounting.Org(created=0)

    def test_expireTrialOrgs(self):
        with Time(0) as time:
            time += self.day * 100
            blm.accounting.expireTrialOrg([self.org])

        with Time(0) as first_warning:
            first_warning += self.org.TRIAL_PERIOD - (
                self.org.TRIAL_WARNING_INTERVAL *
                self.org.TRIAL_WARNING_COUNT) + 1
            blm.accounting.expireTrialOrg([self.org])
            assert self.org.removalWarnings == [first_warning]

        with Time(0) as second_warning:
            second_warning += self.org.TRIAL_PERIOD - 1
            blm.accounting.expireTrialOrg([self.org])
            assert self.org.removalWarnings == [first_warning, second_warning]

        with Time(0) as time:
            time += self.org.TRIAL_PERIOD + self.day * 6
            blm.accounting.expireTrialOrg([self.org])
            assert self.org.removalWarnings == [first_warning, second_warning]

        with Time(0) as time:
            time += self.org.TRIAL_PERIOD + self.day * 7 + 1
            blm.accounting.expireTrialOrg([self.org])
            assert self.org._deleted

    def test_disable_org(self):
        self.org.subscriptionLevel = ['subscriber']
        user = blm.accounting.User(name=['u1'], ugs=self.org.ug)
        self.commit()

        org, = blm.accounting.Org._query().run()
        assert org.subscriptionLevel == ['subscriber']  # sanity
        assert len(org.ug[0].users) == 1  # sanity

        org.disable()
        assert org.subscriptionLevel == []
        assert len(org.ug[0].users) == 0


class TestPGOrder(BLMTests):

    def test_create(self):
        user = blm.accounting.User()
        self.ctx.setUser(user)
        org = blm.accounting.Org()
        pgorder = blm.accounting.PGOrder(
            org=[org],
            contact=['Mr. Foo'],
            contactPhone=['1234567'],
            contactEmail=['foo@example'],
            pgnum=['12345-6'])

        assert pgorder.createdBy == [user]

    def test_orderPG(self):
        user = blm.accounting.User()
        self.ctx.setUser(user)

        org = blm.accounting.Org()
        self.commit()

        org, = blm.accounting.Org._query().run()
        py.test.raises(ClientError, blm.accounting.orderPG, [org], ['Mr. Foo'],
                       ['1234566'], ['foo@example'],
                       ['12345-5'], ['1000'], ['B'])
        self.commit()

        org, = blm.accounting.Org._query().run()
        org.subscriptionLevel = ['subscriber']
        blm.accounting.orderPG([org], ['Mr. Foo'], ['1234566'], ['foo@example'],
                               ['12345-5'], ['1000'], ['B'])
        self.commit()

        org, = blm.accounting.Org._query().run()
        pgorder, =  blm.accounting.PGOrder._query().run()

        assert pgorder.org == [org]
        assert pgorder.contact == ['Mr. Foo']
        assert pgorder.contactPhone == ['1234566']
        assert pgorder.contactEmail == ['foo@example']
        assert pgorder.pgnum == ['12345-5']

        pg, = blm.accounting.PlusgiroProvider._query(org=org).run()

        assert pg.account == ['1000']
        assert pg.series == ['B']
        assert pg.pgnum == []
        assert pg.pgnum_real == ['123455']

    def test_send(self, monkeypatch):
        config.config.set('plusgiro', 'setup_email_from', 'bounce@test')
        config.config.set('plusgiro', 'setup_email_to', 'plusgiro@test, cc@test')
        calls = []
        def sendmail(*args):
            calls.append(args)
        monkeypatch.setattr(mail, 'sendmail', sendmail)

        org = blm.accounting.Org(
            orgnum=['223344-6677']
            )
        pgorder = blm.accounting.PGOrder(
            org=[org],
            contact=['Mr. Foo'],
            contactPhone=['1234567'],
            contactEmail=['foo@example'],
            pgnum=['12345-6'])

        pgorder.send()
        assert pgorder.sent == [True]
        (fromaddr, all_recipients, body), = calls

        assert fromaddr == 'bounce@test'
        assert all_recipients == ['plusgiro@test', 'cc@test']
        print(body)
        assert '\nTo: <plusgiro@test>, <cc@test>\n' in body
        assert '\nFrom: <bounce@test>\n' in body
        msg = email.message_from_string(body)
        body = msg.get_payload(decode=True)
        if PYT3:
            body = body.decode()
        assert '223344-6677' in body
        assert 'foo@example' in body

    def test_send_sent(self, monkeypatch):
        #TODO:  visar
        org = blm.accounting.Org()
        pgorder = blm.accounting.PGOrder(
            org=[org],
            contact=['Mr. Foo'],
            contactPhone=['1234567'],
            contactEmail=['foo@example'],
            pgnum=['12345-6'],
            sent=[True])

        calls = []
        def sendmail(*args):
            calls.append(args)
        monkeypatch.setattr(mail, 'sendmail', sendmail)

        pgorder.send()
        assert calls == []


class TestCurrentAccounting(BLMTests):

    def setup_method(self, method):
        super(TestCurrentAccounting, self).setup_method(method)
        self.org = blm.accounting.Org()

    def test_empty(self):
        assert self.org.current_accounting == []

    def test_set_one(self):
        accounting = blm.accounting.Accounting(org=self.org)
        assert self.org.current_accounting == [accounting]

    def test_multiple_ascending(self):
        accounting2010 = blm.accounting.Accounting(org=self.org,
                                                   start='2010-01-01')
        assert self.org.current_accounting == [accounting2010]

        accounting2011 = blm.accounting.Accounting(org=self.org,
                                                   start='2011-01-01')
        assert self.org.current_accounting == [accounting2011]

        accounting2012 = blm.accounting.Accounting(org=self.org,
                                                   start='2012-01-01')
        assert self.org.current_accounting == [accounting2012]

    def test_multiple_descending(self):
        accounting2012 = blm.accounting.Accounting(org=self.org,
                                                   start='2012-01-01')
        assert self.org.current_accounting == [accounting2012]

        accounting2011 = blm.accounting.Accounting(org=self.org,
                                                   start='2011-01-01')
        assert self.org.current_accounting == [accounting2012]

        accounting2010 = blm.accounting.Accounting(org=self.org,
                                                   start='2010-01-01')
        assert self.org.current_accounting == [accounting2012]

    def test_delete(self):
        accounting2010 = blm.accounting.Accounting(org=self.org,
                                                   start='2010-01-01')
        assert self.org.current_accounting == [accounting2010]

        accounting2011 = blm.accounting.Accounting(org=self.org,
                                                   start='2011-01-01')
        assert self.org.current_accounting == [accounting2011]
        self.commit()

        self.org, = blm.TO._query(id=self.org.id).run()
        accounting2011, = blm.TO._query(id=accounting2011.id).run()
        accounting2011._delete()

        assert self.org.current_accounting == [accounting2010]

    def test_start_year_edited(self):
        accounting2010 = blm.accounting.Accounting(org=self.org,
                                                   start='2010-01-01')
        assert self.org.current_accounting == [accounting2010]

        accounting2011 = blm.accounting.Accounting(org=self.org,
                                                   start='2011-01-01')
        assert self.org.current_accounting == [accounting2011]

        self.commit()
        accounting2010, = blm.TO._query(id=accounting2010.id).run()
        accounting2010(start=['2012-01-01'])
        self.org.current_accounting == [accounting2010]


class TestAccounting(BLMTests):

    def test_create(self):
        acc = blm.accounting.Accounting()

        dimensions = blm.accounting.Dimension._query(accounting=acc).run()
        assert len(dimensions) == 7

        proj, = blm.accounting.Dimension._query(name=['Projekt']).run()
        assert proj.project[0]  # automatically set to project dimension

        assert acc.accounting == [acc]
        assert acc.years['0'] == [acc.start[0], acc.end[0]]

    def test_name(self):
        acc = blm.accounting.Accounting()

        acc(start=['2010-01-01'], end=['2010-12-31'])
        assert acc.name == ['2010-01-01 - 2010-12-31']

    def test_org(self):
        org = blm.accounting.Org(name=['foo'], orgnum=['123456-7890'])
        acc = blm.accounting.Accounting(org=[org])

        assert acc.orgname == ['foo']
        assert acc.orgnum == ['123456-7890']

    def test_accountingImport(self):
        org = blm.accounting.Org()
        data = model.BlobVal(open(os.path.join(os.path.dirname(__file__),
                                               'accountingImport.si')))
        acc, = blm.accounting.accountingImport(org=[org], data=[data])
        assert acc.orgnum == ['555555-5555']

    def test_start_end(self):
        org = blm.accounting.Org(name=['foo'], orgnum=['bar'])
        acc = blm.accounting.Accounting(org=[org])

        assert acc.start == [time.strftime('%Y-%m-%d')]
        assert acc.end == [(datetime.now() + relativedelta(
            years=+1, days=-1)).strftime('%Y-%m-%d')]

        acc2 = blm.accounting.Accounting(org=[org])

        assert acc2.start == [(datetime.now() + relativedelta(
            years=+1)).strftime('%Y-%m-%d')]
        assert acc2.end == [(datetime.now() + relativedelta(
            years=+2, days=-1)).strftime('%Y-%m-%d')]

    def test_previous(self):
        org = blm.accounting.Org()
        acc1 = blm.accounting.Accounting(
            org=[org], start=['2009-01-01'], end=['2009-12-31'])
        acc2 = blm.accounting.Accounting(
            org=[org], start=['2010-01-01'], end=['2010-12-31'])
        acc3 = blm.accounting.Accounting(
            org=[org], start=['2011-01-01'], end=['2011-12-31'])

        assert acc1.previous == []
        assert acc2.previous == [acc1]
        assert acc3.previous == [acc2]

    def mkAccount(self, accounting, number, **kw):
        kw.setdefault('name', 'Account %s' % number)
        return blm.accounting.Account(number=[number], accounting=[accounting],
                                      **kw)

    def test_initialise(self):
        org = blm.accounting.Org()
        prev = blm.accounting.Accounting(
            org=[org], start=['2009-01-01'], end=['2009-12-31'])
        acc = self.mkAccount(prev, '1000', name=u'Tillgång 1', type='T', opening_balance='10')
        assert acc.balance == [Decimal('10.00')] # sanity
        acc = self.mkAccount(prev, '1001', name=u'Tillgång 2', type='T', opening_balance='11')
        acc = self.mkAccount(prev, '2000', name=u'Skuld 1', type='S', opening_balance='27')
        assert acc.balance == [Decimal('27.00')] # sanity
        acc = self.mkAccount(prev, '3000', name=u'Intäkt 1', type='I', opening_balance='10')
        assert acc.balance == [Decimal('10.00')] # sanity
        acc = self.mkAccount(prev, '4000', name=u'Kostnad 1', type='K', opening_balance='10')
        assert acc.balance == [Decimal('10.00')] # sanity

        curr = blm.accounting.Accounting(
            org=[org], start=['2010-01-01'], end=['2010-12-31'])
        acc = self.mkAccount(curr, '1000', name=u'Tillgång new name', opening_balance='12')
        ser = blm.accounting.VerificationSeries(accounting=curr, name=['A'])
        ver = blm.accounting.Verification(accounting=curr, series=ser)
        blm.accounting.Transaction(verification=ver, account=acc, version=[0], amount='5')

        curr.initialise()

        accounts = blm.accounting.Account._query(accounting=curr).run()
        accounts = dict((toi.number[0], toi) for toi in accounts)

        assert len(accounts) == 5
        assert accounts['1000'].name == [u'Tillgång new name']
        assert accounts['1000'].opening_balance == [Decimal('10')]
        assert accounts['1000'].balance == [Decimal('15')]
        assert accounts['1001'].name == [u'Tillgång 2']
        assert accounts['1001'].opening_balance == [Decimal('11')]
        assert accounts['1001'].balance == [Decimal('11')]
        assert accounts['2000'].name == [u'Skuld 1']
        assert accounts['2000'].opening_balance == [Decimal('27')]
        assert accounts['2000'].balance == [Decimal('27')]
        assert accounts['3000'].balance == [Decimal(0)]
        assert accounts['4000'].balance == [Decimal(0)]

    def test_ensureSeries(self):
        org = blm.accounting.Org()
        acc = blm.accounting.Accounting(org=org)

        a, = acc.ensureSeries()
        assert a.name == ['A']

        assert not acc.ensureSeries()
        assert blm.accounting.VerificationSeries._query().run() == [a]

        blm.accounting.PaymentProvider(org=org, series=['X']) # runs ensureSeries()
        x, = blm.accounting.VerificationSeries._query(name='X').run()

        assert not acc.ensureSeries()

        blm.accounting.PaymentProvider(org=org, series=['X'])
        assert not acc.ensureSeries()

        series = blm.accounting.VerificationSeries._query().run()
        series.sort(key=lambda toi: toi.name[0])

        assert series == [a, x]

        org = blm.accounting.Org()
        acc = blm.accounting.Accounting(org=org)
        b = blm.accounting.VerificationSeries(accounting=acc, name='B')
        assert not acc.ensureSeries()
        series = blm.accounting.VerificationSeries._query(
            accounting=acc).run()
        assert series == [b]


class TestAccountingObject(BLMTests):

    def test_create(self):
        acc = blm.accounting.Accounting()
        dim = blm.accounting.Dimension(number=['27'], name=['Customer'],
                                       accounting=[acc])
        blm.accounting.AccountingObject(number=['27'], name=['Nisse'],
                                        dimension=[dim])


class TestDimension(BLMTests):

    def setup_method(self, method):
        super(TestDimension, self).setup_method(method)
        self.accounting = blm.accounting.Accounting()

    def test_create(self):
        blm.accounting.Dimension(number=['27'], name=['Customer'],
                                 accounting=[self.accounting])

    def test_hierarchy(self):
        parent = blm.accounting.Dimension(number=['27'], name=['Customer'],
                                          accounting=[self.accounting])
        child = blm.accounting.Dimension(number=['28'], name=['Customer'],
                                         subdim_of=[parent],
                                         accounting=[self.accounting])

    def test_project_hierarchy(self):
        parent = blm.accounting.Dimension(number=['27'], name=['Customer'],
                                          project=[True],
                                          accounting=[self.accounting])
        child = blm.accounting.Dimension(number=['28'], name=['Customer'],
                                         subdim_of=[parent],
                                         accounting=[self.accounting])
        assert child.project[0]


def account_default_type_test(toc, **kw):
    acc = toc(number=['1234'], **kw)

    assert acc.type == ['T']  # account no starts with 1

    acc = toc(number=['2345'], **kw)
    assert acc.type == ['S']  # account no starts with 2

    acc = toc(number=['3456'], **kw)
    assert acc.type == ['I']  # account no starts with 3

    for n in '4567':
        acc = toc(number=[n + '999'], **kw)
        assert acc.type == ['K']  # account no starts with 4567

    acc = toc(number=['3456'], type=['T'], **kw)
    assert acc.type == ['T']  # don't overwrite with default type


class TestBaseAccount(BLMTests):
    def setup_method(self, method):
        super(TestBaseAccount, self).setup_method(method)

    def test_create(self):
        acc = blm.accounting.BaseAccount(number=['1234'])
        assert acc.name == ['* UNNAMED *']

    def test_default_type(self):
        account_default_type_test(blm.accounting.BaseAccount)

class TestAccountTemplate(BLMTests):

    def test_default_type(self):
        account_default_type_test(blm.accounting.AccountTemplate)

    def test_root_only(self):
        user = blm.accounting.User()
        template = blm.accounting.AccountTemplate(number=['1111'],
                                                  allowRead=[user])
        self.commit()
        template._clear()

        self.ctx.setUser(user)
        with py.test.raises(ClientError):
            blm.accounting.AccountTemplate(number=['2222'])

        self.ctx.setUser(user)
        with py.test.raises(ClientError):
            template(name=['foo'])

        self.ctx.setUser(None)
        template(name=['foo'])


class TestChartOfAccounts(BLMTests):
    def test_simple(self):
        coa = blm.accounting.ChartOfAccounts(name=['test'])

        assert coa.name == ['test']

    def mkChartOfAccounts(self):
        accts = []
        for i in range(1,10):
            accts.append(blm.accounting.AccountTemplate(
                    name=['acct %d' % i],
                    number=[str(1111 * i)]
                    ))
        coa = blm.accounting.ChartOfAccounts(
                    name=['test'],
                    accounts=accts
                    )
        return coa, accts

    def test_populate(self):
        coa, accts = self.mkChartOfAccounts()
        accounting = blm.accounting.Accounting()

        accounts = coa.populate([accounting])
        assert len(accounts) == len(accts)
        assert accounts[0] != accts[0]
        assert type(accounts[0]) == blm.accounting.Account
        accname = sorted((a.name[0], a.number[0]) for a in accounts)
        expname = sorted((a.name[0], a.number[0]) for a in accts)

        assert accname == expname

    def test_accountingFromTemplate(self):
        coa, accts = self.mkChartOfAccounts()
        org = blm.accounting.Org()

        accounting, = blm.accounting.accountingFromTemplate([coa], [org])
        assert accounting.org == [org]

        accounts = blm.accounting.Account._query(accounting=accounting).run()
        assert len(accounts) == len(accts)

        series = blm.accounting.VerificationSeries._query(
            accounting=accounting).run()
        assert len(series) == 1
        assert series[0].name == ['A']

    def test_root_only(self):
        user = blm.accounting.User()
        coa = blm.accounting.ChartOfAccounts(name=['The chart!'],
                                             allowRead=[user])
        self.commit()
        coa._clear()

        self.ctx.setUser(user)
        with py.test.raises(ClientError):
            blm.accounting.ChartOfAccounts(name=['Fake chart'])

        self.ctx.setUser(user)
        with py.test.raises(ClientError):
            coa(name=['foo'])

        self.ctx.setUser(None)
        coa(name=['foo'])


class TestAccount(BLMTests):

    def setup_method(self, method):
        super(TestAccount, self).setup_method(method)
        self.accounting = blm.accounting.Accounting()
        self.series = blm.accounting.VerificationSeries(
            accounting=[self.accounting], name=['A'])
        self.ver = blm.accounting.Verification(
            series=[self.series], number=['1'], accounting=[self.accounting])

    def test_create(self):
        acc = blm.accounting.Account(number=['1234'],
                                     accounting=[self.accounting])
        assert acc.name == ['* UNNAMED *']

    def test_default_type(self):
        account_default_type_test(blm.accounting.Account, accounting=[self.accounting])

    def test_vat_percentage(self):
        blm.accounting.VatCode(code='10', xmlCode='gorp')  # 25%
        blm.accounting.VatCode(code='11', xmlCode='gorp')  # 12%
        acc = blm.accounting.Account(number=['1234'],
                                     accounting=[self.accounting],
                                     vatCode=['10'])
        self.commit()
        acc, = blm.accounting.Account._query().run()
        assert acc.vatPercentage == [Decimal('25.00')]

        acc(vatCode='11')
        assert acc.vatPercentage == [Decimal('12.00')]

    def test_balance(self):
        account = blm.accounting.Account(number=['1234'],
                                         opening_balance=['42.00'],
                                         opening_quantity=['10'],
                                         accounting=[self.accounting])
        assert account.balance == [Decimal('42.00')]

        account.transactions = [
            blm.accounting.Transaction(verification=[self.ver], account=[account],
                                       version=self.ver.version,
                                       amount=['10.00'],
                                       quantity=['5']),
            blm.accounting.Transaction(verification=[self.ver], account=[account],
                                       version=self.ver.version,
                                       amount=['-5.00'], quantity=['-2'])
            ]
        assert account.balance == [Decimal('47.00')] # 42 + 10 - 5
        assert account.balance_quantity == [Decimal('13')] # 10 + 5 - 2

    def test_recalc_balance_when_opening_balance_changes(self):
        account = blm.accounting.Account(number=['1234'],
                                         opening_balance=['0.00'],
                                         opening_quantity=['0'],
                                         accounting=[self.accounting])
        account.transactions = [
            blm.accounting.Transaction(verification=[self.ver], account=[account],
                                       version=self.ver.version,
                                       amount=['10.00'],
                                       quantity=['5']),
        ]
        self.commit()

        account, = blm.accounting.Account._query().run()
        account(opening_balance=['5.00'])
        assert account.balance == [Decimal('15.00')]

    def test_fromtemplate(self, monkeypatch):
        accounting = blm.accounting.Accounting()
        acc = blm.accounting.BaseAccount(number=['1234'])
        accft = blm.accounting.Account.fromtemplate(acc, accounting=[accounting])
        assert accft is not acc
        assert accft.number == ['1234']
        assert accft.accounting == [accounting]


class TestVerificationSeries(BLMTests):

    def test_name_unique(self):
        acc1 = blm.accounting.Accounting()
        acc2 = blm.accounting.Accounting()
        vs1 = blm.accounting.VerificationSeries(name=['A'], accounting=[acc1])
        vs2 = blm.accounting.VerificationSeries(name=['B'], accounting=[acc1])

        py.test.raises(ClientError, blm.accounting.VerificationSeries,
                       name=['A'], accounting=[acc1])

        vs3 = blm.accounting.VerificationSeries(name=['A'], accounting=[acc2])

        vs2(name=['C'])

        py.test.raises(ClientError, vs2, name=['A'])

    def test_pgseries_undeletable(self):
        org = blm.accounting.Org()
        acc = blm.accounting.Accounting(org=org)
        ser = blm.accounting.VerificationSeries(name=['A'], accounting=[acc])
        pp = blm.accounting.PaymentProvider(org=org, series=['A'])
        py.test.raises(ClientError, ser._delete)

        pp.series = ['B']
        ser._delete()
        assert ser._deleted

        ser = blm.accounting.VerificationSeries(name=['B'], accounting=[acc])
        acc._delete()
        assert ser._deleted

    def test_next_verification_data(self):
        acc = blm.accounting.Accounting(start=['2010-01-01'])
        accid = acc.id[0]
        series = blm.accounting.VerificationSeries(name=['A'], accounting=[acc])

        result = blm.accounting.next_verification_data([series])
        assert result == {
            'accounting': accid,
            'number': 1,
            'transaction_date': '2010-01-01'
            }

        blm.accounting.Verification(accounting=[acc], series=[series],
                                    number=[1], transaction_date=['2010-01-04'])

        result = blm.accounting.next_verification_data([series])
        assert result == {
            'accounting': accid,
            'number': 2,
            'transaction_date': '2010-01-04'
            }

        blm.accounting.Verification(accounting=[acc], series=[series],
                                    number=[27], transaction_date=['2011-03-14'])
        result = blm.accounting.next_verification_data([series])
        assert result == {
            'accounting': accid,
            'number': 28,
            'transaction_date': '2011-03-14'
            }


class TestVerification(BLMTests):

    def setup_method(self, method):
        super(TestVerification, self).setup_method(method)
        self.user = blm.accounting.User(name=['Bosse Bagare'])
        self.ctx.setUser(self.user)

        self.org = blm.accounting.Org(accountants=[self.user])
        self.ppd = blm.accounting.PaymentProvider(org=self.org, account=['1000'], series=['A'])
        self.accounting = blm.accounting.Accounting(org=self.org)
        self.series, = blm.accounting.VerificationSeries._query().run()
        self.account = blm.accounting.Account(
            accounting=self.accounting, number=['1000'])

    def mkVerification(self, **kw):
        kw.setdefault('series', self.series)
        kw.setdefault('accounting', self.accounting)
        return blm.accounting.Verification(**kw)

    def test_create(self):
        ver = self.mkVerification()
        assert ver.number == [1] # default to 1
        assert ver.transaction_date == [time.strftime('%Y-%m-%d')]
        assert ver.registration_date == [time.strftime('%Y-%m-%d')]
        assert ver.signature == [str(i) for i in self.user.id]  # map(str, self.user.id)
        assert ver.signature_name == self.user.name
        assert ver.series == [self.series]
        assert self.series.canBeDeleted == [False]

        # badly formatted transaction date
        py.test.raises(exceptions.ClientError, blm.accounting.Verification,
                       series=[self.series], accounting=[self.accounting],
                       transaction_date=['foo'])

        # badly formatted registration date
        py.test.raises(exceptions.ClientError, blm.accounting.Verification,
                       series=[self.series], accounting=[self.accounting],
                       registration_date=['foo'])

        # number should be a positive integer
        py.test.raises(exceptions.ClientError, blm.accounting.Verification,
                       series=[self.series], accounting=[self.accounting],
                       number=[0])

        # number conflict within the series
        py.test.raises(exceptions.ClientError, blm.accounting.Verification,
                       series=[self.series], accounting=[self.accounting],
                       number=[1])

    def test_update_signature_and_regdate(self):
        newUser = blm.accounting.User(name=['Förnamn Efternamn'])
        self.org.accountants.add(newUser)
        self.accounting.allowRead = self.accounting.allowRead + [newUser]
        self.mkVerification()
        self.commit()
        ver, = blm.accounting.Verification._query().run()
        orig_date = ver.registration_date[0]
        self.ctx.setUser(newUser)

        with Time() as time:
            time += 3600 * 24 * 2 # a new date
            ver(text=['foo']) # provoke a change

            assert ver.signature == [str(i) for i in newUser.id]  # map(str, newUser.id)
            assert ver.signature_name == newUser.name
            assert ver.registration_date[0] != orig_date
            assert ver.registration_date == [time.strftime('%Y-%m-%d')]


    def test_block_changes(self):
        self.mkVerification()
        self.commit()
        ver, = blm.accounting.Verification._query().run()

        series2 = blm.accounting.VerificationSeries(
            accounting=self.accounting, name='B')

        py.test.raises(exceptions.ClientError, ver, number=[12])
        py.test.raises(exceptions.ClientError, ver, series=[series2])

    def test_saveVerification(self):
        data = {
            'verification': {'accounting': str(self.accounting.id[0]),
                             'series': str(self.series.id[0]),
                             'number': 1,
                             'transaction_date': '2010-01-01'},

            'transactions': [
                {'account': str(self.account.id[0]),
                 'amount': 10000,
                 'text': 'Transaction text',
                 'version': 0},
                {'account': str(self.account.id[0]),
                 'amount': -10000,
                 'text': 'Transaction text 2',
                 'version': 0}
                ]
            }
        result, = blm.accounting.createVerification([data])
        ver, = blm.accounting.Verification._query().run()
        assert result['number'] == ver.number[0] == 1
        assert result['id'] == ver.id[0]
        assert ver.transaction_date == ['2010-01-01']

        trans1, = blm.accounting.Transaction._query(text='Transaction text').run()
        assert trans1.verification == [ver]
        assert trans1.version == [0]
        assert trans1.text == ['Transaction text']
        assert trans1.amount == [Decimal('100.00')]

        trans2, = blm.accounting.Transaction._query(text='Transaction text 2').run()
        assert trans2.verification == [ver]
        assert trans2.version == [0]
        assert trans2.text == ['Transaction text 2']
        assert trans2.amount == [Decimal('-100.00')]

        data = {
            'verification': {'id': str(ver.id[0]),
                             'accounting': str(self.accounting.id[0]),
                             'series': str(self.series.id[0]),
                             'version': 1,
                             'transaction_date': '2010-01-02'},

            'transactions': [
                {'id': str(trans1.id[0]),
                 'account': str(self.account.id[0]),
                 'amount': 20000,
                 'text': 'Changed transaction text',
                 'version': 1},
                {'account': str(self.account.id[0]),
                 'amount': -20000,
                 'text': 'Transaction text 3',
                 'version': 1}
                ]
            }
        result, = blm.accounting.editVerification([data])
        ver, = blm.accounting.Verification._query().run()
        assert result['number'] == ver.number[0] == 1
        assert result['id'] == ver.id[0]
        assert ver.version == [1]
        assert ver.transaction_date == ['2010-01-02']

        trans1, = blm.accounting.Transaction._query(id=trans1.id[0]).run()
        assert trans1.verification == [ver]
        assert trans1.version == [1]
        assert trans1.text == ['Changed transaction text']
        assert trans1.amount == [Decimal('200.00')]

        assert not blm.accounting.Transaction._query(id=trans2.id[0]).run()

        trans3, = blm.accounting.Transaction._query(text='Transaction text 3').run()
        assert trans3.verification == [ver]
        assert trans3.version == [1]
        assert trans3.text == ['Transaction text 3']
        assert trans3.amount == [Decimal('-200.00')]

    def test_saveVerification_unbalanced(self):
        # Unbalanced verification should fail
        data = {
            'verification': {'accounting': str(self.accounting.id[0]),
                             'series': str(self.series.id[0]),
                             'number': 1,
                             'transaction_date': '2010-01-01'},

            'transactions': [
                {'account': str(self.account.id[0]),
                 'amount': 10000,
                 'text': 'Transaction text',
                 'version': 0},
                {'account': str(self.account.id[0]),
                 'amount': -25000,
                 'text': 'Transaction text 2',
                 'version': 0}
                ]
            }
        try:
            result, = blm.accounting.createVerification([data])
        except ValueError:
            pass
        else:
            raise AssertionError('Saving unbalanced verification should have raised an error.')
        vers = blm.accounting.Verification._query().run()
        assert len(vers) == 0
        trans = blm.accounting.Transaction._query().run()
        assert len(trans) == 0

    def test_saveVerification_with_incomplete_edit_data(self):
        data = {
            'verification': {'accounting': str(self.accounting.id[0]),
                             'series': str(self.series.id[0]),
                             'number': 1,
                             'transaction_date': '2010-01-01'},

            'transactions': [
                {'account': str(self.account.id[0]),
                 'amount': 10000,
                 'text': 'Transaction text',
                 'version': 0},
                {'account': str(self.account.id[0]),
                 'amount': -10000,
                 'text': 'Transaction text 2',
                 'version': 0}
                ]
            }
        result, = blm.accounting.createVerification([data])
        self.commit()
        ver, = blm.accounting.Verification._query().run()
        trans1, = blm.accounting.Transaction._query(text='Transaction text').run()
        trans2, = blm.accounting.Transaction._query(text='Transaction text 2').run()

        data = {
            'verification': {'id': str(ver.id[0]),
                             'accounting': str(self.accounting.id[0]),
                             'series': str(self.series.id[0]),
                             'version': 1,
                             'transaction_date': '2010-01-02'},

            'transactions': [
                {'id': str(trans1.id[0]),
                 'account': str(self.account.id[0]),
                 'amount': 20000,
                 'text': 'Changed transaction text',
                 'verification': '',
                 'version': 1},
                {'account': str(self.account.id[0]),
                 'amount': -20000,
                 'text': 'Transaction text 3',
                 'verification': '',
                 'version': 1}
                ]
            }
        result, = blm.accounting.editVerification([data])
        ver, = blm.accounting.Verification._query().run()
        assert result['number'] == ver.number[0] == 1
        assert result['id'] == ver.id[0]
        assert ver.version == [1]
        assert ver.transaction_date == ['2010-01-02']

        trans1, = blm.accounting.Transaction._query(id=trans1.id[0]).run()
        assert trans1.verification == [ver]
        assert trans1.version == [1]
        assert trans1.text == ['Changed transaction text']
        assert trans1.amount == [Decimal('200.00')]

        assert not blm.accounting.Transaction._query(id=trans2.id[0]).run()

        trans3, = blm.accounting.Transaction._query(text='Transaction text 3').run()
        assert trans3.verification == [ver]
        assert trans3.version == [1]
        assert trans3.text == ['Transaction text 3']
        assert trans3.amount == [Decimal('-200.00')]


class TestBalance(BLMTests):

    def test_abstract_class(self):
        # We should never instantiate Balance directly, only sub classes.
        with py.test.raises(AssertionError):
            balance = blm.accounting.Balance()


class TestObjectBalanceBudget(BLMTests):

    def setup_method(self, method):
        super(TestObjectBalanceBudget, self).setup_method(method)
        self.acc = blm.accounting.Accounting()
        self.account = blm.accounting.Account(accounting=[self.acc], number=['1234'])
        self.dim = blm.accounting.Dimension(name=['bar'], number=['23'], accounting=[self.acc])
        self.aobj = blm.accounting.AccountingObject(name=['foo'], number=['42'], dimension=[self.dim])

    def test_create(self):
        ob = blm.accounting.ObjectBalanceBudget(period=['201003'],
                                                accounting_object=[self.aobj],
                                                account_balance=[self.account])

        ob = blm.accounting.ObjectBalanceBudget(period=[''],
                                                accounting_object=[self.aobj],
                                                account_balance=[self.account])

        # period should be either YYYYMM or empty
        py.test.raises(Exception, blm.accounting.ObjectBalanceBudget,
                       account_balance=[self.account],
                       period=['2010'],
                       accounting_object=[self.aobj])


class TestBalanceBudget(BLMTests):

    def setup_method(self, method):
        super(TestBalanceBudget, self).setup_method(method)
        self.acc = blm.accounting.Accounting()
        self.account = blm.accounting.Account(accounting=[self.acc], number=['1234'])

    def test_create(self):
        blm.accounting.BalanceBudget(account_balance=[self.account], period=['201003'])


class TestAccountBalance(BLMTests):

    def setup_method(self, method):
        super(TestAccountBalance, self).setup_method(method)
        self.accounting = blm.accounting.Accounting()
        self.account = blm.accounting.Account(number=['1234'],
                                              accounting=[self.accounting])

    def test_create(self):
        ab3 = blm.accounting.AccountBalance(year=[-3], account=[self.account])
        assert self.account.account_balances['-3'] == ab3


class TestTransaction(BLMTests):

    def setup_method(self, method):
        super(TestTransaction, self).setup_method(method)
        self.org = blm.accounting.Org()
        self.accounting = blm.accounting.Accounting(org=[self.org])
        self.series = blm.accounting.VerificationSeries(
            accounting=self.accounting, name=['A'])
        self.ver = blm.accounting.Verification(series=[self.series], number=['1'],
                                               transaction_date=['2012-01-02'],
                                               accounting=[self.accounting])

    def test_create(self):
        user = blm.accounting.User()
        self.org.accountants = [user]
        self.ctx.setUser(user)

        accounting = self.accounting
        series = self.series

        accAsset = blm.accounting.Account(number=['1000'], type=['T'],
                                          opening_balance=['10'],
                                          opening_quantity=['2'],
                                          accounting=[accounting])

        accIncome = blm.accounting.Account(number=['3234'], type=['I'],
                                           accounting=[accounting],
                                           opening_balance=['20'],
                                           opening_quantity=['5'])

        trans = blm.accounting.Transaction(account=[accIncome],
                                           verification=[self.ver],
                                           version=self.ver.version)
        assert trans.transtype == ['normal']
        assert trans.amount == [Decimal('0')]
        assert trans.amount.precision == 2
        assert trans.quantity == [Decimal('0')]
        assert trans.transaction_date == ['2012-01-02']
        assert trans.signature == [str(i) for i in user.id]    # map(str, user.id)

        trans = blm.accounting.Transaction(account=[accAsset],
                                           verification=[self.ver],
                                           version=self.ver.version,
                                           transaction_date=['2012-04-05'],
                                           amount=['40'], quantity=['4'])
        assert trans.transaction_date == ['2012-04-05']
        assert accAsset.balance == [Decimal('50')]
        assert accAsset.balance_quantity == [Decimal('6')]

        trans = blm.accounting.Transaction(account=[accIncome],
                                           verification=[self.ver],
                                           version=self.ver.version,
                                           transaction_date=['2012-04-05'],
                                           amount=['30'], quantity=['2'])
        assert accIncome.balance == [Decimal('50')]
        assert accIncome.balance_quantity == [Decimal('7')]

        # update accounting objects
        dimension, = blm.accounting.Dimension._query(number=['1']).run()
        accounting_object = blm.accounting.AccountingObject(number=['101'],
                                                            name=['foo'],
                                                            dimension=[dimension])

        assert not accAsset.object_balance_budgets  # sanity
        # Test that ObjectBalanceBudget is created
        trans = blm.accounting.Transaction(account=[accAsset],
                                           verification=[self.ver],
                                           version=self.ver.version,
                                           transaction_date=['2012-04-05'],
                                           accounting_objects=[accounting_object],
                                           amount=['30'], quantity=['2'])
        obb = accAsset.object_balance_budgets[0]

        assert obb.balance == [Decimal('30')]
        assert obb.balance_quantity == [Decimal('2')]

        # Test that ObjectBalanceBudget is updated
        trans = blm.accounting.Transaction(account=[accAsset],
                                           verification=[self.ver],
                                           version=self.ver.version,
                                           transaction_date=['2012-04-05'],
                                           accounting_objects=[accounting_object],
                                           amount=['10'], quantity=['3'])

        assert obb.balance == [Decimal('40')]
        assert obb.balance_quantity == [Decimal('5')]

        trans = blm.accounting.Transaction(account=[accIncome],
                                           verification=[self.ver],
                                           version=self.ver.version,
                                           transaction_date=['2012-04-05'],
                                           accounting_objects=[accounting_object],
                                           amount=['20'], quantity=['7'])
        obb = accIncome.object_balance_budgets[0]

        assert obb.balance == [Decimal('20')]
        assert obb.balance_quantity == [Decimal('7')]

    def test_transactionIndex(self):
        account = blm.accounting.Account(number=['9999'],
                                         accounting=[self.accounting])

        for text in ('foo', 'bar', 'baz', ''):
            blm.accounting.Transaction(account=account, verification=[self.ver],
                                       version=self.ver.version, text=[text])

        self.commit()

        direct_query = {'filter': [{'property': 'org',
                                    'value': str(self.org.id[0])}]}
        result = blm.accounting.transactionIndex([direct_query])
        if PYT3:
            result.sort(key=lambda a: a['text'])
        else:
            result.sort()
        assert result == [{'text': 'bar', 'org': str(self.org.id[0])},
                          {'text': 'baz', 'org': str(self.org.id[0])},
                          {'text': 'foo', 'org': str(self.org.id[0])}]

    def test_strip_text(self):
        account = blm.accounting.Account(number=['9999'],
                                         accounting=[self.accounting])
        t = blm.accounting.Transaction(account=account, verification=[self.ver],
                                       version=self.ver.version, text=['foo'])
        assert t.text == ['foo']

        t = blm.accounting.Transaction(account=account, verification=[self.ver],
                                       version=self.ver.version, text=['  foo  '])
        assert t.text == ['foo']

        t(text=['  bar  '])
        assert t.text == ['bar']

    def test_transaction_update_recalculates_balance(self):
        account1 = blm.accounting.Account(number=['9999'],
                                         accounting=[self.accounting])
        account2 = blm.accounting.Account(number=['5000'],
                                         accounting=[self.accounting])
        t1 = blm.accounting.Transaction(account=account1, verification=[self.ver],
                                       version=self.ver.version, amount=['10.00'])
        t2 = blm.accounting.Transaction(account=account1, verification=[self.ver],
                                       version=self.ver.version, amount=['20.00'])
        self.commit()

        account1, = blm.accounting.Account._query(number=['9999']).run()
        assert account1.balance == [Decimal('30.00')] # sanity

        t1, = blm.accounting.Transaction._query(id=t1.id[0]).run()
        t1(amount=['30.00'])
        assert account1.balance == [Decimal('50.00')]

        t1(account=account2)
        assert account1.balance == [Decimal('20.00')]

    def test_transaction_delete_recalculates_balance(self):
        account1 = blm.accounting.Account(number=['9999'],
                                         accounting=[self.accounting])
        t1 = blm.accounting.Transaction(account=account1, verification=[self.ver],
                                       version=self.ver.version, amount=['10.00'])
        t2 = blm.accounting.Transaction(account=account1, verification=[self.ver],
                                       version=self.ver.version, amount=['20.00'])
        t3 = blm.accounting.Transaction(account=account1, verification=[self.ver],
                                       version=self.ver.version, amount=['15.00'])
        self.commit()

        account1, = blm.accounting.Account._query(number=['9999']).run()
        assert account1.balance == [Decimal('45.00')] # sanity

        t1, = blm.accounting.Transaction._query(id=t1.id[0]).run()
        t1._delete()
        t2, = blm.accounting.Transaction._query(id=t2.id[0]).run()
        t2._delete()
        assert account1.balance == [Decimal('15.00')]


class TestLogVerification(BLMTests):

    def setup_method(self, method):
        super(TestLogVerification, self).setup_method(method)
        org = blm.accounting.Org()
        accounting = blm.accounting.Accounting(org=[org])
        series = blm.accounting.VerificationSeries(
            accounting=accounting, name=['A'])

        acc1 = blm.accounting.Account(number=['1000'], accounting=[accounting])
        acc2 = blm.accounting.Account(number=['2000'], accounting=[accounting])

        ver = blm.accounting.Verification(accounting=accounting,
                                          series=series,
                                          text=['original'],
                                          transaction_date=['2010-01-01'])
        blm.accounting.Transaction(verification=[ver],
                                   version=ver.version,
                                   account=[acc1],
                                   amount=['10.00'])
        self.commit()
        self.ver, = blm.accounting.Verification._query().run()
        self.trans, = blm.accounting.Transaction._query().run()
        self.acc1, self.acc2 = sorted(blm.accounting.Account._query().run(),
                                      key=lambda t: t.number[0])

    def loadAttrs(self, toi):
        for attr in toi.logattrs:
            getattr(toi, attr).value

    def test_log_verification_edit(self):
        self.loadAttrs(self.ver)
        orgver = self.ver._attrData.copy()

        self.ver(transaction_date=['2010-01-02'],
                 text=['changed'])
        self.commit()
        ver, = blm.accounting.Verification._query().run()
        trans, = blm.accounting.Transaction._query().run()

        assert ver.version == [1]
        assert trans.transaction_date == ['2010-01-02']
        assert trans.version == [0]

        log = ver.log['0']
        assert len(log) == 1
        verlog = bson.BSON(log[0]).decode()
        assert verlog == orgver

    def test_log_transaction_add(self):
        self.ver(text=['changed'])
        assert len(self.ver.log['0']) == 1  # sanity
        self.commit()

        ver, = blm.accounting.Verification._query().run()
        trans = blm.accounting.Transaction(verification=self.ver,
                                           version=[1],
                                           account=[self.acc1],
                                           amount=['40.00'])
        self.commit()
        ver, = blm.accounting.Verification._query().run()

        log = ver.log['0']
        assert len(log) == 2
        try:
            translog = bson.BSON(log[1]).decode()
        except UnicodeEncodeError:
            print(repr(dict(ver.log)))
            raise
        assert translog == {'id': list(trans.id)}

    def test_log_transaction_change(self):
        self.ver(text=['changed'])
        assert len(self.ver.log['0']) == 1  # sanity
        self.commit()

        trans, = blm.accounting.Transaction._query().run()
        acc2 = blm.accounting.Account._query(number='2000').run()
        trans(version=[1], amount=['40.00'], account=acc2)

        self.commit()
        ver, = blm.accounting.Verification._query().run()

        log = self.ver.log['0']
        assert len(log) == 2
        translog = bson.BSON(log[1]).decode()
        assert translog == {'id': list(self.trans.id),
                            'version': [0],
                            'amount': [Decimal('10.00')],
                            'quantity': [Decimal('0')],
                            'text': [''],
                            'signature': [],
                            'transaction_date': ['2010-01-01'],
                            'account': ['1000']}
        assert self.trans.version == [1] # make sure toi._update() has been called

    def test_log_transaction_delete(self):
        self.ver(text=['changed'])
        assert len(self.ver.log['0']) == 1  # sanity
        self.commit()

        self.trans._delete()
        self.commit()
        ver, = blm.accounting.Verification._query().run()

        log = ver.log['0']
        assert len(log) == 2
        translog = bson.BSON(log[1]).decode()
        assert translog == {'id': list(self.trans.id),
                            'version': [0],
                            'amount': [Decimal('10.00')],
                            'quantity': [Decimal('0')],
                            'text': [''],
                            'signature': [],
                            'transaction_date': ['2010-01-01'],
                            'account': ['1000']}

    def test_version_mismatch(self):
        py.test.raises(exceptions.ClientError, self.ver, version=5)


class TestAdminPermissions(BLMTests):
    def setup_method(self, method):
        super(TestAdminPermissions, self).setup_method(method)
        self.admin = blm.accounting.User()
        self.member = blm.accounting.User()
        self.other = blm.accounting.User()
        self.ctx.setUser(self.admin)
        self.org = blm.accounting.Org(subscriptionLevel=['subscriber'])
        self.ctx.setUser(None)
        self.org.ug[0].users = [self.admin, self.member]
        self.accounting = blm.accounting.Accounting(org=[self.org])
        self.commit()
        self.admin = blm.accounting.User._query(id=self.admin).run()[0]
        self.member = blm.accounting.User._query(id=self.member).run()[0]
        self.other = blm.accounting.User._query(id=self.other).run()[0]
        self.org = blm.accounting.Org._query(id=self.org).run()[0]
        self.accounting = blm.accounting.Accounting._query(id=self.accounting).run()[0]

    def test_admin(self):
        assert self.org.admins == [self.admin]

    def test_edit_org(self):
        self.ctx.setUser(self.admin)
        self.org.name = ['Hepp!']
        self.ctx.setUser(self.member)
        py.test.raises(ClientError, setattr, self.org, 'name', ['Hupp!'])
        self.ctx.setUser(self.other)
        py.test.raises(ClientError, setattr, self.org, 'name', ['Hipp!'])

    def test_payment_providers(self):
        for cls in (blm.accounting.PaymentProvider,
                    blm.accounting.SimulatorProvider,
                    blm.accounting.PlusgiroProvider,
                    #blm.accounting.PaysonProvider
                    ):
            self.ctx.setUser(self.admin)
            pp = cls(org=[self.org])
            self.commit()
            pp(account=['1000'])

            self.ctx.setUser(self.member)
            pp, = cls._query(id=pp).run()
            py.test.raises(ClientError, cls, org=[self.org])
            py.test.raises(ClientError, pp, account=['2000'])
            py.test.raises(ClientError, pp._delete)

    def test_pg_order(self):
        self.ctx.setUser(self.admin)
        pgo = blm.accounting.PGOrder(org=[self.org], contact=['a'],
                                     contactPhone=['b'], contactEmail=['c'],
                                     pgnum=['d'])
        self.commit()
        pgo(sent=[True])
        py.test.raises(ClientError, pgo, pgnum=['x'])

        self.ctx.setUser(self.member)
        py.test.raises(ClientError, blm.accounting.PGOrder,
                       org=[self.org], contact=['a'],
                       contactPhone=['b'], contactEmail=['c'],
                       pgnum=['d'])
        py.test.raises(ClientError, pgo, sent=[False])
        py.test.raises(ClientError, pgo, pgnum=['y'])

    def test_propagate_name_and_orgnum_to_current_accounting(self):
        self.ctx.setUser(self.admin)
        self.org(name=['Foo'], orgnum=['123456-7890'])
        assert self.org.current_accounting == [self.accounting]
        assert self.accounting.orgname == ['Foo']
        assert self.accounting.orgnum == ['123456-7890']


class TestPayerPermissions(PermissionTests):

    def setup_method(self, method):
        super(TestPayerPermissions, self).setup_method(method)
        self.payer = blm.accounting.User()
        self.member = blm.accounting.User()
        self.other = blm.accounting.User()
        self.org = blm.accounting.Org()
        self.org.ug[0].users = [self.payer, self.member]
        self.org.payers = [self.payer]
        self.commit()
        self.payer, = blm.accounting.User._query(id=self.payer).run()
        self.member, = blm.accounting.User._query(id=self.member).run()
        self.other, = blm.accounting.User._query(id=self.other).run()
        self.org, = blm.accounting.Org._query(id=self.org).run()

    def test_supplier_invoice(self):
        self.check(blm.accounting.SupplierInvoice,
                   params=dict(org=self.org,
                               recipient='Foo Inc.',),
                   edit=dict(transferAddress='Foo Street 1'),
                   allow=[self.payer],
                   deny=[self.member])


class TestAccountantPermissions(PermissionTests):
    def setup_method(self, method):
        super(TestAccountantPermissions, self).setup_method(method)
        self.accountant = blm.accounting.User()
        self.member = blm.accounting.User()
        self.other = blm.accounting.User()
        self.org = blm.accounting.Org()
        self.org.ug[0].users = [self.accountant, self.member]
        self.org.accountants = [self.accountant]
        self.commit()
        self.accountant = blm.accounting.User._query(id=self.accountant).run()[0]
        self.member = blm.accounting.User._query(id=self.member).run()[0]
        self.other = blm.accounting.User._query(id=self.other).run()[0]
        self.org = blm.accounting.Org._query(id=self.org).run()[0]

    def test_accounting(self):
        self.check(blm.accounting.Accounting,
                   params=dict(org=self.org),
                   edit=dict(start='2014-01-01'),
                   allow=[self.accountant], deny=[self.member])

    def test_create_accounting(self):
        self.ctx.setUser(self.accountant)
        self.accounting = blm.accounting.Accounting(org=[self.org])

        self.ctx.setUser(self.member)
        py.test.raises(ClientError, blm.accounting.Accounting, org=[self.org])

    def test_edit_accounting(self):
        accounting = blm.accounting.Accounting(org=[self.org])
        self.commit()
        accounting, = blm.accounting.Accounting._query(id=accounting.id).run()

        self.ctx.setUser(self.accountant)
        accounting(start=['2010-01-01'])

        self.ctx.setUser(self.member)
        py.test.raises(ClientError, accounting, start=['2011-01-01'])

    def test_edit_and_create_dimensions(self):
        accounting = blm.accounting.Accounting(org=[self.org])
        self.check(blm.accounting.Dimension,
                   params=dict(number='42', name='meaning of life',
                               accounting=accounting),
                   edit=dict(number='43'),
                   allow=self.accountant, deny=self.member)

    def test_accounting_object(self):
        accounting = blm.accounting.Accounting(org=[self.org])
        dim = blm.accounting.Dimension(number='42', name='meaning of life',
                                       accounting=accounting)
        self.check(blm.accounting.AccountingObject,
                   params=dict(number='1', name='ao', dimension=dim),
                   edit=dict(number='2'),
                   allow=self.accountant, deny=self.member)

    def test_edit_and_create_series(self):
        accounting = blm.accounting.Accounting(org=[self.org])
        self.commit()

        self.ctx.setUser(self.accountant)
        seriesA = blm.accounting.VerificationSeries(accounting=[accounting],
                                                    name=['A'])
        self.commit()
        seriesA, = blm.accounting.VerificationSeries._query(id=seriesA).run()
        seriesA(description=['foo'])

        self.ctx.setUser(self.member)
        py.test.raises(ClientError, blm.accounting.VerificationSeries,
                       accounting=[accounting], name=['B'])
        py.test.raises(ClientError, seriesA, description=['bar'])

    def test_edit_and_create_account_and_account_balance(self):
        accounting = blm.accounting.Accounting(org=[self.org])
        self.commit()

        self.ctx.setUser(self.accountant)
        account1000 = blm.accounting.Account(accounting=[accounting],
                                             number=['1000'])
        self.commit()
        account1000, = blm.accounting.Account._query(number='1000').run()
        account1000(name=['the account'])

        self.ctx.setUser(self.member)
        py.test.raises(ClientError, blm.accounting.Account,
                       accounting=[accounting], number=['2000'])
        py.test.raises(ClientError, account1000,
                       name=['the account with the new name'])

        with py.test.raises(ClientError):
            blm.accounting.AccountBalance(account=account1000, year=[-1])

        self.ctx.setUser(self.accountant)
        ab = blm.accounting.AccountBalance(account=account1000, year=[-1])
        self.commit()
        ab._clear()

        self.ctx.setUser(self.member)
        with py.test.raises(ClientError):
            ab(year=[-2])

        self.ctx.setUser(self.accountant)
        ab(year=[-2])

    def test_balance_budget_and_object_balance_budget(self):
        accounting = blm.accounting.Accounting(org=[self.org])
        account = blm.accounting.Account(accounting=[accounting],
                                         number=['1000'])
        dim = blm.accounting.Dimension(accounting=[accounting], number=['1'],
                                       name=['dim'])
        ao = blm.accounting.AccountingObject(dimension=[dim], number=['1'],
                                             name=['ao'])
        # ObjectBalanceBudget
        self.ctx.setUser(self.member)
        with py.test.raises(ClientError):
            blm.accounting.ObjectBalanceBudget(account_balance=[account],
                                               accounting_object=[ao],
                                               period=[''])

        self.ctx.setUser(self.accountant)
        obb = blm.accounting.ObjectBalanceBudget(account_balance=[account],
                                                 accounting_object=[ao],
                                                 period=[''])
        self.commit()
        obb._clear()

        self.ctx.setUser(self.member)
        with py.test.raises(ClientError):
            obb(period=['201401'])

        self.ctx.setUser(self.accountant)
        obb(period=['201402'])

        # BalanceBudget
        self.ctx.setUser(self.member)
        with py.test.raises(ClientError):
            blm.accounting.BalanceBudget(account_balance=[account],
                                         period=['201401'])

        self.ctx.setUser(self.accountant)
        bb = blm.accounting.BalanceBudget(account_balance=[account],
                                           period=['201401'])
        self.commit()
        bb._clear()

        self.ctx.setUser(self.member)
        with py.test.raises(ClientError):
            bb(period=['201402'])

        self.ctx.setUser(self.accountant)
        bb(period=['201403'])

    def test_edit_and_create_verification(self):
        accounting = blm.accounting.Accounting(org=[self.org])
        series = blm.accounting.VerificationSeries(accounting=[accounting],
                                                   name=['A'])
        account = blm.accounting.Account(accounting=[accounting],
                                         number=['1000'])
        self.commit()

        accounting, = blm.accounting.Accounting._query().run()
        series, = blm.accounting.VerificationSeries._query().run()
        account, = blm.accounting.Account._query().run()

        self.ctx.setUser(self.accountant)
        ver = blm.accounting.Verification(accounting=[accounting],
                                          series=[series])
        trans = blm.accounting.Transaction(verification=[ver],
                                           account=[account],
                                           version=[0])
        self.commit()
        ver(transaction_date=['2010-01-01'])
        trans(amount=['10.00'])

        self.ctx.setUser(self.member)
        py.test.raises(ClientError, blm.accounting.Verification,
                       accounting=[accounting], series=[series])
        py.test.raises(ClientError, blm.accounting.Transaction,
                       verification=[ver], account=[account], version=[0])
        py.test.raises(ClientError, ver, transaction_date=['2011-01-01'])
        py.test.raises(ClientError, trans, amount=['20.00'])


class TestInvoiceSenderPermissions(BLMTests):
    def setup_method(self, method):
        super(TestInvoiceSenderPermissions, self).setup_method(method)
        self.org = blm.accounting.Org()
        self.invoicesender = blm.accounting.APIUser(roles='invoicesenders')
        self.member = blm.accounting.User()
        self.other = blm.accounting.User()
        self.org.ug[0].users = [self.invoicesender, self.member]
        self.commit()
        self.org = blm.accounting.Org._query(id=self.org).run()[0]

    def test_ocr_counter(self):
        self.ctx.setUser(self.other)
        with py.test.raises(ClientError):
            self.org.get_ocr()

        self.ctx.setUser(self.member)
        self.org.get_ocr()

        self.ctx.setUser(self.invoicesender)
        self.org.get_ocr()


class TestVatCode(BLMTests):

    def setup_method(self, method):
        super(TestVatCode, self).setup_method(method)
        self.vat_table = blm.accounting.VatCode.vat_table

    def test_create(self):
        vc = blm.accounting.VatCode(code=['10'], xmlCode=['mngol'],
                                    description=['meaning of life'])
        self.commit()
        vc._clear()
        vc(code=['66'])

    def test_set_percentage(self):
        blm.accounting.VatCode.vat_table = {
            '10': '10',
            '11': '10',
            '12': '20'}
        vc10 = blm.accounting.VatCode(code=['10'], xmlCode=['10'])
        vc11 = blm.accounting.VatCode(code=['11'], xmlCode=['10'])
        vc12 = blm.accounting.VatCode(code=['12'], xmlCode=['10'])
        vc13 = blm.accounting.VatCode(code=['13'], xmlCode=['10'])

        assert vc10.percentage == [Decimal('10')]
        assert vc11.percentage == [Decimal('10')]
        assert vc12.percentage == [Decimal('20')]
        assert vc13.percentage == []

    def test_root_only(self):
        vc = blm.accounting.VatCode(code=['10'], xmlCode=['mngol'])
        self.commit()
        vc._clear()

        user = blm.accounting.User()
        self.ctx.setUser(user)
        with py.test.raises(ClientError):
            blm.accounting.VatCode(code=['42'], xmlCode=['mngol'],
                                   description=['meaning of life'])

        with py.test.raises(ClientError):
            vc(code=['17'])


class TestReadPermissions(BLMTests):

    def setup_method(self, method):
        super(TestReadPermissions, self).setup_method(method)
        self.public = blm.accounting.UG(name=['public'])
        self.user = blm.accounting.User()
        self.ctx.setUser(self.user)

    def test_user_setup(self):
        assert self.user.allowRead == [self.user]
        assert self.user.ugs == [self.public]

    def test_ug(self):
        ug = blm.accounting.UG()
        assert ug.allowRead == [ug]

    def test_no_more_public_ugs(self):
        assert self.ctx.user
        # Only super user may create UGs with names
        py.test.raises(Exception, blm.accounting.UG, name=['public'])

    def test_org(self):
        org = blm.accounting.Org()
        assert org.ug[0].users == [self.user]
        assert org.ug[0] in self.user.allowRead
        assert org.ticketchecker_ug[0] in self.user.allowRead
        assert set(org.allowRead) == set(org.ug + org.ticketchecker_ug)

    def get_org(self):
        return blm.accounting.Org(name=['Acme Corporation'],
                                  email=['acme@example'],
                                  accountants=[self.user])

    def test_paymentproviderdata(self):
        org = self.get_org()
        ppd = blm.accounting.PaymentProvider(org=org)
        assert ppd.allowRead == org.ug

    def test_pgorder(self):
        org = self.get_org()
        pgorder = blm.accounting.PGOrder(
            org=[org],
            contact=['Mr. Foo'],
            contactPhone=['1234567'],
            contactEmail=['foo@example'],
            pgnum=['12345-6'])

        assert pgorder.allowRead == org.ug

    def test_invitation(self, monkeypatch):
        org = self.get_org()
        monkeypatch.setattr(mail, 'sendmail', lambda *args, **kw: None)
        invitation, = org.invite(['foo@example'])
        assert invitation.allowRead == org.ug

    def test_accounting(self):
        org = self.get_org()
        acc1 = blm.accounting.Accounting(org=[org])
        assert acc1.allowRead == org.ug

    def get_accounting(self):
        org = self.get_org()
        assert org.ug
        acc = blm.accounting.Accounting(org=[org])
        assert acc.allowRead == org.ug
        return acc

    def test_dimension(self):
        acc = self.get_accounting()
        dim = blm.accounting.Dimension(number=['1'], name=['A'],
                                       accounting=[acc])
        assert dim.allowRead == acc.allowRead

        for dim in blm.accounting.Dimension._query(accounting=acc).run():
            assert dim.allowRead == acc.allowRead

    def test_accounting_object(self):
        acc = self.get_accounting()
        dim = blm.accounting.Dimension(number=['1'], name=['A'],
                                       accounting=[acc])
        ao = blm.accounting.AccountingObject(number=['1'], name=['A'],
                                             dimension=[dim])
        assert ao.allowRead == dim.allowRead

    def test_account(self):
        acc = self.get_accounting()
        account = blm.accounting.Account(number=['1234'], accounting=[acc])
        assert account.allowRead == acc.allowRead

    def get_account(self):
        acc = self.get_accounting()
        account = blm.accounting.Account(number=['1234'], accounting=[acc])
        assert account.allowRead == acc.allowRead
        return account

    def test_verification_series(self):
        acc = self.get_accounting()
        vs = blm.accounting.VerificationSeries(name=['A'], accounting=[acc])
        assert vs.allowRead == acc.allowRead

    def test_verification(self):
        acc = self.get_accounting()
        series = blm.accounting.VerificationSeries(accounting=acc, name=['A'])
        ver = blm.accounting.Verification(series=[series], number=[1],
                                          accounting=[acc])
        assert ver.allowRead == acc.allowRead

    def test_transaction(self):
        acc = self.get_accounting()
        series = blm.accounting.VerificationSeries(accounting=acc, name=['A'])
        ver = blm.accounting.Verification(series=[series], number=[1],
                                          accounting=[acc])
        account = blm.accounting.Account(number=['1234'], accounting=[acc])
        trans = blm.accounting.Transaction(verification=[ver],
                                           version=ver.version,
                                           account=[account])
        assert trans.allowRead == ver.allowRead == account.allowRead

    def test_account_balance(self):
        account = self.get_account()
        ab = blm.accounting.AccountBalance(year=[-1], account=[account])
        assert ab.allowRead == account.allowRead

    def test_object_balance_budget(self):
        account = self.get_account()
        dim = blm.accounting.Dimension(name=['bar'], number=['23'], accounting=account.accounting)
        aobj = blm.accounting.AccountingObject(name=['foo'], number=['42'], dimension=[dim])
        obb = blm.accounting.ObjectBalanceBudget(period=[''],
                                                 accounting_object=[aobj],
                                                 account_balance=[account])
        assert obb.allowRead == account.allowRead

    def test_balance_budget(self):
        account = self.get_account()
        bb = blm.accounting.BalanceBudget(period=['201003'],
                                          account_balance=[account])
        assert bb.allowRead == account.allowRead

    def test_account_template(self):
        self.ctx.setUser(None)
        at = blm.accounting.AccountTemplate(number=['1234'])
        assert at.allowRead == [self.public]

    def test_chart_of_accounts(self):
        self.ctx.setUser(None)
        chart = blm.accounting.ChartOfAccounts(name=['foo'])
        assert chart.allowRead == [self.public]

    def test_vatcode(self):
        self.ctx.setUser(None)
        vatCode = blm.accounting.VatCode(code=['66'], xmlCode=['Awsm'],
                                         description=['Awesome'])
        assert vatCode.allowRead == [self.public]


class TestCascadingDelete(BLMTests):

    def test_delete_all(self):
        fname = os.path.join(os.path.dirname(__file__), 'sie', 'delete.si')
        importer = sie_import.SIEImporter()
        importer.parseFile(fname)
        toid = importer.accounting.id[0]
        self.commit()

        accounting, = blm.accounting.Accounting._query(id=toid).run()
        accounting._delete()
        self.commit()

        assert not blm.accounting.Account._query().run()
        assert not blm.accounting.AccountBalance._query().run()
        assert not blm.accounting.Accounting._query().run()
        assert not blm.accounting.AccountingObject._query().run()
        assert not blm.accounting.BalanceBudget._query().run()
        assert not blm.accounting.Dimension._query().run()
        assert not blm.accounting.ObjectBalanceBudget._query().run()
        assert not blm.accounting.Transaction._query().run()
        assert not blm.accounting.Verification._query().run()
        assert not blm.accounting.VerificationSeries._query().run()


class SIETests(BLMTests):

    def import_sie(self, fname, org=[]):
        sie = os.path.join(os.path.dirname(__file__), 'sie', fname)
        importer = sie_import.SIEImporter(list(org))
        importer.ignoretransactions = False
        importer.parseFile(sie)
        self.commit()
        return blm.accounting.Accounting._query(id=importer.accounting).run()[0]

    def compare(self, acc1, acc2, require_accounting_objects=True,
                require_account_balances=True,
                require_object_balance_budgets=True):
        # compare basic attribute at root level
        assert acc1.contact == acc2.contact
        assert acc1.currency == acc2.currency
        assert acc1.end == acc2.end
        assert acc1.industry_code == acc2.industry_code
        assert acc1.layout == acc2.layout
        assert acc1.mail_address == acc2.mail_address
        assert acc1.orgname == acc2.orgname
        assert acc1.orgnum == acc2.orgnum
        assert acc1.orgtype == acc2.orgtype
        assert acc1.start == acc2.start
        assert acc1.taxation_year == acc2.taxation_year
        assert acc1.telephone == acc2.telephone
        assert acc1.zip_city == acc2.zip_city
        assert acc1.closed == acc2.closed

        key = lambda t: t.number[0]
        acc1_accounts = blm.accounting.Account._query(accounting=acc1).run()
        acc2_accounts = blm.accounting.Account._query(accounting=acc2).run()
        acc1_accounts.sort(key=key)
        acc2_accounts.sort(key=key)

        acc1_dimensions = blm.accounting.Dimension._query(accounting=acc1).run()
        acc2_dimensions = blm.accounting.Dimension._query(accounting=acc2).run()
        acc1_dimensions.sort(key=key)
        acc2_dimensions.sort(key=key)

        acc1_verifications = blm.accounting.Verification._query(accounting=acc1).run()
        acc2_verifications = blm.accounting.Verification._query(accounting=acc2).run()
        acc1_verifications.sort(key=key)
        acc2_verifications.sort(key=key)

        acc1_series = blm.accounting.VerificationSeries._query(
            accounting=acc1).run()
        acc2_series = blm.accounting.VerificationSeries._query(
            accounting=acc2).run()
        acc2_series.sort(key=lambda t: t.name[0])
        acc2_series.sort(key=lambda t: t.name[0])


        for dim1, dim2 in izip_longest(acc1_dimensions, acc2_dimensions):
            assert dim1.accounting == [acc1]
            assert dim2.accounting == [acc2]
            assert dim1.number == dim2.number
            assert dim1.name == dim2.name
            assert dim1.project == dim2.project

            for pdim1, pdim2 in izip_longest(dim1.subdim_of, dim2.subdim_of):
                assert pdim1 != pdim2  # do not just copy the toiref
                assert pdim1.accounting == [acc1]
                assert pdim2.accounting == [acc2]
                assert pdim1.number == pdim2.number
                assert pdim1.name == pdim2.name
                assert pdim1.project == pdim2.project

            dim1_aos = blm.accounting.AccountingObject._query(
                dimension=dim1).run()
            dim2_aos = blm.accounting.AccountingObject._query(
                dimension=dim2).run()
            dim1_aos.sort(key=key)
            dim2_aos.sort(key=key)

            for ao1, ao2 in izip_longest(dim1_aos, dim2_aos):
                assert ao1 != ao2
                assert ao1.dimension == [dim1]
                assert ao2.dimension == [dim2]
                assert ao1.number == ao2.number
                assert ao1.name == ao2.name

        for ver1, ver2 in izip_longest(acc1_verifications, acc2_verifications):
            assert ver1.accounting == [acc1]
            assert ver2.accounting == [acc2]
            assert ver1.series[0].name == ver2.series[0].name
            assert ver1.number == ver2.number
            assert ver1.transaction_date == ver2.transaction_date
            assert ver1.text == ver2.text

        assert pdim1 and pdim2
        if require_accounting_objects:
            assert ao1 and ao2

        for account1, account2 in izip_longest(acc1_accounts, acc2_accounts):
            assert account1.accounting == [acc1]
            assert account2.accounting == [acc2]
            assert account1.number == account2.number
            assert account1.name == account2.name
            assert account1.type == account2.type
            assert account1.unit == account2.unit
            assert account1.sru == account2.sru
            assert account1.opening_balance == account2.opening_balance
            assert account1.vatCode == account2.vatCode
            assert account1.vatPercentage == account2.vatPercentage

            acc1_abs = [ab for (year, ab) in sorted(account1.account_balances.value.items())]
            acc2_abs = [ab for (year, ab) in sorted(account2.account_balances.value.items())]

            for ab1, ab2 in izip_longest(acc1_abs, acc2_abs):
                assert ab1.account == [account1]
                assert ab2.account == [account2]
                assert ab1.year == ab2.year
                assert ab1.opening_balance == ab2.opening_balance
                assert ab1.opening_quantity == ab2.opening_quantity
                assert ab1.balance == ab2.balance
                assert ab1.balance_quantity == ab2.balance_quantity
                assert ab1.budget == ab2.budget
                assert ab1.budget_quantity == ab2.budget_quantity

                ab1_obbs = blm.accounting.ObjectBalanceBudget._query(
                    account_balance=ab1).run()
                ab2_obbs = blm.accounting.ObjectBalanceBudget._query(
                    account_balance=ab2).run()
                # xxx sorting?

                for obb1, obb2 in izip_longest(ab1_obbs, ab2_obbs):
                    assert obb1.account_balance == [ab1]
                    assert obb2.account_balance == [ab2]

                    # xxx account balances
                    assert obb1.opening_balance == obb2.opening_balance
                    assert obb1.opening_quantity == obb2.opening_quantity
                    assert obb1.balance == obb2.balance
                    assert obb1.balance_quantity == obb2.balance_quantity
                    assert obb1.budget == obb2.budget
                    assert obb1.budget_quantity == obb2.budget_quantity

                    assert obb1.period == [''] # xxx ????

            if require_account_balances:
                assert ab1 and ab2

        if require_object_balance_budgets:
            assert obb1, obb2
        assert account1 and account2

        for series1, series2 in izip_longest(acc1_series, acc2_series):
            assert series1.accounting == [acc1]
            assert series2.accounting == [acc2]
            assert series1.name == series2.name
            assert series1.description == series2.description

        assert series1 and series2


class TestNewAccountingYear(SIETests):

    def setup_method(self, method):
        super(TestNewAccountingYear, self).setup_method(method)
        self.tmpdir = py.path.local.make_numbered_dir('pytest-')

    def test_newAccountingFromLastYear(self):
        org = blm.accounting.Org()
        pp = blm.accounting.PaymentProvider(org=[org], account=['1000'],
                                            series=['A'])
        for y in range(3):
            acc = blm.accounting.Accounting(org=[org], start=['201%d-01-01' % y],
                                            layout=[str(y)])

        copy, = blm.accounting.newAccountingFromLastYear([org])
        # whiteboxy, abuse layout to check that we copied the latest year
        assert copy.layout == ['2']

    def test_from_open(self):
        original = self.import_sie('new_year_source.si')
        expect = self.import_sie('new_year_expected.si')

        org = blm.accounting.Org(
            name=['org ' + original.orgname[0]],
            orgnum=['42' + original.orgnum[0]],
            phone=['42' + original.telephone[0]],
        )
        original.org = [org]
        copy, = original.new()
        self.commit()

        original = blm.accounting.Accounting._query(id=original).run()[0]
        expect = blm.accounting.Accounting._query(id=expect).run()[0]
        copy = blm.accounting.Accounting._query(id=copy).run()[0]
        #import pdb;pdb.set_trace()
        self.compare(copy, expect)

class TestSupplierInvoiceProvider(BLMTests):
    def setup_method(self, method):
        super(TestSupplierInvoiceProvider, self).setup_method(method)
        self.org = blm.accounting.Org()

    def test_generateTransferAddress(self):
        provider = blm.accounting.SupplierInvoiceProvider(
            org=self.org, series='A', account='3000', bank_account='4000'
        )

        transferAddress1 = provider.generateTransferAddress(
            clearingnumber='4321', bankaccount='567894321'
        )
        assert len(transferAddress1) == 6
        assert luhn.luhn_checksum(transferAddress1) == 0
        assert int(transferAddress1) > 0

        transferAddress2 = provider.generateTransferAddress(
            clearingnumber='4567', bankaccount='9887654321'
        )
        assert transferAddress1 != transferAddress2
        assert len(transferAddress2) == 6
        assert luhn.luhn_checksum(transferAddress2) == 0
        assert int(transferAddress2) > 0

        # Consistency
        assert provider.generateTransferAddress(
            clearingnumber='4321', bankaccount='567894321'
        ) == transferAddress1


class TestSupplierInvoice(BLMTests):

    def setup_method(self, method):
        super(TestSupplierInvoice, self).setup_method(method)
        self.org = blm.accounting.Org(subscriptionLevel='subscriber', orgnum='5164005810')
        self.payer = blm.accounting.User()
        self.org.ug[0].users = [self.payer]
        self.org.payers = [self.payer]
        self.accounting = blm.accounting.Accounting(org=self.org)
        self.account1000 = blm.accounting.Account(accounting=self.accounting, number='1000')
        self.account2000 = blm.accounting.Account(accounting=self.accounting, number='2000')
        self.account3000 = blm.accounting.Account(accounting=self.accounting, number='3000')
        self.account4000 = blm.accounting.Account(accounting=self.accounting, number='4000')
        self.series = blm.accounting.VerificationSeries(accounting=self.accounting, name='A')
        self.provider = blm.accounting.SupplierInvoiceProvider(org=self.org, series='A', account='3000', bank_account='4000', plusgiro_sending_bank_account='44580231')
        self.bankgiroprovider = blm.accounting.BankgiroProvider(org=self.org, bgnum=['1234566'])

        self.invoice0 = {
            u'amount': 664000,
            u'invoiceIdentifierType': u'message',
            u'transferMethod': u'bgnum',
            u'message': u'Leverans',
            u'recipient': u'Mottagare AB',
            u'bgnum': u'8888885',
            u'regVerificationLines': None,
            u'regVerificationVersion': None,
        }
        self.invoice1 = {
            u'bankaccount': u'',
            u'invoiceNumber': u'',
            u'invoiceDate': u'2017-03-08',
            u'amount': 98000,
            u'transferDate': u'2017-05-06', #unicode(datetime.now().strftime('%Y-%m-%d'))
            u'invoiceType': u'debit',
            u'pgnum': u'',
            u'invoiceIdentifierType': u'ocr',
            u'transferMethod': u'bgnum',
            u'message': u'',
            u'ocr': u'56897456986',
            u'recipient': u'Mottagar1 AB',
            u'dueDate': u'2018-03-25',
            u'bgnum': u'8888885',
            u'regVerificationVersion': 1,
            u'regVerificationLines': [
                {
                    u'text': u'purchases going up',
                    u'account': py23txtu(self.account2000.id[0]),
                    u'amount': 5000,
                    u'version': 1
                },
                {
                    u'amount': -5000,
                    u'account': py23txtu(self.account3000.id[0]),
                    u'text': u'Supplier debt credit account going up',
                    u'version': 1
                }
            ]
        }
        self.invoice2 = {
            u'bankaccount': u'',
            u'invoiceNumber': u'12356986799',
            u'invoiceDate': u'2017-04-08',
            u'amount': 21000,
            u'transferDate': u'2017-05-03',
            u'invoiceType': u'debit',
            u'pgnum': u'',
            u'invoiceIdentifierType': u'invoiceNumber',
            u'transferMethod': u'bgnum',
            u'message': u'Leverans två',
            u'ocr': u'',
            u'recipient': u'Mottagar2 AB',
            u'dueDate': u'2018-04-25',
            u'bgnum': u'8888885',
            u'regVerificationVersion': 1,
            u'regVerificationLines': [
                {
                    u'text': u'asdfasdf',
                    u'account': py23txtu(self.account1000.id[0]),
                    u'amount': 4000,
                    u'version': 1
                },
                {
                    u'amount': -4000,
                    u'account': py23txtu(self.account3000.id[0]),
                    u'text': u'n\xe5gotannat',
                    u'version': 1
                }
            ]
        }
        # PGnum
        self.invoice3 = {
            u'bankclearing': u'3144',
            u'bankaccount': u'7805569',
            u'invoiceNumber': u'',
            u'invoiceDate': u'',
            u'amount': 100000,
            u'transferDate': u'2011-11-30',
            u'invoiceType': u'debit',
            u'pgnum': u'8377004',
            u'invoiceIdentifierType': u'ocr',
            u'transferMethod': u'pgnum',
            u'message': u'Stipendium',
            u'ocr': u'1234567899',
            u'recipient': u'Mottagar1 AB',
            u'dueDate': u'2018-03-25',
            u'bgnum': u'2374825',
            u'regVerificationVersion': 1,
            u'regVerificationLines': [
                {
                    u'text': u'purchases going up',
                    u'account': py23txtu(self.account2000.id[0]),
                    u'amount': 100000,
                    u'version': 0
                },
                {
                    u'amount': -100000,
                    u'account': py23txtu(self.account3000.id[0]),
                    u'text': u'Supplier debt credit account going up',
                    u'version': 0
                }
            ]
        }

    def test_sorting(self):
        x = blm.accounting.SupplierInvoice(
            org=self.org,
            recipient='a',
            transferMethod='bankaccount',
            invoiceIdentifierType='message',
            dateInvoiceRegistered=1
        )
        y = blm.accounting.SupplierInvoice(
            org=self.org,
            recipient='b',
            transferMethod='bankaccount',
            invoiceIdentifierType='message',
            dateInvoiceRegistered=2
        )

        # We sort secondarily on dateInvoiceRegistered
        ts = [x, y]
        ts.sort(key=blm.accounting.SupplierInvoice.sort_transferDate_key)
        assert ts == [x, y]

        x.transferDate=['2017-02-27']
        ts = [x, y]
        ts.sort(key=blm.accounting.SupplierInvoice.sort_transferDate_key)
        assert ts == [y, x]

        x.transferDate=[]
        y.transferDate=['2017-02-28']
        ts = [x, y]
        ts.sort(key=blm.accounting.SupplierInvoice.sort_transferDate_key)
        assert ts == [x,y]

        x.transferDate=['2017-02-27']
        ts = [x, y]
        ts.sort(key=blm.accounting.SupplierInvoice.sort_transferDate_key)
        assert ts == [x,y]

        x.transferDate=['2017-02-29']
        ts = [x, y]
        ts.sort(key=blm.accounting.SupplierInvoice.sort_transferDate_key)
        assert ts == [y,x]

        y.transferDate=['2017-02-29']
        ts = [x, y]
        ts.sort(key=blm.accounting.SupplierInvoice.sort_transferDate_key)
        assert ts == [x,y]

        # x.dateInvoiceRegistered = y.dateInvoiceRegistered
        # ts = [x, y]
        # ts = ts.sort(key=blm.accounting.SupplierInvoice.sort_transferDate)
        # assert blm.accounting.SupplierInvoice.sort_transferDate(x, y) == 0

    def test_saveSupplierInvoice(self):
        invoice1 = {
            u'amount': 664000,
            u'invoiceIdentifierType': u'message',
            u'transferMethod': u'bgnum',
            u'message': u'Leverans',
            u'recipient': u'Mottagar Corp',
            u'dueDate': u'2017-03-25',
            u'bgnum': u'8888885',
            u'regVerificationLines': None,
            u'regVerificationVersion': None,
        }
        result, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[invoice1])
        s1 = result['supplierInvoice']
        assert s1.amount[0] == Decimal('6640.00')
        assert s1.invoiceState[0] == 'incomplete'
        stoid = str(s1.id[0])

        # Modify the same SupplierInvoice, add a registrationVerification.
        invoice1 = {
            u'invoiceDate': u'2017-03-08',
            u'amount': 654000,
            u'transferDate': u'2017-03-24',
            u'invoiceType': u'debit',
            u'invoiceIdentifierType': u'message',
            u'transferMethod': u'bgnum',
            u'message': u'Leverans',
            u'recipient': u'Mottagar Corp',
            u'dueDate': u'2017-03-25',
            u'bgnum': u'8888885',
            u'regVerificationVersion': 1,
            u'regVerificationLines': [
                {
                    u'text': u'asdfasdf',
                    u'account': py23txtu(self.account1000.id[0]),
                    u'amount': 5000,
                    u'version': 1
                },
                {
                    u'amount': -5000,
                    u'account': py23txtu(self.account2000.id[0]),
                    u'text': u'n\xe5gotannat',
                    u'version': 1
                }
            ]
        }
        result, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[invoice1], toid=[stoid])
        s1 = result['supplierInvoice']
        vId = result['saveVerResult']['id']
        assert s1.registrationVerification[0] == vId
        assert s1.invoiceDate[0] == '2017-03-08'
        assert s1.amount[0] == Decimal('6540.00')
        assert s1.recipient[0] == 'Mottagar Corp'
        rv, = blm.accounting.Verification._query(id=vId).run()
        assert rv.externalRef[0] == str(s1.id[0])
        t1, t2 = rv.transactions
        assert t1.amount[0] == Decimal('50.00')
        assert t2.text[0] == u'n\xe5gotannat'
        # No regVerificationLine adding to SupplierInvoiceProvider.account (supplier debt account)
        # so SI is still incomplete.
        assert s1.invoiceState[0] == 'incomplete'

        # Modify the same SupplierInvoice.
        stoid = str(s1.id[0])
        invoice2 = {
            u'invoiceDate': u'',
            u'amount': 4500,
            u'transferDate': u'2017-04-24',
            u'invoiceType': u'debit',
            u'pgnum': u'',
            u'invoiceIdentifierType': u'message',
            u'transferMethod': u'bgnum',
            u'message': u'Leveransen aer skickad',
            u'ocr': u'',
            u'recipient': u'Mottagar Corp',
            u'dueDate': u'2017-04-25',
            u'bgnum': u'8888885',
            u'regVerificationVersion': 2,
            u'regVerificationLines': [
                {
                    u'text': u'asdf racker',
                    u'account': py23txtu(self.account1000.id[0]),
                    u'amount': 4500,
                    u'version': 2
                },
                {
                    u'amount': -4200,
                    u'account': py23txtu(self.account3000.id[0]),
                    u'text': u'n\xe5gotannat, som sagt',
                    u'version': 2
                },{
                    u'amount': -300,
                    u'account': py23txtu(self.account3000.id[0]),
                    u'text': u'n\xe5goting tredje',
                    u'version': 1
                }
            ]
        }
        invoice3 = copy.deepcopy(invoice2)
        result, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[invoice2], toid=[stoid])
        s2 = result['supplierInvoice']
        vId2 = result['saveVerResult']['id']
        assert s2.registrationVerification[0] == vId2
        assert s2.amount[0] == Decimal('45.00')
        assert s2.invoiceDate == []
        rv, = blm.accounting.Verification._query(id=vId2).run()
        assert rv.externalRef[0] == str(s2.id[0])
        t1, t2, t3 = rv.transactions
        assert t2.amount[0] == Decimal('-42.00')
        assert t3.amount[0] == Decimal('-3.00')
        assert t3.text[0] == u'n\xe5goting tredje'
        # We have accounted against SupplierInvoiceProvider.account (supplier debt account)
        # so the SI should have reached registered status.
        assert s2.invoiceState[0] == 'registered'

        invoice3['invoiceState'] = 'paid'
        result, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[invoice3], toid=[stoid])
        si = result['supplierInvoice']
        assert si.invoiceState[0] == 'paid'
        assert len(si.transaction_date[0]) == 10

    def test_prepareVerification(self):
        r1, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[copy.deepcopy(self.invoice0)])
        si1 = r1['supplierInvoice']
        regVerLines = [
            {
                u'text': u'Transaction text',
                u'account': self.account1000.id[0],
                u'version': 0,
                u'amount': 5000
            },{
                u'text': u'Transaction text 2',
                u'amount': -5000,
                u'version': 0,
                u'account': self.account3000.id[0]
            }
        ]
        regVerVersion = 1
        regVerId = None
        siToid = str(si1.id[0])
        siRegDate = datetime.fromtimestamp(si1.dateInvoiceRegistered[0]).date().isoformat()
        result1 = blm.accounting.prepareVerification(self.org, regVerId, regVerLines, regVerVersion, siToid, siRegDate)

        # Output of prepareVerification should be correct input for saveVerification.
        sVr1, = blm.accounting.createVerification([result1])
        ver1, = blm.accounting.Verification._query(id=sVr1['id']).run()
        assert ver1.number[0] == 1
        assert ver1.transaction_date == [date.today().isoformat()]

        trans1, = blm.accounting.Transaction._query(text='Transaction text').run()
        assert trans1.verification == [ver1]
        assert trans1.version == [0]
        assert trans1.text == ['Transaction text']
        assert trans1.amount == [Decimal('50.00')]

        trans2, = blm.accounting.Transaction._query(text='Transaction text 2').run()
        assert trans2.verification == [ver1]
        assert trans2.version == [0]
        assert trans2.text == ['Transaction text 2']
        assert trans2.amount == [Decimal('-50.00')]

    def test_deleteSupplierInvoice(self):
        result, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[copy.deepcopy(self.invoice0)])
        s0 = result['supplierInvoice']
        assert s0.invoiceState[0] == 'incomplete'
        # Delete should succeed as state 'incomplete', no registrationVerification.
        result = blm.accounting.deleteSupplierInvoice(org=[self.org], supInvList=[s0])
        assert len(result['deleted']) == 1
        assert len(result['untouched']) == 0
        self.commit()
        assert len(blm.accounting.SupplierInvoice._query().run()) == 0

        # For SI with registrationVerification / state = registered the delete should fail.
        i1 = copy.deepcopy(self.invoice1)
        result, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[i1])
        s1 = result['supplierInvoice']
        assert s1.invoiceState[0] == 'registered'
        # Delete should fail b/c there is a registrationVerification.
        result = blm.accounting.deleteSupplierInvoice(org=[self.org], supInvList=[s1])
        assert len(result['deleted']) == 0
        assert len(result['untouched']) == 1
        self.commit()
        s1, = blm.accounting.SupplierInvoice._query().run()

        # Lets test nullifying the reg ver and deleting.
        # i1 was modified by saveSupplierInvoice by popping its regVerificationLines and regVerificationVersion.
        i1['regVerificationLines'] = []
        i1['regVerificationVersion'] = 1
        self.commit()
        result, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[i1], toid=[str(s1.id[0])])
        s1 = result['supplierInvoice']
        # As the regVer has no transactions, the SI should have state incomplete
        assert s1.invoiceState[0] == 'incomplete'
        result = blm.accounting.deleteSupplierInvoice(org=[self.org], supInvList=[s1])
        assert len(result['deleted']) == 1
        assert len(result['untouched']) == 0
        self.commit()
        assert len(blm.accounting.SupplierInvoice._query().run()) == 0

    def test_predictSupplierInvoice(self):
        i1 = copy.deepcopy(self.invoice0)
        i1['invoiceDate']  = u'2017-01-01'
        i1['transferDate'] = u'2017-01-20'
        i1['dueDate']      = u'2017-01-25'
        result, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[i1])
        s1 = result['supplierInvoice']

        i2 = copy.deepcopy(self.invoice0)
        i2['invoiceDate']  = u'2017-02-01'
        i2['transferDate'] = u'2017-02-20'
        i2['dueDate']      = u'2017-02-25'
        result, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[i2])
        s2 = result['supplierInvoice']

        i3 = copy.deepcopy(self.invoice0)
        i3['invoiceDate']  = u'2017-03-01'
        i3['transferDate'] = u'2017-03-20'
        i3['dueDate']      = u'2017-03-25'
        result, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[i3])
        s3 = result['supplierInvoice']

        i4 = copy.deepcopy(self.invoice0)
        i4['invoiceDate']  = u'2017-04-10'
        i4['transferDate'] = u'2017-04-25'
        i4['dueDate']      = u'2017-04-30'
        i4['message']      = u'Odd delivery'
        i4['transferMethod'] = u'bankaccount'
        i4['bankclearing'] = u'8899'
        i4['bankaccount'] = u'987654321'
        result, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[i4])
        s4 = result['supplierInvoice']

        prediction, = blm.accounting.predictSupplierInvoice(org=[self.org], recipient=[self.invoice0['recipient']])
        assert prediction['recipient'] == self.invoice0['recipient']
        assert prediction['transferMethod'] == self.invoice0['transferMethod']
        assert prediction['bgnum'] == self.invoice0['bgnum']
        assert prediction['invoiceIdentifierType'] == self.invoice0['invoiceIdentifierType']
        assert prediction['message'] == self.invoice0['message']

        # Check that dates are in next month, but allow for tweaking.
        assert prediction['invoiceDate'].startswith('2017-05')
        assert prediction['transferDate'].startswith('2017-05')
        assert prediction['dueDate'].startswith('2017-05')

        if 'regVerificationLinesPrediction' in prediction:
            regverlines = prediction.pop('regVerificationLinesPrediction')
            prediction['regVerificationLines'] = regverlines
        result, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[prediction])
        sp1 = result['supplierInvoice']
        p2, = blm.accounting.predictSupplierInvoice(org=[self.org], recipient=[self.invoice0['recipient']])

        assert p2['recipient'] == self.invoice0['recipient']
        assert p2['transferMethod'] == self.invoice0['transferMethod']
        assert p2['bgnum'] == self.invoice0['bgnum']
        assert p2['invoiceIdentifierType'] == self.invoice0['invoiceIdentifierType']
        assert p2['message'] == self.invoice0['message']


    def test_createTransferVerification(self):
        invoice1 = self.invoice1
        invoice2 = self.invoice2
        result1, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[invoice1])
        si1 = result1['supplierInvoice']
        result2, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[invoice2])
        si2 = result2['supplierInvoice']
        #supInvList = [str(si1.id[0]), str(si2.id[0])] # This should work to be useable from client
        supInvList = [si1, si2]
        # Mark as paid
        blm.accounting.setSIState(org=[self.org], supInvList=supInvList, newstate=['paid'])

        result, = blm.accounting.createTransferVerification(org=[self.org], supInvList=supInvList)

        accounted = result['accounted']
        verId = result['verifications'][0]['id']
        # Check all SIs where accounted.
        assert set(accounted) - set(supInvList) == set()
        for si in supInvList:
            assert si.accounted[0] is True
        transferVerification, = blm.accounting.Verification._query(id=verId).run()
        banktrans, = blm.accounting.Transaction._query(verification=verId, account=self.account4000.id[0]).run()
        assert banktrans.amount[0] == Decimal('-90') # (-5000 Ore + -4000 Ore)/100 = -90SEK


    def test_toid20(self):
        testtois = (self.account1000, self.account2000, self.account3000, self.account4000)
        for toi in testtois:
            toid20 = bankgiro.encode_toid20(toi)
            assert len(toid20) == 20
            for c in toid20:
                assert c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567'
            decoded = bankgiro.decode_toid20(toid20)
            assert decoded == str(toi.id[0])
        for toi in testtois:
            assert str(toi.id[0]) == bankgiro.decode_toid20(bankgiro.encode_toid20(toi))


    def test_findToi(self):
        tois = (self.account1000, self.account2000, self.account3000, self.account4000)
        toid20s = [bankgiro.encode_toid20(t) for t in tois]    # map(bankgiro.encode_toid20, tois)
        # If user sends payment orders to Bankgirot (not via eutaxia) the
        # information_to_sender field will contain other things than
        # toid20 encoded toid. We need to protect against that.
        garbage = ['hej', 'räksmörgås', '', 'ALHPTK4UQPYAHCOINEUI', '""', '\\', '\n']
        testtoid20s = garbage + toid20s
        counter = 0
        found = []
        for s in testtoid20s:
            t = bankgiro.findToi(s)
            if t is not None:
                found.append(t)
        # Check that we found all of the valid tois and caught all the errors
        assert len(found) == len(tois)


    def test_bg_transferdate(self):
        si1 = blm.accounting.SupplierInvoice(
            org=self.org,
            recipient='one',
            amount=1,
        )
        self.commit()
        # No transferDate
        assert bankgiro.bg_transferdate(si1) == 'GENAST'
        si1.transferDate = ['2017-09-20'] # a wednesday
        with Time(int(time.mktime(date(2017, 9, 19).timetuple()))) as t:
            assert bankgiro.bg_transferdate(si1) == '170920'
        with Time(int(time.mktime(date(2017, 9, 20).timetuple()))) as t:
            assert bankgiro.bg_transferdate(si1) == 'GENAST'
        with Time(int(time.mktime(date(2017, 9, 21).timetuple()))) as t:
            assert bankgiro.bg_transferdate(si1) == 'GENAST'
        si1.transferDate = ['2017-09-24'] # a sunday
        with Time(int(time.mktime(date(2017, 9, 21).timetuple()))) as t:
            assert bankgiro.bg_transferdate(si1) == '170922'
        with Time(int(time.mktime(date(2017, 9, 22).timetuple()))) as t:
            assert bankgiro.bg_transferdate(si1) == 'GENAST'
        with Time(int(time.mktime(date(2017, 9, 23).timetuple()))) as t:
            assert bankgiro.bg_transferdate(si1) == 'GENAST'
        with Time(int(time.mktime(date(2017, 9, 24).timetuple()))) as t:
            assert bankgiro.bg_transferdate(si1) == 'GENAST'
        with Time(int(time.mktime(date(2017, 9, 25).timetuple()))) as t:
            assert bankgiro.bg_transferdate(si1) == 'GENAST'

    def test_gen_opening_record(self):
        with Time(1494257828) as t:
            line = bankgiro.gen_opening_record(self.bankgiroprovider)
        assert len(line) == 80
        assert line in [
            u'110001234566170508LEVERANTÖRSBETALNINGAR                                        ',
            u'110001234566170508LEVERANTORSBETALNINGAR                                        '
        ]

    def test_gen_payment_record(self):
        si1 = blm.accounting.SupplierInvoice(
            id='591462b6907e1340e0ffbd5a',
            org=self.org,
            recipient='one',
            amount=1,
            transferMethod='bgnum',
            invoiceIdentifierType='message'
        )
        self.commit()
        result, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[self.invoice1], toid=['591462b6907e1340e0ffbd5a'])
        si1 = result['supplierInvoice']
        with Time(int(time.mktime(date(2017, 5, 1).timetuple()))) as t:
            line = bankgiro.gen_payment_record(si1)
        assert len(line) == 80
        assert line == u'14000888888556897456986              000000098000170505     LEKGFNUQPYJUBYH7XVNA'
        with Time(int(time.mktime(date(2017, 6, 1).timetuple()))) as t:
            line = bankgiro.gen_payment_record(si1)
        assert len(line) == 80
        assert line == u'14000888888556897456986              000000098000GENAST     LEKGFNUQPYJUBYH7XVNA'

    def test_gen_information_record(self):
        s1 = self.invoice1
        s1['invoiceIdentifierType'] = 'message'
        s1['message'] = ''.join(["{0!s} bottles of beer on the wall, ".format(i) * 2 + "Take one down, pass it around, " for i in range(99, 0, -1)]) + 'no more bottles of beer!'
        result, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[s1])
        si1 = result['supplierInvoice']
        with Time(int(time.mktime(date(2017, 5, 1).timetuple()))) as t:
             lines = bankgiro.gen_information_record(si1)
        assert 1 <= len(lines) <= 90
        for line in lines:
            #print repr(line)
            assert line[:12] == '250008888885'
            assert len(line[12:62]) == 50
            #print line[12:62]
            assert line[62:].strip() == ''
            assert len(line) == 80

    def test_gen_payment_record_plusgiro(self):
        si1 = blm.accounting.SupplierInvoice(
            id='591462b6907e1340e0ffbd5a',
            org=self.org,
            recipient='one',
            amount=1,
            transferMethod='bgnum',
            invoiceIdentifierType='message'
        )
        self.commit()
        s1 = copy.deepcopy(self.invoice1)
        s1['transferMethod'] = 'pgnum'
        s1['pgnum'] = '47651013'
        result, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[s1], toid=['591462b6907e1340e0ffbd5a'])
        si1 = result['supplierInvoice']
        with Time(int(time.mktime(date(2017, 5, 1).timetuple()))) as t:
            line = bankgiro.gen_payment_record_plusgiro(si1)
        assert len(line) == 80
        assert line == u'54004765101356897456986              000000098000170505     LEKGFNUQPYJUBYH7XVNA'
        with Time(int(time.mktime(date(2017, 6, 1).timetuple()))) as t:
            line = bankgiro.gen_payment_record_plusgiro(si1)
        assert len(line) == 80
        assert line == u'54004765101356897456986              000000098000GENAST     LEKGFNUQPYJUBYH7XVNA'

    def test_gen_information_record_plusgiro(self):
        s1 = self.invoice1
        s1['transferMethod'] = 'pgnum'
        s1['pgnum'] = '47651013'
        s1['invoiceIdentifierType'] = 'message'
        s1['message'] = ''.join(["{0!s} bottles of beer on the wall, ".format(i) * 2 + "Take one down, pass it around, " for i in range(99, 0, -1)]) + 'no more bottles of beer!'
        result, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[s1])
        si1 = result['supplierInvoice']
        with Time(1494257828) as t:
             lines = bankgiro.gen_information_record_plusgiro(si1)
        assert 1 <= len(lines) <= 9
        for line in lines:
            #print repr(line)
            assert line[:12] == '650047651013'
            assert len(line[12:47]) == 35
            #print line[12:47]
            assert line[47:].strip() == ''
            assert len(line) == 80


    def test_gen_account_number_record(self):
        s1 = self.invoice1
        s1['transferMethod'] = 'bankaccount'
        s1['bankclearing'] = '4321'
        s1['bankaccount'] = '47651013'
        result, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[s1])
        si1 = result['supplierInvoice']
        with Time(1494257828) as t:
             line = bankgiro.gen_account_number_record(si1)
        assert len(line) == 80
        assert line[41:].strip() == ''
        assert line == '4000000000184321000047651013 56897456986                                        '

    def test_gen_total_amount_record(self):
        bgprovider = blm.accounting.BankgiroProvider(org=self.org, bgnum=['1234566'])
        line = bankgiro.gen_total_amount_record(
            bankgiroProvider=bgprovider,
            len_supInvList=7,
            totamount=500029900,
            sign=' '
        )
        assert len(line) == 80
        assert line == u'29000123456600000007000500029900                                                '

    def test_gen_seal_opening_record(self):
        h = bankgiro.gen_seal_opening_record()
        assert len(h) == 80
        assert h == '00' + time.strftime('%y%m%d', time.localtime(time.time())) + 'HMAC' + ' ' * 68


    def test_transferOrderBankgiro(self):
        invoice1 = copy.deepcopy(self.invoice1)
        invoice2 = copy.deepcopy(self.invoice2)
        si1 = blm.accounting.SupplierInvoice(
            id='591462b6907e1340e0ffbd5a',
            org=self.org,
            recipient='one',
            amount=1,
            transferMethod='bgnum',
            invoiceIdentifierType='message'
        )
        si2 = blm.accounting.SupplierInvoice(
            id='591462b6907e1340e0ffbd5e',
            org=self.org,
            recipient='two',
            amount=2,
            transferMethod='bgnum',
            invoiceIdentifierType='message'
        )
        self.commit()
        result1, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[invoice1], toid=['591462b6907e1340e0ffbd5a'])
        si1 = result1['supplierInvoice']
        result2, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[invoice2], toid=['591462b6907e1340e0ffbd5e'])
        si2 = result2['supplierInvoice']
        supInvList = [si1, si2]
        with Time(int(time.mktime(date(2017, 5, 1).timetuple()))) as t:
            result, = bankgiro.transferOrderBankgiro(bankgiroProvider=self.bankgiroprovider, supInvList=supInvList)

        fname = os.path.join(os.path.dirname(__file__), 'LB/LBin-test_generateBankgiroFile.txt')
        with open(fname) as f:
            filecontent = f.read()
        assert filecontent == result
        with Time(int(time.mktime(date(2017, 5, 8).timetuple()))) as t:
            result, = bankgiro.transferOrderBankgiro(bankgiroProvider=self.bankgiroprovider, supInvList=supInvList)

        fname = os.path.join(os.path.dirname(__file__), 'LB/LBin-test_generateBankgiroFile-genast.txt')
        with open(fname) as f:
            filecontent = f.read()
        assert filecontent == result


    def test_transferOrderBankgiroRecords(self):
        invoice1 = copy.deepcopy(self.invoice1)
        invoice2 = copy.deepcopy(self.invoice2)
        # Create SIs with predictable toids.
        si1 = blm.accounting.SupplierInvoice(
            id='591462b6907e1340e0ffbd5a',
            org=self.org,
            recipient='one',
            amount=1,
            transferMethod='bgnum',
            invoiceIdentifierType='message'
        )
        si2 = blm.accounting.SupplierInvoice(
            id='591462b6907e1340e0ffbd5e',
            org=self.org,
            recipient='two',
            amount=2,
            transferMethod='bgnum',
            invoiceIdentifierType='message'
        )
        self.commit()
        # Update SIs with reasonable example data.
        result1, = blm.accounting.saveSupplierInvoice(
            org=[self.org],
            invoice=[invoice1],
            toid=['591462b6907e1340e0ffbd5a']
        )
        si1 = result1['supplierInvoice']
        result2, = blm.accounting.saveSupplierInvoice(
            org=[self.org],
            invoice=[invoice2],
            toid=['591462b6907e1340e0ffbd5e']
        )
        si2 = result2['supplierInvoice']
        supInvList = [si1, si2]

        # With payments in the future
        with Time(int(time.mktime(date(2017, 5, 1).timetuple()))) as t:
            result = bankgiro.transferOrderBankgiroRecords(bankgiroProvider=self.bankgiroprovider, supInvList=supInvList)
        fname = os.path.join(os.path.dirname(__file__), 'LB/LBin-test_generateBankgiroFile.txt')
        with open(fname) as f:
            filecontent = f.readlines()

        if PYT3:
            for generatedline, expectedline in zip(result, filecontent):
                assert generatedline == expectedline.strip('\r\n')
        else:
            for generatedline, expectedline in zip(result, filecontent):
                assert generatedline.encode('latin-1', 'replace') == expectedline.strip('\r\n')

        # With payments immediately
        with Time(int(time.mktime(date(2017, 5, 8).timetuple()))) as t:
            result = bankgiro.transferOrderBankgiroRecords(bankgiroProvider=self.bankgiroprovider, supInvList=supInvList)
        fname = os.path.join(os.path.dirname(__file__), 'LB/LBin-test_generateBankgiroFile-genast.txt')
        with open(fname) as f:
            filecontent = f.readlines()

        if PYT3:
            for generatedline, expectedline in zip(result, filecontent):
                assert generatedline == expectedline.strip('\r\n')
        else:
            for generatedline, expectedline in zip(result, filecontent):
                assert generatedline.encode('latin-1', 'replace') == expectedline.strip('\r\n')


    def test_createBgcOrder(self):
        invoice1 = copy.deepcopy(self.invoice1)
        result1, = blm.accounting.saveSupplierInvoice(
            org=[self.org],
            invoice=[invoice1]
        )
        si1 = result1['supplierInvoice']
        with Time(int(time.mktime(date(2017, 5, 8).timetuple()))) as t:
            bgcOrder = blm.accounting.createBgcOrder(
                org=self.org,
                bankgiroProvider=self.bankgiroprovider,
                supInvList=[si1]
            )
            assert bgcOrder.creation_date[0] == Time.time(t)
        for line in bgcOrder.order_unsigned[0].splitlines():
            assert len(line) == 80
            if line[:2] == '11':
                pass
            if line[:2] == '14':
                assert bankgiro.encode_toid20(si1) in line
                assert str(int(si1.amount[0])) in line
                assert 'GENAST' in line
            if line[:2] == 29:
                assert str(int(si1.amount[0])) in line


    def test_signBgcOrder(self):
        # Test python internal hmac algorithm
        invoice1 = copy.deepcopy(self.invoice1)
        result1, = blm.accounting.saveSupplierInvoice(
            org=[self.org],
            invoice=[invoice1]
        )
        si1 = result1['supplierInvoice']
        bgcOrder = blm.accounting.createBgcOrder(
            org=self.org,
            bankgiroProvider=self.bankgiroprovider,
            supInvList=[si1]
        )
        bgcOrder = bankgiro.signBgcOrder(bgcOrder=bgcOrder)
        unsigned = bgcOrder.order_unsigned[0]
        signed = bgcOrder.order_signed[0]
        assert unsigned in signed
        assert signed[:2] == '00'
        assert '\n99' in signed
        if PYT3:
            pass # TODO: find a replacement test/ find out why py2 version fails
        else:
            assert 'ff365893d899291c3bf505fb3175e880'.upper() in signed
        for line in signed.splitlines():
            assert len(line) == 80
            if line[:2] == 99:
                assert 'ff365893d899291c3bf505fb3175e880'.upper() in line


    def test_hmac_sha256_128(self):
        # Tests taken from https://tools.ietf.org/html/draft-ietf-ipsec-ciph-sha-256-01
        if PYT3:
            key = b'0102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f20'
            key = codecs.decode(key, encoding='hex')
            data = b'abc'
            hmac = 'a21b1f5d4cf4f73a4dd939750f7a066a'
            assert bankgiro.hmac_sha256_128(key, data) == hmac

            data = b''.join((
                b"abcdbcdecdefdefgefghfghighijhijk",
                b"ijkljklmklmnlmnomnopnopqabcdbcde",
                b"cdefdefgefghfghighijhijkijkljklm",
                b"klmnlmnomnopnopq"))
            hmac = '470305fc7e40fe34d3eeb3e773d95aab'
            assert bankgiro.hmac_sha256_128(key, data) == hmac

            key = codecs.decode((b'aa' * 32), encoding='hex')
            data = codecs.decode((b'dd' * 50), encoding='hex')
            hmac = 'cdcb1220d1ecccea91e53aba3092f962'
            assert bankgiro.hmac_sha256_128(key, data) == hmac

            key = b''.join((
                b'0102030405060708090a0b0c0d0e0f10',
                b'1112131415161718191a1b1c1d1e1f20',
                b'2122232425'))
            key = codecs.decode(key, encoding='hex')

            data = codecs.decode((b'cd' * 50), encoding='hex')
            hmac =  'd4633c17f6fb8d744c66dee0f8f07455'
            assert bankgiro.hmac_sha256_128(key, data) == hmac

            key = codecs.decode((b'0c' * 32), encoding='hex')
            data = b"Test With Truncation"
            hmac = '7546af01841fc09b1ab9c3749a5f1c17'
            assert bankgiro.hmac_sha256_128(key, data) == hmac
        else:
            key ='0102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f20'.decode('hex')
            data = "abc"
            hmac = 'a21b1f5d4cf4f73a4dd939750f7a066a'
            assert bankgiro.hmac_sha256_128(key, data) == hmac

            data = ''.join((
                "abcdbcdecdefdefgefghfghighijhijk",
                "ijkljklmklmnlmnomnopnopqabcdbcde",
                "cdefdefgefghfghighijhijkijkljklm",
                "klmnlmnomnopnopq"))
            hmac = '470305fc7e40fe34d3eeb3e773d95aab'
            assert bankgiro.hmac_sha256_128(key, data) == hmac

            key = ('aa' * 32).decode('hex')
            data = ('dd' * 50).decode('hex')
            hmac = 'cdcb1220d1ecccea91e53aba3092f962'
            assert bankgiro.hmac_sha256_128(key, data) == hmac

            key = ''.join((
                '0102030405060708090a0b0c0d0e0f10',
                '1112131415161718191a1b1c1d1e1f20',
                '2122232425'
            )).decode('hex')
            data = ('cd' * 50).decode('hex')
            hmac =  'd4633c17f6fb8d744c66dee0f8f07455'
            assert bankgiro.hmac_sha256_128(key, data) == hmac

            key = ('0c' * 32).decode('hex')
            data = "Test With Truncation"
            hmac = '7546af01841fc09b1ab9c3749a5f1c17'
            assert bankgiro.hmac_sha256_128(key, data) == hmac

    @pytest.mark.skipif(not os.path.exists("/dev/bgsigner"), reason='No bgsigner connected.')
    def test_bgsigner(self):
        key = '1234567890ABCDEF1234567890ABCDEF'
        lock = '0123456789ABCDEF01234567'
        message = 'fish slapping dance' * 51
        py_hmac = bankgiro.hmac_sha256_128(key.decode('hex'), message)
        bgsigner_hmac = bankgiro.hmac_sha256_128_bgsigner(lock, message)
        assert len(bgsigner_hmac) == 32
        assert py_hmac == bgsigner_hmac

        message = '00000000'
        py_hmac = bankgiro.hmac_sha256_128(key.decode('hex'), message)
        bgsigner_hmac = bankgiro.hmac_sha256_128_bgsigner(lock, message)
        assert len(py_hmac) == len(bgsigner_hmac) == 32
        assert py_hmac == bgsigner_hmac

        message = ' ' * 80 + '\r\n' * 30  # Whitespace
        py_hmac = bankgiro.hmac_sha256_128(key.decode('hex'), message)
        bgsigner_hmac = bankgiro.hmac_sha256_128_bgsigner(lock, message)
        assert len(bgsigner_hmac) == 32
        assert py_hmac == bgsigner_hmac

    @pytest.mark.skipif(not os.path.exists("/dev/bgsigner"), reason='No bgsigner connected.')
    def test_bgsigner_junk(self):
        key = '1234567890ABCDEF1234567890ABCDEF'
        lock = '0123456789ABCDEF01234567'
        message = '\n'.join((''.join(
            random.choice(string.digits + string.letters + string.punctuation) for _ in range(80))
        ) for _ in range(30))  # Random junk
        py_hmac = bankgiro.hmac_sha256_128(key.decode('hex'), message)
        bgsigner_hmac = bankgiro.hmac_sha256_128_bgsigner(lock, message)
        assert len(py_hmac) == len(bgsigner_hmac) == 32
        assert py_hmac == bgsigner_hmac


    @pytest.mark.skipif(not os.path.exists("/dev/bgsigner"), reason='No bgsigner connected.')
    def test_bgsigner_256truncate(self):
        key = '1234567890ABCDEF1234567890ABCDEF'
        lock = '0123456789ABCDEF01234567'
        message = 'fish slapping dance' * 51
        py_hmac = bankgiro.hmac_sha256_128(key, message)
        bgsigner_hmac = bankgiro.hmac_sha256_128_bgsigner_truncated_256(lock, message)
        assert len(bgsigner_hmac) == 32
        assert py_hmac == bgsigner_hmac


    def test_create_hmac(self):
        message = 'fish slapping dance' * 51
        if PYT3:
            message = codecs.encode(message, 'latin-1')
        hmac_signer = bankgiro.create_hmac(message)
        hmac_software = bankgiro.create_hmac(message, force_software_signer=True)
        assert hmac_signer == hmac_software


    def test_normalize_text(self):
        if PYT3:
            assert bankgiro.normalize_text('Å'.encode('latin-1')) == b']'
            assert bankgiro.normalize_text('Ä'.encode('latin-1')) == b'['
            assert bankgiro.normalize_text('Ö'.encode('latin-1')) == b'\\'
            assert bankgiro.normalize_text('å'.encode('latin-1')) == b'}'
            assert bankgiro.normalize_text('ä'.encode('latin-1')) == b'{'
            assert bankgiro.normalize_text('ö'.encode('latin-1')) == b'|'
            assert bankgiro.normalize_text('É'.encode('latin-1')) == b'@'
            assert bankgiro.normalize_text('é'.encode('latin-1')) == b'`'
            assert bankgiro.normalize_text('Ü'.encode('latin-1')) == b'^'
            assert bankgiro.normalize_text('ü'.encode('latin-1')) == b'~'
            assert bankgiro.normalize_text('\n'.encode('latin-1')) == b''
            assert bankgiro.normalize_text('\n\n\n\r\r\n'.encode('latin-1')) == b''
            s1 = 'One\nAring Å\nAuml Ä\nOuml Ö\naring å\nauml ä\nouml ö\nEacc É\neacc é\nUuml Ü\nuuml ü\nTwo\nThree'
            s1 = s1.encode('latin-1')
            s2 = 'OneAring ]Auml [Ouml \\aring }auml {ouml |Eacc @eacc `Uuml ^uuml ~TwoThree'
            s2 = s2.encode('latin-1')
            assert bankgiro.normalize_text(s1) == s2
            n1 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890_-?;"{}@#$%^&*()_'
            n1 = n1.encode('latin-1')
            assert bankgiro.normalize_text(n1) == n1
        else:
            assert bankgiro.normalize_text(u'Å') == ']'
            assert bankgiro.normalize_text(u'Ä') == '['
            assert bankgiro.normalize_text(u'Ö') == '\\'
            assert bankgiro.normalize_text(u'å') == '}'
            assert bankgiro.normalize_text(u'ä') == '{'
            assert bankgiro.normalize_text(u'ö') == '|'
            assert bankgiro.normalize_text(u'É') == '@'
            assert bankgiro.normalize_text(u'é') == '`'
            assert bankgiro.normalize_text(u'Ü') == '^'
            assert bankgiro.normalize_text(u'ü') == '~'
            assert bankgiro.normalize_text(u'\n') == ''
            assert bankgiro.normalize_text(u'\n\n\n\r\r\n') == ''
            s1 = u'One\nAring Å\nAuml Ä\nOuml Ö\naring å\nauml ä\nouml ö\nEacc É\neacc é\nUuml Ü\nuuml ü\nTwo\nThree'
            s2 = 'OneAring ]Auml [Ouml \\aring }auml {ouml |Eacc @eacc `Uuml ^uuml ~TwoThree'
            assert bankgiro.normalize_text(s1) == s2
            n1 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890_-?;"{}@#$%^&*()_'
            assert bankgiro.normalize_text(n1) == n1


    def test_sealTransferOrder(self):
        fname = os.path.join(os.path.dirname(__file__), 'LB/LBin-test_generateBankgiroFile.txt')
        with open(fname, 'rb') as f:
            sourcecontent = f.read()
        with Time(int(time.mktime(date(2017, 5, 2).timetuple()))) as t:
            result = bankgiro.sealTransferOrder(message=py23txtuc(sourcecontent, 'latin-1'))
        fname = os.path.join(os.path.dirname(__file__), 'LB/LBin-test_sealBankgiroFile.txt')
        with open(fname, 'rb') as f:
            targetcontent = f.read()
        assert result == targetcontent

    def test_createSignedBgcOrder(self):
        invoice1 = copy.deepcopy(self.invoice1)
        invoice2 = copy.deepcopy(self.invoice2)
        si1 = blm.accounting.SupplierInvoice(
            id='591462b6907e1340e0ffbd5a',
            org=self.org,
            recipient='one',
            amount=1,
            transferMethod='bgnum',
            invoiceIdentifierType='message'
        )
        si2 = blm.accounting.SupplierInvoice(
            id='591462b6907e1340e0ffbd5e',
            org=self.org,
            recipient='two',
            amount=2,
            transferMethod='bgnum',
            invoiceIdentifierType='message'
        )
        self.commit()
        result1, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[invoice1], toid=['591462b6907e1340e0ffbd5a'])
        si1 = result1['supplierInvoice']
        result2, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[invoice2], toid=['591462b6907e1340e0ffbd5e'])
        si2 = result2['supplierInvoice']
        supInvList = [si1, si2]
        blm.accounting.enableSIAutomation(supInvList=supInvList)
        assert si1.automated[0]
        assert si2.automated[0]
        signedBgcOrder, = blm.accounting.createSignedBgcOrder(org=[self.org], supInvList=supInvList)
        sealed_message = signedBgcOrder.order_signed[0]
        if not PYT3:
            sealed_message = sealed_message.encode('latin-1')
        for si in supInvList:
            assert bankgiro.encode_toid20(si) in sealed_message

    def test_cancelBgcOrder(self):
        py.test.skip()
        invoice1 = copy.deepcopy(self.invoice1)
        invoice2 = copy.deepcopy(self.invoice2)
        si1 = blm.accounting.SupplierInvoice(
            id='591462b6907e1340e0ffbd5a',
            org=self.org,
            recipient='one',
            amount=1,
            transferMethod='bgnum',
            invoiceIdentifierType='message'
        )
        si2 = blm.accounting.SupplierInvoice(
            id='591462b6907e1340e0ffbd5e',
            org=self.org,
            recipient='two',
            amount=2,
            transferMethod='bgnum',
            invoiceIdentifierType='message'
        )
        self.commit()
        result1, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[invoice1], toid=['591462b6907e1340e0ffbd5a'])
        si1 = result1['supplierInvoice']
        result2, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[invoice2], toid=['591462b6907e1340e0ffbd5e'])
        si2 = result2['supplierInvoice']
        supInvList = [si1, si2]
        blm.accounting.enableSIAutomation(supInvList=supInvList)
        bgcOrder ,= blm.accounting.createSignedBgcOrder(org=[self.org], supInvList=supInvList)
        cancellationOrder = blm.accounting.cancelBgcOrder(bgcOrder=[bgcOrder])
        assert bgcOrder.sent[0] < cancellationOrder.sent[0]


    def test_parseBankgiroResponseSuccess(self):
        bankgiroprovider = blm.accounting.BankgiroProvider(org=self.org, bgnum=['1234566'])
        si1 = blm.accounting.SupplierInvoice(
            id='591462b6907e1340e0ffbd5a',
            org=self.org,
            recipient='one',
            amount=1,
            transferMethod='bgnum',
            invoiceIdentifierType='message'
        )
        si2 = blm.accounting.SupplierInvoice(
            id='591462b6907e1340e0ffbd5e',
            org=self.org,
            recipient='two',
            amount=2,
            transferMethod='bgnum',
            invoiceIdentifierType='message'
        )
        self.commit()
        result1, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[self.invoice1], toid=['591462b6907e1340e0ffbd5a'])
        si1 = result1['supplierInvoice']
        result2, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[self.invoice2], toid=['591462b6907e1340e0ffbd5e'])
        si2 = result2['supplierInvoice']
        si1.invoiceState = ['sent']
        si1.automated = [True]
        si2.invoiceState = ['sent']
        si2.automated = [True]
        self.commit()
        supInvList = [si1, si2]
        fname = os.path.join(os.path.dirname(__file__), 'LB/LBut-test_parseBankgiroResponse.txt')
        if PYT3:
            with open(fname, 'rb') as fh:
                responsefile = fh.read()
        else:
            with open(fname) as fh:
                responsefile = fh.read()
        result = blm.accounting.parseBankgiroResponseSuccess(responsefile=py23txtuc(responsefile, 'latin-1'))
        assert len(result) == 2
        for si in result:
            assert si.invoiceState[0] == 'paid'
            assert si.accounted[0]
            ver, = blm.TO._query(id=si.transferVerification[0]).run()
            assert len(ver.transactions) > 2


    def test_fakeBGC_cycle(self):
        r1, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[copy.deepcopy(self.invoice1)])
        si1 = r1['supplierInvoice']
        r2, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[copy.deepcopy(self.invoice2)])
        si2 = r2['supplierInvoice']
        blm.accounting.enableSIAutomation(supInvList=[si1, si2])
        bgcOrder, = blm.accounting.createSignedBgcOrder(org=[self.org], supInvList=[si1, si2])
        order_signed = bgcOrder.order_signed[0]
        order_signed = order_signed.encode('latin-1')
        lbin = order_signed
        si1.invoiceState = ['sent']
        si2.invoiceState = ['sent']
        self.commit()

        from accounting.test.fake_bg_response import fakeResponseSuccess
        lbout = fakeResponseSuccess(lbin.decode().splitlines(True))
        result = blm.accounting.parseBankgiroResponseSuccess(responsefile = ''.join(lbout))
        assert len(result) == 2
        for si in result:
            assert si.invoiceState[0] == 'paid'


    def test_fakeBGC_cycle_rejected(self):
        r1, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[copy.deepcopy(self.invoice1)])
        si1 = r1['supplierInvoice']
        r2, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[copy.deepcopy(self.invoice2)])
        si2 = r2['supplierInvoice']
        blm.accounting.enableSIAutomation(supInvList=[si1, si2])
        bgcOrder, = blm.accounting.createSignedBgcOrder(org=[self.org], supInvList=[si1, si2])
        order_signed = bgcOrder.order_signed[0]
        order_signed = order_signed.encode('latin-1')
        lbin = order_signed
        si1.invoiceState = ['sent']
        si2.invoiceState = ['sent']
        self.commit()

        from accounting.test.fake_bg_response import fakeResponseRejected
        lbout = fakeResponseRejected(lbin.decode().splitlines(True))
        result = blm.accounting.parseBankgiroResponseRejected(responsefile=''.join(lbout))
        for si in result:
            assert si.invoiceState[0] == 'rejected'
            assert si.rejected_log[0] == u'MTRV0082 Stopped after balance check inquiry. Contact your bank.'
            assert si.automated[0] is True
        assert len(result) == 2


    def test_setSIState(self):
        i1 = self.invoice1
        i1['transferDate'] = py23txtu((date.today() + timedelta(days=1)).isoformat()) # Transfer tomorrow.
        result1, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[i1])
        si1 = result1['supplierInvoice']
        result2, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[self.invoice2])
        si2 = result2['supplierInvoice']
        self.commit()
        assert si1.invoiceState[0] == 'registered'
        assert si2.invoiceState[0] == 'registered'

        self.pushnewctx()
        self.ctx.setUser(self.payer)

        si1, = blm.TO._query(id=si1).run()
        si2, = blm.TO._query(id=si2).run()

        # registered -> paid should work.
        blm.accounting.setSIState(org=[self.org], supInvList=[si2], newstate=['paid'])
        assert si2.invoiceState[0] == 'paid'

        # paid -> scheduled should NOT work.
        blm.accounting.setSIState(org=[self.org], supInvList=[si1, si2], newstate=['scheduled'])
        assert si2.invoiceState[0] == 'paid'

        # paid -> registered should work (unless automated).
        assert si2.automated[0] is False
        blm.accounting.setSIState(org=[self.org], supInvList=[si2], newstate=['registered'])
        assert si2.invoiceState[0] == 'registered'

    def test_enableSIAutomation(self):
        sr1, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[copy.deepcopy(self.invoice1)])
        si1 = sr1['supplierInvoice']
        result1 = blm.accounting.enableSIAutomation(supInvList=[si1])
        assert si1.automated[0]
        assert si1.invoiceState[0] == 'registered'

    def test_disableSIAutomation(self):
        sr1, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[copy.deepcopy(self.invoice1)])
        si1 = sr1['supplierInvoice']
        enable = blm.accounting.enableSIAutomation(supInvList=[si1])
        assert si1.automated[0]
        resutl1 = blm.accounting.disableSIAutomation(org=[self.org], supInvList=[si1])

    def test_automation(self):
        # Try moving between states
        result1, = blm.accounting.saveSupplierInvoice(
            org=[self.org], invoice=[copy.deepcopy(self.invoice1)])
        si1 = result1['supplierInvoice']
        result2, = blm.accounting.saveSupplierInvoice(
            org=[self.org], invoice=[copy.deepcopy(self.invoice2)])
        si2 = result2['supplierInvoice']
        self.commit()
        assert si1.invoiceState[0] == 'registered'
        assert si2.invoiceState[0] == 'registered'

        self.pushnewctx()
        self.ctx.setUser(self.payer)

        si1, = blm.TO._query(id=si1).run()
        si2, = blm.TO._query(id=si2).run()

        # Try to schedule both
        result = blm.accounting.enableSIAutomation(supInvList=[si1, si2])
        assert result == {'updated': [si1, si2],
                          'complaints': []}
        self.commit()

        si1, = blm.TO._query(id=si1).run()
        si2, = blm.TO._query(id=si2).run()

        assert si1.invoiceState[0] == 'registered'
        assert si2.invoiceState[0] == 'registered'
        assert si1.automated[0]
        assert si2.automated[0]

        si1, = blm.TO._query(id=si1).run()
        si2, = blm.TO._query(id=si2).run()

        # Unschedule (back to registered)
        result = blm.accounting.disableSIAutomation(org=[self.org],
                                                    supInvList=[si1, si2])
        assert result == {'selected': 2,
                          'updated': 2,
                          'complaints': []}
        self.commit()
        assert si1.invoiceState[0] == 'registered'
        assert si2.invoiceState[0] == 'registered'
        assert not si1.automated[0]
        assert not si2.automated[0]

    def test_gen_cfp_po3_mh00(self):
        result = plusgiro.gen_cfp_po3_mh00(
            org=self.org,
            sending_bank_account=self.provider.plusgiro_sending_bank_account[0]
        )
        assert result == 'MH00        5164005810            44580231  SEK      SEK                        '
        assert len(result) == 80

    def test_gen_cfp_po3_pi00(self):
        # To Plusgiro number
        i3 = copy.deepcopy(self.invoice3)
        result1, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[i3])
        si1 = result1['supplierInvoice']
        self.commit()
        result = plusgiro.gen_cfp_po3_pi00(supplierInvoice=[si1])
        assert result == 'PI0000     8377004      2011113000000001000001234567899                         '
        assert len(result) == 80

        # To Bankgiro number
        i3['transferMethod'] = 'bgnum'
        i3['ocr'] = '1111111116'
        result1, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[i3], toid=[str(si1.id[0])])
        si1 = result1['supplierInvoice']
        result = plusgiro.gen_cfp_po3_pi00(supplierInvoice=[si1])
        assert result == 'PI0005     2374825      2011113000000001000001111111116                         '
        assert len(result) == 80

        # To Bank account
        i3['transferMethod'] = 'bankaccount'
        i3['invoiceIdentifierType'] = 'message'
        result1, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[i3], toid=[str(si1.id[0])])
        si1 = result1['supplierInvoice']
        result = plusgiro.gen_cfp_po3_pi00(supplierInvoice=[si1])
        assert result == 'PI00093144 7805569      201111300000000100000Stipendium                         '
        assert len(result) == 80

        # To Plusgiro number without explicit transferDate
        i3 = copy.deepcopy(self.invoice3)
        i3['transferDate'] = ''
        result1, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[i3])
        si4 = result1['supplierInvoice']
        self.commit()
        with Time(int(time.mktime(date(2011, 11, 30).timetuple()))) as t:
            result = plusgiro.gen_cfp_po3_pi00(supplierInvoice=[si4])
        assert result == 'PI0000     8377004      2011113000000001000001234567899                         '
        assert len(result) == 80

    def test_gen_cfp_po3_ba00(self):
        # Out payment reference (here be TOID)
        i3 = copy.deepcopy(self.invoice3)
        result1, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[i3])
        si1 = result1['supplierInvoice']
        self.commit()
        result = plusgiro.gen_cfp_po3_ba00(supplierInvoice=[si1])
        assert result[:4] == 'BA00'
        assert result.find(str(si1.id[0]))
        assert len(result) == 80

    def test_gen_cfp_po3_bm99(self):
        # To Plusgiro number with OCR
        i3 = copy.deepcopy(self.invoice3)
        result1, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[i3])
        si1 = result1['supplierInvoice']
        self.commit()
        result = plusgiro.gen_cfp_po3_bm99(supplierInvoice=[si1])
        assert result == []

        # To Plusgiro number with message
        i3 = copy.deepcopy(self.invoice3)
        i3['invoiceIdentifierType'] = 'message'
        i3['message'] = ''.join(["{0!s} bottles of beer on the wall, ".format(i) * 2 + "Take one down, pass it around, " for i in range(99, 0, -1)]) + 'no more bottles of beer!'
        result1, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[i3])
        si1 = result1['supplierInvoice']
        self.commit()
        result = plusgiro.gen_cfp_po3_bm99(supplierInvoice=[si1])
        assert len(result) == 5

        # To Bankgiro number with OCR
        i3 = copy.deepcopy(self.invoice3)
        i3['transferMethod'] = 'bgnum'
        result1, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[i3], toid=[str(si1.id[0])])
        si1 = result1['supplierInvoice']
        result = plusgiro.gen_cfp_po3_bm99(supplierInvoice=[si1])
        assert result == []

        # To Bankgiro number with message
        i3 = copy.deepcopy(self.invoice3)
        i3['invoiceIdentifierType'] = 'message'
        i3['message'] = ''.join(["{0!s} bottles of beer on the wall, ".format(i) * 2 + "Take one down, pass it around, " for i in range(99, 0, -1)]) + 'no more bottles of beer!'
        result1, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[i3])
        si1 = result1['supplierInvoice']
        self.commit()
        result = plusgiro.gen_cfp_po3_bm99(supplierInvoice=[si1])
        assert len(result) == 5

        # To Bank account
        i3['transferMethod'] = 'bankaccount'
        i3['invoiceIdentifierType'] = 'message'
        result1, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[i3], toid=[str(si1.id[0])])
        si1 = result1['supplierInvoice']
        result = plusgiro.gen_cfp_po3_bm99(supplierInvoice=[si1])
        assert result == []

    def test_gen_cfp_po3_mt00(self):
        # To Plusgiro number
        i3 = copy.deepcopy(self.invoice3)
        i3['amount'] = '2700'
        result1, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[i3])
        si1 = result1['supplierInvoice']
        # To Bankgiro number
        i3 = copy.deepcopy(self.invoice3)
        i3['transferMethod'] = 'bgnum'
        i3['amount'] = '2300'
        result1, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[i3])
        si2 = result1['supplierInvoice']
        result = plusgiro.gen_cfp_po3_mt00(supInvList=[si1, si2])
        assert result == 'MT00                         0000002000000000005000                             '
        assert len(result) == 80

    def test_generatePlusgiroRecords(self):
        # To Plusgiro number with OCR
        i3 = copy.deepcopy(self.invoice3)
        result1, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[i3])
        si1 = result1['supplierInvoice']

        # To Plusgiro number with message
        i3 = copy.deepcopy(self.invoice3)
        i3['invoiceIdentifierType'] = 'message'
        i3['message'] = ''.join(["{0!s} bottles of beer on the wall, ".format(i) * 2 + "Take one down, pass it around, " for i in range(99, 0, -1)]) + 'no more bottles of beer!'
        result2, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[i3])
        si2 = result2['supplierInvoice']


        # To Bankgiro number with OCR
        i3 = copy.deepcopy(self.invoice3)
        i3['transferMethod'] = 'bgnum'
        result3, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[i3], toid=[str(si1.id[0])])
        si3 = result3['supplierInvoice']

        # To Bankgiro number with message
        i3 = copy.deepcopy(self.invoice3)
        i3['invoiceIdentifierType'] = 'message'
        i3['message'] = ''.join(["{0!s} bottles of beer on the wall, ".format(i) * 2 + "Take one down, pass it around, " for i in range(99, 0, -1)]) + 'no more bottles of beer!'
        result4, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[i3])
        si4 = result4['supplierInvoice']

        # To Bank account
        i3['transferMethod'] = 'bankaccount'
        i3['invoiceIdentifierType'] = 'message'
        result5, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[i3], toid=[str(si1.id[0])])
        si5 = result5['supplierInvoice']

        self.commit()

        result = plusgiro.generatePlusgiroRecords(
            org=self.org,
            sending_bank_account=self.provider.plusgiro_sending_bank_account,
            supInvList=[si1, si2, si3, si4, si5]
        )
        fname = os.path.join(os.path.dirname(__file__), 'cfp/PG_TESTFIL_PO3_CFPinr.txt')
        with open(fname, 'rb') as fh:
            targetfile = fh.readlines()

        # TODO: asserts!
        #import pprint
        #pprint.pprint(result)
        #for generated, target in zip(result, targetfile):
        #    assert generated == target.rstrip('\n')

        resultfile, = blm.accounting.generatePlusgiroFile(org=[self.org], supInvList=[si1, si2, si3, si4, si5])
        # Hard to test as we include toid in file.

        #fname = os.path.join(os.path.dirname(__file__), 'cfp/generated_manually_checked.txt')
        #with open(fname) as fh:
        #    targetfile = fh.readlines()
        #for generated, target in zip(resultfile.splitlines(True), targetfile):
        #    print generated
        #    print target
        #    assert generated == target


class TestBgcReport(BLMTests):

    def setup_method(self, method):
        super(TestBgcReport, self).setup_method(method)
        self.org = blm.accounting.Org(subscriptionLevel='subscriber', orgnum='5164005810')
        self.accounting = blm.accounting.Accounting(org=self.org)
        self.account1000 = blm.accounting.Account(accounting=self.accounting, number='1000')
        self.account2000 = blm.accounting.Account(accounting=self.accounting, number='2000')
        self.account3000 = blm.accounting.Account(accounting=self.accounting, number='3000')
        self.account4000 = blm.accounting.Account(accounting=self.accounting, number='4000')
        self.series = blm.accounting.VerificationSeries(accounting=self.accounting, name='A')
        self.provider = blm.accounting.SupplierInvoiceProvider(org=self.org, series='A', account='3000', bank_account='4000', plusgiro_sending_bank_account='44580231')
        self.bankgiroprovider = blm.accounting.BankgiroProvider(org=self.org, bgnum=['1234566'])
        self.invoice1 = {
            u'amount': 664000,
            u'invoiceIdentifierType': u'message',
            u'transferMethod': u'bgnum',
            u'message': u'Leverans',
            u'recipient': u'Mottagare AB',
            u'bgnum': u'8888885',
            u'regVerificationLines': None,
            u'regVerificationVersion': None,
        }

    def test_process_data(self, monkeypatch):
        r1, = blm.accounting.saveSupplierInvoice(org=[self.org], invoice=[copy.deepcopy(self.invoice1)])
        si1 = r1['supplierInvoice']
        def foo(text):
            return [si1]
        multiline = '1'*47
        bgcReport = blm.accounting.BgcReport(multiline=[multiline])
        self.commit()
        monkeypatch.setattr(blm.accounting, 'parseBankgiroResponseSuccess', foo)
        bgcReport.process_data()
        assert bgcReport.supplierInvoices == [si1]


class TestBootstrap(BLMTests):

    def check_bootstrap(self):
        blm.accounting.bootstrap()
        ugs = blm.accounting.UG._query(name='public').run()
        assert len(ugs) == 1
        assert ugs[0].name == ['public']

        oe = blm.accounting.Org._query().run()
        assert len(oe) == 1
        assert oe[0].orgnum == [blm.accounting.Org._oeOrgNum]

        #assert blm.accounting.ChartOfAccounts._query().run()
        assert blm.accounting.VatCode._query().run()

    def test_bootstrap(self):
        self.check_bootstrap()
        self.check_bootstrap() # reentrant


class TestUpgrade(BLMTests):

    def test_reentrant(self):
        blm.accounting.upgrade()  # don't explode
        blm.accounting.upgrade()  # reentrant


