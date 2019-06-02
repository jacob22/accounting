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

define(['react', 'utils'], (React, utils) ->

    class Amount extends React.Component

        @defaultProps:
            onUpdate: ->
            value: null
            regex: /[^-0-9,.: ]/g
            placeholder: ''
            className: 'form-control text-right'

        constructor: (props) ->
            super(props)
            @state = @_createStateFromProps(props)

        componentWillReceiveProps: (props) ->
            @setState(@_createStateFromProps(props))

        _createStateFromProps: (props) ->
            if props.value?
                return value: utils.formatCurrency(props.value)
            else
                return value: ''

        componentDidUpdate: (prevProps, prevState) ->
            if @props.suggestValue?
                # Make sure the prefilled diff value is
                # selected so it can be easily overwritten.
                if prevState.value != @state.value == utils.formatCurrency(@props.suggestValue) and @state.me?
                    @state.me.select()

        onFocus: (event) =>
            if @props.suggestValue? and not @state.value
                value = utils.formatCurrency(@props.suggestValue)
                @setState(value: value)
            # Select value on focus.
            event.target.select()
            # This will sadly not select the prefilled balancing diff,
            # so that we need to do in componentDidUpdate
            # after setState triggered re-render.
            # For selecting after the fact we need a reference to
            # the <input>, so lets save that in state.
            @setState(me: event.target)

        onKeyDown: (event) =>
            if event.keyCode in [13, 9]
                event.target.blur()

        onBlur: (event) =>
            value = utils.parseCurrency(event.target.value)
            @props.onUpdate(value)

        onChange: (event) =>
            filtered = event.target.value.replace(@props.regex, '')
            @setState(value: filtered)

        render: ->
            content = <input
                type='text'
                className=@props.className
                placeholder=@props.placeholder
                onChange=@onChange
                onBlur=@onBlur
                onFocus=@onFocus
                onKeyDown=@onKeyDown
                readOnly=@props.readOnly
                value=@state.value />
)
