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

from .. import base64long

def test_encode_decode():
    expected = [
        (1, 'B'),
        (64, 'AB'),
        (1<<(6*20), 'A'*20 + 'B')
        ]

    for l, s in expected:
        rs = base64long.encode(l)
        assert rs == s
        rl = base64long.decode(s)
        assert rl == l
