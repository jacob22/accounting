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

import os
import base64
import datetime
import time
from pytransact.object.model import TO
from bson.objectid import ObjectId, InvalidId
from accounting import config
import serial
import hmac, hashlib
import binascii

import sys
if sys.version_info < (3,0):
    PYT3 = False                        # py2
    py3chr = lambda x: x
    py3txt = lambda x: x.encode('hex')
else:                                   # py3
    PYT3 = True
    import codecs
    py3chr = lambda x: chr(x)
    py3txt = lambda x: x
    #unicode = str


def findToi(s):
    try:
        a = decode_toid20(s)
    except ValueError:
        pass
    except TypeError:  # For Python2
        pass
    else:
        try:
            oid = ObjectId(a)
        except InvalidId:
            pass
        else:
            try:
                toi, = TO._query(id=oid).run()
            except ValueError:
                pass
            else:
                return toi.id[0]
    return


def encode_toid20(toi):
    toid = str(toi.id[0])
    toid20 = base64.b32encode(base64.b16decode(toid, casefold=True)).strip(b'=')
    if PYT3:
        return toid20.decode()
    return toid20


def decode_toid20(toid20):
    if PYT3:
        if not toid20:
            raise ValueError

        toidb32 = toid20 + (8 - (len(toid20) % 8)) * '='
        toidb32 = toidb32.upper()
        try:
            toid = base64.b32decode(toidb32)
        except ValueError:
            raise ValueError
        except binascii.Error:
            raise ValueError

        return codecs.encode(toid, 'hex_codec').decode('ascii')
    else:
        toidb32 = toid20 + (len(toid20) % 8) * '='
        toid = base64.b32decode(toidb32)
        return toid.encode('hex')


def bg_transferdate(si):
    datestr = 'GENAST'
    try:
        transferdate = datetime.datetime.strptime(si.transferDate[0], '%Y-%m-%d').date()
    except IndexError:
        # No transferDate set, just transfer ASAP.
        datestr = 'GENAST'
    else:
        # check weekday or weekend, go backward to earlier weekday
        while transferdate.isoweekday() > 5:
                transferdate -= datetime.timedelta(days=1)
        if datetime.date.fromtimestamp(time.time()) < transferdate:
            # new transferdate in the future
            datestr = transferdate.strftime('%y%m%d')
        else:
            # transferDate is today or in the past
            datestr = 'GENAST'
    return datestr


def gen_opening_record(bankgiroProvider):
    opening_record = u'11{0!s:0>10}{1!s:>6}LEVERANTORSBETALNINGAR{2!s:40}'.format(
        bankgiroProvider.bgnum[0],
        time.strftime('%y%m%d', time.localtime(time.time())),
        ''
    )
    return opening_record


def gen_fixed_information_record(information_text=None):
    if information_text is None:
        information_text = 'VID SIGILLFEL KONTAKTA 0708562650.'
    fixed_info_record = u'12{0!s:50}{1!s:6}{2!s:22}'.format(
        information_text[:50],
        (datetime.date.today() + datetime.timedelta(days=5)).strftime('%y%m%d'),
        ''
    )
    assert len(fixed_info_record) == 80
    return fixed_info_record


def gen_payment_record(supplierInvoice):
    payment_record = u'14{0!s:0>10}{1!s:<25}{2!s:0>12}{3!s:>6}{4!s: <5}{5!s: >20}'.format(
        supplierInvoice.transferAddress[0],
        supplierInvoice.invoiceIdentifier[0][:25],
        int(supplierInvoice.amount[0]*100),
        bg_transferdate(supplierInvoice),
        '',
        encode_toid20(supplierInvoice)
    )
    return payment_record


