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
    'reactstrap',
    'utils',
    'widgets/accountselector',
    'gettext'
    ], (
    React,
    reactstrap,
    utils,
    AccountSelector,
    gettext) ->

    _ = gettext.gettext

    class AccountCell extends React.Component

        handleChange: (toid) =>
            for __, toi of @props.accounts_query.toiData
                if toi._id[0] == toid
                    @props.handleChange(toi.number[0])
                    break

        render: ->
            selected = @props.account_by_number[@props.number]

            content = <AccountSelector
                selected=selected
                query=@props.accounts_query
                handleBlur=@handleBlur
                handleChange=@handleChange />

            return <td className='account'>
                {content}
            </td>


    class EditableCell extends React.Component

        handleChange: (evt) =>
            @props.handleChange(evt.target.value)

        render: ->
            value = if @props.value? then @props.value else ''

            widget = <input
                type='text'
                className='form-control'
                value=@props.value
                onChange=@handleChange
                onBlur=@handleBlur
                />

            return <td className=@props.className>{widget}</td>


    class AmountCell extends React.Component

        constructor: (props) ->
            super(props)
            @state = @_createStateFromProps(props)

        componentWillReceiveProps: (props) ->
            @setState(@_createStateFromProps(props))

        _createStateFromProps: (props) ->
            if props.value
                return value: utils.formatCurrency(props.value)
            else
                return value: ''

        handleBlur: (evt) =>
            value = utils.parseCurrency(evt.target.value)
            if value?
                @props.handleChange(value)

        handleChange: (evt) =>
            filtered = evt.target.value.replace(/[^-0-9,.: ]/g, '')
            @setState(value: filtered)

        render: ->
            widget = <input
                type='text'
                className='form-control'
                value=@state.value
                onChange=@handleChange
                onBlur=@handleBlur
                />

            return <td className=@props.className>{widget}</td>


    class Row extends React.Component

        constructor: (props) ->
            super(props)
            @state =
                account: null
                name: null
                price: null
                unit: null
                saving: false
                showDeleteConfirmation: false

        _account_changed: (account) =>
            @setState(account: account)

        _name_changed: (name) =>
            @setState(name: name)

        _price_changed: (price) =>
            @setState(price: price)

        _unit_changed: (unit) =>
            @setState(unit: unit)

        save: =>
            @setState(saving: true)

            data = {}
            if @state.unit?
                data.unit = @state.unit
            if @state.account?
                data.account = @state.account
            if @state.name?
                data.name = @state.name
            if @state.price?
                data.price = @state.price

            if @props.toi._id?
                @props.handleChange(@props.toi._id[0], data, =>
                    @setState(
                        account: null
                        name: null
                        price: null
                        unit: null
                        saving: false
                    )
                )
            else
                @props.handleChange(data, ->)

        delete: =>
            @setState(showDeleteConfirmation: true)

        confirmDelete: =>
            @setState(
                showDeleteConfirmation: false
                saving: true
            )
            @props.handleDelete(@props.toi._id[0], ->)

        render: ->
            dirty = false
            price = unit = null

            if @props.toi._tocName in ['expense.CategoryCountable', 'expense.CategoryOne']
                price = utils.parseCurrency(@props.toi.price[0])

            if @props.toi._tocName == 'expense.CategoryCountable'
                unit = @props.toi.unit[0]

            account = if @props.toi.account? then @props.toi.account[0]
            if @state.account? and @state.account != account
                account = @state.account
                dirty = true

            name = if @props.toi.name? then @props.toi.name[0] else ''
            if @state.name? and @state.name != name
                name = @state.name
                dirty = true

            if @state.price? and @state.price != price
                price = @state.price
                dirty = true

            if @state.unit? and @state.unit != unit
                unit = @state.unit
                dirty = true

            if dirty
                label = if @state.saving then _('Saving') else _('Save')
                action = <button
                    className='btn'
                    disabled=@state.saving
                    onClick=@save>{label}</button>
            else if @props.toi._id?
                label = if @state.saving then _('Removing') else _('Remove')
                action = <button
                    type='button'
                    className='btn'
                    onClick=@delete
                    disabled=@state.saving
                    >{label}</button>
            else
                    action = <div />

            closeModal = => @setState(showDeleteConfirmation: false)

            modal = <reactstrap.Modal isOpen=@state.showDeleteConfirmation toggle=closeModal>
                <reactstrap.ModalHeader toggle=closeModal>
                    {_('Remove this category?')}
                </reactstrap.ModalHeader>
                <reactstrap.ModalBody>
                    <gettext.Message
                        message={_('Are you sure you want to permanently
                                    remove the category <em>{name}</em>?')}
                        attributes={name: name}
                        />
                </reactstrap.ModalBody>
                <reactstrap.ModalFooter>
                    <reactstrap.Button color='danger' onClick=@confirmDelete>
                        {_('Remove category')}
                    </reactstrap.Button>
                    <reactstrap.Button color='secondary' onClick=closeModal>
                        {_('No, keep this category')}
                    </reactstrap.Button>
                </reactstrap.ModalFooter>
            </reactstrap.Modal>

            <tr>
                <AccountCell
                    number=account
                    account_by_number=@props.account_by_number
                    accounts_query=@props.accounts_query
                    handleChange={@_account_changed}
                    />
                <EditableCell
                    value=name
                    className='name'
                    handleChange=@_name_changed
                    />
                {if @props.show_price then <AmountCell
                    value=price
                    className='price'
                    handleChange=@_price_changed
                    />}
                {if @props.show_unit then <EditableCell
                    value=unit
                    className='unit'
                    handleChange=@_unit_changed
                    />}
                <td className='action'>
                    {action}
                    {modal}
                </td>
            </tr>


    class Table extends React.Component

        defaultProps:
            unit: false
            price: false

        constructor: (props) ->
            super(props)
            @state =
                new_toi: false

        _add_row: =>
            @setState(new_toi: true)

        _saveNew: (data, callback) =>
            @props.handleCreate(@props.kind, data, =>
                @setState(new_toi: false)
                callback()
            )

        render: ->
            show_price = @props.kind != 'Category'
            show_unit = @props.kind == 'CategoryCountable'

            rows = (
                <Row
                    key={toid}
                    toid={toid}
                    toi={@props.categories[toid]}
                    show_price=show_price
                    show_unit=show_unit
                    accounts_query=@props.accounts_query
                    account_by_number=@props.account_by_number
                    handleChange=@props.handleChange
                    handleDelete=@props.handleDelete
                    /> for toid of @props.categories
            )

            if @state.new_toi
                toi = {}
                rows.push(
                    <Row
                        key=1
                        toi=toi
                        show_price=show_price
                        show_unit=show_unit
                        accounts_query=@props.accounts_query
                        account_by_number=@props.account_by_number
                        handleChange=@_saveNew
                        />
                )

            columns = 5
            show_price or columns -= 1
            show_unit or columns -= 1

            <div className='categorylist'>
                <h4>{@props.title}</h4>
                <table className='table table-striped table-hover'>
                    {if rows.length then <thead>
                        <tr>
                            <th>{_('Account')}</th>
                            <th>{_('Name')}</th>
                            {if show_price then <th>{_('Price')}</th>}
                            {if show_unit then <th>{_('Unit')}</th>}
                            <th></th>
                        </tr>
                    </thead>}
                    <tfoot>
                        <tr>
                            <td colSpan=columns>
                                <button
                                    className='btn add fa fa-plus'
                                    disabled={@state.new_toi}
                                    type='submit'
                                    onClick=@_add_row
                                    ><span>{_('Create new')}</span></button>
                            </td>
                        </tr>
                    </tfoot>
                    <tbody>
                        {rows}
                    </tbody>
                </table>
            </div>


    class Page extends React.Component

        render: ->

            sections = [
                [
                    'Category',
                    _('Standard expenses'),
                    @props.normal_categories
                ],
                [
                    'CategoryCountable',
                    _('Expenses with a fixed price per unit'),
                    @props.countable_categories
                ],
                [
                    'CategoryOne',
                    _('Expenses with a single, fixed price'),
                    @props.one_categories
                ]
            ]

            tables = (
                <Table
                    key=kind
                    kind=kind
                    title=title
                    categories=categories
                    account_by_number=@props.account_by_number
                    accounts_query=@props.accounts_query
                    handleChange=@props.handleChange
                    handleCreate=@props.handleCreate
                    handleDelete=@props.handleDelete
                    /> for [kind, title, categories] in sections
            )

            <div>
                {tables}
            </div>
