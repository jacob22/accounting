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

from datetime import datetime
from decimal import Decimal
try:
    from exceptions import ValueError   #py2
except ImportError:
    pass   #py3

try:
    unicode
    py3chr = lambda x: x
    py3txt = lambda x: x
except NameError:
    py3chr = lambda x: chr(x)
    py3txt = lambda x: x.decode('latin-1')
    unicode = str
    
    
class Transaction(object):
    def __init__(self, customer_ref, amount, transaction_number):
        self.customer_refs = [customer_ref]
        self.amount = amount
        self.transaction_number = transaction_number
        self.reverse_code = 'No'
        self.messages = []
        self.sender_names = []
        self.sender_addresses = []
        self.sender_postal_code = ''
        self.sender_city = ''
        self.sender_country_code = 'SE'
        self.payer_account = ''
        self.payer_organization_number = ''
        self.payer_names = []
        self.payer_addresses = []
        self.payer_postal_code = ''
        self.payer_city = ''
        self.payer_country_code = 'SE'
        
    def add_bg_number(self, bg_number):
        self.bg_number = bg_number

    def set_reverse_code(self, code):
        if code == '':
            self.reverse_code = 'Yes'
        elif code == '0':
            self.reverse_code = 'Full'
        elif code == '1':
            self.reverse_code = 'Partial'
        elif code == '2':
            self.reverse_code = 'Final part'
        else:
            raise ValueError(code)
    
    def add_attrs(self, attr, value1, value2):
        attribute = getattr(self, attr)
        attribute.append(value1)
        if value2 != '':
            attribute.append(value2)

    def add_sender_code_city(self, code, city, country_code):
        self.sender_postal_code = code
        self.sender_city = city
        if country_code:
            self.sender_country_code = country_code

    def add_payer_code_city(self, code, city, country_code):
        # The payer is normally the senders bank
        self.payer_postal_code = code
        self.payer_city = city
        if country_code:
            self.payer_country_code = country_code

    def add_payer_account(self, account, account_type, organization_number):
        if account != '' and int(account) != 0:
            self.payer_account = account
            if account_type == '1':
                self.payer_account_type = 'Bank account'
            elif account_type == '2':
                self.payer_account_type = 'Bank Giro'
            else:
                self.payer_account_type = 'Other'
        if organization_number != '':
            self.payer_organization_number = organization_number 

    def add_foreign_data(self, bank_costs, bank_cost_currency,
                         foreign_amount, foreign_currency, conversion_rate):
        if bank_costs != Decimal(0):
            self.foreign_bank_costs = bank_costs
            self.foreign_bank_cost_currency = bank_cost_currency
        self.foreign_amount = foreign_amount
        self.foreign_currency = foreign_currency
        self.conversion_rate = conversion_rate

    def add_bg_reference(self, sender_bg_num, customer_ref, amount,
                         ref_code, payment_channel_code,
                         bgc_serial_number, image_flag):
        self.customer_refs.append(customer_ref.strip())
        # Ignore the other stuff. It is mostly redundant as far as I can see.
        # Amount may contain the amount for this reference, but I don't think
        # we need to keep it.

    def add_bg_message(self, msg):
        self.messages.append(msg)

    def add_orgnum(self, num):
        if num != '':
            self.payer_organization_number = num.strip('0') 
  
    def add_sender_street_code(self, street, postal_code):
        self.sender_addresses.append(street)
        self.sender_postal_code = postal_code

    def add_sender_city_country(self, city, country, country_code):
        self.sender_city = city
        # Ingnore country. We have the country code
        if country_code:
            self.sender_country_code = country_code

class GiroAccount(object):
    channel_codes = {
        '1': 'EB', # Electronic bank transfer
        '2': 'LB', # Leverantörsbetalningar, a Bankgirot electronic service
        '3': 'Blankett', # Paper form
        '4': 'Autogiro', # Not currently used
        }
    def __init__(self, account, currency, transaction_date=None):
        self.account = account
        self.currency = currency
        self.transaction_date = transaction_date
        self.transactions = []

    def add_transaction(self, customer_ref, amount,
                        transaction_number, bg_number):
        self.current_transaction = Transaction(customer_ref, amount,
                                               transaction_number)
        self.current_transaction.add_bg_number(bg_number)
        self.transactions.append(self.current_transaction)
        return self.current_transaction

    def add_reverse_transaction(self, customer_ref, amount,
                                transaction_number, reverse_code):
        self.current_transaction = Transaction(customer_ref, -amount,
                                               transaction_number)
        self.current_transaction.set_reverse_code(reverse_code)
        self.transactions.append(self.current_transaction)
        return self.current_transaction

    def end(self, count, total, account_statement_reference):
        self.count = count
        self.total = total
        self.account_statement_reference = account_statement_reference

    def recalc(self, customer_ref, ref_code):
        if ref_code == '0':
            code = 'Empty'
            customer_ref = u''
        elif ref_code == '1':
            code = 'Empty: No service agreement'
            customer_ref = u''
        elif ref_code == '2':
            code = 'OCR'            
            customer_ref = customer_ref.strip()
        elif ref_code == '3':
            code = 'Multiple'            
        elif ref_code == '4':
            code = 'OCR'
            customer_ref = customer_ref.rstrip()
        else:
            code = 'Faulty'

        return (customer_ref, code)

    def add_bg_transaction(self, payer_bg_num, customer_ref, amount,
                           ref_code, payment_channel_code,
                           bgc_serial_number, image_flag):
        customer_ref, code = self.recalc(customer_ref, ref_code)
        t = Transaction(customer_ref, amount,
                                               bgc_serial_number)
        t.payer_account = payer_bg_num
        t.reference_code = code
        t.payment_channel_code = GiroAccount.channel_codes[payment_channel_code]
        t.image_flag = image_flag
        self.current_transaction = t
        self.transactions.append(t)
        return t

    def add_bg_reverse_transaction(self, sender_bg_num, customer_ref, amount,
                                    ref_code, payment_channel_code,
                                    bgc_serial_number, image_flag,
                                    deduction_code):
        trans = self.add_bg_transaction(sender_bg_num, customer_ref, -amount,
                                        ref_code, payment_channel_code,
                                        bgc_serial_number, image_flag)
        trans.set_reverse_code(deduction_code)
        return trans

    def end_bg_account(self, receiver_bank_account, transaction_date,
                       deposit_sequence_number, deposit_amount,
                       deposit_currency, number_of_transactions,
                       type_of_deposit):
        
        self.receiver_bank_account = receiver_bank_account
        self.transaction_date = transaction_date
        self.account_statement_reference = deposit_sequence_number
        self.total = deposit_amount
        # Redundant
        #self.currency = deposit_currency
        self.count = number_of_transactions
        self.type_of_deposit = type_of_deposit # Probably useless
        
