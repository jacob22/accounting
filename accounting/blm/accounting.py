# -*- coding: utf-8 -*-
from __future__ import absolute_import

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
if sys.version_info > (3,0):
    PYT3 = True
else:
    PYT3 = False

import copy
import ssl, tempfile
import bson, dateutil.relativedelta, datetime, decimal, functools, \
    logging, os, re, time, uuid
from bson.objectid import ObjectId, InvalidId
from email.utils import formataddr, getaddresses
from accounting import config, luhn, mail, templating
import pytransact.queryops as Q
import pytransact.runtime as ri
from pytransact import exceptions, spickle
from pytransact.iterate import uniq
from pytransact.object.model import *
from blm import fundamental
import OpenSSL.crypto
import itertools

try:
    from itertools import izip as zip
except ImportError:
    pass

import collections
import accounting.sftp_bgc as sftp_bgc
from accounting import bankgiro, plusgiro, freja
from members.incoming_payments import LBParser as LBSuccessParser
from members.incoming_payments import LBRejectedParser
from members.incoming_payments import LBStoppedPaymentsParser


log = logging.getLogger('blm.accounting')

date_re = r'\d{4}-\d{2}-\d{2}'


def find_org(toi):
    try:
        toi, = toi
    except ValueError:
        pass

    if isinstance(toi, Org):
        return toi

    # order is important!
    for attr in '''org accounting verification dimension account
                   account_balance supplierInvoice'''.split():
        if hasattr(toi, attr):
            return find_org(getattr(toi, attr)[0])


def currentUserHasRole(toi, *roles, **kw):
    user = kw.get('user', ri.getClientUser())
    if user is not None:  # base can always do everything
        try:
            org = find_org(toi)
        except IndexError:
            # Anybody can do anything with orphan TOIs. Should
            # only happen in tests.
            pass
        else:
            # For APIUsers:
            if set(roles) & set(getattr(user, 'roles', [])):
                return user in org.ug[0].users
            # For Users:
            for role in roles:
                if user in getattr(org, role, []):
                    break
            else:
                return False
    return True


def requireRoles(*roles):
    """Raise error if user is not member of a role in `roles' in the owning
    Org."""
    def _(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kw):
            if not currentUserHasRole(self, *roles):
                raise exceptions.cPermissionError('Permission denied: %s, %s' %
                                                  (self, func.__name__))
            return func(self, *args, **kw)
        return wrapper
    return _


class SubscriptionLevel(Enum()):
    values = 'subscriber', 'pg'


class StringNotEmpty(String):

    def on_create(attr, value, self):
        return [v for v in value if v]
    on_update = on_create


def normalize_pgnum(value):
    value = ''.join(c for c in value if c.isdigit())
    if luhn.luhn_checksum(value) != 0:
        raise ValueError("Incorrect check digit: %s should be %s" % (
            value, luhn.luhn_checksum(value[:-1]+'0'))
        )
    return value


def normalize_orgnum(value):
    digits = [c for c in value if c.isdigit()]
    digits[6:6] = '-'
    return ''.join(digits)


# Also used for BGNum
class PGNum(String()):

    def on_create(attr, value, toi):
        return [normalize_pgnum(v) for v in value]
    on_update = on_create


class Client(fundamental.AccessHolder):

    _privilege_attrs = ['ugs']

    class ugs(Relation(Weak())):
        related = 'UG.users'

    class name(String()):
        pass

    class lastAccess(Timestamp(Quantity(1))):
        default = [0]

    def canWrite(self, user, attrName):
        return user == self and attrName in {'set_name', 'openid'}

    def _setAllowRead(self):
        with ri.setuid():
            self.allowRead = [self] + [ug for ug in self.ugs if
                                       'public' not in ug.name]

    def on_create(self):
        self.ugs = self.ugs + UG._query(name='public').run()
        self._setAllowRead()

    def on_update(self, newAttrValues):
        self._update(newAttrValues)
        self._setAllowRead()

    @method(None)
    def set_name(self, name=String(Quantity(1))):
        with ri.setuid():
            self.name = name


class User(Client):

    class openid(String()):
        pass

    class emailAddress(String()):
        pass

    class personNum(String(QuantityMax(1))):
        pass

    def canWrite(self, user, attrName):
        if user == self and attrName == 'set_data':
            return True
        return super(User, self).canWrite(user, attrName)

    @method(None)
    def set_data(self, data=Serializable()):
        with ri.setuid():
            self(**data[0])


class APIUser(Client):

    class key(String()):
        pass

    class roles(String()):
        default = ['storekeepers', 'invoicesenders']

    @method(None)
    def newkey(self):
        self.key = [str(uuid.UUID(bytes=os.urandom(16), version=4))]

    def on_create(self):
        self.newkey()


@method(ToiRef(ToiType(User), Quantity(1)))
def registerUser(name=String(), emailAddress=String(), openid=String()):
    return [User(name=name, emailAddress=emailAddress, openid=openid)]


class UG(fundamental.AccessHolder):

    class name(String(QuantityMax(1), Unchangeable())):

        def on_create(attr, value, self):
            if value and ri.getClientUser():
                raise exceptions.cBlmError('Only super user can give UGs a name.')
            return value

    class users(Relation(Weak())):
        related = Client.ugs

    @method(Serializable(Quantity(1)))
    def getUsers(self):
        return [{'users': [str(user.id[0]) for user in self.users]}]

    def on_create(self):
        self.allowRead.add(self)


class Invitation(TO):

    class emailTo(String(Quantity(1))):
        pass

    class inviteCode(String(post=Quantity(1))):
        def on_create(attr, value, self):
            return [str(uuid.uuid4())]

    class org(ToiRef(ToiType('Org'),Quantity(1))):
        pass

    class groups(String()):
        default = ['admins', 'accountants', 'storekeepers', 'members',
                   'ticketcheckers']

    class accepted(Bool(Quantity(1))):
        default = [False]

    class acceptedBy(ToiRef(ToiType(User), QuantityMax(1))):
        pass

    def on_create(self):
        # XXX Should use template
        self.allowRead = self.org[0].ug
        text = ("You have been invited to the organisation %(org)s in Eutaxia admin.\n"
                 "\n"
                 "Follow this link to join: %(link)s\n")

        link = config.config.get('accounting', 'baseurl').rstrip('/') + '/register?code=' + self.inviteCode[0]

        text %= {'org': self.org[0].name[0], 'link': link}
        subject = 'Welcome to admin.eutaxia.eu'
        to = self.emailTo.value[0]

        user = ri.getClientUser()
        headers = dict(subject=subject, to=to, envfrom=str(self.org[0].id[0]))
        identity = None
        if user:
            identity = str(user.id[0])
            if user.emailAddress:
                headers['Reply-to'] = formataddr((user.name[0], user.emailAddress[0]))
                headers['From'] = formataddr((user.name[0],
                                              'noreply@' + config.config.get('accounting', 'smtp_domain')))

        mail.sendmail(*mail.makemail(text, **headers), identity=identity)

    @method(None)
    def accept(self, user=ToiRef(ToiType(User), Quantity(1))):
        if self.accepted[0]:
            if self.acceptedBy != user:
                raise cBlmError('This invitation has already been accepted')
            else:
                return
        user = user[0]
        for ug in self.org[0].ug:
            if ug not in user.ugs:
                user(ugs=user.ugs + [ug])
        for group in self.groups or self.groups.default:
            attr = getattr(self.org[0], group)
            attr.add(user)
        self.accepted = [True]
        self.acceptedBy = [user]


class PaymentProvider(TO):

    requiredSubscriptionLevel = None

    class org(ToiRef(ToiType('Org'), Quantity(1))):
        pass

    class account(StringNotEmpty()):
        pass

    class series(StringNotEmpty()):
        pass

    class currency(String(post=Quantity(1))):
        #default = ['SEK']

        def on_create(attr, value, self):
            if not value:
                return ['SEK']
            return value

    def canWrite(self, user, attrName):
        return currentUserHasRole(self, 'admins', user=user)

    @requireRoles('admins')
    def on_create(self):
        if (self.requiredSubscriptionLevel and
            self.requiredSubscriptionLevel not in self.org[0].subscriptionLevel[:]):
            raise cBlmError('The organisation does not meet the criteria to '
                            'create this kind of provider')

        self.allowRead = self.org[0].ug
        for acct in self.org[0].current_accounting:
            acct.ensureSeries(ensureOne=False)

    def on_delete(self):
        import members  # NOQA
        import blm.members
        for payment in blm.members.Payment._query(paymentProvider=self).run():
            payment.paymentProvider = []


class ManualProvider(PaymentProvider):

    pass


class SimulatorProvider(PaymentProvider):

    pass


class PlusgiroProvider(PaymentProvider):

    requiredSubscriptionLevel = 'subscriber'

    class pgnum(PGNum(QuantityMax(1))):
        pass

    class pgnum_real(PGNum(QuantityMax(1))):
        pass


class BankgiroProvider(PaymentProvider):

    requiredSubscriptionLevel = 'subscriber'

    class bgnum(PGNum(QuantityMax(1))):
        pass


class PaysonProvider(PaymentProvider):

    requiredSubscriptionLevel = 'subscriber'

    class apiUserId(String(Quantity(1))):
        pass

    class apiPassword(String(Quantity(1))):
        pass

    class receiverEmail(String(Quantity(1))):
        pass


class SeqrProvider(PaymentProvider):

    requiredSubscriptionLevel = 'subscriber'

    class soapUrl(String(Quantity(1))):
        default = ['https://extdev.seqr.com/extclientproxy/service/v2?wsdl']

    class principalId(String(Quantity(1))):
        pass

    class password(String(Quantity(1))):
        pass


class StripeProvider(PaymentProvider):

    requiredSubscriptionLevel = 'subscriber'

    class access_token(String(Quantity(1))):
        pass

    class display_name(String(QuantityMax(1))):
        pass

    class stripe_id(String(QuantityMax(1))):
        pass

    class stripe_email(String(QuantityMax(1))):
        pass

    class stripe_publishable_key(String(QuantityMax(1))):
        pass

    class refresh_token(String(QuantityMax(1))):
        pass


