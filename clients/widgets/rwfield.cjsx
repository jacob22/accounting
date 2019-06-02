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

React = require('react')

class RWField extends React.Component

    @defaultProps:
        name: ""
        type: 'text'
        label: null
        value: ''
        placeholder: null

    constructor: (props) ->
        super(props)
        @state = value: @props.value

    handleChange: (event) ->
        @setState
            value: event.target.value

    render: ->
        label = <label htmlFor=@props.name>{@props.label}</label> if @props.label?
        <fieldset className='form-group'>
            {label}
            <input name=@props.name
                   className='form-control'
                   type=@props.type
                   value=@state.value
                   placeholder=@props.placeholder
                   onChange=@handleChange />
        </fieldset>

define([], -> RWField)
