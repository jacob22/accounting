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
# encode/decode integers using base64 notation
#

import string
_alphabet = string.ascii_uppercase + string.ascii_lowercase + string.digits + '-_'

from base64 import _b32alphabet

try:
    _b32alphabet = _b32alphabet.items()
    _b32alphabet.sort()
except AttributeError:
    _b32alphabet = list(enumerate(_b32alphabet))
_b32tab = [v for k, v in _b32alphabet]
_b32rev = dict([(v, k) for k, v in _b32alphabet])

def encode32(l):
    result = []
    while l:
        result.append(_b32tab[l & 0x1F])
        l >>= 5

    return ''.join(result)

def encode(l):
    result = []
    while l:
        result.append(_alphabet[l & 0x3F])
        l >>= 6

    return ''.join(result)

def decode32(s):
    result = 0
    for c in reversed(s):
        result <<= 5
        result |= _b32rev[c]

    return result


def decode(s):
    result = 0
    for c in reversed(s):
        result <<= 6
        result |= _alphabet.index(c)

    return result
