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

define([
    'react',
    'react-dom',
    'gettext',
    'signals',
    'jslink/JsLink',
    'jslink/query',
    'jslink/commit',
    'data/user',
    'widgets/izettle/tabmenu',
    'widgets/izettle/status',
    ], (
    React,
    ReactDOM,
    gettext,
    signals,
    JsLink,
    query,
    commit,
    User,
    TabMenu,
    Status,
    ) ->

    gettext.install('client')
    _ = gettext.gettext

    [orgid, accounting] = document.location.pathname.split('/')[-2..]

    # Data link setup
    jsLink = new JsLink('/jslink')

    user = new User.User(jsLink, orgid)

    productsQuery = new query.SortedQuery(
        jsLink, 'members.IzettleProduct', {'org': orgid}
    )
    productsQuery.attrList = [
        'name', 'variant', 'izPrice', 'price',
        'productId', 'customUnit', 'vatPercentage',
        'barcode', 'accountingRules']
    productsQuery.sorting = 'name'

    accountingYearQuery = new query.SortedQuery(
        jsLink, 'accounting.Org', {'id': orgid}
    )
    accountingYearQuery.attrList = ['current_accounting']

    accountsQuery = new query.SortedQuery(
        jsLink, 'accounting.Account'
    )
    accountsQuery.attrList = ['name', 'number']
    accountsQuery.sorting = 'number'

    transactionsHistory = new query.SortedQuery(
        jsLink, 'members.TransactionsUpload', {'org': orgid}
    )
    transactionsHistory.attrList = ['uploadTime', 'filename', 'resultingPayments']
    transactionsHistory.sorting = 'uploadTime'

    izettleProviderQuery = new query.SortedQuery(
        jsLink, 'accounting.IzettleProvider', {'org': orgid}
    )
    izettleProviderQuery.attrList = ['account', 'cash_account', 'fee_account', 'series']

    getProvider = (result, toiData) ->
        if result.length?
            toid = result[0]
            provider = toiData[toid]
            return provider
        else
            return null
            
    checkProvider = (provider, accountMap) ->
        if not accountMap?
            # Wait for accountMap to be available.
            return null
        if not provider?
            return 'missing'
        p = provider
        if p.account[0]? and p.cash_account[0]? and p.fee_account[0]? and p.series[0]?
            a = parseInt(p.account[0], 10)
            if a not of accountMap
                console.log(a)
                return 'account'
            if p.cash_account[0] not of accountMap
                return 'cash_account'
            if p.fee_account[0] not of accountMap
                return 'fee_account'
            # all good
            return null
        else
            return 'missing'

    rulesChanged = (toid, rules) =>
        commit.callToiMethod(
            jsLink,
            toid,
            'update',
            [[rules]], (result) ->
                if result.error?
                    debugger
        )

    accountMapper = (accountsData) ->
        accountmap = {}
        for toid, toi of accountsData
            accountmap[toi.number[0]] = toid
        return accountmap

    accountMap = null
    
    prodImportStatus = null
    prodImportStatusResult = {}

    importProducts = (filecontent, callback) =>
        filecontent = btoa(filecontent)
        commit.callBlmMethod(
            jsLink,
            'members.import_izettle_products_file',
            [[orgid],[filecontent]], (result) =>
                if result.error?
                    prodImportStatus = 'failure'
                else
                    prodImportStatus = 'success'
                    prodImportStatusResult = result.result
                callback()
                renderMenu()
        )

    transImportStatus = null
    transImportStatusResult = {}
    
    importTransactions = (filename, filecontent, callback) =>
        filecontent = btoa(filecontent)
        commit.callBlmMethod(
            jsLink,
            'members.import_izettle_payments',
            [[orgid],[filename],[filecontent]], (result) =>
                if result.error?
                    transImportStatus = 'failure'
                else
                    transImportStatus = 'success'
                    transImportStatusResult = result.result
                callback()
                renderMenu()
        )

    renderMenu = () ->
        provider = getProvider(izettleProviderQuery.result, izettleProviderQuery.toiData)
        providerStatus = checkProvider(provider, accountMap)
        ReactDOM.render(
            <div>
                <Status
                    prodImportStatus={prodImportStatus},
                    prodImportStatusResult={prodImportStatusResult},
                    productsData={productsQuery.toiData},
                    accountMap={accountMap},
                    transImportStatus={transImportStatus},
                    transImportStatusResult={transImportStatusResult},
                    providerStatus={providerStatus} />
            </div>,
            document.getElementById('izettle-status')
        )
        prodImportStatus = null
        prodImportStatusResult = null
        transImportStatus = null
        transImportStatusResult = null

        ReactDOM.render(
            <TabMenu
                importProducts={importProducts},
                accountMap={accountMap},
                accountsQuery={accountsQuery},
                onUpdate={rulesChanged},
                prodToiList={productsQuery.result},
                prodToiData={productsQuery.toiData},
                importTransactions={importTransactions},
                transactionsHistory={transactionsHistory},
                providerStatus={providerStatus}
                storekeeper={user.is_storekeeper()}
                />,
            document.getElementById('izettle-targetdiv')
        )


    signals.connect(accountingYearQuery, 'update', () ->
        org = @result[0]
        year = @toiData[org]['current_accounting'][0]
        accountsQuery.push({'accounting': year})
        accountsQuery.start()
    )
    signals.connect(accountsQuery, 'update', () ->
        accountMap = accountMapper(accountsQuery.toiData)
        renderMenu()
    )

    signals.connect(transactionsHistory, 'update', renderMenu)
    signals.connect(productsQuery, 'update', renderMenu)
    signals.connect(izettleProviderQuery, 'update', renderMenu)
    signals.connect(user, 'refresh', renderMenu)

    jsLink.ready.then(->
        user.start()
        productsQuery.start()
        accountingYearQuery.start()
        transactionsHistory.start()
        izettleProviderQuery.start()
    )
)
