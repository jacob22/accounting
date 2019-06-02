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

from email.header import Header
from email.mime.text import MIMEText
from email.utils import getaddresses, formataddr
import os
import re
import dkim
from . import smtppipe
import accounting.config
log = accounting.config.getLogger('mail')
try:
    unicode                     #py2
    py23txt = lambda t, c = 'us-ascii': t
    py23txtc = lambda t, c = 'us-ascii': t.encode(c)
    py23txtu = lambda t, c = 'us-ascii': unicode(t, c)
except NameError:               #py3
    py23txt = lambda t, c = 'us-ascii': t.encode(c)
    py23txtc = lambda t, c = 'us-ascii': t
    py23txtu = lambda t, c = 'us-ascii': t
dkim_key = None

def makemail(body, bcc='', envfrom='<>', **headers):
    smtp_domain = accounting.config.config.get('accounting', 'smtp_domain')
    message = MIMEText(body, _charset='utf-8')

    if '_from' in headers:
        headers['from'] = headers.pop('_from')
    for header, value in headers.items():
        header = header.capitalize()
        if header in ('To', 'Cc', 'Bcc', 'Resent-to', 'Resent-Cc', 'From', 'Sender', 'Reply-to'):
            message[header] = makeAddressHeader(header, getaddresses([value]))
        else:
            message[header] = Header(value, header_name=header)

    if bcc:
        message['Bcc'] = ''
    bcc = makeAddressHeader(header, getaddresses([bcc]))
    tos = message.get_all('to', [])
    ccs = message.get_all('cc', [])
    resent_tos = message.get_all('resent-to', [])
    resent_ccs = message.get_all('resent-cc', [])
    all_recipients = getaddresses(map(str, tos + ccs + resent_tos + resent_ccs + [bcc]))
    all_recipients = [addr[1] for addr in all_recipients if addr[1]]

    fromaddr = getaddresses(map(str, message.get_all('sender', []) +
                                message.get_all('from', []) + ['<>']))[0][1]
    if not fromaddr:
        message['From'] = 'noreply@{}'.format(smtp_domain)

    msgtxt = message.as_string()

    return envfrom, all_recipients, msgtxt


def sendmail(fromaddr, all_recipients, data, identity=None):
    global dkim_key

    recipients_filter = accounting.config.config.get('accounting', 'smtp_to_filter')
    filtered_recipients = []
    for recipient in all_recipients:
        if not recipients_filter or re.match(recipients_filter, recipient) is None:
            log.warn('Not sending to %s', recipient)
        else:
            filtered_recipients.append(recipient)

    if not filtered_recipients:
        return

    # DKIM sign
    if dkim_key is None:
        with open(
            os.path.join(
            os.path.dirname(__file__),
            accounting.config.config.get('accounting', 'dkim_privkey')), 'rb') as f:
            dkim_key = f.read()

    smtp_domain = accounting.config.config.get('accounting', 'smtp_domain')

    if identity is None:
        identity = ''

    dkim_sig = dkim.sign(
        py23txt(data), py23txt(accounting.config.config.get('accounting', 'dkim_selector')),
        py23txt(accounting.config.config.get('accounting', 'dkim_domain')), dkim_key,
        identity=py23txt('{}@{}'.format(identity, smtp_domain)),
        canonicalize=(b'relaxed', b'simple'))
    dkim_sig = b'\n'.join(dkim_sig.split(b'\r\n')) # fix newlines

    if fromaddr and fromaddr != '<>' and '@' not in fromaddr:
        fromaddr = '{}@{}'.format(fromaddr, smtp_domain)

    s = smtppipe.SMTP(accounting.config.config.get('accounting', 'smtp_command'))
    s.sendmail(fromaddr, filtered_recipients, dkim_sig + py23txt(data))
    s.quit()


def makeAddressHeader(headerName, addrs):
    to = Header(charset='iso-8859-1', header_name=headerName)
    lastaddr = None

    for (name, addr) in addrs:
        if lastaddr:
            to.append(py23txtc('<{}>,'.format(lastaddr), 'us-ascii'), 'us-ascii') # No encoding of address
        try:
            name = py23txtc(name, 'us-ascii')
        except UnicodeError:
            pass
        else:
            # It's ascii, so it won't get encoded. We need to escape specials.
            name = py23txtu(formataddr((name, ''))[:-3], 'us-ascii')

        # Empty name string cannot be added because header.append adds
        # another space, which means that there will be two spaces
        # between the header and the address.
        if name:
            to.append(name) # Default encoding

        lastaddr = addr

    if lastaddr:
        to.append(py23txtc('<{}>'.format(lastaddr), 'us-ascii'), 'us-ascii') # No encoding of address

    # Headers may break when flattening if the header is already
    # folded, so unfold the header, and let flattening deal with it.
    return str(to).replace('\n', '')