def gen_information_record(supplierInvoice):
    message = supplierInvoice.invoiceIdentifier[0]
    lines = []
    f = 50  # Chars per record
    n = min(len(message) // f + 1, 90)  # Records needed for full message, limit to 90.
    for i in range(n):
        m_slice = message[i*f:i*f+f]  # next f chars.
        assert 1 <= len(m_slice) <= 50
        information_record = u'25{0!s:0>10}{1!s:<50}{2!s:18}'.format(
            supplierInvoice.transferAddress[0],
            m_slice,
            ''
        )
        lines.append(information_record)
    return lines


def gen_payment_record_plusgiro(supplierInvoice):
    payment_record_plusgiro = u'54{0!s:0>10}{1!s:25}{2!s:0>12}{3!s:6}{4!s:5}{5!s:20}'.format(
        supplierInvoice.transferAddress[0],
        supplierInvoice.invoiceIdentifier[0][:25],
        int(supplierInvoice.amount[0]*100),
        bg_transferdate(supplierInvoice),
        '',
        encode_toid20(supplierInvoice)
    )
    return payment_record_plusgiro


def gen_information_record_plusgiro(supplierInvoice):
    lines = []
    message = supplierInvoice.invoiceIdentifier[0]
    f = 35  # Chars per record
    n = min(len(message) // f + 1, 9)  # Records needed for full message, limit to 9.
    for i in range(n):
        m_slice = message[i*f:i*f+f]  # next f chars.
        information_record_plusgiro = u'65{0!s:0>10}{1!s:<35}{2!s: <33}'.format(
            supplierInvoice.transferAddress[0],
            m_slice,
            ''
        )
        lines.append(information_record_plusgiro)
    return lines


def gen_account_number_record(supplierInvoice):
    record = u'40{0!s:4}{1!s:0>6}{2!s:0>4}{3!s:0>12}{4!s:>12}{5!s:1}{6!s: <39}'.format(
        '0000',
        supplierInvoice.transferAddress[0],
        supplierInvoice.bankclearing[0][:4],
        supplierInvoice.bankaccount[0],
        supplierInvoice.invoiceIdentifier[0][:12],
        ' ',  # Salary token
        ''
    )
    return record


def gen_total_amount_record(bankgiroProvider, len_supInvList, totamount, sign):
    total_amount_record = u'29{0!s:0>10}{1!s:0>8}{2!s:0>12}{3}{4!s:47}'.format(
        bankgiroProvider.bgnum[0],
        len_supInvList,
        totamount,
        sign,
        ''
    )
    return total_amount_record


def transferOrderBankgiroRecords(bankgiroProvider, supInvList):
    # Generate a payment order file to be sent to Bankgirot
    lines = []
    totamount = 0
    lines.append(gen_opening_record(bankgiroProvider))
    # lines.append(gen_fixed_information_record())
    for si in supInvList:
        if si.transferMethod[0] == 'bgnum':
            lines.append(gen_payment_record(si))
            if len(si.invoiceIdentifier[0]) > 25:
                lines += gen_information_record(si)
        if si.transferMethod[0] == 'pgnum':
            lines.append(gen_payment_record_plusgiro(si))
            if len(si.invoiceIdentifier[0]) > 25:
                lines += gen_information_record_plusgiro(si)
        if si.transferMethod[0] == 'bankaccount':
            lines.append(gen_account_number_record(si))
            lines.append(gen_payment_record(si))
            if len(si.invoiceIdentifier[0]) > 25:
                lines += gen_information_record(si)
        totamount += int(si.amount[0]*100)
    if totamount < 0:
        sign = '-'
    else:
        sign = ' '
    total_amount_record = gen_total_amount_record(
        bankgiroProvider=bankgiroProvider,
        len_supInvList=len(supInvList),
        totamount=abs(totamount),
        sign=sign
    )
    lines.append(total_amount_record)
    # width = 80
    # for i, line in enumerate(lines):
    #     l = len(line)
    #     if l < width:
    #         lines[i] += ' ' * (width - l)
    return lines


def transferOrderBankgiro(bankgiroProvider, supInvList):
    # Generate a payment order file to be sent to Bankgirot
    # Purpouse of function is that un-joined records are easier to test.
    lines = transferOrderBankgiroRecords(bankgiroProvider=bankgiroProvider, supInvList=supInvList)
    if PYT3:
        return [('\n'.join(lines) + '\n')]  # .encode('latin-1', 'replace')]
    return [('\n'.join(lines) + '\n').encode('latin-1', 'replace')]


def gen_seal_opening_record():
    encrypt_header = u'00{0!s:6}{1!s:4}{2!s:68}'.format(
        time.strftime('%y%m%d', time.localtime(time.time())),
        'HMAC',
        ''
    )
    return encrypt_header


def normalize_text(message):
    # For HMAC calculation all newlines must be stripped and non ascii characters replaced.
    replace_swedish_chr = {
        201:  64,  # É
        196:  91,  # Ä
        214:  92,  # Ö
        197:  93,  # Å
        220:  94,  # Ü
        233:  96,  # é
        228: 123,  # ä
        246: 124,  # ö
        229: 125,  # å
        252: 126,  # ü
    }

    def norm(i, tbl):
        if 32 <= i <= 126:
            return i
        try:
            nc = tbl[i]
        except KeyError:
            nc = 195
        return nc

    normalized = []
    if PYT3:
        messreprep=message.replace(b'\n', b'').replace(b'\r', b'')
        for c in messreprep:
            normalized.append(norm(c, replace_swedish_chr))
        normalized_msg = bytes(normalized)
    else:
        messreprep = message.replace('\n', '').replace('\r', '')
        for c in messreprep:
            normalized.append(chr(norm(ord(c), replace_swedish_chr)))
        normalized_msg = ''.join(normalized)

    return normalized_msg


def hmac_sha256_128(key, msg):
    hash_obj = hmac.new(key, msg, hashlib.sha256)
    return hash_obj.hexdigest()[:32]


def hmac_sha256_128_bgsigner(lock, msg):
    # See README for bg-signer by Iko.
    signer = serial.Serial("/dev/bgsigner", timeout=5)
    signer.write("\rUNLOCK %s\r" % lock)
    assert signer.readline().strip() == 'OK'
    signer.write("\rHMAC-SHA-256 1 128 %s " % len(msg))
    signer.write(msg.encode('hex'))
    signer.write("\r")
    hmac = signer.readline().strip()
    signer.close()
    return hmac.lower()


def hmac_sha256_128_bgsigner_truncated_256(lock, msg):
    """
    Sign message with 256bit key from 32 chr string, trunkate mac to 32 chr
    """
    signer = serial.Serial("/dev/bgsigner", timeout=5)
    signer.write("\rUNLOCK %s\r" % lock)
    assert signer.readline().strip() == 'OK'
    signer.write("\rHMAC-SHA-256 2 256 %s " % len(msg))
    signer.write(msg.encode('hex'))
    signer.write("\r")
    hmac = signer.readline().strip()
    signer.close()
    return hmac.lower()[:32]


def create_hmac(msg, force_software_signer=False):
    if os.path.exists('/dev/bgsigner') and not force_software_signer:
        lock = config.config.get('bankgiro', 'signer_lock')
        seal = hmac_sha256_128_bgsigner(lock, msg)
    else:
        key = config.config.get('bankgiro', 'test_key')
        if PYT3:
            seal = hmac_sha256_128(codecs.decode(key, 'hex'), msg)
        else:
            seal = hmac_sha256_128(key.decode('hex'), msg)
    return seal


def gen_tamper_protection_record(key_verification_value, hmac_seal):
    encrypt_footer = u'99{0!s:>6}{1!s:32}{2!s:32}{3!s:8}'.format(
        time.strftime('%y%m%d', time.localtime(time.time())),
        key_verification_value,
        hmac_seal,
        ''
    )
    return encrypt_footer.upper()


def sealTransferOrder(message):
    # See document hmac_tamperprotection_technicalmanual_en.pdf from bankgirot.se
    encryptheader = gen_seal_opening_record() + '\n'
    message = encryptheader + message
    message = message.encode('latin-1', 'replace')
    normalized_msg = normalize_text(message)
    seal = create_hmac(normalized_msg)

    standard_file = b'00000000'
    kvv = create_hmac(standard_file)

    encryptfooter = gen_tamper_protection_record(kvv, seal) + '\n'
    encryptfooter = encryptfooter.encode('latin-1', 'replace')
    sealed_msg = message + encryptfooter
    return sealed_msg


def signBgcOrder(bgcOrder):
    order_unsigned = bgcOrder.order_unsigned[0]
    order_signed = sealTransferOrder(message=order_unsigned)
    if PYT3:
        order_signed = order_signed.decode()
    bgcOrder(order_signed=[order_signed])
    return bgcOrder


