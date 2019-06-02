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

from collections import namedtuple, defaultdict
from datetime import datetime
from decimal import Decimal
import functools, re, time
from flask import current_app, g, json, make_response, render_template, request
import jinja2
import os
from pytransact.context import ReadonlyContext
from pytransact import queryops
import blm.accounting
import bson

static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')

def format_amount(fmt, d, create_spans=True):
    try:
        formatted = fmt.format(d)
    except ValueError:
        return d

    if create_spans:
        # put each group of three digits in a span, so spans can be
        # visually separated by css
        spans = ('<span class="part-of-amount">%s</span>' % part
                 for part in formatted.split(','))
        return jinja2.Markup(''.join(spans))
    else:
        return formatted.replace(',', u'\xa0')  # nbsp

# format decimals with tousands sep:
def thousand_sep(d):
    return format_amount('{0:,f}', d)

def no_decimals(d):
    if isinstance(d, str):
        return d
    return format_amount('{0:,.0f}', d)

def negate_no_decimals(d):
    if isinstance(d, str):
        return d
    return format_amount('{0:,.0f}', -d)

def absolute(d): # xxx could this be merged with negate_no_decimals?
    try:
        return abs(d)
    except ValueError:
        return d

def get_timestamp():
    now = datetime.now()
    return now.strftime('%Y-%m-%d %H:%M')

def timestamp2date(ts):
    return time.strftime('%Y-%m-%d', time.localtime(ts))


Row = namedtuple('Row', 'number name opening_balance total')

def make_sums(accounts, from_accno, to_accno, from_date=None, to_date=None):

    def process_account(account):
        opening_balance = account.opening_balance[0]
        total = Decimal('0.00')
        for transaction in account.transactions:
            if from_date and transaction.transaction_date[0] < from_date:
                opening_balance += transaction.amount[0]
            elif to_date and transaction.transaction_date[0] > to_date:
                break
            else:
                total += transaction.amount[0]

        return Row(account.number, account.name, [opening_balance], [total])

    rows = [process_account(account) for account in accounts
           if account.number[0] >= from_accno and account.number[0] < to_accno]

    section_totals = (sum([row.opening_balance[0] for row in rows], Decimal('0.00')),
                      sum([row.total[0] for row in rows], Decimal('0.00')))

    return rows, section_totals


class RunningTotals(object):

    def __init__(self, transactions, opening_balance):
        self.transactions = sorted(
            transactions,
            key=lambda tr: (tr.verification[0].transaction_date[0],
                            tr.verification[0].series[0].name[0],
                            tr.verification[0].number[0]))
        self.total = opening_balance
        self.debit, self.credit = Decimal('0.00'), Decimal('0.00')

    def __iter__(self):
        for transaction in self.transactions:
            self.total += transaction.amount[0]
            if transaction.amount[0] > 0:
                self.debit += transaction.amount[0]
            else:
                self.credit -= transaction.amount[0]
            yield transaction


def parse_range(s, npat=r'\d+'):
    result = []
    npat = r'\b{0}\b'.format(npat)
    pattern = r'({0}-{0}|{0})'.format(npat)

    for part in re.findall(pattern, s):
        part = re.sub(r'[^\d-]', '', part)
        part = list(map(int, part.split('-')))
        if len(part) == 1:
            result.extend(part)
        if len(part) == 2:
            start, end = part
            result.extend(range(start, end+1))
    return list(map(str, result))


def render_report_template(*args, **kw):
    with open(os.path.join(static_dir, 'report.css'), 'r') as f:
        css = f.read()
    kw.setdefault('css', css)
    return render_template(*args, **kw)


