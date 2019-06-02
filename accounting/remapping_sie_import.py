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

from .sie_import import Parser

def swap(n, mapping, *params):
    params = list(params)
    params[n] = mapping[params[n]]
    return params

class RemappingParser(Parser):
    def __init__(self, acc, mapping):
        Parser.__init__(self, acc)
        self.records = self.records.copy()
        for key, value in list(mapping.items()):
            mapping[key.encode('ascii')] = value
        self.mapping = mapping
        self.records[b'#KONTO'  ] = ('T T', RemappingParser.account)
        self.records[b'#KTYP'   ] = ('T T', RemappingParser.account_type)
        self.records[b'#TRANS'  ] = ('T* L N [D] [T] [N] [T]', RemappingParser.transaction)
        self.records[b'#RTRANS' ] = ('T* L N [D] [T] [N] [T]', RemappingParser.added_transaction)
        self.records[b'#BTRANS' ] = ('T* L N [D] [T] [N] [T]', RemappingParser.deleted_transaction)
        self.records[b'#SRU'    ] = ('T T', RemappingParser.sru)
        self.records[b'#ENHET'  ] = ('T T', RemappingParser.unit)
        self.records[b'#IB'     ] = ('I T N [N]', RemappingParser.opening_balance)
        self.records[b'#UB'     ] = ('I T N [N]', RemappingParser.closing_balance)
        self.records[b'#RES'    ] = ('I T N [N]', RemappingParser.turnover)
        self.records[b'#OIB'    ] = ('I T* L N [N]', RemappingParser.object_opening_balance)
        self.records[b'#OUB'    ] = ('I T* L N [N]', RemappingParser.object_closing_balance)
        self.records[b'#PBUDGET'] = ('I T T L N [N]', RemappingParser.period_budget)
        self.records[b'#PSALDO' ] = ('I T T L N [N]', RemappingParser.period_balance)

    def account(self, *params):
        if params[0] in self.mapping:
            Parser.account(self, *swap(0, self.mapping, *params))

    def account_type(self, *params):
        if params[0] in self.mapping:
            Parser.account_type(self, *swap(0, self.mapping, *params))

    def transaction(self, *params):
        Parser.transaction(self, *swap(0, self.mapping, *params))

    def added_transaction(self, *params):
        Parser.added_transaction(self, *swap(0, self.mapping, *params))

    def deleted_transaction(self, *params):
        Parser.deleted_transaction(self, *swap(0, self.mapping, *params))

    def sru(self, *params):
        if params[0] in self.mapping:
            Parser.sru(self, *swap(0, self.mapping, *params))

    def unit(self, *params):
        if params[0] in self.mapping:
            Parser.unit(self, *swap(0, self.mapping, *params))

    def opening_balance(self, *params):
        if params[1] in self.mapping:
            Parser.opening_balance(self, *swap(1, self.mapping, *params))

    def closing_balance(self, *params):
        if params[1] in self.mapping:
            Parser.closing_balance(self, *swap(1, self.mapping, *params))

    def object_opening_balance(self, *params):
        if params[1] in self.mapping:
            Parser.object_opening_balance(self, *swap(1, self.mapping, *params))

    def object_closing_balance(self, *params):
        if params[1] in self.mapping:
            Parser.object_closing_balance(self, *swap(1, self.mapping, *params))

    def turnover(self, *params):
        if params[1] in self.mapping:
            Parser.turnover(self, *swap(1, self.mapping, *params))

    def period_budget(self, *params):
        if params[2] in self.mapping:
            Parser.period_budget(self, *swap(2, self.mapping, *params))

    def period_balance(self, *params):
        if params[2] in self.mapping:
            Parser.period_balance(self, *swap(2, self.mapping, *params))


def build_mapping(fp):
    import re
    pattern = re.compile(r'^(\d\d\d\d)\D+(\d\d\d\d)')
    mapping = {}
    for line in fp.readlines():
        result = pattern.match(line)
        orig = result.group(2)
        next = result.group(1)
        mapping[orig] = next
    return mapping
