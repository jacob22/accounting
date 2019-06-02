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

# Render a ticket to PDF

import os, sys
import contextlib
# Disable attribute assignment checks for 25% speed increase, AKA tell reportlab
# that we are Python programmers.
import reportlab.rl_config
reportlab.rl_config.shapeChecking = 0

from reportlab.graphics.widgetbase import Widget
from reportlab.graphics.barcode import code128
from reportlab.graphics import renderPDF
from reportlab.graphics.shapes import Drawing, Group, Rect, String
from reportlab.lib import colors
from reportlab.lib.attrmap import *
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.validators import isNumber, isColor, isString, Validator
from reportlab.pdfgen import canvas
from reportlab.platypus.flowables import Flowable
from reportlab.platypus.paragraph import Paragraph
from reportlab.platypus.frames import Frame
from reportlab.platypus.doctemplate import BaseDocTemplate, PageTemplate
from reportlab.pdfbase.pdfmetrics import stringWidth

from pdfrw import PdfReader
from pdfrw.buildxobj import pagexobj
from pdfrw.toreportlab import makerl

from . import qrreportlab as qr
try:
    unicode
except NameError:
    unicode = str
# Monkeypatch to fix broken wordwraping of non-ascii
import reportlab.platypus.paragraph

if hasattr(reportlab.platypus.paragraph, '_SplitText'):
    if not issubclass(reportlab.platypus.paragraph._SplitText, unicode):
        class _SplitText(unicode):
            pass
        reportlab.platypus.paragraph._SplitText = _SplitText

@contextlib.contextmanager
def save_state(canvas):
    canvas.saveState()
    yield
    canvas.restoreState()

class Ticket(Flowable):
    _attrMap = AttrMap(
        BASE=Widget,
        title=AttrMapValue(isString, desc='title'),
        width = AttrMapValue(isNumber, desc='width'),
        height = AttrMapValue(isNumber, desc='height'),
        )

    def __init__(self, title, **kw):
        Flowable.__init__(self)

        self.width = 210*mm
        self.height = 99*mm # 1/3 A4 aka A65
        self.title = title

        for k,v in kw.items():
            setattr(self, k, v)

    def wrap(self, aW, aH):
        return (self.width, self.height)

    def draw(self):
        c = self.canv

        titlestyle = ParagraphStyle('Title', fontName='Helvetica', fontSize=36,
                                    leading=43)
        style = ParagraphStyle('Options', leftIndent=10*mm,
                               firstLineIndent=-10*mm)

        text = [Paragraph(self.title, titlestyle)]
        for field, value in self.options:
            text.append(Paragraph(u'<b>{}:</b> <i>{}</i>'.format(field, value),
                                  style))

        f = Frame(10*mm, 25*mm, self.width - 53*mm, 64*mm, leftPadding=0,
                  bottomPadding=0, rightPadding=0, topPadding=-5, # -5 font fudge factor
                  showBoundary=0)
        f.addFromList(text, c)

        with save_state(c):
            c.translate(self.width - 40*mm, self.height - 10*mm)
            c.rotate(270)

            orgstyle = ParagraphStyle('OrgName', fontSize=11, leading=12)
            style = ParagraphStyle('OrgAddr', fontSize=8, leading=10)

            f = Frame(0, 0, self.height - 53*mm, 30*mm,
                      leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0,
                      showBoundary=0)
            l = []
            if self.org.name:
                l.append(Paragraph(self.org.name[0], orgstyle))
            if self.org.address:
                l.append(Paragraph('<br/>'.join(
                    self.org.address[0].split('\n')), style))
            if self.org.phone:
                l.append(Paragraph(self.org.phone[0], style))

            f.addFromList(l, c)

        with save_state(c):
            c.translate(120*mm, 15*mm)
            c.setFont('Helvetica', 8)
            c.drawString(0,0,u'Tickets by ')

            width = stringWidth(u'Tickets by ', 'Helvetica', 8)

            with save_state(c):
                # XXX Ideally, only load the logo once
                logo = PdfReader(os.path.join(os.path.dirname(__file__),
                                              'eutaxia-logo.pdf')).pages[0]
                logo = pagexobj(logo)
                rl_obj = makerl(c, logo)
                scale = 9 / logo.BBox[3]
                c.translate(width, -1.5)
                c.scale(scale, scale)

                c.doForm(rl_obj)

                if False:
                    p = c.beginPath()
                    c.setDash(1)
                    p.moveTo(0, 0)
                    p.lineTo(logo.BBox[2], 0)
                    p.lineTo(logo.BBox[2], logo.BBox[3])
                    p.lineTo(0, logo.BBox[3])
                    p.close()
                    c.drawPath(p)

                width += logo.BBox[2] * scale

            c.drawString(0, -10, u'http://www.eutaxia.se/')
            width = max(width, stringWidth(u'http://www.eutaxia.se/', 'Helvetica', 8))

            c.linkURL('http://www.eutaxia.se', (-1, -13, width, 10), relative=1)

        bar = code128.Code128(self.barcode, barWidth=0.3*mm, humanReadable=1)
        bar.drawOn(c,10*mm,10*mm)

        qd = Drawing()
        # No border, deal with quiet zone manually
        q = qr.QrCodeWidget(self.qrcode, barLevel = 'M', barBorder = 0,
                            barWidth = 30*mm, barHeight = 30*mm)
        qd.add(q)
        renderPDF.draw(qd, c, self.width - q.barWidth - 10*mm, 10*mm)
        c.linkURL(self.qrcode, (self.width - q.barWidth - 10*mm, 10*mm,
                                self.width - 10*mm, 40*mm), relative=1)

        p = c.beginPath()
        c.setDash(1,2)
        p.moveTo(0, 0)
        p.lineTo(self.width, 0)
        c.drawPath(p)

        if False:
            p = c.beginPath()
            c.setDash(1)
            p.moveTo(0, 0)
            p.lineTo(self.width, 0)
            p.lineTo(self.width, self.height)
            p.lineTo(0, self.height)
            p.close()
            c.drawPath(p)


