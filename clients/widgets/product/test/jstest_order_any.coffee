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

require(['react', 'react-dom', 'signals',
         'widgets/product/order'], ->
    [React, ReactDOM, signals, Order] = arguments
    ReactTestUtils = React.addons.TestUtils

    findRenderedDOMComponentWithName = (tree, name) ->
        [dom] = ReactTestUtils.findAllInRenderedTree(tree, (elem) ->
            return elem.name == name
        )
        return dom

    render_form = (props={cart: {contents: []}}) ->
        root = insertTestNode()
        component = React.createElement(Order.Form, props)
        element = ReactDOM.render(component, root)
        return [root, component, element]

    Tests.callback(

        test_create: ->
            [root, component, element] = render_form()
            node = ReactDOM.findDOMNode(element)
            aok(node)

        test_valid: ->
            cart = {contents: []}
            [root, component, element] = render_form({cart: cart})

            button = ReactTestUtils.findRenderedDOMComponentWithTag(element, 'button')
            aok(button.disabled)

            name = findRenderedDOMComponentWithName(element, 'buyerName')
            name.value = 'Mr. Foo'
            ReactTestUtils.Simulate.change(name)
            aok(button.disabled)

            name = findRenderedDOMComponentWithName(element, 'buyerAddress')
            name.value = 'Norra Ågatan 10'
            ReactTestUtils.Simulate.change(name)
            aok(button.disabled)

            email = findRenderedDOMComponentWithName(element, 'buyerEmail')
            email.value = 'foo@bar.baz'
            ReactTestUtils.Simulate.change(email)
            aok(button.disabled)

            cart.contents = ['a cart full of data']
            signals.signal(cart, 'changed')
            aok(not button.disabled)

        test_order: ->
            order = null
            props =
                cart:
                    contents: []
                    get_data: -> items: true
                place_order: (o) ->
                    order = o
            [root, component, element] = render_form(props)

            element.state =
                name: 'mr foo'
                address: 'address'
                email: 'foo@example'
                phone: '12345'
                annotation: 'stuff'
                date: '2010-01-01'
                expiryDate: '2011-01-01'

            element._order()

            expect =
                items: {items: true}
                name: 'mr foo'
                address: 'address'
                email: 'foo@example'
                phone: '12345'
                annotation: 'stuff'
                date: '2010-01-01'
                expiryDate: '2011-01-01'

            aisDeeply(order, expect)

    )
)