class PGRecords(object):
    def __init__(self, my_id, timestamp, delivery, file_type, file_type_name):
        self.my_id = my_id # Our total-in customer number
        self.timestamp = timestamp # A string YYYYMMDDHHMMSSNNNNNN
        self.delivery = delivery # Sequence number for this day 1, 2, 3...
        assert file_type == 'TL1'
        # If it is TOTALIN-T it is a test
        assert file_type_name in ('TOTALIN', 'TOTALIN-T')
        self.giro_accounts = []

        # unique id of this file
        self.file_id = '%s%s%s' % (my_id, timestamp, delivery)

    def add_account(self, account, currency, transaction_date):
        self.current_account = GiroAccount(account, currency, transaction_date)
        self.giro_accounts.append(self.current_account)

class BGRecords(object):
    def __init__(self, layout, version, timestamp, testmark):
        assert layout == "BGMAX"
        assert version == '01'
        assert testmark == 'P'
        self.timestamp = timestamp # string CCYYMMDDHHMMSSµµµµµµ
        self.giro_accounts = []

        # unique id of this file
        self.file_id = timestamp

    def add_bg_account(self, bg_account, pg_account, currency):
        self.current_account = GiroAccount(bg_account, currency)
        self.current_account.pg_account = pg_account
        self.giro_accounts.append(self.current_account)

class Parser(object):
    def __init__(self):
        self.linecount = 0

    def parse(self, txt):
        if py3chr(txt[0]) in '\r\n':
            return
        self.linecount += 1
        key = py3txt(txt[:2])
        subfields, method = self.fielddefs[key]
        params = self.parse_subfields(subfields, txt)
        method(self, *params)

    def parse_subfields(self, fieldlist, txt):
        params =[]
        for start, stop, param_type in fieldlist:
            subfield = py3txt(txt[start-1: stop])
            if param_type == '_': # Reseved field (blanks), skip
                continue
            elif param_type == '0': # Reserved field (zeros), skip
                continue
            elif param_type == 'T': # Text
                subfield = subfield.rstrip()
                try:
                    subfield = subfield.decode('iso8859-1')
                except AttributeError:
                    pass
            elif param_type == 'A': # Account
                subfield = subfield.lstrip('0')
            elif param_type == 'I': # Integer
                subfield = int(subfield)
            elif param_type == 'D': # Date YYYYMMDD
                subfield = datetime.strptime(subfield, '%Y%m%d').date()
            elif param_type == 'd': # Date YYMMDD
                subfield = datetime.strptime(subfield, '%y%m%d').date()
            elif param_type == 'd0': # Date YYMMDD or 000000
                try:
                    subfield = datetime.strptime(subfield, '%y%m%d').date()
                except ValueError:
                    if subfield == '000000':
                        subfield = None
                    else:
                        raise
            elif param_type == 'd_': # Date YYMMDD or blank or GENAST
                try:
                    subfield = datetime.strptime(subfield, '%y%m%d').date()
                except ValueError:
                    if subfield.strip() == '':
                        subfield = None
                    elif subfield == 'GENAST':
                        pass
                    else:
                        raise
            elif param_type == 'C': # Currency
                subfield = Decimal(subfield[:-4] + '.' + subfield[-4:])
            elif param_type == 'N': # Amount in decimal
                subfield = Decimal(subfield[:-2] + '.' + subfield[-2:])
            else:
                raise ValueError('Unknown fieldtype', param_type, ' for subfield ', subfield)
            params.append(subfield)
        return params

