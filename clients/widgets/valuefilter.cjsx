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

define ['react'], (React) ->

    class ValueFilter extends React.Component

        constructor: (props) ->
            super(props)
            values = {}
            for [value, _, checked] in @props.values
                values[value] = checked
            @state = values: values

        onClick: (evt) =>
            values = @state.values
            key = evt.target.getAttribute('value')
            values[key] = not values[key]
            @setState(values: values)
            @signal()

        signal: ->
            @props.onChange(@state.values)

        render: () ->
            toggles = []
            for [value, text, _] in @props.values
                checked = @state.values[value]
                className = 'btn btn-primary-outline'
                if checked
                    className += ' active'
                toggles.push(<div
                    key={value}
                    aria-pressed={checked}
                    className={className}
                    value={value}
                    onClick={@onClick}>
                    {text}
                </div>)

            <div className='valuefilter text-xs-center'>
                <div className='btn-group'>
                    {toggles}
                </div>
            </div>