class SwishProvider(PaymentProvider):

    requiredSubscriptionLevel = 'subscriber'

    TEST_PKEY = '''\
-----BEGIN RSA PRIVATE KEY-----
MIIJKAIBAAKCAgEA2oOkR7XLqv4+KiZm7nTdYbgVGCZhUmDU42Gy/WPwrb5tuB85
vIHIR5ceQe/Ie1XOhncEUYUNBaY7A2gMKNNwc8ktv+7PqWV+qRvWlMTvBxYTunQM
q7+64fkwcXLmWiiRs0+caiq7pjcBoHOHMpQRr6BrD0HufuUKJO/vBSBNb3V2FF6j
7d+JxJNPxUy7vqpNddL/M9mHxrCUps0Scr6fX17Xsq8qlb0xjK5BAsVVCTq1NqOb
ygk/teWMQx6kkRieetXUuc4HlWsSQsZc8ap09OkRjODYOHT8I4uZvBaXhoiv95bJ
LebfnKRucl0trYgLSlgdAsinlQ/mHoXoYxNSjpPIfmcfTwD3qp89PufcNgSaEZMq
++4RxmQBD9jyy5C226P4o6JT92HikRWn9Ah+ZKh+GuRsCKFlRtxA5HZdi1HMY9cX
elrSUZVFVnCdT1glaVlagCaXaMtTHw6CVGkYk5pEJM4C3qPfBoAn0LdAn7dlGzrp
ZyGdiB2iDVq6zDxjJmd5yeaj6bq7/rbcEXHzEBVcPz56npscFW/890kUiOzzDW7k
XKudTkO9E1mMDvdIwrosNqrRmbTH3IWvQms8Xz4Yu3SlbfGsDJme/QHMyvVc/RfR
4CAWtn9kORFbcv5waC9FFAqhSw1NRVH4HIz/TE9+w9DhEWFr5bby/A9zf6UCAwEA
AQKCAgEAzxWk8eTjIKkUBuQf9mrAh2RqcVmmL+jeuKMVezhklnP7DVxiXjjsspQP
s9NnvyMBt8NBT3R1c94m3UKVC3fegYyuE9Bh8xrh36gnQxQjpyaQCcsDWx04IgID
m/CVR+pcsn+HL8JR1eMZYpM6FH/pBvVToMEOIioz4++TKNuFJ1U9U26hksSfjrFB
Dy16W+aPxFLzUpMcLvuX1UBR9HadGUgLySZiiEglljpqGBMlVLrTk/WXpe//9gWW
WOHIek3Hm4fcsz4DR+KSCsBswwaVEqly3X0UzORpM9KQHoWWkoQlp9G51QuQ7aWT
mkSeDm/4qzs4OzQoRYcswc6L/qEIQaA3kR/6u1GVUI3JOMKTsdQgRIiRZekJe/j9
iylrG/vEfDkyDX+Xq45a21x/7wxpVNgE+hu/n24X41U7kHg6Hrq3WCxbanKTBiNp
GdCBqR8a7U5wF6g2vy0o450g45ukLeNK352xufkZIck3/V+M7eXxD+KCaogglcbl
z2uaGB59jAAPNJmzNqZHAKx3OsfWfILoPAOUjQ+Qf7+OzJLvEf/yqfbaBE+xLp2y
8qOJZPZHqftH2Maan7dHhIqIRE1QSPI6KH5SR41wGahjChCEqrtTeVKShb9JgbDx
0rX/I3UN8TIujJ9adAm73ImnIqux4QGy6tInXy/ROSjKhfiMTkECggEBAPZaXVcq
hmax7u84MEukMbxo/HFDkrRgj0pu47gTf3ErWhq42najtcTYp1yqq53s9eoA/ZT+
Nbl5XNx36kUCTgr9rrlr+vnba0nVBTMihDfeGn5XI64Gcdss05BNbeqeTTGZrMQZ
zCNvXWk3j2c5dQQH1kEtenyrH/Vz7CZxwJ1uTFBLOsQQ+7FDppcci5Fg7AmywVMX
vsOcsHqpIoYW7qcJzxRLxzEIPiPT17YtDlUPKYZbN7Ebq8OZ0ULGE/n5Py91wErr
ieJpCYDji9QfieHltrLUI1svBL6w5Dke4AMaGno3Rh5116OBozn/p/4abgL6gCyC
4lNxzAWAEAfo65ECggEBAOMSMxWraRQ1bUMOoTXrGCMrYSBhEVSiff8sReCasEZe
x9FpiWIkBjfotHWdC4+RW3tGh3bAf3YosCMUkWbAcAhuohuB9pB6fBMQaBWvnI8i
P1K4c5SfISuX/b1TWmvU4MFjaOFswrVyLvrxunEBUfxk8Nfo0qVe94PJ4NledY+P
D/jfn8uzKBk7tXbL6XrbQGj56p627WTMY1aVNuX8bqw6QwJm+j/cfPcLnIO+l8bc
aGzob7Vi5AE/7ut1sI1tljfqeHNw61XynLWd6nfJn5jL7f6Ooy+fBOQ0FccpIkmI
tCZMAtz34J+SotEjlIkjQtS71xpP4CzZ//91ilFvgNUCggEAMxmHZv9BJage4awM
CISkdGpqgqv7kEK/NjdOMO6KbtUJOaXCWv2WRKCUBpq4QmfWkpVmBDO+vRw5cNnG
1E2oFouMZJXLV2x2EriG/ZZZSqVdZXt5wS1BDK99qt8Ev7faV0GDHqIjP+5nt914
d3bpmM5vWNGwKI/ubyF+iHLr+zvXxIf2RpknPBvGQG4BXUR3cYOMqkmwni6wRKE0
sg+rrSZRt+oIBVmqWhAlHHq4EFi2ylG9eZU9ybLsPyeLGTzkKFoKav/0d+xFtmB8
rqFkHmFhxjJOqylTmKJklJyc5sfRWiyA9OyIsDfBvdQT6pdc3m1LjPARNjHSmgl4
Scu8oQKCAQB6eRJ8mZtvfvGTvYxOHKNENN2KLVC/qXTz8Nkvr79r9SspVBb5jBye
gzDyTuYxZWFGOGBQOLuG66M1CJ70IM9MfP+KfqqSer35OlwpdjKnMP2ejEYq3zlw
3eXJ++9FQeiH5ipni9XpL9EPINpCoUerLnaIvdb/wx0VRAm2tDAMYklnHpZ9s//o
vD+/93PTA/bVqBZXzKp2N5dM1+ZoXaMD2djSruBDGZV9WhHtLRuH8tGQDD5UQyZf
VjBzZ2L2pSjkt96HxVvpW5YSjz4rpeAi9btEFYMG6Gom+8DTTuhjaQxhq5XPwRKy
ftC6pMo0vYQKYdY/Jt3u0xY0nx0fl1iRAoIBAG61rQvbEgg8gHwQj7VpyhncSx4f
k1SwAhqwOjx/vtmMTHrHL8dNSzBD4igvzNHIkuC+dljhKANyIllshvsRvsJLfnrm
1zlpI8Ahn1KVCzd075Ab52KvCBXtYN358FlR/y2UASEgIws7+K7qxKbGe6ARk1Fz
4NkCdB2D2Cdp5h1Haz38wGjXRlccI+COczErW8s+vL4y8PXjzSY8pffy9Fce6CLF
A8/mR+c8aQ8X9zI9ae8GfLBUzfmNg0uAJPOgiwsiCdLQJuG2P2IHaJE2hIBa28kS
4A2Ikk0KKLPt8quOKQUqolNuaVfGKcQ9+aBJbK6UhQIgCKYGGc/KIkzhQlE=
-----END RSA PRIVATE KEY-----
'''

    class swish_id(String(Quantity(1))):

        def on_create(attr, value, self):
            return [re.sub('[^\d]', '', v) for v in value]

        on_update = on_create

    class cert(StringNotEmpty(QuantityMax(1))):
        pass

    class pkey(String(post=Quantity(1))):

        def on_create(attr, value, self):
            for v in value:
                # Sanity check
                OpenSSL.crypto.load_privatekey(OpenSSL.crypto.FILETYPE_PEM, v)
            return value

        on_update = on_create

    class csr(String()):

        def on_computation(attr, self):
            key = OpenSSL.crypto.load_privatekey(OpenSSL.crypto.FILETYPE_PEM,
                                                 self.pkey[0])
            req = OpenSSL.crypto.X509Req()
            subject = req.get_subject()
            if self.org[0].name:
                subject.organizationName = self.org[0].name[0]
            if self.org[0].email:
                subject.emailAddress = self.org[0].email[0]
            req.set_pubkey(key)
            req.sign(key, 'sha256')
            pem = OpenSSL.crypto.dump_certificate_request(
                OpenSSL.crypto.FILETYPE_PEM, req)
            return [pem]

    class is_test(Bool()):

        def on_computation(attr, self):
            return [self.swish_id[0] == '1231181189']

    class cert_expires(Timestamp(QuantityMax(1))):

        def on_computation(attr, self):
            # this is actually broken, as mktime will interpret the
            # timetuple as localtime, but it's propably in utc
            result = []
            for pem in self.cert:
                cert = OpenSSL.crypto.load_certificate(
                    OpenSSL.crypto.FILETYPE_PEM, pem)
                expires = cert.get_notAfter()
                if PYT3:
                    expires = expires.decode()
                t = time.strptime(expires[:14], '%Y%m%d%H%M%S')
                result.append(int(time.mktime(t)))
            return result

    def verify_cert(self):
        if not self.cert:
            return
        with tempfile.NamedTemporaryFile() as certfile, \
             tempfile.NamedTemporaryFile() as keyfile:
            certfile.write(self.cert[0].encode('ascii'))
            keyfile.write(self.pkey[0].encode('ascii'))
            certfile.flush()
            keyfile.flush()
            context = ssl.create_default_context()
            try:
                context.load_cert_chain(certfile=certfile.name,
                                        keyfile=keyfile.name)
            except ssl.SSLError as exc:
                raise cBlmError('Invalid certificate')

    def on_create(self):
        super(SwishProvider, self).on_create()
        if not self.pkey:
            if self.is_test[0]:
                pem = self.TEST_PKEY
            else:
                key = OpenSSL.crypto.PKey()
                key.generate_key(OpenSSL.crypto.TYPE_RSA, 4096)
                pem = OpenSSL.crypto.dump_privatekey(
                    OpenSSL.crypto.FILETYPE_PEM, key)
            if PYT3:
                if isinstance(pem, bytes):
                    pem = pem.decode()
            self.pkey = [pem]

        if self.cert:
            self.verify_cert()

    def on_update(self, newAttrValues):
        self._update(newAttrValues)
        if 'cert' in newAttrValues or 'pkey' in newAttrValues:
            self.verify_cert()


class IzettleProvider(PaymentProvider):

    requiredSubscriptionLevel = 'subscriber'

    # series inherited

    # account inherited

    class fee_account(StringNotEmpty()):
        pass

    class cash_account(StringNotEmpty()):
        pass


class SupplierInvoiceProvider(PaymentProvider):

    #requiredSubscriptionLevel = 'subscriber'

    # series inherited

    # account inherited
    # used for temporary debt to supplier

    class bank_account(StringNotEmpty()):
        pass

    class transferVerification_text(String(QuantityMax(1))):
        default = ['Accounts payable transfer']
        pass

    class transfer_addresses(StringMap()):
        pass

    def generateTransferAddress(self, clearingnumber, bankaccount):
        key = clearingnumber + bankaccount
        try:
            i = self.transfer_addresses[key]
        except KeyError:
            i = len(self.transfer_addresses) + 1
            transfer_addresses = dict(self.transfer_addresses)
            transfer_addresses[key] = i
            self.transfer_addresses = transfer_addresses
        return luhn.add_luhn_checksum('{0!s:0>5}'.format(i))

    class plusgiro_sending_bank_account(String(QuantityMax(1))):
        pass


class Org(TO):

    class name(String(QuantityMax(1))):
        pass

    class created(Timestamp(post=Quantity(1))):

        def on_create(attr, value, self):
            return value or [time.time()]

    class subscriptionLevel(SubscriptionLevel()):
        pass

    TRIAL_PERIOD = 3600 * 24 * 190  # 190 days, six months and some margin
    TRIAL_WARNING_INTERVAL = 3600 * 24 * 7  # Seven day warning interval
    TRIAL_WARNING_COUNT = 2

    class removalWarnings(Timestamp()):
        pass

    class apikey(String(QuantityMax(1))):
        pass

    class orgnum(String(QuantityMax(1))):

        def on_create(attr, value, self):
            return list(map(normalize_orgnum, value))
        on_update = on_create

    class ug(ToiRef(ToiType(UG), post=Quantity(1))):
        pass

    class ticketchecker_ug(ToiRef(ToiType(UG), post=Quantity(1))):
        pass

    class members(ToiRef(ToiType(User))):

        def on_computation(attr, self):
            return [u for u in self.ug[0].users if isinstance(u, User)]

    class admins(ToiRef(ToiType(User))):
        pass

    class payers(ToiRef(ToiType(User))):
        pass

    class accountants(ToiRef(ToiType(User))):
        pass

    class storekeepers(ToiRef(ToiType(User))):
        pass

    class ticketcheckers(ToiRef(ToiType(User))):

        def on_computation(attr, self):
            return self.ticketchecker_ug[0].users

    class userpermissions(Serializable()):
        def on_computation(attr, self):
            self._preload(['admins', 'ug'])
            result = []
            users = set(self.members) | set(self.ticketcheckers)
            users = User._query(id=users, _attrList=['name', 'ugs']).run()
            for user in users:
                roles = []
                if user in self.admins:
                    roles.append('admin')
                if user in self.payers:
                    roles.append('payer')
                if user in self.accountants:
                    roles.append('accountant')
                if user in self.storekeepers:
                    roles.append('storekeeper')
                if user in self.ticketcheckers:
                    roles.append('ticketchecker')
                if user in self.members:
                    roles.append('member')
                result.append({
                    'id': str(user.id[0]),
                    'name': user.name[0],
                    'ugs': [str(ug.id[0]) for ug in user.ugs],
                    'roles': roles
                    # ...
                    })

            return result

    class permissions(String()):
        _flagAttrs = ['admins', 'accountants', 'payers', 'storekeepers',
                      'ticketcheckers', 'members']
        def on_computation(attr, self):
            flags = []
            user = ri.getClientUser()
            self._preload(attr._flagAttrs)
            for flag in attr._flagAttrs:
                if user in getattr(self, flag):
                    flags.append(flag)
            return flags

    class address(String()):
        pass

    class phone(StringNotEmpty()):
        pass

    class email(String()):
        pass

    class url(StringNotEmpty()):
        pass

    class seat(StringNotEmpty()):
        pass

    class fskatt(Bool(Quantity(1))):
        default = [False]

    class vatnum(StringNotEmpty()):
        pass

    class currency(StringNotEmpty(Regexp(r'[A-Z]{3}'), post=Quantity(1))):

        def on_create(attr, value, toi):
            if not value:
                value = ['SEK']
            return value

    class ocrCounter(Int()):
        default = [1]

    class ocrYearReset(Int(Range(0, 9))):

        def on_create(attr, value, toi):
            return [int(time.strftime('%Y')[-1])]

    class providerPaymentCounter(Int()):
        default = [1]

    class current_accounting(ToiRef(ToiType('Accounting'), QuantityMax(1))):
        pass

    def update_current_accounting(self, ignore=None):
        if ignore:
            q = Accounting._query(org=self, id=Q.NotIn(ignore.id))
        else:
            q = Accounting._query(org=self)
        q.attrList = ['start']
        accountings = sorted(q.run(), key=lambda toi: toi.start[0])
        self.current_accounting = accountings[-1:]

    class image(Blob()):
        "logotype"

    class hasImage(Bool(Quantity(1))):

        def on_computation(attr, self):
            return [bool(len(self.image))]

    class manual_payment_provider(ToiRef(ToiType(ManualProvider), QuantityMax(1))):
        pass

    def get_manual_payment_provider(self):
        if not self.manual_payment_provider:
            self.manual_payment_provider = [ManualProvider(org=self)]
        return self.manual_payment_provider[0]

    def canWrite(self, user, attrName):
        required = ['admins']
        if attrName in ('ocrCounter', 'ocrYearReset'):
            if user == self.ug[0]:
                return True
            required = ['invoicesenders', 'members']
        if attrName == 'current_accounting':
            required += ['accountants']
        return currentUserHasRole(self, *required, user=user)

    @method(ToiRef(ToiType(Invitation), Quantity(1)))
    def invite(self, email=String(Quantity(1)), roles=String()):
        # xxx maybe having different names for groups and roles
        # wasn't such a brilliant idea...
        groups = [role + 's' for role in roles]
        return [Invitation(org=[self], emailTo=email, groups=groups)]

    @method(String())
    def get_ocr(self):
        year = int(time.strftime('%Y')[-1])
        if [year] != self.ocrYearReset:
            self.ocrCounter = [1]
            self.ocrYearReset = [year]

        counter = self.ocrCounter[0]
        self.ocrCounter = self.ocrCounter[0] + 1

        number = str(counter + 9) + str(year)
        return [luhn.add_control_digits(number)]

    @method(None)
    def disable(self):
        if ri.getClientUser():
            raise cBlmError('No permission')
        self.subscriptionLevel = []
        self.ug[0].users = []
        self.admins = []
        self.accountants = []
        self.payers = []
        self.storekeepers = []
        self.ticketchecker_ug[0].users = []
        self.email = []

    _oeOrgNum = '556609-2473'
    def _oeUnique(self):
        if self.orgnum == [self._oeOrgNum] and Org._query(orgnum=self.orgnum).run() != [self]:
            raise cBlmError('This organisation number is reserved.')

    def on_create(self):
        self._oeUnique()
        self.ug = [UG()]
        self.ticketchecker_ug = [UG(allowRead=self.ug)]
        user = ri.getClientUser()
        if user:
            with ri.setuid():
                # users do not have write access to their own .ugs, so
                # this needs to be run with privilege escalation
                user(ugs=user.ugs + self.ug + self.ticketchecker_ug)
                self.admins = [user]
                self.accountants = [user]
                self.storekeepers = [user]
        self.allowRead = self.ug + self.ticketchecker_ug

    def on_update(self, newAttrValues):
        for accounting in  self.current_accounting:
            propagate = {'name': 'orgname',
                         'orgnum': 'orgnum',
                         # xxx exactly what attributes?
                         }
            params = {}
            for attrName in set(propagate) & set(newAttrValues):
                params[propagate[attrName]] = newAttrValues[attrName]
            with ri.setuid():
                accounting(**params)

        self._update(newAttrValues)
        self._oeUnique()


@method(None)
def expireTrialOrg(org=ToiRef(ToiType(Org), Quantity(1))):
    org, = org

    if org.subscriptionLevel:
        return

    if org.created[0] > (time.time() - (org.TRIAL_PERIOD -
                         org.TRIAL_WARNING_COUNT * org.TRIAL_WARNING_INTERVAL)):
        return

    if len(org.removalWarnings) >= org.TRIAL_WARNING_COUNT:
        last = org.removalWarnings[-1]
        if time.time() - org.TRIAL_WARNING_INTERVAL > last:
            # inform user
            org._delete()

    elif org.removalWarnings:
        last = org.removalWarnings[-1]
        if time.time() - org.TRIAL_WARNING_INTERVAL > last:
            # warn
            org.removalWarnings.append(time.time())

    else:
        # warn
        org.removalWarnings.append(time.time())


