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

def luhn_checksum(digits):
    # Check a number with a standard mod10 check digit at the end
    # (i.e. org.nr, pers.nr, OCR-nr, etc)
    # Returns the checksum (0 if correct)

    def onetwo():
        while 1:
            yield 1
            yield 2

    digits = list(map(int, str(digits)))
    digits.reverse()
    digits = [ x*y for x,y in zip(digits, onetwo()) ]
    digits = [ sum(divmod(x, 10)) for x in digits ]
    checksum = sum(digits) % 10
    return (10 - checksum) % 10


def add_control_digits(number, include_length=True):
    """Add luhn checksum at the end of a number, and (optionally) include
    a length digit on the second last position, before the checksum."""
    s = str(number)
    if include_length:
        s += str((len(number) + 2) % 10)
    return s + str(luhn_checksum(s + '0'))


def add_luhn_checksum(number):
    "Add luhn checksum at the end of a number"
    return add_control_digits(number, include_length=False)


if __name__ == '__main__':
    import sys
    for arg in sys.argv[1:] or sys.stdin:
        print(arg, luhn_checksum(arg))
