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

define(['react', 'gettext', 'utils'], ->
    [React, gettext, utils] = arguments

    _ = gettext.gettext

    class DatePicker extends React.Component

        @defaultProps:
            className: 'form-control'
            disabled: false
            id: null
            name: null
            onChange: ->
            pattern: utils.date.pattern
            placeholder: toString: -> _('YYYY-MM-DD')
            value: new Date().toISOString().substr(0, 10)

        render: ->
            props =
                className: @props.className
                disabled: @props.disabled
                value: @props.value
                onChange: @props.onChange

            if @props.id?
                props.id = @props.id

            if @props.name?
                props.name = @props.name

            if @props.placeholder?
                props.placeholder = @props.placeholder.toString()

            if @props.min?
                props.min = @props.min

            if @props.max?
                props.max = @props.max

            return <input type='date' {...props} />
)