@method(String(Quantity(1)))
def createAPIUser(org=ToiRef(ToiType(Org), Quantity(1))):
    org, = org
    if not currentUserHasRole(org, 'admins'):
        raise cBlmError('Permission denied')

    ug, = org.ug

    for user in ug.users:
        if isinstance(user, APIUser):
            raise cBlmError('Org %s already has an API User.' % org.id[0])

    user = APIUser()
    ug.users.append(user)
    org.apikey = user.key
    return user.key


class Role(Enum):
    values = ['admin', 'accountant', 'payer', 'storekeeper', 'member', 'ticketchecker']


@method(Serializable)
def removeMembers(org=ToiRef(ToiType(Org), Quantity(1)),
                  users=ToiRef(ToiType(User))):
    org = org[0]

    if not currentUserHasRole(org, 'admins'):
        raise cBlmError('Permission denied.')

    roleData = []
    for user in users:
        roleData.append({'id': user.id[0], 'roles': []})
    updateMemberRoles([org], roleData, [True])
    if ri.getClientUser() not in org.members:
        return []
    return org.userpermissions


@method(Serializable())
def updateMemberRoles(org=ToiRef(ToiType(Org), Quantity(1)),
                      roleData=Serializable(),
                      remove=Bool()):
    org = org[0]
    remove = any(remove)

    for userData in roleData:
        User._query(id=userData['id']).run()
        user, = User._query(id=userData['id']).run()
        roles = userData['roles']

        if not roles and not remove:
            raise cBlmError('A user must have at least one role.')

        try:
            Role.coerceValueList(roles)
        except exceptions.AttrValueError:
            raise cBlmError('Invalid roles: %s' % roles)

        member = 'member' in roles

        if 'accountant' in roles:
            org.accountants.add(user)
            member = True
        elif user in org.accountants:
            org.accountants.remove(user)

        if 'payer' in roles:
            org.payers.add(user)
            member = True
        elif user in org.payers:
            org.payers.remove(user)

        if 'storekeeper' in roles:
            org.storekeepers.add(user)
            member = True
        elif user in org.storekeepers:
            org.storekeepers.remove(user)

        if 'admin' in roles:
            org.admins.add(user)
            member = True
        elif user in org.admins:
            if org.admins == [user]:
                raise cBlmError('At least one admin is required.')
            org.admins.remove(user)

        with ri.setuid():
            if member:
                org.ug[0].users.add(user)
                user.ugs.add(org.ug[0])
            else:
                org.ug[0].users.discard(user)
                user.ugs.discard(org.ug[0])

            if 'ticketchecker' in roles:
                org.ticketchecker_ug[0].users.add(user)
                user.ugs.add(org.ticketchecker_ug[0])
            elif user in org.ticketcheckers:
                org.ticketchecker_ug[0].users.remove(user)
                user.ugs.remove(org.ticketchecker_ug[0])

    return org.userpermissions


@method(None)
def subscribe(org=ToiRef(ToiType(Org), Quantity(1)),
              level=SubscriptionLevel(Quantity(1))):
    org, = org
    org.subscriptionLevel = list(uniq(org.subscriptionLevel + level))


class PGOrder(TO):

    class org(ToiRef(ToiType(Org), Quantity(1))):
        pass

    class createdBy(ToiRef(ToiType(User), QuantityMax(1), Unchangeable())):
        def on_create(attr, value, self):
            user = ri.getClientUser()
            return [user] if user else []

    class contact(String(Quantity(1))):
        pass

    class contactPhone(String(Quantity(1))):
        pass

    class contactEmail(String(Quantity(1))):
        pass

    class pgnum(String(Quantity(1))):
        "Plugiro account without OCR connection."

    class sent(Bool(Quantity(1))):
        default = [False]

    def canWrite(self, user, attrName):
        return attrName == 'sent' and currentUserHasRole(self, 'admins',
                                                         user=user)

    @requireRoles('admins')
    def on_create(self):
        self.allowRead = self.org[0].ug

    @method(None)
    def send(self):
        if self.sent[0]:
            return
        fromaddr = config.config.get('plusgiro', 'setup_email_from')
        recipients = [a[1] for a in
                      getaddresses([config.config.get('plusgiro', 'setup_email_to')])]

        class toisasdict(dict):
            def __init__(self, *tois):
                self.tois = tois
            def __getitem__(self, key):
                if key in self:
                    return dict.__getitem__(self, key)
                for toi in self.tois:
                    try:
                        return toi[key][0]
                    except exceptions.AttrNameError:
                        continue  # not in this toi
                    except IndexError:
                        return ''
                raise KeyError
            def __getattr__(self, key):
                return self[key]

        values = {'to': ', '.join(recipients),
                  'from': fromaddr}
        body, headers = templating.as_mail_data('plusgirorequest',
                                                o=toisasdict(self, self.org[0]),
                                                **values)
        mail.sendmail(*mail.makemail(body, envfrom=fromaddr, **headers))
        self.sent = [True]


@method(None)
def orderPG(org=ToiRef(ToiType(Org), Quantity(1)),
            contact=String(Quantity(1)),
            contactPhone=String(Quantity(1)),
            contactEmail=String(Quantity(1)),
            pgnum=String(Quantity(1)),
            pgaccount=String(Quantity(1)),
            pgseries=String(Quantity(1))):

    ppd = PlusgiroProvider(org=org, account=pgaccount, series=pgseries,
                           pgnum_real=pgnum)
    return [PGOrder(org=org, contact=contact, contactPhone=contactPhone,
                    contactEmail=contactEmail, pgnum=pgnum)]


class Accounting(TO):
    '''
    A repository for a number of attributes that need to be kept around.
    '''

    class name(String(Quantity(1))):

        def on_computation(attr, self):
            if self.start and self.end:
                return ['%s - %s' % tuple(self.start + self.end)]
            return self.taxation_year.value or self.orgname.value or self.orgnum.value or \
                ['<unnamed>']

    class closed(Bool(Quantity(1))):
        default = [False]

    class years(StringMap()):  # Regexp(date_re))):
        # { 'yearidx' : [start, end] }
        pass

    class start(String(Regexp(date_re), post=Quantity(1))):
        pass

    class end(String(Regexp(date_re), post=Quantity(1))):
        pass

    class contact(StringNotEmpty(QuantityMax(1))):
        pass

    class mail_address(StringNotEmpty(QuantityMax(1))):
        pass

    class zip_city(StringNotEmpty(QuantityMax(1))):
        pass

    class telephone(StringNotEmpty(QuantityMax(1))):
        pass

    class layout(StringNotEmpty(QuantityMax(1))):
        "Kontoplantyp"

    class currency(StringNotEmpty(Regexp(r'[A-Z]{3}'), QuantityMax(1))):
        pass

    class orgnum(StringNotEmpty(QuantityMax(1))):
        pass

    class org(ToiRef(ToiType(Org), QuantityMax(1), Unchangeable())):
        # xxx this should be a Quantity(1) at some point
        pass

    class orgname(StringNotEmpty(QuantityMax(1))):
        pass

    class orgtype(StringNotEmpty(QuantityMax(1))):
        pass

    class industry_code(StringNotEmpty(QuantityMax(1))):
        pass

    class taxation_year(StringNotEmpty(QuantityMax(1))):
        pass

    class previous(ToiRef(ToiType('Accounting'), QuantityMax(1))):

        def on_computation(attr, self):
            accountings = Accounting._query(org=self.org).run()
            accountings.sort(key=lambda toi: toi.start[0])
            while accountings.pop() != self:
                pass
            return [accountings.pop()] if accountings else []

    class imported(Bool(Quantity(1))):
        default = [False]

    def canWrite(self, user, attrName):
        return currentUserHasRole(self, 'accountants', user=user)

    @requireRoles('accountants')
    def on_create(self):
        self.year = [0]
        self.accounting = [self]

        if not self.start:
            enddate = None
            if self.org:  # Should always be true
                try:
                    enddate = max(
                        parsedate(a.end[0]) for a in Accounting._query(
                        org=self.org, end=Q.NotEmpty()).run())
                except ValueError:
                    pass
            if not enddate:
                # No enddate found, use yesterday (maybe start of last quarter?)
                enddate = (datetime.datetime.now() +
                           dateutil.relativedelta.relativedelta(days=-1))
            self.start = [(enddate + dateutil.relativedelta.relativedelta(
                days=+1)).strftime('%Y-%m-%d')]

        if not self.end:
            self.end = [(parsedate(self.start[0]) +
                         dateutil.relativedelta.relativedelta(years=1, days=-1))
                        .strftime('%Y-%m-%d')]

        years = self.years.value
        years['0'] = [self.start[0], self.end[0]]
        self.years = years

        for org in self.org:
            self.orgname = self.orgname or org.name
            self.orgnum = self.orgnum or org.orgnum
            self.telephone = self.telephone or org.phone
            self.allowRead = org.ug
            org.update_current_accounting()

        self.ensureSeries(ensureOne=False)

        dim1 = Dimension(number=['1'], name=[u'Kostnadsställe'],
                         accounting=[self])
        Dimension(number=['2'], name=[u'Kostnadsbärare'],
                  accounting=[self], subdim_of=[dim1])
        Dimension(number=['6'], name=[u'Projekt'],
                  accounting=[self],
                  project=[True])
        Dimension(number=['7'], name=[u'Anställd'],
                  accounting=[self])
        Dimension(number=['8'], name=[u'Kund'],
                  accounting=[self])
        Dimension(number=['9'], name=[u'Leverantör'],
                  accounting=[self])
        Dimension(number=['10'], name=[u'Faktura'],
                  accounting=[self])

    def on_update(self, newattrvalues):
        self._update(newattrvalues)
        if 'start' in newattrvalues or 'end' in newattrvalues:
            years = self.years.value
            years['0'] = [self.start[0], self.end[0]]
            self.years = years
            for org in self.org:
                org.update_current_accounting()
        elif 'years' in newattrvalues and '0' in newattrvalues['years']:
            start, end = newattrvalues['years']['0']
            self.start = [start]
            self.end = [end]

    def on_delete(self):
        # prefetch data
        q = VerificationSeries._query(accounting=[self])
        q.attrList = ['allowRead']
        series = q.run()

        q = Account._query(accounting=[self])
        q.attrList = ['allowRead', 'number', 'account_balances',
                      'balance_budgets', 'object_balance_budgets',
                      'transactions']
        accounts = q.run()
        for account in accounts:
            # no need to recalc balance of accounts that are being deleted
            account.updateBalance = lambda: None

        q = AccountBalance._query(account=accounts)
        q.attrList = ['allowRead', 'balance_budgets', 'object_balance_budgets']
        q.run()

        q = Dimension._query(accounting=[self])
        q.attrList = ['allowRead']
        dimensions = q.run()

        for toi in series:
            toi._allowDelete = True
            toi._delete()

        for toi in accounts:
            toi._delete()

        for toi in dimensions:
            toi._delete()

        for org in self.org:
            org.update_current_accounting(ignore=self)

    @method(None)
    def close(self):
        self.closed = [True]

    def ensureSeries(self, ensureOne=True):
        created = []
        if self.org:
            for ppd in PaymentProvider._query(org=self.org).run():
                if ppd.series and not VerificationSeries._query(accounting=self, name=ppd.series).run():
                    created.append(VerificationSeries(accounting=self, name=ppd.series))
        if ensureOne and not VerificationSeries._query(accounting=self).run():
            created.append(VerificationSeries(accounting=self, name=['A']))
        return created

    @method(Serializable(Quantity(1)))
    def initialise(self):
        """Set opening balance of all accounts to closing balance of
        previous year."""
        if not self.previous:
            return [{'success': False}]
        prev, = self.previous

        q = Account._query(accounting=self)
        q.attrList = ['number', 'opening_balance', 'balance',
                      'opening_quantity', 'quantity'  # used by updateBalance
                      ]

        accounts = dict((account.number[0], account) for account in q.run())

        q = Account._query(accounting=prev)
        q.attrList = ['name', 'number', 'balance']
        for prev_acc in q.run():
            try:
                cur_acc = accounts[prev_acc.number[0]]
            except KeyError:
                cur_acc = Account(accounting=[self],
                                  number=prev_acc.number,
                                  name=prev_acc.name,
                                  type=prev_acc.type)
            if (cur_acc.type[0] in ('T', 'S') and
                cur_acc.opening_balance != prev_acc.balance):
                cur_acc.opening_balance = prev_acc.balance
                cur_acc.updateBalance()

        return [{'success': True}]

    @method(ToiRef(ToiType('Accounting'), Quantity(1)))
    def new(self):
        """
        Create a new accounting year, based on this one.

        Accounts, Dimensions and associated objects will be copied.
        Opening balances will be set to this one's closing balances
        (when appropriate).
        """
        self._preload(set(self._attributes))

        try:
            taxation_year = [str(int(year)+1) for year in self.taxation_year]
        except ValueError:
            # xxx maybe we should formalize taxation_year format a bit...
            taxation_year = []

        start = (parsedate(self.end[0]) +
                 dateutil.relativedelta.relativedelta(days=1)).strftime(
            '%Y-%m-%d')

        accounting = Accounting(
            taxation_year=taxation_year,
            start=[start],
            layout=self.layout,
            currency=self.currency,
            org=self.org,
            allowRead=self.allowRead
            )

        dimensions = Dimension._query(accounting=self,
                                      _attrList=Dimension._attributes).run()
        dimensions.sort(key=lambda toi: int(toi.number[0]))
        for dimension in dimensions:
            new_dimension = accounting.ensureDimension(
                number=dimension.number,
                name=dimension.name,
                project=dimension.project,
                subdim_of=[dim.number[0] for dim in dimension.subdim_of])
            for accounting_object in AccountingObject._query(
                dimension=dimension,
                _attrList=AccountingObject._attributes).run():
                accounting_object.new(dimension=new_dimension)

        accounts = Account._query(accounting=self,
                                  _attrList=set(Account._attributes)).run()
        accounts.sort(key=lambda toi: toi.number[0])

        # preload AccountBalances
        AccountBalance._query(account=accounts,
                              _attrList=set(AccountBalance._attributes)).run()

        for account in accounts:
            account.new([accounting])

        for toi in VerificationSeries._query(
            accounting=self, _attrList=VerificationSeries._attributes).run():
            toi.copy([accounting])

        return [accounting]

    @method(ToiRef(ToiType('Dimension'), Quantity(1)))
    def ensureDimension(self,
                      number=String(Quantity(1)),
                      name=String(Quantity(1)),
                      project=Bool(Quantity(1)),
                      subdim_of=String(QuantityMax(1))):
        "Create or update dimension associated with this Accounting."
        dimension = Dimension._query(accounting=[self], number=number).run()
        if subdim_of:
            parent = Dimension._query(accounting=[self], number=subdim_of).run()
        else:
            parent = []

        if dimension:
            dimension, = dimension
            dimension(number=number,
                      name=name,
                      project=project,
                      subdim_of=parent)
        else:
            dimension = Dimension(accounting=[self],
                                  number=number,
                                  name=name,
                                  project=project,
                                  subdim_of=parent)
        return [dimension]


