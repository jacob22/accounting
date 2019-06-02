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

from suds.client import Client

import sys
if sys.version_info >= (3,0):
    PYT3 = True
    import email.utils
else:
    PYT3 = False
    import rfc822


from bson.objectid import ObjectId
from datetime import datetime
from flask import render_template, jsonify, make_response, redirect

from pytransact.contextbroker import ContextBroker
from pytransact.context import ReadonlyContext, maybe_with_context
from pytransact.commit import CommitContext, CallToi, CreateToi, wait_for_commit
from pytransact import runtime as ri

from accounting import config
import members

import blm.accounting, blm.members

log = config.getLogger('seqr')


class SeqrError(RuntimeError):

    def __init__(self, code, description):
        super(RuntimeError, self).__init__(code, description)
        self.code = code
        self.description = description


def call_method(method, *args):
    resp = method(*args)
    if resp.resultCode != 0:
        log.error(resp)
        raise SeqrError(resp.resultCode, resp.resultDescription)
    log.info(resp)
    return resp


@maybe_with_context()
def get_client_and_context(providerId, purchaseId=None):
    provider, = blm.accounting.SeqrProvider._query(id=providerId).run()
    # XXX Uncertain if this is the proper endpoint for live
    client = Client(provider.soapUrl[0])
    context = client.factory.create("ns0:clientContext")
    context.clientId = 'Open End AB Eutaxia Admin'
    context.clientRequestTimeout = 0
    context.initiatorPrincipalId.type = 'TERMINALID'
    context.initiatorPrincipalId.id = provider.principalId[0]
    context.password = provider.password[0]
    # Which one?
    #context.clientReference = 'Eutaxia Admin'
    context.clientReference = str(purchaseId or ObjectId())

    return client, context, 'SEQR-DEMO'


def _get_invoice(client, providerId, purchaseId, returnto=None):
    provider, = blm.accounting.SeqrProvider._query(id=providerId).run()
    purchase, = blm.members.BasePurchase._query(id=purchaseId).run()
    org = purchase.org[0]
    currency = provider.currency[0]

    invoice = client.factory.create("ns0:invoice")
    invoice.paymentMode = "IMMEDIATE_DEBIT"
    invoice.acknowledgmentMode = "NO_ACKNOWLEDGMENT"
    if returnto:
        invoice.backURL = returnto
    invoice.clientInvoiceId = purchase.ocr[0]

    if ri.getClientUser():
        invoice.cashierId = str(ri.getClientUser().id[0])
    #else:
    #    invoice.cashierId = 'John00232'
    invoice.footer = purchase.ocr[0]
    invoice.issueDate = datetime.utcfromtimestamp(purchase.date[0])
    invoice.title = org.name[0]
    invoice.totalAmount = client.factory.create('ns0:totalAmount')
    invoice.totalAmount.value = purchase.total[0]
    invoice.totalAmount.currency = currency
    rows = invoice.invoiceRows = client.factory.create('ns0:invoiceRows')

    for item in purchase.items:
        row = client.factory.create('ns0:paymentInvoiceRow')
        rows.invoiceRow.append(row)
        row.itemDescription = item.name[0]
        row.itemQuantity = item.quantity[0]
        if item.vatPercentage:
            row.itemTaxRate = item.vatPercentage[0]
        row.itemTotalAmount = client.factory.create('ns0:itemTotalAmount')
        row.itemTotalAmount.value = item.total[0]
        row.itemTotalAmount.currency = currency
        row.itemUnitPrice = client.factory.create('ns0:itemUnitPrice')
        row.itemUnitPrice.value = item.price[0]
        row.itemUnitPrice.currency = currency

    return invoice

def notification(database, providerId, purchaseId, invoiceRef):
    return ''


@maybe_with_context()
def invoice(providerId, purchaseId, returnto):
    client, context, seqr_protocol = get_client_and_context(
        providerId, purchaseId)
    invoice = _get_invoice(client, providerId, purchaseId, returnto)
    #invoice.notificationUrl = 'https://seqr-test.openend.se/seqrNotification/%s/%s' % (
    #    providerId, purchaseId)

    log.info(invoice)
    invoiceResponse = call_method(client.service.sendInvoice, context, invoice)

    purchase = blm.members.Purchase._query(id=purchaseId).run()[0]

    return make_response(render_template(
        'seqr.html',
        seqrQR=invoiceResponse.invoiceQRCode,
        seqrLink=seqr_protocol + invoiceResponse.invoiceQRCode[4:],
        providerId = providerId,
        purchaseId = purchaseId,
        invoiceRef = invoiceResponse.invoiceReference,
        invoiceUrl = purchase.invoiceUrl[0]
        ))


