#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

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
if sys.version_info < (3,0,0):
    PYT3 = False
else:
    PYT3 = True
import copy

import os
from datetime import datetime
from decimal import Decimal

from .crc import Crc
import logging
from accounting import db
from pytransact import blm, commit
from blm import fundamental, accounting

try:
    unicode
except NameError:
    unicode=str

class SIEImporter(object):
    '''
    This importer is designed for importing the SIE4 Export format.
    It should be easy to handle other SIE import situations by
    using a slightly different importer and by inheriting the parser
    and replacing bits as needed.
    '''

    ignoretransactions = True

    def __init__(self, org=[], mapping=None):
        # All the attributes are saved in codepage 437 encoding, which is
        # the only encoding used in SIE. This is because checksums are
        # calculated on the individual data fields in the file using
        # the original encoding. We have to calculate checksums before
        # we convert the data.
        self.filename = None
        self.flag = None
        self.format = None
        self.sietype = None
        self.program = None
        self.org = list(org)
        self.mapping = mapping
        logging.basicConfig(format='%(asctime)s %(message)s',
                            level=logging.INFO)

    def parseFile(self, filename):
        with open(filename, 'rb') as fp:
            self.parse(fp)

    def parse(self, stream, filename=u'<string>'):
        assert isinstance(filename, unicode)
        logging.info(u'Importing {}'.format(filename))
        lines = stream.readlines()

        if PYT3:
            # lines need to be bytes. Lets encode if needed.
            if isinstance(lines[0], str):
                for i in range(len(lines)):
                    lines[i]= lines[i].encode()

        # The file has to end with a linefeed or things will break
        if lines[-1][-1] != b'\n':
           lines[-1] = lines[-1] + b'\n'

        CRCCalculatingParser(lines)  # raises exception on checksum mismatch

        self.accounting = accounting.Accounting(org=self.org, imported=[True])
        self.accounting.ignoretransactions = self.ignoretransactions
        if not self.mapping:
            p = Parser(self.accounting)
        else:
            from . import remapping_sie_import
            p = remapping_sie_import.RemappingParser(self.accounting, self.mapping)
        for n, line in enumerate(lines[1:], 2):
            try:
                p.parse(line, n)
            except DoneException:
                pass
            except Exception:
                print('Error on line %d' % n)
                raise
        # If self.flag is None, we have a format error
        # If self.flag is True, whe have already read the file - skip
        if p.parse_warnings:
            logging.warn(u'Imported {} with warnings:'.format(filename))
        for warn in p.parse_warnings:
            logging.warn(warn)
        logging.info(u'Import complete {}'.format(filename))



class DoneException(Exception):
    pass

class MultipleFlagException(Exception):
    pass

class ChecksumError(Exception):
    pass

class UnsupportedSIEVersion(ValueError):
    pass

class ParseError(ValueError):
    pass

whitespace = b' \t\f'
whitespace_or_newline = whitespace + b'\n\r'
whitespace_or_newline_or_startcurly = whitespace_or_newline + b'{'
label_chars = b'#ABCDEFGHIJKLMNOPQRSTUVWXYZ'
digits = b'1234567890'