class Dimension(TO):

    class number(String(Quantity(1))):
        pass

    class name(String(Quantity(1))):
        pass

    class project(Bool(Quantity(1))):
        default = [False]

    class subdim_of(ToiRef(ToiType('Dimension'), QuantityMax(1), Weak())):
        pass

    class accounting(ToiRef(ToiType(Accounting), Quantity(1), Unchangeable())):
        pass

    def canWrite(self, user, attrName):
        return currentUserHasRole(self, 'accountants', user=user)

    @requireRoles('accountants')
    def on_create(self):
        self.allowRead = self.accounting[0].allowRead
        if self.subdim_of and self.subdim_of[0].project[0]:
            self.project[0] = [True]

    def on_delete(self):
        for toi in AccountingObject._query(dimension=self).run():
            toi._delete()


class AccountingObject(TO):
    ''' Used for Project accounting, result units etc. '''

    class number(String(Quantity(1))):
        pass

    class name(String(Quantity(1))):
        pass

    class dimension(ToiRef(ToiType(Dimension), Quantity(1))):
        pass

    @method(ToiRef(ToiType('AccountingObject'), Quantity(1)))
    def new(self, dimension=ToiRef(ToiType(Dimension), Quantity(1))):
        copy = AccountingObject(number=self.number,
                                name=self.name,
                                dimension=dimension)
        return [copy]

    def updateBalance(self, transaction):
        account = transaction.account[0]
        try:
            obb, = ObjectBalanceBudget._query(account_balance=account,
                                              accounting_object=self).run()
        except ValueError:
            obb = ObjectBalanceBudget(account_balance=[account],
                                      accounting_object=[self],
                                      period=[''])
        obb.updateBalance()

    def canWrite(self, user, attrName):
        return currentUserHasRole(self, 'accountants', user=user)

    @requireRoles('accountants')
    def on_create(self):
        self.allowRead = self.dimension[0].allowRead


class Balance(TO):

    class opening_balance(Decimal(post=Quantity(1))):
        precision = 2
        default = [decimal.Decimal('0')]

    class opening_quantity(Decimal(post=Quantity(1))):
        default = [decimal.Decimal('0')]

    class budget(Decimal(post=Quantity(1))):
        precision = 2
        default = [decimal.Decimal('0')]

    class budget_quantity(Decimal(post=Quantity(1))):
        default = [decimal.Decimal('0')]

    class balance(Decimal(post=Quantity(1))):
        precision = 2
        default = [decimal.Decimal('0')]

    class balance_quantity(Decimal(post=Quantity(1))):
        default = [decimal.Decimal('0')]

    def canWrite(self, user, attrName):
        return currentUserHasRole(self, 'accountants', user=user)

    def on_create(self):
        assert self.__class__ is not Balance, 'only instantiate sub classes'

    # to be obsoleted:
    class closing_balance(Decimal(post=Quantity(1))):
        precision = 2
        default = [decimal.Decimal('0')]

    class closing_quantity(Decimal(post=Quantity(1))):
        default = [decimal.Decimal('0')]

    class turnover(Decimal(post=Quantity(1))):
        precision = 2
        default = [decimal.Decimal('0')]

    class turnover_quantity(Decimal(post=Quantity(1))):
        default = [decimal.Decimal('0')]


class AccountBalance(Balance):

    class account(ToiRef(ToiType('Account'), Unchangeable(), post=Quantity(1))):
        pass

    class year(Int(Quantity(1), RangeMax(0))):
        default = [0]

    class balance_budgets(Relation(Weak())):
        related = 'BalanceBudget.account_balance'

    class object_balance_budgets(Relation(Weak())):
        related = 'ObjectBalanceBudget.account_balance'

    @method(ToiRef(ToiType('AccountBalance'), Quantity(1)))
    def copy(self,
             account=ToiRef(ToiType('Account'), Quantity(1)),
             year=Int(QuantityMax(1))):
        copy = AccountBalance(year=[sum(self.year + year)],
                              account=account,
                              opening_balance=self.opening_balance,
                              opening_quantity=self.opening_quantity,
                              balance=self.balance,
                              balance_quantity=self.balance_quantity,
                              budget=self.budget,
                              budget_quantity=self.budget_quantity)

        for obb in self.object_balance_budgets:
            obb.copy(account_balance=[copy])

        return [copy]

    @requireRoles('accountants')
    def on_create(self):
        if self.year == [0] and self.account != [self]:
            raise cBlmError('Do not create AccountBalance with year 0')

        account = self.account[0]
        self.allowRead = account.allowRead
        abals = account.account_balances.value
        abals[str(self.year[0])] = self
        account.account_balances = abals

    def on_delete(self):
        for toi in self.balance_budgets:
            toi._delete()
        for toi in self.object_balance_budgets:
            toi._delete()


class BaseAccount(TO):
    class number(String(Quantity(1))):
        pass

    class name(String(Quantity(1))):
        default = [u'* UNNAMED *']

    class type(Enum(QuantityMax(1))):
        # Tillgång, Skuld, Kostnad, Intäkt
        values = 'T', 'S', 'K', 'I'

    class unit(String(QuantityMax(1))):
        pass

    class sru(String(QuantityMax(1))):
        "Standardiserat RäkenskapsUtdrag"

    class vatCode(String(QuantityMax(1))):
        "Momsrapportkod"

    def on_create(self):
        if not self.type:
            # default type is decided by first character in account number
            self.type = ['TTSIKKKKKK'[int(self.number[0][0])]]

    @classmethod
    def fromtemplate(cls, template, **params):
        raise NotImplementedError


class AccountTemplate(BaseAccount):

    def canWrite(self, user, attrName):
        return False

    def on_create(self):
        if ri.getClientUser():
            raise cBlmError('You may not create AccountTemplates')

        super(AccountTemplate, self).on_create()
        self.allowRead = self.allowRead + UG._query(name='public').run()


class ChartOfAccounts(TO):
    "Kontoplan"

    class name(String(Quantity(1), Unique())):
        pass

    class accounts(ToiRef(ToiType(AccountTemplate))):
        pass

    @method(ToiRef(ToiType('Account')))
    def populate(self, accounting=ToiRef(ToiType('Accounting'), Quantity(1))):
        res = []
        for template in AccountTemplate._query(
            id=self.accounts,
            _attrList=set(AccountTemplate._attributes) & set(Account._attributes)).run():
            res.append(Account.fromtemplate(template,
                                            accounting=accounting))

        return res

    def canWrite(self, user, attrName):
        return False

    def on_create(self):
        if ri.getClientUser():
            raise cBlmError('You may not create ChartOfAccounts')
        self.allowRead = self.allowRead + UG._query(name='public').run()


@method(ToiRef(ToiType(Accounting), Quantity(1)))
def accountingFromTemplate(template=ToiRef(ToiType(ChartOfAccounts), Quantity(1)),
                           org=ToiRef(ToiType(Org), Quantity(1))):
    accounting = Accounting(org=org)
    template[0].populate([accounting])
    accounting.ensureSeries()
    return [accounting]


class Account(AccountBalance):

    # number, name, type, unit, sru, vatCode from BaseAccount
    class number(String(Quantity(1))):
        pass

    class name(String(Quantity(1))):
        default = [u'* UNNAMED *']

    class type(Enum(QuantityMax(1))):
        # Tillgång, Skuld, Kostnad, Intäkt
        values = 'T', 'S', 'K', 'I'

    class unit(String(QuantityMax(1))):
        pass

    class sru(String(QuantityMax(1))):
        "Standardiserat RäkenskapsUtdrag"

    class vatCode(String(QuantityMax(1))):
        "Momsrapportkod"

        def on_create(attr, value, self):
            return [v for v in value if v]
        on_update = on_create

    class vatPercentage(Decimal(QuantityMax(1))):
        precision = 2

    @classmethod
    def fromtemplate(cls, template, **params):
        for attr in set(template._attributes) & set(cls._attributes):
            if attr not in params:
                params[attr] = getattr(template, attr)
        return cls(**params)

    class accounting(ToiRef(ToiType('Accounting'), Quantity(1), Unchangeable())):
        pass

    class transactions(Relation(Weak())):
        related = 'Transaction.account'

    class account_balances(ToiRefMap(ToiType('AccountBalance'))):
        pass

    def on_create(self):
        self.allowRead = self.accounting[0].allowRead
        # This hack is used by Transaction.sum() to figure out if it
        # needs to query the database for possible transactions on
        # this TOI. While the Account is uncommitted that shouldn't be
        # necessary.
        self._new = True
        self.account = [self]
        super(Account, self).on_create()
        if not self.type:
            # default type is decided by first character in account number
            self.type = ['TTSIKKKKKK'[int(self.number[0][0])]]

        self.balance = self.opening_balance
        self.balance_quantity = self.opening_quantity
        self.updateVatPercentage()

    def on_update(self, newattrvalues):
        self._update(newattrvalues)
        if 'vatCode' in newattrvalues:
            self.updateVatPercentage()
        if {'opening_balance', 'opening_quantity'} & set(newattrvalues):
            self.updateBalance()

    def on_delete(self):
        super(Account, self).on_delete()
        for toi in self.account_balances.value.values():
            if toi is not self:
                toi._delete()

    def updateVatPercentage(self):
        if self.vatCode:
            vc = VatCode._query(code=self.vatCode).run()
            if vc:
                self.vatPercentage = vc[0].percentage

    def sort_number_key(self):
        return self.number[0]
    sort_number_attrs = 'number',

    @method(None)
    def updateBalance(self):
        try:
            ri.cache[self.updateBalance.DELAY].add(self)
            return
        except KeyError:
            pass
        amount, quantity = Transaction.sum(account=self)
        self.balance = [self.opening_balance[0] + amount]
        self.balance_quantity = [self.opening_quantity[0] + quantity]

    updateBalance.DELAY = 'delay-balance-calculation'

    @method(ToiRef(ToiType('Account'), Quantity(1)))
    def new(self, accounting=ToiRef(ToiType('Accounting'), Quantity(1))):
        params = {}
        if self.type[0] in ('S', 'T'):  # xxx test me
            params = {
                'opening_balance': self.balance,
                'opening_quantity': self.balance_quantity
                }

        account = Account(accounting=accounting,
                          number=self.number,
                          name=self.name,
                          type=self.type,
                          unit=self.unit,
                          sru=self.sru,
                          vatCode=self.vatCode,
                          **params)

        # copy ObjectBalanceBudget associated with project dimensions
        for toi in self.object_balance_budgets:
            if toi.accounting_object[0].dimension[0].project[0]:
                toi.copy(account_balance=[account])

        new_balances = {'0': account}  # need to include account or it will disappear

        for year, old in self.account_balances.items():
            year = int(year) - 1
            new_balances[str(year)] = old.copy(account=[account], year=[-1])[0]

        account.account_balances = new_balances

        return [account]


class VerificationSeries(TO):

    class name(String(Quantity(1))):
        pass

    class description(String(QuantityMax(1))):
        pass

    class accounting(ToiRef(ToiType(Accounting), Quantity(1), Unchangeable())):
        pass

    class canBeDeleted(Bool(Quantity(1))):
        default = [True]

    def _check_name(self):
        if VerificationSeries._query(name=self.name,
                                     accounting=self.accounting).run() != [self]:
            raise cBlmError('A VerificationSeries with name "%s" already exists for '
                            'this Accounting' % self.name[0])

    @staticmethod
    def sort_name_key(self):
        return self.name[0]
    sort_name_attrs = 'name',

    @method(ToiRef(ToiType('VerificationSeries'), Quantity(1)))
    def copy(self, accounting=ToiRef(ToiType(Accounting), Quantity(1))):
        result = VerificationSeries._query(name=self.name,
                                           accounting=accounting).run()
        if not result:
            result = [VerificationSeries(name=self.name,
                                         accounting=accounting)]
        result[0].description = self.description
        return result

    def canWrite(self, user, attrName):
        return currentUserHasRole(self, 'accountants', user=user)

    @requireRoles('accountants')
    def on_create(self):
        self._check_name()
        self.allowRead = self.accounting[0].allowRead

    def on_update(self, newAttrValues):
        self._update(newAttrValues)
        self._check_name()

    _allowDelete = False
    def on_delete(self):
        if not self._allowDelete:
            org = self.accounting[0].org
            if org and PaymentProvider._query(org=org,
                                              series=self.name).run():
                raise cBlmError('You can not delete the series used for PG '
                                'payments.')
        q = Verification._query(series=[self])
        q.attrList = {'allowRead', 'log', 'transactions'}
        q.attrList.update(Verification.logattrs)
        verifications = q.run()

        # preload transactions
        q = Transaction._query(verification=verifications)
        q.attrList = {'allowRead', 'verification', 'account', 'version'}
        q.attrList.update(Transaction.logattrs)
        q.run()

        for toi in verifications:
            toi._delete()


@method(Serializable())
def next_verification_data(series=ToiRef(ToiType(VerificationSeries),
                                         Quantity(1))):
    series, = series
    q = Verification._query(series=series)
    q.attrList = ['number', 'transaction_date']
    verifications = q.run()
    if not verifications:
        number = 1
        date = series.accounting[0].start[0]
    else:
        maxver = max(verifications, key=lambda toi: toi.number.value)
        number = maxver.number[0] + 1
        date = maxver.transaction_date[0]
    return dict(accounting=series.accounting[0].id[0],
                number=number,
                transaction_date=date)


