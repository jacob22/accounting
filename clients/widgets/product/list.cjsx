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

# This module expectes product-list.css to be loaded

define(['react', 'reactstrap', 'gettext', 'iter', 'signals', 'utils'], ->
    [React, rs, gettext, iter, signals, utils] = arguments

    Collapse = rs.Collapse
    Card = rs.Card
    CardBlock = rs.CardBlock

    _ = gettext.gettext

    ids = iter.count()

    class Option extends React.Component

        constructor: (props) ->
            super(props)
            @state =
                id: "option-#{ids.next()}"

        onChange: (event) =>
            @props.onChange(@props.index, event.target.value)

        render: ->
            fieldClass = 'form-control col-9'
            id = "#{@state.id}-field"

            placeholder = ''
            if @props.data_source.type == 'personnummer'
                placeholder='YYMMDD-NNNN'
            else if @props.data_source.mandatory
                placeholder = _('This field is mandatory')

            props =
                id: id
                className: fieldClass
                onChange: @onChange
                placeholder: placeholder

            if @props.read_only
                field = <input type='text' disabled {...props} />

            else if @props.data_source.type == 'text'
                field = <input type='text' {...props} />

            else if @props.data_source.type == 'textarea'
                field = <textarea {...props} />

            else if @props.data_source.type == 'select'
                keys = iter.count()
                options = []
                for option in JSON.parse(@props.data_source.typedata).options
                    options.push(
                        <option key=keys.next() value=option.name>
                            {option.name}
                        </option>
                    )
                field = <select {...props}>
                    {options}
                </select>

            else if @props.data_source.type == 'personnummer'
                field = <input type='text' {...props} />

            labelClass = 'col-2 col-form-label'
            if @props.data_source.mandatory
                labelClass += ' mandatory'

            <div className={"option form-inline #{'has-danger' if @props.invalid}"}>
                <label
                    className=labelClass
                    htmlFor="#{@state.id}-field">{@props.data_source.label}</label>
                {field}
            </div>


    class Row extends React.Component

        constructor: (props) ->
            super(props)
            @state =
                id: "product-#{ids.next()}"
                open: false
                indicator: 'fa-chevron-down'

            indexes = iter.count()
            for option in @props.data_source.options
                index = indexes.next()
                if option.type == 'select'
                    for o in JSON.parse(option.typedata).options
                        @state["option-#{index}"] = o.name
                        break

        _set_option: (index, value) =>
            @setState("option-#{index}": value)

        _add: =>
            options = []
            indexes = iter.count()
            for option in @props.data_source.options
                index = indexes.next()
                value = @state["option-#{index}"]
                unless value?
                    value = null
                options.push([option.label, value])

            item =
                id: @props.data_source.id
                name: @props.data_source.name
                price: @props.data_source.price
                options: options
                count: 1

            @props.cart.add(item)

        _toggle_collapse: =>
            @setState(open: not @state.open)

        _onOpened: =>
            @setState(indicator: 'fa-chevron-up')

        _onClosed: =>
            @setState(indicator: 'fa-chevron-down')

        is_valid: ->
            if @props.data_source.currentStock == 0
                return false

            indexes = iter.count()
            for option in @props.data_source.options
                index = indexes.next()
                data = @state["option-#{index}"]
                unless option.is_valid(data)
                    return false
            return true

        render: ->
            currency = utils.formatCurrency(@props.data_source.price, ':')

            options = []
            keys = iter.count()
            mandatory = false
            for option in @props.data_source.options
                key = index = keys.next()
                value = @state["option-#{index}"]
                options.push(
                    <Option
                        index=index
                        key=key
                        data_source=option
                        read_only={@props.data_source.currentStock == 0}
                        invalid={value? and not option.is_valid(value)}
                        onChange=@_set_option />
                )
                mandatory = mandatory or option.mandatory

            if mandatory
                mandatory = <gettext.Message
                    className='mandatory-explanation'
                    message={_('Fields marked with
                                <span class="mandatory"></span>
                                are mandatory.')} />
            else
                mandatory = null

            if @props.data_source.currentStock?
                stock = <div className='stock pull-right'>
                    {_('Quantity remaining')}: {@props.data_source.currentStock}
                </div>
            else
                stock = null

            return <div className='product card'>
                <div
                    onClick=@_toggle_collapse
                    className='row-header'>
                    <div className='card-header'>
                        <span className='price'>{currency}</span>
                        <i className={'fa mr-3 ' + @state.indicator}
                            aria-hidden></i>
                        <span className='name'>{@props.data_source.name}</span>
                    </div>
                </div>
                <Collapse isOpen=@state.open id="#{@state.id}-content"
                    onOpened=@_onOpened onClosed=@_onClosed >
                    <Card>
                        <CardBlock className='card-body'>
                            <p className='description'>
                                {@props.data_source.description}
                            </p>
                            <div className='options'>
                                {options}
                            </div>
                            <div className='pull-right'>
                                <button
                                    className='btn'
                                    disabled={not @is_valid()}
                                    onClick=@_add>{_('Add')}</button>
                            </div>
                            {mandatory}
                            {stock}
                        </CardBlock>
                    </Card>
                </Collapse>
            </div>


    class Section extends React.Component

        constructor: (props) ->
            super(props)
            @state =
                id: "product-section-#{ids.next()}"
                open: false
                indicator: 'fa-chevron-down'

        top_level: ->
            return !@props.data_source.name

        _toggle_collapse: =>
            @setState(open: not @state.open)

        _onOpened: =>
            @setState(indicator: 'fa-chevron-up')

        _onClosed: =>
            @setState(indicator: 'fa-chevron-down')

        render: ->
            rows = []
            for product in @props.data_source.products
                rows.push(
                    <Row
                        key=product.id
                        data_source=product
                        cart=@props.cart
                        />
                )

            product_count = @props.data_source.products.length

            if @top_level()
                return <div className='section'>
                    {rows}
                </div>
            else
                return <div id=@state.id className='section card' >
                    <div onClick=@_toggle_collapse
                        className='section-name card-header'>
                        <span className='product-count'>
                            {product_count + ' ' + _('products')}
                        </span>
                        <i className={'fa mr-3 ' + @state.indicator}
                            aria-hidden></i>
                        <span>
                            {@props.data_source.name}
                        </span>
                    </div>
                    <Collapse
                        isOpen=@state.open
                        onOpened=@_onOpened
                        onClosed=@_onClosed>
                        <Card>
                            <CardBlock className='card-body'>
                                {rows}
                            </CardBlock>
                        </Card>
                    </Collapse>
                </div>


    class List extends React.Component

        constructor: (props) ->
            super(props)
            @state =
                id: "product-list-#{ids.next()}"
                loaded: false
            signals.connect(@props.data_source, 'refresh', @_update)

        _update: (source) =>
            @setState(loaded: true)

        render: ->
            if @state.loaded
                sections = []
                for section in @props.data_source.sections
                    sections.push(
                        <Section
                            key=section.name
                            data_source=section
                            cart=@props.cart
                            />
                    )
                content = sections
            else
                content = <p className='font-italic'>
                    {_('Loading...')}
                </p>

            return <div id=@state.id className='products'>
                {content}
            </div>


    return {
        List: List
        Option: Option
        Row: Row
        Section: Section
    }
)
