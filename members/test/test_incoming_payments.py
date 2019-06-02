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

import os
from members.incoming_payments import PGParser, BGParser, LBRequestParser, LBParser, LBRejectedParser, LBStoppedPaymentsParser, LBReconciliationParser
from accounting.bankgiro import decode_toid20
from datetime import date
from decimal import Decimal

here = os.path.dirname(__file__)

class TestParser(object):
    def setup(self):
        self.parser = PGParser()
        fname = os.path.join(here, 'total_in_bas_exempelfil.txt')
        with open(fname, 'rb') as fp:
            self.lines = fp.readlines()

    def test_parser(self):
        for line in self.lines:
            #import pdb;pdb.set_trace()
            self.parser.parse(line)
        r = self.parser.records
        assert len(r.giro_accounts) == 2
        acc1 = r.giro_accounts[0]
        acc2 = r.giro_accounts[1]
        assert len(acc1.transactions) == 6
        assert len(acc2.transactions) == 3
        assert acc1.account == '10181'
        assert acc1.currency == 'SEK'
        assert acc1.transaction_date == date(2011, 10, 24)

        t1 = acc1.transactions[0]
        assert t1.customer_refs[0] == '38952344444'
        assert t1.amount == Decimal('3025.50')
        assert t1.transaction_number == '22222333334444451'
        assert t1.reverse_code == 'No'
        assert t1.messages == [u'FAKTURANR:38952344444',
                               u'INTERN REF:  9780858',
                               u'FAKTURANR:38952345678',
                               u'38952145778ABC']
        assert len(t1.sender_names) == 0
        assert t1.payer_account == '1234567'
        assert t1.payer_account_type == 'Bank account'
        assert t1.payer_organization_number == '9999999999'
        assert t1.payer_names == ['TESTBOLAGET AB']
        assert t1.payer_addresses == ['GATAN 12']
        assert t1.payer_postal_code == '12345'
        assert t1.payer_city == 'TESTSTAD'
        assert t1.payer_country_code == 'SE'

        t2 = acc1.transactions[1]
        assert t2.customer_refs[0] == '0000000000000000000000000'
        assert t2.amount == Decimal('4297.35')
        assert t2.transaction_number == '22222333334444455'
        assert t2.reverse_code == 'No'
        assert t2.messages == [u'TACK FÖR LÅNET']
        assert t2.sender_names == [u'FÖRETAGET AB FRISKVÅRDAVD.']

        t6 = acc1.transactions[5]
        assert t6.customer_refs == ['987654123']
        assert t6.amount == Decimal('-525.50')

        assert sum(t.amount for t in acc1.transactions) == acc1.total
        assert sum(t.amount for t in acc2.transactions) == acc2.total

class TestBGParser(object):
    def test_parsing(self):
        for n in '12345':
            self.parser = BGParser()
            fname = os.path.join(here, 'BgMaxfil%s.txt' % n)
            with open(fname, 'rb') as fp:
                self.lines = fp.readlines()
            self.runtests()
            method = getattr(self, 'check' + n)
            method(self.parser.records)

    def runtests(self):
        for line in self.lines:
            self.parser.parse(line)

    def check1(self, r):
        assert len(r.giro_accounts) == 1
        acc1 = r.giro_accounts[0]
        assert len(acc1.transactions) == 5

    def check2(self, r):
        assert len(r.giro_accounts) == 2
        acc1 = r.giro_accounts[0]
        acc2 = r.giro_accounts[1]
        assert len(acc1.transactions) == 2
        assert acc1.account == u'9912346'
        assert acc1.currency == u'EUR'
        assert acc1.transaction_date == date(2004, 5, 25)
        assert len(acc2.transactions) == 4
        assert acc2.account == u'9912346'
        assert acc2.currency == u'SEK'
        assert acc2.transaction_date == date(2004, 5, 25)

        t1 = acc1.transactions[0]
        assert t1.payer_account == u'3783511'
        assert t1.customer_refs == ['65599']
        assert t1.reference_code == u'OCR'
        assert t1.payment_channel_code == 'LB'
        assert t1.amount == Decimal('700')
        assert t1.image_flag == '0'
        assert t1.messages == [
            u'Här är betalningar från mig till dig med många med', u'delanden']
        assert t1.payer_country_code == u'SE'
        assert t1.payer_organization_number == '5500001234'
        assert t1.reverse_code == 'No'
        assert t1.sender_addresses == [u'Storgatan 2']
        assert t1.sender_city == u'Storåker'
        assert t1.sender_country_code == 'SE'
        assert t1.sender_names == [u'Kalles Plåt AB']
        assert t1.sender_postal_code == '12345'
        assert t1.transaction_number == '000000000007'

    def check3(self, r):
        assert len(r.giro_accounts) == 3
        acc1 = r.giro_accounts[0]
        acc2 = r.giro_accounts[1]
        acc3 = r.giro_accounts[2]
        assert len(acc1.transactions) == 3
        assert len(acc2.transactions) == 4
        assert len(acc3.transactions) == 2


    def check4(self, r):
        assert len(r.giro_accounts) == 4
        acc1 = r.giro_accounts[0]
        acc2 = r.giro_accounts[1]
        acc3 = r.giro_accounts[2]
        acc4 = r.giro_accounts[3]
        assert len(acc1.transactions) == 2
        assert len(acc2.transactions) == 1
        assert len(acc3.transactions) == 4
        assert len(acc4.transactions) == 2


    def check5(self, r):
        assert len(r.giro_accounts) == 1
        acc1 = r.giro_accounts[0]
        assert len(acc1.transactions) == 6


