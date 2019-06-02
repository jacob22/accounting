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

require ['jslink/commit'], (commit) ->

    Tests.callback

        test_call_blm_method: ->
            check = null
            calls = []

            jsLink =
                makeLink: (name, args, callback, lowprio) ->
                    check = [name, args, callback, lowprio]
                    return detach: -> calls.push('detach')

            testCallback = (args) ->
                calls.push(['callback', args])
                return 'cb result'

            commit.callBlmMethod(
                jsLink,
                'helpdesk.dummyFunction',
                [[42], [43], ['abc']],
                testCallback
            )
            ais(check[0], "CallMethod")
            aisDeeply(check[1],
                params:
                    blmName: 'helpdesk'
                    methodName: 'dummyFunction'
                    'args': [[42], [43], ['abc']]
            )

            cb = check[2]
            aok(!check[3])
            res = cb('foo')
            aisDeeply(calls, ['detach', ['callback', 'foo']])
            ais(res, 'cb result')

            # Test calling without a callback
            commit.callBlmMethod(jsLink, 'helpdesk.anotherMethod', [[11]])
            ais(check[0], "CallMethod")
            aisDeeply(check[1],
                params:
                    blmName: 'helpdesk'
                    methodName: 'anotherMethod'
                    args: [[11]]
            )
            aok(check[2])


        test_call_toi_method: ->
            check = null
            calls = []

            jsLink =
                makeLink: (name, args, callback, lowprio) ->
                    check = [name, args, callback, lowprio]
                    return detach: -> calls.push('detach')

            testCallback = (args) ->
                calls.push(['callback', args])

            commit.callToiMethod(
                jsLink,
                14,
                'dummyFunction',
                [[42], [43], ['abc']],
                testCallback
            )
            ais(check[0], "CallMethod")
            aisDeeply(check[1],
                params:
                    toid: 14
                    methodName: 'dummyFunction'
                    args: [[42], [43], ['abc']]
            )
            cb = check[2]
            aok(!check[3])
            cb('foo')
            aisDeeply(calls, ['detach', ['callback', 'foo']])

            # Test calling without a callback
            calls = []
            commit.callToiMethod(jsLink, 14, 'anotherMethod', [[11]])
            ais(check[0], "CallMethod")
            aisDeeply(check[1],
                params:
                    toid: 14
                    methodName: 'anotherMethod'
                    args: [[11]]
            )
            cb = check[2]
            cb('foo')
            aok(check[3])
            aisDeeply(calls, ['detach'])
