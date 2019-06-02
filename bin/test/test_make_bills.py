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

import py
import members.billing
from .. import make_bills

def test_main(monkeypatch):
    calls = []
    def bootstrap_products(_self):
        calls.append('bootstrap')
    def process(_self, year):
        calls.append('process')
        assert year == '2011'

    monkeypatch.setattr(members.billing.Billing, 'bootstrap_products',
                        bootstrap_products)
    monkeypatch.setattr(members.billing.Billing, 'process', process)

    make_bills.main(['make_bills.py', '2011'])
    assert calls == ['bootstrap', 'process']

    py.test.raises(ValueError, make_bills.main, ['make_bills.py', 'abcd'])
    py.test.raises(ValueError, make_bills.main, ['make_bills.py', '12'])
    py.test.raises(ValueError, make_bills.main, ['make_bills.py', '201301'])
