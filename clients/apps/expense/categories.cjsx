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

require('./common.css')
require('./categories.css')

define [
    'react',
    'react-dom',
    'signals',
    'utils',
    'jslink/JsLink',
    'jslink/commit',
    'jslink/query',
    'jslink/ToiSetWatcher',
    'widgets/expense/categorylist',
    'gettext'
    ], (
    React,
    ReactDOM,
    signals,
    utils,
    JsLink,
    commit,
    query,
    ToiSetWatcher,
    CategoryList,
    gettext
    ) ->

    gettext.install('client')

    jsLink = new JsLink('/jslink')

    [orgid] = document.location.pathname.split('/')[-1..]

    qCat = new query.SortedQuery(jsLink, 'expense.Category', org: orgid)
    qCat.attrList = ['account', 'name']

    qCountable = new query.SortedQuery(jsLink, 'expense.CategoryCountable', org: orgid)
    qCountable.attrList = ['account', 'name', 'price', 'unit']

    qOne = new query.SortedQuery(jsLink, 'expense.CategoryOne', org: orgid)
    qOne.attrList = ['account', 'name', 'price']

    org_watcher = new ToiSetWatcher(jsLink, 'accounting.Org',
        ['current_accounting'])

    updateCategory = (toid, data, callback) ->
        commit.callToiMethod(jsLink, toid, 'save', [[data]], (result) ->
            if result.error?
                debugger
            callback()
        )

    createCategory = (toc, data, callback) ->
        data.org = [orgid]
        commit.callBlmMethod(jsLink, 'expense.createCategory', [[toc], [data]], (result) ->
            if result.error?
                debugger
            callback()
        )

    deleteCategory = (toid, callback) ->
        commit.callToiMethod(jsLink, toid, 'delete', [], (result) ->
            if result.error?
                debugger
            callback()
        )

    render = ->
        account_by_number = {}
        for toid, toi of qAccounts.toiData
            account_by_number[toi.number[0]] = toid

        ReactDOM.render(
            <CategoryList
                normal_categories=qCat.toiData
                countable_categories=qCountable.toiData
                one_categories=qOne.toiData
                account_by_number=account_by_number
                accounts_query=qAccounts
                handleChange=updateCategory
                handleCreate=createCategory
                handleDelete=deleteCategory
                />,
            document.getElementById('categorylist')
        )

    qAccounts = new query.SortedQuery(jsLink, 'accounting.Account')
    qAccounts.attrList = ['name', 'number']
    signals.connect(qAccounts, 'update', render)

    update_org = ->
        accounting = org_watcher.getToiData(orgid).current_accounting[0]
        qAccounts.push(accounting: accounting)
        qAccounts.start()

        qCat.start()
        qCountable.start()
        qOne.start()

    signals.connect(qCat, 'update', render)
    signals.connect(qCountable, 'update', render)
    signals.connect(qOne, 'update', render)

    signals.connect(org_watcher, 'refresh', update_org)

    jsLink.ready.then(->
        org_watcher.watch('org', [orgid])
    )
