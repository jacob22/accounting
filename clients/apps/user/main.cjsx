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

require [
    'react',
    'react-dom',
    'cookies',
    'signals',
    'widgets/rwfield',
    'jslink/JsLink',
    'jslink/ToiSetWatcher',
    'jslink/commit',
    'jslink/query',
    ], (prereqs...) ->
    [
        React,
        ReactDOM,
        cookies,
        signals,
        RWField,
        JsLink,
        ToiSetWatcher,
        commit,
        query,
    ] = prereqs


    OrgList = React.createClass

        getDefaultProps: ->
            organisations: {}

        getInitialState: ->
            organisations: @props.organisations

        render: ->
            rows = []
            for toid, data of @state.organisations
                name = data.name[0]
                rows.push(<div key={toid}>{name}</div>)
            return <div>{rows}</div>

    fields =
        name: ReactDOM.render(
            <RWField name="name" label="Name" value="<current user>" />
            document.getElementById('name')
        )

        emailAddress: ReactDOM.render(
            <RWField name="emailAddress" label="Email" />
            document.getElementById('email')
        )

        organisations: ReactDOM.render(
            <OrgList />
            document.getElementById('organisations')
        )

    jsLink = new JsLink('/jslink')

    jsLink.ready.then(->
        tsw = new ToiSetWatcher(jsLink, 'accounting.User',
            ['name', 'emailAddress'])
        p = tsw.perspective()
        signals.connect(p, 'refresh', (p, setId, toiIds) ->
            if setId == 'me'
                [toid] = toiIds
                toiData = p.getToiData(toid)
                fields.name.setState(value: toiData.name[0])
                fields.emailAddress.setState(value: toiData.emailAddress[0])
        )
        p.watch('me', [cookies.get('userid')])

        q = new query.SortedQuery(jsLink, 'accounting.Org')
        q.attrList = ['name']
        signals.connect(q, 'update', (args) ->
            organisations = {}
            for toid in q.result
                data = q.toiData[toid]
                organisations[toid] = data
            fields.organisations.setState(organisations: organisations)
        )
        q.start()
    )

    document.getElementById('save_userdetails').onclick = ->
        data =
            name: fields.name.state.value
            emailAddress: fields.emailAddress.state.value

        commit.callToiMethod(
            jsLink,
            cookies.get('userid'),
            'set_data',
            [[data]],
            (args...) ->
        )
