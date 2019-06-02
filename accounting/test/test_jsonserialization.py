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

import json
from bson.objectid import ObjectId
import pytransact.query as q
from ..jsonserialization import JSONEncoder, JSONDecoder

def test_objectid():
    objectid = ObjectId()
    r = json.dumps(objectid, cls=JSONEncoder)
    assert r == '"%s"' % objectid


def test_exception():
    e = RuntimeError('everything is broken!')
    r = json.loads(json.dumps(e, cls=JSONEncoder))
    assert r == {'__class__': 'RuntimeError', 'args': ['everything is broken!']}


class TestDecoder(object):

    def setup_method(self, method):
        self.decoder = JSONDecoder()

    def test_decode_simple_query(self):
        data = json.dumps({
            '_cls_': 'Query',
            'toc': 'Foo',
            'cgs': [
                {
                    '_cls_': 'ConditionGroup',
                    'a': [{'_cls_': 'Like', 'value': 'abc*'}],
                    'b': [{'_cls_': 'Between', 'value': [1, 2]}]
                }
            ]
        })
        decoded = self.decoder.decode(data)
        query = q.Query('Foo', a=q.Like('abc*'), b=q.Between(1, 2))
        assert decoded == query