class PGParser(Parser):
    def __init__(self):
        self.linecount = 0
        self.fielddefs = pg_fielddefs

    def file_header(self, *params):
        self.records = PGRecords(*params)

    def start_account(self, *params):
        self.records.add_account(*params)

    def start_transaction(self, *params):
        self.trans = self.records.current_account.add_transaction(*params)

    def start_reverse_transaction(self, *params):
        self.trans = self.records.current_account.add_reverse_transaction(*params)
    def add_references(self, *params):
        self.trans.add_attrs('customer_refs', *params)

    def add_messages(self, *params):
        self.trans.add_attrs('messages', *params)

    def add_sender_name(self, *params):
        self.trans.add_attrs('sender_names', *params)

    def add_sender_address(self, *params):
        self.trans.add_attrs('sender_addresses', *params)

    def add_sender_code_city(self, *params):
        self.trans.add_sender_code_city(*params)
        
    def add_payer_account(self, *params):
        self.trans.add_payer_account(*params)
        
    def add_payer_name(self, *params):
        self.trans.add_attrs('payer_names', *params)

    def add_payer_address(self, *params):
        self.trans.add_attrs('payer_addresses', *params)

    def add_payer_code_city(self, *params):
        self.trans.add_payer_code_city(*params)

    def foreign_payment(self, *params):
        self.trans.add_foreign_data(*params)

    def end_account(self, *params):
        self.records.current_account.end(*params)

    def file_end(self, *params):
        if params[0] != self.linecount:
            raise ValueError('linecount')
        
# Field starting and ending positions. Initial position has index 1
# T = Text
# I = Integer
# D = Date
# N = Decimal number, 2 significant decimals
# C = Currency conversion - decimal number, 4 significant decimals
# A = Account number, right adjusted, zero filled

pg_fielddefs = {
    '00': ([(3, 14, 'T'), (15, 34, 'T'), (35, 36, 'I'),
            (37, 39, 'T'), (40, 49, 'T')], PGParser.file_header),
    '10': ([(3, 38, 'T'), (39, 41, 'T'), (42, 49, 'D')], PGParser.start_account),
    '20': ([(3, 37, 'T'), (38, 52, 'N'), (53, 69, 'T'), (70, 77, 'T')],
           PGParser.start_transaction),
    '25': ([(3, 37, 'T'), (38, 52, 'N'), (53, 69, 'T'), (70, 70, 'T')],
           PGParser.start_reverse_transaction),
    '30': ([(3, 37, 'T'), (38, 72, 'T')], PGParser.add_references),
    '40': ([(3, 37, 'T'), (38, 72, 'T')], PGParser.add_messages),
    '50': ([(3, 37, 'T'), (38, 72, 'T')], PGParser.add_sender_name),
    '51': ([(3, 37, 'T'), (38, 72, 'T')], PGParser.add_sender_address),
    '52': ([(3, 11, 'T'), (12, 46, 'T'), (47, 48, 'T')],
           PGParser.add_sender_code_city),
    '60': ([(3, 38, 'T'), (39, 39, 'T'), (40, 59, 'T')],
           PGParser.add_payer_account),
    '61': ([(3, 37, 'T'), (38, 72, 'T')], PGParser.add_payer_name),
    '62': ([(3, 37, 'T'), (38, 72, 'T')], PGParser.add_payer_address),
    '63': ([(3, 11, 'T'), (12, 46, 'T'), (47, 48, 'T')],
           PGParser.add_payer_code_city),
    '70': ([(3, 17, 'N'), (18, 20, 'T'), (39, 53, 'N'),
           (54, 56, 'T'), (57, 68, 'C')], PGParser.foreign_payment),
    '90': ([(3, 10, 'I'), (11, 27, 'N'), (28, 38, 'T')], PGParser.end_account),
    '99': ([(3, 17, 'I')], PGParser.file_end),
    }

class BGParser(Parser):
    def __init__(self):
        self.linecount = 0
        self.fielddefs = bg_fielddefs

    def file_header(self, *params):
        self.records = BGRecords(*params)
        
    def start_account(self, *params):
        self.records.add_bg_account(*params)

    def start_transaction(self, *params):
        self.trans = self.records.current_account.add_bg_transaction(*params)

    def start_reverse_transaction(self, *params):
        self.trans = self.records.current_account.add_bg_reverse_transaction(*params)

    def add_sender_name(self, *params):
        self.trans.add_attrs('sender_names', *params)

    def add_references(self, *params):
        self.trans.add_bg_reference(*params)

    def add_messages(self, *params):
        self.trans.add_bg_message(*params)

    def add_orgnum(self, *params):
        self.trans.add_orgnum(*params)

    def add_sender_address(self, *params):
        self.trans.add_sender_street_code(*params)
    
    def add_sender_city_country(self, *params):
        self.trans.add_sender_city_country(*params)

    def end_bg_account(self, *params):
        self.records.current_account.end_bg_account(*params)

    def file_end(self, *params):
        if len(self.records.giro_accounts) != params[3]:
            raise ValueError('accounts')
        if sum(len(x.transactions) for x in self.records.giro_accounts) != params[0] + params[1]:
            raise ValueError('transactions')

