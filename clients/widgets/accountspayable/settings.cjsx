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

define [
    'react',
    'react-dom',
    'gettext',
    'utils',
    'moment',
    'signals',
    'jslink/JsLink',
    'jslink/query',
    'jslink/commit',
    'classnames',
    'widgets/queryselect',
    'widgets/accountselector',
    ], (
    React,
    ReactDOM,
    gettext,
    utils,
    moment,
    signals,
    JsLink,
    query,
    commit,
    classnames,
    QuerySelect,
    AccountSelector,
    ) ->

    _ = gettext.gettext

    class SeriesSelect extends QuerySelect
        get_label_for_toi: (toi) ->
            name = toi.name[0]
            description = toi.description[0]
            if description?
                return "#{name} - #{description}"
            return name

    class Settings extends React.Component
        @defaultProps:
            accountsQuery: {result: []}
            seriesQuery: {result: []}
            #providerQuery: {result: []}

        constructor: (props) ->
            super(props)
            @state = {text: ''}
            state = @_prepareState(props)
            @state = state
            
        componentWillReceiveProps: (nextProps) ->
            state = @_prepareState(nextProps)
            @setState(state)

        _prepareState: (props) ->
            newstate = {}
            if not props.accountsQuery.result.length > 0 or not props.seriesQuery.result.length > 0
                # Wait for queries
                return {}
            if props.providerQuery.result.length == 0
                # No provider yet
                return {}
            else if props.providerQuery.result.length == 1
                toid = props.providerQuery.result[0]
                provider = props.providerQuery.toiData[toid]
                if provider?
                    series = provider.series[0]
                    account = provider.account[0]
                    bankAccount = provider.bank_account[0]
                    for toid, toi of @props.accountsQuery.toiData
                        if toi.number[0] == account
                            debtAccountId = toid
                        if toi.number[0] == bankAccount
                            bankAccountId = toid
                    for toid, toi of @props.seriesQuery.toiData
                        if toi.name[0] == series
                            seriesId = toid
                    text = provider.transferVerification_text[0]
                    pgAccount = provider.plusgiro_sending_bank_account[0]
                    newstate = {
                        series: series,
                        seriesId: seriesId,
                        debtAccount: account,
                        debtAccountId: debtAccountId,
                        bankAccount: bankAccount,
                        bankAccountId: bankAccountId,
                        text: text,
                        originaltext: text,
                        pgAccount: pgAccount,
                        originalPgAccount: pgAccount,
                    }
            else if props.providerQuery.result.length > 1
                console.log('Error: Multiple providers!')
            return newstate


        _series_changed: (seriesId) =>
            if seriesId == @state.seriesId
                # No change
                return
            if seriesId?
                seriesToi = @props.seriesQuery.toiData[seriesId]
                seriesName = seriesToi['name'][0]
                @setState(
                    seriesId: seriesId
                    series: seriesName,
                )
                @_saveSettings(seriesName, @state.debtAccount, @state.bankAccount, @state.text)
            else
                @setState(
                    seriesId: undefined
                    series: undefined
                )


        _account_changed_debt: (accountId) =>
            if accountId == @state.debtAccountId
                # No change
                return
            if accountId?
                accountToi = @props.accountsQuery.toiData[accountId]
                accountNo = accountToi['number'][0]
                @setState(
                    debtAccountId: accountId,
                    debtAccount: accountNo,
                )
                @_saveSettings(@state.series, accountNo, @state.bankAccount, @state.text)
            else
                @setState(
                    debtAccountId: undefined,
                    debtAccount: undefined,
                )

        _account_changed_bank: (accountId) =>
            if accountId == @state.bankAccountId
                # No change
                return
            if accountId?
                accountToi = @props.accountsQuery.toiData[accountId]
                accountNo = accountToi['number'][0]
                @setState(
                    bankAccountId: accountId,
                    bankAccount: accountNo,
                )
                @_saveSettings(@state.series, @state.debtAccount, accountNo, @state.text)
            else
                @setState(
                    bankAccountId: undefined,
                    bankAccount: undefined,
                )

        _update_text: (event) =>
            # For every character entered
            text = event.target.value
            @setState(text: text)

        _text_changed: () =>
            # onBlur, save if needed
            if @state.text != @state.originaltext
                @_saveSettings(@state.series, @state.debtAccount, @state.bankAccount, @state.text, @state.pgAccount)

        _update_pgAccount: (event) =>
            # For every character entered
            text = event.target.value
            @setState(pgAccount: utils.parseBankaccount(text))

        _pgAccount_changed: () =>
            # onBlur, save if needed
            if @state.pgAccount != @state.originalPgAccount
                @_saveSettings(@state.series, @state.debtAccount, @state.bankAccount, @state.text, @state.pgAccount)

        _saveSettings: (series, debtAccount, bankAccount, text, pgAccount) =>
            callback = () =>
                @setState({saving: false})
            if series? and debtAccount? and bankAccount? and text?
                @props.saveSettings({
                    series: series,
                    account: debtAccount,
                    bank_account: bankAccount,
                    transferVerification_text: text,
                    plusgiro_sending_bank_account: pgAccount,
                }, callback)
                @setState({saving: true})

        render: ->
            <div
                id='settingsModal'
                className={
                    classnames(
                        'modal': true
                        'fade': true
                    )
                }
                tabIndex="-1"
                role="dialog"
                aria-hidden="true"
                >
                <div className="modal-dialog modal-lg">
                    <div className="modal-content" role="document">
                        <div className='modal-header'>
                            <h4 className="modal-title">{_('Settings')}</h4>
                        </div>
                        <div className='modal-body'>
                            <p>{_('Select verification series, account for payables and receivables, and the bank account from which to draw money on transfer.')}</p>
                            <div className='form-group row'>
                                <div className='col-3'>
                                    <label htmlFor='settings-series' className='col-form-label'>
                                        {_('Series')}
                                    </label>
                                </div>
                                <div className='col'>
                                    <SeriesSelect
                                        htmlId='settings-series'
                                        query={@props.seriesQuery}
                                        selected={@state.seriesId}
                                        handleChange={@_series_changed}
                                        className='series-select'
                                        placeholder={_('Select series')}
                                        />
                                </div>
                            </div>
                            <div className='form-group row'>
                                <div className='col-3'>
                                    <label htmlFor='accountselector-supplier-debt-account' className='col-form-label'>
                                        {_('Supplier debt account')}
                                    </label>
                                </div>
                                <div className='col'>
                                    <AccountSelector
                                        query={@props.accountsQuery}
                                        handleChange={@_account_changed_debt}
                                        selected={@state.debtAccountId}
                                        allow_empty={true}
                                        placeholder={_('Select account')}
                                        />
                                </div>
                            </div>
                            <div className='form-group row'>
                                <div className='col-3'>
                                    <label htmlFor='accountselector-bank' className='col-form-label'>
                                        {_('Bank account')}
                                    </label>
                                </div>
                                <div className='col'>
                                    <AccountSelector
                                        query={@props.accountsQuery}
                                        handleChange={@_account_changed_bank}
                                        selected={@state.bankAccountId}
                                        allow_empty={true}
                                        placeholder={_('Select account')}
                                        />
                                </div>
                            </div>
                            <div className='form-group row'>
                                <div className='col-3'>
                                    <label htmlFor='settings-text' className='col-form-label'>
                                        {_('Transfer verification text')}
                                    </label>
                                </div>
                                <div className='col'>
                                    <input
                                        id='settings-text'
                                        type='text'
                                        className='form-control'
                                        value={@state.text or ''}
                                        onChange={@_update_text}
                                        onBlur={=> @_text_changed()}
                                        />
                                </div>
                            </div>
                            <div className='form-group row'>
                                <div className='col-3'>
                                    <label htmlFor='settings-pgaccount' className='col-form-label'>
                                        {_('Plusgiro payment order file: sending bank account')}
                                    </label>
                                </div>
                                <div className='col'>
                                    <input
                                        id='settings-pgaccount'
                                        type='text'
                                        className='form-control'
                                        value={@state.pgAccount or ''}
                                        onChange={@_update_pgAccount}
                                        onBlur={=> @_pgAccount_changed()}
                                        />
                                </div>
                            </div>
                        </div>
                        <div className='modal-footer'>
                            <div className={classnames(
                                'has-spinner': true
                                'float-right': true
                                'mr-0': true
                                'd-none': not @state.saving
                                'active': @state.saving
                            )}>
                                <span className='spinner'>
                                    <i className="fa fa-spinner fa-spin" aria-hidden="true"></i> {_('Saving...')}
                                </span>
                            </div>
                            <button
                                type="button"
                                className={classnames(
                                    'btn': true
                                    'btn-outline-dark': true
                                    'disabled': @state.saving
                                )}
                                onClick={=> $('#settingsModal').modal('hide')}>{_('Close')}</button>
                        </div>
                    </div>
                </div>
            </div>
