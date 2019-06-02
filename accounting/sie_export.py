#!/usr/bin/env python
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

import codecs
from accounting import db
from pytransact import blm
from blm import fundamental, accounting
from decimal import Decimal
import pytransact.queryops as Q
import datetime
try:
    basestring
except NameError:
    basestring = str
def sie_export(fp, acc):
    '''Takes a cp437 encoded file handle.'''
    fp.write(u'#FLAGGA 0\n')
    fp.write(print_program_name())
    fp.write(print_format())
    fp.write(print_gen())
    fp.write(print_sietype())
    " Skipping #PROSA"
    fp.write(print_orgtype(acc))
    fp.write(print_org_id(acc))
    fp.write(print_orgnum(acc))
    fp.write(print_industry_code(acc))
    fp.write(print_address(acc))
    fp.write(print_orgname(acc))
    fp.write(print_accounting_year(acc))
    for year in acc.years.keys():
        if year != '0':
            fp.write(print_prev_accounting_year(year,
                acc.years[year][0], acc.years[year][1]))
    fp.write(print_taxation_year(acc))
    # Skipping #OMFATTN
    fp.write(print_layout(acc))
    fp.write(print_currency(acc))

    # Defining accounts, dimensions and objects
    q = accounting.Account._query(accounting=acc)
    q.attrList = ['number', 'name', 'type', 'unit', 'sru', 'account_balances']
    accounts = sorted(q.run(), key=lambda acc: acc.number[0]) 
    for account in accounts:
        fp.write(print_account(account))
        fp.write(print_account_type(account))
        if len(account.unit):
            fp.write(print_unit(account))
        if len(account.sru):
            fp.write(print_sru(account))
    dims = sorted(accounting.Dimension._query(accounting=acc).run(),
                  key=lambda dim: dim.number[0])
    for dim in dims:
        if len(dim.subdim_of) == 0:
            fp.write(print_dim(dim))
        else:
            fp.write(print_subdim(dim))
        for obj in accounting.AccountingObject._query(dimension=dim).run():
            fp.write(print_accounting_object(obj))

    # Setting opening balances etc
    for account in accounts:
        for bal in account.account_balances.value.values():
            if account.type[0] in ['T', 'S']:
                fp.write(print_opening_balance(account.number[0], bal))
                fp.write(print_closing_balance(account.number[0], bal))
            else:
                fp.write(print_turnover(account.number[0], bal))
    
    # Skipping object balances for now
    # Skipping period balances and period budgets for now

    for ver in blm.accounting.Verification._query(accounting=acc).run():
        fp.write(print_verification(ver))
        fp.write(u'{\n')
        for trans in ver.transactions:
            fp.write(print_transaction(trans))
        fp.write(u'}\n')

def remove_dashes_from_date(date):
    date_list = date.split("-")
    return ''.join(date_list)

def or_empty(obj):
    if len(obj):
        return obj[0]
    else:
        return u''

def escape(s):
    if isinstance(s, basestring):
        return s.replace('"', r'\"')
    return s

def print_program_name():
    return u'#PROGRAM "Eutaxia Admin" "Version X.Y"\n'

def print_format():
    return u'#FORMAT "PC8"\n'

def print_gen(): # XXX Test, get a real user identifier
    today = datetime.date.today()
    return u'#GEN {} {}\n'.format(today.strftime('%Y%m%d'), 'User')

def print_sietype():
    return u'#SIETYP 4\n'

def print_orgtype(accounting):
    try:
        return u'#FTYP "{}"\n'.format(escape(accounting.orgtype[0]))
    except IndexError:
        return u''

def print_org_id(accounting):
    # Is this the correct id?
    assert isinstance(accounting, blm.accounting.Accounting)
    return u'#FNR "{}"\n'.format(accounting.org[0].id[0])

def print_orgnum(accounting):
    # could be #ORGNR orgnum aquisitionnum activitynum but we ignore the
    # last 2 unimplemented fields for now.
    return u'#ORGNR "{}"\n'.format(escape(accounting.orgnum[0]))

def print_industry_code(accounting):
    try:
        return u'#BKOD "{}"\n'.format(escape(accounting.industry_code[0]))
    except IndexError:
        return u''

def print_address(accounting):
    return u'#ADRESS "{}" "{}" "{}" "{}"\n'.format(
        escape(or_empty(accounting.contact)),
        escape(or_empty(accounting.mail_address)),
        escape(or_empty(accounting.zip_city)),
        escape(or_empty(accounting.telephone)))

def print_orgname(accounting):
    return u'#FNAMN "{}"\n'.format(escape(accounting.orgname[0]))

def print_accounting_year(accounting): # XXX Test
    return u'#RAR 0 {} {}\n'.format(
        remove_dashes_from_date(accounting.start[0]),
        remove_dashes_from_date(accounting.end[0]))

def print_prev_accounting_year(year_index, start, end): # XXX Test
    return u'#RAR {} {} {}\n'.format(year_index,
        remove_dashes_from_date(start),
        remove_dashes_from_date(end))