class Verification(TO):

    class version(Int(RangeMin(0), Quantity(1))):
        default = [0]

    class series(ToiRef(ToiType(VerificationSeries), Unchangeable(),
                        Quantity(1))):
        pass

    class number(Int(RangeMin(1), Unchangeable(), post=Quantity(1))):
        pass

    class transaction_date(String(Regexp(date_re), post=Quantity(1))):

        def on_create(attr, value, self):
            if not value:
                value = [time.strftime('%Y-%m-%d')]
            return value

    class text(String(QuantityMax(1))):
        pass

    class signature(String(QuantityMax(1))):

        def on_create(attr, value, self):
            if not value:
                user = ri.getClientUser()
                if user:
                    value = list(map(str, user.id))
            return value

    class signature_name(String(QuantityMax(1))):

        def on_create(attr, value, self):
            if not value:
                user = ri.getClientUser()
                if user:
                    value = user.name
            return value

    class registration_date(String(Regexp(date_re), QuantityMax(1))):

        def on_create(attr, value, self):
            if not value:
                value = [time.strftime('%Y-%m-%d')]
            return value

    class transactions(Relation(Weak())):
        related = 'accounting.Transaction.verification'

    class accounting(ToiRef(ToiType(Accounting), Quantity(1))):
        pass

    class externalRef(String()):
        pass

    logattrs = 'version transaction_date text signature signature_name registration_date'.split()

    class log(StringMap()):
        pass

    def _getLogCopy(self):
        log = {}
        for key, values in self.log.items():
            log[key] = list(values)
        return log

    def logVerification(self):
        self._preload(self.logattrs)
        attrs = {}
        for attr in self.logattrs:
            try:
                attrs[attr] = self._orgAttrData[attr]
            except KeyError:
                value = getattr(self, attr)
                attrs[attr] = value.value
        log = self._getLogCopy()

        if PYT3:
            log[str(self.version[0])] = [bson.BSON.encode(attrs)]
        else:
            log[str(self.version[0])] = [str(bson.BSON.encode(attrs))]

        self.log = log

    def logTransactionAdd(self, transaction):
        log = self._getLogCopy()
        version = 0
        vlog = log.setdefault(str(version), [''])

        if PYT3:
            vlog.append(bson.BSON.encode({'id': transaction.id}))
        else:
            vlog.append(str(bson.BSON.encode({'id': transaction.id})))
        self.log = log

    def logTransactionChange(self, transaction):
        log = self._getLogCopy()
        version = transaction.version[0]
        vlog = log.setdefault(str(version), [''])
        attrs = {'id': transaction.id}
        for attr in transaction.logattrs:
            try:
                attrs[attr] = transaction._orgAttrData[attr]
            except KeyError:
                value = getattr(transaction, attr)
                if attr == 'account':
                    value = value[0].number
                attrs[attr] = value.value

        if PYT3:
            vlog.append(bson.BSON.encode(attrs))
        else:
            vlog.append(str(bson.BSON.encode(attrs)))

        self.log = log

    def canWrite(self, user, attrName):
        return currentUserHasRole(self, 'accountants', user=user)

    @requireRoles('accountants')
    def on_create(self):
        if not self.number:
            try:
                previous = ri.cache['verification-number']
            except KeyError:
                q = Verification._query(series=self.series,
                                        _attrList=['number'])
                try:
                    previous = max(v.number[0] for v in q.run() if v != self)
                except ValueError:
                    previous = 0
            number = ri.cache['verification-number'] = previous + 1
            self.number = [number]
        else:
            q = Verification._query(series=self.series, number=self.number)
            if q.run() != [self]:
                raise cBlmError('A Verification with the number %s already '
                                'exists in this series.' % self.number[0])

        self.series[0].canBeDeleted = [False]
        self.allowRead = self.accounting[0].allowRead

    def on_update(self, newattrvalues):
        self.logVerification()
        nextversion = self.version[0] + 1
        if ('version' in newattrvalues and
            newattrvalues['version'] != [nextversion]):
            raise cBlmError('Version mismatch. Got %d, expected %d.' % (
                    newattrvalues['version'][0], nextversion))

        if set(self.logattrs) & set(newattrvalues):  # test me
            newattrvalues['version'] = [nextversion]
        self._update(newattrvalues)
        for transaction in self.transactions:
            transaction.transaction_date = self.transaction_date

        client_user = ri.getClientUser()
        if client_user:
            self.signature = list(map(str, client_user.id))
            self.signature_name = client_user.name
        self.registration_date = [time.strftime('%Y-%m-%d')]

    def on_delete(self):
        for toi in self.transactions:
            toi._delete()


@method(Serializable(Quantity(1)))
def createVerification(data=Serializable(Quantity(1))):
    data, = data
    data = copy.deepcopy(data)
    verData = data['verification']
    number = verData.pop('number', None)

    tot_amount = 0
    for transData in data['transactions']:
        tot_amount += transData['amount']
    if tot_amount != 0:
        raise ValueError('Verification not balanced.')

    def fixObjectId(attrData, toiRefs):
        for attrName in toiRefs:
            try:
                value = attrData[attrName]
                attrData[attrName] = bson.objectid.ObjectId(value)
            except KeyError:
                pass
            except InvalidId:
                if value == '':
                    # xxx client sends bad data sometimes, see
                    # https://todo.eutaxia.eu/#todo:59b9715d7af57651a8000002
                    del attrData[attrName]
                else:
                    raise

    fixObjectId(verData, 'accounting series'.split())

    verification = Verification(**verData)
    if number is not None and verification.number[0] < int(number):
        raise ValueError('Unexpected verification number')

    for transData in data['transactions']:
        fixObjectId(transData, 'account'.split())
        transData['amount'] = decimal.Decimal(transData['amount']) / 100,
        transData['verification'] = [verification]
        Transaction(**transData)

    return [{'number': verification.number[0], 'id': verification.id[0]}]


@method(Serializable(Quantity(1)))
def editVerification(data=Serializable(Quantity(1))):
    data, = data
    data = copy.deepcopy(data)
    verData = data['verification']

    tot_amount = 0
    for transData in data['transactions']:
        tot_amount += transData['amount']
    if tot_amount != 0:
        raise ValueError('Verification not balanced.')

    def fixObjectId(attrData, toiRefs):
        for attrName in toiRefs:
            try:
                value = attrData[attrName]
                attrData[attrName] = bson.objectid.ObjectId(value)
            except KeyError:
                pass
            except InvalidId:
                if value == '':
                    # xxx client sends bad data sometimes, see
                    # https://todo.eutaxia.eu/#todo:59b9715d7af57651a8000002
                    del attrData[attrName]
                else:
                    raise

    fixObjectId(verData, 'id accounting series'.split())

    verification, = Verification._query(id=verData['id']).run()
    del verData['id']
    verification(**verData)

    old_transactions = {trans.id[0]: trans for trans in verification.transactions}
    edited_transactions = set()

    for transData in data['transactions']:
        fixObjectId(transData, 'id account verification'.split())
        transData['amount'] = decimal.Decimal(transData['amount']) / 100,
        if 'id' in transData:
            edited_transactions.add(transData['id'])
            transaction, = Transaction._query(id=transData['id']).run()
            del transData['id']
            transaction(**transData)
        else:
            transData['verification'] = [verification]
            Transaction(**transData)

    for toid in set(old_transactions) - edited_transactions:
        old_transactions[toid]._delete()

    return [{'number': verification.number[0], 'id': verification.id[0]}]


class Transaction(TO):

    class version(Int(RangeMin(0), Quantity(1))):
        pass

    class transtype(Enum(Quantity(1))):
        values = 'normal', 'added', 'deleted'
        default = ['normal']

    class amount(Decimal(Quantity(1))):
        precision = 2
        default = [decimal.Decimal('0')]

    class quantity(Decimal(QuantityMax(1))):
        default = [decimal.Decimal('0')]

    class text(String(Quantity(1))):
        default = ['']

        def on_create(attr, value, self):
            return [v.strip() for v in value]
        on_update = on_create

    class signature(String(QuantityMax(1))):

        def on_create(attr, value, self):
            if not value:
                user = ri.getClientUser()
                if user:
                    value = list(map(str, user.id))
            return value

    class transaction_date(String(Regexp(date_re), post=Quantity(1))):
        pass

    class account(Relation(Quantity(1))):
        related = 'Account.transactions'

    class verification(Relation(Quantity(1), Unchangeable())):
        related = 'accounting.Verification.transactions'

    class accounting_objects(ToiRef(ToiType(AccountingObject))):
        pass

    logattrs = 'version amount quantity text signature transaction_date account'.split()

    @requireRoles('accountants')
    def on_create(self):
        if not self.transaction_date:
            self.transaction_date = self.verification[0].transaction_date
        self.allowRead = self.verification[0].allowRead
        self.account[0].transactions.add(self)
        self.account[0].updateBalance()
        for toi in self.accounting_objects:
            toi.updateBalance(self)

        if self.version != [0]:
            self.verification[0].logTransactionAdd(self)

    def canWrite(self, user, attrName):
        return currentUserHasRole(self, 'accountants', user=user)

    def on_update(self, newattrvalues):
        account = self.account[0]
        self.verification[0].logTransactionChange(self)
        self._update(newattrvalues)
        for account in set([account, self.account[0]]):  # update both old and new acc
            account.updateBalance()

    def on_delete(self):
        self.verification[0].logTransactionChange(self)
        account = self.account[0]
        self.account = []  # make sure this transaction is ignored when recalculating balance
        account.updateBalance()

    @staticmethod
    def sum(**kw):
        # If we're summing transactions on an account that was created in this
        # commit, we don't need to query the DB.
        if kw.keys() == ['account'] and getattr(kw['account'], '_new', False):
            transactions = kw['account'].transactions
        else:
            query = Transaction._query(**kw)
            query.attrList = ['amount', 'quantity']
            transactions = query.run()
        amount = sum((toi.amount[0] for toi in transactions), 0)
        quantity = sum((toi.quantity[0] for toi in transactions), 0)
        return amount, quantity


class ObjectBalanceBudget(Balance):

    class account_balance(Relation(Quantity(1), Unchangeable())):
        related = AccountBalance.object_balance_budgets

    class accounting_object(ToiRef(ToiType(AccountingObject), Quantity(1))):
        pass

    class period(String(Regexp(r'^(\d{6}|)$'), Quantity(1))):
        pass

    @method(ToiRef(ToiType('ObjectBalanceBudget'), Quantity(1)))
    def copy(self,
             account_balance=ToiRef(ToiType(AccountBalance), Quantity(1))):
        accounting = account_balance[0].account[0].accounting
        dimension = Dimension._query(
            accounting=accounting,
            number=self.accounting_object[0].dimension[0].number).run()
        assert dimension != self.accounting_object[0].dimension

        accounting_object = AccountingObject._query(
            number=self.accounting_object[0].number,
            dimension=dimension).run()

        copy = ObjectBalanceBudget(account_balance=account_balance,
                                   accounting_object=accounting_object,
                                   period=[''],
                                   opening_balance=self.opening_balance,
                                   opening_quantity=self.opening_quantity,
                                   balance=self.balance,
                                   balance_quantity=self.balance_quantity,
                                   budget=self.budget,
                                   budget_quantity=self.budget_quantity)
        return [copy]

    def updateBalance(self):
        account = self.account_balance[0].account[0]
        amount, quantity = Transaction.sum(
            account=account,
            accounting_objects=self.accounting_object)

        self.balance = [self.opening_balance[0] + amount]
        self.balance_quantity = [self.opening_quantity[0] + quantity]

    @requireRoles('accountants')
    def on_create(self):
        self.allowRead = self.account_balance[0].allowRead


class BalanceBudget(Balance):

    class account_balance(Relation(Quantity(1), Unchangeable())):
        related = AccountBalance.balance_budgets

    class period(String(Regexp(r'\d{6}'), Quantity(1))):
        pass

    def on_create(self):
        self.allowRead = self.account_balance[0].allowRead


class VatCode(TO):

    vat_table = {
        '10': 25, '11': 12, '12': 6,
        '30': 25, '31': 12, '32': 6
        }

    class code(String(Regexp(r'\d{2}'), Quantity(1))):
        pass

    class xmlCode(String(Quantity(1))):
        pass

    class description(String(QuantityMax(1))):
        pass

    class percentage(Decimal(QuantityMax(1))):
        pass

    def set_percentage(self):
        if not self.percentage:
            percentage = self.vat_table.get(self.code[0])
            self.percentage = [percentage] if percentage else []

    def canWrite(self, user, attrName):
        return False  # Doesn't apply to super user

    def on_create(self):
        if ri.getClientUser():
            raise cBlmError('You may not create VatCodes')
        self.allowRead = self.allowRead + UG._query(name='public').run()
        self.set_percentage()

    def on_update(self, newattrvalues):
        self._update(newattrvalues)
        self.set_percentage()


class BgcOrder(TO):

    class org(ToiRef(Quantity(1), Unchangeable(),
                     post=ToiType(Org))):
        pass

    class creation_date(Timestamp(post=Quantity(1))):

        def on_create(attr, value, self):
            return value or [time.time()]

    class supplierInvoices(Relation()):
        related = 'SupplierInvoice.bgcOrders'

    class trying_to_send(Timestamp(QuantityMax(1))):
        pass

    class sent(Timestamp(QuantityMax(1), Unchangeable())):
        pass

    class order_unsigned(String(QuantityMax(1))):
        pass

    class order_signed(String(QuantityMax(1))):
        pass


class BgcReport(TO):

    class report_type(String()):
        pass

    class multiline(String()):
        pass

    class filename(String(QuantityMax(1))):
        pass

    class time_recieved(Timestamp(post=Quantity(1))):
        def on_create(attr, value, toi):
            return value or [time.time()]

    class time_processed(Timestamp(post=Quantity(1))):
        def on_create(attr, value, toi):
            return value or [time.time()]

    class supplierInvoices(Relation()):
        related = 'SupplierInvoice.bgcReports'

    @method(None)
    def process_data(self):
        report_type = self.multiline[0][46]
        descriptions = {
            '1': 'Payments specification with payment types',
            '2': 'Reconciliation report/payment monitoring',
            '5': 'Cancellations/date amendments',
            '6': 'Rejected payments',
            '7': 'Stopped payments',
            '–': 'Returned money orders',
        }
        description = descriptions[report_type]
        if report_type == '1':
            self.supplierInvoices = parseBankgiroResponseSuccess(self.multiline[0])
        elif report_type == '2':
            # Reconciliation report
            pass
        elif report_type == '6':
            self.supplierInvoices = parseBankgiroResponseRejected(self.multiline[0])
        elif report_type == '7':
            # Stopped payment
            self.supplierInvoices = parseBankgiroResponseStopped(self.multiline[0])
        self.report_type = [report_type]


class InvoiceImage(TO):

    class supplierInvoice(Relation(Quantity(1))):
        related = 'SupplierInvoice.images'

    @requireRoles('accountants')
    def on_create(self):
        self.allowRead = self.supplierInvoice[0].allowRead

    class image(Blob(Quantity(1))):
        pass

    class filename(String(Quantity(1))):
        pass


