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

require ['jslink/ToiSetWatcher', 'jslink/ToiRequester', 'signals'], (ToiSetWatcher, ToiRequester, signals) ->

    tests =
        test_toi_set_watcher_logic: ->
            reqs = []

            class TestRequester extends ToiRequester

                _makeRequest: (toid) ->
                    deactivate: (what) ->
                    detach: ->

                track: (toid) ->
                    reqs.push ['track', toid]
                    super toid

                drop: (toid) ->
                    reqs.push ['drop', toid]
                    super toid

                destroy: ->
                    reqs.push 'DESTROY'
                    super

            gotCacheSize = null
            jsLink = {}

            tsw = new ToiSetWatcher jsLink, 'Foo', ['a', 'b'], 25,
                (jsLink, tocName, attrs, cacheSize, cb, errorh) ->
                    gotCacheSize = cacheSize
                    new TestRequester jsLink, tocName, attrs, cacheSize, cb, errorh

            ais gotCacheSize, 25

            calls = []

            tsw._watch 'first', [42]
            aisDeeply reqs, [['track', 42]]
            reqs = []

            tsw._notifyForget = (setId) ->
                calls.push ['forget', setId]

            tsw._notifyRefresh = (setId, toids) ->
                calls.push [setId, toids]

            aisDeeply keys(tsw.pending), ['first']
            aisDeeply keys(tsw.pending['first']), [42]

            tsw.requester._dataUpdate 42, {toiDiff: {attrs: {'a': [3], 'b': [5]}}}
            aisDeeply keys(tsw.pending['first']), []
            aisDeeply calls.pop(), ['first', [42]]

            aisDeeply tsw.getToiData(42), {'a': [3], 'b': [5]}

            tsw._watch 'second', [42, 43]
            aisDeeply reqs, [['track', 42], ['track', 43]]
            reqs = []

            aisDeeply keys(tsw.pending['first']), []
            aisDeeply keys(tsw.pending['second']), [43]

            tsw._watch 'third', [43, 44]
            aisDeeply reqs, [['track', 43], ['track', 44]]
            reqs = []

            aisDeeply keys(tsw.pending['first']), []
            aisDeeply keys(tsw.pending['second']), [43]
            thirdPending = keys(tsw.pending['third'])
            thirdPending.sort()
            aisDeeply thirdPending, [43, 44]

            tsw.requester._dataUpdate 43, {toiDiff: {attrs: {'a': [4], 'b': [6]}}}

            aisDeeply keys(tsw.pending['first']), []
            aisDeeply keys(tsw.pending['second']), []
            aisDeeply keys(tsw.pending['third']), [44]

            aisDeeply calls.pop(), ['second', [42, 43]]

            aisDeeply tsw.getToiData(42), {'a': [3], 'b': [5]}
            aisDeeply tsw.getToiData(43), {'a': [4], 'b': [6]}

            tsw._watch 'fourth', [43, 42]
            aisDeeply reqs, [['track', 43], ['track', 42]]
            aisDeeply keys(tsw.pending['fourth']), []
            reqs = []

            aisDeeply calls.pop(), ['fourth', [43, 42]]

            tsw._unwatch 'second'
            aisDeeply reqs, []

            aisDeeply calls.pop(), ['forget', 'second']

            aisDeeply keys(tsw.sets).sort(), ['first', 'fourth', 'third']
            aisDeeply keys(tsw.pending).sort(), ['first', 'fourth', 'third']

            ais keys(tsw.membership).length, 3
            aisDeeply keys(tsw.membership[42]).sort(), ['first', 'fourth']
            aisDeeply keys(tsw.membership[43]).sort(), ['fourth', 'third']
            aisDeeply keys(tsw.membership[44]).sort(), ['third']

            tsw._unwatch 'third'
            aisDeeply reqs, [['drop', 44]]
            aisDeeply calls, []
            reqs = []
            ais keys(tsw.membership).length, 2

            tsw._unwatch 'fourth'
            aisDeeply reqs, [['drop', 43]]
            ais keys(tsw.membership).length, 1
            aisDeeply calls, [['forget', 'fourth']]
            reqs = []

            tsw._watch('fifth', [45])
            tsw.requester._dataUpdate(45, {toiDiff: {attrs: {a: [5], b: [8]}}})
            aisDeeply(tsw.pending['fifth'], [])
            aisDeeply(tsw.sets['fifth'], [45])
            calls = []

            err =
                __class__: 'ToiNonexistantError'
                args: ['Foo', 45]
            errMsg = error: err
            tsw.requester._dataUpdate(45, errMsg)
            aisDeeply(tsw.pending['fifth'], [])
            aisDeeply(tsw.sets['fifth'], [])
            aok(!(45 in tsw.membership))
            aisDeeply(calls, [['fifth', []]])
            reqs = []

            tsw.destroy()
            aisDeeply reqs, ['DESTROY']


        test_toi_set_watcher_logic_duplicate: ->
            reqs = []

            class TestRequester extends ToiRequester

                _makeRequest: (toid) ->
                    deactivate: (what) ->
                    detach: ->

                track: (toid) ->
                    reqs.push ['track', toid]
                    super toid

                drop: (toid) ->
                    reqs.push ['drop', toid]
                    super toid

                destroy: ->
                    reqs.push 'DESTROY'
                    super

            gotCacheSize = null
            jsLink = {}

            tsw = new ToiSetWatcher jsLink, 'Foo', ['a', 'b'], 25,
                (jsLink, tocName, attrs, cacheSize, cb, errorh) ->
                    gotCacheSize = cacheSize
                    new TestRequester jsLink, tocName, attrs, cacheSize, cb, errorh

            ais gotCacheSize, 25

            calls = []

            tsw._watch 'first', [42, 42]
            aisDeeply reqs, [['track', 42], ['track', 42]]
            reqs = []

            tsw._notifyForget = (setId) ->
                calls.push ['forget', setId]

            tsw._notifyRefresh = (setId, toids) ->
                calls.push [setId, toids]

            aisDeeply keys(tsw.pending), ['first']
            aisDeeply keys(tsw.pending['first']), [42]

            tsw.requester._dataUpdate 42, {toiDiff: {attrs: {'a': [3], 'b': [5]}}}
            aisDeeply keys(tsw.pending['first']), []
            aisDeeply calls.pop(), ['first', [42, 42]]

            aisDeeply tsw.getToiData(42), {'a': [3], 'b': [5]}

            tsw._watch 'second', [42, 43, 43]
            aisDeeply reqs, [['track', 42], ['track', 43], ['track', 43]]
            reqs = []

            aisDeeply keys(tsw.pending['first']), []
            aisDeeply keys(tsw.pending['second']), [43]

            tsw._watch 'third', [43, 44, 44]
            aisDeeply reqs, [['track', 43], ['track', 44], ['track', 44]]
            reqs = []

            aisDeeply keys(tsw.pending['first']), []
            aisDeeply keys(tsw.pending['second']), [43]
            thirdPending = keys(tsw.pending['third'])
            thirdPending.sort()
            aisDeeply thirdPending, [43, 44]

            tsw.requester._dataUpdate 43, {toiDiff: {attrs: {'a': [4], 'b': [6]}}}

            aisDeeply keys(tsw.pending['first']), []
            aisDeeply keys(tsw.pending['second']), []
            aisDeeply keys(tsw.pending['third']), [44]

            aisDeeply calls.pop(), ['second', [42, 43, 43]]

            aisDeeply tsw.getToiData(42), {'a': [3], 'b': [5]}
            aisDeeply tsw.getToiData(43), {'a': [4], 'b': [6]}

            tsw._watch 'fourth', [43, 42, 43]
            aisDeeply reqs, [['track', 43], ['track', 42], ['track', 43]]
            aisDeeply keys(tsw.pending['fourth']), []
            reqs = []

            aisDeeply calls.pop(), ['fourth', [43, 42, 43]]

            tsw._unwatch 'second'
            aisDeeply reqs, []

            aisDeeply calls.pop(), ['forget', 'second']

            aisDeeply keys(tsw.sets).sort(), ['first', 'fourth', 'third']
            aisDeeply keys(tsw.pending).sort(), ['first', 'fourth', 'third']

            ais keys(tsw.membership).length, 3
            aisDeeply keys(tsw.membership[42]).sort(), ['first', 'fourth']
            aisDeeply keys(tsw.membership[43]).sort(), ['fourth', 'third']
            aisDeeply keys(tsw.membership[44]).sort(), ['third']

            tsw._unwatch 'third'
            aisDeeply reqs, [['drop', 44]]
            aisDeeply calls, []
            reqs = []
            ais keys(tsw.membership).length, 2

            tsw._unwatch 'fourth'
            aisDeeply reqs, [['drop', 43]]
            ais keys(tsw.membership).length, 1
            aisDeeply calls, [['forget', 'fourth']]
            reqs = []

            tsw.destroy()
            aisDeeply reqs, ['DESTROY']


        test_toi_set_watcher_perspectives: ->
            calls = []

            class ToiSetWatcherTest extends ToiSetWatcher

                _watch: (setId, toids) ->
                    calls.push [setId, toids]

                _unwatch: (setId) ->
                    calls.push setId

                getToiData: (toid) ->
                    toiAttr: [toid]

            tsw = new ToiSetWatcherTest()

            aisDeeply tsw.perspectives, {}
            ais tsw.pcounter.next(), 0

            p1 = tsw.perspective()
            p2 = tsw.perspective()

            ais keys(tsw.perspectives).length, 2

            p1.watch 'foo', [1,2,3]
            ais calls.length, 1
            aisDeeply calls[0][1], [1,2,3]
            id1 = calls[0][0]

            calls = []
            p2.watch 'foo', [1,2]
            aisDeeply calls[0][1], [1,2]
            id2 = calls[0][0]

            aok id1 != id2

            calls = []
            refresh1 = (watcher, setId, toiIds) ->
                calls.push [1, setId, toiIds]

            forget1 = (watcher, setId) ->
                calls.push [1, setId]

            refresh2 = (watcher, setId, toiIds) ->
                calls.push [2, setId, toiIds]

            signals.connect p1, 'refresh', refresh1
            signals.connect p1, 'forget', forget1
            signals.connect p2, 'refresh', refresh2

            # proto._notifyRefresh.call.tsw_internals, id1, [1,2,3])
            tsw._notifyRefresh id1, [1, 2, 3]
            # proto._notifyRefresh.call(tsw_internals, id2, [1, 2])
            tsw._notifyRefresh id2, [1, 2]

            aisDeeply calls, [[1, 'foo', [1,2,3]],
                              [2, 'foo', [1,2]]]
            calls = []

            res = p1.getToiData 1
            aisDeeply res, {'toiAttr': [1]}

            calls = []
            tsw._notifyForget id1
            aisDeeply calls, [[1, 'foo']]

            calls = []
            p2.unwatch 'foo'
            aisDeeply calls, [id2]

            calls = []
            p2.destroy()
            p1.destroy()

            aisDeeply calls, [id1]

        test_toi_set_watcher_perspective_integration: ->
            reqs = []
            jsLink = {}

            tsw = new ToiSetWatcher jsLink, 'Foo', ['a', 'b'], 0, ->
                track: (toid) ->
                    reqs.push(['track', toid])
                    false
                drop: (toid) ->
                    reqs.push(['drop', toid])
                destroy: ->

            calls = []
            p = tsw.perspective()

            p.watch('first', [42])
            aisDeeply(reqs, [['track', 42]])

            signals.connect(p, 'refresh', (watcher, setId, toids) ->
                calls.push([setId, toids])
                calls.push(watcher)
            )

            signals.connect(p, 'forget', (watcher, setId) ->
                calls.push(['forget', setId])
                calls.push(watcher)
            )

            tsw._dataUpdate(42, {'a': [3], 'b': [5]})

            aok(calls.pop() == tsw)
            aisDeeply(calls.pop(), ['first', [42]])

            p.unwatch('first')

            aok(calls.pop() == tsw)
            aisDeeply(calls.pop(), ['forget', 'first'])

            tsw.destroy()
            p.destroy()

        test_toi_set_watcher_self_integration: ->
            reqs = []
            jsLink = {}

            tsw = new ToiSetWatcher(jsLink, 'Foo', ['a', 'b'], 0, ->
                track: (toid) ->
                    reqs.push(['track', toid])
                    false
                drop: (toid) ->
                    reqs.push(['drop', toid])
                destroy: ->
            )
            calls = []

            tsw.watch('first', [42])
            aisDeeply(reqs, [['track', 42]])

            signals.connect(tsw, 'refresh', (watcher, setId, toids) ->
                calls.push([setId, toids])
                calls.push(watcher)
            )

            signals.connect(tsw, 'forget', (watcher, setId) ->
                calls.push(['forget', setId])
                calls.push(watcher)
            )

            tsw._dataUpdate(42, {'a': [3], 'b': [5]})

            aok(calls.pop() == tsw)
            aisDeeply(calls.pop(), ['first', [42]])

            tsw.unwatch('first')

            aok(calls.pop() == tsw)
            aisDeeply(calls.pop(), ['forget', 'first'])

            tsw.destroy()


    Tests.callback tests
