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

import decimal, json
import py
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO
import members.invoice
from members.invoice import *
import accounting
from pytransact.testsupport import BLMTests
import blm.accounting, blm.members

def test(tmpdir):
    class FakeToi(object):
        def __init__(self, **kw):
            self.__dict__ = kw

    inv = FakeToi(
        kind = ['purchase'],
        org = [FakeToi(
                name=[u'Arrangemangsföreningen Fuskcon'],
                #name=[u'Näsets Paddlarklubb'],
                address=[u'Paradisäppelvägen 6\n891 00 Ankeborg'],
                phone=[u'0941-12 34 56']
                )],
        date = [1234567890],
        items = [
            FakeToi(
                name = [u'Foo'],
                price = [decimal.Decimal(3)],
                quantity = [99],
                total = [decimal.Decimal(298)],
                options = [],
                optionsWithValues = [],
                ),
            FakeToi(
                product = [],
                name = [u'Blomvas'],
                price = [decimal.Decimal(42)],
                quantity = [2],
                total = [decimal.Decimal(84)],
                accountingRules = [],
                options = [
                    u'Grön'
                    ],
                optionsWithValues = [
                    [u'Färg', u'Grön']
                    ],

                ),
            FakeToi(
                product = [],
                name = [u'Vas'],
                price = [decimal.Decimal(249.5)],
                quantity = [10],
                total = [decimal.Decimal(2495)],
                accountingRules = [],
                options = [
                    u'Lila',
                    u'Grön',
                    u'50 år',
                    ],
                optionsWithValues = [
                    [u'Färg', u'Lila'],
                    [u'Lock', u'Grön'],
                    [u'Inskription', u'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Cras lacinia quam nec nunc pulvinar lacinia. Nulla ut congue eros, in convallis urna.'],
                    ],

                )
            ],
        total = [decimal.Decimal(42)],
        ocr = [u'12345'],
        buyerName = [u'Allan F. Octamac'],
        buyerAddress = [u'Paradisäppelvägen 13\n313 13 Ankeborg'],
        buyerPhone = [u'013-13 13 13'],
        buyerEmail = [u'fop@dd.chalmers.se'],
        extraText=['''<font size=10><b>Betalningsvillkor</b><br/></font>
Fakturan skall vara betald innan hyresdagen. Vid betalning senare än 10 dagar innan hyresdagen skall kvitto på erlagd betalning kunna förevisas för uthyrande personal.<br/><br/>

Faktura ställd till skolor tillhörande Göteborgs skolförvaltning eller till annan organisation med speciell överenskommelse med Näsets Paddlarklubb skall vara betald inom 30 dagar från fakturadatum.<br/><br/>

Bokning är bindande. Kreditering av fakturerat belopp sker endast om faktureringen varit felaktig, om hyresmannen med läkarintyg påvisar att han på grund av sjukdom varit förhindrad att utnyttja sin beställning, eller om uthyraren bedömer att väderläget inte medger säker färd. Ändring av bokning kan i undantagsfall ske, om detta inte är till olägenhet för uthyraren.<br/><br/>

Näsets Paddlarklubb är en allmännyttig ideell idrottsförening. Vår uthyrningsverksamhet är inte momspliktig.'''],
        # For kind == 'invoice'
        expiryDate = [],
        buyerOrg = [],
        )

    fp = tmpdir.join('bar.pdf').open('wb')

    #fp = open('/tmp/bar.pdf','w')
    doc = BaseDocTemplate(fp, pagesize=A4)
    styles = getSampleStyleSheet()
    tmpl = InvoiceTemplate('invoice',
                           rcptaddr=['Allan F. Octamac', u'Paradisäppelvägen 13',
                                     '313 13 Ankeborg'],
                           senderaddr=['Arrangemangsföreningen Fuskcon',
                                       u'Paradisäppelvägen 6',
                                       '891 00 Ankeborg'],
                           phone='031-13 13 13',
                           email='fusk@con.se',
                           url='http://www.fuskcon.se/',
                           orgnum='888777-4567',
                           vatnum='SE888777456701',
                           fskatt=True,
                           seat=u'Västra Frölunda',
                           kind='invoice',
                           #kind='purchase',
                           ocr='123456789012',
                           expiryDate=time.time() + 86400*30,
                           conditions='30 dagar netto',
                           latefee=u'Efter förfallodatum debiteras '
                           u'dröjsmålsränta enligt räntelagen.',
                           buyerref='Joakim von Anka',
                           annotation=['This is for Joakim von Anka', 'and for his cousin', '1', '2', '3', '4'],
                           total=decimal.Decimal('1234567.50'),
                           pgnum='12345678',
                           qrcode= u'{"uqr":1,"tp":1,"nme":"Test company AB","cid":"555555-5555","iref":"52456","ddt":"20130408","due":5,"pt":"BG","acc":"433-8778"}',
                           styles = styles,
                           showBoundary=0)

    tmpl2 = Invoice2Template('invoice2',
                           rcptaddr=['Allan F. Octamac', u'Paradisäppelvägen 13',
                                     '313 13 Ankeborg'],
                           senderaddr=['Arrangemangsföreningen Fuskcon',
                                       u'Paradisäppelvägen 6',
                                       '891 00 Ankeborg'],
                           phone='031-13 13 13',
                           email='fusk@con.se',
                           url='http://www.fuskcon.se/',
                           orgnum='888777-4567',
                           vatnum='SE888777456701',
                           fskatt=True,
                           seat=u'Västra Frölunda',
                           kind='invoice',
                           #kind='purchase',
                           ocr='123456789012',
                           expiryDate=time.time() + 86400*30,
                           conditions='30 dagar netto',
                           latefee=u'Efter förfallodatum debiteras '
                           u'dröjsmålsränta enligt räntelagen.',
                           total=decimal.Decimal('1234567.50'),
                           pgnum='12345678',
                           qrcode= u'{"uqr":1,"tp":1,"nme":"Test company AB","cid":"555555-5555","iref":"52456","ddt":"20130408","due":5,"pt":"BG","acc":"433-8778"}',
                           styles = styles)
    doc.addPageTemplates([tmpl, tmpl2])

    elements = [NextPageTemplate('invoice'), NextPageTemplate('invoice2')]

    indentedsmallstyle = ParagraphStyle('Small', fontName='Helvetica',
                                        fontSize=8, leading=9, leftIndent=5*mm)
    boldstyle = ParagraphStyle('Bold', fontName='Helvetica-Bold',
                               fontSize=10, leading=12)
    boldrightstyle = ParagraphStyle('Bold', fontName='Helvetica-Bold',
                               fontSize=10, leading=12, alignment=TA_RIGHT)
    mycellstyle = CellStyle('mycellstyle')
    mycellstyle.topPadding = mycellstyle.bottomPadding = 0
    tabledata = [
        Table([[Paragraph('Vara', boldstyle),
                Paragraph('Pris', boldrightstyle),
                Paragraph('Antal', boldrightstyle),
                Paragraph('Summa', boldrightstyle)]],
              colWidths=[115*mm, 20*mm, 20*mm, 25*mm], style=
              TableStyle([('ALIGN', (1,0), (-1, -1), 'RIGHT'),
                          ('TOPPADDING', (0,0), (-1, -1), 0),
                          ('BOTTOMPADDING', (0,0), (-1, -1), 0),
                          #('BOX', (0,0), (-1, -1), 0.25, colors.black),
                          ]))
        ]
    for item in inv.items * 20:
        celldata = [Table([[item.name[0], formatters.money(item.price[0], True),
                            item.quantity[0], formatters.money(item.total[0], True)]],
                          colWidths=[115*mm, 20*mm, 20*mm, 25*mm], style=
                          TableStyle([('ALIGN', (1,0), (-1, -1), 'RIGHT'),
                                      ('TOPPADDING', (0,0), (-1, -1), 0),
                                      ('BOTTOMPADDING', (0,0), (-1, -1), 0),
                                      #('BOX', (0,0), (-1, -1), 0.25, colors.black),
                                      #('ALIGN', (0,0), (-1, 0), 'LEFT')
                                      ]),)]
        if item.options:
            for opt, val in item.optionsWithValues:
                celldata.append(Paragraph('%s: <i>%s</i>' % (opt, val), indentedsmallstyle))
        tabledata.append(celldata)


    # Sum and VAT
    tabledata.append([Table([['', Paragraph('Summa', boldrightstyle),
                              Paragraph(formatters.money(inv.total[0], True), boldrightstyle)]],
                            colWidths=[115*mm, 40*mm, 25*mm], style=
                            TableStyle([('ALIGN', (1,0), (-1, -1), 'RIGHT'),
                                        ('TOPPADDING', (0,0), (-1, -1), 0),
                                        ('BOTTOMPADDING', (0,0), (-1, -1), 0),
                                        #('BOX', (0,0), (-1, -1), 0.25, colors.black),
                                        #('ALIGN', (0,0), (-1, 0), 'LEFT')
                                        ]),)])

    vats = [('25.00', decimal.Decimal('11.37')), ('12.00', decimal.Decimal('6.78'))]

    for percentage, amount in vats:
        tabledata.append([Table([['', Paragraph('Varav moms %s%%' % percentage, boldrightstyle),
                                  Paragraph(formatters.money(amount, True), boldrightstyle)]],
                                colWidths=[115*mm, 40*mm, 25*mm], style=
                                TableStyle([('ALIGN', (1,0), (-1, -1), 'RIGHT'),
                                            ('TOPPADDING', (0,0), (-1, -1), 0),
                                            ('BOTTOMPADDING', (0,0), (-1, -1), 0),
                                            #('BOX', (0,0), (-1, -1), 0.25, colors.black),
                                            #('ALIGN', (0,0), (-1, 0), 'LEFT')
                                            ]),)])

    t = Table([[t] for t in tabledata], colWidths=[180*mm], repeatRows=1,
              style=TableStyle([
                ('LEFTPADDING', (0,0), (0, -1), 0),
                ('RIGHTPADDING', (0, -1), (-1, -1), 0),
                #('BOX', (0,0), (-1, -1), 0.25, colors.black)
                ]))

    elements.append(t)

    extraText = inv.extraText
    if extraText:
        textElements = []
        text_style = ParagraphStyle('Text', fontName='Helvetica',
                                    fontSize=8, leading=9)
        for text in extraText:
            textElements.append(Paragraph(text, text_style))
        elements.append(KeepTogether(textElements))

    doc.multiBuild(elements)
    fp.close()


