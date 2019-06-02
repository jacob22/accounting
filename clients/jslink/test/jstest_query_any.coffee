/*
Copyright 2019 Open End AB

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
*/

Tests = new Deferred()

require(['jslink/query', 'signals'], (query, signals) ->

    Tests.callback(

        test_operator_between: ->
            op = new query.Operator.Between(1, 2)
            aisDeeply(op.value, [1, 2])

        test_operator_like: ->
            op = new query.Operator.Like('abc*')
            aisDeeply(op.value, 'abc*')

        test_query_construction: ->
            jsLink = {}
            qry = new query.Query(jsLink, "Foo", {'a': new query.Operator.Like("abc*")})
            ais(qry.condGroups.length, 1)
            ais(qry.condGroups[0]['_cls_'], 'ConditionGroup')
            ais(qry.condGroups[0].a.length, 1)
            ais(qry.condGroups[0].a[0]['_cls_'], 'Like')
            ais(qry.condGroups[0].a[0]['value'], "abc*")

            qry = new query.Query(jsLink, "Foo")
            qry.push({'a': [new query.Operator.Like("abc*")]})
            ais(qry.condGroups.length, 1)
            ais(qry.condGroups[0]['_cls_'], 'ConditionGroup')
            ais(qry.condGroups[0].a.length, 1)
            ais(qry.condGroups[0].a[0]['_cls_'], 'Like')
            ais(qry.condGroups[0].a[0]['value'], "abc*")

        test_update_success: ->
            q = new query.Query('Foo')
            check = null
            signals.connect(q, 'update', (add, remove) ->
                check = [Object.keys(add), Object.keys(remove)]
            )
            q._update({'add': {1: null, 2: null}, 'del': {}})
            aisDeeply(Object.keys(q.result),  [1, 2])
            aisDeeply(check, [[1, 2], []])

            q._update({'add': {3: null}, 'del': {1: null}})
            aisDeeply(Object.keys(q.result),  [2, 3])
            aisDeeply(check, [[3], [1]])

            # xxx test error checking

        test_sorted_construction: () ->
            jsLink = {}
            qry = new query.SortedQuery(jsLink, "Foo",
                {'a': new query.Operator.Like("abc*")})
            qry.sorting = "priority"
            ais(qry.tocName, "Foo")
            ais(qry.sorting, "priority")
            ais(qry.condGroups.length, 1)
            ais(qry.condGroups[0]['_cls_'], 'ConditionGroup')
            ais(qry.condGroups[0].a.length, 1)
            ais(qry.condGroups[0].a[0]['_cls_'], 'Like')
            ais(qry.condGroups[0].a[0]['value'], "abc*")
            ais(qry.gotResult, 0)

            qry = new query.SortedQuery(jsLink, "Foo")
            qry.sorting = "priority"
            qry.push({'a': [new query.Operator.Like("abc*")]})
            ais(qry.tocName, "Foo")
            ais(qry.sorting, "priority")
            ais(qry.condGroups.length, 1)
            ais(qry.condGroups[0]['_cls_'], 'ConditionGroup')
            ais(qry.condGroups[0].a.length, 1)
            ais(qry.condGroups[0].a[0]['_cls_'], 'Like')
            ais(qry.condGroups[0].a[0]['value'], "abc*")
            ais(qry.gotResult, 0)


        test_sorted_update_toilist: ->
            q = new query.SortedQuery("Foo")
            q.sorting = "priority"
            check = null
            signals.connect(q, 'update', (add, remove, moved, opcodes) ->
                check = [
                    Object.keys(add).sort(),
                    Object.keys(remove).sort(),
                    Object.keys(moved).sort(),
                    opcodes
                ]
            )

            dummyDiff = {'attrs': {'foo': ['FOO']}}

            ops = [[0,0,[1,2,4,5]]]
            q._update({'diffops': ops, 'toiDiffs': {
                1: dummyDiff, 2: dummyDiff,
                4: dummyDiff, 5: dummyDiff
            }})
            aisDeeply(q.result,  [1,2,4,5])
            aisDeeply(check, [[1, 2, 4, 5], [], [], ops])
            aisDeeply(keys(q.toiData).sort(), ['1', '2', '4', '5'])
            ais(q.gotResult, 1)

            ops = [[0,2,[]], [2,2,[3]]]
            q._update({'diffops': ops, 'toiDiffs': {3: dummyDiff}})
            aisDeeply(q.result,  [3,4,5])
            aisDeeply(check, [[3], [1, 2], [], ops])
            aisDeeply(keys(q.toiData).sort(), ['3', '4', '5'])
            ais(q.gotResult, 2)

            ops = [[0,3,[]], [3,3,[2, 3]]]
            q._update({'diffops': ops, 'toiDiffs': {2: dummyDiff}})
            aisDeeply(q.result,  [2,3])
            aisDeeply(check, [[2], [4, 5], [3], ops])
            aisDeeply(keys(q.toiData).sort(), ['2', '3'])
            ais(q.gotResult, 3)

        test_sorted_update_toidata: ->
            jsLink = {}
            q = new query.SortedQuery(jsLink, "Foo")
            q.sorting = "priority"
            check = []
            signals.connect(q, 'update', (add, remove, moved, opcodes, toiDiffs) ->
                check.push(toiDiffs)
            )

            toidiff = {'attrs': {'a': [3], 'b': [5]}}

            q._update({'diffops': [], 'toiDiffs': { 11: toidiff }})

            checkMe = check.pop()
            aisDeeply(checkMe, { 11: toidiff })
            aisDeeply(q.toiData, {11: {'_id': [11], 'a': [3], 'b': [5]}})
            aok(check.length == 0)
            ais(q.gotResult, 1)

            toidiff = {'attrs': {'a': [1]}}
            q._update({'diffops': [], 'toiDiffs': { 11: toidiff }})

            checkMe = check.pop()
            aisDeeply(checkMe, { 11: toidiff })
            aisDeeply(q.toiData, {11: {'_id': [11], 'a': [1], 'b': [5]}})
            aok(check.length == 0)
            ais(q.gotResult, 2)

    )
)