class BaseParser(object):

    def getc(self, offset=0):
        try:
            s = self.s[self.pos + offset]
            try:
                s = ord(s)
            except TypeError:
                pass
            if s < 32 or s == 127:
                if s not in [9, 10, 13]:
                    raise ValueError(s)
            try:
                return s.to_bytes(1, sys.byteorder)
            except AttributeError:
                return chr(s)
        except IndexError:
            raise DoneException
        # the old py2 only code
        # try:
        #     s = self.s[self.pos + offset]
        #     if ord(s) < 32 or ord(s) == 127:
        #         if ord(s) not in [9, 10, 13]:
        #             raise ValueError(ord(s))
        #     return s
        # except IndexError:
        #     raise DoneException

    def consume_label(self):
        p = self.pos
        try:
            while self.getc() in label_chars:
                self.pos += 1
        except DoneException:
            if self.pos == p:
                raise
        end = self.pos
        self.consume_whitespace()
        return self.s[p:end]

    def consume_whitespace(self):
        while 1:
            c = self.getc()
            if c in whitespace:
                self.pos += 1
            else:
                return c

    def consume_string(self):
        if self.getc() == b'"':
            self.pos += 1
            p = self.pos
            while True:
                if self.getc() == b'\\':
                    if self.getc(+1) == b'"':
                        self.pos += 1
                elif self.getc() == b'"':
                    break
                self.pos += 1
            end = self.pos
            self.pos += 1
        else:
            p = self.pos
            while self.getc() not in whitespace_or_newline:
                self.pos += 1
            end = self.pos

        self.consume_whitespace()
        s = self.s[p:end]
        ss = s.split(b'\\"')
        s = b'"'.join(sss for sss in ss)
        return s

    def consume_numeric(self):
        # In "#TRANS" records the account number may be immediately followed
        # by a "{"
        if self.getc() == b'"':
            self.pos += 1
            p = self.pos
            while self.getc() != b'"':
                if self.getc() not in digits:
                    raise ValueError(self.getc())
                self.pos += 1
            end = self.pos
            self.pos += 1
        else:
            p = self.pos
            while self.getc() not in whitespace_or_newline_or_startcurly:
                self.pos += 1
            end = self.pos

        self.consume_whitespace()
        return self.s[p:end]

    def consume_object_list(self):
        if self.getc() != b'{':
            raise ValueError(self.getc())
        self.pos += 1
        self.consume_whitespace()

        objects = []
        while True:
            if self.getc() == b'}':
                self.pos += 1
                break
            if self.getc() == b'"':
                self.pos += 1
                p = self.pos
                while True:
                    if self.getc() == b'\\':
                        if self.getc(+1) == b'"':
                            self.pos += 1
                    elif self.getc() == b'"':
                        break
                    self.pos += 1
                s = self.s[p:self.pos]
                s = b'"'.join(s.split(b'\\"'))
                objects.append(s)
                self.pos += 1
                self.consume_whitespace()
            else:
                p = self.pos
                while True:
                    if self.getc() == b'}':
                        if self.getc(+1) != b'}':
                            break
                    elif self.getc() in whitespace:
                        break
                    self.pos += 1
                objects.append(self.s[p:self.pos])
                self.consume_whitespace()
        self.consume_whitespace()
        if len(objects) % 2 != 0:
            raise ValueError(objects)
        return objects

    def read_record(self, format):

        param_types = format.split(' ')
        params = []
        for param in param_types:
            if param == 'T':
                params.append(self.consume_string())
            elif param == 'T*':
                params.append(self.consume_numeric())
            elif param == 'N':
                s = self.consume_string()
                if s:
                    try:
                        s = s.decode('ascii')
                    except AttributeError:
                        pass
                    params.append(Decimal(s))
                else:
                    params.append(Decimal(0))
            elif param == 'D':
                s = self.consume_string()
                try:
                    s = s.decode('ascii')
                except AttributeError:
                    pass
                params.append('%s-%s-%s' % (s[:4], s[4:6], s[6:]))
            elif param == 'I':
                s = self.consume_string()
                if s:
                    params.append(int(s))
                else:
                    params.append(-1)
            elif param == 'L':
                params.append(self.consume_object_list())
            elif param == '[T]':
                if self.getc() not in whitespace_or_newline:
                    params.append(self.consume_string())
            elif param == '[N]':
                if self.getc() not in whitespace_or_newline:
                    s = self.consume_string()
                    try:
                        s = s.decode('ascii')
                    except AttributeError:
                        pass
                    if s:
                        params.append(Decimal(s))
                    else:
                        params.append(Decimal(0))
            elif param == '[D]':
                if self.getc() not in whitespace_or_newline:
                    s = self.consume_string()
                    if not s:
                        params.append(None)
                    else:
                        try:
                            s = s.decode('ascii')
                        except AttributeError:
                            pass
                        params.append('%s-%s-%s' % (s[:4], s[4:6], s[6:]))
        return params

