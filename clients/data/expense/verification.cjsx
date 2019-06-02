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

define ['signals', 'utils', 'jslink/query', 'jslink/ToiSetWatcher'], (
    signals, utils, query, ToiSetWatcher) ->

    class VerificationDataAggregator

        constructor: (@jsLink, @orgid) ->
            @_org_watcher = new ToiSetWatcher(@jsLink, 'accounting.Org',
                ['current_accounting'])
            @_ver_watcher = new ToiSetWatcher(@jsLink, 'expense.Verification',
                ['lines', 'text', 'amount', 'receipt', 'state'])
            @_line_watcher = new ToiSetWatcher(@jsLink, 'expenses.Line',
                ['category', 'amount', 'text'])
            @_category_watcher = new ToiSetWatcher(@jsLink, 'expense.BaseCategory',
                ['name', 'account'])

            signals.connect(@_org_watcher, 'refresh', @_org_updated)
            signals.connect(@_ver_watcher, 'refresh', @_verification_updated)
            signals.connect(@_line_watcher, 'refresh', @_lines_updated)
            signals.connect(@_category_watcher, 'refresh', @_categories_updated)

            @_accounts_by_number = {}
            @lines = []
            @amount = 0
            @_got_accounts = false
            @_got_categories = false
            @_got_series = false

        start: ->
            @_got_categories = false
            @lines = []
            @amount = 0
            @_org_watcher.watch('org', [@orgid])
            @_ver_watcher.watch('foo', [@verification])

        stop: ->
            @_org_watcher.unwatch('org')
            @_ver_watcher.unwatch('foo')
            @_line_watcher.unwatch('foo')
            @_category_watcher.unwatch('foo')
            if @accounts_query?
                @accounts_query.stop()
            if @series_query?
                @series_query.stop()

        restart: ->
            @stop()
            @start()

        set_verification: (@verification) ->

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
            signals.connect(@accounts_query, 'update', @_accounts_updated)
            @accounts_query.start()

        _fetch_series: (accounting) ->
            if @series_query?
                @series_query.stop()
            toc = 'accounting.VerificationSeries'
            params = accounting: accounting
            @series_query = new query.SortedQuery(@jsLink, toc, params)
            @series_query.attrList = ['name', 'description']
            signals.connect(@series_query, 'update', @_series_updated)
            @series_query.start()

        _accounts_updated: =>
            @_got_accounts = true
            @_accounts_by_number = {}
            for _, toi of @accounts_query.toiData
                @_accounts_by_number[toi.number[0]] = toi
            @_populate_account_data(@lines)
            @_refresh()

        _series_updated: =>
            @_got_series = true
            @_refresh()

        _verification_updated: (watcher) =>
            toi = watcher.getToiData(@verification)
            @amount = -1 * utils.parseCurrency(toi.amount[0])
            @_line_watcher.unwatch('foo')
            @_line_watcher.watch('foo', toi.lines)

        _lines_updated: (watcher, setid, toids) =>
            categories = []
            @lines.push(
                id: 0
                amount: @amount
            )

            for toid in toids
                toi = watcher.getToiData(toid)
                amount = toi.amount[0]
                category = toi.category[0]
                line =
                    id: toid
                    amount: utils.parseCurrency(amount)
                    category: category
                    text: toi.text[0]
                @lines.push(line)
                categories.push(category)
            @_category_watcher.unwatch('foo')
            @_category_watcher.watch('foo', categories)

        _categories_updated: (watcher) =>
            @_got_categories = true
            @_populate_account_data(@lines)
            @_refresh()

        _populate_account_data: (lines) ->
            for line in lines
                category = @_category_watcher.getToiData(line.category)
                if category?
                    account_number = category.account[0]
                    account = @_accounts_by_number[account_number]
                    if account?
                        line.account = account._id[0]

        _refresh: ->
            if @_got_accounts and @_got_categories and @_got_series
                signals.signal(this, 'refresh', this)
