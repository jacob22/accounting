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

from accounting import luhn

def test_luhn_checksum():
    assert luhn.luhn_checksum(1) == 9
    assert luhn.luhn_checksum(11) == 7
    assert luhn.luhn_checksum(111) == 6
    assert luhn.luhn_checksum(1111) == 4
    assert luhn.luhn_checksum(11111) == 3
    assert luhn.luhn_checksum(111111) == 1
    assert luhn.luhn_checksum(1111111) == 0
    # open end org no
    assert luhn.luhn_checksum(5566092473) == 0
    # wikipedia example
    assert luhn.luhn_checksum(79927398713) == 0

    assert luhn.luhn_checksum(7) == 3
    assert luhn.luhn_checksum(75) == 0


def test_add_control_digits(monkeypatch):
    assert luhn.add_control_digits('1') == '133'
    assert luhn.add_control_digits('11') == '1149'
    assert luhn.add_control_digits('13') == '1347'

    monkeypatch.setattr(luhn, 'luhn_checksum', lambda x: '0')
    assert luhn.add_control_digits('1') == '130'
    assert luhn.add_control_digits('11') == '1140'
    assert luhn.add_control_digits('111') == '11150'
    assert luhn.add_control_digits('1111') == '111160'


def test_add_luhn_checksum():
    assert luhn.add_luhn_checksum(1) == '18'
    assert luhn.add_luhn_checksum(11) == '117'
    assert luhn.add_luhn_checksum(111) == '1115'
    assert luhn.add_luhn_checksum(1111) == '11114'
    assert luhn.add_luhn_checksum(11111) == '111112'
    assert luhn.add_luhn_checksum(556609247) == '5566092473'
    # wikipedia example
    assert luhn.add_luhn_checksum(7992739871) == '79927398713'