class CRCCalculatingParser(BaseParser):
    def __init__(self, lines):
        self.lines = lines
        self.s = self.lines[0]
        self.pos = 0
        BPcl=BaseParser.consume_label(self)
        if BPcl == b'#FLAGGA':
            flag = BaseParser.consume_string(self)
            if flag != b'0':
                raise ValueError
        else:
            # File not to be read
            raise ValueError

        if not self.lines[1].startswith(b'#KSUMMA'):
            self.result = True # No checksum. Assume file is ok
            return

        self.crc = Crc()
        for line in lines[2:-1]:
            self.parse(line)

        crc = self.crc.finalize()
        self.s = self.lines[-1]
        self.pos = 0
        BPcl=BaseParser.consume_label(self)
        if BPcl == b'#KSUMMA':
            checksum = BaseParser.consume_string(self)
            if crc == int(checksum):
                self.result = True
                return
        raise ValueError

    def parse(self, line):
        self.s = line
        self.pos = 0
        c = self.consume_whitespace()
        if c == b'#':
            label = self.consume_label()
            fmt = records[label][0]
            self.read_record(fmt)

    def get_crc32(self):
        return self.crc.finalize()

    def consume_label(self):
        s = BaseParser.consume_label(self)
        self.crc.crc(s)
        return s

    def consume_string(self):
        s = BaseParser.consume_string(self)
        self.crc.crc(s)
        return s

    def consume_numeric(self):
        s = BaseParser.consume_numeric(self)
        self.crc.crc(s)
        return s

    def consume_object_list(self):
        objects = BaseParser.consume_object_list(self)
        for o in objects:
            self.crc.crc(o)
        return objects

class Codepage437TranslatingParser(BaseParser):
    def consume_string(self):
        s = BaseParser.consume_string(self)
        return s.decode('cp437')

    def consume_numeric(self):
        s = BaseParser.consume_numeric(self)
        return s.decode('cp437')

    def consume_object_list(self):
        objects = BaseParser.consume_object_list(self)
        return [o.decode('cp437') for o in objects]

