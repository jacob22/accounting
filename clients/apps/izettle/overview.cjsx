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

define([
    'react',
    'react-dom',
    'gettext',
    'signals',
    'jslink/JsLink',
    'jslink/query',
    'jslink/commit',
    'data/user',
    'widgets/izettle/izettle',
    'widgets/sie4iimport/sie4imenu',
    'widgets/sie4iimport/sie4istatus'
    ], (
    React,
    ReactDOM,
    gettext,
    signals,
    JsLink,
    query,
    commit,
    User,
    izettle,
    Sie4iImporter,
    Sie4istatus
    ) ->

    _ = gettext.gettext

    import4istatus = ->
        ReactDOM.render(
            <Sie4istatus />,
            document.getElementById('4i-status')
        )
    import4i = ->
        ReactDOM.render(
            <Sie4iImporter />,
            document.getElementById('4i-targetdiv')
        )

    if document.location.hostname != 'admin.eutaxia.eu'
        import4istatus()
        import4i()

)
