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

define [
    'react',
    'gettext',
    'utils',
    ], (
    React,
    gettext,
    utils,
    ) ->

    _ = gettext.gettext

    class Status extends React.Component
        @defaultStatus:
            prodImportStatus: null
            transImportStatus: null
            providerStatus: null
            
        constructor: (props) ->
            super(props)
            @state = {}
            @state.productsMismatchRules = @checkAccountingRules(props.productsData)
            @state.prodImportStatus = props.prodImportStatus
            @state.prodImportStatusResult = props.prodImportStatusResult
            @state.accountsMissing = @checkAccountsMissing(props.productsData, props.accountMap)
            @state.transImportStatus = props.transImportStatus
            @state.transImportStatusResult = props.transImportStatusResult

        componentWillReceiveProps: (nextprops) ->
            @setState({'productsMismatchRules': @checkAccountingRules(nextprops.productsData)})
            @setState({'accountsMissing': @checkAccountsMissing(nextprops.productsData, nextprops.accountMap)})

            if nextprops.prodImportStatus?
                @setState({'prodImportStatus': nextprops.prodImportStatus})
                @setState({'prodImportStatusResult': nextprops.prodImportStatusResult})
            if nextprops.transImportStatus?
                @setState({'transImportStatus': nextprops.transImportStatus})
                @setState({'transImportStatusResult': nextprops.transImportStatusResult})

            
        checkAccountingRules: (productsData) ->
            counter = 0
            for id, product of productsData
                # Skip products with blank izPrice
                if not product.izPrice.length
                    continue
                price = utils.parseCurrency(product.izPrice[0])
                sum = 0
                for acc, amount of product.accountingRules
                    sum = sum + utils.parseCurrency(amount)
                if sum != price
                    counter = counter + 1
            return counter

        checkAccountsMissing: (productsData, accountMap) ->
            if not accountMap?
                return 0
            counter = 0
            for id, product of productsData
                for accountNumber, amount of product.accountingRules
                    if accountNumber not of accountMap
                        counter = counter + 1
            return counter

        hideprod: () =>
            @setState({'prodImportStatus': null})

        hidetrans: () =>
            @setState({'transImportStatus': null})

        render: () ->
            <div>
                {<div className='alert alert-success alert-dismissible' role='alert'>
                    <strong>{_('Success!')}</strong>
                    <span className="alerttext">
                        <gettext.Message
                            message={_(
                                'The uploded iZettle products file has been imported,
                                creating {created} new, and updating {updated}
                                iZettle products.')},
                            attributes={@state.prodImportStatusResult}/>
                    </span>
                    <button type="button" className="close" aria-label="Close" onClick={@hideprod}>
                        <span aria-hidden="true">&times;</span>
                    </button>
                </div> if @state.prodImportStatus == 'success' }
                
                {<div className='alert alert-danger alert-dismissible' role='alert'>
                    <strong>{_('Failure!')}</strong>
                    <span className='alerttext'>
                        <gettext.Message
                            message={_('The iZettle product import failed.')} />
                    </span>
                    <button type="button" className="close" aria-label="Close" onClick={@hideprod}>
                        <span aria-hidden="true">&times;</span>
                    </button>
                </div> if @state.prodImportStatus == 'failure' }

                {<div className='alert alert-warning alert-dismissible' role='alert'>
                    <strong>{_('Warning!')}</strong>
                    <span className='alerttext'>
                        <gettext.Message
                            message={_('In {number} iZettle products the price does not match
                                the accounting rules. These products are marked with
                                <i class="fa fa-exclamation-triangle" aria-hidden="true"></i>.')}
                            attributes={number: @state.productsMismatchRules} />
                    </span>
                </div> if @state.productsMismatchRules }

                {<div className='alert alert-warning' role='alert'>
                    <strong>{_('Warning!')}</strong>
                    <gettext.Message
                        message={_('In {number} iZettle products an account
                                    is no longer present in the current account plan.
                                    These products are marked with
                                    <i class="fa fa-bug" aria-hidden="true"></i>.')}
                        attributes={number: @state.accountsMissing}
                        className='alerttext' />
                </div> if @state.accountsMissing > 0}

                {<div className='alert alert-success alert-dismissible' role='alert'>
                    <strong>{_('Success!')}</strong>
                    <span className='alerttext'>
                        <gettext.Message
                            message={_('The uploaded transactions file has
                                been imported, 
                                creating {created} payments.')},
                            attributes={@state.transImportStatusResult} />
                    </span>
                    <button type="button" className="close" aria-label="Close" onClick={@hidetrans}>
                        <span aria-hidden="true">&times;</span>
                    </button>
                </div> if @state.transImportStatus == 'success' }
                
                {<div className='alert alert-danger alert-dismissible' role='alert'>
                    <strong>{_('Failure!')}</strong>
                    <span className='alerttext'>
                        <gettext.Message
                            message={_('The iZettle transaction import failed.')} />
                    </span>
                    <button type="button" className="close" aria-label="Close" onClick={@hidetrans}>
                        <span aria-hidden="true">&times;</span>
                    </button>
                </div> if @state.transImportStatus == 'failure' }

                {<div className='alert alert-info' role='alert'>
                    <strong>{_('Attention!')}</strong>
                    <gettext.Message
                        message={_('You have not set up iZettle as a payment provider for your organization.')}
                        className='alerttext' />
                </div> if @props.providerStatus == 'missing'}

                {<div className='alert alert-warning' role='alert'>
                    <strong>{_('Warning!')}</strong>
                    <gettext.Message
                        message={_('Accounts used in your iZettle payment provider settings is missing in the current accounting. Correct this situation in order to import transactions.')}
                        className='alerttext' />
                </div> if @props.providerStatus != null and @props.providerStatus != 'missing'}
            </div>

    return Status
