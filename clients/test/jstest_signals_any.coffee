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

require ['signals'], (signals) ->

    Tests.callback

        test_signals: ->
            object = {}
            calls = []

            target_foo_1 = (arg1, arg2) ->
                calls.push ['foo', 1, arg1, arg2]

            target_foo_2 = ->
                calls.push ['foo', 2]

            target_bar_1 = (arg1) ->
                calls.push ['bar', 1, arg1]

            signals.connect(object, 'foo', target_foo_1)
            signals.connect(object, 'foo', target_foo_2)
            signals.connect(object, 'bar', target_bar_1)

            aok target_foo_1 in object.__signals__['foo']  # whitebox
            aok target_foo_2 in object.__signals__['foo']  # whitebox
            aok target_bar_1 in object.__signals__['bar']  # whitebox

            signals.signal(object, 'foo', 'bar', 'baz')
            aisDeeply calls, [['foo', 1, 'bar', 'baz'], ['foo', 2]]

            calls = []
            signals.signal(object, 'bar', 42)
            aisDeeply calls, [['bar', 1, 42]]

            calls = []
            signals.disconnect(object, 'foo', target_foo_2)
            signals.signal(object, 'foo', 'bar', 'baz')
            aisDeeply calls, [['foo', 1, 'bar', 'baz']]
            aok target_foo_2 not in object.__signals__['foo']  # whitebox
            aok 'foo' of object.__signals__  # whitebox

            calls = []
            signals.disconnect(object, 'foo', target_foo_1)
            signals.signal(object, 'foo', 'bar', 'baz')
            aisDeeply calls, []
            aok 'foo' not of object.__signals__  # whitebox

            signals.disconnect(object, 'bar', target_bar_1)
            signals.signal(object, 'bar', 27)
            aisDeeply calls, []
            ais object.__signals__, undefined  # whitebox

        test_disconnect_all: ->
            object = {}
            calls = []

            target_foo_1 = (arg1, arg2) ->
                calls.push ['foo', 1, arg1, arg2]

            target_foo_2 = ->
                calls.push ['foo', 2]

            signals.connect(object, 'foo', target_foo_1)
            signals.connect(object, 'foo', target_foo_2)

            aok object.__signals__  # whitebox

            signals.disconnectAll(object)
            ais object.__signals__, undefined  # whitebox

            signals.disconnectAll(object)  # be reentrant, please
            ais object.__signals__, undefined