def report(filename):
    """
    Decorator for report producing functions.

    It will:
     - Set up a ReadonlyContext with the right user
     - Attach the correct Content-Disposition header in case the user
       is downloading the report as a file.
     - Set up a jinja environment with commonly used utility functions

    Arguments: filename - The filename of the downloaded version of
                          the report
    """
    # explodes if filename isn't ascii, which is the only thing we
    # support right now
    filename.encode('ascii')

    def mkdecorator(func):
        @functools.wraps(func)
        def decorator(*args, **kw):
            env = current_app.jinja_env
            env.filters['thousand_sep'] = thousand_sep
            env.filters['negate_no_decimals'] = negate_no_decimals
            env.filters['no_decimals'] = no_decimals
            env.filters['timestamp2date'] = timestamp2date
            env.globals['make_running_totals'] = RunningTotals
            env.globals['make_sums'] = make_sums
            env.filters['abs'] = absolute

            if 'filters' in request.values:
                kw.setdefault('filters', json.loads(request.values['filters']))

            with ReadonlyContext(g.database, g.user) as ctx:
                # maybe we should move the actual template rendering
                # here too?
                response = func(*args, **kw)
                if request.args.get('mode') == 'download':
                    response = make_response(response)
                    response.headers['Content-Disposition'] = \
                        'attachment; filename=%s' % filename
                return response
        # func_name is apparently important to flask...
        try:
            decorator.func_name = func.func_name
        except AttributeError:
            pass
        return decorator
    return mkdecorator


def route(app, requires_login):
    """
    Sets up wsgi routes to reports.

    Arguments: app - wsgi app
               requires_login - decorator that checks login status
    """
    routes = {
        '/kontoplan/<accounting>': kontoplan,
        '/huvudbok/<accounting>': huvudbok,
        '/balansrakning/<accounting>': balance_report,
        '/resultatrakning/<accounting>': income_statement_report,
        '/verifikationslista/<accounting>': verifications,
        '/arsrapport/<accounting>': year_report,
        '/verifikat/<objectid:verification>': print_verification,
        '/vatreport/<objectid:accounting>': vat_report,
        '/periodrapport/<accounting>': period_report,
        '/salesreport/<objectid:toid>': sales_report,
        '/verifikationslista_andrade/<accounting>': verifications_modified,
        '/accountspayable_report/<accounting>': accountspayable_report,
        '/accountspayable_paymentjournal/<accounting>': accountspayable_paymentjournal
        }
    for route, func in routes.items():
        name = func.__name__
        func = requires_login()(func)
        app.add_url_rule(route, name, func, methods=['GET', 'POST'])


# reports

@report('kontoplan.html')
def kontoplan(accounting):
    accounting = blm.accounting.Accounting._query(id=accounting).run()
    report_result = blm.accounting.accounts_layout(accounting)
    return render_report_template('kontoplan.html', acc=accounting[0],
        time=get_timestamp(), result=report_result)


@report('huvudbok.html')
def huvudbok(accounting, filters={}):
    accounting = blm.accounting.Accounting._query(id=accounting).run()
    numbers = []
    if 'accounts' in filters:
        numbers = parse_range(filters['accounts'], npat=r'\d{4}')

    report_result = blm.accounting.main_ledger_report(accounting, numbers)
    return render_report_template('huvudbok.html', acc=accounting[0],
        time=get_timestamp(), result=report_result)


@report('balansrakning.html')
def balance_report(accounting, filters={}):
    env = current_app.jinja_env

    def balance_sums(args):
        sum1 = sum([n[0] for n in args])
        sum2 = sum([n[1] for n in args])
        return (sum1, sum2, sum1+sum2)
    env.globals['balance_sums'] = balance_sums

    start, end = filters.get('daterange', (None, None))
    env.globals['make_sums'] = functools.partial(env.globals['make_sums'],
                                                 from_date=start, to_date=end)

    accounting = blm.accounting.Accounting._query(id=accounting).run()
    report_result = blm.accounting.balance_report(accounting)

    return render_report_template('balansrakning.html', time=get_timestamp(),
        acc=accounting[0], result=report_result)


