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

define(['signals', 'utils'], ->
    [signals, utils] = arguments

    class VerificationDataAggregator

        constructor: (@verId, @verificationsWatcher, @transactionsWatcher,
                      @accounts_query, @series_query) ->
            @lines = []
            @amount = 0
            @verificationVersion = 0
            @_got_accounts = false
            @_got_transactions = false
            @_got_series = false
            if not @verId?
                # New verification
                @_got_transactions = true
            else
                @verSetId = 'verification-' + @verId
                @transSetId = 'transactions-' + @verId
                signals.connect(@verificationsWatcher, 'refresh', @_verification_updated)
                signals.connect(@transactionsWatcher, 'refresh', @_transactions_updated)

            signals.connect(@accounts_query, 'update', @_accounts_updated)
            signals.connect(@series_query, 'update', @_series_updated)

        start: ->
            @lines = []
            @amount = 0
            if @verId?
                @verificationsWatcher.watch(@verSetId, [@verId])
            @_accounts_updated()
            @_series_updated()

        stop: ->
            if @verificationsWatcher?
                @verificationsWatcher.unwatch(@verSetId)
            if @transactionsWatcher?
                @transactionsWatcher.unwatch(@transSetId)

        restart: ->
            @stop()
            @start()

        _accounts_updated: =>
            @_got_accounts = !!@accounts_query.gotResult
            @_refresh()

        _series_updated: =>
            @_got_series = !!@series_query.gotResult
            @_update_series_name()
            @_refresh()

        _verification_updated: (watcher, setId, toiIds) =>
            if setId != @verSetId
                return

            verData = watcher.getToiData(@verId)
            @transactionsWatcher.watch(@transSetId, verData.transactions)

            @verificationNumber = verData.number[0]
            @_update_series_name()
            @verificationVersion = verData.version[0] + 1

        _transactions_updated: (watcher, setId, toiIds) =>
            if setId != @transSetId
                return
            verData = @verificationsWatcher.getToiData(@verId)
            lines = []
            for toid in verData.transactions
                transData = watcher.getToiData(toid)
                lines.push({
                    id: toid
                    account: transData.account[0]
                    text: transData.text[0]
                    amount: utils.parseCurrency(transData.amount[0])
                    version: transData.version[0]
                })
            @lines = lines
            @_got_transactions = true
            @_refresh()

        _refresh: ->
            if @_got_accounts and @_got_transactions and @_got_series
                signals.signal(this, 'refresh', this)

        _update_series_name: ->
            verData = @verificationsWatcher.getToiData(@verId)
            if verData?
                toid = verData.series[0]
                if toid in @series_query.result
                    @verificationSeries = @series_query.toiData[toid].name[0]
)
