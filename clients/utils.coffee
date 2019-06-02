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

define([], ->

    date =

        regex: /^\d{4}-(?:0[1-9]|10|11|12)-(?:0|1|2|3)\d$/

    date.pattern = date.regex.toString().substr(1, date.regex.toString().length - 2)

    utils =

        date: date

        addCurrencyUnit: (value, currency) ->
            switch currency
                when 'SEK'
                    "#{value}\xa0kr"
                when 'USD'
                    "$#{value}"
                else
                    value


        formatCurrency: (value, decimalSeparator=',', thousandSeparator=' ') ->
            decimalPlaces = 2
            v = parseInt(value)
            if isNaN(v)
                throw 'Not a number: ' + value
            value = v.toString()

            if value[0] == '-'
                negative = '-'
                value = value.slice(1)
            else
                negative = ''

            while value.length < (decimalPlaces + 1)
                value = "0" + value

            res = decimalSeparator + value.slice(-decimalPlaces)
            value = value.slice(0, -decimalPlaces)

            if not thousandSeparator
                res = value + res
            else
                while value
                    res = value.slice(-3) + res
                    value = value.slice(0,-3)
                    if value
                        res = thousandSeparator + res

            return negative + res


        parseCurrency: (value) ->
            decimals = ".,:"
            thousands = ".,' "

            decimalPlaces = 2
            res = 0
            multiplier = 0
            sign = 1

            if typeof(value) != "string"
                return value

            value = value.trim()

            # Split string into numerics and non-numerics
            groups = value.match(/-|[0-9]+|[^-0-9]+/g)

            if not groups
                return null

            if groups[0] == '-'
                groups.shift()
                sign = -1

            if groups.length == 0
                return null

            groups.reverse()

            if groups.length == 1
                return sign * parseInt(groups[0]) * Math.pow(10, decimalPlaces)

            if isNaN(groups[0])
                endsep = groups.shift()
                if decimals.indexOf(endsep[0]) != -1
                    multiplier = decimalPlaces

            if groups.length == 0
                return null

            while groups.length
                num = groups.shift()
                sep = groups.shift()
                if sep and sep.length != 1
                    # Separator is not single character
                    return null

                if not multiplier and (decimals.indexOf(sep) != -1)
                    if num.length > decimalPlaces
                        multiplier = decimalPlaces
                    else
                        # Decimal part
                        multiplier = decimalPlaces - num.length
                        res = parseInt(num) * Math.pow(10, multiplier)
                        multiplier = decimalPlaces
                        continue

                res += parseInt(num) * Math.pow(10, multiplier)
                multiplier += num.length

            return sign * res


        parseDecimal: (value) ->
            # Parses a decimal value represented as a string with an
            # optional decimal fraction separated by a decimal point.
            #
            # Only two significant decimal digits is allowed.
            #
            # Valid examples:
            # 1  1.0  1.00  1.000  1.01
            #
            # Invalid examples:
            # 1.  1.001  1,0  10,000.00
            unless value.match(/^[0-9]+(\.[0-9]{1,2}[0]*)?$/)?
                throw "Invalid decimal: #{value}"

            [integer, fraction] = value.split('.')

            if fraction?
                fraction = fraction.substr(0, 2)
                if fraction.length == 1
                    fraction += '0'
            else
                fraction = '0'

            return parseInt(integer) * 100 + parseInt(fraction)


        formatBgnum: (bgnum) ->
            if bgnum.length <= 6
                re = /^(\d{4})(\d{1,4})$/
            else if bgnum.length == 7
                re = /(\d{3})(\d{4})/
            else
                # bgnum.length >= 8
                re = /(\d{4})(\d{4})/
            return bgnum.replace(re, '$1-$2')


        parseBgnum: (bgnum) ->
            return @filterDigits(bgnum).slice(0,8)


        formatPgnum: (pgnum) ->
            re_71dig = /^(\d{1,7})(\d).*$/
            return pgnum.replace(re_71dig, '$1-$2')


        parsePgnum: (pgnum) ->
            return @filterDigits(pgnum).slice(0,8)


        formatClearing: (clrno) ->
            re_41dig = /(\d{4})(\d)/
            return clrno.replace(re_41dig, '$1-$2')


        parseClearing: (clrno) ->
            return @filterDigits(clrno).slice(0,5)


        parseBankaccount: (acc) ->
            return @filterDigits(acc).slice(0,15)


        filterDigits: (str) ->
            return str.replace(/[^\d]/, '')


        imageUrl: (toid, attribute='image', index=0, width=null, height=null,
                   nocache=false) ->
            url = "/image/#{ toid }/#{ attribute }/#{ index }"
            if width? and height?
                url = "#{ url }/#{ width }/#{ height }"
            if nocache
                # if nocahe is true, create a token, otherwise just use
                # nocache itself
                if nocache == true
                    nocache = new Date().getTime()
                url = "#{ url }?nocache=#{ nocache }"
            return url


        clear: (obj) ->
            for key of obj
                delete obj[key]
            return obj


        update: (self, obj) ->
            for key, value of obj
                self[key] = value
            return self


        copyobj: (obj) ->
            return @update({}, obj)


        sum: (seq, func) ->
            unless func?
                func = (a, b) -> a + b
            seq.reduce(func, 0)


        array_equal: (a, b) ->
            if a? and b? and typeof a is typeof b is 'object'
                return a.length == b.length and a.every((elem, i) ->
                    utils.array_equal(elem, b[i])
                )
            return a is b


        is_email: (s) ->
            unless s?
                return false
            return !!(s.match(/^[\0-\x7f]+$/) and s.match(/^[^@]+@[^@]+\.[^@]+$/))


        luhn_check: (s) ->
            # taken from https://gist.github.com/ShirtlessKirk/2134376
            s = s.replace(/[^\d]/, '')
            prodarr = [
                [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
                [0, 2, 4, 6, 8, 1, 3, 5, 7, 9]
            ]

            length = s.length
            sum = 0
            mul = 0

            while length--
                sum += prodarr[mul][parseInt(s.charAt(length), 10)]
                mul ^= 1

            return sum % 10 is 0 and sum > 0


        get_error_message: (error) ->
            # Extract the error message from a cBlmError that has been
            # raised in a BLM.
            unless error?
                return null

            if error.__class__ == 'PermissionError'
                return 'Permission denied'

            if error.__class__ == 'BlmError' and error.args?
                message = error.args[0]
                if message[..17] == 'Permission denied:'
                    return 'Permission denied'
                return message

        is_permission_error: (error) ->
            return utils.get_error_message(error) == 'Permission denied'


    return utils
)