@report('resultatrakning.html')
def income_statement_report(accounting, filters={}):
    env = current_app.jinja_env

    def income_sums(args):
        return sum([n[1] for n in args], Decimal('0.00'))
    env.globals['income_sums'] = income_sums

    start, end = filters.get('daterange', (None, None))
    env.globals['make_sums'] = functools.partial(env.globals['make_sums'],
                                                 from_date=start, to_date=end)


    accounting = blm.accounting.Accounting._query(id=accounting).run()
    report_result = blm.accounting.income_statement_report(accounting)

    return render_report_template('resultatrakning.html', time=get_timestamp(),
        acc=accounting[0], result=report_result)

try:
    from itertools import izip_longest
except ImportError:
    from itertools import zip_longest as izip_longest
def year_report_income_sums(args):
    # args is a list of lists which can vary in length.
    # We want to sum the i:th element of each list
    # If the sub-list does not contain enough elements, assume
    # a 0.
    result = []
    for arg in args:
        result = [a + b for a, b in
                  izip_longest(result, arg, fillvalue=Decimal('0.00'))]

    return result

@report('arsrapport.html')
def year_report(accounting):
    ''' An income statement and budget report comparing several years. '''
    env = current_app.jinja_env

    env.globals['income_sums'] = year_report_income_sums

    def make_sums(report_result, start, end):
        def sum(l):
            ''' A version of sum that ignores non-numeric values. '''
            s = Decimal('0.00')
            for i in l:
                try:
                    s += i
                except:
                    pass
            return s
        rows = [r for r in report_result
                if r[0] >= start and r[0] < end]
        section_totals = []
        try:
            n = len(rows[0])
            for i in range(2, n):
                section_totals.append(sum( r[i] for r in rows ))
        except IndexError:
            section_totals = [] # Section empty

        return rows, section_totals

    env.globals['make_sums'] = make_sums
    env.globals['make_int'] = int

    accounting = blm.accounting.Accounting._query(id=accounting).run()
    report_result = blm.accounting.year_report(accounting)

    print_matrix = []
    def get_acc_value(index, attr):
        try:
            obj = r.account_balances[index]
        except KeyError:
            return '-'
        return getattr(obj, attr)[0]

    for r in report_result:
        print_matrix.append((r.number[0], r.name[0],
                             get_acc_value('-4', 'balance'),
                             get_acc_value('-3', 'balance'),
                             get_acc_value('-2', 'balance'),
                             get_acc_value('-1', 'balance'),
                             get_acc_value('-1', 'budget'),
                             get_acc_value('0', 'balance'),
                             get_acc_value('0', 'budget')))

    return render_report_template('arsrapport.html', time=get_timestamp(),
        acc=accounting[0], result=print_matrix)