def poll(database, providerId, purchaseId, invoiceRef):
    client, context, seqr_protocol = get_client_and_context(
        providerId, purchaseId, database=database)
    response = call_method(client.service.getPaymentStatus, context, invoiceRef)

    if response.resultCode == 0 and response.status == 'PAID':
        with CommitContext(database) as ctx:
            purchase, = blm.members.BasePurchase._query(id=purchaseId).run()
            op = CreateToi('members.SeqrPayment', None, dict(
                paymentProvider=[providerId],
                matchedPurchase=[purchase],
                amount=[response.receipt.invoice.totalAmount.value],
                paymentDate=[datetime_to_epoch(response.receipt.paymentDate)],
                invoiceReference=[response.receipt.invoiceReference],
                ersReference=[response.ersReference],
                paymentReference=[response.receipt.paymentReference],
                payerTerminalId=[response.receipt.payerTerminalId],
                receiverName=[r for r in [response.receipt.receiverName] if r]
                ))
            interested = 'seqr-%s' % ObjectId()
            commit = ctx.runCommit([op], interested=interested)

        result, error = wait_for_commit(database, interested=interested)
        if error:
            raise error

        receiptDoc = client.factory.create('ns0:receiptDocument')
        receiptDoc.mimeType = 'text/plain'
        receiptDoc.receiptData = ''
        receiptDoc.receiptType = ''

        receipt_response = call_method(client.service.submitPaymentReceipt,
            context, response.ersReference, receiptDoc)

        paymentId = result[0]

        with CommitContext(database) as ctx:
            op = CallToi(paymentId, 'sendConfirmationEmail', [])
            interested = 'send-seqr-payment-confirmation-%s' % ObjectId()
            commit = ctx.runCommit([op], interested=interested)
        result, error = wait_for_commit(database, interested=interested)
        if error:
            raise error

    return jsonify({
        'resultCode' : response.resultCode,
        'status' : response.status
        })


@maybe_with_context()
def refund(paymentId):
    payment, = blm.members.SeqrPayment._query(id=paymentId).run()
    provider = payment.paymentProvider[0]
    purchase = payment.matchedPurchase[0]

    client, context, seqr_protocol = get_client_and_context(
        provider.id[0], purchase.id[0])

    log.info(context)

    invoice = _get_invoice(client, provider.id[0], purchase.id[0])
    log.info(invoice)

    resp = call_method(client.service.refundPayment,
                       context, payment.ersReference[0], invoice)
    return resp.ersReference


def cancel(database, providerId, purchaseId, invoiceRef):
    client, context, seqr_protocol = get_client_and_context(
        providerId, purchaseId, database=database)
    resp = call_method(client.service.cancelInvoice, context, invoiceRef)
    with ReadonlyContext(database) as ctx:
        purchase, = blm.members.Purchase._query(id=purchaseId).run()
        return redirect(purchase.invoiceUrl[0])


def mark_transaction_period(database, providerId, principalId, userId, password,
                            terminalId='openend_terminal'):
    client, context, seqr_protocol = get_client_and_context(
        providerId, database=database)

    context.initiatorPrincipalId.type = 'RESELLERUSER'
    context.initiatorPrincipalId.id = principalId
    context.initiatorPrincipalId.userId = userId
    context.password = password

    entry = client.factory.create("ns0:parameterMap")
    entry.parameter = client.factory.create("ns0:mapArray")
    entry.parameter.entry = client.factory.create("ns0:parameter")
    entry.parameter.entry.key = 'TERMINALID'
    entry.parameter.entry.value = terminalId

    resp = call_method(client.service.markTransactionPeriod, context, entry)

def datetime_to_epoch(dt):
    if PYT3:
        return email.utils.mktime_tz(dt.utctimetuple() + (0,))
    return rfc822.mktime_tz(dt.utctimetuple() + (0,))
