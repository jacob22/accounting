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

define(['react', 'react-dom', 'iter', 'country-calling-code'], ->
    [React, ReactDOM, iter, CountryCallingCode] = arguments

    countries = CountryCallingCode.default

    class Phone extends React.Component

        @defaultProps:
            countryCode: '46'
            localNumber: ''
            placeholder: null

        _changed: (countryCode, localNumber) =>
            unless countryCode?
                countryCode = @props.countryCode
            unless localNumber?
                localNumber = @props.localNumber

            normalized = countryCode
            normalized += localNumber.replace(/^0/, '')
            normalized = normalized.replace(/[^\d]/g, '')

            phone =
                countryCode: countryCode
                localNumber: localNumber
                phoneNumber: "+#{countryCode}#{localNumber}"
                normalized: normalized

            @props.onUpdate(phone)

        countryCodeChanged: (evt) =>
            @_changed(evt.target.value, null)

        localNumberChanged: (evt) =>
            @_changed(null, evt.target.value)

        render: ->
            options = []
            keys = iter.count()
            for country in countries
                for code in country.countryCodes
                    options.push(<option
                        key={keys.next()}
                        value=code>
                        {"#{country.isoCode2}: +#{code}"}
                    </option>)

            return <div className='phone'>
                <select
                    className='form-control'
                    value=@props.countryCode
                    onChange=@countryCodeChanged
                    >
                    {options}
                </select>
                <input
                    className='form-control'
                    onChange=@localNumberChanged
                    value=@props.localCode
                    placeholder=@props.placeholder
                    />
            </div>
)
