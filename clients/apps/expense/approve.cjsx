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
require('./approve.css')

define [
    'react',
    'react-dom',
    'gettext',
    'signals',
    'utils',
    'jslink/JsLink',
    'jslink/commit',
    'jslink/query',
    'jslink/ToiSetWatcher',
    'widgets/expense/reportlist',
    'widgets/reportview',
    'widgets/valuefilter',
    ], (
    React,
    ReactDOM,
    gettext,
    signals,
    utils,
    JsLink,
    commit,
    query,
    ToiSetWatcher,
    ReportList,
    ReportView,
    ValueFilter
    ) ->

    gettext.install('client')
    _ = gettext.gettext

    jsLink = new JsLink('/jslink')

    verWatcher = new ToiSetWatcher(jsLink, 'expense.Verification',
        ['lines', 'text', 'amount', 'receipt', 'state'])
    lineWatcher = new ToiSetWatcher(jsLink, 'expenses.Line',
        ['category', 'amount', 'count', 'text'])
    categoryWatcher = new ToiSetWatcher(jsLink, 'expense.BaseCategory',
        ['name', 'account'])

    setVerificationState = (toid, state, callback) ->
        commit.callToiMethod(jsLink, toid, 'setState', [[state]],
            (result) -> callback(result)
        )

    selected = null
    reportsQuery = null

    filterChanged = (values) ->
        if reportsQuery?
            reportsQuery.stop()
        states = []
        for state, include of values
            if include
                states.push(state)

        reportsQuery = new query.SortedQuery(
            jsLink, 'expense.Verification', {'state': states})
        reportsQuery.attrList = ['state', 'amount', 'date']
        signals.connect(reportsQuery, 'update', () ->
            ReactDOM.render(
                <ReportList
                    empty_text={_('No expense reports match.')}
                    selected={selected}
                    verificationSelected={showVerification}
                    toilist={@result}
                    toiData={@toiData}/>,
                document.getElementById('reports'))

            if @result.length == 0
                showVerification(null)
        )
        reportsQuery.start()

    filter = ReactDOM.render(<ValueFilter
        onChange={filterChanged}
        values={[
            ['new', 'Nya', true],
            ['approved', 'Godkända', false],
            ['denied', 'Nekade', false],
            ['handling', 'Under behandling', true]
        ]} />,
        document.getElementById('filter')
    )

    showVerification = (toid) ->
        selected = toid

        if not toid?
            ReactDOM.render(
                <div />,
                document.getElementById('reportview')
            )
        else
            ReactDOM.render(
                <ReportView
                    verification={toid}
                    setVerificationState={setVerificationState}
                    verWatcher={verWatcher}
                    lineWatcher={lineWatcher}
                    categoryWatcher={categoryWatcher} />,
                document.getElementById('reportview')
            )

    jsLink.ready.then(-> filter.signal())
