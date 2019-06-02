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
    'reactstrap',
    'classnames',
    'widgets/sie4iimport/sie4i',
    'widgets/sie4iimport/sie4ilist'
    ],(
    React,
    ReactDOM
    gettext,
    signals,
    JsLink,
    query,
    commit,
    rs,
    classnames,
    Sie4iImporter,
    Sie4iList
    ) ->

    _ = gettext.gettext

    class Sie4iMenu extends React.Component
        @defaultProps:
            activeTab: '1'

        constructor: (props) ->
            super(props)
            @state = {'activeTab': props.activeTab}

        toggle: (tab) =>
            if @state.activeTab != tab
                @setState({'activeTab': tab})

        render: () ->
            <div className='card mb-3'>

                <div className='card-body'>
                    <rs.TabContent activeTab={@state.activeTab}>
                        <rs.TabPane tabId="1">
                            <div className='row no-gutters'>
                                <div className='col'>
                                    <Sie4iImporter
                                        importProducts={@props.importProducts}
                                        editable={@props.storekeeper} />
                                    <Sie4iList
                                        accountsQuery={@props.accountsQuery},
                                        onUpdate={@props.onUpdate},
                                        accountMap={@props.accountMap},
                                        toilist={@props.prodToiList},
                                        toiData={@props.prodToiData}
                                        editable={@props.storekeeper} />
                                </div>
                            </div>
                        </rs.TabPane>

                    </rs.TabContent>
                </div>
            </div>
)
