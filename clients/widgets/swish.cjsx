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

define(['react', 'react-dom', 'gettext', 'iter', 'widgets/phone'], ->
    [React, ReactDOM, gettext, iter, Phone] = arguments

    _ = gettext.gettext

    class SwishPopup extends React.Component

        constructor: (props) ->
            super(props)
            @state =
                phone: @props.phone
                errors: @props.errors
                code: ''

        componentWillReceiveProps: (props) ->
            @setState(errors: props.errors)

        componentDidMount: ->
            $(ReactDOM.findDOMNode(@)).on('hidden.bs.modal', @clear)

        clear: =>
            @setState(errors: null)

        submit: (evt) =>
            phone = @state.phone.normalized
            if @state.code
                @props.submit(phone, @state.code)
            else
                @props.submit(phone)
            evt.preventDefault()

        updatePhone: (phone) =>
            @setState(phone: phone)

        codeSelected: (evt) =>
            @setState(code: evt.target.value)

        render: ->
            if @state.errors?
                extra = <SwishErrors errors=@props.errors />

            else if @props.submitting
                extra = <p>
                    {_('Complete the payment in your Swish app.')}
                </p>

            else if @props.aborted
                extra = <p>
                    {_('You have aborted the payment.')}
                </p>
            else
                extra = <span />

            if @props.is_test
                keys = iter.count(1)
                codes =
                    '': ''
                    'FF08': 'PaymentReference is invalid'
                    'RP03': 'Callback URL is missing or does not use Https'
                    'BE18': 'Payer alias is invalid'
                    'RP01': 'Missing Merchant Swish Number'
                    'PA02': 'Amount value is missing or not a valid number'
                    'AM06': 'Specified transaction amount is less than agreed minimum'
                    'AM02': 'Amount value is too large'
                    'AM03': 'Invalid or missing Currency'
                    'RP02': 'Wrong formated message'
                    'RP06': 'A payment request already exist for that payer. Only applicable for Swish ecommerce.'
                    'ACMT03': 'Payer not Enrolled'
                    'ACMT01': 'Counterpart is not activated'
                    'ACMT07': 'Payee not Enrolled'
                    'RF07': 'Transaction declined'
                    'BANKIDCL': 'Payer cancelled BankId signing'
                    'FF10': 'Bank system processing error'
                    'TM01': 'Swish timed out before the payment was started'
                    'DS24': 'Swish timed out waiting for an answer from the banks after payment was
                             started. Note: If this happens Swish has no knowledge of whether the payment
                             was successful or not. The Merchant should inform its consumer about this and
                             recommend them to check with their bank about the status of this payment.'
                options = []
                for code, descr of codes
                    options.push(<option key=code value=code>{code}</option>)
                testctrl = <select value=@state.code onChange=@codeSelected>{options}</select>
            else
                testctrl = null

            return <div id="swish-box" className="modal fade" role="dialog">
                <div className="modal-dialog">
                    <div className="modal-content">
                        <div className="modal-header">
                            <button type="button" className="close" data-dismiss="modal">&times;</button>
                            <h4 className="modal-title"><img src="/static/swish.png" /></h4>
                        </div>
                        <div className="modal-body">
                            <p>
                                {_("When you pay with Swish, you should open your
                                    Swish app and verify that the information there
                                    is correct. You must authorize the purchas
                                    with your Mobile BankID and you will immediately
                                    get a payment confirmation.")}
                            </p>
                            <form
                                id="swish-form"
                                className="form-inline"
                                onSubmit=@submit
                                >
                                <div>
                                    <label>
                                        {_("Enter your phone number:")}
                                    </label>
                                </div>
                                <Phone
                                    id="swish-phone"
                                    name="phone"
                                    type="text"
                                    onUpdate=@updatePhone
                                    placeholder={_('phone number')}
                                    {...@state.phone}
                                    />
                                <button
                                    type="submit"
                                    className={"btn btn-primary has-spinner" +
                                        if @props.submitting then " active" else ""}
                                    disabled=@props.submitting
                                    >
                                    <span className="spinner">
                                        <i className="fa fa-spinner fa-spin"
                                        aria-hidden="true">
                                        </i>
                                    </span>
                                    {_('Pay')}
                                </button>
                                {testctrl}
                            </form>
                            {extra}
                        </div>
                        <div className="modal-footer">
                            <button
                                type="button"
                                className="btn btn-default"
                                data-dismiss="modal">
                                {_('Close')}
                            </button>
                        </div>
                    </div>
                </div>
            </div>


    class SwishError extends React.Component

        render: ->
            descr = switch @props.error.errorCode
                when 'ACMT03'
                    _('Phone number is not connected to Swish.')
                when 'BE18'
                    _('Incorrect phone number.')
                when 'RP01'
                    _('You have not entered a phone number.')
                when 'RP06'
                    _('You already have a payment you need to handle. Please check your phone.')
                when 'BANKIDCL'
                    _('You have cancelled the BankID signing.')
                when 'DS24'
                    _("Timeout during communication with bank.
                       Please note that we can not tell if the
                       payment was successful or not. You should
                       check your bank statement.")
                else
                    @props.error.errorMessage
            return <li className='error-description'>
                {descr}
            </li>


    class SwishErrors extends React.Component

        render: ->
            errors = []
            keys = iter.count(1)
            server_error = false
            if typeof @props.errors is 'string'  # This shouldn't happen
                error =
                    errorCode: 'UNKNOWN'
                    errorMessage: _('An unknown error has occured. Please try again later.')
                errors.push(<SwishError key=keys.next() error=error />)
            else
                for error in @props.errors
                    errors.push(<SwishError key=keys.next() error=error />)
            return <div className='swish-errors bg-danger'>
                {_('An error occured while processing your payment.')}
                <ul>
                    {errors}
                </ul>
            </div>


    class SwishButton extends React.Component

        render: ->
            return <div
                data-toggle="modal"
                data-target="#swish-box"
                style={'cursor': 'pointer'} >
                <button type="button" className="btn btn-primary">
                    {_('Pay with Swish')}
                </button>
                <img src="/static/swish.png" />
            </div>


    class Swish extends React.Component

        render: ->
            return <div>
                <SwishPopup {...@props} />
                <SwishButton />
            </div>

    return module =
        Swish: Swish
        SwishButton: SwishButton
        SwishPopup: SwishPopup

)