bg_fielddefs = {
    '01': ([(3, 22, 'T'), (23, 24, 'T'), (25, 44, 'T'), (45, 45, 'T')],
           BGParser.file_header),
    '05': ([(3, 12, 'A'), (13, 22, 'A'), (23, 25, 'T')],
           BGParser.start_account),
    '20': ([(3, 12, 'A'), (13, 37, 'T'), (38, 55, 'N'), (56, 56, 'T'),
            (57, 57, 'T'), (58, 69, 'T'), (70, 70, 'T')],
           BGParser.start_transaction),
    '21': ([(3, 12, 'A'), (13, 37, 'T'), (38, 55, 'N'), (56, 56, 'T'),
            (57, 57, 'T'), (58, 69, 'T'), (70, 70, 'T'), (71, 71, 'T')],
           BGParser.start_reverse_transaction),
    '22': ([(3, 12, 'A'), (13, 37, 'T'), (38, 55, 'N'), (56, 56, 'T'),
            (57, 57, 'T'), (58, 69, 'T'), (70, 70, 'T')],
           BGParser.add_references),
    '23': ([(3, 12, 'A'), (13, 37, 'T'), (38, 55, 'N'), (56, 56, 'T'),
            (57, 57, 'T'), (58, 69, 'T'), (70, 70, 'T')],
           BGParser.add_references),
    '25': ([(3, 52, 'T')], BGParser.add_messages),
    '26': ([(3, 37, 'T'), (38, 72, 'T')], BGParser.add_sender_name),
    '27': ([(3, 37, 'T'), (38, 46, 'T')], BGParser.add_sender_address),
    '28': ([(3, 37, 'T'), (38, 72, 'T'), (73, 74, 'T')],
           BGParser.add_sender_city_country),
    '29': ([(3, 14, 'T')], BGParser.add_orgnum),
    '15': ([(3, 37, 'A'), (38, 45, 'D'), (46, 50, 'I'), (46, 68, 'N'),
            (69, 71, 'T'), (72, 79, 'I'), (80, 80, 'T')],
           BGParser.end_bg_account),
    '70': ([(3, 10, 'I'), (11, 18, 'I'), (19, 26, 'I'), (27, 38, 'I')],
           BGParser.file_end),
    }

# Field starting and ending positions. Initial position has index 1
# T = Text
# I = Integer
# D = Date yyyymmdd
# d = Date yymmdd
# N = Decimal number, 2 significant decimals
# C = Currency conversion - decimal number, 4 significant decimals
# A = Account number, right adjusted, zero filled

#
# LB-in request file to be sent to Bankgirot
#

class Payment(object):
    def __init__(
            self,
            payees_bankgiro_or_credit_transfer_number,
            ocr_or_invoice_number,
            amount,
            payment_date,
            information_to_sender):
        self.target = payees_bankgiro_or_credit_transfer_number
        self.identifier = ocr_or_invoice_number
        self.payment_date = payment_date
        self.information_to_sender = information_to_sender

class LBRequestRecords(object):
    def __init__(self):
        self.payments = []
        pass

    def add_sender_bankgiro_number(self, sender_bankgiro_number):
        self.sender_bankgiro_number = sender_bankgiro_number

    def add_payment(self, payment):
        self.payments.append(payment)

class LBRequestParser(Parser):
    def __init__(self):
        self.linecount = 0
        self.fielddefs = lbin_fielddefs
        self.records = LBRequestRecords()
        self.sections = []
        self.record_target = None

    def opening_record(self, sender_bankgiro_number, senders_file_creation_date, product, payment_date, currency_code):
        # TK11
        assert unicode(product) == u'LEVERANTORSBETALNINGAR' or unicode(product) == u'LEVERANTÖRSBETALNINGAR'
        self.records = LBRequestRecords()
        self.sections.append(self.records)
        self.records.add_sender_bankgiro_number(sender_bankgiro_number)

    def fixed_information_record(self, *params):
        # TK12
        pass

    def header_record(self, *params):
        # TK13
        pass

    def payment_record(
            self,
            payees_bankgiro_or_credit_transfer_number,
            ocr_or_invoice_number,
            amount,
            payment_date,
            information_to_sender):
        # TK14
        self.record_target = payees_bankgiro_or_credit_transfer_number
        payment = Payment(
            payees_bankgiro_or_credit_transfer_number,
            ocr_or_invoice_number,
            amount,
            payment_date,
            information_to_sender)
        self.records.add_payment(payment)

    def deduction_record(self, *params):
        # TK15
        pass

    def credit_invoice_partial(self, *params):
        # TK16
        pass

    def credit_invoice_entire(self, *params):
        # TK17
        pass

    def information_record(self, *params):
        # TK25
        pass

    def name_record(self, *params):
        # TK26
        pass

    def address_record(self, *params):
        # TK27
        pass

    def total_amount_record(self, *params):
        # TK29
        pass

    def account_number_record(self, *params):
        # TK40
        pass

    def plusgiro_payment_record(self, *params):
        # TK54
        pass

    def plusgiro_information_record(self, *params):
        # TK65
        pass

    def cancellation_and_date_amendment_record(self, *params):
        # TKLB
        #self.sections.append(amendment_record)
        pass

