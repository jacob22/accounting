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

import datetime

def fakeResponseSuccess(lines):
    response = []
    today = datetime.datetime.now().strftime('%y%m%d')
    for line in lines:
        tk = line[:2]
        new = False
        if tk == '00':
            pass
        elif tk == '11':
            new = bytearray(line, 'latin-1')
            new[40:46] = bytearray(today, 'latin-1')
            new[46:47] = b'1' # report_code
        elif tk == '14':
            new = bytearray(line, 'latin-1')
            # Payment type code. C = Supplier payments
            new[49:50] = b'C'
            # Referenced bankgiro number (recipient bgnum changed), or zeros.
            new[50:60] = b'0000000000'
        elif tk == '29':
            new = bytearray(line, 'latin-1')
        elif tk == '99':
            pass
        if new:
            if PYT3:
                response.append(new.decode('latin-1'))
            else:
                response.append(str(new))
    return response

def fakeResponseRejected(lines):
    response = []
    today = datetime.datetime.now().strftime('%y%m%d')
    for line in lines:
        tk = line[:2]
        new = False
        if tk == '00':
            pass
        elif tk == '11':
            new = bytearray(line, 'latin-1')
            new[40:46] = bytearray(today, 'latin-1')
            new[46:47] = b'6' # report_code
        elif tk == '14':
            #Preserve line, append rejection Comment record (TK49)
            if PYT3:
                response.append(line)
            else:
                response.append(str(line))
            new = bytearray(' '*80+'\r\n', 'latin-1')
            new[0:2] = b'49' #TK49
            new[2:6] =  b'MTRV'  # Alphabetical error code
            new[6:10] = b'0082' # Numerical error code
            new[10:65] = b'Stopped after balance check inquiry. Contact your bank.' # Plain text error description
        elif tk == '29':
            new = bytearray(line, 'latin-1')
            #new[12:20] # number of rejected Payment records (TK14-TK17, TK54), zero filled.
        elif tk == '99':
            pass
        if new:
            if PYT3:
                response.append(new.decode('latin-1'))
            else:
                response.append(str(new))
    return response
