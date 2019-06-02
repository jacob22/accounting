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

define(['signals', 'utils', 'jslink/query', 'jslink/ToiSetWatcher'], ->
    [signals, utils, query, ToiSetWatcher] = arguments

    class Option

        constructor: (data) ->
            [
                @label,
                @description,
                @type,
                mandatory,
                @typedata
            ] = data.split('\x1f')
            @mandatory = if mandatory == '1' then true else false

        is_valid: (value) ->
            if @mandatory and not value
                return false

            if @type == 'personnummer'
                return value.match(/^\d{6}[-+]?\d{4}/) and utils.luhn_check(value)

            return true


    class Product

        constructor: (@id, @data) ->
            @name = @data.name[0] if @data.name?
            @price = utils.parseDecimal(@data.price[0]) if @data.price?
            @description = @data.description[0] if @data.description?
            @options = (new Option(field) for field in (@data.optionFields or []))
            if @data.currentStock? and @data.currentStock.length
                @currentStock = @data.currentStock[0]
            else
                @currentStock = null

        get_sections: ->
            return if @data.tags.length then @data.tags else ['']


    class Section

        constructor: (@name) ->
            @products = []

        add: (product) ->
            @products.push(product)


    class Products

        constructor: (@jsLink, @orgid) ->
            @sections = []
            @org_name = ''

        start: ->
            criteria =
                org: @orgid
                archived: false
            @query = new query.SortedQuery(@jsLink, 'members.Product', criteria)
            @query.attrList = [
                'accountingRules', 'availableFrom', 'availableTo',
                'currentStock', 'description', 'hasImage', 'name',
                'price', 'optionFields', 'tags'
            ]
            signals.connect(@query, 'update', @_products_updated)
            @query.start()

            @watcher = new ToiSetWatcher(@jsLink, 'accounting.Org',
                ['name', 'currency'])
            signals.connect(@watcher, 'refresh', @_org_loaded)
            @watcher.watch('org', [@orgid])

        stop: ->
            @query.stop()

        _org_loaded: =>
            data = @watcher.getToiData(@orgid)
            @org_name = data.name[0]
            @currency = data.currency[0]
            signals.signal(@, 'refresh')

        _products_updated: =>
            sections = {}
            for toid, data of @query.toiData
                product = new Product(toid, data)
                for name in product.get_sections()
                    if not sections[name]?
                        sections[name] = new Section(name)
                    sections[name].add(product)

            @sections = []
            for name, section of sections
                @sections.push(section)

            signals.signal(@, 'refresh')


    return {
        Option: Option
        Product: Product
        Section: Section
        Products: Products
    }
)
