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

require(['jslink/ToiRequester'], function(ToiRequester) {

    Tests.callback({
        test_toi_requester: function() {
            var calls = []
            var jsLink = {
                makeLink: function(name, args, callback) {
                    calls.push([name, args, callback])
                    return { deactivate: function() {calls.push('deactivate')} }
                }
            }

            function cb(toid, data) {
                calls.push([toid, data])
            }

            function error(toid, err) {
                calls.push([toid, err])
            }

            //var requester = OpenEnd.requesterFactory('Foo', ['a', 'b'], 0, cb, error)
            var requester = new ToiRequester(jsLink, 'Foo', ['a', 'b'], 0, cb, error)
            ais(requester._nToDrop, 1)

            var hasData = requester.track(42)
            aok(!hasData)
            aisDeeply(keys(requester._links), ['42']) // white-box testing
            aisDeeply(keys(requester._data), ['42'])
            aok(requester._data['42'] === null)

            ais(calls.length, 1)
            ais(calls[0][0], 'Request')
            aisDeeply(calls[0][1], {'params': {'toid': 42, 'subscription': true,
                                               'tocIdent': 'Foo',
                                               'attrList': ['a', 'b'] }})
            var cb42 = calls[0][2]
            calls = []

            cb42({'toiDiff': {'attrs': {'a': [3], 'b': [5]}}, 'error': null})
            aisDeeply(calls, [[42, {'a': [3], 'b': [5]}]])
            aisDeeply(requester._data, {42: {'a': [3], 'b': [5]}})
            calls = []

            hasData = requester.track(42)
            aok(hasData)


            // check data update
            cb42({'toiDiff': {'attrs': {'a': [7]}}, 'error': null})
            aisDeeply(calls, [[42, {'a': [7], 'b': [5]}]])
            aisDeeply(requester._data, {42: {'a': [7], 'b': [5]}})
            calls = []

            requester.drop(42)
            aisDeeply(calls, ['deactivate'])
            aisDeeply(keys(requester._links), []) // white-box testing
            aisDeeply(keys(requester._data), [])
        },


        test_toi_requester_toinonexistant: function() {
            var calls = []
            var jsLink = {
                makeLink: function(name, args, callback) {
                    calls.push([name, args, callback])
                    return { deactivate: function() {calls.push('deactivate')},
                             detach: function() { calls.push('detach')} }
                }
            }

            var requester

            function cb(toid, data) {
                calls.push([toid, data, toid in requester._data])
            }

            function error(toid, err) {
                calls.push(['err', toid, err])
            }

            // requester = OpenEnd.requesterFactory('Foo', ['a', 'b'], 10, cb, error)
            var requester = new ToiRequester(jsLink, 'Foo', ['a', 'b'], 10, cb, error)

            // Does not exist at all - initial callback has error
            var hasData = requester.track(42)
            aok(!hasData)
            ais(calls.length, 1)
            ais(calls[0][0], 'Request')
            var linkCb = calls[0][2]
            calls = []

            var err = {'__class__': 'ToiNonexistantError',
                       'args': ['Foo', 42]}
            var errMsg = {'error': err }
            linkCb(errMsg)
            aisDeeply(calls, [[42, null, false], 'detach'])
            aisDeeply(requester._links, {})
            aisDeeply(requester._data, {})
            aisDeeply(requester._tracked, {})
            aisDeeply(requester._untracked, [])
            calls = []

            // random other error handling
            var hasData = requester.track(43)
            var err = {'value': ['otherstuff']}
            var linkCb = calls[0][2]
            calls = []
            linkCb({'error': err})
            aisDeeply(calls, [['err', 43, err], 'detach'])
            calls = []

            // Vanished after an initial update with data
            var hasData = requester.track(42)
            var linkCb = calls[0][2]
            calls = []
            linkCb({'toiDiff': {'attrs': {'a': [3], 'b': [5]}}, 'error': null})
            aisDeeply(calls, [[42, {'a': [3], 'b': [5]}, true]])
            calls = []

            linkCb(errMsg)
            aisDeeply(calls, [[42, null, false], 'detach'])
            aisDeeply(requester._links, {})
            aisDeeply(requester._data, {})
            aisDeeply(requester._tracked, {})
            aisDeeply(requester._untracked, [])
            calls = []

            // Dropped and then got an error update
            var hasData = requester.track(42)
            requester.drop(42)
            calls = []
            linkCb(errMsg)
            aisDeeply(calls, ['detach'])
            aisDeeply(requester._links, {})
            aisDeeply(requester._data, {})
            aisDeeply(requester._tracked, {})
            aisDeeply(requester._untracked, [])
            calls = []

            // data update, dropped, error update
            var hasData = requester.track(42)
            linkCb({'toiDiff': {'attrs': {'a': [3], 'b': [5]}}, 'error': null})
            calls = []
            requester.drop(42)
            linkCb(errMsg)
            aisDeeply(calls, ['detach'])
            aisDeeply(requester._links, {})
            aisDeeply(requester._data, {})
            aisDeeply(requester._tracked, {})
            aisDeeply(requester._untracked, [])
            calls = []

            // spurious extra drop
            requester.drop(42)
            aisDeeply(calls, [])
            aisDeeply(requester._links, {})
            aisDeeply(requester._data, {})
            aisDeeply(requester._tracked, {})
            aisDeeply(requester._untracked, [])
        },

        test_toi_requester_lru_logic: function() {
            var calls = []
            var jsLink = {
                makeLink: function(name, args, callback) {
                    calls.push([name, args, callback])
                    return { deactivate: function() {calls.push('deactivate')},
                             detach: function() { calls.push('detach') } }
                }
            }

            var triggered = []
            function cb(toid, data) {
                triggered.push(toid)
            }

            //var requester = OpenEnd.requesterFactory('Foo', ['a'], 50, cb, null)
            var requester = new ToiRequester(jsLink, 'Foo', ['a'], 50, cb, null)

            for(var i=1; i<71; i++) {
                var hasData = requester.track(i)
                aok(!hasData)
                aok(i in requester._tracked)
                requester._dataUpdate(i, {'toiDiff': {'attrs': {'a': [i]}},
                                          'error': null})
            }
            // white-box testing
            ais(keys(requester._data).length, 70)
            ais(keys(requester._links).length, 70)
            aisDeeply(requester._untracked, [])
            ais(triggered.length, 70) // sanity-check
            triggered = []
            calls = []

            for(var i=1; i<50; i++) {
                requester.drop(i)
                ais(keys(requester._data).length, 70)
                var n = requester._untracked.length
                ais(n, i)
                ais(requester._untracked[n-1], i)
                aok(!(i in requester._tracked))
            }

            requester.drop(50)
            aisDeeply(requester._untracked.length, 50)
            aok(!(50 in requester._tracked))
            requester.drop(51)
            aisDeeply(requester._untracked.length, 41)
            aok(!(51 in requester._tracked))
            requester.drop(52)
            aisDeeply(requester._untracked.length, 42)
            aok(!(52 in requester._tracked))

            var expectedKept = list(range(11, 53))
            aisDeeply(requester._untracked, expectedKept)
            aisDeeply(calls.length, 10)
            ais(calls[0], 'deactivate')
            ais(keys(requester._links).length, 60)

            // data update on tracked
            requester._dataUpdate(60, {'toiDiff': {'attrs': {'a': [600]}},
                                       'error': null})
            aisDeeply(triggered, [60])
            triggered = []
            aisDeeply(requester._data[60], {'a': [600]})

            // data update on untracked but kept
            requester._dataUpdate(40, {'toiDiff': {'attrs': {'a': [400]}},
                                       'error': null})
            aisDeeply(triggered, [])
            aisDeeply(requester._data[40], {'a': [400]})

            hasData = requester.track(37)
            aok(hasData)
            aisDeeply(triggered, []) // we got hasData=true instead
            aok(37 in requester._tracked)
            aisDeeply(requester._untracked.length, 41)
            var expectedKept = list(range(11, 37)).concat(list(range(38, 53)))
            aisDeeply(requester._untracked, expectedKept)

            calls = []
            hasData = requester.track(10)
            aok(!hasData)
            aok(10 in requester._tracked)
            ais(calls.length, 1)
            calls = []

            requester.destroy()
            aisDeeply(calls.length, 61)
            ais(calls[0], 'deactivate')
        }
    })
})
