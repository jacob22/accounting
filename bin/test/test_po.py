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

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO
import json
import os
from .. import po2json


here = os.path.dirname(__file__)


def test_main():
    out = StringIO()
    po2json.main(['', os.path.join(here, 'test.po')], out)
    out.seek(0)
    lines = out.readlines()
    prefix = lines[0]
    data = lines[1:-1]
    suffix = lines[-1]

    assert prefix == 'define([], function() {\n'
    assert suffix == '});\n'
    translations = json.loads(''.join(data))
    assert translations == {
        u'Hello, world!': [
            None, u'Hej, världen!'
        ],
        u'<div class="greeting">Hello, world!</div>': [
            None, u'<div class="greeting">Hej, världen!</div>'
        ]
    }
