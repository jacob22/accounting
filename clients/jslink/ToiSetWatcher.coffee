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

define ['jslink/ToiRequester', 'signals', 'iter'], (ToiRequester, signals, iter) ->

    class ToiSetWatcherPerspective

        constructor: (@watcher, @sn) ->
            @sets = {}

        getToiData: (toid) ->
            @watcher.getToiData(toid)

        watch: (setId, toids) ->
            @sets[setId] = null
            name = @sn + '/' + setId
            @watcher._watch name, toids

        unwatch: (setId) ->
            name = @sn + '/' + setId
            @watcher._unwatch(name)
            delete @sets[setId]

        destroy: ->
            signals.disconnectAll this
            if @watcher?
                for setId of @sets
                    @unwatch setId

                delete @watcher.perspectives[@sn]
                @watcher = null


    class ToiSetWatcher

        constructor: (@jsLink, @tocName, @attrs, @cacheSize=50, factory) ->
            unless factory?
                factory = (jsLink, tocName, attrs, cacheSize, dataUpdate, errorHandler) ->
                    new ToiRequester jsLink, tocName, attrs, cacheSize, dataUpdate, errorHandler

            @requester = factory @jsLink, @tocName, @attrs, @cacheSize, @_dataUpdate, @_error
            @membership = {}
            @sets = {}
            @pending = {}
            @pcounter = iter.count()
            @perspectives = {}

        getToiData: (toid) ->
            @requester._data[toid]

        watch: (setId, toids) ->
            unless 'SELF' of @perspectives
                @perspectives['SELF'] = this
            @_watch 'SELF/' + setId, toids

        unwatch: (setId) ->
            @_unwatch 'SELF/' + setId

        perspective: ->
            sn = @pcounter.next()
            @perspectives[sn] = new ToiSetWatcherPerspective(this, sn)

        _notifyRefresh: (setId, toiIds) ->
            parts = setId.split '/'
            sn = parts[0]
            pSetId = parts[1]
            p = @perspectives[sn]
            signals.signal(p, 'refresh', this, pSetId, toiIds)

        _notifyForget: (setId) ->
            parts = setId.split '/'
            sn = parts[0]
            pSetId = parts[1]
            p = this.perspectives[sn]
            signals.signal(p, 'forget', this, pSetId)

        _watch: (setId, toiIds) ->
            whichPending = {}
            nPending = 0

            @sets[setId] = toiIds

            for toid in toiIds
                pending = not @requester.track(toid)
                unless toid of @membership
                    @membership[toid] = {}
                @membership[toid][setId] = null
                if pending
                    whichPending[toid] = null
                    nPending++

            @pending[setId] = whichPending
            if nPending == 0
                @_notifyRefresh setId, toiIds

        _unwatch: (setId) ->
            if setId of @sets
                pending = @pending[setId]
                if Object.keys(pending).length == 0
                    @_notifyForget setId
                ids = @sets[setId]
                delete @sets[setId]
                delete @pending[setId]
                for toid in ids
                    unless @membership[toid]
                        return

                    delete @membership[toid][setId]

                    empty = true
                    for key of @membership[toid]
                        empty = false
                        break

                    if empty
                        delete @membership[toid]
                        @requester.drop toid

        _dataUpdate: (toid, newData) =>
            for setId, _ of @membership[toid]
                pending = @pending[setId]

                if toid of pending
                    delete pending[toid]

                if newData == null
                    valueIdx = @sets[setId].indexOf(toid)
                    @sets[setId].splice(valueIdx, 1)

                if Object.keys(pending).length == 0
                    @_notifyRefresh setId, @sets[setId]

            if newData == null
                delete @membership[toid]

        destroy: ->
            @requester.destroy()
            for _, p of @perspectives
                p.watcher = null
            @sets = null
            @perspectives = null
            @requester = null
