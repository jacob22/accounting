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

define ['react', 'gettext', 'iter', 'utils'], (React, gettext, iter, utils) ->

    _ = gettext.gettext

    class CategoryCell extends React.Component

        constructor: (props) ->
            super props
            @state = data: ''

        handleChange: (evt) =>
            @props.onUpdate(evt.target.value)

        render: () ->
            if @props.readOnly
                try
                    name = @props.categories[@props.data].name
                catch
                    name = ''
                widget = <div className='form-control'>{name}</div>

            else
                options = [<option key=0 value="">{_('Choose category')}</option>]
                for toid, data of @props.categories
                    option = <option key={toid} value={toid}>{data.name}</option>
                    options.push(option)
                widget = <select className='form-control'
                    required
                    disabled={@props.readOnly}
                    onChange={@handleChange}
                    onBlur={@handleBlur}
                    defaultValue={@props.data}>
                    {options}
                </select>

            return <div className={@props.className}>
                {widget}
            </div>


    class TextCell extends React.Component

        constructor: (props) ->
            super(props)
            @state = data: props.data

        handleChange: (evt) =>
            @props.onUpdate(evt.target.value)

        handleKeyDown: (evt) =>
            if evt.keyCode == 13 or evt.keyCode == 9
                evt.target.blur()

        handleBlur: (evt) =>
            @setState(data: evt.target.value)

        render: () ->
            if @props.readOnly
                widget = <div className='form-control'>{@state.data}</div>
            else
                widget = <input
                    type='text'
                    disabled={@props.readOnly}
                    placeholder={_('Comment')}
                    className='form-control'}
                    onChange={@handleChange}
                    defaultValue={@state.data}
                    onKeyDown={@handleKeyDown}
                    onBlur={@handleBlur} />

            return <div className={@props.className}>
                {widget}
            </div>


    class CountCell extends TextCell

        render: () ->
            if @props.readOnly
                widget = <div className='form-control'>{@state.data}</div>
            else
                widget = <input
                    type='text'
                    className='form-control'}
                    disabled={@props.readOnly}
                    onChange={@handleChange}
                    defaultValue={@state.data}
                    onKeyDown={@handleKeyDown}
                    onBlur={@handleBlur} />

            return <div className={@props.className + ' input-group'}>
                {widget}
                <div className="input-group-addon">{@props.unit}</div>
            </div>


    class AmountCell extends TextCell

        @defaultProps:
            editable: false
            onUpdate: ->
            data: 0

        constructor: (props) ->
            super(props)
            @state = @_createStateFromProps(props)

        componentWillReceiveProps: (props) ->
            @setState(@_createStateFromProps(props))

        _createStateFromProps: (props) ->
            if props.data
                return data: utils.formatCurrency(props.data)
            else
                return data: ''

        handleBlur: (evt) =>
            data = utils.parseCurrency(evt.target.value)
            if data?
                @props.onUpdate(data)

        handleChange: (event) ->
            filtered = event.target.value.replace(/[^-0-9,.: ]/g, '')
            @setState(data: filtered)

        render: () ->
            if @props.editable
                if @props.readOnly
                    content = <div className='form-control'>{@state.data}</div>
                else
                    content = <input
                        type='text'
                        className='form-control'
                        placeholder={_('Amount')}
                        onChange={@handleChange}
                        onBlur={@handleBlur}
                        onKeyDown={@handleKeyDown}
                        value={@state.data} />
            else
                content = <span className='form-control'>
                    {utils.formatCurrency(@props.data)}
                </span>
            return <div className={@props.className}>
                {content}
            </div>


    class ExpenseLine extends React.Component

        @defaultProps:
            id: null
            category: ''
            categories: {}
            text: ''
            amount: 0
            onUpdate: ->

        categoryUpdated: (value) =>
            @props.onUpdate(@props.id, 'category', value)

        textUpdated: (value) =>
            @props.onUpdate(@props.id, 'text', value)

        countUpdated: (value) =>
            @props.onUpdate(@props.id, 'count', value)

        amountUpdated: (value) =>
            @props.onUpdate(@props.id, 'amount', value)

        render: () ->
            type = 'expense.Category'
            category = @props.categories[@props.category]
            if category?
                type = category._tocName

            <div className='row'>
                <CategoryCell
                    readOnly={@props.readOnly}
                    categories={@props.categories}
                    className='col-md-4'
                    data={@props.category}
                    onUpdate={@categoryUpdated}
                    />
                <TextCell
                    readOnly={@props.readOnly}
                    className={if type == 'expense.CategoryCountable' then 'col-md-4' else 'col-md-6'}
                    data={@props.text}
                    onUpdate={@textUpdated}
                    />
                {if type == 'expense.CategoryCountable' then <CountCell
                    readOnly={@props.readOnly}
                    className='col-md-2 count'
                    unit={if category? then category.unit}
                    data={@props.count}
                    onUpdate={@countUpdated}
                    />}
                <AmountCell
                    className='col-md-2 amount'
                    readOnly={@props.readOnly}
                    editable={type == 'expense.Category'}
                    data={@props.amount}
                    onUpdate={@amountUpdated}
                    />
            </div>


    class ExpenseGrid extends React.Component

        @defaultProps:
            id: null
            categories: {}
            lines: []

        constructor: (props) ->
            super props
            ids = iter.count(1)
            @state =
                lines: props.lines.concat([id: ids.next()])
                ids: ids

        componentWillReceiveProps: (props, state) ->
            if props.lines?
                lines = props.lines
                if lines.length
                    [last] = lines[-1..]
                    addEmpty = last.category
                else
                    addEmpty = true

                if addEmpty and not props.readOnly
                    lines = lines.concat([id: @state.ids.next()])

                @setState(lines: lines)

        recalcLine: (line, field) ->
            category = @props.categories[line.category]
            unless category?
                return

            if field == 'count'
                line.amount = line.count * category.price

            if field == 'category'
                if category._tocName == 'expense.CategoryOne'
                    line.amount = category.price

        calcSum: () ->
            sum = 0
            for line in @state.lines
                if line.amount?
                    sum += line.amount
            return sum

        onUpdate: (id, field, value) =>
            lines = @state.lines
            for line in lines
                if line.id == id
                    line[field] = value
                    @recalcLine(line, field)
                    break

            last = lines[lines.length - 1]
            if last.category and last.amount
                # add new line if last is complete
                lines.push(id: @state.ids.next())

            @setState(lines: lines)
            @props.handleChange(lines)

        render: () ->
            lines = (
                <ExpenseLine
                    id={line.id}
                    key={line.id}
                    readOnly={@props.readOnly}
                    category={line.category}
                    categories={@props.categories}
                    classNames={@props.classNames}
                    count={line.count}
                    text={line.text}
                    amount={line.amount}
                    onUpdate={@onUpdate}
                    /> for line in @state.lines
            )

            return <div>
                {lines}
                <div className='row'>
                    <div className='col-md-12 form-inline'>
                        <div className='pull-md-right input-group'>
                            <div className='input-group-addon'>{_('Sum')}</div>
                            <div className='sum form-control'>
                                {utils.formatCurrency(@calcSum())}
                            </div>
                        </div>
                    </div>
                </div>
            </div>

    return (
        CategoryCell: CategoryCell
        TextCell: TextCell
        AmountCell: AmountCell
        ExpenseLine: ExpenseLine
        ExpenseGrid: ExpenseGrid
    )
