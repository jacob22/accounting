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

# Render invoice / order confirmation to PDF

import json, os, sys, decimal, time
import contextlib

# Disable attribute assignment checks for 25% speed increase, AKA tell reportlab
# that we are Python programmers.
import reportlab.rl_config
reportlab.rl_config.shapeChecking = 0

from reportlab.graphics.widgetbase import Widget
from reportlab.graphics import renderPDF
from reportlab.graphics.shapes import Drawing, Group, Rect, String
from reportlab.lib import colors
from reportlab.lib.attrmap import *
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.validators import isNumber, isColor, isString, Validator
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus.flowables import Flowable, KeepTogether
from reportlab.platypus.paragraph import Paragraph
from reportlab.platypus.frames import Frame
from reportlab.platypus.tables import Table, TableStyle, CellStyle
from reportlab.platypus.doctemplate import BaseDocTemplate, PageTemplate
from reportlab.platypus.doctemplate import NextPageTemplate
from reportlab.pdfbase.pdfmetrics import stringWidth

from pdfrw import PdfReader
from pdfrw.buildxobj import pagexobj
from pdfrw.toreportlab import makerl

from accounting.templating import formatters
from accounting import luhn

from . import qrreportlab as qr
from .qrencoder import QRECI, QR8bitByte

import sys
if sys.version_info < (3,0,0):
    PYT3 = False
    py3chr = lambda x: x
    py3txt = lambda x: x
else:
    PYT3 = True
    py3chr = lambda x: chr(x)
    py3txt = lambda x: x.encode('utf-8')
    unicode = str

import gettext
def _(s):
    try:
        import flask, flaskext.babel
        if flask.request:
            return flaskext.babel.get_domain().get_translations().ugettext(s)
    except ImportError:
        pass
    texttest = gettext.gettext(s)
    #return gettext.gettext(s).decode('utf-8')  # all our po files are utf-8
    # if isinstance(texttest, str):
    #     return texttest     #.encode('utf-8')
    return py3txt(texttest)     #.decode('utf-8')  # all our po files are utf-8

# Monkeypatch to fix broken wordwraping of non-ascii
import reportlab.platypus.paragraph

if hasattr(reportlab.platypus.paragraph, '_SplitText'):
    if not issubclass(reportlab.platypus.paragraph._SplitText, unicode):
        class _SplitText(unicode):
            pass
        reportlab.platypus.paragraph._SplitText = _SplitText

# Add OCR-B font
pdfmetrics.registerFont(TTFont('OCRB', os.path.join(
            os.path.dirname(__file__),
            '..', 'static', 'fonts', 'OCRB.ttf')))

@contextlib.contextmanager
def save_state(canvas):
    canvas.saveState()
    yield
    canvas.restoreState()


