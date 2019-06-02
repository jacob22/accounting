# -*- coding: utf-8 -*-
# Swish integration

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
if (sys.version_info >=(3, 0)):
    PYT3 = True
else:
    PYT3 = False

import decimal
import flask
import os
import re
import tempfile
import time

import OpenSSL.crypto
import dateutil.parser
from bson.objectid import ObjectId

if PYT3:
    import json
    from io import StringIO
    from http import client as httplib
    from urllib.request import Request
    from urllib import request as urllib2
else:
    import json
    from StringIO import StringIO
    import httplib
    import urllib2

import pytransact.commit
import pytransact.context
import accounting.config
import blm.accounting



log = accounting.config.getLogger('swish')

swish_api = flask.Blueprint('swish_api', __name__)


def itercerts(chain):
    try:
        chain.read
    except AttributeError:
        f = StringIO(chain)
    else:
        f = chain

    cert = StringIO()
    for line in f:
        if line == '-----BEGIN CERTIFICATE-----\n':
            cert = StringIO()

        cert.write(line)

        if line == '-----END CERTIFICATE-----\n':
            yield cert.getvalue()


def find_root_cert(cert):
    for pem in itercerts(cert):
        cert = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, pem)
        issuer = dict(cert.get_issuer().get_components())
        if PYT3:
            # Convert from byte to string
            issuer = { k.decode() : v.decode() for (k,v) in issuer.items()}
        if (issuer['O'] == 'Getswish AB' and
            issuer['OU'] == 'Swish Member CA' and
            issuer['CN'] == 'Swish Root CA v1'):
            return 'live', pem
        if (issuer['O'] == 'Getswish AB' and
            issuer['OU'] == 'Swish Member CA' and
            issuer['CN'] == 'Swish Root CA v2 Test'):
            return 'test', pem
    raise ValueError('Bad certificate', issuer)


class HTTPSClientAuthHandler(urllib2.HTTPSHandler):

    def __init__(self, cert, key):
        urllib2.HTTPSHandler.__init__(self)
        self.key = key
        self.cert = cert

    def https_open(self, req):
        # Rather than pass in a reference to a connection class, we pass in
        # a reference to a function which, for all intents and purposes,
        # will behave as a constructor
        return self.do_open(self.getConnection, req)

    def getConnection(self, host, timeout=300):
        return httplib.HTTPSConnection(host, key_file=self.key,
                                       cert_file=self.cert)


class Client(object):

    def __init__(self, merchant, cert, pkey, test=False):
        self.merchant = merchant
        self.cert_data = cert
        self.pkey_data = pkey
        self.test = test

    def __enter__(self):
        self.cert_file = tempfile.NamedTemporaryFile()
        self.pkey_file = tempfile.NamedTemporaryFile()
        if PYT3:
            self.cert_file.write(self.cert_data.encode())
        else:
            self.cert_file.write(self.cert_data)
        self.cert_file.flush()
        if PYT3:
            self.pkey_file.write(self.pkey_data.encode())
        else:
            self.pkey_file.write(self.pkey_data)
        self.pkey_file.flush()
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self.cert_file.close()
        self.pkey_file.close()

    @classmethod
    def from_toi(cls, toi):
        return cls(toi.swish_id[0], toi.cert[0], toi.pkey[0], toi.is_test[0])

    @property
    def cert(self):
        return self.cert_file.name, self.pkey_file.name

    @property
    def callback_root(self):
        try:
            baseurl = os.environ['FAKE_HTTPS_ROOT']
        except KeyError:
            baseurl = accounting.config.config.get('accounting', 'baseurl')
        return baseurl + 'providers/swish/webhook/'

    @property
    def url(self):
        if self.test:
            return 'https://mss.cpc.getswish.net/swish-cpcapi/api/v1/'
        else:
            return 'https://cpc.getswish.net/swish-cpcapi/api/v1/'

    def _get_url(self, endpoint):
        if endpoint.startswith(self.url):
            return endpoint
        return self.url + endpoint

    def get(self, endpoint):
        opener = urllib2.build_opener(HTTPSClientAuthHandler(*self.cert))
        url = self._get_url(endpoint)
        request = urllib2.Request(url)
        return opener.open(request)

    def post(self, endpoint, payload):
        opener = urllib2.build_opener(HTTPSClientAuthHandler(*self.cert))
        data = json.dumps(payload)
        url = self._get_url(endpoint)
        log.info('Posting: %s, %s', url, data)
        if PYT3:
            request = Request(url, data)
        else:
            request = urllib2.Request(url, data)
        request.add_header('Content-Type', 'application/json')
        if PYT3:
            request.data = request.data.encode()
        return opener.open(request)

    def create_payment(self, provider, purchase, **kw):
        callback = self.callback_root + 'charge/%s/%s' % (provider, purchase)
        kw.setdefault('callbackUrl', callback)
        kw.setdefault('payeeAlias', self.merchant)
        try:
            response = self.post('paymentrequests', payload=kw)
        except urllib2.HTTPError as exc:
            data = json.load(exc.fp)
            return Payment.from_error(data)
        return Payment.from_location(response.headers['Location'])

    def retrieve(self, refid):
        response = self.get('paymentrequests/%s' % refid)
        return Payment.from_json(response)

    def refund(self, id, **kw):
        callback = self.callback_root + 'refund/%s' % id
        kw.setdefault('callbackUrl', callback)
        kw.setdefault('payerAlias', self.merchant)
        try:
            response = self.post('refunds', payload=kw)
        except urllib2.HTTPError as exc:
            print(json.load(exc.fp))
            raise

        location = response.headers['Location']
        # xxx we need an asynchronous api for refunds...
        for x in range(20):
            response = self.get(location)
            payment = Payment.from_json(response)
            if payment.status == 'PAID':
                return payment
            time.sleep(1)

    def request_callback(self, payment):
        return self.get(payment.location)


