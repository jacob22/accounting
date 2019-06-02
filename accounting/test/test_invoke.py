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

from pytransact.testsupport import BLMTests
import simplejson, os, flask
from werkzeug.datastructures import MultiDict

import pytransact.blm

from .. import invoke

import blm.fundamental

def setup_module(module):
    pytransact.blm.addBlmPath(os.path.join(os.path.dirname(__file__), 'blm'))
    import blm.testblm

def test__get_params_json():

    class Fake(object):
        def __init__(self, **kw):
            self.__dict__.update(kw)

    request = Fake(
        content_type='application/json; charset=UTF-8', # firefox sends charset
        mimetype='application/json',
        data='{"foo": ["bar"], "bar": ["baz"]}'
        )

    method = Fake(params=[Fake(name='foo'), Fake(name='bar')])

    params = invoke._get_params(request, method)
    assert params == [['bar'], ['baz']]


class TestInvoke(BLMTests):

    def test_invoke(self):
        import blm.testblm

        app = flask.Flask(__name__)

        with app.test_request_context('/?k1=foo&k1=bar&k2=baz'):
            res = invoke.invoke(flask.request, self.database, None,
                                'testblm', 'the_method')

        assert simplejson.loads(res.data) == { 'k1': ['foo', 'bar'],
                                               'k2': ['baz'] }

    def test_invoke_toi(self):
        import blm.testblm

        toi = blm.testblm.Foo(string='bar')
        self.commit()
        self.sync()

        app = flask.Flask(__name__)

        with app.test_request_context('/?k1=foo&k1=bar'):
            res = invoke.invoke_toi(flask.request, self.database, None,
                                toi.id[0], 'method1')

        assert simplejson.loads(res.data) == { 'k1': ['foo', 'bar'],
                                               'string': ['bar'] }
