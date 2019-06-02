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
    'js-file-download',
    'signals',
    'jslink/JsLink',
    'jslink/query',
    'jslink/commit',
    'widgets/date',
    'widgets/accountspayable/invoicelist',
    'widgets/accountspayable/menues',
    'classnames',
    ], (
    React,
    ReactDOM,
    gettext,
    utils,
    iter,
    moment,
    fileDownload,
    signals,
    JsLink,
    query,
    commit,
    DatePicker,
    InvoiceList,
    Menues,
    classnames,
    ) ->

    _ = gettext.gettext

    class Main extends React.Component
        constructor: (props) ->
            super(props)
            @state = {
               newformlist: [],
               counter: iter.count(),
               selected: {},
               sortingOrder: 1,
               filterArguments: {'accounted': false},
            }

        componentWillReceiveProps: (nextProps) ->
            # Prune selection of SupplierInvoice toids no longer in scope.
            if nextProps.supplierInvoiceList != @props.supplierInvoiceList
                newsel = {}
                for toid in nextProps.supplierInvoiceList
                    if toid of @state.selected
                        newsel[toid] = true
                @setState(selected: newsel)

        _genKey: () =>
            newkey = 'new' + @state.counter.next()
            return newkey

        _createNewForm: () =>
            newformlist = [@_genKey()].concat(@state.newformlist)
            @setState(newformlist: newformlist)

        _removeNewForms: (keys) =>
            n = []
            for a in @state.newformlist
                if a not in keys
                    n.push(a)
            @setState(newformlist: n)

        # SELECTION
        _toggleSelected: (event) =>
            # Add or remove toid from dict of selected Invoices.
            toid = event.target.value
            selected = utils.copyobj(@state.selected)
            if toid not of selected
                # add toid to selected
                selected[toid] = true
            else
                # remove/filter toid from selected
                delete selected[toid]
            @setState(selected: selected)
            console.log(selected)

        _select: (toid) =>
            selected = utils.copyobj(@state.selected)
            selected[toid] = true
            @setState(selected: selected)
            console.log(selected)

        _deSelect: (toid) =>
            selected = utils.copyobj(@state.selected)
            if toid of selected
                delete selected[toid]
                @setState(selected: selected)
                console.log(selected)

        _selectNone: () =>
            @setState(selected: {})

        _selectInvert: () =>
            # Create an object for with keys as javascript has no Set
            inv = {}
            for a in [].concat(@props.supplierInvoiceList, @state.newformlist)
                if a not of @state.selected
                    inv[a] = true
            @setState(selected: inv)
            console.log(inv)

        _selectAll: () =>
            selected = {}
            for toid in [].concat(@props.supplierInvoiceList, @state.newformlist)
                selected[toid] = true
            @setState(selected: selected)
            console.log(selected)

        _selectAllUnaccounted: () =>
            selected = {}
            for toid in [].concat(@props.supplierInvoiceList, @state.newformlist)
                si = @props.supplierInvoiceTData[toid]
                if si['accounted'][0] == false
                    selected[toid] = true
            @setState(selected: selected)
            console.log(selected)

        _selectDue: () =>
            selection = {}
            for toid in @props.supplierInvoiceList
                si = @props.supplierInvoiceTData[toid]
                tdate = si['transferDate'][0]
                transferDateObj = moment(tdate)
                dueDateObj = moment(si['dueDate'][0])
                due = (
                    moment().isAfter(transferDateObj) or moment().isAfter(dueDateObj)
                )
                if due or (not tdate?)
                    if si['invoiceState'][0] == 'registered' and si['automated'][0] == false
                        selection[toid] = true
            @setState(selected: selection)
            console.log(selection)

        _selectPaid: () =>
            selection = {}
            for toid in @props.supplierInvoiceList
                si = @props.supplierInvoiceTData[toid]
                if si['invoiceState'][0] == 'paid' and si['accounted'][0] == false
                    selection[toid] = true
            @setState(selected: selection)
            console.log(selection)

        _printSelected: () =>
            console.log(@state.selected)

        _filterNew: (selection) =>
            selection = utils.copyobj(selection)
            for toid of selection
                if toid in @state.newformlist
                    delete selection[toid]
            return selection

        _setFilter: (key, value) =>
            filter = utils.copyobj(@state.filterArguments)
            filter[key] = value
            console.log('filter', filter)
            @setState(filterArguments: filter)

        _delFilter: (key) =>
            filter = utils.copyobj(@state.filterArguments)
            delete filter[key]
            console.log('filter', filter)
            @setState(filterArguments: filter)

        _changeQueryStartDate: (event) =>
            date = event.target.value
            @setState(startdatestring: date)
            @props.setQueryDates(date, @state.stopdatestring)

        _changeQueryStopDate: (event) =>
            date = event.target.value
            @setState(stopdatestring: date)
            @props.setQueryDates(@state.startdatestring, date)

        _setSearchTerm: (term) =>
            @setState(searchTerm: term)


        # BLM METHODS CALLS

        _createSupplierInvoice: (key, invoice) =>
            callback = (createStatus) =>
                @setState(working: false)
                if createStatus == 'success'
                    @_removeNewForms([key])
            @setState(working: true)
            @props.createSupplierInvoice(invoice, callback)

        _deleteSupplierInvoice: (selected) =>
            newlist = []
            toidList = []
            for toid in selected
                # Separate new and drafts
                if toid in @props.supplierInvoiceList
                    # Saved drafts
                    toidList.push(toid)
                else
                    newlist.push(toid)
            @_removeNewForms(newlist)
            @props.deleteSupplierInvoice(toidList)

        _generatePlusgiroFile: (selected) =>
            callback = (resultStatus, resultData) =>
                console.log(resultStatus)
                @setState(working: false)
                if resultStatus == 'success'
                    console.log(resultData)
                    fileDownload(resultData[0], 'plusgiro_cfp_po3.txt')
                else
                    @props.renderAlerts([{
                        contextcolor: 'danger'
                        title: 'Failure!'
                        message: 'File generation failed: {err}'
                        messageattrs: {err: resultData}
                    }])
            if selected.length >= 1
                @setState(working: true)
                @props.generatePlusgiroFile(selected, callback)

        _generateLBin: (selected) =>
            # Developer tool. This should never be enabled in production!
            callback = (resultStatus, resultData) =>
                console.log(resultStatus)
                @setState(working: false)
                if resultStatus == 'success'
                    console.log(resultData)
                    @props.renderAlerts([{
                        contextcolor: 'info'
                        title: 'Note!'
                        message: 'Wrote transfer order to file: {filename}'
                        messageattrs: {filename: resultData}
                    }])
            if selected.length >= 1
                @setState(working: true)
                @props.generateLBin(selected, callback)

        _enableAutomation: (selected) =>
            callback = () =>
                @setState(working: false)
            @setState(working: true)
            if selected.length >= 1
                @props.enableSIAutomation(selected, callback)

        _disableAutomation: (selected) =>
            callback = () =>
                @setState(working: false)
            @setState(working: true)
            if selected.length >= 1
                @props.disableSIAutomation(selected, callback)

        _createTransferVerification: (selected) =>
            callback = () =>
                @setState(working: false)
            @setState(working: true)
            if selected.length >= 1
                @props.createTransferVerification(selected, callback)

        render: () =>
            invoicelist =
                 <InvoiceList
                        fetchPredictions={@props.fetchPredictions}
                        updateSupplierInvoice={@props.updateSupplierInvoice}
                        deleteSupplierInvoice={@_deleteSupplierInvoice}
                        removeNewForms={@_removeNewForms}
                        createTransferVerification={@props.createTransferVerification}
                        setSIState={@props.setSIState}
                        enableSIAutomation={@props.enableSIAutomation}
                        disableSIAutomation={@props.disableSIAutomation}
                        generatePlusgiroFile={@props.generatePlusgiroFile}
                        generateLBin={@props.generateLBin}
                        uploadInvoiceImage={@props.uploadInvoiceImage}
                        removeInvoiceImage={@props.removeInvoiceImage}
                        supplierInvoiceList={@props.supplierInvoiceList}
                        supplierInvoiceTData={@props.supplierInvoiceTData}
                        supplierInvoiceQuery={@props.supplierInvoiceQuery}
                        verificationsWatcher={@props.verificationsWatcher}
                        transactionsWatcher={@props.transactionsWatcher}
                        accountsQuery={@props.accountsQuery}
                        seriesQuery={@props.seriesQuery}
                        providerQuery={@props.providerQuery}
                        imageQuery={@props.imageQuery}
                        recipients={@props.recipients}
                        renderAlerts={@props.renderAlerts}
                        viewJournal={@state.viewJournal}
                        selected={@state.selected}
                        newformlist={@state.newformlist}
                        sortingOrder={@state.sortingOrder}
                        toggleSelected={@_toggleSelected}
                        select={@_select}
                        deSelect={@_deSelect}
                        enableAutomation={@_enableAutomation}
                        disableAutomation={@_disableAutomation}
                        createTransferVerification={@_createTransferVerification}
                        createSupplierInvoice={@_createSupplierInvoice}
                        filterArguments={@state.filterArguments}
                        searchTerm={@state.searchTerm}
                        />

            html =
                <div>
                    <Menues
                        createNewForm={@_createNewForm}
                        selectNone={@_selectNone}
                        selectInvert={@_selectInvert}
                        selectAll={@_selectAll}
                        selectAllUnaccounted={@_selectAllUnaccounted}
                        selectDue={@_selectDue}
                        selectPaid={@_selectPaid}
                        setFilter={@_setFilter}
                        delFilter={@_delFilter}
                        filterArguments={@state.filterArguments}
                        setParentState={(dict) => @setState(dict)}
                        setQueryDates={@props.setQueryDates}
                        deleteSupplierInvoice={@_deleteSupplierInvoice}
                        generatePlusgiroFile={@_generatePlusgiroFile}
                        generateLBin={@_generateLBin}
                        enableAutomation={@_enableAutomation}
                        disableAutomation={@_disableAutomation}
                        setSearchTerm={@_setSearchTerm}
                        createTransferVerification={@_createTransferVerification}
                        setSIState={@props.setSIState}
                        # Data
                        selected={@state.selected}
                        enableNew={(@props.providerQuery.result? and @props.providerQuery.result[0])}
                        working={@state.working}
                        supplierInvoiceList={@props.supplierInvoiceList}
                        # filterNew
                        newformlist={@state.newformlist}
                        />
                    {invoicelist}
                </div>
            return html