class Parser(Codepage437TranslatingParser):
    def __init__(self, acc):
        self.acc = acc
        self.added_trans = False
        self._account_cache = {}
        self._series_cache = {}
        self._object_cache = {}
        self.parse_warnings = []
        self.records = records # Makes Parser inheritable
        self.lineno = -1

    def parse(self, line, lineno=-1):
        self.s = line
        self.lineno = lineno
        self.pos = 0
        c = self.consume_whitespace()
        if c == b'#':
            label = self.consume_label()
            format = self.records[label][0]
            method = self.records[label][1]
            params = self.read_record(format)
            method(self, *params)

    def get_account(self, number):
        try:
            return self._account_cache[number]
        except KeyError:
            try:
                account, = accounting.Account._query(number=number,
                                                     accounting=self.acc).run()
            except ValueError:
                self.parse_warnings.append(
                    u'Referenced undefined account %s at line %s' %
                    (number, self.lineno))
                account = accounting.Account(accounting=self.acc, number=number)
            self._account_cache[number] = account
            return account

    # The following methods all deal with turning a single line
    # in the SIE file into internal objects
    def gen(self, *params):
        if len(params) < 2:
            logging.info(u'Genererad {}'.format(params[0]))
        else:
            logging.info(u'Genererad {} av {}'.format(params[0], params[1]))

    def program(self, *params):
        logging.info(u'Program: {}, version {}'.format(*params))

    def unit(self, *params):
        self.get_account(params[0]).unit = [params[1]]

    def format(self, *params):
        if params[0] != 'PC8':
            raise ValueError(params[0])
        self.acc.format = params[0]

    def account_layout(self, *params):
        self.acc.layout = [params[0]]

    def currency(self, *params):
        self.acc.currency = params[0]

    def sie_type(self, sietype):
        if sietype != '4':
            raise UnsupportedSIEVersion(sietype)

    def address(self, *params):
        params = [[p] if p else [] for p in params]
        (self.acc.contact,
         self.acc.mail_address,
         self.acc.zip_city,
         self.acc.telephone) = params

    def orgnum(self, *params):
        self.acc.orgnum = params[0]
        if len(params) > 1:
            self.acc.purchase_number = params[1]
        if len(params) > 2:
            self.acc.site = params[2] # Should be unused with current practice

    def orgname(self, *params):
        self.acc.orgname = params[0]

    def orgtype(self, *params):
        self.acc.orgtype = params[0]

    def internal_number(self, *params):
        logging.info(u'Ignorerade exporterande systems interna id {}.'.format(
                params[0]))

    def extent(self, *params):
        logging.info(u'Bokföringen omfattar poster t.o.m. {}.'.format(
                params[0]))

    def industry_code(self, *params):
        self.acc.industry_code = params[0]

    def taxation_year(self, *params):
        self.acc.taxation_year = params[0]

    def accounting_period(self, *params):
        year = params[0]
        if year == 0:
            self.acc.start = [params[1]]
            self.acc.end = [params[2]]

        years = self.acc.years.value
        years[str(params[0])] = list(params[1:3])
        self.acc.years = years

    def comment(self, text, *params):
        logging.info(u'Kommentar: {}'.format(text))

    def dim(self, *params):
        try:
            dimension, = accounting.Dimension._query(number=params[0],
                                                     accounting=self.acc).run()
        except ValueError:
            dimension = accounting.Dimension(
                number=[params[0]], name=[params[1]], accounting=[self.acc])
        else:
            dimension.name = [params[1]]
            dimension.subdim_of = []

    def sub_dim(self, *params):
        try:
            parent, = accounting.Dimension._query(accounting=self.acc,
                                                  number=params[2]).run()
        except ValueError:
            self.parse_warnings.append(
                u'Referenced undefined dimension %s at line %s' %
                (params[2], self.lineno))
            parent = accounting.Dimension(accounting=[self.acc],
                                          name=[u'Överdimension till %s' % params[1]],
                                          number=[params[2]])

        try:
            dimension, = accounting.Dimension._query(number=params[0],
                                                     accounting=self.acc).run()
        except ValueError:
            dimension = accounting.Dimension(
                number=[params[0]], name=[params[1]], accounting=[self.acc],
                subdim_of=[parent])
        else:
            dimension.name = [params[1]]
            dimension.subdim_of = [parent]

        return dimension

    def accounting_object(self, *params):
        try:
            dimension, = accounting.Dimension._query(accounting=self.acc,
                                                     number=params[0]).run()
        except ValueError:
            self.parse_warnings.append(
                u'Referenced undefined dimension %s at line %s' %
                (params[0], self.lineno))
            dimension = accounting.Dimension(accounting=[self.acc],
                                             name=['Autogenererad'],
                                             number=[params[0]])

        return accounting.AccountingObject(number=[params[1]], name=[params[2]],
                                    dimension=[dimension])

    def get_accounting_object(self, dimension_no, number):
        try:
            return self._object_cache[(dimension_no, number)]
        except KeyError:
            try:
                dimension, = accounting.Dimension._query(accounting=self.acc,
                                                 number=dimension_no).run()
            except ValueError:
                self.parse_warnings.append(
                    u'Referenced undefined dimension %s at line %s' %
                    (dimension_no, self.lineno))
                dimension = accounting.Dimension(
                    name=['Autogenererad'],
                    number=[dimension_no], accounting=[self.acc])
            try:
                acct_obj, = accounting.AccountingObject._query(
                    dimension = dimension, number = number).run()
            except ValueError:
                self.parse_warnings.append(
                    u'Referenced undefined object %s at line %s' %
                    (number, self.lineno))
                acct_obj = accounting.AccountingObject(
                    name=['Autogenererad'],
                    dimension = [dimension], number = [number])

            self._object_cache[(dimension_no, number)] = acct_obj
            return acct_obj

    def account(self, number, name):
        if number in self._account_cache:
            raise ValueError('Account already exists: %s' % name)
        account = accounting.Account(accounting=[self.acc], number=[number],
                                     name=[name])
        self._account_cache[number] = account
        return account

    def account_type(self, *params):
        account = self.get_account(params[0])
        account.type = [params[1]]

    def sru(self, *params):
        self.get_account(params[0]).sru = [params[1]]

    def get_balance(self, account, year):
        if year == 0:
            return account
        params = {'account': [account], 'year': [year]}
        try:
            balance = accounting.AccountBalance._query(**params).run()[0]
        except IndexError:
            balance = accounting.AccountBalance(**params)
        return balance

    def opening_balance(self, year, account, opening_balance, *params):
        account = self.get_account(account)
        balance = self.get_balance(account, year)
        balance.opening_balance = [opening_balance]
        balance.balance = [opening_balance]
        if params:
            balance.opening_quantity = params[:1]
            balance.balance_quantity = params[:1]

    def closing_balance(self, *params):
        account = self.get_account(params[1])
        balance = self.get_balance(account, params[0])
        balance.balance = [params[2]]
        if len(params) > 3:
            balance.balance_quantity = [params[3]]

    def turnover(self, year, account, turnover, turnover_quantity=None):
        account = self.get_account(account)
        balance = self.get_balance(account, year)
        balance.balance = [turnover]
        if turnover_quantity is not None:
            balance.balance_quantity = [turnover_quantity]

    def get_object_balance(self, year, accountno, dim_accobj, period=''):
        dimension, accounting_object=dim_accobj
        account = self.get_account(accountno)
        balance = self.get_balance(account, year)

        accounting_object = self.get_accounting_object(dimension,
                                                       accounting_object)

        obj_balance = accounting.ObjectBalanceBudget._query(
            accounting_object = accounting_object,
            account_balance = balance,
            period = period).run()
        if obj_balance:
            return obj_balance[0]

        else:
            return accounting.ObjectBalanceBudget(
                accounting_object=[accounting_object],
                period=[period], account_balance=[balance])

    def object_opening_balance(self, *params):
        obj_balance = self.get_object_balance(params[0], params[1], params[2])
        obj_balance.opening_balance = [params[3]]
        obj_balance.balance = [params[3]]
        if len(params) > 4:
            obj_balance.opening_quantity = [params[4]]
            obj_balance.balance_quantity = [params[4]]

    def object_closing_balance(self, *params):
        obj_balance = self.get_object_balance(params[0], params[1], params[2])
        obj_balance.balance = [params[3]]
        if len(params) > 4:
            obj_balance.balance_quantity = [params[4]]

    def get_balance_budget(self, *params):
        account = self.get_account(params[2])
        balance = self.get_balance(account, params[0])

        period = params[1]

        balance_budget = accounting.BalanceBudget._query(period = period,
                                                         account_balance = balance).run()
        if balance_budget:
            return balance_budget[0]
        else:
            return accounting.BalanceBudget(period=[period],
                                            account_balance=[balance])

    def period_budget(self, *params):
        balance = None
        if len(params[3]) == 0:
            # Regular account turnover
            balance = self.get_balance_budget(*params)
        elif len(params[3]) == 2:
            # Object turnover
            balance = self.get_object_balance(params[0], params[2], params[3],
                                              period=params[1])
        else:
            logging.error(u'Felaktigt format i objektlistan.')

        if balance:
            balance.budget = [params[4]]
            if len(params) > 5:
                balance.budget_quantity = [params[5]]

    def period_balance(self, *params):
        balance = None
        if len(params[3]) == 0:
            # Regular account turnover
            balance = self.get_balance_budget(*params)
        elif len(params[3]) == 2:
            # Object turnover
            balance = self.get_object_balance(params[0], params[2], params[3],
                                              period=params[1])
        else:
            logging.error(u'Felaktigt format i objektlistan.')

        if balance:
            balance.balance = [params[4]]
            if len(params) > 5:
                balance.balance_quantity = [params[5]]

    def series(self, name, description=None):
        try:
            return self._series_cache[name]
        except KeyError:
            try:
                series, = blm.accounting.VerificationSeries._query(
                    accounting=self.acc, name=name).run()
            except ValueError:
                series = blm.accounting.VerificationSeries(
                    accounting=[self.acc], name=[name])
            if description:
                series(description=[description])
            self._series_cache[name] = series
            return series

    def verification(self, *params):
        series = self.series(params[0])
        v = accounting.Verification(series=[series], number=[params[1]],
                                    transaction_date=[params[2]],
                                    accounting=[self.acc])
        self.current_verification = v
        if len(params) > 3:
            v.text = [params[3]]
        if len(params) > 4:
            if params[4]:
                v.registration_date = [params[4]]
        if len(params) > 5:
            if params[5]:
                v.signature = [params[5]]

    def trans(self, transtype, *params):
        # Add transaction to current verification
        v = self.current_verification
        account = self.get_account(params[0])
        transData = dict(version=v.version,
                         transtype=[transtype],
                         verification=[v],
                         account=[account],
                         amount=[params[2]])
        if len(params) > 3:
            if params[3]:
                transData['transaction_date'] = [params[3]]
        if len(params) > 4:
            transData['text'] = [params[4]]
        if len(params) > 5:
            if params[5]:
                transData['quantity'] = [params[5]]
        if len(params) > 6:
            if params[6]:
                transData['signature'] = [params[6]]

        while params[1]:
            dimension_number = params[1].pop(0)
            object_number = params[1].pop(0)
            accounting_object = self.get_accounting_object(dimension_number,
                                                           object_number)
            transData.setdefault('accounting_objects', []).append(accounting_object)
        #print(transData)
        t = accounting.Transaction(**transData)

        # while params[1]:
        #     dimension_number = params[1].pop(0)
        #     object_number = params[1].pop(0)
        #     dimension, = accounting.Dimension._query(number=dimension_number,
        #                                              accounting=self.acc).run()
        #     accounting_object, = accounting.AccountingObject._query(
        #         dimension=dimension, number=object_number).run()
        #     t.accounting_objects = t.accounting_objects + [accounting_object]

    def transaction(self, *params):
        if not self.added_trans:
            self.trans('normal', *params)

        self.added_trans = False

    def added_transaction(self, *params):
        self.added_trans = True
        self.trans('added', *params)

    def deleted_transaction(self, *params):
        self.trans('deleted', *params)

    def no_op(self, *params):
        pass

    def closed(self):
        # do not invoke .close(), as that one has logic that will modify data
        self.acc.closed = [True]

    def vatcode(self, account, vatcode, *params):
        account = self.get_account(account)
        account.vatCode = [vatcode]
        account.updateVatPercentage()


