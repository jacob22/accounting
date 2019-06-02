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

import os
import pytransact.testsupport
from pytransact.testsupport import BLMTests, Time
from contextlib import contextmanager

try:
    from cookielib import Cookie
except ImportError:
    from http.cookiejar import Cookie

from flask import request_started, appcontext_pushed, g, session, request
import time
import flask
import lxml.html
import accounting.direct
from .. import wsgi

import blm.accounting


@contextmanager
def user_set(app, user):
    # this is the preferred way of faking the user
    # wsgi._fake_user is deprecated!
    @app.before_request
    def handler():
        g.user = user

    try:
        yield
    finally:
        f = app.before_request_funcs[None].pop()
        assert f is handler


class TestDirectInterface(object):

    def setup_method(self, method):
        self.app = wsgi.app.test_client()
        self.user = object()

        wsgi.app.before_request(self._fake_user)

    def _fake_user(self):
        g.user = self.user

    def teardown_method(self, method):
        f = wsgi.app.before_request_funcs[None].pop()
        if PYT3:
            assert f.__name__ is self._fake_user.__name__
        else:
            assert f.im_func is self._fake_user.im_func

    def test_api(self, monkeypatch):
        def api(baseurl, tocnames):
            assert baseurl.endswith('/router/')
            assert 'accounting.Accounting' in tocnames  # lazy, don't test all tocs
            return 'foo'
        monkeypatch.setattr(accounting.direct, 'api', api)

        result = self.app.get('/api')
        assert result.mimetype == 'application/javascript'
        assert result.data == b'foo'

    def test_route(self, monkeypatch):
        class FakeRouter(object):
            routers = []
            def __init__(self, database, user):
                self.routers.append(self)
                self.database = database
                self.user = user

            def route(self, blmname, request):
                self.blmname = blmname
                self.request = request
                return 'a result'

        monkeypatch.setattr(accounting.direct, 'Router', FakeRouter)
        result = self.app.post('/router/foo')
        assert result.data == b'a result'

        router, = FakeRouter.routers
        assert router.database.name == pytransact.testsupport.dbname
        assert router.user == self.user
        assert router.blmname == 'foo'


class TestUser(BLMTests):
    def setup_method(self,method):
        super(TestUser, self).setup_method(method)

        user = blm.accounting.User()
        apiuser = blm.accounting.APIUser()
        self.commit()
        self.user, = blm.accounting.User._query(id=user).run()
        self.apiuser, = blm.accounting.APIUser._query(id=apiuser).run()

    def test_lookup_current_user_user(self):
        with wsgi.app.test_request_context('/'):
            flask.session['userid'] = self.user.id[0]
            wsgi.lookup_current_user()
            assert flask.g.user == self.user


    def test_lookup_current_user_apiuser(self):
        with wsgi.app.test_request_context('/', headers={
            'Authorization': 'Bearer %s' % self.apiuser.key[0]}):
            # Check that Authorization header wins
            flask.session['userid'] = self.user.id[0]
            wsgi.lookup_current_user()
            assert flask.g.user == self.apiuser


    def test_lookup_current_user_lastaccess(self):
        with Time() as time:
            with wsgi.app.test_request_context('/'):
                flask.session['userid'] = self.user.id[0]
                wsgi.lookup_current_user()
                assert flask.g.user == self.user
                self.user._attrData.clear()
                assert self.user.lastAccess == [time.now]
                oldtime = time.now
                time.step()
                wsgi.lookup_current_user()
                self.user._attrData.clear()
                assert self.user.lastAccess == [oldtime]

                time += 12*60*60
                wsgi.lookup_current_user()
                self.user._attrData.clear()
                assert self.user.lastAccess == [time.now]


class TestLogin(object):

    def setup_method(self, method):
        self.app = wsgi.app
        self.user = object()

    def test_login_redirect_without_next(self):
        with user_set(self.app, self.user):
            with self.app.test_client() as c:
                resp = c.get('/login',
                             # make sure referer is ignored:
                             headers={'referer': 'http://example.com/'})
                assert resp.status_code == 302
                assert resp.location == request.url_root

    def test_login_redirect_with_next(self):
        with user_set(self.app, self.user):
            with self.app.test_client() as c:
                resp = c.get('/login?next=http://example.com/')
                assert resp.status_code == 302
                assert resp.location == 'http://example.com/'

