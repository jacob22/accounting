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

import sys
if (sys.version_info >=(3, 0)):
    PYT3 = True
    import urllib.request
    import urllib.parse
else:
    PYT3 = False
    import urllib2
    import urlparse

import contextlib
import json
import os
import py
import subprocess
import time
import uuid

from . import support

here = os.path.dirname(__file__)


class Container(object):
    def __init__(self, **kw):
        self.__dict__.update(kw)


def do_purchase(products, emailaddress):
    params = {
        'data': [
            {'items': [{'product': product} for product in products],
             'buyerName': 'Kalle Anka',
             'buyerEmail': emailaddress}
        ]
    }

    if PYT3:
        req = urllib.request.Request(urllib.parse.urljoin(support.url, '/rest/purchase'),
                                  json.dumps(params).encode('ascii'),
                                     {'Content-Type': 'application/json'})
        data = json.load(urllib.request.urlopen(req))
    else:
        req = urllib2.Request(urlparse.urljoin(support.url, '/rest/purchase'),
                                  json.dumps(params),
                                  {'Content-Type': 'application/json'})
        data = json.load(urllib2.urlopen(req))

    return Container(id=data['purchase'],
                     invoice=data['invoiceUrl'],
                     buyerEmail=emailaddress)


def check_mail(client, mailssh, purchase, mailtype):
    client.run('sendmail -qf')
    message, = mailssh.find_and_delete_mail(None, 'TO', purchase.buyerEmail)
    msg, headers = mailssh.parse(message)
    assert headers['X-OE-MailType'] == [mailtype]
    assert purchase.invoice in msg
    return msg, headers


@contextlib.contextmanager
def check_mails(client, mailssh, purchase):
    check_mail(client, mailssh, purchase, 'order-confirmation')
    yield
    check_mail(client, mailssh, purchase, 'full-payment-confirmation')


def gen_pg(client, org, id_args=[1, 1]):
    cmd = 'python /root/accounting/members/paymentgen.py %s %s %s' % (
        org.id, id_args[0], id_args[1])
    id_args[0] += 1
    id_args[1] += 1000
    stdin, stdout, stderr = client.exec_command('PYTHONPATH=/root/accounting ' +
                                                cmd)
    return stdout.read()


def upload_pg(tmpdir, ssh, pgdata):
    pgfile = tmpdir.join('pgfile')
    pgfile.write(pgdata)

    dest = uuid.uuid4()
    with ssh(username='nordea') as client:
        sftp = client.open_sftp()
        sftp.put(str(pgfile), 'incoming/%s' % dest, confirm=False)


@py.test.mark.usefixtures('cluster', 'clean_db', 'bootstrapped', 'mailssh',
                          'ssh', 'org', 'emailaddress')
def test_full_plusgiro_payment(mailssh, ssh, org, emailaddress, tmpdir):
    purchase = do_purchase([org.product], emailaddress)
    with ssh() as client:
        with check_mails(client, mailssh, purchase):
            pgdata = gen_pg(client, org)
            upload_pg(tmpdir, ssh, pgdata)


@py.test.mark.usefixtures('cluster', 'clean_db', 'bootstrapped', 'mailssh',
                          'ssh', 'org', 'emailaddress')
def test_partial_plusgiro_payment(ssh, mailssh, org, emailaddress,
                                  tmpdir):
    purchase = do_purchase([org.product], emailaddress)

    with ssh() as client:
        with check_mails(client, mailssh, purchase):
            pgdata1 = gen_pg(client, org)
            pgdata2 = gen_pg(client, org)
            pgdata3 = gen_pg(client, org)
            # The sum is 66666 (öre). It is probably unique in the fake pgfile,
            # so we can simply replace it in order to make partial payments.
            if PYT3:
                partial_payment1 = pgdata1.replace(b'66666', b'22222')  # pay 222.22 SEK
                partial_payment2 = pgdata2.replace(b'66666', b'33333')  # pay 333.33 SEK
                final_payment = pgdata3.replace(b'66666', b'11111')  # final 111.11 SEK
            else:
                partial_payment1 = pgdata1.replace('66666', '22222')  # pay 222.22 SEK
                partial_payment2 = pgdata2.replace('66666', '33333')  # pay 333.33 SEK
                final_payment = pgdata3.replace('66666', '11111')  # final 111.11 SEK

            upload_pg(tmpdir, ssh, partial_payment1)
            msg, headers = check_mail(client, mailssh, purchase,
                                      'partial-payment-confirmation')
            assert '222,22' in msg  # amount paid
            assert '444,44' in msg  # amount remaining

            upload_pg(tmpdir, ssh, partial_payment2)
            msg, headers = check_mail(client, mailssh, purchase,
                                      'partial-payment-confirmation')
            assert '333,33' in msg  # amount paid
            assert '111,11' in msg  # amount remaining

            upload_pg(tmpdir, ssh, final_payment)


@py.test.mark.usefixtures('cluster', 'clean_db', 'bootstrapped', 'mailssh',
                          'nodes', 'ssh', 'org', 'emailaddress')
def test_swish_payment(nodes, ssh, mailssh, org, emailaddress):
    #py.test.skip('Skip swish tests until certificates work')
    purchase = do_purchase([org.product], emailaddress)
    with ssh() as client:
        with check_mails(client, mailssh, purchase):
            print(purchase.invoice)
            if PYT3:
                parsed = urllib.parse.urlparse(purchase.invoice)
                _, _, purchase, _ = parsed.path.split('/')
                path = '/providers/swish/charge/%s/%s' % (org.swish_provider, purchase)
                url = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, path,
                                       '', '', ''))
                data = {'phone': '1231181189'}
                req = urllib.request.Request(url, json.dumps(data).encode('ascii'),
                                      {'Content-Type': 'application/json'})
                response = json.load(urllib.request.urlopen(req))
            else:
                parsed = urlparse.urlparse(purchase.invoice)
                _, _, purchase, _ = parsed.path.split('/')
                path = '/providers/swish/charge/%s/%s' % (org.swish_provider, purchase)
                url = urlparse.urlunparse((parsed.scheme, parsed.netloc, path,
                                           '', '', ''))
                data = {'phone': '1231181189'}
                req = urllib2.Request(url, json.dumps(data),
                                      {'Content-Type': 'application/json'})
                response = json.load(urllib2.urlopen(req))
            print(response)
            assert response['status'] == 'CREATED'

            path = '/providers/swish/poll/%s/%s' % (org.swish_provider,
                                                    response['id'])
            if PYT3:
                url = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, path,
                                               '', '', ''))
            else:
                url = urlparse.urlunparse((parsed.scheme, parsed.netloc, path,
                                           '', '', ''))

            for _ in range(20):
                if PYT3:
                    req = urllib.request.Request(url)
                    response = json.load(urllib.request.urlopen(req))
                else:
                    req = urllib2.Request(url)
                    response = json.load(urllib2.urlopen(req))

                print(response)
                if response['status'] == 'PAID':
                    break
                time.sleep(1)