@report('periodrapport.html')
def period_report(accounting, filters={}):


    ##Get start of year from accounting
    accounting = blm.accounting.Accounting._query(id=accounting).run()
    start_of_acc_year,  = accounting[0].start #grabs the firts item in list
    end_of_acc_year,  = accounting[0].end #grabs the firts item in list

    #filterdates and rules for missing dates
    period_start_date, period_end_date = filters.get('daterange', (None, None))
    #filterdatum

    if period_start_date == None: period_start_date = start_of_acc_year
    if period_end_date == None: period_end_date = end_of_acc_year


    #filtername = "Daterange"
    filterinfo = str(period_start_date) + " - " + str(period_end_date)

    """
create logic for providing filter values when one or more are not provided by user choice

<!--- if startdate of period empty - use start of accountingyear  --->
<!--- print Period: firstdate -  --->
<!---     if enddate empty use end of end of accounting year --->

    """


    env = current_app.jinja_env
    env.globals['income_sums'] = year_report_income_sums

    """
    #These functions can not reach global scope. is there a workaround /Paul
    #sum acconts from period start to period end

    #make_period_sums = functools.partial(reports.make_sums,  from_date=period_start_date, to_date=period_end_date)
    #make_to_period_end_sums = functools.partial(make_sums,  from_date=start_of_acc_year, to_date=period_end_date)

    #sum accounts from start of year to period end

    """



    #sum up account balances in section
    def make_sums(report_result, start, end):
        def sum(l):
            ''' A version of sum that ignores non-numeric values. '''
            s = Decimal('0.00')
            for i in l:
                try:
                    s += i
                except:
                    pass
            return s

        rows = [r for r in report_result   #filter accounts between start and end
                if r[0] >= start and r[0] < end]
        section_totals = []
        try:
            n = len(rows[0])
            for i in range(2, n):
                section_totals.append(sum( r[i] for r in rows ))
        except IndexError:
            section_totals = [] # Section empty

        return rows, section_totals



    #env.globals['make_period_sums']  = make_period_sums
   # env.globals['make_to_period_end_sums']  = make_to_period_end_sums
    env.globals['make_sums'] = make_sums
    env.globals['make_int'] = int


    #provides accountingdata from database

    #summed? budget data for the current year
    accounting = blm.accounting.Accounting._query(id=accounting).run() #accounting object
    accounts = blm.accounting.period_report(accounting) #account sum for current year

    print_matrix = []
    def get_acc_value(index, attr):
        try:
            obj = r.account_balances[index]
        except KeyError:
            return '-'
        return getattr(obj, attr)[0]

    def account_period_sum(account,  start_date, end_date):
        #sum transactions in given accountobject based on period dates
        return sum((transaction.amount[0] for transaction in account.transactions
                            if  start_date <= transaction.transaction_date[0] <= end_date),
                            Decimal('0.00'))


    for r in accounts:
        print_matrix.append((r.number[0], r.name[0],
                                        account_period_sum(r,  period_start_date, period_end_date),
                                        account_period_sum(r,  start_of_acc_year,  period_end_date),
                                        get_acc_value('-1', 'balance'),   #previous year
                                        get_acc_value('0', 'budget')))



    return render_report_template('periodrapport.html', time=get_timestamp(),
                                                    acc = accounting[0], result = print_matrix ,
                                                    filterinfo = filterinfo ) #acc is required for render_report_templact() to work



@report('verifikationslista.html')
def verifications(accounting, filters={}):
    q = blm.accounting.Accounting._query(id=accounting)
    q.attrList = ['end', 'start']
    accounting, = q.run()



    #capture start and enddate of accounting year
    start_of_acc_year,   = accounting.start#grabs the firts item in list
    end_of_acc_year,   = accounting.end #grabs the firts item in list



    if 'series' in filters:
  #      print filters['series']
        q = blm.accounting.VerificationSeries._query(id=filters['series'])

    else:
        q = blm.accounting.VerificationSeries._query(accounting=accounting)

    q.attrList = ['name']
    series = q.run()



    filterinfo_series = ''
    if series:
    #for s in series:
        #filterinfo_series += s.name[0] + ' '
        x=[s.name[0] for s in series]
        x.sort()
        filterinfo_series = ", ".join(x)
    #else:
        #get available series from accounting,
        #create list and string

    filtername_series = 'Series'
    qparam = {'series': series}


    start, end = filters.get('daterange', (None, None))
    if start and end:
        qparam['transaction_date'] = queryops.Between(start, end)
    elif start:
        qparam['transaction_date'] = queryops.GreaterEq(start)
    elif end:
        qparam['transaction_date'] = queryops.LessEq(end)


    #filterdates if missing
    if start == None: start = start_of_acc_year
    if end == None: end = end_of_acc_year

    filtername_daterange = "Daterange"
    filterinfo_daterange = str(start) + " - " + str(end)


    if 'numbers' in filters:
        qparam['number'] = parse_range(filters['numbers'])
        filterinfo_verificationnumbers = str(filters['numbers'])
    else: filterinfo_verificationnumbers =  u'1 - ' + u'\u221E' #replace this with smallest and largest number in database

    filtername_verificationnumbers = "Verification numbers"


    q = blm.accounting.Verification._query(**qparam)
    q.attrList = ['series', 'number', 'registration_date', 'transactions']
    verifications = q.run()
    def sort_key(ver):
        key = ver.series[0].name[0], ver.number[0]
        return key

    verifications.sort(key=sort_key)



    # preload Transactions
    q = blm.accounting.Transaction._query(verification=verifications)
    q.attrList = ['account', 'amount', 'text', 'transaction_date',
                  'verification']
    transactions = q.run()

    accounts = set(t.account[0] for t in transactions)

    # preload Accounts
    q = blm.accounting.Account._query(id=accounts)
    q.attrList = ['number', 'name']
    q.run()

    # Workaround for faulty scoping rules in the template language
    totals = {}
    for v in verifications:
        #v.series[0].name[0]  ## pekar ut namnet på angiven serie
        debit, credit = Decimal('0.00'), Decimal('0.00')
        for t in v.transactions:
            if t.amount[0] > 0:
                debit += t.amount[0]
            else:
                credit -= t.amount[0]
        totals[(v.series[0], v.number[0])] = (debit, credit)




    return render_report_template('verifikationslista.html', time=get_timestamp(),
                           acc=accounting, verifications=verifications,
                           totals=totals,
                           filtername_daterange = filtername_daterange,  filterinfo_daterange = filterinfo_daterange,
                           filtername_series = filtername_series,  filterinfo_series = filterinfo_series,
                           filtername_verificationnumbers = filtername_verificationnumbers,  filterinfo_verificationnumbers = filterinfo_verificationnumbers  )