lbin_fielddefs = {
    '11': ([(3, 12, 'A'), (13, 18, 'd'), (19, 40, 'T'), (41, 46, 'd_'),
            (47, 59, '_'), (60, 62, 'T'), (63, 80, '_')],
           LBRequestParser.opening_record),
    '12': ([(3, 52, 'T'), (53, 58, 'd'), (59, 80, '_')],
           LBRequestParser.fixed_information_record),
    '13': ([(3, 27, 'T'), (28, 39, 'T'), (40, 80, '_')],
           LBRequestParser.header_record),
    '14': ([(3, 12, 'A'), (13, 37, 'T'), (38, 49, 'N'), (50, 55, 'd_'),
            (56, 60, '_'), (61, 80, 'T')],
           LBRequestParser.payment_record),
    '15': ([(3, 12, 'A'), (13, 37, 'T'), (38, 49, 'N'), (50, 55, 'd_'),
            (56, 60, '_'), (61, 80, 'T')],
           LBRequestParser.deduction_record),
    '16': ([(3, 12, 'A'), (13, 37, 'T'), (38, 49, 'N'), (50, 55, 'd_'),
            (56, 60, '_'), (61, 80, 'T')],
           LBRequestParser.credit_invoice_partial),
    '17': ([(3, 12, 'A'), (13, 37, 'T'), (38, 49, 'N'), (50, 55, 'd_'),
            (56, 60, '_'), (61, 80, 'T')],
           LBRequestParser.credit_invoice_entire),
    '25': ([(3, 12, 'A'), (13, 62, 'T'), (63, 80, '_')],
           LBRequestParser.information_record),
    '26': ([(3, 6, '0'), (7, 12, 'A'), (13, 47, 'T'), (48, 80, 'T')],
           LBRequestParser.name_record),
    '27': ([(3, 6, '0'), (7, 12, 'A'), (13, 47, 'T'), (48, 52, 'T'),
            (53, 72, 'T'), (73, 80, '_')],
           LBRequestParser.address_record),
    '29': ([(3, 12, 'A'), (13, 20, 'I'), (21, 32, 'N'), (33, 33, 'T'),
            (34, 80, '_')],
           LBRequestParser.total_amount_record),
    '40': ([(3, 6, '0'), (7, 12, 'A'), (13, 16, 'I'), (17, 28, 'I'),
            (29, 40, 'T'), (41, 41, 'T'), (42, 80, '_')],
           LBRequestParser.account_number_record),
    '54': ([(3, 12, 'A'), (13, 37, 'T'), (38, 49, 'N'), (50, 55, 'd_'),
            (56, 60, '_'), (61, 80, 'T')],
           LBRequestParser.plusgiro_payment_record),
    '65': ([(3, 12, 'A'), (13, 47, 'T'), (48, 80, '_')],
           LBRequestParser.plusgiro_information_record),
    'LB': ([(3, 4, 'I'), (5, 10, 'I'), (11, 20, 'A'), (21, 30, 'A'),
            (31, 36, 'd_'), (37, 42, 'd_'), (43, 54, 'N'), (55, 66, '_'),
            (67, 71, 'T'), (72, 74, 'T'), (75, 77, '_'), (78, 80, '_')],
           LBRequestParser.cancellation_and_date_amendment_record),
}

# Field starting and ending positions. Initial position has index 1
# T = Text
# I = Integer
# D = Date yyyymmdd
# d = Date yymmdd
# d0 = Date yymmdd or 000000
# d_ = Date yymmdd or blank
# N = Decimal number, 2 significant decimals
# C = Currency conversion - decimal number, 4 significant decimals
# A = Account number, right adjusted, zero filled
# _ = reserved field (blank), skip.
# 0 = reserved field (zeros), skip.


class LBRecords(object):
    def __init__(self, senders_bankgiro_number, bankgirots_creation_date, product, payment_date, report_code, currency_code):
        assert unicode(product) == u'LEVERANTORSBETALNINGAR' or unicode(product) == u'LEVERANTÖRSBETALNINGAR'
        assert report_code == '1'
        self.completed_transactions = []

    def add_completed_transaction(
            self,
            payees_bankgiro_or_credit_transfer_number,
            ocr_or_invoice_number,
            amount,
            payment_type_code,
            referenced_bankgiro_number,
            information_to_sender):
        self.completed_transactions.append(information_to_sender)

    def add_completed_transaction_plusgiro(
            self,
            payees_plusgiro_number,
            ocr_or_invoice_number,
            amount,
            processing_code,
            referenced_bankgiro_number,
            information_to_sender):
        self.completed_transactions.append(information_to_sender)

    def name_record(self, payees_bankgiro_number, payees_name, extra_name_field):
        pass

class LBParser(Parser):
    def __init__(self):
        self.linecount = 0
        self.fielddefs = lbout_fielddefs
        self.sections = []

    def opening_record(self, *params):
        # TK11
        self.records = LBRecords(*params)
        self.sections.append(self.records)

    def payment_record(self, *params):
        # TK14
        self.records.add_completed_transaction(*params)

    def deduction_record(self, *params):
        # TK15
        pass

    def credit_monitor_partial(self, *params):
        # TK16
        pass

    def credit_monitor_full(self, *params):
        # TK17
        pass

    def credit_invoice_remainder_record(self, *params):
        # TK20
        pass

    def credit_previous_deductions_record(self, *params):
        # TK21
        # add up to 3 previous deductions per record,
        # multiple contigous TK21 records possible.
        pass

    def information_record(self, *params):
        # TK25
        pass

    def name_record(self, *params):
        # TK26
        pass

    def address_record(self, *params):
        # TK27
        pass

    def total_sum_record(self, *params):
        # TK29
        # Total amount per section, the sum of all TK14, TK15, TK16, TK17 and TK54.
        pass

    def account_number_record(self, *params):
        # TK40
        # The account number record appears immediately before the payment record (TK14).
        pass

    def payment_record_plusgiro_number(self, *params):
        # TK54
        self.records.add_completed_transaction_plusgiro(*params)
        pass

    def information_record_plusgiro_number(self, *params):
        # TK65
        pass

