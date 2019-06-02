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

React = require('react')
ReactDOM = require('react-dom')
ReactStrap = require('reactstrap')
gettext = require('gettext')
JsLink = require('jslink/JsLink')
commit = require('jslink/commit')
VerificationDataAggregator = require('data/purchase/verification')
Verification = require('widgets/verification')

gettext.install('client')  # xxx
_ = gettext.gettext

jsLink = new JsLink('/jslink')
[orgid, purchaseid] = document.location.pathname.split('/')[-2..]


save = (state) ->
    verification =
        transaction_date: state.date.format('YYYY-MM-DD')
        series: state.series
        org: orgid
        transactions: ({
            account: line.account
            text: line.text
            amount: if line.debit? then line.debit else -line.credit
        } for line in state.lines)

    commit.callBlmMethod(
        jsLink,
        'members.manualPayment_ex',
        [[purchaseid], [verification]], (response) ->
            if response.error?
                render_error(response.error)
            else
                payment = response.result[0]
                parent.postMessage("payment created: #{payment}", '*')
    )


render_error = (error) ->
    ReactDOM.render(
        <ReactStrap.Alert color='danger'>
            {_('Failed to save verification. Please close this window.')}
        </ReactStrap.Alert>,
        document.getElementById('error')
    )


render = ->
    aggregator = new VerificationDataAggregator(jsLink, orgid)
    aggregator.set_purchase(purchaseid)

    ReactDOM.render(
        <Verification
            verDataAggregator=aggregator
            save=save />,
        document.getElementById('verification')
    )

jsLink.ready.then(render)
