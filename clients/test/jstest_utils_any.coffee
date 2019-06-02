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

require(['utils'], (utils) ->

    Tests.callback(

        test_formatCurrency: ->
            res = utils.formatCurrency(1000)
            ais(res, '10,00')

            res = utils.formatCurrency(1000, '.')
            ais(res, '10.00')

            res = utils.formatCurrency(0)
            ais(res, '0,00')

            res = utils.formatCurrency(-12345)
            ais(res, '-123,45')

            res = utils.formatCurrency(1.1)
            ais(res, '0,01')

        test_parseCurrency: ->
            res = utils.parseCurrency('1234')
            ais(res, 123400)

            res = utils.parseCurrency('12.34')
            ais(res, 1234)

            res = utils.parseCurrency('12.')
            ais(res, 1200)

            res = utils.parseCurrency('1,212.')
            ais(res, 121200)

            res = utils.parseCurrency('1.212.00')
            ais(res, 121200)

            res = utils.parseCurrency('1.212.00 ')
            ais(res, 121200)

            res = utils.parseCurrency('.45')
            ais(res, 45)

            res = utils.parseCurrency('')
            ais(res, null)

            res = utils.parseCurrency("-12")
            ais(res, -1200)

            res = utils.parseCurrency("-12.34")
            ais(res, -1234)

            res = utils.parseCurrency("-1.234.56")
            ais(res, -123456)

            res = utils.parseCurrency("1,000")
            ais(res, 100000)

            res = utils.parseCurrency("-.45")
            ais(res, -45)

            res = utils.parseCurrency('12,34,56,78')
            ais(res, 12345678)

            res = utils.parseCurrency('1,23,45,678')  # Indians...
            ais(res, 1234567800)

            res = utils.parseCurrency('12 34 56:78')
            ais(res, 12345678)

        test_parseDecimal: ->
            res = utils.parseDecimal('0')
            ais(res, 0)

            res = utils.parseDecimal('1234')
            ais(res, 123400)

            res = utils.parseDecimal('1234.0')
            ais(res, 123400)

            res = utils.parseDecimal('1234.00')
            ais(res, 123400)

            res = utils.parseDecimal('1234.000')
            ais(res, 123400)

            res = utils.parseDecimal('1234.0000')
            ais(res, 123400)

            res = utils.parseDecimal('1234.1')
            ais(res, 123410)

            res = utils.parseDecimal('1234.10')
            ais(res, 123410)

            res = utils.parseDecimal('1234.100')
            ais(res, 123410)

            res = utils.parseDecimal('1234.1000')
            ais(res, 123410)

            res = utils.parseDecimal('12.34')
            ais(res, 1234)

            res = utils.parseDecimal('12.340000')
            ais(res, 1234)

            araises(utils.parseDecimal, '12.')
            araises(utils.parseDecimal, '12.345678')  # too many decimals
            araises(utils.parseDecimal, '12,000')
            araises(utils.parseDecimal, '12,000.00')
            araises(utils.parseDecimal, 'random gorp')

        test_clear: ->
            obj =
                foo: 1
                bar: 2
                baz: 3

            result = utils.clear(obj)
            aok(result == obj)  # result and obj is the same object

            # All keys should have been removed
            aok(not obj.foo?)
            aok(not obj.bar?)
            aok(not obj.baz?)

        test_sum: ->
            ais(utils.sum([]), 0)
            ais(utils.sum([1]), 1)
            ais(utils.sum([1, 2, 3]), 6)

        test_update: ->
            first = foo: 1
            second = bar: 2

            result = utils.update(first, second)
            aok(result == first)  # result and first is the same object
            ais(result.foo, 1)
            ais(result.bar, 2)

            # second should be unaffected
            ais(second.bar, 2)
            aok(not second.foo?)

        test_array_equal: ->
            aok(utils.array_equal([1], [1]))
            aok(utils.array_equal([1, 2, 3, 4, 5], [1, 2, 3, 4, 5]))
            aok(not utils.array_equal([1], [2]))
            aok(not utils.array_equal([1, 2, 3, 4, 5], [1, 2, 3, 4, 4]))
            aok(not utils.array_equal([1, 2, 3, 4, 5], [1, 2, 3, 4]))
            aok(not utils.array_equal([1, 2, 3, 4, 5], [1, 2, 3, 4, 5, 6]))
            aok(not utils.array_equal([1, 2, 3, 4, 5], [1, 2, 3, '4', 5]))

            # Nested arrays
            a = [[1, 2]]
            b = [[1, 2]]
            aok(utils.array_equal(a, b, true))

            a = [null]
            b = [null]
            aok(utils.array_equal(a, b, true))

            a = [[1, 2]]
            b = [[1]]
            aok(not utils.array_equal(a, b, true))

            a = [[1, 2]]
            b = [1]
            aok(not utils.array_equal(a, b, true))

        test_is_email: ->
            aok(not utils.is_email(null))
            aok(not utils.is_email(''))
            aok(not utils.is_email('foo@bar'))

            aok(utils.is_email('foo@bar.baz'))

        test_luhn_check: ->
            aok(utils.luhn_check('4539869986356160'))
            aok(utils.luhn_check('5440269983606292'))
            aok(utils.luhn_check('345779552730759'))
            aok(utils.luhn_check('6011826568969481'))
            aok(utils.luhn_check('3589289678861297'))
            aok(utils.luhn_check('5512860722117394'))
            aok(utils.luhn_check('30002946744307'))
            aok(utils.luhn_check('36084156383632'))
            aok(utils.luhn_check('6763994125062388'))
            aok(utils.luhn_check('6771326207691877'))
            aok(utils.luhn_check('4844738655516265'))
            aok(utils.luhn_check('6374721799752858'))

            aok(!utils.luhn_check('5539869986356160'))
            aok(!utils.luhn_check('5540269983606292'))
            aok(!utils.luhn_check('346779552730759'))
            aok(!utils.luhn_check('6012826568969481'))
            aok(!utils.luhn_check('3589389678861297'))
            aok(!utils.luhn_check('5512870722117394'))
            aok(!utils.luhn_check('30002956744307'))
            aok(!utils.luhn_check('36084157383632'))
            aok(!utils.luhn_check('6763994135062388'))
            aok(!utils.luhn_check('6771326208691877'))
            aok(!utils.luhn_check('4844738655616265'))
            aok(!utils.luhn_check('6374721799762858'))

        test_date_re: ->
            ok = [
                '2017-05-01'
                '2017-02-28'
                '2017-02-31'  # Oh well
            ]

            not_ok = [
                ''
                'not a date'
                '2017-13-01'  # Invalid month
            ]

            for v in ok
                aok(v.match(utils.date.regex)?)
                aok(v.match(utils.date.pattern)?)

            for v in not_ok
                aok(!v.match(utils.date.regex)?)
                aok(!v.match(utils.date.pattern)?)


        test_get_error_message: ->
            error1 =
                __class__: 'BlmError'
                args: ['foo']

            error2 =
                __class__: 'BlmError'
                args: ['Permission denied: <TO 5b30dc50a735c30327ade3a3>, on_create']

            error3 =
                __class__: 'PermissionError'

            ais(utils.get_error_message(error1), 'foo')
            ais(utils.get_error_message(error2), 'Permission denied')
            ais(utils.get_error_message(error3), 'Permission denied')
            ais(utils.get_error_message(null), null)
            ais(utils.get_error_message('whatever'), null)


        test_is_permission_error: ->
            permerror =
                __class__: 'PermissionError'

            wrappedpermerror =
                __class__: 'BlmError'
                args: ['Permission denied: <TO 5b30dc50a735c30327ade3a3>, on_create']

            othererror =
                __class__: 'BlmError'
                args: ['foo']

            aok(utils.is_permission_error(permerror))
            aok(utils.is_permission_error(wrappedpermerror))
            aok(!utils.is_permission_error(othererror))
    )
)
