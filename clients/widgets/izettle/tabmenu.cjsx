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
    'widgets/izettle/productimporter',
    'widgets/izettle/productlist',
    'widgets/izettle/transactionsimporter',
    'widgets/izettle/transactionshistory',
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
    ProductImporter,
    ProductList,
    TransactionsImporter,
    TransactionsHistory,
    ) ->

    _ = gettext.gettext
    
    class TabMenu extends React.Component
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
                <div className='card-header'>
                    <ul className="nav nav-tabs card-header-tabs">
                        <li className="nav-item">
                            <a
                                role='button'
                                className={classnames({
                                    'nav-link': true
                                    'active': @state.activeTab == '1'
                                })}
                                onClick={() => @toggle('1')} >{_('iZettle Products')}</a>
                        </li>
                        <li className="nav-item">
                            <a
                                role='button'
                                className={classnames({
                                    'nav-link': true
                                    'active': @state.activeTab == '2'
                                })}
                                onClick={() => @toggle('2')} >{_('iZettle Transactions')}</a>
                        </li>
                    </ul>
                </div>
                <div className='card-body'>
                    <rs.TabContent activeTab={@state.activeTab}>
                        <rs.TabPane tabId="1">
                            <div className='row no-gutters'>
                                <div className='col'>
                                    <ProductImporter
                                        importProducts={@props.importProducts}
                                        editable={@props.storekeeper} />
                                    <ProductList
                                        accountsQuery={@props.accountsQuery},
                                        onUpdate={@props.onUpdate},
                                        accountMap={@props.accountMap},
                                        toilist={@props.prodToiList},
                                        toiData={@props.prodToiData}
                                        editable={@props.storekeeper} />
                                </div>
                            </div>
                        </rs.TabPane>
                        <rs.TabPane tabId="2">
                            <div className='row no-gutters'>
                                <div className='col'>
                                    {<TransactionsImporter
                                        importTransactions={@props.importTransactions} /> if @props.providerStatus == null }
                                    <TransactionsHistory
                                        transactionsHistory={@props.transactionsHistory} />
                                </div>
                            </div>
                        </rs.TabPane>
                    </rs.TabContent>
                </div>
            </div>
)