class TestCreateOrLogin(BLMTests):

    def setup_method(self, method):
        super(TestCreateOrLogin, self).setup_method(method)
        self.user1 = blm.accounting.User(openid=['http://user1'], name=['user1'])
        self.user2 = blm.accounting.User(openid=['oauth://user2'], name=['user2'])
        self.commit()

        self.app = flask.Flask(__name__)
        self.app.secret_key = 's3kr1t'
        @self.app.route('/create_profile')
        def create_profile():
            pass

    @contextmanager
    def request_context(self, url):
        with self.app.test_request_context(url) as c:
            flask.g.database = self.database
            flask.g.user = None
            yield c

    def fakeResp(self, **kw):
        class FakeIdResp(object):
            def __init__(self, **kw):
                self.__dict__.update(kw)

        return FakeIdResp(**kw)

    def test_openid(self):
        with self.request_context('/') as c:
            fake = self.fakeResp(identity_url = 'http://user1',
                                 fullname=['user1'], email=['1@users'])
            resp = wsgi.create_or_login(fake)
            assert flask.session['userid'] == self.user1.id[0]
            assert resp.status_code == 302

    def test_openid_new(self):
        with self.request_context('/') as c:
            fake = self.fakeResp(identity_url = 'http://newuser',
                                 fullname=['newuser'], email=['new@users'])
            resp = wsgi.create_or_login(fake)
            assert flask.session['openid'] == 'http://newuser'
            assert resp.headers['Location'].startswith('/create_profile')

class TestInvoice(BLMTests):

    def setup_method(self, method):
        super(TestInvoice, self).setup_method(method)
        self.org = blm.accounting.Org(name='ACME Inc.')
        blm.accounting.VatCode(code='10', percentage='25', xmlCode='vc10')
        blm.accounting.VatCode(code='11', percentage='12', xmlCode='vc11')

        self.accounting = blm.accounting.Accounting(org=self.org)
        self.acc3000 = blm.accounting.Account(accounting=self.accounting,
                                              number='3000')
        self.acc2611 = blm.accounting.Account(accounting=self.accounting,
                                              number='2611', vatCode='10')
        self.acc2621 = blm.accounting.Account(accounting=self.accounting,
                                              number='2621', vatCode='11')

        self.product1 = blm.members.Product(name='Cream of Vanity',
                                            org=self.org,
                                            accountingRules={'3000': '100'},
                                            vatAccount='2611')
        self.product2 = blm.members.Product(name='Food',
                                            org=self.org,
                                            accountingRules={'3001': '50'},
                                            vatAccount='2621',
                                            makeTicket=[True])
        self.purchase = blm.members.Purchase(
            org=self.org,
            items=[blm.members.PurchaseItem(product=self.product1),
                   blm.members.PurchaseItem(product=self.product2)])

        self.payment = blm.members.Payment(matchedPurchase=[self.purchase],
                                           amount=['181.00'])

        self.commit()
        self.app = wsgi.app.test_client()

    def test_invoice(self):
        url = self.purchase.invoiceUrl[0]
        response = self.app.get(url)
        assert response.status_code == 200
        html = response.data
        tree = lxml.html.fromstring(html)

        sum_el, = tree.cssselect('.total.numeric')
        assert sum_el.text_content() == '181.00'

        vats = tree.cssselect('.vat span')
        assert vats[0].text_content() == 'VAT 25%: 25.00'
        assert vats[1].text_content() == 'VAT 12%: 6.00'

        tickets = tree.cssselect('form#getTickets')
        assert tickets[0].action == self.purchase.ticketsUrl[0]


class TestGetTickets(BLMTests):

    def set_cookie(self, key, value):
        self.app.cookie_jar.set_cookie(Cookie(
                None, key, value, None, None, '.', *((None,)*10)))

    def setup_method(self, method):
        super(TestGetTickets, self).setup_method(method)
        self.org = blm.accounting.Org(name='ACME Inc.',
                                      address='foo',
                                      phone='123')

        self.user = blm.accounting.User(
            ugs=self.org.ticketchecker_ug)

        self.product = blm.members.Product(org=[self.org], name=['foo'],
                                           accountingRules={'1234': '27'},
                                           optionFields=['\x1f'.join('abcde'),
                                                         '\x1f'.join('fghij')],
                                           makeTicket=[True])
        self.item = blm.members.PurchaseItem(product=[self.product])
        self.purchase = blm.members.Purchase(items=[self.item],
                                             paymentState=['paid'])

        self.commit()
        self.app = wsgi.app.test_client()

    def test_getTickets(self, tmpdir):
        # sanity
        assert not blm.members.Ticket._query().run()
        url = self.purchase.ticketsUrl[0]
        response = self.app.get(url)
        self.sync()
        assert response.mimetype == 'application/pdf'
        with tmpdir.join('foo.pdf').open('wb') as f:
            f.write(response.data)
        os.system('pdftotext %s' % f.name)
        with tmpdir.join('foo.txt').open() as f:
            text = f.read()
            assert 'ACME Inc.' in text
        self.pushnewctx()
        assert blm.members.Ticket._query().run()


