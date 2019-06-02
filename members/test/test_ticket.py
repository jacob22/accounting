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

from .. import ticket
import py, os
from reportlab.pdfgen import canvas

class FakeToi(object):
    def __init__(self, **kw):
        self.__dict__ = kw

globaltestorg = FakeToi(
    name=[u'Arrangemangsföreningen för Fuskcon'],
    address=[u'Paradisäppelvägen 13\n313 13 Ankeborg'],
    phone=[u'013-13 13 13'])

class TestTicket(object):
    def test_it(self, tmpdir):
        t = ticket.Ticket(title='zhe_title',
                          options=[('opt1', 'foo'), ('opt2', 'bar')],
                          barcode='barcodedata',
                          qrcode='qrcodedata',
                          org=globaltestorg
                          )
        f = tmpdir.join('foo.pdf')
        fp = f.open('wb')
        c = canvas.Canvas(fp, pagesize=ticket.A4)
        t.drawOn(c, 0, 0)
        c.showPage()
        c.save()
        fp.close()
        os.system('pdftotext %s' % f)
        textf = tmpdir.join('foo.txt').open('rb')
        text =textf.read()

        assert b'zhe_title' in text
        assert b'opt1: foo' in text
        assert b'opt2: bar' in text

    def test_emptyorg(self, tmpdir):
        testorg = FakeToi(
            name=[],
            address=[],
            phone=[])

        t = ticket.Ticket(title='zhe_title',
                          options=[('opt1', 'foo'), ('opt2', 'bar')],
                          barcode='barcodedata',
                          qrcode='qrcodedata',
                          org=testorg
                          )
        f = tmpdir.join('foo.pdf')
        fp = f.open('wb')
        c = canvas.Canvas(fp, pagesize=ticket.A4)
        t.drawOn(c, 0, 0)
        c.showPage()
        c.save()
        fp.close()
        os.system('pdftotext %s' % f)
        textf = tmpdir.join('foo.txt').open('rb')
        text = textf.read()
        assert b'zhe_title' in text
        assert b'opt1: foo' in text
        assert b'opt2: bar' in text

class TestPage(object):
    testorg = FakeToi(
        name=[],
        address=[],
        phone=[])

    testdata = [
        FakeToi(name=['Fusket i natten'],
                options=[('Namn', 'Allan F. Octamac'), (u'Karaktär', u'Räksmörgås')],
                barcode=[u'0256802913644062033722112261163040310146'],
                qrcode=['https://admin.eutaxia.eu/ticket/52fa3bdb5e144c5413b39517/2054512641/52fa3bdb5e144c5413b39515/445671341912272066024349244874082604647348288310/368585379760158096688016088313942883089230885699'],
                org=[testorg]),
        FakeToi(name=[u'Fusket i natten'],
                options=[('Namn', 'Allan G. Octamac'), (u'Karaktär', u'Räksmörgås')],
                barcode=['barcodedata'],
                qrcode=['qrcodedata'],
                org=[testorg]),
        FakeToi(name=['Fusket i natten'],
                options=[('Namn', 'Allan H. Octamac'), (u'Karaktär', u'Räksmörgås')],
                barcode=['barcodedata'],
                qrcode=['qrcodedata'],
                org=[testorg]),
        FakeToi(name=['Fusket i natten'],
                options=[('Namn', 'Allan I. Octamac'), (u'Karaktär', u'Räksmörgås')],
                barcode=['barcodedata'],
                qrcode=['qrcodedata'],
                org=[testorg]),
        ]

    def test_it(self, tmpdir):
        f = tmpdir.join('foo.pdf')
        fp = f.open('wb')

        ticket.generate(fp, self.testdata)
        fp.close()
        os.system('pdftotext %s' % f)
        textf = tmpdir.join('foo.txt').open('rb')
        text = textf.read()
        assert b'F. ' in text
        assert b'G. ' in text
        assert text.count(b'\x0c') == 2
