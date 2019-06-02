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

# This module expectes order.css to be loaded

define(['react', 'gettext', 'signals', 'utils', 'widgets/date'], ->
    [React, gettext, signals, utils, DatePicker] = arguments

    _ = gettext.gettext

    class Form extends React.Component

        constructor: (props) ->
            super(props)
            now = new Date()
            expire = new Date()
            expire.setDate(expire.getDate() + 30)

            @state =
                name: null
                address: null
                email: null
                phone: null
                annotation: null
                date: now.toISOString().substr(0, 10)
                expiryDate: expire.toISOString().substr(0, 10)
                cart_has_data: props.cart.contents.length > 0

            signals.connect(props.cart, 'changed', @_cart_changed)

        _cart_changed: (cart) =>
            @setState(cart_has_data: @props.cart.contents.length > 0)

        _name_set: (event) =>
            @setState(name: event.target.value)

        _address_set: (event) =>
            @setState(address: event.target.value)

        _email_set: (event) =>
            @setState(email: event.target.value)

        _phone_set: (event) =>
            @setState(phone: event.target.value)

        _note_set: (event) =>
            @setState(note: event.target.value)

        _date_set: (event) =>
            @setState(date: event.target.value)

        _expiryDate_set: (event) =>
            @setState(expiryDate: event.target.value)

        _order: =>
            order =
                items: @props.cart.get_data()
                name: @state.name

            if @state.address?
                order.address = @state.address

            if @state.email?
                order.email = @state.email

            if @state.phone?
                order.phone = @state.phone

            if @state.annotation?
                order.annotation = @state.annotation

            if @state.date?
                order.date = @state.date

            if @state.expiryDate?
                order.expiryDate = @state.expiryDate

            @props.place_order(order)

        render: ->
            complete = (
                @state.cart_has_data and
                !!@state.name and
                (!!@state.address or utils.is_email(@state.email))
            )

            <div className='order-form'>
                <div className='form-group'>
                    <label htmlFor='buyerName' className='mandatory'>
                        {_('Name')}
                    </label>
                    <input required name='buyerName' type='text'
                        className='form-control'
                        onChange=@_name_set
                        />
                </div>
                <div className='form-group'>
                    <label htmlFor='buyerAddress' className='mandatory-or'>
                        {_('Address')}
                    </label>
                    <textarea required rows=5 name='buyerAddress'
                        className='form-control'
                        onChange=@_address_set
                        ></textarea>
                </div>
                <div className='form-group'>
                    <label htmlFor='buyerEmail' className='mandatory-or'>
                        {_('E-mail')}
                    </label>
                    <input required name='buyerEmail' type='text'
                        className='form-control'
                        onChange=@_email_set />
                </div>
                <div className='form-group'>
                    <label htmlFor='buyerPhone'>
                        {_('Phone')}
                    </label>
                    <input required name='buyerPhone' type='text'
                        className='form-control'
                        onChange=@_phone_set />
                </div>
                <div className='form-group'>
                    <label htmlFor='buyerAnnotation'>
                        {_('Note')}
                    </label>
                    <textarea required rows=5 name='buyerAnnotation'
                        className='form-control'
                        onChange=@_note_set
                        ></textarea>
                </div>

                <div className='form-inline'>
                    <label htmlFor='date' className='mr-sm-2'>
                        {_('Invoice date')}
                    </label>
                    <DatePicker
                        className='form-control mb-2 mr-sm-2 mb-sm-0'
                        name='date'
                        onChange=@_date_set
                        value=@state.date />

                    <label htmlFor='expiryDate' className='mr-sm-2'>
                        {_('Expiry date')}
                    </label>
                    <DatePicker
                        className='form-control mb-2 mr-sm-2 mb-sm-0'
                        name='expiryDate'
                        onChange=@_expiryDate_set
                        value=@state.expiryDate />
                </div>

                <div className='mandatory-explanation'>
                    <span className='mandatory'>
                        {_('The name field is mandatory.')}
                    </span>
                    <br />
                    <span className='mandatory-or'>
                        {_('You must fill in at least one of the
                            Address and E-mail fields.')}
                    </span>
                </div>

                <button
                    className='btn order-button'
                    onClick=@_order
                    disabled={not complete}>{_('Order')}</button>
            </div>

    module =
        Form: Form
)
