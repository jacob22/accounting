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

from pytransact.context import ReadonlyContext
import functools
import accounting.db
import members
import blm.members

TotalIN_ID = 'TI12345678'

def normalise_pg(pgnum):
    return ''.join(c for c in pgnum if c in '0123456789')


class FixedWidthWriter(object):

    def __init__(self, out, width):
        self.out = out
        self.width = width

    def write(self, line):
        assert '\n' not in line
        assert len(line) < self.width
        self.out.write(line)
        self.out.write(' ' * (self.width - len(line)))
        self.out.write('\n')


def fixedWidth(func):
    @functools.wraps(func)
    def wrapper(*args, **kw):
        if not isinstance(kw['out'], FixedWidthWriter):
            kw['out'] = FixedWidthWriter(kw['out'], 80)
        return func(*args, **kw)
    return wrapper


@fixedWidth
def generate_pg_file(provider, purchases, timestamp, file_id, start_tid, out):
    fmt = '00TI{0:0>8}  {1}01TL1TOTALIN-T'
    assert len(timestamp) == len('YYYYMMDDHHMMSS')
    timestamp += '0' * 6 # nanoseconds
    out.write(fmt.format(file_id, timestamp))

    num_lines = generate_pg(provider, purchases, timestamp[:8],
                            start_tid, out=out)

    fmt = '99{0:0>15}'
    out.write(fmt.format(num_lines + 2))


@fixedWidth
def generate_pg(provider, purchases, date, start_tid, out):
    fmt = '10{0:<36}SEK{1}'
    assert len(date) == 8
    out.write(fmt.format(normalise_pg(provider.pgnum[0]), date))

    tot_lines = 1
    tot_price = 0
    for transaction_number, purchase in enumerate(purchases, start_tid):
        price, lines = generate_pg_transaction(
            purchase, transaction_number, out=out)
        tot_price += price
        tot_lines += lines

    fmt = '90{0:0>8}{1:0>17}{2}001'
    out.write(fmt.format(len(purchases), tot_price, date))
    tot_lines += 1

    return tot_lines


@fixedWidth
def generate_pg_transaction(purchase, transaction_number, out):
    fmt = '20{0:<35}{1:0>15}{2}{3}'

    try:
        partial_payments = purchase.partial_payments
    except AttributeError:
        partial_payments = 1

    bg_no = ' ' * 8
    price = int(purchase.total[0] * 100)
    lines = 0
    for n in range(1, partial_payments + 1):
        tno = transaction_number + 10 * n
        tno = '{0:1>17}'.format(tno)
        out.write(fmt.format(purchase.ocr[0], price // partial_payments,
                             tno, bg_no))
        lines += 1
        lines += generate_payer_data(purchase, out=out)

    return price, lines


import re
address_re = '(?P<address>.+)\n(?P<zip>[\d ]+) (?P<city>.+)'

@fixedWidth
def generate_payer_data(purchase, out):
    lines = 0
    if purchase.buyerName:
        fmt = u'50{0:<35}{1:<35}'
        out.write(fmt.format(purchase.buyerName[0], ''))
        lines += 1

    if purchase.buyerAddress:
        match = re.match(address_re, purchase.buyerAddress[0])
        if match:
            fmt = u'51{0:<35}{1:<35}'
            out.write(fmt.format(match.group('address').strip(), ''))
            lines += 1

            fmt = u'52{0:<9}{1:<35}'
            out.write(fmt.format(match.group('zip').strip(),
                                 match.group('city').strip()))
            lines += 1

    return lines


if __name__ == '__main__':
    import datetime, sys
    from pytransact.queryops import *
    database = accounting.db.connect()
    with ReadonlyContext(database):
        orgid = sys.argv[1]
        file_id = 12345678
        start_tid = 1
        try:
            file_id = int(sys.argv[2])
            start_tid = int(sys.argv[3])
        except IndexError:
            pass

        org, = blm.accounting.Org._query(id=orgid).run()
        provider, = blm.accounting.PlusgiroProvider._query(org=org).run()

        purchases = blm.members.Purchase._query(
            org=org, matchedPayments=Empty()).run()

        if purchases:
            generate_pg_file(provider, purchases,
                             datetime.datetime.now().strftime('%Y%m%d%H%M%S'),
                             file_id, start_tid,
                             out=sys.stdout)
