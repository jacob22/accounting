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

# This module expectes shopping-cart.css to be loaded

define(['react', 'gettext', 'iter', 'signals', 'utils'], ->
    [React, gettext, iter, signals, utils] = arguments

    _ = gettext.gettext


    class Item extends React.Component

        _change_count: (event) =>
            @props.change_count(@props.item.key, parseInt(event.target.value))

        _remove: =>
            @props.change_count(@props.item.key, 0)

        render: ->
            formatAmount = (v) =>
                utils.addCurrencyUnit(
                    utils.formatCurrency(v, ':'),
                    @props.currency
                )
            [price, total] = [@props.item.price, @props.item.total].map(formatAmount)

            options = []
            keys = iter.count()
            for option in @props.item.options
                [label, value] = option
                if value?
                    options.push(
                        <div
                            key=keys.next()
                            className='row option'>
                            <div className='col-3 name'>{label}:</div>
                            <div className='col-4 value'>{value}</div>
                        </div>
                    )

            <div className='cart-item'>
                <div className='row'>
                    <div className='col-5 name'>{@props.item.name}</div>
                    <div className='col-2 price'>{price}</div>
                    <div className='col-2 quantity'>
                        <input
                            className='form-control form-control-sm'
                            type='number'
                            min=0
                            value=@props.item.count
                            onChange=@_change_count />
                    </div>
                    <div className='col-2 total'>{total}</div>
                    <div className='col-1'>
                        <button
                            title={_('Remove')}
                            alt={_('Remove')}
                            className='remove close'
                            onClick=@_remove>x</button>
                    </div>
                </div>
                <div className='options'>
                    {options}
                </div>
            </div>


    class List extends React.Component

        constructor: (props) ->
            super(props)
            signals.connect(props.cart, 'changed', @_cart_changed)
            @state = counter: 0

        change_count: (itemid, count) =>
            @props.cart.set_item_count(itemid, count)

        _cart_changed: =>
            @setState(counter: @state.counter + 1)  # xxx

        render: ->
            items = []
            keys = iter.count()
            total = 0
            for item in @props.cart.contents
                items.push(<Item
                    key=keys.next()
                    item=item
                    change_count=@change_count
                    currency=@props.currency
                    />)
                total += item.total

            if items.length == 0
                return <div className='cart text-center font-italic pb-5'>
                    {_('The shopping cart is empty.')}
                </div>

            else

                total = utils.addCurrencyUnit(
                    utils.formatCurrency(total, ':'),
                    @props.currency)

                return <div className='cart'>
                    <div className='row cart-header'>
                        <div className='col-5 name'>{_('Item')}</div>
                        <div className='col-2 price'>{_('Price')}</div>
                        <div className='col-2 quantity'>{_('Quantity')}</div>
                        <div className='col-2 total'>{_('Total')}</div>
                        <div className='col-1'></div>
                    </div>
                    {items}
                    <div className='total row footer justify-content-end'>
                        <div className='col-11'>
                            {_('Amount to pay')}
                            <span className='amount'>
                                {total}
                            </span>
                        </div>
                        <div className='col-1' />
                    </div>

                </div>

    module =
        Item: Item
        List: List
)
