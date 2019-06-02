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

import decimal, json, os, py
from .. import direct
import pytransact.blm, pytransact.testsupport
from pytransact.queryops import *
import blm.fundamental, blm.accounting


def setup_module(module):
    pytransact.blm.addBlmPath(os.path.join(os.path.dirname(__file__), 'blm'))
    import blm.testblm


class FakeRequest(object):
    def __init__(self, data):
        self.data = json.dumps(data)


class TestAPI(object):

    def test_api(self):
        result = direct.api('/router/', ['testblm.Foo', 'testblm.Bar', 'testblm.method1'])
        result = result.splitlines()
        assert result[0] == "Ext.ns('blm.testblm')"
        result[1] = result[1][len('Ext.Direct.addProvider('):]
        result[-1] = result[-1][:-1]

        api = json.loads('\n'.join(result[1:]))
        assert api == {
            'url': '/router/testblm',
            'type': 'remoting',
            'namespace': 'blm.testblm',
            'maxRetries': 0,
            'actions': {'Foo': [{ 'name': 'create', 'len':1},
                                { 'name': 'read', 'len':1},
                                { 'name': 'update', 'len':1},
                                { 'name': 'destroy', 'len':1}],
                        'Bar': [{ 'name': 'create', 'len':1},
                                { 'name': 'read', 'len':1},
                                { 'name': 'update', 'len':1},
                                { 'name': 'destroy', 'len':1}],
                        'method1': [{ 'name': 'call', 'len': 0}]}
            }