class AppendingParser(Parser):
    def __init__(self,acc):
        super(AppendingParser,self).__init__(acc)
        self.records = copy.deepcopy(records)
        self.records[b'#KONTO'] = ('T T', AppendingParser.account)
        self.records[b'#VER'] = ('T I D [T] [D] [T]', AppendingParser.verification)
        self.records[b'SERIE'] = ('T [T]', AppendingParser.series)

    def account(self, number, name):
        pass

    def verification(self, *params):
        from blm.accounting import next_verification_data as nvd


        series = self.series(params[0])
        #import pdb; pdb.set_trace()
        #series = nvd(series)

        #print(params)
        v = accounting.Verification(series=[series], number=[params[1]],
                                    transaction_date=[params[2]],
                                    accounting=[self.acc])
        self.current_verification = v

        if len(params) > 3:
            v.text = [params[3]]
        if len(params) > 4:
            if params[4]:
                v.registration_date = [params[4]]
        if len(params) > 5:
            if params[5]:
                v.signature = [params[5]]

    def series(self, name, description=None):
        try:
            return self._series_cache[name]
        except KeyError:
            try:
                return self._series_cache['A']
            except KeyError:
                try:
                    series, = blm.accounting.VerificationSeries._query(
                        accounting=self.acc, name='A').run()
                    return  series

                except ValueError:
                    pass

        # if description:
        #     series(description=[description])
        #
        # # if series:
        #
        # print("\nkoll av series:\n")
        # print(series)
        # print('slut koll av series')
        # # import pdb;pdb.set_trace()
        #
        # self._series_cache[name] = series
        # return series


