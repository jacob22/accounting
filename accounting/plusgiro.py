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

import time
import textwrap
import pytransact.exceptions


def gen_cfp_po3_mh00(org, sending_bank_account):
    header_record = u'MH00{0!s:8}{1!s:10}{2!s:12}{3!s:10}{4!s:3}{5!s:6}{6!s:3}{7!s:24}'.format(
        '',  # blank
        org.orgnum[0].replace('-', ''),
        '',  # blank
        sending_bank_account,
        'SEK',
        '',  # blank
        'SEK',
        ''   # blank
    )
    return header_record


def gen_cfp_po3_pi00(supplierInvoice):
    si, = supplierInvoice
    clearing = False
    reference = ''
    if si.transferMethod[0] == 'pgnum':
        payment_type = '00'
        transferAddress = si.pgnum[0]
        if si.invoiceIdentifierType[0] in ('ocr', 'invoiceNumber'):
            try:
                reference = si[str(si.invoiceIdentifierType[0])][0]
            except IndexError:
                pass
    elif si.transferMethod[0] == 'address':
        payment_type = '02'
        raise pytransact.exceptions.cBlmError('System not prepared for payment to address.')
    elif si.transferMethod[0] == 'bgnum':
        payment_type = '05'
        transferAddress = si.bgnum[0]
        if si.invoiceIdentifierType[0] in ('ocr', 'invoiceNumber'):
            try:
                reference = si[str(si.invoiceIdentifierType[0])][0]
            except IndexError:
                pass
    elif si.transferMethod[0] == 'bankaccount':
        payment_type = '09'
        clearing = si.bankclearing[0]
        transferAddress = si.bankaccount[0]
        if si.invoiceIdentifierType[0] in ('message', 'invoiceNumber'):
            try:
                reference = si[str(si.invoiceIdentifierType[0])][0][:12]
            except IndexError:
                pass
    if si.transferDate:
        transferDate = si.transferDate[0].replace('-', '')
    else:
        transferDate = time.strftime('%Y%m%d', time.localtime(time.time()))
    payment_instruction = u'PI00{0!s:2}{1!s:5}{2!s:10}{3!s:3}{4!s:8}{5!s:0>13}{6!s:25}{7!s:10}'.format(
        payment_type,
        clearing or '',
        transferAddress,
        '',  # blank
        transferDate,
        int(si.amount[0] * 100),
        reference,
        ''  # blank
    )
    return payment_instruction


def gen_cfp_po3_ba00(supplierInvoice):
    si, = supplierInvoice
    internal_reference = u'BA00{0!s:18}{1!s:9}{2!s:35}{3!s:14}'.format(
        si.recipient[0][:18],
        '',  # blank
        str(si.id[0]),
        ''  # blank
    )
    return internal_reference


def gen_cfp_po3_bm99(supplierInvoice):
    si, = supplierInvoice
    if si.invoiceIdentifierType[0] == 'message' and si.transferMethod[0] in ('pgnum', 'bgnum'):
        messagelines = textwrap.wrap(si.message[0], 35)
    else:
        return []
    records = []
    for part1, part2 in zip(*[iter(messagelines)]*2):
        message_record = u'BM99{0!s:35}{1!s:35}{2!s:6}'.format(
            part1,
            part2,
            ''  # blank
        )
        records.append(message_record)
    return records[:5]


def gen_cfp_po3_mt00(supInvList):
    record_count = len(supInvList)
    amount_sum = int(sum([si.amount[0] for si in supInvList]) * 100)
    closing_record = u'MT00{0!s:25}{1!s:0>7}{2!s:0>15}{3!s:29}'.format(
        '',  # blank
        record_count,
        amount_sum,
        ''  # blank
    )
    return closing_record


def generatePlusgiroRecords(org, sending_bank_account, supInvList):
    lines = []
    lines.append(gen_cfp_po3_mh00(org=org, sending_bank_account=sending_bank_account))
    for si in supInvList:
        lines.append(gen_cfp_po3_pi00([si]))
        lines.append(gen_cfp_po3_ba00([si]))
        lines += gen_cfp_po3_bm99([si])
    lines.append(gen_cfp_po3_mt00(supInvList))
    return lines