class TestRouter(pytransact.testsupport.BLMTests):

    def setup_method(self, method):
        super(TestRouter, self).setup_method(method)
        self.router = direct.Router(self.database, None)

    def test_route(self):
        calls = []
        self.router.do_read = lambda *args: calls.append(args) or 'read_result'
        self.router.do_create = lambda *args: calls.append(args) or 'create_result'

        request = FakeRequest([{'tid': 1, 'action': 'Verification',
                                'method': 'read', 'data': ['foo']},
                               {'tid': 2, 'action': 'Transaction',
                                'method': 'create', 'data': ['bar']}
                               ])
        result = self.router.route('accounting', request)

        result = json.loads(result)
        assert result == [{'type':'rpc',
                           'tid': 1,
                           'action': 'Verification',
                           'method': 'read',
                           'result': 'read_result'},
                          {'type':'rpc',
                           'tid': 2,
                           'action': 'Transaction',
                           'method': 'create',
                           'result': 'create_result'}]

        assert calls == [('accounting', 'Verification', ['foo']),
                         ('accounting', 'Transaction', ['bar'])]

    def test_do_call(self):
        result = self.router.do_call('testblm', 'method1', [])
        assert result == [{'name': 'method1'}]

    def test_do_create(self):
        result = self.router.do_create('testblm', 'Foo',
                                       [[{'string': ['foo'], 'decimal': [250]},
                                         {'string': ['bar'], 'decimal': [375]}]])

        foos = blm.testblm.Foo._query().run()
        foos.sort(key=lambda toi: toi['string'][0])
        foos.reverse()
        assert len(foos) == 2
        assert foos[0].string == ['foo']
        assert foos[0].decimal == [decimal.Decimal('2.50')]
        assert foos[1].string == ['bar']
        assert foos[1].decimal == [decimal.Decimal('3.75')]

        assert len(result) == 2
        assert result == {
            'success': True,
            'tois': [{'id': [str(foos[0].id[0])],
                      'allowRead': [],
                      'int': [],
                      'string': ['foo'],
                      'decimal': [250],
                      'decimalmap': {},
                      'toirefmap': {}},
                     {'id': [str(foos[1].id[0])],
                      'allowRead': [],
                      'int': [],
                      'string': ['bar'],
                      'decimal': [375],
                      'decimalmap': {},
                      'toirefmap': {}}]
            }

    def test_do_destroy(self):
        foo = blm.testblm.Foo()
        self.commit()

        result = self.router.do_destroy(
            'testblm', 'Foo',
            [{'id': [str(foo.id[0])]}])
        assert result == {'success': True} # ???

        assert not blm.testblm.Foo._query().run()

        foo = blm.testblm.Foo()
        bar = blm.testblm.Foo()
        baz = blm.testblm.Foo()
        self.commit()

        result = self.router.do_destroy(
            'testblm', 'Foo',
            [[{'id': [str(foo.id[0])]}, {'id': [str(bar.id[0])]}]])
        assert result == {'success': True}

        assert blm.testblm.Foo._query().run() == [baz]

    def test_destroy_with_error(self):
        bar = blm.testblm.Bar(dont_delete=[True])
        self.commit()

        result = self.router.do_destroy(
            'testblm', 'Bar',
            [{'id': [str(bar.id[0])]}])
        assert result == {'success': False}

        assert blm.testblm.Bar._query().run()

    def test_do_read_by_id(self):
        foo = blm.testblm.Foo(string=['foo'], decimal=['42.27'],
                              decimalmap={'foo': '27.12'})
        self.commit()

        result = self.router.do_read(
            'testblm', 'Foo',
            [{'id': str(foo.id[0]),
              'attributes': ['string', 'decimal', 'decimalmap']}])
        assert result == {
            'success': True,
            'tois': [{'id': [str(foo.id[0])],
                       'string': ['foo'], 'decimal': [4227],
                       'decimalmap': {'foo': 2712}}]
            }

        result = self.router.do_read(
            'testblm', 'Foo',
            [{'id': None, 'attributes': []}])
        assert result == {'success': False, 'tois': []}

    def test_do_read_with_filter(self):
        foo = blm.testblm.Foo(string=['foo'], decimal=['42.27'])
        bar = blm.testblm.Foo(string=['bar'], decimal=['42.27'])
        self.commit()

        result = self.router.do_read(
            'testblm', 'Foo',
            [{'attributes': ['string', 'decimal'],
              'filter': [{'property': 'string', 'value': 'foo'}]}])
        assert result == {
            'success': True,
            'tois': [{'id': [str(foo.id[0])],
                      'string': ['foo'], 'decimal': [4227]}]
            }

    def test_do_read_with_query(self):
        foo = blm.testblm.Foo(string=['foo'], decimal=['42.27'])
        bar = blm.testblm.Foo(string=['bar'], decimal=['42.27'])
        self.commit()

        result = self.router.do_read(
            'testblm', 'Foo',
            [{'attributes': ['string', 'decimal'], 'query': {'string': 'foo'}}])
        assert result == {
            'success': True,
            'tois': [{'id': [str(foo.id[0])],
                      'string': ['foo'], 'decimal': [4227]}]}

    def test_do_read_with_filter_and_query(self):
        foo1 = blm.testblm.Foo(string=['foo'], int=[1])
        foo2 = blm.testblm.Foo(string=['foo'], int=[2])
        bar1 = blm.testblm.Foo(string=['bar'], int=[1])

        self.commit()

        result = self.router.do_read(
            'testblm', 'Foo',
            [{'attributes': ['string', 'int'],
              'filter': [{'property': 'int', 'value': 1}],
              'query': {'string': 'foo'}}])
        assert result == {
            'success': True,
            'tois': [{'id': [str(foo1.id[0])],
                      'string': ['foo'], 'int': [1]}]}

    def test_do_read_with_like(self):
        foo = blm.testblm.Foo(string=['foo'])
        bar = blm.testblm.Foo(string=['bar'])
        baz = blm.testblm.Foo(string=['baz'])
        self.commit()

        result = self.router.do_read(
            'testblm', 'Foo',
            [{'attributes': ['string'],
              'like': {'string': 'ba*'},
              'sort': [{'property': 'string', 'direction': 'ASC'}]}])
        assert result == {
            'success': True,
            'tois': [
                {'id': [str(bar.id[0])], 'string': ['bar']},
                {'id': [str(baz.id[0])], 'string': ['baz']}
                ]
            }

    def test_do_read_with_sort(self):
        foo = blm.testblm.Foo(string=['foo'], int=[1])
        bar = blm.testblm.Foo(string=['bar'], int=[2])
        self.commit()

        result = self.router.do_read(
            'testblm', 'Foo',
            [{'attributes': ['string', 'int'],
              'sort': [{'property': 'int', 'direction': 'ASC'}]}])
        assert result == {
            'success': True,
            'tois': [
                {'id': [str(foo.id[0])], 'string': ['foo'], 'int': [1]},
                {'id': [str(bar.id[0])], 'string': ['bar'], 'int': [2]}
                ]
            }

        result = self.router.do_read(
            'testblm', 'Foo',
            [{'attributes': ['string', 'int'],
              'sort': [{'property': 'int', 'direction': 'DESC'}]}])
        assert result == {
            'success': True,
            'tois': [
                {'id': [str(bar.id[0])], 'string': ['bar'], 'int': [2]},
                {'id': [str(foo.id[0])], 'string': ['foo'], 'int': [1]}
                ]
            }

        result = self.router.do_read(
            'testblm', 'Foo',
            [{'attributes': ['string', 'int'],
              'sort': [{'property': 'string', 'direction': 'ASC'}]}])
        assert result == {
            'success': True,
            'tois': [
                {'id': [str(bar.id[0])], 'string': ['bar'], 'int': [2]},
                {'id': [str(foo.id[0])], 'string': ['foo'], 'int': [1]}
                ]
            }

        result = self.router.do_read(
            'testblm', 'Foo',
            [{'attributes': ['string', 'int'],
              'sort': [{'property': 'string', 'direction': 'DESC'}]}])
        assert result == {
            'success': True,
            'tois': [
                {'id': [str(foo.id[0])], 'string': ['foo'], 'int': [1]},
                {'id': [str(bar.id[0])], 'string': ['bar'], 'int': [2]}
                ]
            }

        # sort by id
        result = self.router.do_read(
            'testblm', 'Foo',
            [{'attributes': [],
              'sort': [{'property': 'id', 'direction': 'ASC'}]}])
        assert result == {
            'success': True,
            'tois': [
                {'id': [str(foo.id[0])]},
                {'id': [str(bar.id[0])]}
                ]
            }

    def test_update(self):
        foo = blm.testblm.Foo(string=['foo'], decimal=['42.27'])
        self.commit()

        res = self.router.do_update(
            'testblm', 'Foo',
            [{'string': ['bar'], 'id': [str(foo.id[0])],
              'decimalmap': {'foo': 1234}}])
        self.sync()

        assert res == {'success': True,
                       'tois': [{'string': ['bar'], 'id': [str(foo.id[0])],
                                 'decimalmap': {'foo': 1234}}]}

        bar, = blm.testblm.Foo._query().run()
        assert bar.id[0] == foo.id[0]
        assert bar.string == ['bar']
        assert bar.decimalmap['foo'] == decimal.Decimal('12.34')

    def test__get_toi_data(self):
        foo = blm.testblm.Foo()
        foo.toirefmap = {'me': foo}
        foo.string = ['foo']

        data = self.router._get_toidata(foo, foo._attributes)
        json.dumps(list(data)) # don't explode

        data = self.router._get_toidata(foo, ['string'], polymorph=False)
        assert data == {'id': [str(foo.id[0])], 'string': foo.string.value}

        data = self.router._get_toidata(foo, ['string', 'bazattr'], polymorph=True)
        assert data == {'id': [str(foo.id[0])], 'string': foo.string.value, '_toc': foo._fullname}

        baz = blm.testblm.Baz(bazattr=1)
        data = self.router._get_toidata(baz, ['string', 'bazattr'], polymorph=True)
        assert data == {'id': [str(baz.id[0])], 'string': [], 'bazattr': [1], '_toc': baz._fullname}

        py.test.raises(AttributeError, self.router._get_toidata, foo, ['bazattr'], polymorph=False)


class Test_filter2cond(object):

    def _getOp(self, id='someid', property='someattr', value='someval'):
        filter = dict(id=id, property=property, value=value)
        return direct.filter2cond(filter)

    def test_simple(self):
        attr, cond = self._getOp('someid', 'someattr', 'someval')
        assert attr == 'someattr'
        assert cond == 'someval'

    def test_ignore(self):
        filter = dict(id='someid', property='whatever')
        py.test.raises(direct.IgnoreFilter, direct.filter2cond, filter)

        filter = dict(id='someid', value='whatever')
        py.test.raises(direct.IgnoreFilter, direct.filter2cond, filter)

    def test_Unknown(self):
        filter = dict(id='someid', property='whatever', value={'op': 'Unknown'})
        py.test.raises(ValueError, direct.filter2cond, filter)

    def test_Empty(self):
        attr, op = self._getOp(value={'op': 'Empty'})
        assert op == Empty()

    def test_NotEmpty(self):
        attr, op = self._getOp(value={'op': 'NotEmpty'})
        assert op == NotEmpty()
