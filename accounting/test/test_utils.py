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
from accounting import utils

def test_case_insinsensitive_dict():
    d = utils.cidict()
    d['Foo'] = 'foo'
    assert d['Foo'] == 'foo'
    assert d['foo'] == 'foo'
    assert d['fOo'] == 'foo'

    d.setdefault('bar', 'bar')
    assert d['Bar'] == 'bar'
    assert d['bar'] == 'bar'

    assert set(d.keys()) == {'Foo', 'bar'}

    with py.test.raises(KeyError):
        d['baz']

    # don't explode on non strings
    key, val = object(), object()
    d[key] = val
    assert d[key] is val

    # raise the right type of exception on non strings
    with py.test.raises(KeyError):
        d[object()]