class SupplierInvoice(TO):

    class org(ToiRef(Quantity(1), Unchangeable(),
                     post=ToiType(Org))):
        pass

    class accounted(Bool(Quantity(1))):
        default = [False]

    class invoiceState(Enum(Quantity(1))):
        values = ['incomplete', 'registered', 'sent', 'paid', 'rejected']
        default = ['incomplete']

    class automated(Bool(Quantity(1))):
        default = [False]

    class recipient(String(Quantity(1))):
        pass

    class invoiceType(Enum(Quantity(1))):
        values = ['debit', 'credit']
        default = ['debit']

    class amount(Decimal(QuantityMax(1))):
        default = [decimal.Decimal('0.00')]
        precision = 2

    class transferMethod(Enum(QuantityMax(1))):
        values = ['bgnum', 'pgnum', 'bankaccount']

    class pgnum(PGNum(QuantityMax(1))):
        def on_create(attr, value, self):
            return [normalize_pgnum(v) for v in value]
        on_update = on_create

    class bgnum(PGNum(QuantityMax(1))):
        def on_create(attr, value, self):
            return [normalize_pgnum(v) for v in value]
        on_update = on_create

    class bankaccount(String(QuantityMax(1))):
        def on_create(attr, value, self):
            return [''.join(c for c in v if c.isdigit()) for v in value]
        on_update = on_create

    class bankclearing(String(QuantityMax(1))):
        def on_create(attr, value, self):
            return [''.join(c for c in v if c.isdigit()) for v in value]
        on_update = on_create

    class transferAddress(String(QuantityMax(1))):
        pass

    def calcTransferAddress(self):
        try:
            transferMethod = self.transferMethod[0]
        except IndexError:
            return
        if transferMethod in ['bgnum', 'pgnum']:
            self.transferAddress = getattr(self, str(transferMethod))[:]
        else:
            # For recipients without bgnum or pgnum, (ie a bank account or money transfer) we
            # need a unique and consistent "credit transfer number" that
            # looks like a bgnum to identify the payment recipient
            # Max length is 6 digits, (5 digits plus luhn).
            try:
                cl = self.bankclearing[0][:4]
                acc = self.bankaccount[0]
            except IndexError:
                return
            try:
                provider, = SupplierInvoiceProvider._query(org=self.org).run()
            except TypeError:
                return
            self.transferAddress = [provider.generateTransferAddress(cl, acc)]

    class invoiceIdentifierType(Enum(QuantityMax(1))):
        values = ['ocr', 'invoiceNumber', 'message']

    class ocr(String(QuantityMax(1))):
        pass

    class invoiceNumber(String(QuantityMax(1))):
        pass

    class message(String(QuantityMax(1))):
        pass

    class invoiceIdentifier(String()):
        def on_computation(attr, self):
            try:
                identifier = getattr(self, str(self.invoiceIdentifierType[0]))[:]
            except IndexError:
                return
            else:
                return identifier

    class registrationVerification(ToiRef(ToiType(Verification), QuantityMax(1))):
        pass

    class transferVerification(ToiRef(ToiType(Verification), QuantityMax(1))):
        pass

    class invoiceDate(String(Regexp(date_re), QuantityMax(1))):
        pass

    class dateInvoiceRegistered(Timestamp(post=Quantity(1))):
        def on_create(attr, value, toi):
            return value or [time.time()]

    class transferDate(String(Regexp(date_re), QuantityMax(1))):
        # Date to begin payment process.
        pass

    class dueDate(String(Regexp(date_re), QuantityMax(1))):
        pass

    class transaction_date(String(Regexp(date_re), QuantityMax(1))):
        # Date when payment was completed.
        pass

    class rejected_log(String()):
        pass

    class bgcOrders(Relation()):
        related = BgcOrder.supplierInvoices

    class bgcReports(Relation()):
        related = BgcReport.supplierInvoices

    @requireRoles('payers')
    def on_create(self):
        self.allowRead = self.org[0].allowRead
        self.calcTransferAddress()

    @requireRoles('payers')
    def on_update(self, newAttrValues):
        self._update(newAttrValues)
        self.calcTransferAddress()

    class images(Relation()):
        related = InvoiceImage.supplierInvoice

    @staticmethod
    def sort_transferDate_key(self):
        try:
            return self['transferDate'][0]
        except IndexError:
            return ''
    sort_transferDate_attrs = ['transferDate', 'dateInvoiceRegistered']

    @staticmethod
    def sort_transferDateDescending_key(self):
        std = SupplierInvoice.sort_transferDate(self)
        std = std.split('-')
        std = -int(std)
        return std
    sort_transferDateDescending_attrs = ['transferDate', 'dateInvoiceRegistered']

    @method(Serializable())
    def suggestVerification(self):
        pass


# methods
@method(None)
def saveSupplierInvoice(org=ToiRef(ToiType(Org), Quantity(1)),
                        invoice=Serializable(Quantity(1)),
                        toid=String(QuantityMax(1))):
    # toid=ToiRef(ToiType(SupplierInvoice), QuantityMax(1))) does not work.
    org = org[0]
    unchecked = invoice[0]

    try:
        regVerLines = unchecked.pop('regVerificationLines')
        regVerVersion = unchecked.pop('regVerificationVersion')
    except KeyError:
        regVerLines = None
        regVerVersion = None

    if toid:
        toid = toid[0]
        # Look for existing SupplierInvoice to update
        try:
            supplierinvoice, = SupplierInvoice._query(org=org.id, id=toid).run()
        except ValueError:
            # Did not find SupplierInvoice, we will create new one later
            supplierinvoice = None
        else:
            #Safety check
            if supplierinvoice.accounted[0]:
                raise cBlmError('Accounted SupplierInvoice is write protected.')
    else:
        toid = None
        supplierinvoice = None

    # Massage data from client.
    invoice = {}
    for key, value in unchecked.items():
        if value != '':
            try:
                invoice[key] = value.strip()
            except AttributeError:
                invoice[key] = value
        else:
            if supplierinvoice is not None:
                # Clear TOI attribute as client changed string to empty string.
                if supplierinvoice[key] != []:
                    invoice[key] = []

    try:
        invoice['amount'] = decimal.Decimal(invoice['amount']) / decimal.Decimal('100.00')
    except TypeError:
        # if amount is None (user cleared input widget)
        invoice['amount'] = decimal.Decimal('0')

    if supplierinvoice is None:
        # Create new SupplierInvoice
        try:
            supplierinvoice = SupplierInvoice(org=org, **invoice)
        except Exception as e:
            raise cBlmError(str(e))
    else:
        # Update existing SupplierInvoice
        try:
            supplierinvoice(**invoice)
        except Exception as e:
            raise cBlmError(str(e))

    result = {}

    if regVerLines is not None:
        # Create or update registration verification
        try:
            regVerId = supplierinvoice.registrationVerification[0].id[0]
        except IndexError:
            regVerId = None
        siRegDate =  datetime.datetime.fromtimestamp(supplierinvoice.dateInvoiceRegistered[0]).date().isoformat()
        if not regVerVersion:
            #Trying to fix bug
            regVerVersion = 0
        verificationToSave = prepareVerification(
            org=org,
            regVerId=regVerId,
            regVerLines=regVerLines,
            regVerVersion=regVerVersion,
            siToid=str(supplierinvoice.id[0]),
            siRegDate=siRegDate
        )
        if regVerId is None:
            saveVerResult, = createVerification([verificationToSave])
        else:
            saveVerResult, = editVerification([verificationToSave])
        supplierinvoice.registrationVerification = TO._query(id=saveVerResult['id']).run()
        result['saveVerResult'] = saveVerResult

    # If verification looks ok, move SI from state 'incomplete' to 'registered'. (or the reverse)
    if supplierinvoice.invoiceState[0] in ['incomplete', 'registered']:
        provider, = SupplierInvoiceProvider._query(org=org.id).run()
        debtaccount, = Account._query(accounting=org.current_accounting, number=provider.account).run()
        if supplierinvoice.invoiceState[0] == 'incomplete':
            # Check if registrationVerification has a transaction to supplier debt account. Consider it registered.
            debtTransactions = Transaction._query(verification=supplierinvoice.registrationVerification, account=debtaccount).run()
            if len(debtTransactions) >= 1:
                supplierinvoice.invoiceState = ['registered']
        elif supplierinvoice.invoiceState[0] == 'registered':
            # If all transactions of the verification has been zeroed,
            #  then revert the SI to draft/incomplete state.
            # This is the only way to back out of an SI that have been registered in the system.
            regTransactions = Transaction._query(verification=supplierinvoice.registrationVerification, account=debtaccount).run()
            if len(regTransactions) == 0:
                supplierinvoice.invoiceState = ['incomplete']

    # Add transaction_date if paid, or else clear it.
    if supplierinvoice.invoiceState[0] == 'paid' and supplierinvoice.transaction_date == []:
        supplierinvoice.transaction_date = [time.strftime('%Y-%m-%d', time.localtime(time.time()))]
    elif supplierinvoice.invoiceState[0] not in ('paid', 'accounted') and supplierinvoice.transaction_date != []:
        supplierinvoice.transaction_date = []

    result['supplierInvoice'] = supplierinvoice
    return [result]


def prepareVerification(org, regVerId, regVerLines, regVerVersion, siToid, siRegDate):
    # This is currently only called from saveSupplierInvoice, and the purouse
    # of splitting it out is to get a more testable saveSupplierInvoice.
    provider, = SupplierInvoiceProvider._query(org=org.id).run()
    series, = VerificationSeries._query(accounting=org.current_accounting, name=provider.series).run()
    debtaccount, = Account._query(accounting=org.current_accounting, number=provider.account).run()

    transdata = []
    for line in regVerLines:
        account, = Account._query(id=ObjectId(line['account'])).run()
        trans = {
            'account': str(account.id[0]),
            'amount': line['amount'],  # Integer Ore conversion happens in saveVerification
            'text': line['text'] if 'text' in line else '',
        }
        if 'id' in line:
            # id can be a valid Transaction toid, or for new transactions: a made up string.
            try:
                transid = ObjectId(line['id'])
            except InvalidId:
                pass
            else:
                trans['id'] = transid
        if 'version' in line:
            if line['version'] is not None:
                trans['version'] = line['version']
        if 'id' not in trans:
            # New transaction
            trans['version'] = 0

        transdata.append(trans)

    verdata = {
            'accounting': str(org.current_accounting[0].id[0]),
            'series': str(series.id[0]),
            'externalRef': str(siToid),
            'transaction_date': siRegDate
    }

    if regVerId is not None:
        # Specify existing registration verification for updating,
        # do not create new verification.
        verdata['id'] = str(regVerId)
        if regVerVersion and regVerVersion > 0:
            # The client should have set version to the existing version + 1.
            verdata['version'] = regVerVersion
        else:
            verdata['version'] = 0

    verification = {
        'verification': verdata,
        'transactions': transdata
    }
    return verification


@method(Serializable)
def deleteSupplierInvoice(org=ToiRef(ToiType(Org), Quantity(1)),
                          supInvList=ToiRef(ToiType(SupplierInvoice))):
    org = org[0]
    deleted = []
    untouched = []
    for si in supInvList:
        if si.invoiceState[0] == 'incomplete':
            deleted.append(str(si.id[0]))
            si._delete()
        else:
            untouched.append(str(si.id[0]))
    return {'deleted': deleted, 'untouched': untouched}


@method(ToiRef(ToiType(InvoiceImage)))
def uploadInvoiceImage(org=ToiRef(ToiType(Org), Quantity(1)), si=ToiRef(ToiType(SupplierInvoice), Quantity(1)), images=Serializable()):
    result = []
    for image in images:
        blob = BlobVal(image['data'].decode('base64'),
                    filename=image['name'],
                    content_type=image['type'])
        toi = InvoiceImage(supplierInvoice=si, image=[blob], filename=image['name'])
        result.append(toi)
    return result


@method(Serializable())
def removeInvoiceImage(imagetoi=ToiRef(ToiType(InvoiceImage), Quantity(1))):
    imagetoi, = imagetoi
    oldimages = imagetoi.supplierInvoice[0].images
    newimages = []
    for i in oldimages:
        if i != imagetoi:
            newimages.append(i)
    imagetoi.supplierInvoice[0].images = newimages
    imagetoi._delete()
    return []


@method(Serializable())
def proposeRecipients(org=ToiRef(ToiType(Org), Quantity(1))):
    org, = org
    SIs = SupplierInvoice._query(org=org).run()
    recipients = sorted(set(si['recipient'][0] for si in SIs))
    return recipients


def pairwise(iterable):
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    a, b = itertools.tee(iterable)
    next(b, None)
    return zip(a, b)


def most_common(lst):
    return max(set(lst), key=lst.count)


def median(lst):
    sortedLst = sorted(lst)
    lstLen = len(lst)
    index = (lstLen - 1) // 2
    if (lstLen % 2):
        return sortedLst[index]
    else:
        return (sortedLst[index] + sortedLst[index + 1])/2.0


@method(Serializable())
def predictSupplierInvoice(org=ToiRef(ToiType(Org), Quantity(1)), recipient=String(Quantity(1))):
    # The user has entered a recipient name, we should suggest back form content based on existing SupplierInvoice TOIs.
    org, = org
    recipient, = recipient

    similarSIQuery = SupplierInvoice._query(org=org, recipient=recipient)
    similarSIQuery._attrList = ['recipient', 'invoiceType', 'amount', 'transferMethod', 'pgnum',
                'bgnum', 'bankaccount', 'bankclearing', 'invoiceIdentifierType',
                'ocr', 'invoiceNumber', 'message', 'invoiceDate', 'transferDate',
                'dueDate']
    similarSI = similarSIQuery.run()
    if not similarSI:
        return []

    dateregex = re.compile(r'\d{4}-\d{2}-\d{2}')

    predictions = []  # Single prediction currently.
    prediction = {}
    for attribute in [
            'recipient', 'invoiceType', 'amount', 'transferMethod', 'pgnum',
            'bgnum', 'bankaccount', 'bankclearing', 'invoiceIdentifierType',
            'ocr', 'invoiceNumber', 'message', 'invoiceDate', 'transferDate',
            'dueDate']:

        # Extract from SupplierInvoices prediction candidates for attribute.
        candidates = []
        for si in similarSI:
            try:
                candidates.append(si[attribute][0])
            except IndexError:
                pass

        # Determine best candidate for prediction
        if len(candidates) == 0:
            # No candidates for this attribute
            continue
        elif len(set(candidates)) == 1:
            # All identical: Easy!
            prediction[attribute], = set(candidates)
            if attribute == 'ocr':
                # Special case: OCR should only be suggested if all are identical.
                continue
        else:
            if attribute in set(('invoiceDate', 'transferDate', 'dueDate')):
                # Dates: find recurrence and extrapolate from the last one.
                dates = [datetime.datetime.strptime(date, "%Y-%m-%d").date() for date in sorted(candidates)]
                timespans = [stop - start for start, stop in pairwise(dates)]
                meantimespan = sum(timespans, datetime.timedelta())/len(timespans)
                # mediantimespan = median(timespans)
                lastdate = sorted(dates)[-1]
                nextdate = lastdate + meantimespan
                while nextdate.weekday() > 4:
                    # Avoid weekend, back up
                    nextdate -= datetime.timedelta(days=1)
                prediction[attribute] = nextdate.isoformat()
            else:
                # Take most common occurance
                prediction[attribute] = most_common(candidates)

    # Extract registration verification lines from accounted SupplierInvoices to recipient.
    similarSI = SupplierInvoice._query(org=org, recipient=recipient, accounted=True).run()
    similarSI.sort(key=SupplierInvoice.sort_transferDate_key)
    verifications = []
    for si in similarSI[-1:]:
        try:
            verifications.append(si.registrationVerification[0])
        except IndexError:
            pass
    transactions = []
    for ver in verifications:
        transactions += ver.transactions
    regVerLines = []
    for t in transactions:
        a, = Account._query(number=t.account[0].number[0], accounting=org.current_accounting[0]).run()
        regVerLines.append({
            'account': a.id[0],
            'text': t.text[0],
            'amount': int(t.amount[0] * 100),
            'version': 0,
        })
    if len(regVerLines) >= 1:
        prediction['regVerificationLinesPrediction'] = regVerLines

    predictions.append(prediction)
    return predictions


