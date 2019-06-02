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
    'moment',
    'gettext',
    'signals',
    'utils',
    'widgets/date',
    'widgets/expensegrid',
    'widgets/receiptimages',
    ], (
    React,
    moment,
    gettext,
    signals,
    utils,
    DatePicker,
    ExpenseGrid,
    ReceiptImages) ->

    _ = gettext.gettext

    class ExpenseReport extends React.Component

        constructor: (props) ->
            super props
            @state = @_updateState(props)
            @lineWatcher = props.lineWatcher.perspective()
            signals.connect(@lineWatcher, 'refresh', @_line_changed)

        componentWillMount: ->
            if @props.toiData?
                @lineWatcher.watch('lines', @props.toiData.lines)

        componentWillReceiveProps: (props, state) ->
            @setState(@_updateState(props))
            @lineWatcher.unwatch('lines')
            if props.toiData?
                @lineWatcher.watch('lines', props.toiData.lines)

        _updateState: (props) ->
            if props.toiData?
                toiData = props.toiData
                state =
                    id: toiData._id[0]
                    date: moment(toiData.date[0], 'YYYY-MM-DD')
                    newFiles: []
                    oldFiles: toiData.receipt
                    text: toiData.text[0]
            else
                state =
                    id: null
                    date: moment()
                    newFiles: []
                    oldFiles: []
                    lines: []
                    text: ''
            return state

        dateChanged: (date) =>
            @setState(date: date)

        filesChanged: (newFiles, oldFiles) =>
            @setState(
                newFiles: newFiles
                oldFiles: oldFiles
            )

        _line_changed: (watcher, setid, toiIds) =>
            lines = []
            for toid in toiIds
                toiData = watcher.getToiData(toid)
                line =
                    id: toid
                    category: toiData.category[0]
                    text: toiData.text[0]
                    count: toiData.count[0] if toiData.count.length
                    amount: utils.parseCurrency(toiData.amount[0])
                lines.push(line)
            @setState(lines: lines)

        linesChanged: (lines) =>
            @setState(lines: lines)

        textChanged: (event) =>
            @setState(text: event.currentTarget.value)

        save: =>
            @setState(saving: true)
            @props.save(this, => @setState(saving: false))

        render: () ->
            if @props.readOnly
                misc = <div className='form-control'>{@state.text}</div>
            else
                misc = <textarea className='form-control'
                    id='expense-description' rows='5'
                    placeholder={_('Enter additional information here')}
                    disabled={@props.readOnly}
                    value={@state.text}
                    onChange={@textChanged}
                    ></textarea>

            return <div>
                <DatePicker
                    id='inkopsdatum'
                    readOnly={@props.readOnly}
                    label={_('Date of purchase')}
                    date={@state.date}
                    handleChange={@dateChanged}/>
                <ReceiptImages.ReceiptImages
                    toid={@state.id}
                    readOnly={@props.readOnly}
                    newFiles={@state.newFiles}
                    oldFiles={@state.oldFiles}
                    handleChange={@filesChanged} />
                <ExpenseGrid.ExpenseGrid
                    readOnly={@props.readOnly}
                    lineWatcher={@props.lineWatcher}
                    lines={@state.lines}
                    categories={@props.categories}
                    handleChange={@linesChanged} />
                <div className='form-group'>
                    <label htmlFor='expense-description'>{_('Additional information')}</label>
                    {misc}
                </div>
                {<div className='save'>
                    <button
                        className='btn'
                        disabled={@state.saving}
                        onClick={@save}>
                            {if @state.saving then _('Saving...') else _('Save')}
                    </button>
                </div> if not @props.readOnly}
            </div>