@report('verifikationslista_andrade.html')
def verifications_modified(accounting, filters={}):
    q = blm.accounting.Accounting._query(id=accounting)
    q.attrList = ['end', 'start']
    accounting, = q.run()

    #capture start and enddate of accounting year
    start_of_acc_year,   = accounting.start#grabs the firts item in list
    end_of_acc_year,   = accounting.end #grabs the firts item in list

    if 'series' in filters:
        q = blm.accounting.VerificationSeries._query(id=filters['series'])

    else:
        q = blm.accounting.VerificationSeries._query(accounting=accounting)

    q.attrList = ['name']
    series = q.run()

    filterinfo_series = ''
    if series:
        x=[s.name[0] for s in series]
        x.sort()
        filterinfo_series = ", ".join(x)

    filtername_series = 'Series'
    qparam = {'series': series}

    start, end = filters.get('daterange', (None, None))
    if start and end:
        qparam['transaction_date'] = queryops.Between(start, end)
    elif start:
        qparam['transaction_date'] = queryops.GreaterEq(start)
    elif end:
        qparam['transaction_date'] = queryops.LessEq(end)

    #filterdates if missing
    if start == None: start = start_of_acc_year
    if end == None: end = end_of_acc_year

    filtername_daterange = "Daterange"
    filterinfo_daterange = str(start) + " - " + str(end)

    if 'numbers' in filters:
        qparam['number'] = parse_range(filters['numbers'])
        filterinfo_verificationnumbers = str(filters['numbers'])
    else: filterinfo_verificationnumbers =  u'1 - ' + u'\u221E' #replace this with smallest and largest number in database

    filtername_verificationnumbers = "Verification numbers"

    q = blm.accounting.Verification._query(log=queryops.NotEmpty(), **qparam)
    q.attrList = ['series', 'number', 'registration_date', 'transactions']
    verifications = q.run()
    def sort_key(ver):
        key = ver.series[0].name[0], ver.number[0]
        return key

    verifications.sort(key=sort_key)

    # preload Transactions
    q = blm.accounting.Transaction._query(verification=verifications)
    q.attrList = ['account', 'amount', 'text', 'transaction_date',
                  'verification']
    transactions = q.run()

    accounts = set(t.account[0] for t in transactions)

    # preload Accounts
    q = blm.accounting.Account._query(id=accounts)
    q.attrList = ['number', 'name']
    q.run()

    def get_signature(logentry):
        try:
            return logentry['signature_name'][0]
        except (KeyError, IndexError):
            pass
        try:
            return logentry['signature'][0]
        except (KeyError, IndexError):
            return ''

    mv = []
    # Workaround for faulty scoping rules in the template language
    totals = {}
    for v in verifications:
        vlog = []
        for (version, logentries) in v.log.items():
            decoded = []
            for logentry in logentries:
                entry = bson.BSON(logentry).decode()
                if entry.keys() == ['id']:
                    continue
                decoded.append(entry)
            vlog.append((int(version), decoded))
        vlog.sort()
        mv.append((v, vlog))
        #v.series[0].name[0]  ## pekar ut namnet på angiven serie
        debit, credit = Decimal('0.00'), Decimal('0.00')
        for t in v.transactions:
            if t.amount[0] > 0:
                debit += t.amount[0]
            else:
                credit -= t.amount[0]
        totals[(v.series[0], v.number[0])] = (debit, credit)

    return render_report_template(
        'verifikationslista_andrade.html',
        time=get_timestamp(),
        acc=accounting,
        modified_verifications=mv,
        totals=totals,
        get_signature=get_signature,
        filtername_daterange=filtername_daterange,
        filterinfo_daterange=filterinfo_daterange,
        filtername_series=filtername_series,
        filterinfo_series=filterinfo_series,
        filtername_verificationnumbers=filtername_verificationnumbers,
        filterinfo_verificationnumbers=filterinfo_verificationnumbers)