# Field starting and ending positions. Initial position has index 1
# T = Text
# I = Integer
# D = Date yyyymmdd
# d = Date yymmdd
# d0 = Date yymmdd or 000000
# d_ = Date yymmdd or blank
# N = Decimal number, 2 significant decimals
# C = Currency conversion - decimal number, 4 significant decimals
# A = Account number, right adjusted, zero filled
# _ = reserved field, skip.

# Payments specification with payment types
# Betalningsspecifikation med Betaltyper
lbout_fielddefs = {
    '11': ([(3, 12, 'A'), (13, 18, 'd'), (19, 40, 'T'), (41, 46, 'd'),
            (47, 47, 'T'), (48, 59, '_'), (60, 62, 'T'), (63, 80, '_')],
           LBParser.opening_record),
    '14': ([(3, 12, 'A'), (13, 37, 'T'), (38, 49, 'N'), (50, 50, 'T'),
            (51, 60, 'A'), (61, 80, 'T')],
            LBParser.payment_record),
    '15': ([(3, 12, 'A'), (13, 37, 'T'), (38, 49, 'N'), (50, 50, 'T'),
            (51, 60, 'A'), (61, 80, 'T')],
            LBParser.deduction_record),
    '16': ([(3, 12, 'A'), (13, 37, 'A'), (38, 49, 'N'), (50, 55, 'd'),
            (56, 56, 'I'), (57, 60, '_'), (61, 80, 'T')], LBParser.credit_monitor_partial),
    '17': ([(3, 12, 'A'), (13, 37, 'A'), (38, 49, 'N'), (50, 55, 'd'),
            (56, 56, 'I'), (57, 60, '_'), (61, 80, 'T')], LBParser.credit_monitor_full),
    '20': ([(3, 12, 'A'), (13, 18, 'd'), (19, 30, 'N'), (31, 42, 'N'), (43, 80, '_')],
           LBParser.credit_invoice_remainder_record),
    '21': ([(3, 12, 'A'), (13, 18, 'd'), (19, 30, 'N'),
                          (31, 36, 'd0'), (37, 48, 'N'),
                          (49, 54, 'd0'), (55, 66, 'N'), (67, 80, '_')],
           LBParser.credit_previous_deductions_record),
    '25': ([(3, 12, 'A'), (13, 62, 'T'), (63, 80, '_')], LBParser.information_record),
    '26': ([(3, 12, 'A'), (13, 47, 'T'), (48, 80, 'T')], LBParser.name_record),
    '27': ([(3, 12, 'A'), (13, 47, 'T'), (48, 52, 'T'), (53, 72, 'T'), (73, 80, '_')], LBParser.address_record),
    '29': ([(3, 12, 'A'), (13, 20, 'I'), (21, 32, 'N'), (33, 80, '_')], LBParser.total_sum_record),
    '40': ([(3, 12, 'A'), (13, 16, 'T'), (17, 28, 'A'), (29, 40, 'T'), (41, 41, 'T'), (42, 80, '_')], LBParser.account_number_record),
    '54': ([(3, 12, 'A'), (13, 37, 'T'), (38, 49, 'N'), (50, 50, 'I'), (51, 60, 'A'), (61, 80, 'T')], LBParser.payment_record_plusgiro_number),
    '65': ([(3, 12, 'A'), (13, 47, 'T'), (48, 80, '_')], LBParser.information_record_plusgiro_number)
}


# Reconciliation report
# Avstämningsrapport
class LBReconciliationRecords(object):
    def __init__(self, senders_bankgiro_number, bankgirots_creation_date, product, payment_date, report_code, currency_code):
        assert unicode(product) == u'LEVERANTÖRSBETALNINGAR'
        assert report_code == '2'

class LBReconciliationParser(Parser):
    def __init__(self):
        self.linecount = 0
        self.fielddefs = lbout_reconciliation_fielddefs
        self.sections = []

    def opening_record(self, *params):
        # TK11
        self.records = LBReconciliationRecords(*params)
        self.sections.append(self.records)

    def end_record(self, *params):
        # TK29
        pass

    def balance_1(self, *params):
        # TK40
        # Balance 1 reports the opening balance at the time of the reconciliation.
        pass

    def balance_2(self, *params):
        # TK41
        # Balance 2 reports the amounts that have been paid or cancelled since the last reconciliation.
        pass

    def balance_3(self, *params):
        # TK42
        # Balance 3 reports the closing balance and the sum of the amounts of any reported invoices.
        pass

    def monitored_instructions(self, *params):
        # TK43
        # Reports payments, deductions or credit invoices being monitored.
        pass

lbout_reconciliation_fielddefs = {
    '11': ([(3, 12, 'A'), (13, 18, 'd'), (19, 40, 'T'), (41, 46, 'd'),
            (47, 47, 'T'), (48, 59, '_'), (60, 62, 'T'), (63, 80, '_')],
           LBReconciliationParser.opening_record),
    '29': ([(3, 12, 'A'), (13, 20, 'I'), (21, 80, '_')],
           LBReconciliationParser.end_record),
    '40': ([(3, 15, 'N'), (16, 16, 'T'),
            (17, 29, 'N'), (30, 30, 'T'),
            (31, 43, 'N'), (44, 44, 'T'),
            (45, 57, 'N'), (58, 58, 'T'), (59, 80, '_')],
           LBReconciliationParser.balance_1),
    '41': ([(3, 15, 'N'), (16, 16, 'T'),
            (17, 29, 'N'), (30, 30, 'T'),
            (31, 43, 'N'), (44, 44, '_'),
            (45, 57, 'N'), (58, 58, 'T'), (59, 80, '_')],
           LBReconciliationParser.balance_2),
    '42': ([(3, 15, 'N'), (16, 16, 'T'),
            (17, 29, 'N'), (30, 30, 'T'),
            (31, 43, 'N'), (44, 44, 'T'),
            (45, 57, 'N'), (58, 58, 'T'), (59, 80, '_')],
           LBReconciliationParser.balance_3),
    '43': ([(3, 8, 'd0'), (9, 14, '0'),
            (15, 27, 'N'), (28, 28, 'T'),
            (29, 41, 'N'), (42, 42, 'T'), (43, 44, 'I'), (45, 80, '_')],
           LBReconciliationParser.monitored_instructions),
    }

