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

require(['signals', 'data/webshop/cart'], (signals, Cart) ->

    class LocalStorage

        constructor: ->
            @data = {}

        getItem: (key) ->
            return @data[key]

        removeItem: (key) ->
            delete @data[key]

        setItem: (key, value) ->
            @data[key] = value


    create = ->
        return new Cart.Cart(new LocalStorage())


    Tests.callback(

        test_constructor: ->
            cart = new Cart.Cart()  # do not explode
            aisDeeply(cart.contents, [])
            ais(cart.localStorage, window.localStorage)

        test_add_unique: ->
            cart = create()
            key = cart.add(id: 'A', options: [])
            ais(key, 1)
            ais(cart.contents[0].key, key)
            ais(cart.contents[0].id, 'A')
            ais(cart.contents[0].count, 1)

            key = cart.add(id: 'B', count: 1, options: [])
            ais(key, 2)
            ais(cart.contents[1].key, key)
            ais(cart.contents[1].id, 'B')
            ais(cart.contents[1].count, 1)

        test_add_identical: ->
            cart = create()
            key = cart.add(id: 'A', options: [])
            ais(key, 1)
            ais(cart.contents[0].key, key)
            ais(cart.contents[0].id, 'A')
            ais(cart.contents[0].count, 1)

            key = cart.add(id: 'A', options: [])
            ais(key, 1)
            ais(cart.contents.length, 1)
            ais(cart.contents[0].count, 2)

        test_add_signals: ->
            cart = create()
            calls = []
            signals.connect(cart, 'changed', -> calls.push('x'))
            cart.add(id: 'A', options: [])
            aisDeeply(calls, ['x'])

            cart.add(id: 'A', options: [])
            aisDeeply(calls, ['x', 'x'])

        test_set_item_count: ->
            cart = create()
            key = cart.add(id: 'A')
            ais(cart.contents[0].count, 1)

            calls = []
            signals.connect(cart, 'changed', -> calls.push('x'))

            cart.set_item_count(key, 42)
            ais(cart.contents[0].count, 42)
            aisDeeply(calls, ['x'])

        test_set_item_count_to_zero: ->
            cart = create()
            key = cart.add(id: 'A')
            ais(cart.contents[0].count, 1)

            cart.set_item_count(key, 0)
            ais(cart.contents.length, 0)

        test_calculate_total: ->
            cart = create()
            key = cart.add(id: 'A', price: 100)
            ais(cart.contents[0].total, 100)

            cart.add(id: 'A', price: 100)
            ais(cart.contents[0].total, 200)

            cart.set_item_count(key, 3)
            ais(cart.contents[0].total, 300)

        test_save_load: ->
            localStorage = new LocalStorage()

            cart1 = new Cart.Cart(localStorage)
            key = cart1.add(id: 'A', price: 100)

            cart2 = new Cart.Cart(localStorage)
            cart2.load()
            ais(cart2.contents[0].total, 100)

            cart1.set_item_count(key, 2)

            cart2.load()
            ais(cart2.contents[0].total, 200)

        test_load_corrupt_data: ->
            localStorage = new LocalStorage()
            cart = new Cart.Cart(localStorage)
            localStorage.data[cart.storageKey] = 'this is not json'
            cart.load()
            aisDeeply(cart.contents, [])
            ais(cart.key_counter.current, 1)

        test_clear: ->
            cart = create()
            cart.add(id: 'A', price: 100)
            aok(cart.localStorage.data[cart.storageKey]?)

            cart.clear()
            aok(!cart.localStorage.data[cart.storageKey]?)

        test_get_data: ->
            cart = create()
            item1 =
                id: 'A'
                price: 100
                count: 2
                options: [['foo', 1], ['bar', '2']]

            item2 =
                id: 'B'
                price: 300
                count: 1
                options: [['foo', null], ['bar', 'gazonk']]

            cart.add(item1)
            cart.add(item2)

            data = cart.get_data()
            expect = [
                {
                    product: 'A'
                    quantity: 2
                    options: ['1', '2']
                },
                {
                    product: 'B'
                    quantity: 1
                    options: ['', 'gazonk']
                }
            ]
            aisDeeply(data, expect)
    )
)
