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

Tests = new Deferred()

require(['react', 'react-dom', 'widgets/date'], ->
    [React, ReactDOM, DatePicker] = arguments
    ReactTestUtils = React.addons.TestUtils

    render = (props={}) ->
        root = insertTestNode()
        component = React.createElement(DatePicker, props)
        element = ReactDOM.render(component, root)
        return [root, component, element]


    Tests.callback(

        test_create: ->
            [root, component, element] = render()

            input = ReactTestUtils.findRenderedDOMComponentWithTag(
                element, 'input')
            aok(!input.disabled)
            ais(input.placeholder, 'YYYY-MM-DD')

        test_with_props: ->
            props =
                className: 'foo'
                disabled: true
                id: 'bar'
                name: 'baz'
                placeholder: 'type something'
                value: '2017-01-01'

            [root, component, element] = render(props)

            input = ReactTestUtils.findRenderedDOMComponentWithTag(
                element, 'input')

            ais(input.className, 'foo')
            aok(input.disabled)
            ais(input.id, 'bar')
            ais(input.name, 'baz')
            ais(input.placeholder, 'type something')
            ais(input.value, '2017-01-01')

        test_callback: ->
            value = null
            props =
                onChange: (event) ->
                    value = event.target.value

            [root, component, element] = render(props)

            input = ReactTestUtils.findRenderedDOMComponentWithTag(
                element, 'input')
            input.value = '2001-01-01'
            ReactTestUtils.Simulate.change(input)
            ais(value, '2001-01-01')
    )
)