@report('momsrapport.html')
def vat_report(accounting):
    accounting, = blm.accounting.Accounting._query(id=accounting).run()

    # preload accounts
    q = blm.accounting.Account._query(accounting=accounting)
    q.attrList = ['name', 'vatCode']
    q.run()

    q = blm.accounting.Verification._query(accounting=accounting)
    q.attrList = ['transactions']
    verifications = q.run()

    # preload transactions
    q = blm.accounting.Transaction._query(verification=verifications)
    q.attrList = ['account', 'amount']
    q.run()

    vatReport = defaultdict(Decimal)
    codeDescrs = {toi.code[0]: toi.description[0] for toi in
                  blm.accounting.VatCode._query(
            _attrList=['code', 'description']).run()}

    for verification in verifications:
        for transaction in verification.transactions:
            account = transaction.account[0]
            if account.vatCode:
                vatCode = account.vatCode[0]
                vatReport[vatCode] += transaction.amount[0]

    vatReport = sorted(vatReport.items())
    return render_report_template(
        'momsrapport.html', acc=accounting, time=get_timestamp(),
        vatReport=vatReport, codeDescrs=codeDescrs)


@report('sales_report.html') # this should probably be dynamic somehow
def sales_report(toid):
    query = blm.members.Product._query(id=toid)
    query._attrList = 'name optionFields'.split()
    product, = query.run()
    fields = [field.split('\x1f')[0] for field in product.optionFields]

    query = blm.members.PurchaseItem._query(product=product)
    query.attrList = 'price product purchase quantity options'.split()
    items = query.run()

    # Preload associated purchases.
    query = blm.members.Purchase._query(
        id=[item.purchase[0].id[0] for item in items if item.purchase],
        _attrList='buyerName buyerPhone buyerEmail date paymentState'.split())
    query.run()

    items = [item for item in items if (item.purchase and item.paid[0] and item.purchase[0].kind[0] != 'credit')]
    items.sort(key=lambda toi: toi.id[0])

    with open(os.path.join(static_dir, 'sales_report.css'), 'r') as f:
        sales_css = f.read()

    return render_report_template('sales_report.html', product=product,
                                  fields=fields, items=items,
                                  sales_css=sales_css)


