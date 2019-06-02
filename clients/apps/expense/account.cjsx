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
require('./account.css')

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
    'data/expense/verification',
    'widgets/expense/reportlist',
    'widgets/verification'
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
    VerificationDataAggregator,
    ReportList,
    Verification
    ) ->

    gettext.install('client')
    _ = gettext.gettext

    jsLink = new JsLink('/jslink')

    [orgid] = document.location.pathname.split('/')[-1..]

    selected = null

    reportsQuery = new query.SortedQuery(
        jsLink, 'expense.Verification', {'state': 'approved'})
    reportsQuery.attrList = ['state', 'amount', 'date']

    signals.connect(reportsQuery, 'update', () ->
        ReactDOM.render(
            <ReportList
                empty_text={_('There are no expense reports to manage.')},
                selected={selected}
                verificationSelected={show_verification}
                toilist={@result}
                toiData={@toiData}/>,
            document.getElementById('reports'))
        )

    show_verification = (toid) ->
        if toid == selected
            return
        selected = toid
        verDataAggregator.set_verification(toid)
        ReactDOM.render(
            <Verification
                verDataAggregator={verDataAggregator}
                save=save />,
            document.getElementById('reportview')
        )

    clear_verification = ->
        ReactDOM.render(
            <div />
            document.getElementById('reportview')
        )

    save = (state) ->
        params =
            date: state.date.format('YYYY-MM-DD')
            series: state.series
            org: orgid
            lines: ({
                account: line.account
                text: line.text
                amount: if line.debit? then -line.debit else line.credit
            } for line in state.lines)
        commit.callToiMethod(
            jsLink,
            selected,
            'create_accounting_verification',
            [[params]], (result) ->
                if result.error?
                    debugger
                else
                    clear_verification()
        )

    verDataAggregator = new VerificationDataAggregator(jsLink, orgid)

    jsLink.ready.then(->
        reportsQuery.start()
    )
