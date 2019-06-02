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

define(['signals', 'jslink/ToiSetWatcher'], ->
    [signals, ToiSetWatcher] = arguments

    class User

        constructor: (@jsLink, @org) ->
            @permissions = []
            @watcher = new ToiSetWatcher(@jsLink, 'accounting.Org',
                ['permissions'])

        start: ->
            signals.connect(@watcher, 'refresh', @_org_updated)
            @watcher.watch('org', [@org])

        _org_updated: (watcher) =>
            @permissions = @watcher.getToiData(@org).permissions
            signals.signal(@, 'refresh')

        is_accountant: ->
            'accountants' in @permissions

        is_admin: ->
            'admins' in @permissions

        is_member: ->
            'members' in @permissions

        is_storekeeper: ->
            'storekeepers' in @permissions

        is_ticketchecker: ->
            'ticketcheckers' in @permissions


    module =
        User: User
)