@method(Serializable())
def setSIState(org=ToiRef(ToiType(Org), Quantity(1)),
               supInvList=ToiRef(ToiType(SupplierInvoice)),
               newstate=String(Quantity(1))):
    # Handle client (user) requests to change the SupplierInvoice invoiceState.
    org, = org
    updated = []
    complaints = []
    for si in supInvList:
        # Dont touch accounted SI.
        if si.accounted[0]:
            complaints.append("Invoice is accounted.")
            continue
        # User may not change state of automated SI.
        if si.automated[0]:
            complaints.append("Invoice is automated.")
            continue
        # Manual and unaccounted
        if si.invoiceState[0] == 'registered' and newstate[0] == 'paid':
            # User marked invoice as paid manually.
            si(invoiceState=newstate)
            si(transaction_date=[time.strftime('%Y-%m-%d', time.localtime(time.time()))])
            updated.append(si)
        elif si.invoiceState[0] == 'paid' and newstate[0] == 'registered':
            # User unmarked invoice as paid manually.
            si(invoiceState=newstate)
            si(transaction_date=[])
            updated.append(si)
        elif si.invoiceState[0] == 'registered' and newstate[0] == 'sent':
            si(invoiceState=newstate)
            updated.append(si)
        elif si.invoiceState[0] == 'sent' and newstate[0] == 'registered':
            si(invoiceState=newstate)
            updated.append(si)
        elif si.invoiceState[0] == 'sent' and newstate[0] == 'paid':
            si(invoiceState=newstate)
            si(transaction_date=[time.strftime('%Y-%m-%d', time.localtime(time.time()))])
            updated.append(si)
        elif si.invoiceState[0] == 'paid' and newstate[0] == 'sent':
            si(invoiceState=newstate)
            si(transaction_date=[])
            updated.append(si)
        #elif si.invoiceState[0] == 'rejected' and newstate[0] == 'registered':
        #    # Lets do this in disableAutomation instead.
        #    si.invoiceState = newstate
        #    updated.append(si)
        else:
            # incomplete <-> registered is handled by saveSupplierInvoice
            complaints.append('Unsupported status change for manual invoice: '
                              '%s to %s' % (si.invoiceState[0], newstate[0]))
    return {
        'selected': len(supInvList),
        'updated': len(updated),
        'complaints': list(set(complaints))
    }


def _verifySIAutomation(supInvList):
    updated = []
    complaints = set()

    if not supInvList:
        return {
            'updated': updated,
            'complaints': list(complaints),
        }

    q = SupplierInvoice._query(id=supInvList, _attrList=[
        'accounted', 'automated', 'invoiceState',
        'transferAddress', 'invoiceIdentifier', 'org',
        'recipient'])
    supInvList = q.run()

    org = supInvList[0].org[0]

    # Check outgoing bankgiro number
    try:
        bgProvider, = BankgiroProvider._query(org=org).run()
        sender_bgnum = bgProvider.bgnum[0]

        siProvider, = SupplierInvoiceProvider._query(org=org).run()

        debtaccount, = Account._query(
            accounting=org.current_accounting[0].id[0],
            number=siProvider.account[0]
        ).run()

        series, = VerificationSeries._query(
            accounting=org.current_accounting[0].id[0],
            name=siProvider.series[0]
        ).run()

        bank_account, = Account._query(
            accounting=org.current_accounting[0].id[0],
            number=siProvider.bank_account[0]
        ).run()

    except (IndexError, ValueError):
        complaints.add('Bankgiro provider settings incomplete.')
        return {
            'updated': updated,
            'complaints': list(complaints),
        }

    for si in supInvList:
        assert si.org[0] == org
        # Dont touch accounted SI.
        if si.accounted[0] is True:
            complaints.add("Invoice is accounted.")
            continue
        elif si.automated[0]:
            complaints.add("Invoice is already automated.")
            continue
        elif si.invoiceState[0] == 'registered':
            # User want us to transfer the money with Bankgirot LB, we
            # should check that everything is in order to do so.
            if not si.transferAddress[0] or not si.invoiceIdentifier[0]:
                complaints.add('Invoice does not contain enough '
                                  'information for automatic payment.')
                continue
            else:
                # No problems found
                updated.append(si)
        else:
            complaints.add('Could not enable automation of invoice in '
                              'state %s for %s' % (si.invoiceState[0],
                                                   si.recipient[0]))
    return {
        'updated': updated,
        'complaints': list(complaints),
    }


@method(String(Quantity(1)))
def requestSIAutomation(org=ToiRef(ToiType(Org), Quantity(1)),
                        supInvList=ToiRef(ToiType(SupplierInvoice))):
    result = _verifySIAutomation(supInvList)
    if result['complaints']:
        raise cBlmError(str(result['complaints']))

    if not currentUserHasRole(org, 'payers'):
        raise cBlmError('You must be a payer.')

    user = ri.getClientUser()
    try:
        ssn = user.personNum[0]
    except IndexError:
        raise cBlmError('You must be registered with a personnummer')

    extra_data = spickle.dumps([str(toi.id[0]) for toi in supInvList])

    lines = []
    for toi in supInvList:
        line = '%s: %s' % (toi.recipient[0], toi.amount[0])
        lines.append(line)
    text = '\n'.join(lines)
    title = u'Godkänn utbetalningar'
    response = freja.request_signature(ssn, title=title, text=text,
                                       extra_data=extra_data)
    return [response['signRef']]


@method(String(Quantity(1)))
def getSignatureResultAndApprovePayment(signRef=String(Quantity(1))):
    status, toids = freja.get_result(signRef[0])
    if status == 'APPROVED':
        enableSIAutomation(toids)
        return ['SCHEDULED']

    elif status in ['CANCELED', 'RP_CANCELED', 'EXPIRED']:
        return ['FAILED']

    return ['PENDING']


def enableSIAutomation(supInvList):
    result = _verifySIAutomation(supInvList)
    for si in result['updated']:
        si(automated=[True])
    return result


@method(Serializable())
def disableSIAutomation(org=ToiRef(ToiType(Org), Quantity(1)), supInvList=ToiRef(ToiType(SupplierInvoice))):
    org, = org
    updated = []
    complaints = []
    for si in supInvList:
        # Dont touch accounted SI.
        if si.accounted[0] is True:
            complaints.append("Invoice is accounted!")
            continue
        if si.automated[0] is False:
            complaints.append("Invoice is not automated.")
            continue
        if si.invoiceState[0] == 'registered' and si.automated[0]:
            si(automated=[False])
            updated.append(si)
        elif si.invoiceState[0] == 'rejected' and si.automated[0]:
            # Clear rejected status.
            si(automated=[False])
            si(invoiceState=['registered'])
            updated.append(si)
        else:
            complaints.append(
                "Unable to disable automation for invoice in state " + str(si.invoiceState[0])
            )
    return {'selected': len(supInvList), 'updated': len(updated), 'complaints': list(set(complaints))}


@method(Serializable())
def generatePlusgiroFile(org=ToiRef(ToiType(Org), Quantity(1)), supInvList=ToiRef(ToiType(SupplierInvoice))):
    supInvList = [si for si in supInvList if not si.accounted[0]]
    supInvList = [si for si in supInvList if not si.automated[0]]
    supInvList = [si for si in supInvList if si.invoiceState[0] == 'registered']
    if len(supInvList) < 1:
        raise cBlmError('No invoices suitable for payment.')
    org = org[0]
    supplierinvoiceprovider, = SupplierInvoiceProvider._query(org=org).run()
    try:
        sending_bank_account = supplierinvoiceprovider.plusgiro_sending_bank_account[0]
        assert len(sending_bank_account) > 0
    except (IndexError, AssertionError) as e:
        raise cBlmError('Unable to find Plusgiro sending bank account, check your Settings.')
    lines = plusgiro.generatePlusgiroRecords(
        org=org,
        sending_bank_account=sending_bank_account,
        supInvList=supInvList
    )
    filecontent = '\n'.join(lines) + '\n'
    return [filecontent]


def createBgcOrder(org, bankgiroProvider, supInvList):
    # Make sure we did not already create a BgcOrder.
    # Failed BgcOrders (sent and rejected) should not prevent creating a new one.
    filtered = []
    for si in supInvList:
        for bgcOrder in si.bgcOrders:
            if bgcOrder.sent == []:
                break
        else:
            filtered.append(si)
    supInvList = filtered
    if len(supInvList) < 1:
        return []
    order_unsigned = bankgiro.transferOrderBankgiro(bankgiroProvider=bankgiroProvider, supInvList=supInvList)
    bgcOrder = BgcOrder(org=[org], order_unsigned=order_unsigned, supplierInvoices=supInvList)
    return bgcOrder


@method(ToiRef(ToiType(BgcOrder)))
def createSignedBgcOrder(org=ToiRef(ToiType(Org), Quantity(1)), supInvList=ToiRef(ToiType(SupplierInvoice))):
    # Called by bin/sendbgorders.py
    org ,= org
    bankgiroProvider, = BankgiroProvider._query(org=org).run()
    bgcOrder = createBgcOrder(org=org, bankgiroProvider=bankgiroProvider, supInvList=supInvList)
    if not bgcOrder:
        return []
    signedBgcOrder = bankgiro.signBgcOrder(bgcOrder=bgcOrder)
    return [signedBgcOrder]


@method(Serializable())
def writeBankgiroTransferOrder(org=ToiRef(ToiType(Org), Quantity(1)), supInvList=ToiRef(ToiType(SupplierInvoice))):
    # Used in developement from GUI client.
    bgcOrder, = createSignedBgcOrder(org=org, supInvList=supInvList)
    result = writeBgcOrder(bgcOrder=[bgcOrder])
    return result


def writeBgcOrder(bgcOrder=ToiRef(ToiType(BgcOrder), Quantity(1))):
    bgcOrder ,= bgcOrder
    order_signed = bgcOrder.order_signed[0]
    order_signed = order_signed.encode('latin-1')
    assert bgcOrder.sent == []
    for si in bgcOrder.supplierInvoices:
        if not (si.invoiceState[0] == 'registered' and si.automated[0] is True):
            raise cBlmError('State should be registered and automated.')
    bgcOrder.trying_to_send = [time.time()]
    filename = config.config.get('bankgiro', 'filename')
    with tempfile.NamedTemporaryFile(prefix=filename+'.', delete=False) as f:
        f.write(order_signed)
    bgcOrder.sent = [time.time()]
    for si in bgcOrder.supplierInvoices:
        si.invoiceState = ['sent']
    return [f.name]


@method(Serializable())
def sendBgcOrder(bgcOrder=ToiRef(ToiType(BgcOrder), Quantity(1))):
    # Called by bin/sendbgorders.py
    bgcOrder ,= bgcOrder
    order_signed = bgcOrder.order_signed[0]
    order_signed = order_signed.encode('latin-1')
    # Safety checks
    for si in bgcOrder.supplierInvoices:
        if not (si.invoiceState[0] == 'registered' and si.automated[0] is True):
            raise cBlmError('State should be registered and automated.')
    if not bgcOrder.sent == []:
        raise cBlmError('Order previously sent.', str(bgcOrder.sent[0]))
    if bgcOrder.trying_to_send != []:
        log.warn("Warning: Sending already attempted upload: bgcOrder %s" % str(bgcOrder.id[0]))

    # Try sending order
    bgcOrder.trying_to_send = [time.time()]
    result = sftp_bgc.sftpBgcOrder(
        order_signed=order_signed,
    )

    # Record success
    bgcOrder.sent = [time.time()]
    for si in bgcOrder.supplierInvoices:
        si.invoiceState = ['sent']
    return [result]


def identifyOrgsWithDueTransfers():
    supInvAll = SupplierInvoice._query(invoiceState='registered', automated=True).run()
    supInvAll.sort(key=SupplierInvoice.sort_transferDate_key)
    supInvDue = []
    for si in supInvAll:
        if bankgiro.bg_transferdate(si) == 'GENAST':
            supInvDue.append(si)
    orgs = list(set((si.org[0] for si in supInvDue)))
    return orgs


def identifyDueTransfers(org):
    supInvOrg = SupplierInvoice._query(org=org, invoiceState='registered', automated=True).run()
    supInvOrg.sort(key=SupplierInvoice.sort_transferDate_key)
    supInvOrgDue = []
    for si in supInvOrg:
        if bankgiro.bg_transferdate(si) == 'GENAST':
            supInvOrgDue.append(si)
    return supInvOrgDue


def cancellationOrderRecord(supplierInvoice, bankgiroProvider):
    # Amendment code for cancellation of entire file not clearly defined in documentation.
    # So we use cancellation of single payment order instead.
    amendment_code = '14' # KK14 for cancelling single payment
    payee_number = supplierInvoice.transferAddress[0]
    sender_customer_number = config.config.get('bankgiro', 'service_bureau_number')
    sender_bgnum = bankgiroProvider.bgnum[0]
    amount = supplierInvoice.amount[0]
    if supplierInvoice.transferMethod[0] == 'pgnum':
        pgtype = 'PGBET'
    else:
        pgtype = ''
    cancellation_record = u'LB{0!:s:2}{1!s:0>6}{2!s:0>10}{3!s:0>10}{4!s:6}{5!s:6}{6!s:0>12}{7!s:12}{8!s:5}{9!s:3}{10!s:3}{11!s:3}'.format(
        amendment_code,
        sender_customer_number,
        sender_bgnum,
        payee_number,
        '',  # specified date
        '',  # new date
        amount,
        '',  # reserved
        pgtype,
        'SEK',  # Currency
        '',  # reserved
        ''   # reserved for BGC
    )
    return cancellation_record


@method(Serializable())
def cancelBgcOrder(bgcOrder=ToiRef(ToiType(BgcOrder), Quantity(1))):
    bgcOrder ,= bgcOrder
    records = []
    for si in bgcOrder.supplierInvoices:
        org = si.org[0]
        bankgiroProvider = BankgiroProvider._query(org=org).run()[0]
        r = cancellationOrderRecord(supplierInvoice=si, bankgiroProvider=bankgiroProvider)
        records.append(r)
    unsinged_order = ('\n'.join(records) + '\n').encode('latin-1', 'replace')
    cancelationOrder = BgcOrder(
        org=[org],
        supplierInvoices=bgcOrder.supplierInvoices,
        order_unsigned=[unsinged_order]
    )
    cancelationOrder = bankgiro.signBgcOrder(cancelationOrder)
    #result = sendBgcOrder(bgcOrder=cancelationOrder)  # Does not work due to safety checks # TODO
    return [cancelationOrder]


