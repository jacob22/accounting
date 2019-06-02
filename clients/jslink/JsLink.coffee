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

define ['axios', 'iter'], (axios, iter) ->
    class Link
        constructor: (@jsLink, @id, @callback, lowprio) ->
            @jsLink._attach(@id, this, lowprio)

        update: (name, args, setPending) ->
            if setPending
                @jsLink._setPending(@id)
            return @jsLink.sendReq(
                type: 'link_update'
                name: name
                args: args
                id: @id
            )

        detach: ->
            @jsLink._detach(@id)

        deactivate: (name, args={}) ->
            @detach()
            return @jsLink.sendReq(
                type: 'link_deactivate'
                name: name
                args: args
                id: @id
            )

    class JsLink

        constructor: (@url, @pollingInterval=10) ->
            @pollingErrors = 0

            @clientId = null
            @msgQueue = []

            @links = {}
            @pending = {}
            @nPending = 0
            @_busyFunction = null
            @window = window
            @_link_id = iter.count()
            @ready = @_post([version: 2, type: 'handshake']).then((response) =>
                @finishInit(response.data.results[0])
            )

        sendReq: (msg) ->
            unless @msgQueue.length
                @window.setTimeout =>
                    @_sendRequests()
            p = new Promise (resolved, rejected) =>
                @msgQueue.push([msg, resolved, rejected])
            return p

        _post: (messages) ->
            axios.post(@url, messages: messages)

        _sendRequests: ->
            messages = []
            resolveds = []
            rejecteds = []

            while @msgQueue.length
                [msg, resolved, rejected] = @msgQueue.shift()
                msg.clientId = @clientId
                messages.push(msg)
                resolveds.push(resolved)
                rejecteds.push(rejected)

            @_post(messages).then((response) =>
                for result in response.data.results
                    resolved = resolveds.shift()
                    resolved(result)
                @restartPolling(0)
            ).catch((response) ->
                for rejected in rejecteds
                    rejected(response)
            )

        finishInit: (data) ->
            @extraInfo = data.extraInfo
            @clientId = data.clientId
            @setupPolling()
            return data

        _wait: (timeout) =>
            new Promise((resolved) =>
                timeout *= 1000  # seconds -> milliseconds
                @pollwait = @window.setTimeout(resolved, timeout)
            )

        setupPolling: (timeout) ->
            if not @clientId? or @pollwait?
                return

            if timeout?
                interval = timeout
            else if @nPending
                interval = 0.3
            else
                interval = @pollingInterval

            p = @_wait(interval)
            p.then(=>
                @_do_poll().then(=>
                    @restartPolling()
                )
            )

        stopPolling: ->
            if @pollwait?
                @window.clearTimeout(@pollwait)
            @pollwait = null

        restartPolling: (timeout) ->
            @stopPolling()
            @setupPolling(timeout)

        close: ->
            @stopPolling()
            @clientId = null

        logout: ->
            p = @sendReq({'type': 'logout'})
            p.then(@close)
            return p

        deactivate: ->
            p = @sendReq(
                type: 'client_deactivate'
                clientId: @clientId
            )
            return p

        forcePoll: ->
            @stopPolling()
            @_do_poll().then(=>
                @restartPolling()
            )

        _do_poll: ->
            p = @sendReq(
                type: 'poll'
                clientId: @clientId
            )
            return p.then(@deliver)  # xxx handle error?

        deliver: (data) =>
            @pollingErrors = 0
            for result in data
                @_resetPending result.id
                try
                    this['_msg_' + result.type](result)
                catch error
                    console.log(error)
                    debugger
            return 'delivered'

        _msg_update: (msg) ->
            id = msg['id']
            if id of @links
                link = @links[id]
                link.callback(msg['args'])

        _attach: (id, link, lowprio) ->
            @links[id] = link
            unless lowprio
                @pending[id] = null
                @nPending++

        _detach: (id) ->
            this._resetPending(id)
            delete @links[id]

        _resetPending: (id) ->
            if id of @pending
                delete @pending[id]
                @nPending--

        _setPending: (id) ->
            unless id of @pending
                @pending[id] = null
                @nPending++

        makeLink: (name, args, callback, lowprio) =>
            newId = @_link_id.next()
            link = new Link(this, newId, callback, lowprio)

            link.ready = @sendReq(
                type: 'link'
                name: name
                args: args
                id: newId
            )
            return link