class BaseInvoiceTemplate(PageTemplate):

    width = 210*mm
    height = 297*mm

    def __init__(self, name=None, rcptaddr=[], senderaddr=[], kind='purchase',
                 phone=None,  email=None, url=None, seat=None,
                 orgnum=None, vatnum=None, fskatt=None,
                 date=None, ocr='', expiryDate=None, conditions=None,
                 latefee=None, buyerref='', annotation='', pgnum=None, total=0,
                 qrcode=None,
                 styles={}, showBoundary=0, frames=[]):
        self.kind = kind
        self.date = date or time.time()
        self.ocr = ocr
        self.expiryDate = expiryDate
        self.conditions = conditions
        self.latefee = latefee
        self.buyerref = buyerref
        self.annotation = annotation
        self.pgnum = pgnum
        self.total = total
        self.qrcode = qrcode

        self.showBoundary = showBoundary
        self.styles = styles
        self.smallstyle = smallstyle = ParagraphStyle('Small', fontName='Helvetica',
                               fontSize=8, leading=9)

        self.detailsFooterFrame = Frame(75*mm, 12*mm, 55*mm, 20*mm,
                                        id='phonefooter', leftPadding=0,
                                        bottomPadding=0, rightPadding=0,
                                        topPadding=0, showBoundary=showBoundary)
        self.detailstext = s = []
        if phone:
            s.append(Paragraph(_(u'Phone: %s') % py3txt(phone), smallstyle))
        if email:
            s.append(Paragraph(_(u'Email: %s') % py3txt(email), smallstyle))
        if url:
            s.append(Paragraph(_(u'Web: %s') % py3txt(url), smallstyle))
        if seat:
            s.append(Paragraph(_(u'Registered office: %s') % py3txt(seat), smallstyle))

        self.bankFooterFrame = Frame(140*mm, 12*mm, 55*mm, 20*mm,
                                     id='bankfooter', leftPadding=0,
                                     bottomPadding=0, rightPadding=0,
                                     topPadding=0, showBoundary=showBoundary)
        self.banktext = s = []
        if pgnum:
            s.append(Paragraph(_('Pg: %s') % py3txt(formatters.pgnum(pgnum)), smallstyle))
        s.append(Paragraph(_('Org no: %s') % py3txt(orgnum), smallstyle))
        if vatnum:
            s.append(Paragraph(_('VAT no: %s') % py3txt(vatnum), smallstyle))
        if fskatt:
            s.append(Paragraph('Innehar F-skattsedel', smallstyle))

        PageTemplate.__init__(self, name, frames)

    @property
    def kind_text(self):
        if self.kind == 'purchase':
            return _(u'Order')
        else:
            return _(u'Invoice')

    @property
    def date_text(self):
        if self.kind == 'purchase':
            return _(u'Order date')
        else:
            return _(u'Invoice date')

    @property
    def ocr_text(self):
        if self.kind == 'purchase':
            return _(u'Order number')
        else:
            return _(u'Invoice number')

    def beforeDrawPage(self, canvas, doc):
        self.senderFrame._reset()
        self.senderFrame.addFromList(self.sendertext[:], canvas)
        self.senderFooterFrame._reset()
        self.senderFooterFrame.addFromList(self.sendertext[:], canvas)
        self.detailsFooterFrame._reset()
        self.detailsFooterFrame.addFromList(self.detailstext, canvas)
        self.bankFooterFrame._reset()
        self.bankFooterFrame.addFromList(self.banktext, canvas)
        with save_state(canvas):
            p = canvas.beginPath()
            p.moveTo(15*mm, 35*mm)
            p.lineTo(self.width-15*mm, 35*mm)
            canvas.drawPath(p)

            to = canvas.beginText()
            to.setTextOrigin(118*mm, self.height-15*mm)
            to.setFont('Helvetica-Bold', 24)
            to.textOut(self.kind_text)
            to.moveCursor(50*mm,0)
            to.setFont('Helvetica', 10)
            to.textOut(_(u'page %d') % doc.page)
            to.setTextOrigin(118*mm, self.height-21*mm)
            to.textOut(self.date_text)
            to.moveCursor(50*mm, 0)
            to.textLine(formatters.date(self.date))
            to.moveCursor(-50*mm, 0)
            to.textOut(self.ocr_text)
            to.moveCursor(50*mm, 0)
            to.textLine(self.ocr)
            to.moveCursor(-50*mm, 0)
            if self.expiryDate:
                to.textOut(_(u'Due date'))
                to.moveCursor(50*mm, 0)
                to.textLine(formatters.date(self.expiryDate))
                to.moveCursor(-50*mm, 0)
            canvas.drawText(to)


# Page Template for second and later pages of invoice
class Invoice2Template(BaseInvoiceTemplate):

    def __init__(self, name, showBoundary=0, **kw):

        frames = [
            Frame(15*mm, 40*mm, self.width-30*mm, self.height-75*mm,
                  id='normal', leftPadding=0, bottomPadding=0,
                  rightPadding=0, topPadding=0, showBoundary=showBoundary)
            ]
        BaseInvoiceTemplate.__init__(self, name, frames=frames,
                                     showBoundary=showBoundary, **kw)

        self.senderFrame = Frame(20*mm, self.height-35*mm+20, 60*mm, 20*mm,
                                 id='sender', leftPadding=0, bottomPadding=0,
                                 rightPadding=0, topPadding=0,
                                 showBoundary=showBoundary)
        self.senderFooterFrame = Frame(15*mm, 12*mm, 55*mm, 20*mm,
                                       id='senderfooter', leftPadding=0,
                                       bottomPadding=0, rightPadding=0,
                                       topPadding=0, showBoundary=showBoundary)
        self.sendertext = s = []
        for line in kw.get('senderaddr', []):
            s.append(Paragraph(line, self.smallstyle))