# Stopped payments report
class LBStoppedPaymentsRecords(object):
    def __init__(self, senders_bankgiro_number, bankgirots_creation_date, product, report_code, currency_code):
        assert unicode(product) == u'LEVERANTÖRSBETALNINGAR'
        assert report_code == '7'
        self.stopped_payments = []
        self.comments = []

    def add_stopped_payment(
            self,
            payees_bankgiro_or_credit_transfer_number,
            ocr_or_invoice_number,
            amount,
            payment_date,
            information_to_sender):
        self.stopped_payments.append(information_to_sender)

    def add_comment(
            self,
            alpha_error_code,
            num_error_code,
            comment):
        assert alpha_error_code == 'MTRV'
        assert num_error_code == '0082'
        self.comments.append(comment)

# filename: BFEP.ULBU3.K0NNNNNN.DYYMMDD.THHMMSS
class LBStoppedPaymentsParser(Parser):
    def __init__(self):
        self.linecount = 0
        self.fielddefs = lbout_stopped_payments_fielddefs
        self.sections = []

    def opening_record(self, *params):
        # TK11
        self.records = LBStoppedPaymentsRecords(*params)
        self.sections.append(self.records)

    def fixed_information_record(self, *params):
        # TK12
        pass

    def header_record(self, *params):
        # TK13
        pass

    def payment_record(self, *params):
        # TK14
        self.records.add_stopped_payment(*params)

    def deduction_record(self, *params):
        # TK15
        self.records.add_stopped_payment(*params)

    def credit_invoice_partial(self, *params):
        # TK16
        self.records.add_stopped_payment(*params)

    def credit_invoice_entire(self, *params):
        # TK17
        self.records.add_stopped_payment(*params)

    def information_record(self, *params):
        # TK25
        pass

    def name_record(self, *params):
        # TK26
        pass

    def address_record(self, *params):
        # TK27
        pass

    def account_number_record(self, *params):
        # TK40
        pass

    def plusgiro_payment_record(self, *params):
        # TK54
        self.records.add_stopped_payment(*params)
        pass

    def plusgiro_information_record(self, *params):
        # TK65
        pass

    def comment_record(self, *params):
        # TK46
        self.records.add_comment(*params)

    def end_record(self, *params):
        # TK29
        pass

lbout_stopped_payments_fielddefs = {
    '11': ([(3, 12, 'A'), (13, 18, 'd'), (19, 40, 'T'), (41, 46, '_'),
            (47, 47, 'T'), (48, 59, '_'), (60, 62, 'T'), (63, 80, '_')],
           LBStoppedPaymentsParser.opening_record),
    # Beginning of LB-in defined records (that were stopped)
    '12': ([(3, 52, 'T'), (53, 58, 'd'), (59, 80, '_')],
           LBStoppedPaymentsParser.fixed_information_record),
    '13': ([(3, 27, 'T'), (28, 39, 'T'), (40, 80, '_')],
           LBStoppedPaymentsParser.header_record),
    '14': ([(3, 12, 'A'), (13, 37, 'T'), (38, 49, 'I'), (50, 55, 'd'),
            (56, 60, '_'), (61, 80, 'T')],
           LBStoppedPaymentsParser.payment_record),
    '15': ([(3, 12, 'A'), (13, 37, 'T'), (38, 49, 'I'), (50, 55, 'd'),
            (56, 60, '_'), (61, 80, 'T')],
           LBStoppedPaymentsParser.deduction_record),
    '16': ([(3, 12, 'A'), (13, 37, 'T'), (38, 49, 'I'), (50, 55, 'd'),
            (56, 60, '_'), (61, 80, 'T')],
           LBStoppedPaymentsParser.credit_invoice_partial),
    '17': ([(3, 12, 'A'), (13, 37, 'T'), (38, 49, 'I'), (50, 55, 'd'),
            (56, 60, '_'), (61, 80, 'T')],
           LBStoppedPaymentsParser.credit_invoice_entire),
    '25': ([(3, 12, 'A'), (13, 62, 'T'), (63, 80, '_')],
           LBStoppedPaymentsParser.information_record),
    '26': ([(3, 6, 'I'), (7, 12, 'I'), (13, 47, 'T'), (48, 80, 'T')],
           LBStoppedPaymentsParser.name_record),
    '27': ([(3, 6, 'I'), (7, 12, 'I'), (13, 47, 'T'), (48, 52, 'T'), (53, 72, 'T'), (73, 80, '_')],
           LBStoppedPaymentsParser.address_record),
    '40': ([(3, 6, 'I'), (7, 12, 'I'), (13, 16, 'I'), (17, 28, 'I'),
            (29, 40, 'T'), (41, 41, 'T'), (42, 80, '_')],
           LBStoppedPaymentsParser.account_number_record),
    '54': ([(3, 12, 'A'), (13, 37, 'T'), (38, 49, 'N'), (50, 55, 'd'),
            (56, 60, '_'), (61, 80, 'T')],
           LBStoppedPaymentsParser.plusgiro_payment_record),
    '65': ([(3, 12, 'A'), (13, 47, 'T'), (48, 80, '_')],
           LBStoppedPaymentsParser.plusgiro_information_record),
    # End of LB-in defined records
    '49': ([(3, 6, 'T'), (7, 10, 'T'), (11, 80, 'T')],
           LBStoppedPaymentsParser.comment_record),
    '29': ([(3, 12, 'A'), (13, 20, 'I'), (21, 80, '_')],
           LBStoppedPaymentsParser.end_record),
    }


