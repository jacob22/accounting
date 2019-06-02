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

define ['react', 'moment', 'locale/sv_SE/LC_MESSAGES/client'], (
    React, moment, client_sv) ->

    all_translations =
        client:
            sv_SE: client_sv
            sv: client_sv

    translations = null
    locale = document.getElementsByTagName('html')[0].getAttribute('lang')
    moment.locale(locale)

    try
        bcp47 = locale.split('_')[0]
    catch
        bcp47 = null

    class Message extends React.Component

        @defaultProps:
            className: ''
            attributes: {}

        render: ->
            message = @props.message
            for k, v of @props.attributes
                message = message.replace("{#{ k }}", v)

            <span
                className=@props.className
                dangerouslySetInnerHTML={__html: message} />


    gettext =

        bcp47: bcp47

        install: (domain) ->
            translations = all_translations[domain][locale]

        gettext: (msgid) ->
            try
                return translations[msgid][1] or msgid
            catch
                return msgid

        Message: Message
