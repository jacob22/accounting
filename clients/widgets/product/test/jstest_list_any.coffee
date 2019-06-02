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

require(['react', 'react-dom', 'widgets/product/list'], ->
    [React, ReactDOM, ProductList] = arguments

    ReactTestUtils = React.addons.TestUtils

    findRenderedDOMComponentWithName = (tree, name) ->
        [dom] = ReactTestUtils.findAllInRenderedTree(tree, (elem) ->
            return elem.name == name
        )
        return dom

    render_comp = (cls, props) ->
        root = insertTestNode()
        component = React.createElement(cls, props)
        element = ReactDOM.render(component, root)
        return [root, component, element]

    render_option = (props={}) ->
        return render_comp(ProductList.Option, props)

    render_row = (props={}) ->
        return render_comp(ProductList.Row, props)

    Tests.callback(

        test_row: ->
            props =
                data_source:
                    name: 'foo'
                    price: 12345
                    description: 'a very foo foo'
                    options: []

            [root, component, element] = render_row(props)
            node = ReactDOM.findDOMNode(element)

            name = getFirstElementByTagAndClassName('span', 'name', node)
            ais(scrapeText(name), 'foo')

            price = getFirstElementByTagAndClassName('span', 'price', node)
            ais(scrapeText(price), '123:45')

            descr = getFirstElementByTagAndClassName(null, 'description', node)
            ais(scrapeText(descr), 'a very foo foo')

        test_row_is_valid_no_options: ->
            props =
                data_source:
                    name: 'foo'
                    price: 12345
                    description: 'a very foo foo'
                    options: []

            [root, component, element] = render_row(props)
            aok(element.is_valid())

        test_row_is_valid_out_of_stock: ->
            props =
                data_source:
                    name: 'foo'
                    price: 12345
                    description: 'a very foo foo'
                    options: []
                    currentStock: 0

            [root, component, element] = render_row(props)
            aok(not element.is_valid())

        test_option_select: ->
            props =
                data_source:
                    label: 'Choices'
                    mandatory: false
                    type: 'select'
                    typedata: JSON.stringify(
                        options: [
                            {name: "foo"}
                            {name: "bar"}
                            {name: "baz"}
                        ]
                    )

            [root, component, element] = render_option(props)
            node = ReactDOM.findDOMNode(element)

            select = getFirstElementByTagAndClassName('select', null, node)
            options = getElementsByTagAndClassName('option', null, select)
            ais(options.length, 3)
            ais(options[0].value, 'foo')
            ais(options[1].value, 'bar')
            ais(options[2].value, 'baz')
    )
)
