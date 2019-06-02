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

require(['signals', 'data/user'], ->

    [signals, User] = arguments


    class FakeJsLink

    class FakeWatcher

        constructor: (@toiData) ->

        getToiData: (toid) ->
            return @toiData[toid]

        watch: ->


    create = ->
        return new User.User(new FakeJsLink(), '1')


    Tests.callback(

        test_constructor: ->
            org1 = '1'  # toid
            user = new User.User('jsLink', org1)
            ais(user.jsLink, 'jsLink')
            ais(user.org, '1')

        test_start: ->
            user = create()
            calls = []
            user.watcher.watch = (set, toids) ->
                calls.push([set, toids])

            user.start()
            aisDeeply(calls, [['org', ['1']]])

        test_handle_update: ->
            user = create()
            permissions = [1, 2, 3]
            toiData = {1: {permissions: [1, 2, 3]}}
            user.watcher = new FakeWatcher(toiData)
            user.start()
            calls = []
            signals.connect(user, 'refresh', -> calls.push(true))
            signals.signal(user.watcher, 'refresh', null, null, [1])
            aisDeeply(calls, [true])
            aisDeeply(user.permissions, [1, 2, 3])

        test_permission_checks: ->
            user = create()
            user.permissions = []

            aok(!user.is_accountant())
            aok(!user.is_admin())
            aok(!user.is_member())
            aok(!user.is_storekeeper())
            aok(!user.is_ticketchecker())

            user.permissions.push('accountants')
            aok(user.is_accountant())
            aok(!user.is_admin())
            aok(!user.is_member())
            aok(!user.is_storekeeper())
            aok(!user.is_ticketchecker())

            user.permissions.push('admins')
            aok(user.is_accountant())
            aok(user.is_admin())
            aok(!user.is_member())
            aok(!user.is_storekeeper())
            aok(!user.is_ticketchecker())

            user.permissions.push('members')
            aok(user.is_accountant())
            aok(user.is_admin())
            aok(user.is_member())
            aok(!user.is_storekeeper())
            aok(!user.is_ticketchecker())

            user.permissions.push('storekeepers')
            aok(user.is_accountant())
            aok(user.is_admin())
            aok(user.is_member())
            aok(user.is_storekeeper())
            aok(!user.is_ticketchecker())

            user.permissions.push('ticketcheckers')
            aok(user.is_accountant())
            aok(user.is_admin())
            aok(user.is_member())
            aok(user.is_storekeeper())
            aok(user.is_ticketchecker())

    )
)
