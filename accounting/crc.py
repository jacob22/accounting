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

# This is the SIE checksum calculation as translated from the C
# implementation in the standards document

CRC32_POLYNOMIAL = 0xedb88320

CRCTable = []

# Denna rutin skall anropas för att initiera lookup-tabellen
# innan beräkningen påbörjas

for i in range(256):
    crc = i
    for j in range(8):
        if crc & 1:
            crc = ( crc >> 1 ) ^ CRC32_POLYNOMIAL
        else:
            crc >>= 1
    CRCTable.append(crc)

class Crc(object):
    def __init__(self):
        self.reset()

    # Denna rutin anropas för varje textdel som ska ingå
    # i kontrollsumman
    def crc(self, buffer):
        #print '"'+buffer+'"'
        for c in buffer:
            try:
                c = ord(c)  # python 2
            except TypeError:
                pass  # python 3
            temp1 = ( self.crc_value >> 8 ) & 0x00ffffff
            temp2 = CRCTable[ (self.crc_value ^ c) & 0xff ]
            self.crc_value = temp1 ^ temp2
        #with open('apa', 'a') as fp:
        #    fp.write('%x %s\n' % (self.crc_value, buffer))

    def reset(self):
        self.crc_value = 0xffffffff

    # Denna rutin avslutar CRC-beräkningen samt returnerar det
    # resulterande CRC-värdet.
    def finalize(self):
        # Gör postkonditionering av det ackumulerade CRC-värdet genom
        # att bitinvertera enligt postkonditioneringsmasken
        return self.crc_value ^ 0xffffffff