class TestTicket(BLMTests):

    def set_cookie(self, key, value):
        self.app.cookie_jar.set_cookie(Cookie(
                None, key, value, None, None, '.', *((None,)*10)))

    def setup_method(self, method):
        super(TestTicket, self).setup_method(method)
        self.org = blm.accounting.Org(name='ACME Inc.')

        self.user = blm.accounting.User(
            ugs=self.org.ticketchecker_ug)

        self.product = blm.members.Product(org=[self.org], name=['foo'],
                                           accountingRules={'1234': '27'},
                                           optionFields=['\x1f'.join('abcde'),
                                                         '\x1f'.join('fghij')],
                                           makeTicket=[True])
        self.item = blm.members.PurchaseItem(product=[self.product])

        self.ticket = blm.members.Ticket(purchaseitem=[self.item])

        self.commit()
        self.app = wsgi.app.test_client()

    def test_ticket(self, monkeypatch):
        calls = []
        def rendertemplate(template, **kw):
            calls.append((template, kw))
            return 'OK'

        monkeypatch.setattr(wsgi, 'render_template', rendertemplate)

        url = self.ticket.qrcode[0]
        response = self.app.get(url)
        assert calls[0][1]['ticket'] == self.ticket
        calls = []

        url = '/'.join(self.ticket.qrcode[0].split('/')[:-3])
        response = self.app.get(url)
        assert calls[0][1]['ticket'] == self.ticket
        calls = []

        url = '/'.join(self.ticket.qrcode[0].split('/')[:-4]) + '/random'
        response = self.app.get(url)
        assert calls[0][1]['ticket'] is None
        calls = []

        url = '/ticket/' + self.ticket.barcode[0]
        response = self.app.get(url)
        assert calls[0][1]['ticket'] == self.ticket
        calls = []

    def test_void(self):
        with self.app.session_transaction() as sess:
            sess['userid'] = self.user.id[0]

        assert self.ticket.voided == []

        url = self.ticket.qrcode[0]
        response = self.app.post(url, data=dict(void=1))
        self.commit() # Get ourselves a new context
        tkt, = blm.members.Ticket._query(id=self.ticket).run()

        assert len(tkt.voided) == 1

    def test_void_get(self):
        with self.app.session_transaction() as sess:
            sess['userid'] = self.user.id[0]

        assert self.ticket.voided == []

        url = self.ticket.qrcode[0]
        response = self.app.get(url, query_string="void=1")
        self.commit() # Get ourselves a new context
        tkt, = blm.members.Ticket._query(id=self.ticket).run()

        assert len(tkt.voided) == 1

    def test_void_no_user(self):
        assert self.ticket.voided == []

        url = self.ticket.qrcode[0]
        response = self.app.post(url, data=dict(void=1))
        self.commit() # Get ourselves a new context
        tkt, = blm.members.Ticket._query(id=self.ticket).run()

        # We can't void unless we are logged in
        assert len(tkt.voided) == 0

    def test_void_wrong_user(self):
        user = blm.accounting.User()

        with self.app.session_transaction() as sess:
            sess['userid'] = user.id[0]

        assert self.ticket.voided == []

        url = self.ticket.qrcode[0]
        response = self.app.post(url, data=dict(void=1))
        self.commit() # Get ourselves a new context
        tkt, = blm.members.Ticket._query(id=self.ticket).run()

        # We can't void if we're not a member of org
        assert len(tkt.voided) == 0

    def test_autovoid(self):
        with self.app.session_transaction() as sess:
            sess['userid'] = self.user.id[0]

        self.set_cookie('autovoid', 'true')

        assert self.ticket.voided == []

        url = self.ticket.qrcode[0]
        response = self.app.get(url)
        self.commit() # Get ourselves a new context
        tkt, = blm.members.Ticket._query(id=self.ticket).run()

        assert len(tkt.voided) == 1

    def test_no_autovoid(self):
        with self.app.session_transaction() as sess:
            sess['userid'] = self.user.id[0]

        self.set_cookie('autovoid', 'false')

        assert self.ticket.voided == []

        url = self.ticket.qrcode[0]
        response = self.app.get(url)
        self.commit() # Get ourselves a new context
        tkt, = blm.members.Ticket._query(id=self.ticket).run()

        assert len(tkt.voided) == 0


    def test_unvoid(self):
        with self.app.session_transaction() as sess:
            sess['userid'] = self.user.id[0]

        assert self.ticket.voided == []
        self.ticket(voided=[time.time()], voidedBy=[self.user])
        self.commit()
        tkt, = blm.members.Ticket._query(id=self.ticket).run()
        assert len(tkt.voided) == 1

        url = self.ticket.qrcode[0]
        response = self.app.post(url, data=dict(unvoid=1))
        self.commit() # Get ourselves a new context
        tkt, = blm.members.Ticket._query(id=self.ticket).run()

        assert len(tkt.voided) == 0

    def test_autovoid_unvoid(self):
        with self.app.session_transaction() as sess:
            sess['userid'] = self.user.id[0]

        self.set_cookie('autovoid', 'true')

        assert self.ticket.voided == []
        self.ticket(voided=[time.time()], voidedBy=[self.user])
        self.commit()
        tkt, = blm.members.Ticket._query(id=self.ticket).run()
        assert len(tkt.voided) == 1

        url = self.ticket.qrcode[0]
        response = self.app.post(url, data=dict(unvoid=1))
        self.commit() # Get ourselves a new context
        tkt, = blm.members.Ticket._query(id=self.ticket).run()

        assert len(tkt.voided) == 0
