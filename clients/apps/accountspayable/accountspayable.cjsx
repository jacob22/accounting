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
    'react', 'react-dom',
    'gettext', 'signals', 'utils',
    'jslink/JsLink', 'jslink/ToiSetWatcher', 'jslink/query', 'jslink/commit',
    'widgets/amount', 'widgets/date',
    'widgets/accountspayable/main',
    'widgets/accountspayable/authorize',
    'widgets/accountspayable/fileuploader',
    'widgets/accountspayable/settings',
    'widgets/accountspayable/alerts',
    'classnames',
    ], ->

    [React, ReactDOM,
     gettext, signals, utils,
     JsLink, ToiSetWatcher, query, commit,
     Amount, DatePicker,
     Main,
     Authorize,
     Fileuploader,
     Settings,
     Alerts,
     classnames,
    ] = arguments

    gettext.install('client')
    _ = gettext.gettext

    orgid = document.location.pathname.split('/')[-1..][0]
    
    # Data link setup
    jsLink = new JsLink('/jslink')

    # Queries
    SIattrList = [
        'org',
        'accounted',
        'invoiceState',
        'automated',
        'recipient',
        'invoiceType',
        'amount',
        'transferMethod',
        'pgnum',
        'bgnum',
        'bankaccount',
        'bankclearing',
        #'transferAddress',
        'invoiceIdentifierType',
        'ocr',
        'invoiceNumber',
        'message',
        #'invoiceIdentifier',
        'registrationVerification',
        'transferVerification',
        'invoiceDate',
        'dateInvoiceRegistered',
        'transferDate',
        'dueDate',
        'rejected_log',
        'images']

    startdate=''
    stopdate='a'
    setQueryDates = (start, stop) =>
        console.log('querydates', start, stop)
        startdate = start
        stopdate = stop or 'a'
        supplierInvoiceQuery.link.deactivate()
        supplierInvoiceQuery.result = []
        supplierInvoiceQuery.toiData = {}
        supplierInvoiceQuery.condGroups = []
        if start.length > 0 or stop.length > 0
            supplierInvoiceQuery.push({'org': orgid, 'transferDate': new query.Operator.Between(startdate, stopdate)})
        else
            supplierInvoiceQuery.push({'org': orgid})
        supplierInvoiceQuery.start()

    supplierInvoiceQuery = new query.SortedQuery(
        jsLink, 'accounting.SupplierInvoice', {'org': orgid}
    )
    supplierInvoiceQuery.attrList = SIattrList
    supplierInvoiceQuery.sorting = 'transferDate'

    accountingYearQuery = new query.SortedQuery(
        jsLink, 'accounting.Org', {'id': orgid}
    )
    accountingYearQuery.attrList = ['current_accounting']

    accountsQuery = new query.SortedQuery(
        jsLink, 'accounting.Account'
    )
    accountsQuery.attrList = ['name', 'number']
    accountsQuery.sorting = 'number'

    seriesQuery = new query.SortedQuery(
        jsLink, 'accounting.VerificationSeries'
    )
    seriesQuery.attrList = ['name', 'description']

    providerQuery = new query.SortedQuery(
        jsLink, 'accounting.SupplierInvoiceProvider', {'org': orgid}
    )
    providerQuery.attrList = ['series', 'account', 'bank_account', 'transferVerification_text', 'plusgiro_sending_bank_account']

    imageQuery = new query.SortedQuery(
        jsLink, 'accounting.InvoiceImage'
    )
    imageQuery.attrList = ['filename']

    verificationsWatcher = new ToiSetWatcher(
        jsLink, 'accounting.Verification', ['transactions', 'version', 'series', 'number']
    )

    transactionsWatcher = new ToiSetWatcher(
        jsLink, 'accounting.Transactions', ['account', 'amount', 'text', 'version']
    )

    recipients = undefined

    # Div functions
    #_setQueryArgs = (newargs) =>
    #    newargs['org'] = orgid
    #    si_query_args = newargs
    #    supplierInvoiceQuery.start()
    #    console.log(si_query_args, newargs)

    #_delQueryArgs = (delargs) =>
    #    console.log(si_query_args)
    #    for arg in delargs
    #        if arg != 'org'
    #            delete si_query_args[arg]
    #    supplierInvoiceQuery.start()

    # BLM functions
    createSupplierInvoice = (invoice, callback) =>
        commit.callBlmMethod(
            jsLink,
            'accounting.saveSupplierInvoice',
            [[orgid],[invoice]], (result) =>
                if result.error?
                    console.log(result.error)
                    createStatus = 'failure'
                    alert = {
                        key: 'savefail'
                        contextcolor: 'danger'
                        title: 'Failure!'
                        message: 'Invoice record could not be created. {err}.'
                        messageattrs: {
                            err: utils.get_error_message(result.error)
                        }
                    }
                    renderAlerts([alert])
                else
                    createStatus = 'success'
                    createResult = result.result
                    renderAlerts([], [{key: 'savefail'}])
                callback(createStatus)
                renderApp()
        )

    updateSupplierInvoice = (toid, invoice, callback) =>
        commit.callBlmMethod(
            jsLink,
            'accounting.saveSupplierInvoice',
            [[orgid], [invoice], [toid]], (result) =>
                if result.error?
                    console.log(result.error)
                    updateStatus = 'failure'
                    alert = {
                        key: 'savefail'
                        contextcolor: 'danger'
                        title: 'Failure!'
                        message: 'Failed to save invoice record. {err}.'
                        messageattrs:
                            err: utils.get_error_message(result.error)
                    }
                    renderAlerts([alert])
                else
                    updateStatus = 'success'
                    updateResult = result.result
                    renderAlerts([], [{key: 'savefail'}])
                callback(updateStatus)
                renderApp()
        )

    deleteSupplierInvoice = (siToiList) =>
        commit.callBlmMethod(
            jsLink,
            'accounting.deleteSupplierInvoice',
            [[orgid], siToiList], (result) =>
                if result.error?
                    deleteStatus = 'failure'
                    renderAlerts([{
                        contextcolor: 'danger'
                        title: 'Failure!'
                        message: 'Delete command failed. {err}'
                        messageattrs: {err: result.error.args}
                    }])
                else
                    deleteStatus = 'success'
                    deleteResult = result.result
                    if deleteResult.deleted.length > 0
                        renderAlerts([{
                            contextcolor: 'success'
                            title: 'Success!'
                            message: 'Deleted {del} drafts.'
                            messageattrs: {
                                del: deleteResult.deleted.length,
                                unt: deleteResult.untouched.length
                            }
                        }])
                renderApp()
        )

    proposeRecipients = () =>
        commit.callBlmMethod(
            jsLink,
            'accounting.proposeRecipients',
            [[orgid]], (result) =>
                if result.error?
                    status = 'failure'
                else
                    status = 'success'
                    recipients = result.result
                    renderApp()
        )

    fetchPredictions = (recipient, callback) =>
        commit.callBlmMethod(
            jsLink,
            'accounting.predictSupplierInvoice',
            [[orgid], [recipient]], (result) =>
                if result.error?
                    # Handle failure
                    predictStatus = 'failure'
                else
                    predictStatus = 'success'
                    prediction = result.result
                    callback(prediction)
                renderApp()
        )

     setSIState = (siToiList, newstate, callback) =>
        commit.callBlmMethod(
            jsLink,
            'accounting.setSIState',
            [[orgid], siToiList, [newstate]], (result) =>
                callback()
                if result.error?
                    updateStatus = 'failure'
                    renderAlerts([{
                        contextcolor: 'danger'
                        title: 'Failure!'
                        message: '{err}.'
                        messageattrs: {err: utils.get_error_message(result.error)}
                    }])
                else
                    updateStatus = 'success'
                    updateResult = result.result
                    if updateResult['updated'] > 0
                        renderAlerts([{
                            contextcolor: 'success'
                            title: 'Success!'
                            message: '{mod} of the {sel} selected set to {state}.'
                            messageattrs: {
                                mod: updateResult['updated'],
                                sel: updateResult['selected'],
                                state: newstate
                            }
                        }])
                    if updateResult['complaints'].length > 0
                        renderAlerts([{
                            contextcolor: 'warning'
                            title: 'Warning!'
                            message: 'Some states could not be changed due to the following reasons: {reasons}'
                            messageattrs: {reasons: updateResult['complaints']}
                        }])
        )

     enableSIAutomation = (siToiList, callback) =>

        commit.callBlmMethod(
            jsLink,
            'accounting.requestSIAutomation',
            [[orgid], siToiList], (result) =>
                if result.error?
                    if result.error.args?
                        message = result.error.args[0]
                    else
                        message = result.error
                    renderAlerts([
                        contextcolor: 'danger'
                        title: 'Failure.'
                        message: message
                    ])
                else
                    signRef = result.result[0]
                    renderAuthorization(signRef)
                callback()
        )


     disableSIAutomation = (siToiList, callback) =>
        commit.callBlmMethod(
            jsLink,
            'accounting.disableSIAutomation',
            [[orgid], siToiList], (result) =>
                callback()
                if result.error?
                    if utils.is_permission_error(result.error)
                        renderAlerts([
                            contextcolor: 'danger'
                            title: 'Permission denied.'
                            message: 'You do not have permission to schedule automatic payments.'
                        ])
                    updateStatus = 'failure'
                else
                    updateStatus = 'success'
                    updateResult = result.result
                    if updateResult['updated'] > 0
                        renderAlerts([{
                            contextcolor: 'success'
                            title: 'Success!'
                            message: 'Disabled automated payment for {mod} of the {sel} selected.'
                            messageattrs: {
                                mod: updateResult['updated'],
                                sel: updateResult['selected'],
                            }
                        }])
                    if updateResult['complaints'].length > 0
                        renderAlerts([{
                            contextcolor: 'warning'
                            title: 'Warning!'
                            message: 'Failed to disable automation for the following reasons: {reasons}'
                            messageattrs: {reasons: updateResult['complaints']}
                        }])
        )

    createTransferVerification = (siToiList, callback) =>
        commit.callBlmMethod(
            jsLink,
            'accounting.createTransferVerification',
            [[orgid], siToiList], (result) =>
                callback()
                if result.error?
                    updateStatus = 'failure'
                    renderAlerts([{
                        contextcolor: 'danger'
                        title: 'Failure!'
                        message: '{err}.'
                        messageattrs: {
                            err: utils.get_error_message(result.error)
                        }
                    }])
                else
                    updateStatus = 'success'
                    updateResult = result.result[0]
                    renderAlerts([{
                        contextcolor: 'success'
                        title: 'Success!'
                        message: 'Verification number {vers} created, marking {nacc} invoices as accounted.'
                        messageattrs: {
                                vers: [ver.number for ver in updateResult['verifications']]
                                nacc: updateResult['accounted'].length,
                            }
                    }])
                renderApp()
        )

    generatePlusgiroFile = (siToiList, callback) =>
        commit.callBlmMethod(
            jsLink,
            'accounting.generatePlusgiroFile',
            [[orgid], siToiList], (result) =>
                if result.error?
                    resultStatus = 'failure'
                    resultData = result.error.args
                else
                    resultStatus = 'success'
                    resultData = result.result
                callback(resultStatus, resultData)
        )

    generateLBin = (siToiList, callback) =>
        # Developer function, disable for production.
        # Writes BGC file to /tmp/ on developer machine.
        commit.callBlmMethod(
            jsLink,
            'accounting.writeBankgiroTransferOrder',
            [[orgid], siToiList], (result) =>
                if result.error?
                    resultStatus = 'failure'
                    resultData = {}
                else
                    resultStatus = 'success'
                    resultData = result.result
                callback(resultStatus, resultData)
        )

    saveSettings = (settings, callback) =>
        commit.callBlmMethod(
            jsLink,
            'accounting.updateSupplierInvoiceProvider',
            [[orgid], [settings]], (result) =>
                if result.error?
                    saveProviderStatus = 'failure'
                    renderAlerts([{
                        contextcolor: 'danger'
                        title: 'Failure!'
                        message: 'Unable to save settings.'
                    }])
                else
                    saveProviderStatus = 'success'
                    saveProviderResult = result.result
                    renderAlerts([{
                        contextcolor: 'success'
                        title: 'Success!'
                        key: 'savesuccess'
                        message: 'Settings saved.'
                    }])
                callback()
                renderApp()
            )

    uploadInvoiceImage = (sitoid, file, filedata) =>
        images = []
        image = {
            name: file.name,
            type: file.type,
            data: btoa(filedata),
        }
        images.push(image)
        commit.callBlmMethod(
            jsLink,
            'accounting.uploadInvoiceImage',
            [[orgid], [sitoid], images], (result) =>
                if result.error?
                    renderAlerts([{
                        contextcolor: 'danger'
                        title: 'Failure!'
                        message: 'Unable to upload image.'
                    }])
            )
    removeInvoiceImage = (imagetoid) =>
        commit.callBlmMethod(
            jsLink,
            'accounting.removeInvoiceImage',
            [[imagetoid]], (result) =>
                if result.error?
                    renderAlerts([{
                        contextcolor: 'danger'
                        title: 'Failure!'
                        message: 'Unable to remove image.'
                    }])
            )
    renderApp = () ->
        ReactDOM.render(
            <div className='row'>
                <div className='col'>
                    <Main
                        org={orgid}
                        fetchPredictions={fetchPredictions}
                        createSupplierInvoice={createSupplierInvoice}
                        updateSupplierInvoice={updateSupplierInvoice}
                        deleteSupplierInvoice={deleteSupplierInvoice}
                        createTransferVerification={createTransferVerification}
                        setSIState={setSIState}
                        enableSIAutomation={enableSIAutomation}
                        disableSIAutomation={disableSIAutomation}
                        generatePlusgiroFile={generatePlusgiroFile}
                        generateLBin={generateLBin}
                        uploadInvoiceImage={uploadInvoiceImage}
                        removeInvoiceImage={removeInvoiceImage}
                        setQueryDates={setQueryDates}
                        supplierInvoiceList={supplierInvoiceQuery.result}
                        supplierInvoiceTData={supplierInvoiceQuery.toiData}
                        supplierInvoiceQuery={supplierInvoiceQuery}
                        verificationsWatcher={verificationsWatcher}
                        transactionsWatcher={transactionsWatcher}
                        accountsQuery={accountsQuery}
                        seriesQuery={seriesQuery}
                        providerQuery={providerQuery}
                        imageQuery={imageQuery}
                        recipients={recipients}
                        renderAlerts={renderAlerts}
                        />
                    </div>
            </div>,
            document.getElementById('maintarget')
        )

    renderAlerts = (alerts, dismiss) ->
        ReactDOM.render(
            <div className='row'>
                <div className='col'>
                    <Alerts
                        alerts={alerts}
                        dismiss={dismiss}
                        />
                </div>
            </div>,
            document.getElementById('alertstarget')
        )

    renderSettings = () ->
        ReactDOM.render(
            <div className='row'>
                <div className='col'>
                    <Settings
                        providerQuery={providerQuery}
                        accountsQuery={accountsQuery}
                        seriesQuery={seriesQuery}
                        saveSettings={saveSettings}
                        />
                </div>
            </div>,
            document.getElementById('settingstarget')
        )
    
    renderAuthorization = (signRef) ->
        unmountAuthorizationDialog = ->
            ReactDOM.render(
                <div></div>,
                document.getElementById('authorizetarget')
            )

        ReactDOM.render(
            <div className='row'>
                <div className='col'>
                    <Authorize.AuthorizationWidget
                        signRef=signRef
                        jsLink=jsLink
                        unmount=unmountAuthorizationDialog
                    />
                </div>
            </div>,
            document.getElementById('authorizetarget')
        )
        $('#authorizationModal').modal('show')

    signals.connect(supplierInvoiceQuery, 'update', () ->
        renderApp()
        imageQuery.push({supplierInvoice: @result})
        imageQuery.start()
        proposeRecipients()
    )

    signals.connect(accountingYearQuery, 'update', () ->
        org = @result[0]
        year = @toiData[org]['current_accounting'][0]
        accountsQuery.push({'accounting': year})
        accountsQuery.start()
        seriesQuery.push({'accounting': year})
        seriesQuery.start()
    )

    signals.connect(accountsQuery, 'update', () ->
        renderSettings()
        renderApp()
    )
    signals.connect(seriesQuery, 'update', ->
        renderSettings()
        renderApp()
    )
    signals.connect(providerQuery, 'update', ->
        renderSettings()
        renderApp()
        renderAlerts([])
        if (providerQuery.result? and providerQuery.result.length < 1)
            renderAlerts([{
                key: 'missingsettings'
                contextcolor: 'info'
                dismissable: false
                title: 'Welcome!'
                message: 'You have not yet configured the Accounts payable module. To do so, click View -> Settings.'
            }])
        if (providerQuery.result? and providerQuery.result.length > 0)
            # Dismiss alert
            renderAlerts([], [{
                key: 'missingsettings'
            }])
    )
    signals.connect(imageQuery, 'update', ->
        renderApp()
    )

    jsLink.ready.then(->
        accountingYearQuery.start()
        providerQuery.start()
        supplierInvoiceQuery.start()
    )
    renderApp()
)
