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
    'react-select',
    'moment',
    'gettext',
    'iter',
    'signals',
    'utils',
    'widgets/amount',
    'widgets/date',
    'widgets/queryselect',
    'widgets/accountselector',
    'classnames',
    ], (
    React,
    Select,
    moment,
    gettext,
    iter,
    signals,
    utils,
    Amount,
    DatePicker,
    QuerySelect,
    AccountSelector,
    classnames
    ) ->

    require('react-select/dist/react-select.css')

    _ = gettext.gettext

    class SeriesSelect extends QuerySelect

        get_label_for_toi: (toi) ->
            name = toi.name[0]
            description = toi.description[0]
            if description?
                return "#{name} - #{description}"
            return name


    class TextSelect extends React.Component

        get_options: (input, callback) =>
            unless @props.transaction_index?
                callback(null, options: [
                    {value: input, label: input},
                    {value: @props.value, label: @props.value}
                ])
            else
                @props.transaction_index.complete(input, callback)
            return null

        _filterOptions: (options, filterString, values) ->
            return options

        onChange: (option) =>
            if @props.transaction_index?
                @props.transaction_index.push(option.value)
            @props.onChange(option.value)

        render: () ->
            <Select.AsyncCreatable
                onChange=@onChange
                loadOptions=@get_options
                loadingPlaceholder={_('Enter text')}
                filterOptions=@_filterOptions
                arrowRenderer={-> <span/>}
                autosize=false
                clearable=false
                value=@props.value
                tabSelectsValue=false
                ignoreCase=false
                ignoreAccents=false
                cache=false
                disabled=@props.readOnly
            />


    class Line extends React.Component

        @defaultProps:
            id: null
            account: null
            debit: null
            credit: null
            text: null

        _account_changed: (account) =>
            @props.handle_account_change(@props.id, account)

        _text_changed: (value) =>
            @props.handle_text_change(@props.id, value)

        _debit_changed: (value) =>
            @props.handle_debit_change(@props.id, value)

        _credit_changed: (value) =>
            @props.handle_credit_change(@props.id, value)

        render: ->
            if @props.account? and @props.account.exists
                account = @props.account
            else
                account = null

            if @props.diff? and not @props.debit and not @props.credit
                # This is an empty line and there is an inbalance diff to
                # prefill the amount widget when it receives focus,
                # such that it will balance the verification.
                if @props.diff < 0
                    suggestDebit = Math.abs(@props.diff)
                else if @props.diff > 0
                    suggestCredit = Math.abs(@props.diff)

            return <tr>
                <td className='account'>
                    <AccountSelector
                        query=@props.accounts_query
                        handleChange=@_account_changed
                        selected=@props.account
                        allow_empty=true
                        placeholder={_('No account')}
                        disabled=@props.readOnly
                        />
                </td>
                <td className='text'>
                    <TextSelect
                        transaction_index=@props.transaction_index
                        onChange=@_text_changed
                        value={if @props.text? then @props.text else ''}
                        readOnly=@props.readOnly
                        />
                </td>
                <td className='debit'>
                    <Amount
                        value=@props.debit
                        suggestValue=suggestDebit
                        onUpdate=@_debit_changed
                        readOnly=@props.readOnly
                        />
                </td>
                <td className='credit'>
                    <Amount
                        value=@props.credit
                        suggestValue=suggestCredit
                        onUpdate=@_credit_changed
                        readOnly=@props.readOnly
                        />
                </td>
            </tr>


    class Verification extends React.Component

        @defaultProps:
            verification: null  # toid
            verDataAggregator: null
            showMetadata: false
            showMetadataForm: true
            showButtons: true
            padTables: true
            pullData: () -> ;,
            readOnly: false

        constructor: (props) ->
            super(props)
            @state = @_get_empty_state()

        componentDidMount: () ->
            signals.connect(@props.verDataAggregator, 'refresh', @_data_updated)
            @props.verDataAggregator.start()

        componentWillReceiveProps: (props) ->
            unless @props.verDataAggregator is props.verDataAggregator
                @setState(@_get_empty_state())
                signals.disconnect(@props.verDataAggregator, 'refresh', @_data_updated)
                @props.verDataAggregator.stop()
                props.verDataAggregator.start()
                signals.connect(props.verDataAggregator, 'refresh', @_data_updated)
            # Experimental stuff for proposing registrationVerifications.
            if props.defaultlines? and props.defaultlines != @props.defaultlines
                # Only apply once: when we got the data from parent.
                @_applyPrediction(props.defaultlines)

        componentWillUnmount: () ->
            signals.disconnect(@props.verDataAggregator, 'refresh', @_data_updated)
            @props.verDataAggregator.stop()

        _get_empty_state: () ->
            return {
                dirty: false
                loading: true
                date: moment()
                series: null
                lines: []
                saving: false
            }

        _series_changed: (series) =>
            @setState(
                series: series,
                dirty: true
            )

        _date_changed: (date) =>
            @setState(
                date: date,
                dirty: true
            )

        _set_line_data: (id, key, value) ->
            lines = @state.lines
            debit = credit = 0
            add_empty_line = true
            for line in @state.lines
                if line.id == id
                    line[key] = value

                if line.debit?
                    debit += line.debit
                if line.credit?
                    credit += line.credit

                add_empty_line = line.account?

            if add_empty_line and not @props.readOnly
                lines.push(id: "empty-#{ @state.lineids.next() }", version: 0)

            dirty = @_compare_data_changed(lines)

            @setState(
                lines: lines
                debit: debit
                credit: credit
                diff: debit - credit
                dirty: dirty
            )

            @_pushToParent(lines, dirty)

        _line_account_changed: (id, value) =>
            @_set_line_data(id, 'account', value)

        _line_text_changed: (id, value) =>
            @_set_line_data(id, 'text', value)

        _line_debit_changed: (id, value) =>
            @_set_line_data(id, 'debit', value)

        _line_credit_changed: (id, value) =>
            @_set_line_data(id, 'credit', value)

        _data_updated: =>
            lines = []
            debit = @props.verDataAggregator.amount
            lineids = iter.count(1)

            tot_debit = tot_credit = 0
            for line in @props.verDataAggregator.lines
                amount = line.amount
                debit = null
                credit = null
                if amount < 0
                    credit = -1 * amount
                    tot_credit += credit
                else if amount > 0
                    debit = amount
                    tot_debit += debit

                lines.push(
                    id: line.id
                    account: line.account
                    text: line.text
                    debit: debit
                    credit: credit
                    version: line.version
                )

            if not @props.readOnly
                lines.push(id: "empty-#{ lineids.next() }", version: 0)

            verificationVersion = @props.verDataAggregator.verificationVersion

            @setState(
                loading: false
                lines: lines
                lineids: lineids
                valid: false
                debit: tot_debit
                credit: tot_credit
                diff: tot_debit - tot_credit
                verificationVersion: verificationVersion
                dirty: false
            )

        _applyPrediction: (predictedLines) ->
            # Examine possibility to merge/deduplicate this with @_data_updated
            lines = []
            lineids = iter.count(1)
            tot_debit = tot_credit = 0
            for line in predictedLines
                amount = line.amount
                debit = null
                credit = null
                if amount < 0
                    credit = -1 * amount
                    tot_credit += credit
                else if amount > 0
                    debit = amount
                    tot_debit += debit
                lines.push(
                    id: "predictionline-#{ lineids.next() }"
                    account: line.account
                    text: line.text
                    debit: debit
                    credit: credit
                    version: line.version
                )

            if not @props.readOnly
                lines.push(id: "empty-#{ lineids.next() }", version: 0)

            dirty = true
            @setState(
                loading: false
                lines: lines
                lineids: lineids
                debit: tot_debit
                credit: tot_credit
                valid: false
                verificationVersion: 0
                dirty: dirty
            )
            @_pushPredictionToParent(lines, dirty)

        _compare_data_changed: (lines) =>
            debit = @props.verDataAggregator.amount

            tot_debit = tot_credit = 0
            i = 0
            for orgline in @props.verDataAggregator.lines
                line = lines[i]
                amount = orgline.amount
                if amount < 0
                    credit = -1 * amount
                    if credit != line.credit
                        # Credit was modified
                        return true
                else if amount > 0
                    debit = amount
                    if debit != line.debit
                        # Debit was modified
                        return true
                if line.text != orgline.text
                    return true
                if line.account != orgline.account
                    return true
                i += 1

            while line = lines[i]
                if line.account? and (line.debit or line.credit)
                    return true
                i += 1

            return false

        _is_valid: ->
            unless @state.series
                return false
            unless @state.date
                return false
            unless @_lines_valid()
                return false
            return true

        _lines_valid: ->
            amount = 0
            lines_with_account = 0
            for line in @state.lines
                if line.account?
                    lines_with_account += 1
                    amount += line.credit || 0
                    amount -= line.debit || 0

            unless amount == 0
                return false

            unless lines_with_account >= 2
                return false

            return true

        _revert: =>
            @setState(@_get_empty_state())
            @props.verDataAggregator.restart()

        _save: =>
            lines = []
            for line in @state.lines
                if line.account? and (line.debit or line.credit)
                    lines.push(line)

            @setState(saving: true)

            @props.save(
                date: @state.date
                series: @state.series
                lines: lines
            )

        _pushToParent: (lines, dirty) =>
            if @_lines_valid()
                lines = []
                for line in @state.lines
                    if line.account? and (line.debit or line.credit)
                        lines.push({
                            id: line.id
                            account: line.account
                            text: line.text
                            amount: if line.debit? then line.debit else -line.credit
                            version: line.version
                        })
                @props.pullData(@props.verification, dirty, lines, @state.verificationVersion)

        _pushPredictionToParent: (lines, dirty) =>
            # Examine possibility to merge this with @_pushToParent
            checkedlines = []
            for line in lines
                if line.account? and (line.debit or line.credit)
                    checkedlines.push({
                        account: line.account
                        text: line.text
                        amount: if line.debit? then line.debit else -line.credit
                    })
            @props.pullData(null, dirty, checkedlines, 0)

        render: ->
            if @state.loading
                verification = <div className='verification text-sm-center'>
                    {_('Loading...')}
                </div>
            else
                lines = (
                    <Line
                        key=line.id
                        id=line.id
                        account=line.account
                        text=line.text
                        debit=line.debit
                        credit=line.credit
                        diff=@state.diff
                        accounts_query=@props.verDataAggregator.accounts_query
                        transaction_index=@props.verDataAggregator.transaction_index
                        jsLink=@props.verDataAggregator.jsLink
                        handle_account_change=@_line_account_changed
                        handle_text_change=@_line_text_changed
                        handle_debit_change=@_line_debit_changed
                        handle_credit_change=@_line_credit_changed
                        readOnly={@props.readOnly}
                    /> for line in @state.lines
                )

                verification = <div className='verification'>
                    {<div className='metadata'>
                        <label className='mr-1'>
                            {_('Verification')}
                        </label>
                        {@props.verDataAggregator.verificationSeries}
                        <label className='mx-1'>
                            {@props.verDataAggregator.verificationNumber}
                        </label>
                    </div> if @props.showMetadata and @props.verDataAggregator.verificationSeries? and @props.verDataAggregator.verificationNumber?}
                    {<div className='form-inline metadata'>
                        <label htmlFor='series' className='col-form-label'>
                            {_('Series')}
                        </label>
                        <SeriesSelect
                            query=@props.verDataAggregator.series_query
                            selected=@state.series
                            handleChange=@_series_changed
                            className='series-select'
                            placeholder={_('Select series')}
                            readOnly={@props.readOnly}
                            />
                        <label htmlFor='date' className='ml-4 col-form-label'>
                            {_('Date')}
                        </label>
                        <DatePicker
                            id='date'
                            label='Datum:'
                            handleChange=@_date_changed
                            date=@state.date
                            readOnly={@props.readOnly}
                            />
                    </div> if @props.showMetadataForm}
                    <table className={classnames(
                        'table table-striped': @props.padTables
                        'w-100': not @props.padTables
                    )}>
                        {
                            <thead>
                                <tr>
                                    <th className='account'>{_('Account')}</th>
                                    <th className='text'>{_('Text')}</th>
                                    <th className='debit'>{_('Debit')}</th>
                                    <th className='credit'>{_('Credit')}</th>
                                </tr>
                            </thead> if lines.length
                        }
                        {
                            <tfoot>
                                <tr>
                                    <td colSpan=1></td>
                                    <td className={classnames(
                                        'diff': true
                                        'text-sm-right': true
                                        )}>
                                        {<Amount
                                            value={@state.diff}
                                            readOnly={true}
                                            className={classnames(
                                                'form-control': true
                                                'form-control-plaintext': false
                                                'text-right': true
                                            )}
                                            /> if @state.diff != 0}
                                    </td>
                                    <td className={classnames(
                                            'debit': true
                                            'text-sm-right': true
                                            )}>

                                        {<Amount
                                            value={@state.debit if @state.debit != 0}
                                            readOnly={true}
                                            className={classnames(
                                                'form-control': true
                                                'text-right': true
                                                'is-valid':  @_lines_valid()
                                                'is-invalid': not @_lines_valid()
                                            )}
                                            /> if @state.debit != 0 or @state.credit != 0 }
                                    </td>
                                    <td className={classnames(
                                            'credit': true
                                            'text-sm-right': true
                                            )}>
                                        {<Amount
                                            value={@state.credit if @state.credit != 0}
                                            className={classnames(
                                                'form-control': true
                                                'text-right': true
                                                'is-valid':  @_lines_valid()
                                                'is-invalid': not @_lines_valid()
                                            )}
                                            readOnly={true}
                                            /> if @state.debit != 0 or @state.credit != 0 }
                                    </td>
                                </tr>
                            </tfoot>
                        }
                        <tbody>
                            {lines}
                        </tbody>
                    </table>
                    {<div className='actions'>
                        <button
                            className='btn'
                            onClick=@_revert
                            disabled={not @state.dirty or @state.saving}>
                                {_('Revert')}
                        </button>
                        <button
                            id='save'
                            className='btn'
                            onClick=@_save
                            disabled={not @_is_valid() or @state.saving}>
                                {if @state.saving then _('Saving...') else _('Save')}
                        </button>
                    </div> if @props.showButtons }
                </div>

            return verification