# T = Text
# N = Decimal number
# I = Integer
# D = Date
# L = Object list
# T* = Text in front of object list
# [] = Optional
records = {
    b'#GEN'     : ('D [T]', Parser.gen),
    b'#PROGRAM' : ('T T', Parser.program),
    b'#ENHET'   : ('T T', Parser.unit),
    b'#FORMAT'  : ('T', Parser.format),
    b'#KPTYP'   : ('T', Parser.account_layout),
    b'#ADRESS'  : ('T T T T', Parser.address),
    b'#ORGNR'   : ('T [T] [T]', Parser.orgnum),
    b'#FNAMN'   : ('T', Parser.orgname),
    b'#FNR'     : ('T', Parser.internal_number),
    b'#FTYP'    : ('T', Parser.orgtype),
    b'#BKOD'    : ('T', Parser.industry_code),
    b'#OMFATTN' : ('D', Parser.extent),
    b'#RAR'     : ('I D D', Parser.accounting_period),
    b'#TAXAR'   : ('T', Parser.taxation_year),
    b'#SIETYP'  : ('T', Parser.sie_type),
    b'#VALUTA'  : ('T', Parser.currency),
    b'#PROSA'   : ('T', Parser.comment),
    b'#DIM'     : ('T T', Parser.dim),
    b'#UNDERDIM': ('T T T', Parser.sub_dim),
    b'#OBJEKT'  : ('T T T', Parser.accounting_object),
    b'#KONTO'   : ('T T', Parser.account),
    b'#KTYP'    : ('T T', Parser.account_type),
    b'#SRU'     : ('T T', Parser.sru),
    b'#IB'      : ('I T N [N]', Parser.opening_balance),
    b'#UB'      : ('I T N [N]', Parser.closing_balance),
    b'#RES'     : ('I T N [N]', Parser.turnover),
    b'#OIB'     : ('I T* L N [N]', Parser.object_opening_balance),
    b'#OUB'     : ('I T* L N [N]', Parser.object_closing_balance),
    b'#PBUDGET' : ('I T T L N [N]', Parser.period_budget),
    b'#PSALDO'  : ('I T T L N [N]', Parser.period_balance),
    b'#VER'     : ('T I D [T] [D] [T]', Parser.verification),
    b'#TRANS'   : ('T* L N [D] [T] [N] [T]', Parser.transaction),
    b'#RTRANS'  : ('T* L N [D] [T] [N] [T]', Parser.added_transaction),
    b'#BTRANS'  : ('T* L N [D] [T] [N] [T]', Parser.deleted_transaction),
    b'#KSUMMA'  : ('[T]', Parser.no_op),

    # Non standard Open End extensions
    b'#AVSLUTAT': ('', Parser.closed),  # the accounting year is closed
    b'#SERIE'   : ('T [T]', Parser.series),
    b'#MOMSKOD' : ('T T', Parser.vatcode),
    }

if __name__ == '__main__':
    import bson, locale, sys
    locale.setlocale(locale.LC_CTYPE, '')
    enc = locale.getpreferredencoding()
    database = db.connect()
    for fname in sys.argv[1:]:
        fname = fname.decode(enc)
        sys.stdout.write('Importing %s ' % fname)
        sys.stdout.flush()
        interested = bson.objectid.ObjectId()
        with commit.CommitContext(database) as ctx:
            ctx.setMayChange(True)
            importer = SIEImporter()
            importer.parseFile(fname)
            accountingId = importer.accounting.id[0]
            ctx.runCommit([], interested=interested)
        result, errors = commit.wait_for_commit(database, interested=interested)
        assert not errors
        sys.stdout.write('done, created: %s\n' % accountingId)
