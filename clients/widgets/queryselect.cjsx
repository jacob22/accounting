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

require('react-select/dist/react-select.css')

define(['react', 'react-select'], ->

    [React, Select] = arguments

    class QuerySelect extends React.Component

        @defaultProps:
            allow_empty: false
            disabled: false
            query: null
            selected: null
            className: null
            handleBlur: ->
            handleChange: ->
            placeholder: null

        compare: null

        get_value_for_toi: (toi) ->
            return toi._id[0]

        get_label_for_toi: (toi) ->
            return null

        get_option: (toi) ->
            return {
                value: if toi? then @get_value_for_toi(toi) else null
                label: if toi? then @get_label_for_toi(toi) else @props.placeholder
            }

        onChange: (option) =>
            @props.handleChange(option.value)

        render: () ->
            tois = (
                @props.query.toiData[toid] for toid in @props.query.result
            )
            if @compare?
                tois.sort(@compare)

            options = (@get_option(toi) for toi in tois)
            if @props.allow_empty
                empty = @get_option(null)
                options = [empty].concat(options)
            else
                empty = null

            if @props.selected?
                value = @props.selected
            else
                value = ''

            <Select
                options=options
                value=value
                onBlur=@props.handleBlur
                onChange=@onChange
                clearable=@props.allow_empty
                resetValue=empty
                autosize=false
                className=@props.className
                placeholder=@props.placeholder
                disabled=@props.disabled
            />
)
