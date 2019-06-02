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

require(['signals', 'data/webshop/products'], (signals, ProductData) ->

    class JsLink

        makeLink: ->

    make_option = (label, description, type, mandatory, typedata) ->
        field = [label, description, type, mandatory, typedata].join('\x1f')
        return new ProductData.Option(field)

    Tests.callback(

        test_constructor: ->
            products = new ProductData.Products()
            aok(products.sections)
            ais(products.sections.length, 0)

        test_query: ->
            products = new ProductData.Products(new JsLink(), 'myorgid')
            products.start()
            ais(products.query.tocName, 'members.Product')

        test_sections: ->
            products = new ProductData.Products(new JsLink(), 'myorgid')
            products.start()
            products.query.toiData = {
                1: {
                    tags: []
                },
                2: {
                    tags: ['foo']
                },
                3: {
                    tags: ['foo', 'bar']
                }

            }
            signals.signal(products.query, 'update')
            console.log(products.sections)
            ais(products.sections.length, 3)

        test_option: ->
            label = 'name'
            description = 'fill in your name'
            type = 'text'
            mandatory = '1'
            typedata = ''

            option = make_option(label, description, type, mandatory, typedata)
            ais(option.label, label)
            ais(option.description, description)
            ais(option.type, 'text')
            ais(option.mandatory, true)
            ais(option.typedata, typedata)

            mandatory = '0'
            typedata = 'foobar'
            option = make_option(label, description, type, mandatory, typedata)
            ais(option.label, 'name')
            ais(option.description, 'fill in your name')
            ais(option.type, 'text')
            ais(option.mandatory, false)
            ais(option.typedata, 'foobar')

        test_option_is_valid_mandatory: ->
            label = 'name'
            description = 'fill in your name'
            type = 'text'
            mandatory = '0'
            typedata = ''

            option = make_option(label, description, type, mandatory, typedata)
            aok(option.is_valid(''))
            aok(option.is_valid('some data'))

            mandatory = '1'
            option = make_option(label, description, type, mandatory, typedata)
            aok(!option.is_valid(''))
            aok(option.is_valid('some data'))

        test_option_personnummer: ->
            label = 'personnummer'
            description = 'big brother demands it'
            type = 'personnummer'
            mandatory = '1'
            typedata = ''

            option = make_option(label, description, type, mandatory, typedata)
            aok(!option.is_valid(''))
            aok(!option.is_valid('some data'))
            aok(!option.is_valid('123456-7890'))

            aok(option.is_valid('460430-0014'))

        test_product: ->
            id = '1234'  # toid
            data =
                name: ['foo']
                price: ['100.0000']
                description: ['an exceptional foo']
                optionFields: []
                currentStock: [3]

            product = new ProductData.Product(id, data)
            ais(product.name, 'foo')
            ais(product.price, 10000)
            ais(product.description, 'an exceptional foo')
            ais(product.currentStock, 3)
            aisDeeply(product.options, [])

    )
)