class LBRejectedRecords(object):
    def __init__(self, senders_bankgiro_number, bankgirots_creation_date, product, payment_date, report_code, currency_code):
        assert unicode(product) == u'LEVERANTÖRSBETALNINGAR' or unicode(product) == u'LEVERANTORSBETALNINGAR'
        assert report_code == '6'
        self.rejected_transactions = []
        self.rejection_errors = []
        self.toid20 = ''

    def set_faulty_line(self, faulty_line):
        self.faulty_line = faulty_line

    def add_rejected_transaction(
            self,
            faulty_line,
            information_to_sender):
        self.faulty_line = faulty_line
        self.toid20 = information_to_sender
        self.rejected_transactions.append(information_to_sender)

    def add_rejection_comment(
            self,
            alphabetical_error_code,
            numeric_error_code,
            comment):
        if alphabetical_error_code != u'':
            self.rejection_errors.append((self.faulty_line, self.toid20, alphabetical_error_code + str(numeric_error_code), comment))

    def check_and_clean(
            self,
            senders_bankgiro_number,
            number_of_rejected_payment_records):
        #assert number_of_rejected_payment_records == len(self.rejected_transactions)
        #assert number_of_rejected_payment_records == len(self.rejection_errors)
        self.toid20 = ''
        self.faulty_line = ''

class LBRejectedParser(Parser):
    def __init__(self):
        self.linecount = 0
        self.fielddefs = lbout_rejected_fielddefs
        self.sections = []

    def opening_record(self, *params):
        # TK11
        self.records = LBRejectedRecords(*params)
        self.sections.append(self.records)

    def payment_record(self, *params):
        # TK14
        self.records.add_rejected_transaction(*params)

    def payment_record_plusgiro(self, *params):
        # TK54
        self.records.add_rejected_transaction(*params)

    def noop(self, *params):
        # Other TK from LBin with some error
        pass

    def faulty_record(self, *params):
        # Other TK from LBin with some error
        self.records.set_faulty_line(*params)

    def rejection_comment_record(self, *params):
        # TK49
        self.records.add_rejection_comment(*params)

    def end_record(self, *params):
        # TK29
        # Number of erroneous K14, KT15, TK16, TK17, TK54.
        self.records.check_and_clean(*params)

lbout_rejected_fielddefs = {
    '11': ([(3, 12, 'A'), (13, 18, 'd'), (19, 40, 'T'), (41, 46, 'd'),
            (47, 47, 'T'), (60, 62, 'T')],
           LBRejectedParser.opening_record),
    '12': ([(1, 80, 'T')], LBRejectedParser.faulty_record),
    '13': ([(1, 80, 'T')], LBRejectedParser.noop),
    '14': ([(1, 80, 'T'), (61, 80, 'T')], LBRejectedParser.payment_record),
    '15': ([(1, 80, 'T')], LBRejectedParser.faulty_record),
    '16': ([(1, 80, 'T')], LBRejectedParser.faulty_record),
    '17': ([(1, 80, 'T')], LBRejectedParser.faulty_record),
    '40': ([(1, 80, 'T')], LBRejectedParser.faulty_record),
    '54': ([(1, 80, 'T'), (61, 80, 'T')], LBRejectedParser.payment_record_plusgiro),
    '25': ([(1, 80, 'T')], LBRejectedParser.faulty_record),
    '26': ([(1, 80, 'T')], LBRejectedParser.faulty_record),
    '27': ([(1, 80, 'T')], LBRejectedParser.faulty_record),
    '65': ([(1, 80, 'T')], LBRejectedParser.faulty_record),
    'LB': ([(1, 80, 'T')], LBRejectedParser.faulty_record),
    '49': ([(3, 6, 'T'), (7, 10, 'T'), (11, 80, 'T')],
           LBRejectedParser.rejection_comment_record),
    '29': ([(3, 12, 'A'), (13, 20, 'I')],
           LBRejectedParser.end_record),
}


if __name__ == '__main__':
    import sys
    import accounting.db
    import members
    import blm.members
    database = accounting.db.connect()

    from pytransact.commit import CommitContext, CallToi
    with CommitContext(database) as ctx:
        ctx.setMayChange(True)
        pfile = blm.members.PGPaymentFile(data=sys.stdin, fileName='string')
        toid = pfile.id[0]
        pfile.process()
        ctx.runCommit([])

    with CommitContext(database) as ctx:
        for payment in blm.members.PGPaymentFile._query(id=toid).run():
            op = CallToi(toid, 'match', [])
            ctx.runCommit([op])

