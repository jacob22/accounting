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

define ['signals'], (signals) ->

    Operator =

        Between: class Between
            constructor: (lower, upper) ->
                @_cls_ = 'Between'
                unless upper?
                    @value = lower
                else
                    @value = [lower, upper]

    for op in ['Like', 'Ilike']
        do (op) ->
            Operator[op] = class _Operator
                constructor: (@value, @_cls_=op) ->

    class BaseQuery

        constructor: (@jsLink, @tocName, cgs...) ->
            @condGroups = []
            @result = {}
            for cg in cgs
                @push(cg)

        push: (cDict) ->
            cg = _cls_: 'ConditionGroup'
            for attr, value of cDict
                if attr.name?
                    attr = attr.name

                if attr == '_cls_'
                    return

                unless value.length?
                    value = [value]

                cg[attr] = value

            @condGroups.push(cg)

        stop: ->
            # The original function in Eutaxia is much more
            # complicated. Might want to understand why.
            signals.disconnectAll(this)
            if @link?
                @link.deactivate()

        _start: (kind, params) ->
            if @_aborted
                return  # xxx

            params.criteria =
                _cls_: 'Query'
                toc: @tocName
                cgs: @condGroups

            @link = @jsLink.makeLink(kind, params: params, @_update)


    class Query extends BaseQuery

        start: ->
            @_start('Query', subscription: true)

        _update: (args) =>
            if args.error?
                return  # xxx

            add = args.add
            remove = args.del

            for toid, attrs of add
                this.result[toid] = attrs

            for toid of remove
                delete this.result[toid]

            signals.signal(this, 'update', add, remove)


    class SortedQuery extends BaseQuery

        constructor: (jsLink, tocName, cgs...) ->
            super(jsLink, tocName, cgs...)
            @result = []
            @toiData = {}
            @attrList = []
            @gotResult = 0

        _update: (args) =>
            if args.error?
                return  # xxx

            opcodes = args.diffops
            add = {}
            remove = {}
            moved = {}
            toiDiffs = args.toiDiffs

            for opcode in opcodes
                for i in [opcode[0] ... opcode[1]]
                    remove[@result[i]] = null
                for i in [0 ... opcode[2].length]
                    add[opcode[2][i]] = null

            for toid of remove
                if toid of add
                    moved[toid] = null
                    delete add[toid]
                    delete remove[toid]
                else
                    delete @toiData[toid]

            for toid of toiDiffs
                unless toid of @toiData
                    @toiData[toid] =
                        _id: [toid]
                        _tocName: toiDiffs[toid].toc

                for key, value of toiDiffs[toid].attrs
                    @toiData[toid][key] = value

            result = @result
            newresult = _apply_opcodes(result, opcodes)
            @result = newresult

            @gotResult++

            signals.signal(this, 'update', add, remove, moved, opcodes, toiDiffs)

        start: ->
            params =
                subscription: true
                sorting: @sorting
                attrList: @attrList
            @_start('SortedQuery', params)


    _apply_opcodes = (oldList, opcodes) ->
        len = oldList.length
        for opcode in opcodes
            len += opcode[2].length - opcode[1] + opcode[0]

        result = new Array(len)
        lasti = 0
        offset = 0

        for opcode in opcodes
            for i in [lasti ... opcode[0]]
                result[i + offset] = oldList[i]

            for i in [0 ... opcode[2].length]
                result[i + opcode[0] + offset] = opcode[2][i]

            lasti = opcode[1]
            offset += opcode[2].length - opcode[1] + opcode[0]

        for i in [lasti ... oldList.length]
            result[i + offset] = oldList[i]

        return result


    query =
        Operator: Operator
        Query: Query
        SortedQuery: SortedQuery