class TestMakeInvoice(BLMTests):

    def test_make_invoice(self, monkeypatch):
        vc25 = blm.accounting.VatCode(code='10', percentage='25', xmlCode='xml25')
        vc12 = blm.accounting.VatCode(code='11', percentage='12', xmlCode='xml12')
        vc12 = blm.accounting.VatCode(code='12', percentage='6', xmlCode='xml12')

        org = blm.accounting.Org(name=['Foo Inc.'],
                                 address=['The Street 1\n123 45 The City'],
                                 phone=['123 456 789'],
                                 email=['foo@test'],
                                 orgnum=['987654-3210'],
                                 url=['http://foo.test/'],
                                 seat=['The City'],
                                 fskatt=[True],
                                 vatnum=['SE987654321001']
                                 )
        accounting = blm.accounting.Accounting(org=org)
        vatAccount = blm.accounting.Account(number='2025', vatCode='10',
                                            accounting=accounting)
        vatAccount = blm.accounting.Account(number='2012', vatCode='11',
                                            accounting=accounting)
        vatAccount = blm.accounting.Account(number='2013', vatCode='12',
                                            accounting=accounting)

        product1 = blm.members.Product(
            name=['The Product'], accountingRules={'1000': '100'}, org=[org],
            vatAccount='2025',
            optionFields=['opt\x1fdesc\x1fstring\x1f1\x1f'])
        product2 = blm.members.Product(
            name=['The Other Product'], accountingRules={'1000': '200'}, org=[org],
            vatAccount='2012')
        product3 = blm.members.Product(
            name=['The Expensive Product'], accountingRules={'1000': '50'}, org=[org],
            vatAccount='2013')

        purchase = blm.members.Invoice(
            buyerName=[u'Örjan Början'],
            buyerAddress=['Buyer Rd. 1\n123 45 The City'],
            expiryDate=[3600 * 12 + 86400 * 30],
            extraText=['Betalningsvillkor', '''\
Fakturan skall vara betald innan hyresdagen. Vid betalning senare än 10 dagar innan hyresdagen skall kvitto på erlagd betalning kunna förevisas för uthyrande personal.

Faktura ställd till skolor tillhörande Göteborgs skolförvaltning eller till annan organisation med speciell överenskommelse med Näsets Paddlarklubb skall vara betald inom 30 dagar från fakturadatum.

Bokning är bindande. Kreditering av fakturerat belopp sker endast om faktureringen varit felaktig, om hyresmannen med läkarintyg påvisar att han på grund av sjukdom varit förhindrad att utnyttja sin beställning, eller om uthyraren bedömer att väderläget inte medger säker färd. Ändring av bokning kan i undantagsfall ske, om detta inte är till olägenhet för uthyraren.

Näsets Paddlarklubb är en allmännyttig ideell idrottsförening. Vår uthyrningsverksamhet är inte momspliktig.'''],
            items=[blm.members.PurchaseItem(
                    product=[product1], options=['gurka']),
                   blm.members.PurchaseItem(
                    product=[product2]),
                   blm.members.PurchaseItem(
                    product=[product3])])
        purchase.date = [3600 * 12]
        #vats = {'25.00': decimal.Decimal('25.00'), '12.00': decimal.Decimal('12.00'),
        #        '6.00': decimal.Decimal('6.00')}.items()
        pgnum = '123456'
        tickets = None


        class FakeBaseDocTemplate(object):
            created = []
            def __init__(self, fp, pagesize):
                assert fp is pdf
                self.created.append(self)
            def addPageTemplates(self, template1_2):
                template1, template2 = template1_2
                assert template1.kind == purchase.kind[0]
                assert template1.pgnum == pgnum
                assert [
                    # different reportlabs handle strings as
                    # unicode/str internally
                    p.text if type(p.text) == unicode else p.text.decode('utf-8')
                        for p in template1.rcpttext] == [
                    u'Örjan Början',
                    'Buyer Rd. 1',
                    '123 45 The City']
                assert [p.text for p in template1.sendertext] == [
                    'Foo Inc.',
                    'The Street 1',
                    '123 45 The City']
                assert [
                    p.text if type(p.text) == unicode else p.text.decode('utf-8')
                    for p in template1.detailstext] == [
                    'Phone: 123 456 789',
                    'Email: foo@test',
                    'Web: http://foo.test/',
                    u'Registered office: The City']
                assert [p.text for p in template1.banktext] == [
                    'Pg: 1 23 45-6',
                    'Org no: 987654-3210',
                    'VAT no: SE987654321001',
                    'Innehar F-skattsedel']
                assert template1.ocr == purchase.ocr[0]
                assert template1.expiryDate == 3600 * 12 + 86400 * 30
                assert template1.date == 3600 * 12
                assert template1.total == decimal.Decimal('402.00')
                assert json.loads(template1.qrcode) == {
                    'uqr': 1,
                    'tp': 1,
                    'nme': 'Foo Inc.',
                    'cid': '987654-3210',
                    'iref': purchase.ocr[0],
                    'ddt': '19700131',
                    'idt': '19700101',
                    'due': '402.00',
                    'pt': 'PG',
                    'acc': '12345-6',
                    'vh': '25.00',
                    'vm': '24.00',
                    'vl': '3.00',
                    }

            def multiBuild(self, elements):
                self.elements = elements

        monkeypatch.setattr(members.invoice, 'BaseDocTemplate',
                            FakeBaseDocTemplate)
        pdf = StringIO()
        make_invoice(pdf, purchase, org, pgnum, tickets)
        doctemplate, = FakeBaseDocTemplate.created
        assert doctemplate.elements  # not empty


if __name__ == '__main__':
    import locale, gettext
    locale.setlocale(locale.LC_ALL)
    localedir = os.path.abspath(os.path.join(os.path.dirname(
        os.path.dirname(os.path.dirname(__file__))), 'locale'))
    print(localedir)
    gettext.bindtextdomain('accounting', localedir)
    gettext.textdomain('accounting')

    try:
        test(py.path.local('/tmp'))
    except Exception:
        import traceback, pdb
        traceback.print_exc()
        pdb.post_mortem()