# Page Template for first page of invoice/order confirmation
class InvoiceTemplate(BaseInvoiceTemplate):

    def __init__(self, name, showBoundary=0, **kw):
        if kw.get('pgnum'):
            height_adjust = 0
        else:
            height_adjust = 110
        frames = [
            Frame(15*mm, 40*mm, self.width-30*mm, self.height-155*mm+height_adjust,
                  id='normal', leftPadding=0, bottomPadding=0,
                  rightPadding=0, topPadding=0, showBoundary=showBoundary)
            ]
        BaseInvoiceTemplate.__init__(self, name, frames=frames,
                                     showBoundary=showBoundary, **kw)

        # Intended to fit H2 window envelopes (C5/E5/E65/S65)
        self.rcptFrame = Frame(118*mm, self.height-65*mm, 70*mm, 20*mm,
                               id='recipient', leftPadding=0, bottomPadding=0,
                               rightPadding=0, topPadding=0,
                               showBoundary=showBoundary)
        self.rcpttext = s = []
        for line in kw.get('rcptaddr', []):
            s.append(Paragraph(line, self.styles['Normal']))

        self.senderFrame = Frame(20*mm, self.height-40*mm, 60*mm, 20*mm,
                                 id='sender', leftPadding=0, bottomPadding=0,
                                 rightPadding=0, topPadding=0,
                                 showBoundary=showBoundary)
        self.senderFooterFrame = Frame(15*mm, 12*mm, 55*mm, 20*mm,
                                       id='senderfooter', leftPadding=0,
                                       bottomPadding=0, rightPadding=0,
                                       topPadding=0, showBoundary=showBoundary)
        self.sendertext = s = []
        for line in kw.get('senderaddr', []):
            s.append(Paragraph(line, self.smallstyle))

        self.annotationframe = Frame(20*mm, self.height-69*mm, 60*mm, 20*mm,
                                     id='annotation', leftPadding=0, bottomPadding=0,
                                     rightPadding=0, topPadding=0,
                                     showBoundary=showBoundary)

    def beforeDrawPage(self, canvas, doc):
        BaseInvoiceTemplate.beforeDrawPage(self, canvas, doc)
        self.rcptFrame.addFromList(self.rcpttext, canvas)
        with save_state(canvas):
            p = canvas.beginPath()
            to = canvas.beginText()
            to.setTextOrigin(20*mm, self.height-44*mm)
            to.setFont('Helvetica', 8)
            to.textOut(_(u'Your reference'))
            to.setFont('Helvetica', 10)
            to.textOut(' ')
            to.textLine(self.buyerref)
            to.setFont('Helvetica', 8)
            to.textLine(_(u'Your notes'))
            paragraphs = [Paragraph(line, self.styles['Normal'])
                          for line in self.annotation]
            self.annotationframe.addFromList(paragraphs, canvas)
            canvas.drawText(to)

            if self.pgnum and self.total != 0:
                ypos = self.height - 75*mm - 5
                to = canvas.beginText()
                to.setTextOrigin(20*mm, ypos)
                to.setFont('Helvetica', 10)
                to.textLine('Betalas till')
                to.setFont('Helvetica-Bold', 12)
                to.textOut('Pg ' + formatters.pgnum(self.pgnum))

                to.setTextOrigin(55*mm, ypos)
                to.setFont('Helvetica', 10)
                to.textLine('OCR / referens')
                to.setFont('Helvetica-Bold', 12)
                to.textOut(self.ocr)

                to.setTextOrigin(85*mm, ypos)
                to.setFont('Helvetica', 10)
                to.textLine('Att betala')
                to.setFont('Helvetica-Bold', 12)
                to.textLine(formatters.money(self.total, True))

                ypos = to.getY()-5
                if self.expiryDate:
                    to.setTextOrigin(20*mm, ypos)
                    to.setFont('Helvetica', 10)
                    to.textLine(u'Förfallodatum')
                    to.setFont('Helvetica-Bold', 12)
                    to.textLine(formatters.date(self.expiryDate))

                    latestyle = ParagraphStyle('Late', fontName='Helvetica',
                                               fontSize=8, leading=9)
                    lateframe = Frame(45*mm, ypos-15, 65*mm, 22,
                                      id='latefee', leftPadding=0,
                                      bottomPadding=0, rightPadding=0,
                                      topPadding=0, showBoundary=self.showBoundary)
                    lateframe.addFromList([Paragraph(self.latefee, latestyle)],
                                          canvas)

                canvas.drawText(to)
                canvas.roundRect(17*mm, ypos-21, 100*mm + 68, 68, 6)

                # Need to set ECI to UTF-8
                # seee https://github.com/zxing/zxing/blob/3de3374dd25739bde952c788c1064cb17bc11ff8/core/src/main/java/com/google/zxing/qrcode/decoder/Mode.java
                # etc, update qrcode encoder...
                qd = Drawing()
                # No border, deal with quiet zone manually
                data = [ QRECI(26),
                         QR8bitByte(self.qrcode) ]
                q = qr.QrCodeWidget(data, barLevel = 'L', barBorder = 4.0,
                                    barWidth = 68.0, barHeight = 68.0)
                qd.add(q)
                renderPDF.draw(qd, canvas, 117*mm, ypos-21)

                qrstyle = ParagraphStyle('QR', fontName='Helvetica',
                                           fontSize=10, leading=12)
                qrinfoframe = Frame(145*mm, ypos-21, self.width - 160*mm, 68,
                                    id='qrinfo', topPadding=0, leftPadding=0,
                                    bottomPadding=0, rightPadding=0,
                                    showBoundary=self.showBoundary)
                qrinfoframe.addFromList([Paragraph(
                            u'Om du betalar med bankapp kan du skanna QR-koden '
                            u'bredvid eller OCR-raden nedan. '
                            u'Läs mer om QR-koden på http://usingqr.se',
                            qrstyle)], canvas)

                # http://www.nordea.se/sitemod/upload/root/content/nordea_se/foretag/programleverantorer/filer/ocr_totalin.pdf
                to = canvas.beginText()
                to.setTextOrigin(10*mm, self.height - 105*mm)
                to.setFont('OCRB', 10)

                #  7777777777666666666655555555554444444444333333333322222222221111111111000000000
                #  9876543210987654321098765432109876543210987654321098765432109876543210987654321
                # '#              123456789012 #12345678 50   9 >                12345678 #14#    '
                #  # ooooooooooooooooooooooooo #kkkkkkkk öö   c >                PpppppppP#tt#

                ocrformat = '# {ocr:>25} #{totalkr:>8} {totaldec:<02}   {totalcheck:1} > {pgnum:>23} #14#    '
                totalkr = str(int(self.total))  # integer part of Decimal
                totaldec = str(int(self.total % 1 * 100))  # fraction part of Decimal
                totalcheck = luhn.luhn_checksum(
                    str(self.total).replace('.', '') + '0')
                ocrkeys = {
                    'ocr': self.ocr,
                    'totalkr': totalkr,
                    'totaldec': totaldec,
                    'totalcheck': totalcheck,
                    'pgnum': self.pgnum
                }

                ocrline = ocrformat.format(**ocrkeys)

                assert len(ocrline) == 79
                to.textLine(ocrline)

                canvas.drawText(to)

