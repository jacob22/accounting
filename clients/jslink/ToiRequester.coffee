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

define [], () ->

    class ToiRequester

        constructor: (@jsLink, @tocName, @attrs, @cacheSize, dataUpdate, errorHandler) ->
            @_dataUpdateCb = dataUpdate
            @_errorHandler = errorHandler
            @_links = {}
            @_data = {}
            @_tracked = {}
            @_untracked = []
            @_nToDrop = Math.floor(@cacheSize/100*20) || 1 # 20% or 1

        track: (toid) ->
            if toid of @_links
                unless toid of @_tracked

                    untrackedIdx = @_untracked.indexOf(toid)
                    @_untracked.splice(untrackedIdx, 1)
                    @_tracked[toid] = true
                return @_data[toid] != null
            @_links[toid] = this._makeRequest(toid)
            @_data[toid] = null
            @_tracked[toid] = true
            return false

        _makeRequest: (toid) ->
            params =
                toid: toid
                subscription: true
                tocIdent: @tocName
                attrList: @attrs

            @jsLink.makeLink 'Request', {params: params}, (args) =>
                @_dataUpdate toid, args

        _dataUpdate: (toid, args) ->
            self = this
            error = args.error
            if error
                existed = this._data[toid] != null
                delete this._data[toid]
                if toid of this._tracked
                    if error.__class__ == 'ToiNonexistantError'
                        @_dataUpdateCb toid, null
                    else if @_errorHandler
                        @_errorHandler toid, error
                else
                    untrackedIdx = @_untracked.indexOf(toid)
                    @_untracked.splice(untrackedIdx, 1)

                @_links[toid].detach()
                delete @_links[toid]
                delete @_tracked[toid]
                return

            diff = args.toiDiff.attrs
            data = @_data[toid]
            if data == null
                data = this._data[toid] = {}

            for key of diff
                data[key] = diff[key]

            if toid of this._tracked
                this._dataUpdateCb toid, data

        drop: (toid) ->
            unless toid of this._links
                return

            delete @_tracked[toid]
            @_untracked.push(toid)
            if @_untracked.length > @cacheSize
                toDrop = @_untracked.splice 0, @_nToDrop
                @_really_drop toid for toid in toDrop

        _really_drop: (toid) ->
            link = @_links[toid]
            d = link.deactivate 'deactivate'
            delete @_links[toid]
            delete @_data[toid]
            return d

        destroy: () ->
            @_really_drop toid for toid of @_links
            @_links = null
            @_data = null
            @_tracked = null
            @_untracked = null