def print_taxation_year(accounting):
    try:
        return u'#TAXAR "{}"\n'.format(accounting.taxation_year[0])
    except IndexError:
        return u''
                                      
def print_layout(accounting): 
    # This field is optional.
    # Permitted values are BAS95, BAS96, EUBAS97 or NE2007, or something
    # that begins with "BAS2"  .. i.e BAS2007.
    # If the field does not exist, assume BAS95
    # If the field exists and is in the BAS2xxx, use EUBAS97
    try:
        layout = accounting.layout[0]
    except IndexError as e:
        layout = 'BAS95'
    
    if layout.startswith('BAS2'):
        # should we check that there are only 3 digits after the 2?
        layout = 'EUBAS97'
    
    if layout in ['BAS95', 'BAS96', 'EUBAS97', 'NE2007']:
        return u'#KPTYP "{}"\n'.format(layout)
    else:
        # should we raise an exception here?  Try to keep going?
        return u'#KPTYP "{} not in BAS95, BAS96, EUBAS97, NE2007 or BAS2xxx"\n'.format(layout)

def print_currency(accounting): 
    # This field is optional.
    # If the field does not exist, assume SEK
    try:
        currency = accounting.currency[0]
    except IndexError as e:
        currency = 'SEK'
    return u'#VALUTA "{}"\n'.format(escape(currency))

def print_account(account):
    return u'#KONTO {} "{}"\n'.format(
        account.number[0],
        escape(account.name[0]))

def print_account_type(account):
    return u'#KTYP {} {}\n'.format(account.number[0], account.type[0])

def print_unit(account):
    return u'#ENHET {} "{}"\n'.format(
        account.number[0],
        escape(account.unit[0]))

def print_sru(account):
    return u'#SRU {} {}\n'.format(account.number[0], account.sru[0])

def print_dim(dim):
    return u'#DIM {} "{}"\n'.format(
        dim.number[0],
        escape(dim.name[0]))

def print_subdim(dim):
    return u'#UNDERDIM {} "{}" {}\n'.format(
        dim.number[0],
        escape(dim.name[0]),
        dim.subdim_of[0].number[0])

def print_accounting_object(obj):
    return u'#OBJEKT {} {} "{}"\n'.format(
        obj.dimension[0].number[0],
        obj.number[0],
        escape(obj.name[0]))

def print_opening_balance(account_number, bal):
    s = u'#IB {} {} {}'.format(bal.year[0], account_number, bal.opening_balance[0])
    if bal.opening_quantity[0] != Decimal(0):
        s += u' {}\n'.format(bal.opening_quantity[0])
    else:
        s += u'\n'
    return s

def _print_balance(command, account_number, bal):
    s = u'{} {} {} {}'.format(command, bal.year[0], account_number, bal.balance[0])
    if bal.balance_quantity[0] != Decimal(0):
        s += u' {}\n'.format(bal.balance_quantity[0])
    else:
        s += u'\n'
    return s

def print_closing_balance(account_number, bal):
    return _print_balance('#UB', account_number, bal)

def print_turnover(account_number, bal):
    return _print_balance('#RES', account_number, bal)

def print_verification(obj):
    return u'#VER {} {} {} "{}" "{}" "{}"\n'.format(
        obj.series[0].name[0],
        obj.number[0],
        remove_dashes_from_date(obj.transaction_date[0]),
        escape(or_empty(obj.text)),
        escape(remove_dashes_from_date(or_empty(obj.registration_date))),
        escape(or_empty(obj.signature)))

def print_transaction(obj):
    accounting_objects = u'{}' 

    def mk_string(tag):    
        return u'{} {} {} {} {} "{}" {:f} "{}"\n'.format(
            tag,
            obj.account[0].number[0],
            accounting_objects,
            obj.amount[0],
            remove_dashes_from_date(obj.transaction_date[0]),
            escape(obj.text[0]),
            obj.quantity[0],
            escape(or_empty(obj.signature)))
    # We don't implement this yet, so don't try to print obj.accounting_objects
    if obj.transtype[0] == 'added':
        return mk_string(u'#RTRANS') + mk_string('#TRANS')
    elif obj.transtype[0] == 'deleted':
        return mk_string(u'#BTRANS')
    else:
        return mk_string(u'#TRANS')

if __name__ == '__main__':
    class StdOutWrapper(object):
        def __init__(self, fp):
            self.fp = fp
        def write(self, s):
            self.fp.write(s.encode('cp437'))

    from pytransact import context
    import bson, locale, sys
    locale.setlocale(locale.LC_CTYPE, '')
    enc = locale.getpreferredencoding()
    database = db.connect()
    for acctname in sys.argv[1:]:
        acctname = acctname.decode(enc)
        sys.stdout.write('Exporting %s ' % acctname)
        sys.stdout.flush()
        interested = bson.objectid.ObjectId()
        with context.ReadonlyContext(database) as ctx:
            org, acct = acctname.split(':')
            org = accounting.Org._query(name=Q.Like('%s*' % org)).run()
            if org:
                acct = accounting.Accounting._query(org=org, start=Q.Like('%s*' % acct)).run()

            sie_export(StdOutWrapper(sys.stdout), acct[0])
