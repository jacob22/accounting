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

require(['react', 'react-dom', 'widgets/product/cart'], ->

    [React, ReactDOM, Cart] = arguments
    ReactTestUtils = React.addons.TestUtils

    Tests.callback(

        test_item: ->
            root = insertTestNode()
            props =
                item:
                    name: 'foo'
                    price: 10000
                    count: 2
                    total: 20000
                    options: []

            comp = React.createElement(Cart.Item, props)
            element = ReactDOM.render(comp, root)
            node = ReactDOM.findDOMNode(element)

            name = getFirstElementByTagAndClassName('div', 'name', node)
            ais(scrapeText(name), 'foo')

            price = getFirstElementByTagAndClassName('div', 'price', node)
            ais(scrapeText(price), '100:00')

            quantity = getFirstElementByTagAndClassName('input', null, node)
            ais(quantity.value, '2')

            total = getFirstElementByTagAndClassName('div', 'total', node)
            ais(scrapeText(total), '200:00')

            options = getFirstElementByTagAndClassName('div', 'options', node)
            aok(options?)

    )
)
