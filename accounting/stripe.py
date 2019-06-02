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

from bson.objectid import ObjectId
import decimal, os, hashlib, json, time
try:
    import httplib                      #py2
except ImportError:
    from http import client as httplib  #py3
from pytransact.context import ReadonlyContext
from pytransact.commit import CommitContext, wait_for_commit, CreateToi, CallBlm
import stripe, stripe.error
from accounting import config
from accounting.flask_utils import requires_login
import blm.accounting, blm.members

from flask import g, session, request, url_for, redirect, current_app, render_template
import flask

log = config.getLogger('stripe')

from flask_oauthlib.client import OAuth

stripe_api = flask.Blueprint('stripe_api', __name__)

oauth = OAuth()
stripe_oauth = oauth.remote_app('stripe', **dict(config.config.items('stripe')))

@stripe_api.route('/authorize/<objectid:org>', methods=['POST', 'GET'])
def authorize(org):
    session['stripe_accounting_info'] = (str(org),
                                         request.values.get('account'),
                                         request.values.get('series'))
    params = {}
    session.pop('stripe_oauth_token', None) # Clear old auth tokens
    rand = os.urandom(32)
    params['state'] = hashlib.sha256(current_app.secret_key + rand).hexdigest()
    params['scope'] = 'read_write'
    session['oauth_random'] = rand

    with ReadonlyContext(g.database, g.user) as ctx:
        org, = blm.accounting.Org._query(id=org).run()
        params['stripe_user[business_name]'] = org.name[0]
        params['stripe_user[currency]'] = org.currency[0]
        if org.email:
            params['stripe_user[email]'] = org.email[0]
        if org.url:
            params['stripe_user[url]'] = org.url[0]

    authorized_url = url_for('.authorized_handler', _external=True)
    return stripe_oauth.authorize(callback=authorized_url, **params)


@stripe_api.route('/charge/<objectid:provider>/<objectid:purchase>', methods=['GET', 'POST'])
def charge(provider, purchase):
    card_token = request.values['stripeToken']
    with ReadonlyContext(g.database) as ctx:
        provider, = blm.accounting.StripeProvider._query(id=provider).run()
        purchase, = blm.members.BasePurchase._query(id=purchase).run()
        amount = int((purchase.total[0] * 100).quantize(1))
        currency = provider.currency[0]
        access_token = provider.access_token[0]
        invoiceUrl = purchase.invoiceUrl[0]

        try:
            charge = stripe.Charge.create(
                amount=amount,
                currency=currency,
                card=card_token,
                description=invoiceUrl,
                api_key=access_token)
        except stripe.error.StripeError as e:
            return flask.redirect(invoiceUrl + '?status=fail')

    if charge.paid:
        with CommitContext(g.database) as ctx:
            op = CreateToi('members.StripePayment', None, dict(
                paymentProvider=[provider],
                matchedPurchase=[purchase],
                amount=[decimal.Decimal(charge.amount) / 100],
                paymentDate=[charge.created],
                transaction_date=[time.strftime('%Y-%m-%d',
                                                time.localtime(charge.created))], # xxx
                charge_id=[charge.id],
                currency=[charge.currency.upper()],
                json_data=[json.dumps(charge)]
            ))
            interested = 'stripe-%s' % ObjectId()
            commit = ctx.runCommit([op], interested=interested)

        result, error = wait_for_commit(g.database, interested=interested)
        if error:
            raise error

    return flask.redirect(invoiceUrl)


@stripe_api.route('/webhook', methods=['GET', 'POST'])
def webhook():
    data = request.get_json()
    log.info('WEBHOOK: %r', data)
    if not 'user_id' in data:
        return '' # Nothing we know what to do with
    with ReadonlyContext(g.database) as ctx:
        provider = blm.accounting.StripeProvider._query(stripe_id = data['user_id']).run()
        if not provider:
            return ''
        org_ug = provider[0].org[0].ug[0]

    interested = 'stripe-%s-%s-%s' % (data['type'], data['id'], ObjectId())
    with CommitContext(g.database, org_ug) as ctx:  # Use organisations permissions
        op = []
        if data['type'] == 'invoice.created':
            op.append(CallBlm('members', 'handleStripeInvoice', [[data], provider]))
        elif data['type'] == 'charge.succeeded':
            op.append(CallBlm('members', 'handleStripeCharge', [[data], provider]))
        elif data['type'] == 'invoice.payment_succeeded':
            pass
        ctx.runCommit(op, interested)
    _, error = wait_for_commit(g.database, interested)
    if error:
        raise error

    return ''


@stripe_oauth.tokengetter
def get_stripe_token(token=None):
    return None  # We never call stripe functions that need the token


@stripe_api.route('')
def authorized_handler():
    baseurl = config.config.get('accounting', 'baseurl')

    if 'oauth_random' in session and \
           request.args['state'] != hashlib.sha256(
        current_app.secret_key +
        session.pop('oauth_random', '')).hexdigest():
        log.info('Connect authorization failed: bad state. %s', request.args)

        return redirect(baseurl)

    resp = stripe_oauth.authorized_response()
    if resp is None:
        # XXX Hack to minimze changes
        log.info('Connect authorization failed: %s', request.args)
        return redirect(baseurl)

    access_token = resp['access_token']
    publishable_key = resp['stripe_publishable_key']
    refresh_token = resp['refresh_token']

    account = stripe.Account.retrieve(api_key=access_token)
    print(account)

    with CommitContext(g.database, g.user) as ctx:
        org, accno, series = session.pop('stripe_accounting_info')
        display_name = account['display_name']

        attrData = {
            'org': [org],
            'account': [accno] if accno else [],
            'series': [series] if series else [],
            'access_token': [access_token],
            'display_name': [display_name] if display_name else [],
            'stripe_id': [account['id']],
            'stripe_email': [account['email']],
            'stripe_publishable_key': [publishable_key],
            'refresh_token': [refresh_token],
        }

        op = CreateToi('accounting.StripeProvider', None, attrData)
        interested = 'stripe-%s' % ObjectId()
        ctx.runCommit([op], interested=interested)

    result, error = wait_for_commit(g.database, interested)
    if error:
        return render_template('error.html', error=error)

    return redirect(baseurl)

