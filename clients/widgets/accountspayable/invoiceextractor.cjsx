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
    'react-bootstrap-typeahead',
    'widgets/amount',
    'widgets/date',
    'data/accountspayable/verification',
    'widgets/accountspayable/fileuploader',
    'widgets/verification',
    'widgets/accountspayable/invoice',
    'widgets/accountspayable/journal',
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
    Typeahead,
    Amount,
    DatePicker,
    VerDataAggregator,
    FileUploader,
    Verification,
    Invoice,
    Journal,
    classnames,
    ) ->

    _ = gettext.gettext

    class InvoiceExtractor extends React.Component
        constructor: (props) ->
            super(props)
            newstate =  @_extract(props)
            @state = newstate

        componentWillReceiveProps: (nextProps) ->
            newstate = @_extract(nextProps)
            @setState(newstate)

        _extract: (props) ->
            if props.invoice.accounted
                accounted=props.invoice.accounted[0]
            else
                accounted=false

            if props.invoice.invoiceState
                invoiceState=props.invoice.invoiceState[0]
            else
                invoiceState=''

            if props.invoice.automated
                automated=props.invoice.automated[0]
            else
                automated=''

            if props.invoice.recipient
                recipient=props.invoice.recipient[0]
            else
                recipient=''

            if props.invoice.invoiceType
                invoiceType=props.invoice.invoiceType[0]
            else
                invoiceType=''

            if props.invoice.amount
                amount=props.invoice.amount[0]
            else
                amount=0

            if props.invoice.transferMethod
                transferMethod=props.invoice.transferMethod[0]
            else
                transferMethod=''

            if props.invoice.pgnum
                pgnum=props.invoice.pgnum[0]
            else
                pgnum=''

            if props.invoice.bgnum
                bgnum=props.invoice.bgnum[0]
            else
                bgnum=''

            if props.invoice.bankaccount
                bankaccount=props.invoice.bankaccount[0]
            else
                bankaccount=''

            if props.invoice.bankclearing
                bankclearing=props.invoice.bankclearing[0]
            else
                bankclearing=''

            if props.invoice.invoiceIdentifierType
                invoiceIdentifierType=props.invoice.invoiceIdentifierType[0]
            else
                invoiceIdentifierType=''

            if props.invoice.ocr
                ocr=props.invoice.ocr[0]
            else
                ocr=''

            if props.invoice.invoiceNumber
                invoiceNumber=props.invoice.invoiceNumber[0]
            else
                invoiceNumber=''

            if props.invoice.message
                message=props.invoice.message[0]
            else
                message=''

            if props.invoice.invoiceDate
                invoiceDate=props.invoice.invoiceDate[0]
            else
                invoiceDate=''

            if props.invoice.transferDate
                transferDate=props.invoice.transferDate[0]
            else
                transferDate=''

            if props.invoice.dueDate
                dueDate=props.invoice.dueDate[0]
            else
                dueDate=''

            if props.invoice.rejected_log
                rejected_log=props.invoice.rejected_log[0]
            else
                rejected_log=''

            if props.invoice.registrationVerification
                registrationVerification=props.invoice.registrationVerification[0]
            else
                registrationVerification=null

            if props.invoice.transferVerification
                transferVerification=props.invoice.transferVerification[0]
            else
                transferVerification=null

            newstate = {
                'accounted': accounted,
                'invoiceState': invoiceState,
                'automated': automated,
                'rejected_log': rejected_log,
                'recipient': recipient,
                'invoiceType': invoiceType,
                'amount': amount,
                'invoiceDate': invoiceDate,
                'transferDate': transferDate,
                'dueDate': dueDate,
                'transferMethod': transferMethod,
                'pgnum': pgnum,
                'bgnum': bgnum,
                'bankaccount': bankaccount,
                'bankclearing': bankclearing,
                'invoiceIdentifierType': invoiceIdentifierType,
                'ocr': ocr,
                'invoiceNumber': invoiceNumber,
                'message': message,
                'registrationVerification': registrationVerification,
                'transferVerification': transferVerification,
            }
            return newstate

        _filter: (filterArguments) =>
            # Hide if there is a filter and it does not match
            if @props.toid of @props.selected
                # Selected SI should never be hidden
                return true
            if not filterArguments?
                filterArguments = @props.filterArguments
            showMe = true
            for key, value of filterArguments
                re_search = new RegExp(value, 'i')
                #console.log('matching filter', value, @state[key], 'for', key)
                if not (@state[key]).toString().match(re_search)
                    showMe = false
            return showMe

        _searchkeys: [
            'invoiceState',
            'transferDate',
            'recipient',
            'bgnum',
            'pgnum',
            'bankclearing',
            'bankaccount',
            'ocr',
            'invoiceNumber',
            'message',
            'amount']

        _search: (searchTerm) =>
            if not searchTerm?
                searchTerm = @props.searchTerm
            showMe = undefined
            if searchTerm
                re_search = new RegExp(searchTerm, 'i')
                showMe = false
                for key in @_searchkeys
                    if @state[key]?
                        #console.log('search', key, 'matching', @state[key], 'against', searchTerm)
                        if (@state[key]).toString().match(re_search)
                            showMe = true
            return showMe

        render: () ->
            html = null
            f = @_filter(@props.filterArguments)
            s = @_search(@props.searchTerm)
            if s?
                show = s
            else
                show = f
            if show and not @props.viewJournal
                html =
                    <Invoice
                        toid={@props.toid}
                        selected={@props.selected}
                        toggleSelected={@props.toggleSelected}
                        select={@props.select}
                        deSelect={@props.deSelect}
                        supplierInvoiceList={@props.supplierInvoiceList}
                        createSupplierInvoice={@props.createSupplierInvoice}
                        updateSupplierInvoice={@props.updateSupplierInvoice}
                        deleteSupplierInvoice={@props.deleteSupplierInvoice}
                        recipients={@props.recipients}
                        fetchPredictions={() => ;}
                        enableAutomation={@props.enableAutomation}
                        disableAutomation={@props.disableAutomation}
                        setRegistered={@props.setRegistered}
                        createTransferVerification={@props.createTransferVerification}
                        accounted={@state.accounted}
                        invoiceState={@state.invoiceState}
                        automated={@state.automated}
                        rejected_log={@state.rejected_log}
                        recipient={@state.recipient}
                        invoiceType={@state.invoiceType}
                        amount={@state.amount}
                        transferMethod={@state.transferMethod}
                        pgnum={@state.pgnum}
                        bgnum={@state.bgnum}
                        bankaccount={@state.bankaccount}
                        bankclearing={@state.bankclearing}
                        invoiceIdentifierType={@state.invoiceIdentifierType}
                        ocr={@state.ocr}
                        invoiceNumber={@state.invoiceNumber}
                        message={@state.message}
                        invoiceDate={@state.invoiceDate}
                        transferDate={@state.transferDate}
                        dueDate={@state.dueDate}
                        registrationVerification={@state.registrationVerification}
                        transferVerification={@state.transferVerification}
                        images={@props.invoice.images}
                        verificationsWatcher={@props.verificationsWatcher}
                        transactionsWatcher={@props.transactionsWatcher}
                        accountsQuery={@props.accountsQuery}
                        seriesQuery={@props.seriesQuery}
                        uploadInvoiceImage={@props.uploadInvoiceImage}
                        removeInvoiceImage={@props.removeInvoiceImage}
                        imageQuery={@props.imageQuery}
                        />
            if show and @props.viewJournal
                html =
                    <Journal
                        toid={@props.toid}
                        selected={@props.selected}
                        toggleSelected={@props.toggleSelected}
                        select={@props.select}
                        deSelect={@props.deSelect}
                        supplierInvoiceList={@props.supplierInvoiceList}
                        createSupplierInvoice={@props.createSupplierInvoice}
                        updateSupplierInvoice={@props.updateSupplierInvoice}
                        deleteSupplierInvoice={@props.deleteSupplierInvoice}
                        recipients={@props.recipients}
                        fetchPredictions={() => ;}
                        enableAutomation={@props.enableAutomation}
                        disableAutomation={@props.disableAutomation}
                        setRegistered={@props.setRegistered}
                        createTransferVerification={@props.createTransferVerification}
                        accounted={@state.accounted}
                        invoiceState={@state.invoiceState}
                        automated={@state.automated}
                        rejected_log={@state.rejected_log}
                        recipient={@state.recipient}
                        invoiceType={@state.invoiceType}
                        amount={@state.amount}
                        transferMethod={@state.transferMethod}
                        pgnum={@state.pgnum}
                        bgnum={@state.bgnum}
                        bankaccount={@state.bankaccount}
                        bankclearing={@state.bankclearing}
                        invoiceIdentifierType={@state.invoiceIdentifierType}
                        ocr={@state.ocr}
                        invoiceNumber={@state.invoiceNumber}
                        message={@state.message}
                        invoiceDate={@state.invoiceDate}
                        transferDate={@state.transferDate}
                        dueDate={@state.dueDate}
                        registrationVerification={@state.registrationVerification}
                        transferVerification={@state.transferVerification}
                        images={@props.invoice.images}
                        verificationsWatcher={@props.verificationsWatcher}
                        transactionsWatcher={@props.transactionsWatcher}
                        accountsQuery={@props.accountsQuery}
                        seriesQuery={@props.seriesQuery}
                        uploadInvoiceImage={@props.uploadInvoiceImage}
                        removeInvoiceImage={@props.removeInvoiceImage}
                        imageQuery={@props.imageQuery}
                        />

            return html