def make_invoice(fp, purchase, org, pgnum, tickets, **kw):
    """
    make pdf invoice. Should be called with the same parameters
    as the render_template with the html template.
    """
    doc = BaseDocTemplate(fp, pagesize=A4)
    styles = getSampleStyleSheet()

    args = dict(
        date=purchase.date[0],
        rcptaddr=[purchase.buyerName[0]],
        senderaddr=[org.name[0]],
        orgnum=org.orgnum[0],
        fskatt=org.fskatt[0],
        kind=purchase.kind[0],
        ocr=purchase.ocr[0],
        conditions='30 dagar netto',
        latefee=u'Efter förfallodatum debiteras '
        u'dröjsmålsränta enligt räntelagen.',
        total=purchase.total[0],
        pgnum=pgnum,
        styles = styles)

    qrcode = {
        'uqr': 1,
        'tp': 1,
        'nme': org.name[0],
        'cid': org.orgnum[0],
        'idt': time.strftime('%Y%m%d', time.localtime(purchase.date[0])),
        'iref': purchase.ocr[0],
        'due': str(purchase.total[0]),
        'pt': 'PG',
        'acc': pgnum[:-1] + '-' + pgnum[-1:]
        }

    if purchase.buyerAddress:
        args['rcptaddr'] += purchase.buyerAddress[0].split('\n')
    if org.address:
        args['senderaddr'] += org.address[0].split('\n')
    if org.phone:
        args['phone'] = org.phone[0]
    if org.email:
        args['email'] = org.email[0]
    if org.url:
        args['url'] = org.url[0]
    if org.seat:
        args['seat'] = org.seat[0]
    if org.vatnum:
        args['vatnum'] = org.vatnum[0]
    if purchase.buyerReference:
        args['buyerref'] = purchase.buyerReference[0]
    if purchase.buyerAnnotation:
        args['annotation'] = purchase.buyerAnnotation[0].split('\n')
    for (code, pct, value) in purchase.vat:
        qrcode[{'10': 'vh', '11': 'vm', '12': 'vl'}[code]] = str(value)
    try:
        args['expiryDate'] = purchase.expiryDate[0]
        qrcode['ddt'] = time.strftime('%Y%m%d',
                                      time.localtime(purchase.expiryDate[0]))
    except (AttributeError, IndexError):
        qrcode['ddt'] = time.strftime('%Y%m%d')

    args['qrcode'] = json.dumps(qrcode)

    tmpl = InvoiceTemplate(name='invoice', **args)
    tmpl2 = Invoice2Template(name='invoice2', **args)

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
        Table([[Paragraph(_('Item'), boldstyle),
                Paragraph(_('Price'), boldrightstyle),
                Paragraph(_('Quantity'), boldrightstyle),
                Paragraph(_('Total'), boldrightstyle)]],
              colWidths=[115*mm, 20*mm, 20*mm, 25*mm], style=
              TableStyle([('ALIGN', (1,0), (-1, -1), 'RIGHT'),
                          ('TOPPADDING', (0,0), (-1, -1), 0),
                          ('BOTTOMPADDING', (0,0), (-1, -1), 0),
                          #('BOX', (0,0), (-1, -1), 0.25, colors.black),
                          ]))
        ]
    for item in purchase.items:
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
            for opt, val in item.optionsWithValue:
                celldata.append(Paragraph('%s: <i>%s</i>' % (opt, val), indentedsmallstyle))
        tabledata.append(celldata)


    # Sum and VAT
    tabledata.append([Table([['', Paragraph(_('Total'), boldrightstyle),
                              Paragraph(formatters.money(purchase.total[0], True), boldrightstyle)]],
                            colWidths=[115*mm, 40*mm, 25*mm], style=
                            TableStyle([('ALIGN', (1,0), (-1, -1), 'RIGHT'),
                                        ('TOPPADDING', (0,0), (-1, -1), 0),
                                        ('BOTTOMPADDING', (0,0), (-1, -1), 0),
                                        #('BOX', (0,0), (-1, -1), 0.25, colors.black),
                                        #('ALIGN', (0,0), (-1, 0), 'LEFT')
                                        ]),)])

    #vats = [(25, decimal.Decimal('11.37')), (12, decimal.Decimal('6.78'))]

    for code, percentage, amount in purchase.vat:
        tabledata.append([Table([['', Paragraph(_('Including %s%% VAT') % py3txt(formatters.vatpercentage(percentage)),
                                                boldrightstyle),
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


    extraText = purchase.extraText
    if extraText:
        textElements = []
        text_style = ParagraphStyle('Text', fontName='Helvetica',
                                    fontSize=8, leading=9)
        for text in extraText:
            textElements.append(Paragraph(text, text_style))
        elements.append(KeepTogether(textElements))

    doc.multiBuild(elements)
    #fp.close()