class Payment(object):

    def __init__(self, id=None, status='CREATED', currency='SEK',
                 payerAlias=None, paymentReference=None, amount=None,
                 datePaid=None, **kw):
        self.id = id
        self.status = status
        self.currency = currency
        self.payerAlias = payerAlias
        self.paymentReference = paymentReference

        try:
            self.amount = decimal.Decimal(amount)
        except TypeError:
            self.amount = None

        try:
            self.datePaid = int(dateutil.parser.parse(datePaid).strftime('%s'))
        except (AttributeError, TypeError):
            self.datePaid = None

        if self.status == 'ERROR':
            self.errors = [{'errorCode': kw['errorCode'],
                            'errorMessage': kw['errorMessage']}]
        else:
            self.errors = None

    @property
    def http_result(self):
        if self.errors:
            return json.dumps(self.errors), 422
        else:
            data = {'id': self.id, 'status': self.status}
            return json.dumps(data), 200

    @classmethod
    def from_location(cls, location):
        obj = cls(location.split('/')[-1])
        obj.location = location
        return obj

    @classmethod
    def from_error(cls, errors):
        obj = cls()
        obj.errors = errors
        obj.error = errors[0]['errorCode']
        obj.errorMessage = errors[0]['errorMessage']
        return obj

    @classmethod
    def from_json(cls, stream):
        return cls.from_dict(json.load(stream))

    @classmethod
    def from_dict(cls, data):
        log.debug('Payment from data: %s', data)
        return cls(**data)


def _filter_message(message):
    message = re.sub(u'[^a-zA-z0-9åäöÅÄÖ:;.,\\?!\\(\\)]', ' ', message)
    message = re.sub(u'[ ]+', ' ', message)
    return message[:50]


@swish_api.route('/charge/<objectid:provider>/<objectid:purchase>',
                 methods=['GET', 'POST'])
def charge(provider, purchase):
    data = flask.request.get_json()
    phone = data['phone']
    with pytransact.context.ReadonlyContext(flask.g.database):
        provider, = blm.accounting.SwishProvider._query(id=provider).run()
        purchase, = blm.members.BasePurchase._query(id=purchase).run()
        amount = purchase.total[0]
        currency = provider.currency[0]
        swish_id = provider.swish_id[0]
        cert = provider.cert[0]
        pkey = provider.pkey[0]
        is_test = provider.is_test[0]

        with Client(swish_id, cert, pkey, test=is_test) as client:

            message = provider.org[0].name[0]
            if is_test:
                message = data.get('code', message)

            message = _filter_message(message)

            payment = client.create_payment(
                provider=provider.id[0],
                purchase=purchase.id[0],
                payeePaymentReference=purchase.ocr[0],
                payerAlias=phone,
                amount=str(amount.quantize(decimal.Decimal('1.00'))),
                currency=currency,
                message=message,
            )

            return payment.http_result


@swish_api.route('/poll/<objectid:provider>/<refid>', methods=['GET', 'POST'])
def poll(provider, refid):
    with pytransact.context.ReadonlyContext(flask.g.database):
        q = blm.accounting.SwishProvider._query(id=provider)
        q.attrList = ['swish_id', 'cert', 'pkey']
        provider, = q.run()
        swish_id = provider.swish_id[0]
        cert = provider.cert[0]
        pkey = provider.pkey[0]
        is_test = provider.is_test[0]
        with Client(swish_id, cert, pkey, test=is_test) as client:
            payment = client.retrieve(refid)
            result = payment.http_result

    return result


@swish_api.route('/webhook/refund/<objectid:payment>', methods=['GET', 'POST'])
def webhook_refund(payment):
    data = flask.request.get_json()
    log.info('WEBHOOK REFUND: %s', data)
    return ''


@swish_api.route('/webhook/charge/<objectid:provider>/<objectid:purchase>',
                 methods=['GET', 'POST'])
def webhook_charge(provider, purchase):
    data = flask.request.get_json()
    log.info('WEBHOOK CHARGE: %s', data)

    if data['status'] != 'PAID':
        return ''

    paymentReference = data['paymentReference']

    interested = 'swish-%s-%s' % (paymentReference, ObjectId())
    with pytransact.commit.CommitContext(flask.g.database) as ctx:
        provider = blm.accounting.SwishProvider._query(id=provider).run()
        purchase = blm.members.BasePurchase._query(id=purchase).run()

        if not provider + purchase:
            return ''
        op = pytransact.commit.CallBlm('members', 'handleSwishPayment',
                                       [provider, purchase, [data]])
        ctx.runCommit([op], interested)

    result, error = pytransact.commit.wait_for_commit(flask.g.database,
                                                      interested)
    if error:
        raise error

    paymentId = result[0][0]
    interested = 'send-swish-payment-confirmation-%s' % ObjectId()
    with pytransact.commit.CommitContext(flask.g.database) as ctx:
        op = pytransact.commit.CallToi(paymentId, 'sendConfirmationEmail', [])
        commit = ctx.runCommit([op], interested=interested)

    result, error = pytransact.commit.wait_for_commit(flask.g.database,
                                                      interested=interested)
    if error:
        raise error

    return ''