@method(Serializable())
def bgcOrderCancellation(supplierInvoice=ToiRef(ToiType(SupplierInvoice), Quantity(1))):
    si ,= supplierInvoice
    records = []
    org = si.org[0]
    bankgiroProvider = BankgiroProvider._query(org=org).run()[0]
    r = cancellationOrderRecord(supplierInvoice=si, bankgiroProvider=bankgiroProvider)
    records.append(r)
    unsinged_order = ('\n'.join(records) + '\n').encode('latin-1', 'replace')
    cancelationOrder = BgcOrder(
        org=[org],
        supplierInvoices=bgcOrder.supplierInvoices,
        order_unsigned=[unsinged_order]
    )
    cancelationOrder = bankgiro.signBgcOrder(cancelationOrder)
    #result = sendBgcOrder(bgcOrder=cancelationOrder)  # Does not work due to safety checks # TODO
    return [cancelationOrder]


@method(Serializable())
def createTransferVerification(org=ToiRef(ToiType(Org), Quantity(1)), supInvList=ToiRef(ToiType(SupplierInvoice))):
    org, = org
    result = {'verifications': [], 'accounted': []}
    try:
        provider, = SupplierInvoiceProvider._query(org=org).run()
        bank_transaction_text = provider.transferVerification_text[0]
        debtaccount, = Account._query(accounting=org.current_accounting[0].id[0],
                                      number=provider.account[0]).run()
        series, = VerificationSeries._query(accounting=org.current_accounting[0].id[0],
                                            name=provider.series[0]).run()
        bank_account, = Account._query(accounting=org.current_accounting[0].id[0],
                                       number=provider.bank_account[0]).run()
    except ValueError:
        raise cBlmError('Problem with settings.')

    # Safety check
    for si in supInvList:
        if si.invoiceState[0] != 'paid' or si.accounted[0]:
            raise cBlmError("Can only create transfer verification for paid "
                            "and unaccounted supplier invoices.")
        if len(si.transaction_date) != 1:
            raise cBlmError("Missing transaction date.")

    siListByDate = collections.defaultdict(list)
    for si in supInvList:
        siListByDate[si.transaction_date[0]].append(si)

    dates = sorted(siListByDate.keys())
    for transaction_date in dates:
        siListDay = siListByDate[transaction_date]

        regVerList = []
        supInvAccounted = []
        for si in siListDay:
            if si.invoiceState[0] == 'paid' and si.accounted[0] is False:
                regVerList.append(si.registrationVerification[0])
                regTransactions = Transaction._query(verification=regVerList,
                                                     account=debtaccount).run()
        if len(regTransactions) < len(regVerList):
            raise cBlmError("At least one registration verification is missing "
                            "transaction for supplier debt account.")

        # Create indata for saveVerification
        totalamount = decimal.Decimal('0.0')
        transdata = []
        for rt in regTransactions:
            amount = rt.amount[0]
            totalamount += amount
            trans = {
                'account': str(debtaccount.id[0]),
                'amount': -amount * decimal.Decimal('100'),  # Integer Ore
                'text': rt.text[0] if rt.text else '',
                'version': 0,
            }
            transdata.append(trans)

        banktrans = {
            'account': str(bank_account.id[0]),
            'amount': totalamount * decimal.Decimal('100'),  # Integer Ore
            'text': bank_transaction_text,
            'version': 0,
        }
        transdata.append(banktrans)

        verdata = {
            'accounting': str(org.current_accounting[0].id[0]),
            'series': str(series.id[0]),
            'externalRef': str(siListDay),
            'transaction_date': str(transaction_date),
        }

        verification = {
            'verification': verdata,
            'transactions': transdata
        }
        saveResult, = createVerification([verification])
        result['verifications'].append(saveResult)
        transferVerification, = TO._query(id=saveResult['id']).run()
        for si in siListDay:
            si(transferVerification=[transferVerification])
            si(accounted=[True])
            supInvAccounted.append(si)
        result['accounted'] += supInvAccounted
    return [result]


def parseBankgiroResponseSuccess(responsefile):
    # Query prevents move to bankgiro.py
    responsefile = responsefile.encode('iso8859-1')
    parser = LBSuccessParser()
    flines = responsefile.splitlines()
    for line in flines:
        parser.parse(line)
    # Completed transactions
    silist = []
    for section in parser.sections:
        possible_toid20s = section.completed_transactions
        toids = []
        for s in possible_toid20s:
            toid = bankgiro.findToi(s)
            if toid is not None:
                toids.append(str(toid))
        silist += SupplierInvoice._query(id=toids).run()
    for si in silist:
        assert si.automated[0] is True
        assert si.invoiceState[0] == 'sent'
        si.invoiceState = ['paid']
        si.transaction_date = [time.strftime('%Y-%m-%d', time.localtime(time.time()))]
    # Create one transferVerification per Org
    orgs = list(set([si.org[0] for si in silist]))
    for org in orgs:
        orgsilist = [si for si in silist if si.org[0] == org]
        createTransferVerification(org=[org], supInvList=orgsilist)
    return silist


def parseBankgiroResponseRejected(responsefile):
    # Query prevents move to bankgiro.py
    responsefile = responsefile.encode('iso8859-1')
    parser = LBRejectedParser()
    flines = responsefile.splitlines()
    for line in flines:
        parser.parse(line)
    # Rejected transactions
    silist = []
    for section in parser.sections:
        possible_toid20s = section.rejected_transactions
        toids = []
        for s in possible_toid20s:
            toid = bankgiro.findToi(s)
            if toid is not None:
                toids.append(str(toid))
        rejection_errors = section.rejection_errors
        error_map = dict(zip(toids, rejection_errors))
        silist += SupplierInvoice._query(id=toids).run()
    for si in silist:
        assert si.automated[0] is True
        assert si.invoiceState[0] == 'sent'
        si.invoiceState = ['rejected']
        si.transaction_date = []
        error = error_map[str(si.id[0])]
        assert str(si.id[0]) == bankgiro.decode_toid20(error[1])
        si.rejected_log = [' '.join(error[2:])]
    return silist


def parseBankgiroResponseStopped(responsefile):
    # Query prevents move to bankgiro.py
    responsefile = responsefile.encode('iso8859-1')
    parser = LBStoppedPaymentsParser()
    flines = responsefile.splitlines()
    for line in flines:
        parser.parse(line)
    # Stopped transactions
    silist = []
    for section in parser.sections:
        possible_toid20s = section.stopped_payments
        toids = []
        for s in possible_toid20s:
            toid = bankgiro.findToi(s)
            if toid is not None:
                toids.append(str(toid))
        rejection_errors = section.comments
        error_map = dict(zip(toids, rejection_errors))
        silist += SupplierInvoice._query(id=toids).run()
    for si in silist:
        assert si.automated[0] is True
        assert si.invoiceState[0] == 'sent'
        si.invoiceState = ['rejected']
        si.transaction_date = []
        error = error_map[str(si.id[0])]
        # si.rejected_log = [' '.join(error[2:])]
        si.rejected_log = ['Payment stopped due to insufficient funds on sender account.' + ' '.join(error[2:])]
    return silist


@method(None)
def updateSupplierInvoiceProvider(org=ToiRef(ToiType(Org), Quantity(1)), settings=Serializable(Quantity(1))):
    org = org[0]
    settings = settings[0]
    try:
        supplierinvoiceprovider, = SupplierInvoiceProvider._query(org=org).run()
    except ValueError:
        # Did not find provider, so create one
        SupplierInvoiceProvider(org=org, **settings)
    else:
        supplierinvoiceprovider(**settings)


def parsedate(source):
    fmt = '%Y-%m-%d'
    return datetime.datetime.strptime(source, fmt)


@method(ToiRef(ToiType(Accounting), Quantity(1)))
def newAccountingFromLastYear(org=ToiRef(ToiType(Org), Quantity(1))):
    try:
        return org[0].current_accounting[0].new()
    except IndexError:
        return []


@method(String())
def transactionIndex(direct_data=Serializable()):
    data, = direct_data
    for filter in data['filter']:
        if filter['property'] == 'org':
            orgid = filter['value']
            break
    else:
        raise ValueError('Unknown Org')

    accountings = Accounting._query(org=orgid).run()
    accounts = Account._query(accounting=accountings).run()
    transactions = Transaction._query(account=accounts,
                                      _attrList=['text']).run()
    texts = set(transaction.text[0] for transaction in transactions)
    texts.discard('')
    return [{'text': text, 'org': orgid} for text in texts]


def accounts_layout(accounting=ToiRef(ToiType(Accounting), Quantity(1))):
    q = Account._query(accounting=accounting)
    q.attrList = ['number', 'name', 'type']
    accounts = q.run()
    accounts = sorted(accounts, key=lambda acc: acc.number[0])
    return accounts


def account_query(accounting, accountNumbers=None, full=False):
    if accountNumbers:
        q = Account._query(accounting=accounting,
                           number=accountNumbers)
    else:
        q = Account._query(accounting=accounting)

    q.attrList = ['number', 'name', 'account_balances', 'transactions']
    accounts = q.run()
    if not full:
        accounts = [a for a in accounts
                    if a.opening_balance[0] or a.transactions]
    accounts = sorted(accounts, key=lambda acc: acc.number[0])
    return accounts


def load_verifications(accounts):

    q = AccountBalance._query()  # xxx limit selection
    q.attrList = ['year', 'opening_balance']
    q.run()

    q = Transaction._query(account=accounts)
    q.attrList = ['text', 'verification', 'amount']
    transactions = q.run()

    q = Verification._query(transactions=transactions)
    q.attrList = ['series', 'number', 'transaction_date']
    q.run()

    return accounts


def main_ledger_report(accounting=ToiRef(ToiType(Accounting), Quantity(1)),
                       accountNumbers=String()):
    accounts = account_query(accounting, accountNumbers=accountNumbers)
    return load_verifications(accounts)


def balance_report(accounting=ToiRef(ToiType(Accounting), Quantity(1))):
    accounts = account_query(accounting)
    accounts = [a for a in accounts if a.number[0][0] in '12']
    return load_verifications(accounts)


def income_statement_report(accounting=ToiRef(ToiType(Accounting), Quantity(1))):
    accounts = account_query(accounting)
    accounts = [a for a in accounts if a.number[0][0] not in '12']
    return load_verifications(accounts)


def year_report(accounting=ToiRef(ToiType(Accounting), Quantity(1))):
    accounts = account_query(accounting, full=True)
    accounts = [a for a in accounts if a.number[0][0] not in '12']
    return load_verifications(accounts)


def period_report(accounting=ToiRef(ToiType(Accounting), Quantity(1))):
    accounts = account_query(accounting, full=True)
    accounts = [a for a in accounts if a.number[0][0] not in '12']  #not balance accounts
    return load_verifications(accounts)  #returns all acounts that are not balance accounts and
                                                                #for the current year?


@method(ToiRef(ToiType(Accounting), Quantity(1)))
def accountingImport(org=ToiRef(ToiType(Org), Quantity(1)),
                     data=Blob(Quantity(1))):
    from accounting import sie_import
    importer = sie_import.SIEImporter(org=org)
    importer.parse(data[0])
    importer.accounting.ensureSeries()
    return [importer.accounting]


@method(Serializable())
def sugestAddedVerifications(data=String()):
    pass


@method(None)
def bootstrap():
    if not UG._query(name='public').run():
        UG(name=['public'])

    oeorg = Org._query(orgnum=Org._oeOrgNum).run()
    if not oeorg:
        oeorg = [Org(name=['Open End'],
                     orgnum=[Org._oeOrgNum],
                     subscriptionLevel='subscriber',
                     email='someWhere@foo.org')]

    if not PlusgiroProvider._query(org=oeorg).run():
        PlusgiroProvider(org=oeorg, account=['1920'], series=['A'],
                         pgnum=['47305008'], pgnum_real=['6840193'])

    if not BankgiroProvider._query(org=oeorg).run():
        BankgiroProvider(org=oeorg, account=['1930'], series=['A'],
                         bgnum=['54456371'])

    vatCodes = {
        '05': ('ForsMomsEjAnnan', u'Momspliktig försäljning'),
        '06': ('UttagMoms', u'Momspliktiga uttag'),
        '07': ('UlagMargbesk', u'Beskattningsunderlag vid vinstmarginalbeskattning'),
        '08': ('HyrinkomstFriv', u'Hyresinkomster vid frivillig skattskyldighet'),
        '10': ('MomsUtgHog', u'Utgående moms försäljning - 25%'),
        '11': ('MomsUtgMedel', u'Utgående moms försäljning - 12%'),
        '12': ('MomsUtgLag', u'Utgående moms försäljning - 6%'),
        '20': ('InkopVaruAnnatEg', u'Inköp av varor från annat EU-land'),
        '21': ('InkopTjanstAnnatEg', u'Inköp av tjänster från annat EU-land'),
        '22': ('InkopTjanstUtomEg', u'Inköp av tjänster från land utanför EU'),
        '23': ('InkopVaruSverige', u'Inköp av varor i Sverige'),
        '24': ('InkopTjanstSverige', u'Övriga inköp av tjänster'),
        '30': ('MomsInkopUtgHog', u'Utgående moms inköp - 25%'),
        '31': ('MomsInkopUtgMedel', u'Utgående moms inköp - 12%'),
        '32': ('MomsInkopUtgLag', u'Utgående moms inköp - 6%'),
        '35': ('ForsVaruAnnatEg', u'Försäljning av varor till annat EU-land'),
        '36': ('ForsVaruUtomEg', u'Försäljning av varor utanför EU'),
        '37': ('InkopVaruMellan3p', u'Mellanmans inköp av varor vid trepartshandel'),
        '38': ('ForsVaruMellan3p', u'Mellanmans försäljning av varor vid trepartshandel'),
        '39': ('ForsTjSkskAnnatEg', u'Försäljning av tjänster till näringsidkare i annat EU-land '),
        '40': ('ForsTjOvrUtomEg', u'Övrig försäljning av tjänster omsatta utanför Sverige'),
        '41': ('ForsKopareSkskSverige', u'Försäljning när köparen är skattskyldig i Sverige'),
        '42': ('ForsOvrigt', u'Övrig momsfri försäljning m.m.'),
        '48': ('MomsIngAvdr', u'Ingående moms att dra av'),
        '49': ('MomsBetala', u'Moms att betala eller få tillbaka')
        }

    for code, (xmlCode, description) in vatCodes.items():
        if not VatCode._query(code=code).run():
            VatCode(code=[code], xmlCode=[xmlCode], description=[description])


@method(None)
def upgrade():
    log.info('Upgrading accounting BLM')
