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

#
# ReportLab QRCode widget
#
# Inspired by previous module by German M. Bravo
#
# by Anders Hammarquist <iko@openend.se>
#

__all__ = ('QrCodeWidget', 'QrCode')

import itertools

from reportlab.platypus.flowables import Flowable
from reportlab.graphics.shapes import Group, Rect, Path
from reportlab.lib import colors
from reportlab.lib.validators import isNumber, isNumberOrNone, isColor, isString, Validator
from reportlab.lib.attrmap import AttrMap, AttrMapValue
from reportlab.graphics.widgetbase import Widget
from reportlab.lib.units import mm
try:
    from reportlab.lib.utils import asUnicodeEx, isUnicode
except ImportError:
    # ReportLab 2.x compatibility
    def asUnicodeEx(v, enc='utf8'):
        if isinstance(v, unicode):
            return v
        if isinstance(v, str):
            return v.decode(enc)
        return str(v).decode(enc)

    def isUnicode(v):
        return isinstance(v, unicode)

from . import qrencoder

class isLevel(Validator):
    def test(self, x):
        return x in ['L', 'M', 'Q', 'H']
isLevel = isLevel()

class isUnicodeOrQRList(Validator):
    def _test(self, x):
        if isUnicode(x):
            return True
        if all(isinstance(v, qrencoder.QR) for v in x):
            return True
        return False

    def test(self, x):
        return self._test(x) or self.normalizeTest(x)

    def normalize(self, x):
        if self._test(x):
            return x
        try:
            return asUnicodeEx(x)
        except UnicodeError:
            raise ValueError("Can't convert to unicode: %r" % x)
isUnicodeOrQRList = isUnicodeOrQRList()

class SRect(Rect):
    def __init__(self, x, y, width, height, fillColor=colors.black):
        Rect.__init__(self, x, y, width, height, fillColor=fillColor,
                      strokeColor=None, strokeWidth=0)

class QrCodeWidget(Widget):
    codeName = "QR"
    _attrMap = AttrMap(
        BASE = Widget,
        value = AttrMapValue(isUnicodeOrQRList, desc='QRCode data'),
        x = AttrMapValue(isNumber, desc='x-coord'),
        y = AttrMapValue(isNumber, desc='y-coord'),
        barFillColor = AttrMapValue(isColor, desc='bar color'),
        barWidth = AttrMapValue(isNumber, desc='Width of bars.'), # maybe should be named just width?
        barHeight = AttrMapValue(isNumber, desc='Height of bars.'), # maybe should be named just height?
        barBorder = AttrMapValue(isNumber, desc='Width of QR border.'), # maybe should be named qrBorder?
        barLevel = AttrMapValue(isLevel, desc='QR Code level.'), # maybe should be named qrLevel
        qrVersion = AttrMapValue(isNumberOrNone, desc='QR Code version. None for auto'),
        # Below are ignored, they make no sense
        barStrokeWidth = AttrMapValue(isNumber, desc='Width of bar borders.'),
        barStrokeColor = AttrMapValue(isColor, desc='Color of bar borders.'),
        )
    x = 0
    y = 0
    barFillColor = colors.black
    barStrokeColor = None
    barStrokeWidth = 0
    barHeight = 32*mm
    barWidth = 32*mm
    barBorder = 4
    barLevel = 'L'
    qrVersion = None
    value = None

    def __init__(self, value=None, **kw):
        self.value = isUnicodeOrQRList.normalize(value)
        for k, v in kw.items():
            setattr(self, k, v)

        ec_level = getattr(qrencoder.QRErrorCorrectLevel, self.barLevel)

        self.qr = qrencoder.QRCode(self.qrVersion, ec_level)

        if isUnicode(self.value):
            self.addData(self.value)
        elif self.value:
            for v in self.value:
                self.addData(v)

    def addData(self, value):
        self.qr.addData(value)

    def draw(self):
        self.qr.make()

        g = Group()

        color = self.barFillColor
        border = self.barBorder
        width = self.barWidth
        height = self.barHeight
        x = self.x
        y = self.y

        g.add(SRect(x, y, width, height, fillColor=None))

        path = Path(fillColor=colors.black, strokeColor=None)

        moduleCount = self.qr.getModuleCount()
        minwh = float(min(width, height))
        boxsize = minwh / (moduleCount + border * 2)
        offsetX = (width - minwh) / 2
        offsetY = (minwh - height) / 2

        for r, row in enumerate(self.qr.modules):
            c = 0
            for t, tt in itertools.groupby(row):
                isDark = t
                count = len(list(tt))
                if isDark:
                    x = (c + border) * boxsize
                    y = (r + border + 1) * boxsize
                    path.moveTo(offsetX + x, offsetY + height - y)
                    path.lineTo(offsetX + x + count * boxsize, offsetY + height - y)
                    path.lineTo(offsetX + x + count * boxsize, offsetY + height - y + boxsize)
                    path.lineTo(offsetX + x, offsetY + height - y + boxsize)
                    path.closePath()

                c += count

        g.add(path)

        return g


# Flowable version

class QrCode(Flowable):
    height = 32*mm
    width = 32*mm
    qrBorder = 4
    qrLevel = 'L'
    qrVersion = None
    value = None

    def __init__(self, value=None, **kw):
        self.value = isUnicodeOrQRList.normalize(value)

        for k, v in kw.items():
            setattr(self, k, v)

        ec_level = getattr(qrencoder.QRErrorCorrectLevel, self.qrLevel)

        self.qr = qrencoder.QRCode(self.qrVersion, ec_level)

        if isUnicode(self.value):
            self.addData(self.value)
        elif self.value:
            for v in self.value:
                self.addData(v)

    def addData(self, value):
        self.qr.addData(value)

    def draw(self):
        self.qr.make()

        moduleCount = self.qr.getModuleCount()
        border = self.qrBorder
        xsize = self.width / (moduleCount + border * 2.0)
        ysize = self.height / (moduleCount + border * 2.0)

        path = self.canv.beginPath()

        for r, row in enumerate(self.qr.modules):
            c = 0
            for t, tt in itertools.groupby(row):
                isDark = t
                count = len(list(tt))
                if isDark:
                    x = (c + border) * xsize
                    y = self.height - (r + border + 1) * ysize
                    path.moveTo(x,y)
                    path.lineTo(x, y+ysize)
                    path.lineTo(x+count*xsize, y+ysize)
                    path.lineTo(x+count*xsize, y)
                    path.lineTo(x,y)
                c += count

        self.canv.drawPath(path, fill=1, stroke=0)
