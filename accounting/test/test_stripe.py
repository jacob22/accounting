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

import decimal
import flask
from pytransact.testsupport import BLMTests
import stripe
import accounting.stripe
from accounting import config, flask_utils
import members

import blm.accounting, blm.members


class TestStripe(BLMTests):

    def setup_method(self, method):
        super(TestStripe, self).setup_method(method)
        self.org = blm.accounting.Org(subscriptionLevel=['subscriber'], name=['The Org'])
        self.provider = blm.accounting.StripeProvider(
            org=self.org,
            access_token=['access-token'],
            currency=['EUR'],
            stripe_publishable_key=['pubkey']
        )
        self.product = blm.members.Product(org=[self.org], name=['prod'],
                                           accountingRules={'1000': '10.01'})
        self.item = blm.members.PurchaseItem(product=[self.product],
                                             quantity=[2])
        self.purchase = blm.members.Purchase(
            items=[self.item],
            buyerEmail=['bar@text'],
            buyerName=['Bar von Jobbigt Namn'],
            date=[0])
        self.commit()

        self.app = flask.Flask(__name__, template_folder=config.template_dir)
        flask_utils.add_converters(self.app)
        self.app.register_blueprint(accounting.stripe.stripe_api, url_prefix='/foo')

        @self.app.before_request
        def set_db():
            flask.g.database = self.database

    def test_charge_success(self, monkeypatch):
        @staticmethod
        def create(**kw):
            assert kw['card'] == 'stripeToken'
            assert kw['description'] == self.purchase.invoiceUrl[0]
            charge = stripe.Charge()
            charge.update(dict(
                id='stripe_id',
                created=1,
                paid=True,
                **kw
            ))
            return charge
        monkeypatch.setattr(stripe.Charge, 'create', create)

        with self.app.test_client() as client:
            resp = client.post('/foo/charge/%s/%s' %
                               (self.provider.id[0], self.purchase.id[0]),
                               data=dict(stripeToken='stripeToken'))

            assert resp.status_code == 302
            assert resp.headers['Location'] == self.purchase.invoiceUrl[0]

            payment, = blm.members.StripePayment._query(charge_id='stripe_id').run()
            assert payment.paymentProvider == [self.provider]
            assert payment.currency == ['EUR']
            assert payment.amount == [decimal.Decimal('20.02')]

    def test_charge_failure(self, monkeypatch):
        @staticmethod
        def create(**kw):
            raise stripe.error.CardError(u'Your card was declined.',
                                         None,
                                         u'card_declined')

        monkeypatch.setattr(stripe.Charge, 'create', create)

        with self.app.test_client() as client:
            resp = client.post('/foo/charge/%s/%s' %
                               (self.provider.id[0], self.purchase.id[0]),
                               data=dict(stripeToken='stripeToken'))

            assert resp.status_code == 302
            assert resp.headers['Location'] == self.purchase.invoiceUrl[0] + '?status=fail'
            assert not blm.members.StripePayment._query().run()
