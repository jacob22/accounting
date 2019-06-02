# -*- encoding: utf-8 -*-

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
# Tests for QR-Encoder
#

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import py.test

import qrencoder

class TestMask(object):

    def test_maskPattern_0(self):
        # (i + j) mod 2 == 0

        for i in range(20):
            for j in range(20):
                p = qrencoder.QRUtil.getMask(0)(i,j)
                assert ((i + j) % 2 == 0) == p

        assert qrencoder.QRUtil.getMask(0)(0,0) is True
        assert qrencoder.QRUtil.getMask(0)(0,1) is False
        assert qrencoder.QRUtil.getMask(0)(0,2) is True
        assert qrencoder.QRUtil.getMask(0)(1,0) is False
        assert qrencoder.QRUtil.getMask(0)(1,1) is True

    def test_maskPattern_1(self):
        # i mod 2 == 0

        for i in range(20):
            for j in range(20):
                p = qrencoder.QRUtil.getMask(1)(i,j)
                assert (i % 2 == 0) == p

        assert qrencoder.QRUtil.getMask(1)(0,0) == True
        assert qrencoder.QRUtil.getMask(1)(0,1) == True
        assert qrencoder.QRUtil.getMask(1)(0,2) == True
        assert qrencoder.QRUtil.getMask(1)(1,0) == False
        assert qrencoder.QRUtil.getMask(1)(1,1) == False

    def test_maskPattern_2(self):
        # j mod 3 == 0

        for i in range(20):
            for j in range(20):
                p = qrencoder.QRUtil.getMask(2)(i,j)
                assert (j % 3 == 0) == p

        assert qrencoder.QRUtil.getMask(2)(0,0) == True
        assert qrencoder.QRUtil.getMask(2)(0,1) == False
        assert qrencoder.QRUtil.getMask(2)(0,2) == False
        assert qrencoder.QRUtil.getMask(2)(0,3) == True
        assert qrencoder.QRUtil.getMask(2)(1,0) == True
        assert qrencoder.QRUtil.getMask(2)(1,1) == False

    def test_maskPattern_3(self):
        # (i + j) mod 3 == 0

        for i in range(20):
            for j in range(20):
                p = qrencoder.QRUtil.getMask(3)(i,j)
                assert ((i + j) % 3 == 0) == p

        assert qrencoder.QRUtil.getMask(3)(0,0) == True
        assert qrencoder.QRUtil.getMask(3)(0,1) == False
        assert qrencoder.QRUtil.getMask(3)(0,2) == False
        assert qrencoder.QRUtil.getMask(3)(0,3) == True
        assert qrencoder.QRUtil.getMask(3)(1,0) == False
        assert qrencoder.QRUtil.getMask(3)(1,1) == False
        assert qrencoder.QRUtil.getMask(3)(1,2) == True

    def test_maskPattern_4(self):
        # (i/2 + j/3) mod 2 == 0

        for i in range(20):
            for j in range(20):
                p = qrencoder.QRUtil.getMask(4)(i,j)
                assert ((i//2 + j//3) % 2 == 0) == p

        assert qrencoder.QRUtil.getMask(4)(0,0) == True
        assert qrencoder.QRUtil.getMask(4)(0,1) == True
        assert qrencoder.QRUtil.getMask(4)(0,2) == True
        assert qrencoder.QRUtil.getMask(4)(0,3) == False
        assert qrencoder.QRUtil.getMask(4)(1,0) == True
        assert qrencoder.QRUtil.getMask(4)(2,0) == False
        assert qrencoder.QRUtil.getMask(4)(3,0) == False

    def test_maskPattern_5(self):
        # (i*j) mod 2 + (i*j) mod 3 == 0

        for i in range(20):
            for j in range(20):
                p = qrencoder.QRUtil.getMask(5)(i,j)
                assert ((i*j)%2 + (i*j)%3 == 0) == p

        assert qrencoder.QRUtil.getMask(5)(0,0) == True
        assert qrencoder.QRUtil.getMask(5)(0,1) == True
        assert qrencoder.QRUtil.getMask(5)(0,2) == True
        assert qrencoder.QRUtil.getMask(5)(0,3) == True
        assert qrencoder.QRUtil.getMask(5)(1,0) == True
        assert qrencoder.QRUtil.getMask(5)(2,0) == True
        assert qrencoder.QRUtil.getMask(5)(3,0) == True
        assert qrencoder.QRUtil.getMask(5)(1,1) == False
        assert qrencoder.QRUtil.getMask(5)(2,2) == False
        assert qrencoder.QRUtil.getMask(5)(2,3) == True
        assert qrencoder.QRUtil.getMask(5)(3,2) == True

    def test_maskPattern_6(self):
        # ((i*j) mod 2 + (i*j) mod 3) mod 2 == 0

        for i in range(20):
            for j in range(20):
                p = qrencoder.QRUtil.getMask(6)(i,j)
                assert (((i*j)%2 + (i*j)%3)%2 == 0) == p

        assert qrencoder.QRUtil.getMask(6)(0,0) == True
        assert qrencoder.QRUtil.getMask(6)(0,1) == True
        assert qrencoder.QRUtil.getMask(6)(0,2) == True
        assert qrencoder.QRUtil.getMask(6)(0,3) == True
        assert qrencoder.QRUtil.getMask(6)(1,0) == True
        assert qrencoder.QRUtil.getMask(6)(2,0) == True
        assert qrencoder.QRUtil.getMask(6)(3,0) == True
        assert qrencoder.QRUtil.getMask(6)(1,1) == True
        assert qrencoder.QRUtil.getMask(6)(2,2) == False
        assert qrencoder.QRUtil.getMask(6)(2,3) == True
        assert qrencoder.QRUtil.getMask(6)(3,2) == True


    def test_maskPattern_7(self):
        # ((i+j) mod 2 + (i*j) mod 3) mod 2 == 0

        for i in range(20):
            for j in range(20):
                p = qrencoder.QRUtil.getMask(7)(i,j)
                assert (((i+j)%2 + (i*j)%3)%2 == 0) == p

        assert qrencoder.QRUtil.getMask(7)(0,0) == True
        assert qrencoder.QRUtil.getMask(7)(0,1) == False
        assert qrencoder.QRUtil.getMask(7)(0,2) == True
        assert qrencoder.QRUtil.getMask(7)(0,3) == False
        assert qrencoder.QRUtil.getMask(7)(1,0) == False
        assert qrencoder.QRUtil.getMask(7)(2,0) == True
        assert qrencoder.QRUtil.getMask(7)(3,0) == False
        assert qrencoder.QRUtil.getMask(7)(1,1) == False
        assert qrencoder.QRUtil.getMask(7)(2,2) == False
        assert qrencoder.QRUtil.getMask(7)(2,3) == False
        assert qrencoder.QRUtil.getMask(7)(3,2) == False
        assert qrencoder.QRUtil.getMask(7)(1,3) == True
        assert qrencoder.QRUtil.getMask(7)(3,1) == True

    def test_maskScoreRule1vert(self):
        # score 3 + i point for each run of 5 or more cells in the same
        # colour (i = length of run - 5)

        data = [ [True] * 10,  # 8 points
                 [False] * 10, # 8 points
                 [False, True] * 5,
                 [True, False] * 5
                 ] + [ [False, True] * 5,
                       [True, False] * 5 ] * 3  # must be square

        assert qrencoder.QRUtil.maskScoreRule1vert(list(zip(*data))) == 8 + 8

        data = [ [True, True, True, True, True, True, True, True, True, False],  # 7 points
                 [False, False, False, False, False, False, False, False, False, True],  # 7 points
                 [True, False] * 5,
                 [False, True] * 5
                 ] + [ [False, True] * 5, [True, False] * 5 ] * 4  # must be square

        assert qrencoder.QRUtil.maskScoreRule1vert(list(zip(*data))) == 7 + 7

        data = ([ [False, True] * 5 ] * 2) + ([ [True, False] * 5 ] * 5) + ([ [False, True] * 5 ] * 3)

        assert qrencoder.QRUtil.maskScoreRule1vert(data) == 30

        data = [ [True, False] * 5 ] * 10

        assert qrencoder.QRUtil.maskScoreRule1vert(data) == 80

        data = [ [ False, True ] * 5 ] * 5 + [ [True, False] * 5 ] * 5

        assert qrencoder.QRUtil.maskScoreRule1vert(data) == 60

    def test_maskScoreRule2(self):
        # 3*(m-1)*(n-1) for each (non-overlapping) m*n box of unchanging color

        # No boxes
        data = [ [False, True] * 5, [True, False] * 5 ] * 5

        assert qrencoder.QRUtil.maskScoreRule2(data) == 0

        # 1 2x2 box = 3
        data = [ [False, False, True, False, True, False, True, False, True, False],
                 [False, False, False, True, False, True, False, True, False, True],
                 ] + [ [ True, False ] * 5 ] * 8

        assert qrencoder.QRUtil.maskScoreRule2(data) == 3


        # 1 2x2 box = 3
        data = [ [True, True, True, False, True, False, True, False, True, False],
                 [True, True, False, True, False, True, False, True, False, True],
                 ] + [ [ True, False ] * 5 ] * 8

        assert qrencoder.QRUtil.maskScoreRule2(data) == 3

        # 1 2x3 box = 6
        data = [ [False, False, False, False, True, False, True, False, True, False],
                 [False, False, False, True, False, True, False, True, False, True],
                 ] + [ [ True, False ] * 5 ] * 8

        assert qrencoder.QRUtil.maskScoreRule2(data) == 6

        # 1 2x3 box at end = 6
        data =  ([ [ True, False ] * 5 ] * 8
                 ) + [
            [False, False, False, False, True, False, True, False, True, False],
            [False, False, False, True, False, True, False, True, False, True],
            ]

        assert qrencoder.QRUtil.maskScoreRule2(data) == 6

        # 1 10x10 box = 243
        data = [ [True] * 10 ] * 10

        assert qrencoder.QRUtil.maskScoreRule2(data) == 9*9*3

        # 1 10x10 box = 243
        data = [ [False] * 10 ] * 10

        assert qrencoder.QRUtil.maskScoreRule2(data) == 9*9*3

    def test_maskScoreRule3hor(self):
        # 10111010000 yields 40 points

        data = [ [False, True] * 5, [True, False] * 5 ] * 5

        assert qrencoder.QRUtil.maskScoreRule3hor(data) == 0

        row = [True, False, True, True, True, False, True,
               False, False, False, False, False, False, False]
        data = [row[i:] + row[:i] for i in range(len(row))]

        assert qrencoder.QRUtil.maskScoreRule3hor(data) == 3 * 40

    def test_maskScoreRule4(self):
        # Proportion of dark:light in symbol
        # 10 points for every 5% from 50%

        data = [ [False, True] * 5, [True, False] * 5 ] * 5

        assert qrencoder.QRUtil.maskScoreRule4(data) == 0

        data = [ [True] * 10 ] * 10

        assert qrencoder.QRUtil.maskScoreRule4(data) == 100

        data = [ [False] * 10 ] * 10

        assert qrencoder.QRUtil.maskScoreRule4(data) == 100

        data = [ [False] * 10 ] * 6 + [ [True] * 10 ] * 4

        assert qrencoder.QRUtil.maskScoreRule4(data) == 20

class TestQRCode(object):

    def test_calculate_version(self):
        qr = qrencoder.QRCode(None, qrencoder.QRErrorCorrectLevel.L)

        testdata = [
            (qrencoder.QRNumber('1'*41), 1),    # 137 bits + overhead
            (qrencoder.QRNumber('1'*42), 2),    # 140 bits
            (qrencoder.QRAlphaNum('A'*25), 1),  # 138 bits
            (qrencoder.QRAlphaNum('A'*26), 2),  # 144 bits
            (qrencoder.QR8bitByte('a'*17), 1),  # 136 bits
            (qrencoder.QR8bitByte('a'*18), 2),  # 144 bits
            (qrencoder.QRKanji(u'ク'*10), 1),   # 130 bits
            (qrencoder.QRKanji(u'ク'*11), 2),   # 143 bits
            ]

        for qrdata, version in testdata:
            qr.dataList = [qrdata]
            assert qr.calculate_version() == version

class FakeBuffer(object):
    def __init__(self):
        self.data = []

    def put(self, data, bits):
        self.data.append((data,bits))

class TestQRKanji(object):

    def test_unicode_to_qrkanji(self):
        qrk = qrencoder.QRKanji('')
        testdata = [
            (u'a', UnicodeEncodeError),
            (u'‽', UnicodeEncodeError),
            (u'、', 1),
            (u'ク', 398),
            (u'滌', 5948),
            (u'漾', 5952),
            (u'熙', 7972),
            ]

        for data, value in testdata:
            if isinstance(value, type) and issubclass(value, Exception):
                py.test.raises(value, qrk.unicode_to_qrkanji, data)
            else:
                c = qrk.unicode_to_qrkanji(data)
                assert c == [value]

    def test_bits(self):
        qrk = qrencoder.QRKanji(u'熙')

        buf = FakeBuffer()
        qrk.write(buf, 1)

        assert buf.data == [
            (0x8, 4),  # Kanji mode
            (0x1, 8),  # 1 char
            (7972, 13)
            ]

class TestQRHanzi(object):

    def test_unicode_to_qrhanzi(self):
        qrk = qrencoder.QRHanzi('')
        testdata = [
            (u'a', UnicodeEncodeError),
            (u'‽', UnicodeEncodeError),
            (u'、', 1),
            (u'ク', 398),
            (u'漾', 4217),
            (u'熙', 3924),
            ]

        for data, value in testdata:
            if isinstance(value, type) and issubclass(value, Exception):
                py.test.raises(value, qrk.unicode_to_qrhanzi, data)
            else:
                c = qrk.unicode_to_qrhanzi(data)
                assert c == [value]

    def test_bits(self):
        qrk = qrencoder.QRHanzi(u'\u963f')

        buf = FakeBuffer()
        qrk.write(buf, 1)

        assert buf.data == [
            (0xD, 4),  # Hanzi mode
            (1, 4),    # Subset 1, GB2312
            (1, 8),    # 1 character
            (0x3C1, 13)
            ]

class TestQRECI(object):

    def test_bits1(self):
        qrk = qrencoder.QRECI(2)

        buf = FakeBuffer()
        qrk.write(buf, 1)

        assert buf.data == [
            (0x7, 4),  # ECI mode
            (2, 8)     # ECI 2
            ]

    def test_bits2(self):
        qrk = qrencoder.QRECI(0x82)

        buf = FakeBuffer()
        qrk.write(buf, 1)

        assert buf.data == [
            (0x7, 4),  # ECI mode
            (0x8082, 16)
            ]


    def test_bits2b(self):
        qrk = qrencoder.QRECI(0x382)

        buf = FakeBuffer()
        qrk.write(buf, 1)

        assert buf.data == [
            (0x7, 4),  # ECI mode
            (0x8382, 16)
            ]

    def test_bits3(self):
        qrk = qrencoder.QRECI(0x8123)

        buf = FakeBuffer()
        qrk.write(buf, 1)

        assert buf.data == [
            (0x7, 4),  # ECI mode
            (0xC08123, 24)
            ]

class TestQRNumber(object):

    def test_valid(self):
        qrk = qrencoder.QRNumber('')

        assert qrk.valid('1')
        assert qrk.valid('01234567890')
        assert not qrk.valid('a')
        assert not qrk.valid('a1')
        assert not qrk.valid('1a')

    def test_bits1(self):
        qrk = qrencoder.QRNumber('1')

        buf = FakeBuffer()
        qrk.write(buf, 1)

        assert buf.data == [
            (0x1, 4),  # Number mode
            (1, 10),   # 1 char
            (1, 4)
            ]

    def test_bits2(self):
        qrk = qrencoder.QRNumber('12')

        buf = FakeBuffer()
        qrk.write(buf, 1)

        assert buf.data == [
            (0x1, 4),  # Number mode
            (2, 10),   # 1 char
            (12, 7)
            ]

    def test_bits1(self):
        qrk = qrencoder.QRNumber('123')

        buf = FakeBuffer()
        qrk.write(buf, 1)

        assert buf.data == [
            (0x1, 4),  # Number mode
            (3, 10),   # 1 char
            (123, 10)
            ]

class TestQRAlphaNum(object):

    def test_valid(self):
        qrk = qrencoder.QRAlphaNum('')

        assert qrk.valid('A')
        assert qrk.valid('ABCDEFGHI')
        assert not qrk.valid('a')
        assert not qrk.valid('a1')
        assert not qrk.valid('1a')

    def test_bits1(self):
        qrk = qrencoder.QRAlphaNum('A')

        buf = FakeBuffer()
        qrk.write(buf, 1)

        assert buf.data == [
            (0x2, 4),  # AlphaNum mode
            (1, 9),    # 1 char
            (10, 6)    # A
            ]

    def test_bits2(self):
        qrk = qrencoder.QRAlphaNum('AB')

        buf = FakeBuffer()
        qrk.write(buf, 1)

        assert buf.data == [
            (0x2, 4),  # AlphaNum mode
            (2, 9),    # 1 char
            (461, 11)  # A + B
            ]

class TestQR8bitByte(object):

    def test_bits(self):
        qrk = qrencoder.QR8bitByte('a')

        buf = FakeBuffer()
        qrk.write(buf, 1)

        assert buf.data == [
            (0x4, 4),  # 8bitByte mode
            (1, 8),    # 1 char
            (0x61, 8)  # 'a'
            ]

class TestQRStructAppend(object):

    def test_bits(self):

        qrk = qrencoder.QRStructAppend(1, 2, 0x3f)

        buf = FakeBuffer()
        qrk.write(buf, 1)

        assert buf.data == [
            (0x3, 4),   # Structured append mode
            (1, 4),
            (2, 4),
            (0x3f, 8)
            ]

class TestQRFNC1First(object):

    def test_bits(self):
        qrk = qrencoder.QRFNC1First()

        buf = FakeBuffer()
        qrk.write(buf, 1)

        assert buf.data == [
            (0x5, 4)
            ]

class TestQRFNC1Second(object):

    def test_valid(self):
        qrk = qrencoder.QRFNC1Second('42')

        assert qrk.valid('A')
        assert not qrk.valid('ABCDEFGHI')
        assert qrk.valid('a')
        assert not qrk.valid('a1')
        assert qrk.valid('11')
        assert not qrk.valid('1')

    def test_bits1(self):
        qrk = qrencoder.QRFNC1Second('37')

        buf = FakeBuffer()
        qrk.write(buf, 1)

        assert buf.data == [
            (0x9, 4),
            (37, 8)
            ]

    def test_bits2(self):
        qrk = qrencoder.QRFNC1Second('a')

        buf = FakeBuffer()
        qrk.write(buf, 1)

        assert buf.data == [
            (0x9, 4),
            (0x61+100, 8)
            ]