class DocTemplate(BaseDocTemplate):
    def _canvasMaker(self, *args, **kw):
        canv = canvas.Canvas(*args, **kw)
        catalog = canv._doc.Catalog
        try:
            vp = catalog.ViewerPreferences
        except AttributeError:
            from reportlab.pdfbase.pdfdoc import PDFDictionary
            vp = catalog.ViewerPreferences = PDFDictionary()

        vp['Duplex'] = 'Simplex'
        return canv

    def build(self, flowables):
        self._calc()    #in case we changed margins sizes etc
        frameT = Frame(self.leftMargin, self.bottomMargin, self.width,
                       self.height, id='normal', leftPadding=0, bottomPadding=0,
                       rightPadding=0, topPadding=0)
        self.addPageTemplates([PageTemplate(id='First',frames=frameT, pagesize=self.pagesize)])
        BaseDocTemplate.build(self,flowables, canvasmaker=self._canvasMaker)

def generate(fp, data):
    doc = DocTemplate(fp, pagesize=A4, leftMargin=0, rightMargin=0,
                            topMargin=0, bottomMargin=0)
    flow = []
    for t in data:
        flow.append(Ticket(title=t.name[0], options=t.options,
                           barcode=str(t.barcode[0]), qrcode=t.qrcode[0],
                           org=t.org[0]))
    doc.build(flow)



def test():
    class FakeToi(object):
        def __init__(self, **kw):
            self.__dict__ = kw

    import sys
    from . import base64long
    t = Ticket(
        #'Fusket i natten',
        u'Invigningsfest - av våra nya lokaler.',
        options=[('Namn', 'Allan F. Octamac'), (u'Karaktär', u'Räksmörgås')],
        org = FakeToi(
            name=[u'Arrangemangsföreningen Fuskcon'],
            #name=[u'Näsets Paddlarklubb'],
            address=[u'Paradisäppelvägen 6\n891 00 Ankeborg'],
            phone=[u'0941-12 34 56']
            ),
        #barcode='52fa3d385e144c54fd474604 300310146',
        barcode=u'0256802913644062033722112261163040310146',
        #qrcode='https://admin.eutaxia.eu/ticket/52fa3bdb5e144c5413b39517/2054512641/52fa3bdb5e144c5413b39515/445671341912272066024349244874082604647348288310/368585379760158096688016088313942883089230885699'
        #qrcode=('https://admin.eutaxia.eu/ticket/52fa3bdb5e144c5413b39517/%s/52fa3bdb5e144c5413b39515/%s/%s' % (tuple(map(base64long.encode32, [2054512641,445671341912272066024349244874082604647348288310,368585379760158096688016088313942883089230885699])))).upper(),
        qrcode=('https://admin.eutaxia.eu/ticket/52fa3bdb5e144c5413b39517/%s/52fa3bdb5e144c5413b39515/%s/%s' % (tuple(map(base64long.encode, [2054512641,445671341912272066024349244874082604647348288310,368585379760158096688016088313942883089230885699]))))
        )

    c = canvas.Canvas(sys.stdout, pagesize=A4)

    t.drawOn(c, 0, 0)

    c.showPage()
    c.save()

if __name__ == '__main__':
    try:
        test()
    except Exception:
        import traceback, pdb
        traceback.print_exc()
        pdb.post_mortem()
