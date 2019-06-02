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

define ['gettext', 'iter', 'signals', 'jslink/commit', 'jslink/query', 'jslink/ToiSetWatcher'], (
    gettext, iter, signals, commit, query, ToiSetWatcher) ->

    class TransactionTextIndex

        constructor: (@jsLink, @orgid) ->
            @transaction_texts = []
            @started = false

        start: ->
            if @started
                return

            @started = true
            commit.callBlmMethod(
                @jsLink,
                'accounting.transactionIndex',
                [[{filter: [{property: 'org', value: @orgid}]}]],
                (response) =>
                    if response.error?
                        null  # what to do?
                    else
                        @transaction_texts = (
                            obj.text for obj in response.result
                        )
            )

        push: (string) ->
            unless string in @transaction_texts
                @transaction_texts.push(string)

        complete: (input, callback) ->
            if not input
                callback(null, options: [])
                return

            pattern = input.toLocaleLowerCase()
            options = [
                {value: input, label: input, _index: -1, _lower: pattern}
            ]
            for line in @transaction_texts
                if line == input
                    continue
                lower = line.toLocaleLowerCase()
                index = lower.indexOf(pattern)
                if index != -1
                    options.push({
                        value: line,
                        label: line,
                        _index: index,
                        _lower: lower,
                    })

            options.sort((a, b) ->
                a._index - b._index ||
                    a._lower.localeCompare(b._lower, gettext.bcp47) ||
                    a.value.length - input.length
            )

            callback(null, {
                options: options
            })
            return null


    class VerificationDataAggregator

        constructor: (@jsLink, @orgid) ->
            @_org_watcher = new ToiSetWatcher(@jsLink, 'accounting.Org',
                ['current_accounting'])

            signals.connect(@_org_watcher, 'refresh', @_org_updated)

            @lines = []
            @amount = 0
            @_got_accounts = false
            @_got_series = false
            @_got_transactions = false

        start: ->
            @lines = []
            @amount = 0
            @_org_watcher.watch('org', [@orgid])
            commit.callToiMethod(@jsLink, @purchase, 'suggestVerification', [],
                (response) =>
                    if response.error?
                        debugger
                    @_transactions_suggested(response.result)
            )

            @transaction_index = new TransactionTextIndex(@jsLink, @orgid)

        stop: ->
            @_org_watcher.unwatch('org')
            if @accounts_query?
                @accounts_query.stop()
                @accounts_query = null
            if @series_query?
                @series_query.stop()
                @series_query = null

        restart: ->
            @stop()
            @start()

        set_purchase: (@purchase) ->

        _org_updated: =>
            accounting = @_org_watcher.getToiData(@orgid).current_accounting[0]
            @_fetch_accounts(accounting)
            @_fetch_series(accounting)

        _fetch_accounts: (accounting) ->
            if @accounts_query?
                @accounts_query.stop()
            toc = 'accounting.Account'
            params = accounting: accounting
            @accounts_query = new query.SortedQuery(@jsLink, toc, params)
            @accounts_query.attrList = ['name', 'number']
            @accounts_query.sorting = 'number'
            signals.connect(@accounts_query, 'update', @_accounts_updated)
            @accounts_query.start()

        _fetch_series: (accounting) ->
            if @series_query?
                @series_query.stop()
            toc = 'accounting.VerificationSeries'
            params = accounting: accounting
            @series_query = new query.SortedQuery(@jsLink, toc, params)
            @series_query.attrList = ['name', 'description']
            @series_query.sorting = 'name'
            signals.connect(@series_query, 'update', @_series_updated)
            @series_query.start()

        _accounts_updated: =>
            @_got_accounts = true
            @_refresh()

        _series_updated: =>
            @_got_series = true
            @_refresh()

        _transactions_suggested: (response) =>
            ids = iter.count(1)
            for transaction in response.transactions
                line =
                    id: "transaction-#{ ids.next() }"
                    amount: transaction.amount
                    text: transaction.text
                    account: transaction.account
                @lines.push(line)
            @_got_transactions = true
            @_refresh()

        _refresh: ->
            if @_got_accounts and @_got_series and @_got_transactions
                signals.signal(this, 'refresh', this)
                @transaction_index.start()
