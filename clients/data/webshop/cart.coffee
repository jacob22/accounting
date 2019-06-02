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

define(['iter', 'signals', 'utils'], ->
    [iter, signals, utils] = arguments

    class Cart

        constructor: (@localStorage=localStorage, @storageKey='eutaxia-cart') ->
            @contents = []
            @key_counter = iter.count(1)

        load: ->
            serialized = @localStorage.getItem(@storageKey)
            unless serialized
                return
            try
                data = JSON.parse(serialized)
            catch
                return  # Corrupt data, give up

            if data?
                @contents = data.contents
                @key_counter = iter.count(data.current)

        save: ->
            @localStorage.setItem(@storageKey, JSON.stringify(
                contents: @contents
                counter: @key_counter.current)
            )

        clear: ->
            @localStorage.removeItem(@storageKey)

        add: (item) ->
            unless item.count?
                item.count = 1

            unless item.options?
                item.options = []

            unless item.price?
                item.price = 0

            item.total = item.price * item.count

            push = true
            for prev in @contents
                if @_compare_items(prev, item)
                    prev.count += item.count
                    prev.total = prev.price * prev.count
                    key = prev.key
                    push = false
                    break

            if push
                item.key = key = @key_counter.next()
                @contents.push(item)

            signals.signal(@, 'changed')
            @save()
            return key

        set_item_count: (key, count) ->
            for item in @contents
                if item.key is key
                    if count == 0
                        @contents.splice(@contents.indexOf(item), 1)
                    else
                        item.count = count
                        item.total = item.price * count
                    signals.signal(@, 'changed')
                    @save()
                    return
            throw "No such item: #{key}"

        get_data: ->
            items = []
            for item in @contents
                options = []
                for [label, value] in item.options
                    if value?
                        value = value.toString()
                    else
                        value = ''
                    options.push(value)
                items.push(
                    product: item.id
                    quantity: item.count
                    options: options
                )
            return items

        _compare_items: (a, b) ->
            return a.id is b.id and utils.array_equal(a.options, b.options, true)


    module =
        Cart: Cart
)