class TestFieldDef(object):
    def test_lbin_fielddefs(self):
        from members.incoming_payments import lbin_fielddefs
        check_fielddef(lbin_fielddefs)

    def test_lbout_fielddefs(self):
        from members.incoming_payments import lbout_fielddefs
        check_fielddef(lbout_fielddefs)

    def test_lbout_reconciliation_fielddefs(self):
        from members.incoming_payments import lbout_reconciliation_fielddefs
        check_fielddef(lbout_reconciliation_fielddefs)

    def test_lbout_stopped_payments_fielddefs(self):
        from members.incoming_payments import lbout_stopped_payments_fielddefs
        check_fielddef(lbout_stopped_payments_fielddefs)

def check_fielddef(fielddef):
    for tk, record in fielddef.items():
        desc, f = record
        stopold = len(tk)
        for field in desc:
            start, stop, fieldtype = field
            assert stopold + 1 == start
            assert start <= stop
            stopold = stop
        assert stop == 80


class TestLBParser(object):
    def test_parseRequest(self):
        self.parser = LBRequestParser()
        fname = os.path.join(here, 'bankgirolink_leverantorsbetalning_lb_exempelfil_sv.txt')
        with open(fname, 'rb') as fp:
            self.lines = fp.readlines()
        for line in self.lines:
            self.parser.parse(line)
        sections = self.parser.sections
        # for r in sections:
        #     print r.sender_bankgiro_number
        #     for p in r.payments:
        #         print p

        # TODO: test

    def test_parseResponse1(self):
        self.parser = LBParser()
        fname = os.path.join(here, 'LB-response-1.txt')
        with open(fname, 'rb') as fp:
            self.lines = fp.readlines()
        for line in self.lines:
            self.parser.parse(line)
        sections = self.parser.sections
        for r in sections:
            t = r.completed_transactions
            assert t == [u'LEKGFNUQPYJUBYH7XVNA', u'LEKGFNUQPYJUBYH7XVPA']
            toids = [decode_toid20(tt) for tt in t]
            assert toids == ['591462b6907e1340e0ffbd5a', '591462b6907e1340e0ffbd5e']


    def test_parseExampleRespons(self):
        # Payments specification with payment types
        # Betalningsspecifikation med Betaltyper
        self.parser = LBParser()
        fname = os.path.join(here, 'leverantorsbetalning_exempelfil_betalningsspecifikation-med-lonedetaljer.txt')
        with open(fname, 'rb') as fp:
            self.lines = fp.readlines()
        for line in self.lines:
            self.parser.parse(line)
        sections = self.parser.sections
        for r in sections:
            t = r.completed_transactions
            assert len(t) == 13
            #print t

    def test_parseExampleRejected(self):
        # Payment instructions containing errors and therefore not processed.
        # Avvisade betalningar
        self.parser = LBRejectedParser()
        fname = os.path.join(here, 'leverantorsbetalning_exempelfil_avvisade_sv.txt')
        with open(fname, 'rb') as fp:
            self.lines = fp.readlines()
        for line in self.lines:
            self.parser.parse(line)
        sections = self.parser.sections
        for r in sections:
            t = r.rejected_transactions
            e = r.rejection_errors
            assert t == [u'', u'VERIF 20', u'VERIF 29', u'']


    def test_parseExampleStoppedPayments(self):
        # Stopped payments report
        # Bankgirot did not provide an example file for this report so this one is home baked/faked.
        self.parser = LBStoppedPaymentsParser()
        fname = os.path.join(here, 'leverantorsbetalning_stoppade.txt')
        with open(fname, 'rb') as fp:
            self.lines = fp.readlines()
        for line in self.lines:
            self.parser.parse(line)
        sections = self.parser.sections
        for r in sections:
            s = r.stopped_payments
            assert s == [u'VERIF 12', u'VERIF 13', u'VERIF 14', u'VERIF 16', u'VERIF 19', u'VERIF 32', u'VERIF 25']

    def test_parseExampleReconciliation(self):
        # Reconciliation report
        # Avstämningsrapport
        self.parser = LBReconciliationParser()
        fname = os.path.join(here, 'leverantorsbetalning_exempelfil_betalningsbevakning_sv.txt')
        with open(fname, 'rb') as fp:
            self.lines = fp.readlines()
        for line in self.lines:
            self.parser.parse(line)
        sections = self.parser.sections
        for r in sections:
            pass
