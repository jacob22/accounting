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

from bson.objectid import ObjectId
import decimal
import flask
try:
    import httplib                  #py2
except ImportError:
    import http.client as httplib   #py3
    
import payson
try:
    import urlparse                     #py2
    from urlparse import urljoin as urljoin
    import urllib
    from urllib import urlencode as urlencode
except ImportError:
    from urllib.parse import urlparse   #py3
    from urllib.parse import urljoin as urljoin
    from urllib.parse import urlencode as urlencode
from accounting import config
import members

from pytransact.context import ReadonlyContext, maybe_with_context
from pytransact.commit import CommitContext, CallToi, CreateToi, wait_for_commit

import blm.accounting, blm.members

log = config.getLogger('payson')


class PaysonError(RuntimeError):

    pass



def pay(database, providerId, purchaseId, returnto):
    with ReadonlyContext(database) as ctx:
        provider, = blm.accounting.PaysonProvider._query(id=providerId).run()
        org = provider.org[0]
        purchase, = blm.members.BasePurchase._query(id=purchaseId).run()

        api = payson.PaysonApi(provider.apiUserId[0], provider.apiPassword[0])
        receiver = payson.Receiver(email=provider.receiverEmail[0],
                                   amount=purchase.remainingAmount[0])
        memo = (u'Betalning till %s' % org.name[0])[:128]

        ipnBase = (config.config.get('payson', 'ipn_notification_baseurl') or
                    config.config.get('accounting', 'baseurl'))

        ipnNotificationUrl = urljoin(ipnBase, 'paysonipn')

        payment_response = api.pay(
            returnUrl=returnto,
            cancelUrl=returnto,
            ipnNotificationUrl=ipnNotificationUrl,
            memo=memo,
            senderEmail=purchase.buyerEmail[0],
            senderFirstName=purchase.buyerName[0].split()[0],
            senderLastName=purchase.buyerName[0].split()[-1],
            trackingId=str(purchaseId),
            custom=str(providerId),
            receiverList=[receiver]
            )

        if payment_response.success:
            return flask.redirect(payment_response.forward_pay_url)

    return ''

def payson_ipn(request, database):
    log.info('IPN request')

    payData = payson.PaymentDetails(request.values)

    with ReadonlyContext(database):
        provider, = blm.accounting.PaysonProvider._query(id=payData.custom).run()
        api = payson.PaysonApi(provider.apiUserId[0], provider.apiPassword[0])

    requestdata = urlencode(request.form)

    log.info('Request data: %r', requestdata)

    if api.validate(requestdata):
        log.info('IPN Verified')
        update_payment(payData.token, database, provider=provider)
    else:
        log.info('IPN NOT Verified')

    return '', httplib.NO_CONTENT

def update_payment(token, database, purchase=None, provider=None):
    log.info('Payson update')

    with ReadonlyContext(database):
        if blm.members.PaysonPayment._query(token=token).run():
            log.info('Payment %s already registered, aborting.', token)
            return
        if not provider:
            purchase, = blm.members.Purchase._query(id=purchase, _attrList=['org']).run()
            provider = blm.accounting.PaysonProvider._query(org=purchase.org).run()[0]

        api = payson.PaysonApi(provider.apiUserId[0], provider.apiPassword[0])

    payData = api.payment_details(token)

    if payData.status == 'COMPLETED':
        with CommitContext(database) as ctx:
            purchase, = blm.members.Purchase._query(id=payData.trackingId).run()
            op = CreateToi('members.PaysonPayment', None, dict(
                    paymentProvider=[provider],
                    matchedPurchase=[purchase],
                    amount=[payData.receiverList[0].amount],
                    purchaseId=[payData.purchaseId],
                    senderEmail=[payData.senderEmail],
                    token=[payData.token],
                    receiverFee=[payData.receiverFee],
                    receiverEmail=[payData.receiverList[0].email],
                    type=[payData.type]))
            interested = 'payson-%s' % ObjectId()
            commit = ctx.runCommit([op], interested=interested)

        result, error = wait_for_commit(database, interested=interested)
        if error:
            raise error
        paymentId = result[0]

        with CommitContext(database) as ctx:
            op = CallToi(paymentId, 'sendConfirmationEmail', [])
            interested = 'send-payson-payment-confirmation-%s' % ObjectId()
            commit = ctx.runCommit([op], interested=interested)
        result, error = wait_for_commit(database, interested=interested)
        if error:
            raise error


@maybe_with_context()
def refund(payment):
    provider = payment.paymentProvider[0]
    api = payson.PaysonApi(provider.apiUserId[0], provider.apiPassword[0])
    if not api.payment_update(payment.token[0], 'REFUND'):
        raise PaysonError()
    return True