@report('accountspayable_report.html')
def accountspayable_report(accounting, filters={}):
    accounting, = blm.accounting.Accounting._query(id=accounting).run()
    org = accounting.org[0]
    if not filters:
        query = blm.accounting.SupplierInvoice._query(org=org)
    else:
        query = blm.accounting.SupplierInvoice._query(org=org, **filters)

    query.attrList = [
        'org',
        'accounted',
        'invoiceState',
        'automated',
        'recipient',
        'invoiceType',
        'amount',
        'transferMethod',
        'pgnum',
        'bgnum',
        'bankaccount',
        'bankclearing',
        'transferAddress',
        'invoiceIdentifierType',
        'ocr',
        'invoiceNumber',
        'message',
        'invoiceIdentifier',
        'registrationVerification',
        'transferVerification',
        'invoiceDate',
        'dateInvoiceRegistered',
        'transferDate',
        'dueDate',
        'images']
    supInvList = query.run()
    supInvList.sort(key = lambda d: (d['transferDate'][0], d['dateInvoiceRegistered'][0]))

    images = [image for si in supInvList for image in si.images]

    # Preload associated images.
    query = blm.accounting.InvoiceImage._query(
        id=images,
        _attrList=['filename'])
    imagefilenames = query.run()

    # Preload associated verifications.
    vers = []
    for si in supInvList:
        vers += si.registrationVerification
        vers += si.transferVerification
    query = blm.accounting.Verification._query(
        id=vers,
        _attrList=['number', 'series'])
    verifications = query.run()

    series = blm.accounting.Verification._query(
        accounting=accounting,
        _attrList=['name']
    ).run()

    return render_report_template(
        'accountspayable_report.html',
        acc=accounting,
        supInvList=supInvList,
        verifications=verifications,
        imagefilenames=imagefilenames,
        series=series
    )

@report('accountspayable_paymentjournal.html')
def accountspayable_paymentjournal(accounting, filters={}):
    accounting, = blm.accounting.Accounting._query(id=accounting).run()
    org = accounting.org[0]

    if not filters:
        query = blm.accounting.SupplierInvoice._query(org=org, invoiceType='debit', automated=False, accounted=False)
    else:
        query = blm.accounting.SupplierInvoice._query(org=org, invoiceType='debit', automated=False, accounted=False, **filters)

    query.attrList = [
        'org',
        'accounted',
        'invoiceState',
        'automated',
        'recipient',
        'invoiceType',
        'amount',
        'transferMethod',
        'pgnum',
        'bgnum',
        'bankaccount',
        'bankclearing',
        'transferAddress',
        'invoiceIdentifierType',
        'ocr',
        'invoiceNumber',
        'message',
        'invoiceIdentifier',
        'registrationVerification',
        'transferVerification',
        'invoiceDate',
        'dateInvoiceRegistered',
        'transferDate',
        'dueDate',
        'images']
    supInvList = query.run()
    supInvList.sort(key = lambda d: (d['transferDate'][0], d['dateInvoiceRegistered'][0]))

    # Preload associated verifications.
    vers = []
    for si in supInvList:
        vers += si.registrationVerification
    query = blm.accounting.Verification._query(
        id=vers,
        _attrList=['number', 'series'])
    verifications = query.run()

    return render_report_template(
        'accountspayable_paymentjournal.html',
        acc=accounting,
        supInvList=supInvList,
    )


@report('verifikat.html') # XXX should be dynamic
def print_verification(verification):
    verification, = blm.accounting.Verification._query(id=verification).run()

    # Workaround for faulty scoping rules in the template language
    totals = {}
    debit, credit = Decimal('0.00'), Decimal('0.00')
    for t in verification.transactions:
        if t.amount[0] > 0:
            debit += t.amount[0]
        else:
            credit -= t.amount[0]
    totals = (debit, credit)

    return render_report_template('verifikat.html', time=get_timestamp(),
        verification=verification, totals=totals, acc=verification.accounting[0])

