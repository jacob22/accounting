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
    'react-dom',
    'gettext',
    'utils',
    'iter',
    'moment',
    'signals',
    'jslink/JsLink',
    'jslink/query',
    'jslink/commit',
    'widgets/accountspayable/invoice',
    'widgets/accountspayable/invoiceextractor',
    'classnames',
    ], (
    React,
    ReactDOM,
    gettext,
    utils,
    iter,
    moment,
    signals,
    JsLink,
    query,
    commit,
    Invoice,
    InvoiceExtractor,
    classnames,
    ) ->

    _ = gettext.gettext

    class InvoiceList extends React.Component
        render: () =>
            if not @props.supplierInvoiceQuery.gotResult
                return <div className='d-flex h-100 my-5 justify-content-center'>Loading supplier invoices...</div>
            widgets = []
            # New forms
            for key in @props.newformlist
                widgets.push(
                    <Invoice
                        key={key}
                        toid={key}
                        selected={@props.selected}
                        toggleSelected={@props.toggleSelected}
                        deSelect={@props.deSelect}
                        supplierInvoiceList={@props.supplierInvoiceList}
                        recipients={@props.recipients}
                        fetchPredictions={@props.fetchPredictions}
                        createSupplierInvoice={@props.createSupplierInvoice}
                        updateSupplierInvoice={@props.updateSupplierInvoice}
                        removeNewForms={@props.removeNewForms}
                        verificationsWatcher={@props.verificationsWatcher}
                        transactionsWatcher={@props.transactionsWatcher}
                        accountsQuery={@props.accountsQuery}
                        seriesQuery={@props.seriesQuery}
                        uploadInvoiceImage={@props.uploadInvoiceImage}
                        removeInvoiceImage={@props.removeInvoiceImage}
                        expand={true}
                        />
                )

            # SupplierInvoices from query
            for toid in @props.supplierInvoiceList by @props.sortingOrder
                widgets.push(
                    <InvoiceExtractor
                        key={toid}
                        toid={toid}
                        selected={@props.selected}
                        toggleSelected={@props.toggleSelected}
                        select={@props.select}
                        deSelect={@props.deSelect}
                        enableAutomation={@props.enableAutomation}
                        disableAutomation={@props.disableAutomation}
                        setRegistered={@props.setRegistered}
                        createTransferVerification={@props.createTransferVerification}
                        supplierInvoiceList={@props.supplierInvoiceList}
                        recipients={@props.recipients}
                        createSupplierInvoice={@props.createSupplierInvoice}
                        updateSupplierInvoice={@props.updateSupplierInvoice}
                        deleteSupplierInvoice={@props.deleteSupplierInvoice}
                        verificationsWatcher={@props.verificationsWatcher}
                        transactionsWatcher={@props.transactionsWatcher}
                        accountsQuery={@props.accountsQuery}
                        seriesQuery={@props.seriesQuery}
                        uploadInvoiceImage={@props.uploadInvoiceImage}
                        removeInvoiceImage={@props.removeInvoiceImage}
                        imageQuery={@props.imageQuery}
                        filterArguments={@props.filterArguments}
                        searchTerm={@props.searchTerm}
                        viewJournal={@props.viewJournal}
                        invoice={@props.supplierInvoiceTData[toid]}
                        />
                )
            html =
                <div
                    id="accordion"
                    role="tablist"
                    aria-multiselectable="true"
                    className='mb-3'
                    >
                    {widgets}
                </div>
            return html
