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

define ['react', 'gettext', 'signals', 'widgets/images'], (React, gettext, signals, Images) ->

    _ = gettext.gettext

    class ReportView extends React.Component

        constructor: (props) ->
            super(props)
            @state =
                id: null
                loading: false
                lineData: {}
                categoryData: {}

        componentWillMount: () ->
            @_set_verification(@props.verification)

        componentWillReceiveProps: (props) ->
            @_set_verification(props.verification)

        _setVerificationState: (state) ->
            @setState(loading: true)
            @props.setVerificationState(@state.id, state, () =>
                @setState(loading: false)
            )

        _approve: () =>
            @_setVerificationState('approved')

        _deny: () =>
            @_setVerificationState('denied')

        _handle: () =>
            @_setVerificationState('handling')

        _verification_changed: (watcher, setid, toiIds) =>
            for toid in toiIds
                @lineWatcher.watch(toid, watcher.getToiData(toid).lines)

        _line_changed: (watcher, setid, toiIds) =>
            lineData = {}
            categories = []
            for toid in toiIds
                lineData[toid] = data = watcher.getToiData(toid)
                categories = categories.concat(data.category)

            @categoryWatcher.watch(setid, categories)
            @setState(lineData: lineData)

        _category_changed: (watcher, setid, toiIds) =>
            categoryData = {}
            for toid in toiIds
                categoryData[toid] = watcher.getToiData(toid)
            @setState(
                categoryData: categoryData
                loading: false
            )

        _set_verification: (verification) ->
            @setState(
                id: verification
                loading: true
                lineData: {}
                categoryData: {}
            )

            if @lineWatcher?
                @lineWatcher.destroy()
            @lineWatcher = @props.lineWatcher.perspective()
            signals.connect(@lineWatcher, 'refresh', @_line_changed)

            if @categoryWatcher?
                @categoryWatcher.destroy()
            @categoryWatcher = @props.categoryWatcher.perspective()
            signals.connect(@categoryWatcher, 'refresh', @_category_changed)
            if @verWatcher?
                @verWatcher.destroy()
            @verWatcher = @props.verWatcher.perspective()
            signals.connect(@verWatcher, 'refresh', @_verification_changed)

            if verification?
                @verWatcher.watch('verification', [verification])

        render: () ->
            fetching = _('Fetching data...')
            verData = @verWatcher.getToiData(@state.id)

            if verData?
                state = verData.state[0]
                lines = []
                for lineid in verData.lines
                    lineData = @state.lineData[lineid]
                    unless lineData?
                        lines.push(
                            <tr key={lineid}>
                                <td colSpan=4>{fetching}</td>
                            </tr>
                        )
                        continue

                    category = @state.categoryData[lineData.category[0]]
                    if category?
                        categoryName = category.name
                        account = category.account
                    else
                        categoryName = ''
                        account = ''

                    if lineData.count.length
                        count = lineData.count[0]
                    else
                        count = '-'

                    lines.push(
                        <tr key={lineid}>
                            <td className='category'>{categoryName}</td>
                            <td className='account'>{account}</td>
                            <td className='text'>{lineData.text}</td>
                            <td className='count'>{count}</td>
                            <td className='amount'>{lineData.amount}</td>
                        </tr>
                    )

                verification = <div className='verification'>
                    {<div className='comment' key='comment'>
                        <h5>{_('Description')}</h5>
                        <span>{verData.text}</span>
                    </div> if verData.text.length}
                    <table className='table table-striped'>
                        {
                            <thead>
                                <tr>
                                    <th className='category'>{_('Expense category')}</th>
                                    <th className='account'>{_('Account')}</th>
                                    <th className='text'>{_('Note')}</th>
                                    <th className='count'>{_('Quantity')}</th>
                                    <th className='amount'>{_('Amount')}</th>
                                </tr>
                            </thead> if lines.length
                        }
                        {
                            <tfoot>
                                <tr>
                                    <td className='sum' colSpan=5><span>{_('Total')}:</span> {verData.amount}</td>
                                </tr>
                            </tfoot> if lines.length
                        }
                        <tbody>
                            {lines}
                        </tbody>
                    </table>
                    <hr />
                    <h5>{_('Receipts and documents')}</h5>
                    <Images
                        toid={@state.id}
                        attribute='receipt'
                        width=300 height=300
                        nocache=true
                        imageInfo={verData.receipt} />
                </div>
            else
                verification = <div>{fetching}</div>
                state = null

            bdef = [
                ['handling', _('Handle'), @_handle, 'btn-primary'],
                ['approved', _('Approve'), @_approve, 'btn-success'],
                ['denied', _('Deny'), @_deny, 'btn-danger']
            ]

            buttons = []
            for [_state, text, action, className] in bdef
                if _state != state
                    buttons.push(<button
                        key={_state}
                        className={'btn ' + className}
                        disabled={@state.loading}
                        onClick={action}
                        >{text}</button>)

            className = 'reportview'
            if @state.loading
                className += ' loading'

            <div className={className}>
                {verification}
                <hr />
                <div className='actions'>
                    {buttons}
                </div>
            </div>
