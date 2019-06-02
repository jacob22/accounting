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
    classnames,
    ) ->

    require('react-bootstrap-typeahead/css/Typeahead.css')

    _ = gettext.gettext

    class Invoice extends React.Component
        @defaultProps:
            'accounted': false,
            'invoiceState': '',
            'automated': false
            'recipient': '',
            'invoiceType': 'debit',
            'amount': 0,
            'invoiceDate': '',
            'transferDate': '',
            'dueDate': '',
            'transferMethod': '',
            'pgnum': '',
            'bgnum': '',
            'bankaccount': '',
            'bankclearing': '',
            'invoiceIdentifierType': '',
            'ocr': '',
            'invoiceNumber': '',
            'message': '',
            'selected': [],
            'recipients': [''],
            'images': []

        constructor: (props) ->
            super(props)
            accounted = props.accounted
            invoiceState = props.invoiceState
            recipient = props.recipient
            invoiceType = props.invoiceType
            amount = props.amount

            invoiceDate = props.invoiceDate
            transferDate = props.transferDate
            dueDate = props.dueDate

            transferMethod=props.transferMethod
            bgnum = props.bgnum
            pgnum = props.pgnum
            bankaccount = props.bankaccount
            bankclearing = props.bankclearing

            invoiceIdentifierType = props.invoiceIdentifierType
            ocr = props.ocr
            invoiceNumber = props.invoiceNumber
            message = props.message

            recipients = props.recipients

            @state = {
                'accounted': accounted,
                'invoiceState': invoiceState,
                'recipient': recipient,
                'invoiceType': invoiceType,
                'amount': amount * 100,
                'invoiceDate': invoiceDate,
                'transferDate': transferDate,
                'dueDate': dueDate,
                'transferMethod': transferMethod,
                'bgnum': bgnum,
                'pgnum': pgnum,
                'bankaccount': bankaccount,
                'bankclearing': bankclearing,
                'invoiceIdentifierType': invoiceIdentifierType,
                'ocr': ocr,
                'invoiceNumber': invoiceNumber,
                'message': message,
                'recipients': recipients,
                'enableSubmit': false,
                'expandCollapse': false,
                'regVerificationLines': null,
                'regVerificationVersion': null,
                'dirty': false,
                'saving': false,
            }

            @registrationVerAggr = new VerDataAggregator(
                @props.registrationVerification,
                @props.verificationsWatcher,
                @props.transactionsWatcher,
                @props.accountsQuery,
                @props.seriesQuery
            )
            @registrationVerAggr.start()
            @transferVerAggr = new VerDataAggregator(
                @props.transferVerification,
                @props.verificationsWatcher,
                @props.transactionsWatcher,
                @props.accountsQuery,
                @props.seriesQuery
            )
            @transferVerAggr.start()


        componentWillReceiveProps: (nextProps) =>
            # If value has not been changed by user, get new value from the BLM.
            # Except some values we want from the server even if we have a dirty state in the form.

            if @state.accounted == @props.accounted
                @setState(accounted: nextProps.accounted)

            # Always accept new invoiceState from server
            if nextProps.invoiceState
                @setState(invoiceState: nextProps.invoiceState)

            if nextProps.recipient != @props.recipient == @state.recipient
                @setState(
                    recipient: nextProps.recipient
                )

            if @state.invoiceType == @props.invoiceType != nextProps.invoiceType
                @setState(invoiceType: nextProps.invoiceType)

            if @state.amount == @props.amount * 100 != nextProps.amount * 100
                @setState(amount: nextProps.amount * 100)


            if @state.invoiceDate == @props.invoiceDate != nextProps.invoiceDate
                @setState(invoiceDate: nextProps.invoiceDate)

            if @state.transferDate == @props.transferDate != nextProps.transferDate
                @setState(transferDate: nextProps.transferDate)

            if @state.dueDate == @props.dueDate != nextProps.dueDate
                @setState(dueDate: nextProps.dueDate)


            # Transfer method
            if @state.transferMethod == @props.transferMethod != nextProps.transferMethod
                @setState(transferMethod: nextProps.transferMethod)

            if @state.bgnum == @props.bgnum != nextProps.bgnum
                @setState(bgnum: nextProps.bgnum)

            if @state.pgnum == @props.pgnum != nextProps.pgnum
                @setState(pgnum: nextProps.pgnum)

            if @state.bankaccount == @props.bankaccount != nextProps.bankaccount
                @setState(bankaccount: nextProps.bankaccount)

            if @state.bankclearing == @props.bankclearing != nextProps.bankclearing
                @setState(bankclearing: nextProps.bankclearing)


            # Identifier
            if @state.invoiceIdentifierType == @props.invoiceIdentifierType != nextProps.invoiceIdentifierType
                @setState(invoiceIdentifierType: nextProps.invoiceIdentifierType)

            if @state.ocr == @props.ocr != nextProps.ocr
                @setState(ocr: nextProps.ocr)

            if @state.invoiceNumber == @props.invoiceNumber != nextProps.invoiceNumber
                @setState(invoiceNumber: nextProps.invoiceNumber)

            if @state.message == @props.message != nextProps.message
                @setState(message: nextProps.message)

            if @props.recipients != nextProps.recipients
                recipients = nextProps.recipients
                @setState(recipients: recipients)

            if nextProps.registrationVerification != @props.registrationVerification
                @registrationVerAggr.stop()
                @registrationVerAggr = new VerDataAggregator(
                    nextProps.registrationVerification,
                    nextProps.verificationsWatcher,
                    nextProps.transactionsWatcher,
                    nextProps.accountsQuery,
                    nextProps.seriesQuery
                )
            if nextProps.transferVerification != @props.transferVerification
                @transferVerAggr.stop()
                @transferVerAggr = new VerDataAggregator(
                    nextProps.transferVerification,
                    nextProps.verificationsWatcher,
                    nextProps.transactionsWatcher,
                    nextProps.accountsQuery,
                    nextProps.seriesQuery
                )

        _resetForm: () =>
            @setState({
                'dirty': false
                'accounted': @props.accounted,
                'invoiceState': @props.invoiceState,
                'recipient': @props.recipient,
                'invoiceType': @props.invoiceType,
                'amount': @props.amount * 100,
                'invoiceDate': @props.invoiceDate,
                'transferDate': @props.transferDate,
                'dueDate': @props.dueDate,
                'transferMethod': @props.transferMethod,
                'bgnum': @props.bgnum,
                'pgnum': @props.pgnum,
                'bankaccount': @props.bankaccount,
                'bankclearing': @props.bankclearing,
                'invoiceIdentifierType': @props.invoiceIdentifierType,
                'ocr': @props.ocr,
                'invoiceNumber': @props.invoiceNumber,
                'message': @props.message,
                'enableSubmit': false,
                'regVerificationLines': null,
                'regVerificationVersion': null,
                })
            @registrationVerAggr.stop()
            @registrationVerAggr.start()
            @transferVerAggr.stop()
            @transferVerAggr.start()

        _runDebugger: () =>
            debugger

        _checkPaid: () =>
            if @state.invoiceState in ['sent', 'paid']
                return true
            else
                return false

        _readOnly: () =>
            if @state.invoiceState in ['sent', 'paid'] or @props.automated or @props.accounted
                return true
            else
                return false

        _enableSubmit: (newvalues) =>
            if not @state.dirty
                return false
            # This approach checks state directly after setState, which is flawed.
            if (@state.recipient? and @state.transferMethod? and @state.amount > 0 and @state.invoiceIdentifierType?)
                if not @state.recipient.length > 0
                    return false
                if not @state[@state.invoiceIdentifierType]
                    return false
                if not @state[@state.transferMethod]
                    return false
                # things seem ok so return true
                return true
            else
                return false

        _updateValue: (key, value) =>
            if @state[key] != value
                newstate = {dirty: true}
                newstate[key] = value
                @setState(newstate)
                @props.deSelect(@props.toid)
                console.log(key, value)

        _updateRecipient: (recipient) =>
            @_updateValue('recipient', recipient)

        _updateRecipientSelect: (selected) =>
            if selected.length > 0
                if selected[0].label?
                    # Mouse click on item
                    recipient = selected[0].label
                else
                    # Keyboard select
                    recipient = selected[0]
                @_updateValue('recipient', recipient)
                @_fetchPredictions(recipient)

        _updateInvoiceType: (event) =>
            @_updateValue('invoiceType', event.target.value)

        _updateTransferMethod: (event) =>
            @_updateValue('transferMethod', event.target.value)

        _updateBgnum: (event) =>
            @_updateValue('bgnum', utils.parseBgnum(event.target.value))

        _updatePgnum: (event) =>
            @_updateValue('pgnum', utils.parseBgnum(event.target.value))

        _updateBankaccount: (event) =>
            @_updateValue('bankaccount', utils.parseBankaccount(event.target.value))

        _updateBankclearing: (event) =>
            @_updateValue('bankclearing', utils.parseClearing(event.target.value))

        _updateAmount: (amount) =>
            if amount is null
                amount = 0
            @_updateValue('amount', amount)

        _updateInvoiceDate: (event) =>
            @_updateValue('invoiceDate', event.target.value)

        _updateTransferDate: (event) =>
            @_updateValue('transferDate', event.target.value)

        _updateDueDate: (event) =>
            @_updateValue('dueDate', event.target.value)

        _updateInvoiceIdentifierType: (event) =>
            @_updateValue('invoiceIdentifierType', event.target.value)

        _updateOcr: (event) =>
            @_updateValue('ocr', utils.filterDigits(event.target.value))

        _updateInvoiceNumber: (event) =>
            @_updateValue('invoiceNumber', event.target.value)

        _updateMessage: (event) =>
            @_updateValue('message', event.target.value)

        _updateRegistrationVerification: (verId, dirty, lines, version) =>
            if dirty
                @setState(
                    regVerificationLines: lines
                    regVerificationVersion: version
                    dirty: true
                )
            else
                @setState(
                    regVerificationLines: null
                    regVerificationVersion: null
                )
            @props.deSelect(@props.toid)

        _updateToggleSent: (event) =>
            old = @state.invoiceState
            if old == 'registered'
                @setState(invoiceState: 'sent', dirty: true)
            else if old == 'sent'
                @setState(invoiceState: 'registered', dirty: true)
            else if old == 'paid'
                @setState(invoiceState: 'registered', dirty: true)
            @props.deSelect(@props.toid)


        _updateTogglePaid: (event) =>
            old = @state.invoiceState
            if old == 'registered'
                @setState(invoiceState: 'paid', dirty: true)
            else if old == 'sent'
                @setState(invoiceState: 'paid', dirty: true)
            else if old == 'paid'
                @setState(invoiceState: 'sent', dirty: true)
            @props.deSelect(@props.toid)

        _enableAutomaticPayment: (event) =>
            callback = (saveResult) =>
                if saveResult == 'success'
                    @props.enableAutomation([@props.toid])
                @saveDone(saveResult)

            if @_checkAutomation()
                if @state.dirty
                    @saveForm(callback)
                else
                    @props.enableAutomation([@props.toid])

        _disableAutomaticPayment: (event) =>
            @props.disableAutomation([@props.toid])

        _generateTransferVerification: (event) =>
            callback = (saveResult) =>
                if saveResult == 'success'
                    @props.createTransferVerification([@props.toid])
                @saveDone(saveResult)

            if @state.invoiceState == 'paid' and not @props.accounted and not @props.automated
                if @state.dirty
                    @saveForm(callback)
                else
                    @props.createTransferVerification([@props.toid])

        _isValidDate: (datestring) =>
            date_re = /\d{4}-\d{2}-\d{2}/
            return (datestring.match(date_re) and moment(datestring).isValid())

        _isValidDateOrEmpty: (datestring) =>
            return datestring == '' or @_isValidDate(datestring)

        _isBankday: (date) =>
            if not moment(date).isValid()
                return false
            dow = moment(date).isoWeekday()
            return dow <= 5

        _isWeekday: (date) =>
            if not moment(date).isValid()
                return false
            dow = moment(date).isoWeekday()
            return dow <= 5

        _checkDates: () =>
            date_re = /\d{4}-\d{2}-\d{2}/

            if @state.invoiceDate?
                if not @state.invoiceDate.match(@date_re)
                    return false
                if not moment(@state.invoiceDate).isValid()
                    console.log('Invalid invoice date.')
                    return false

            if @state.transferDate?
                if not @state.transferDate.match(@date_re)
                    return false
                if not moment(@state.transferDate).isValid()
                    console.log('Invalid transfer date.')
                    return false

            if @state.dueDate?
                if not @state.dueDate.match(@date_re)
                    return false
                if not moment(@state.dueDate).isValid()
                    console.log('Invalid due date.')
                    return false

            if moment(@state.transferDate).isBefore(@state.invoiceDate)
                console.log('Trans before inv date.')
                return false

            if moment(@state.dueDate).isBefore(@state.invoiceDate)
                console.log('Due before inv date.')
                return false

            if moment(@state.transferDate).isSameOrBefore(@state.dueDate) and @_isBankday(@state.transferDate)
                return true
            else
                console.log('Transfer date not valid.')
                return false

        _checkOverdue: () =>
            if @state.invoiceState == 'paid'
                overdue = false
            else
                # Check dates
                overdue = (
                    moment(moment().format('YYYY-MM-DD')).isAfter(moment(@state.transferDate)) or
                    moment(moment().format('YYYY-MM-DD')).isAfter(moment(@state.dueDate))
                )
            return overdue

        _realisticTransferDate: () =>
            if @_checkOverdue() or not moment(@state.transferDate).isValid()
                return 'as soon as possible'
            else
                if @_isBankday(@state.transferDate)
                    return @props.transferDate
                else
                    return @props.transferDate

        _checkDueToday: () =>
            if moment().format('YYYY-MM-DD') == @state.transferDate
                return true
            else
                return false

        _checkAutomation: () =>
            #if not @props.automationProviderQuery.result[0]?
            #    return false

            # Dont care about date, if none given, transfer ASAP.
            # if not moment(@state.transferDate).isValid()
            #     console.log('Invalid transfer date.')
            #     return false

            # if not @_isBankday(@state.transferDate)
            #     console.log('Improper transfer date.')
            #     return false

            # if @_checkOverdue()
            #     console.log('transfer date too soon.')
            #     return false

            # if @_checkDueToday() and moment().isAfter(moment(moment().format('YYYY-MM-DD') + 'T16:00:00Z'))
            #     console.log('Too late for transfer today.')
            #     return false

            if not @state.transferMethod in ['bgnum', 'pgnum', 'bankaccount']
                console.log('transferMethod problem.')
                return false

            if not @state[@state.transferMethod].length > 0
                console.log('transferMethod problem.')
                return false

            if not @state.recipient.length > 0
                console.log('No recipient.')
                return false

            if not @state.invoiceIdentifierType in ['ocr', 'invoiceNumber', 'message']
                console.log('identifier problem.')
                return false

            if not @state[@state.invoiceIdentifierType].length > 0
                console.log('identifier problem.')
                return false

            if not @state.invoiceState == 'registered'
                return false

            # Everything seems ok
            return true

        _clearRejected: () =>
            @props.setRegistered([@props.toid])

        _toggleSelected: (event) =>
            event.stopPropagation()
            #console.log(event.target.value, event.target.checked)
            if not @state.dirty
                @props.toggleSelected(event)

        _deSelect: (event) =>
            event.stopPropagation()
            @props.deSelect(@props.toid)

        _select: (event) =>
            event.stopPropagation()
            @props.select(@props.toid)

        _toggleExpanded: (event) =>
            event.stopPropagation()
            if @state.expandCollapse
                @_hideCollapse()
            else
                @_showCollapse()

        _hideCollapse: () =>
            wid=@props.toid
            collapseId = 'collapse-' + wid
            collapseCssId = '#collapse-' + wid
            # Set listener for when collapse is hidden to
            # remove the form from the DOM (re-render triggered by setState).
            $(collapseCssId).on('hidden.bs.collapse', () =>
                @setState(expandCollapse: false)
            )
            # Hide
            $(collapseCssId).collapse('hide')

        _showCollapse: () =>
            @setState(expandCollapse: true)
            # After render is done componentDidUpdate will
            # trigger the expand animation.

        componentDidUpdate: (prevProps, prevState) =>
            if prevState.expandCollapse is false and @state.expandCollapse is true
                wid = @props.toid
                collapseCssId = '#collapse-' + wid
                # Begin expand animation
                $(collapseCssId).collapse('show')

        componentDidMount: () =>
            if @props.expand
                @_showCollapse()

        _fetchPredictions: (recipient) =>
            if not recipient
                return
            callback = (prediction) =>
                #Fill in the prediction
                console.log('prediction', prediction)
                for key, value of prediction[0]
                    if key == 'amount'
                        value = value * 100
                    @_updateValue(key, value)
            @props.fetchPredictions(recipient, callback)

        _trimStrings: () =>
            trimmed = {}
            for key in [
                'recipient',
                'invoiceDate',
                'transferDate',
                'dueDate',
                'bgnum',
                'pgnum',
                'bankaccount',
                'bankclearing',
                'ocr',
                'invoiceNumber',
                'message']
                trimmed[key] = @state[key].trim()
            @setState(trimmed)

        saveDone: (saveResult) =>
            @setState(saving: false)
            if saveResult == 'success'
                @setState(dirty: false)

        handleSubmit: () =>
            @saveForm(@saveDone)

        saveForm: (callback) =>
            @_trimStrings()
            @setState(saving: true)
            invoicedata = {
                'invoiceState':            @state.invoiceState,
                'recipient':               @state.recipient,
                'invoiceType':             @state.invoiceType,
                'amount':                  @state.amount,
                'invoiceDate':             @state.invoiceDate,
                'transferDate':            @state.transferDate,
                'dueDate':                 @state.dueDate,
                'transferMethod':          @state.transferMethod,
                'bgnum':                   @state.bgnum,
                'pgnum':                   @state.pgnum,
                'bankaccount':             @state.bankaccount,
                'bankclearing':            @state.bankclearing,
                'invoiceIdentifierType':   @state.invoiceIdentifierType,
                'ocr':                     @state.ocr,
                'invoiceNumber':           @state.invoiceNumber,
                'message':                 @state.message,
                'regVerificationLines':    @state.regVerificationLines,
                'regVerificationVersion':  @state.regVerificationVersion,
            }
            if @props.toid in @props.supplierInvoiceList
                # Entry in DB, update entry
                @props.updateSupplierInvoice(@props.toid, invoicedata, callback)
            else
                # Not in database, create new
                @props.createSupplierInvoice(@props.toid, invoicedata)

        render: () ->
            wid=@props.toid
            collapseId = 'collapse-' + wid
            collapseCssId = '#' + collapseId

            selected = @props.toid of @props.selected

            # Status badges
            if @state.invoiceState == ''
                stateBadge = <span className='badge badge-info'>{_('New')}</span>
            if @state.invoiceState == 'incomplete'
                stateBadge = <span className='badge badge-secondary'>{_('Draft')}</span>
            if @state.invoiceState == 'registered' and @props.automated == false
                stateBadge = <span className='badge badge-secondary'>{_('Registered')}</span>
            if @state.invoiceState == 'registered' and @props.automated == true
                stateBadge = <span className='badge badge-secondary'>{_('Scheduled')}</span>
            if @state.invoiceState == 'sent' and @props.automated == false
                stateBadge = <span className='badge badge-secondary'>{_('Sent')}</span>
            if @state.invoiceState == 'sent' and @props.automated == true
                stateBadge = <span className='badge badge-secondary'>{_('Sent')}</span>
            if @state.invoiceState == 'paid' and @state.accounted == false
                stateBadge = <span className='badge badge-success'>{_('Paid')}</span>
            if @state.invoiceState == 'paid' and @state.accounted == true
                stateBadge = <span className='badge badge-secondary'>{_('Paid')}</span>
            if @state.invoiceState == 'rejected'
                stateBadge = <span className='badge badge-danger'>{_('Rejected')}</span>

            # Automation badge
            if @props.automated == true
                automatedBadge = <span className='badge badge-secondary'>{_('Automated')}</span>
            else
                automatedBadge = null

            # Date badges
            nonBankDayBadge = null
            if moment(@state.transferDate).isValid() and not @_isWeekday(@state.transferDate)
                nonBankDayBadge = <span className='badge badge-danger'>{_('Not a banking day')}</span>
            lateTransferDateBadge1 = null
            if @state.invoiceState != 'paid'
                if moment(@state.transferDate).isAfter(moment(@state.dueDate))
                    lateTransferDateBadge1 = <span className='badge badge-danger'>{_('Overdue date')}</span>
            lateTransferDateBadge2 = null
            if @state.invoiceState != 'paid'
                if moment(@state.transferDate).isBefore(moment(moment().format('YYYY-MM-DD')))
                    lateTransferDateBadge2 = <span className='badge badge-warning'>{_('Past date')}</span>

            if @state.invoiceState == 'paid'
                dueBadge = null
            else
                if @_checkOverdue()
                    dueBadge = <span className='badge badge-danger'>{_('Overdue')}</span>
                else if @_checkDueToday()
                    dueBadge = <span className='badge badge-warning'>{_('Due')}</span>
                else
                    dueBadge = null

            # Misc. badges
            if @state.accounted == true
                accountedBadge = <span className='badge badge-secondary'>{_('Accounted')}</span>
            else
                accountedBadge = null

            if @state.dirty
                dirtyBadge = <span className='badge badge-warning'>{_('Unsaved changes')}</span>
            else
                dirtyBadge = null

            if @state.invoiceType == 'credit'
                creditBadge = <span className='badge badge-secondary'>{_('Credit')}</span>
            else
                creditBadge = null

            if @props.images.length > 0
                attacheIcons = []
                for image in @props.images
                    attacheIcons.push(<i key=image className="fa fa-paperclip" aria-hidden="true"></i>)
            else
                attacheIcons = null

            headerRef = null
            if @state.invoiceIdentifierType == 'ocr'
                headerRef = @state.ocr
            else if @state.invoiceIdentifierType == 'invoiceNumber'
                headerRef = @state.invoiceNumber
            else if @state.invoiceIdentifierType == 'message'
                if @state.message.length < 50
                    headerRef = @state.message
                else
                    headerRef = @state.message[..50] + '...'

            # Remove-InvoiceImage-function generator-function
            generateRemover = (imagetoid) =>
                # Return a function with a dereferenced toid (= a string),
                # rather than a reference to whatever variable imagetoid has been
                # assigned when the button is clicked. 
                return () =>
                     @props.removeInvoiceImage(imagetoid)

            yieldImageFilename = (imagetoid) =>
                imagefilename = null
                if @props.imageQuery?
                    if @props.imageQuery.result.length > 0
                        if imagetoid of @props.imageQuery.toiData
                            imagefilename = @props.imageQuery.toiData[imagetoid].filename[0]

            headline =
                <div
                    className="card-header"
                    role="button"
                    id={'heading' + wid}
                    onClick={@_toggleExpanded}
                    >
                    <div className='row'>
                        <div className='col-auto px-3'>
                            {<input
                                id={"selected-checkbox-y-"+wid}
                                type="checkbox"
                                value={@props.toid}
                                checked={true}
                                onClick={@_deSelect}
                                onChange={=>}
                                aria-label="Mark invoice selected."
                                /> if selected}
                            {<input
                                id={"selected-checkbox-n-"+wid}
                                type="checkbox"
                                checked={false}
                                value={@props.toid}
                                onClick={@_select}
                                onChange={=>}
                                disabled={@state.dirty or @state.accounted}
                                aria-label="Mark invoice selected."
                                /> if not selected}
                        </div>
                        <div className='col'>
                            {stateBadge} {accountedBadge} {automatedBadge} {dueBadge} {dirtyBadge} {attacheIcons}
                        </div>
                        <div className='col'>
                            <span className={classnames({
                                'text-warning': @_checkDueToday() and @state.invoiceState != 'paid',
                                'text-danger': @_checkOverdue() and @state.invoiceState != 'paid',
                                })}>{@state.transferDate}{'ASAP' if @props.automated and not @state.transferDate}</span> {nonBankDayBadge}
                            </div>
                        <div className='col text-center'>{@state.recipient}</div>
                        <div className='col text-center'><small>{headerRef}</small></div>
                        <div className='col text-right'>{creditBadge} {utils.formatCurrency(@state.amount)}</div>
                    </div>
                </div>

            # Unexpanded dummy body
            if not @state.expandCollapse
                expandbody =
                    <div
                        className={classnames({
                            collapse: true
                        })}
                        role="tabpanel"
                        >
                    </div>

            # Expanded body
            if @state.expandCollapse
                expandbody =
                <div
                    id={collapseId}
                    className={classnames({
                        collapse: true
                    })}
                    role="tabpanel"
                    >
                    <div className="card-body">
                        <div className="d-flex flex-column">
                            <form className='form'>
                                <fieldset disabled={@_readOnly()}>
                                    <div className="d-flex row form-group">
                                        <label htmlFor={"text-typeahead-recipient-" + wid}
                                               className="col-2 col-form-label">
                                            {_('Recipient name')}
                                        </label>
                                        <div className="col-10">
                                            <Typeahead.Typeahead
                                                id={"text-typeahead-recipient-" + wid}
                                                allowNew={true}
                                                minLength={2}
                                                newSelectionPrefix=' '
                                                onInputChange={@_updateRecipient}
                                                onChange={@_updateRecipientSelect}
                                                options={@state.recipients}
                                                selected={[@state.recipient]}
                                                disabled={@_readOnly()}
                                                />
                                        </div>
                                    </div>
                                    <div className="d-flex row form-group">
                                            <label className="col-2 col-form-label">
                                                {_('Invoice type')}
                                            </label>
                                        <div className='col'>
                                            <label className="form-check-label col-form-label"
                                                   htmlFor={'radio-debit-' + wid}>
                                                <input className="form-check-input"
                                                       type="radio"
                                                       id={"radio-debit-" + wid}
                                                       name={"radio-type-" + wid}
                                                       value={"debit"}
                                                       checked={@state.invoiceType == 'debit'}
                                                       onChange={@_updateInvoiceType}
                                                       readOnly={@_readOnly()}
                                                       /> {_('Debit')}
                                            </label>
                                        </div>
                                        <div className='col'>
                                            <label className="form-check-label col-form-label"
                                                   htmlFor={'radio-credit-' + wid}>
                                                <input className="form-check-input"
                                                       type="radio"
                                                       id={"radio-credit-" + wid}
                                                       name={"radio-type-" + wid}
                                                       value={"credit"}
                                                       checked={@state.invoiceType == 'credit'}
                                                       onChange={@_updateInvoiceType}
                                                       readOnly={@_readOnly()}
                                                       /> {_('Credit')}
                                            </label>
                                        </div>
                                        {<div className='col text-right'><button className='btn' onClick={@_runDebugger}></button></div> if false}
                                    </div>
                                    <div className="form-group row align-items-center">
                                        <label htmlFor={"amount-input-" + wid}
                                               className="col-2 col-form-label">
                                            {_('Amount')}
                                        </label>
                                        <div className="col">
                                            <Amount
                                                value={@state.amount}
                                                onUpdate={@_updateAmount}
                                                id={"amount-input-" + wid}
                                                readOnly={@_readOnly()}
                                                />
                                        </div>
                                    </div>
                                    { ->
                                                # TRANSFER METHOD
                                    }
                                    <div className="d-flex row form-group">
                                        <div className='col-2 d-flex align-items-center'>
                                            <label className="form-check col-form-label">
                                                {_('Transfer method')}
                                            </label>
                                        </div>
                                        <div className='col'>
                                            <div className='row'>
                                                <div className='col'>
                                                    <label className="form-check-label col-form-label-sm"
                                                           htmlFor={'radio-bankgiro-' + wid}>
                                                        <input className="form-check-input" type="radio"
                                                               id={"radio-bankgiro-" + wid}
                                                               name={"radio-transferMethod-" + wid}
                                                               value={"bgnum"}
                                                               checked={@state.transferMethod == 'bgnum'}
                                                               onChange={@_updateTransferMethod}
                                                               readOnly={@_readOnly()}
                                                               /> {_('Bankgiro')}
                                                    </label>
                                                </div>
                                                <div className='col'>
                                                    <label className="form-check-label col-form-label-sm"
                                                           htmlFor={'radio-plusgiro-' + wid}>
                                                        <input className="form-check-input" type="radio"
                                                               id={"radio-plusgiro-" + wid}
                                                               name={"radio-transferMethod-" + wid}
                                                               value={"pgnum"}
                                                               checked={@state.transferMethod == 'pgnum'}
                                                               onChange={@_updateTransferMethod}
                                                               readOnly={@_readOnly()}
                                                               /> {_('Plusgiro')}
                                                    </label>
                                                </div>
                                                <div className='col'>
                                                    <label className="form-check-label col-form-label-sm"
                                                           htmlFor={'radio-bankaccount-' + wid}>
                                                        <input className="form-check-input" type="radio"
                                                               id={"radio-bankaccount-" + wid}
                                                               name={"radio-transferMethod-" + wid}
                                                               value={"bankaccount"}
                                                               checked={@state.transferMethod == 'bankaccount'}
                                                               onChange={@_updateTransferMethod}
                                                               readOnly={@_readOnly()}
                                                               /> {_('Bank account number')}
                                                    </label>
                                                </div>
                                            </div>
                                            <div className='row'>
                                                {<div className="col">
                                                    <input
                                                        type="text"
                                                        id={"bgnum-" + wid}
                                                        className={classnames(
                                                            'form-control': true
                                                            'form-control-sm': true
                                                            'is-invalid': @state.bgnumInvalid
                                                        )}
                                                        value={utils.formatBgnum(@state.bgnum)}
                                                        onChange={@_updateBgnum}
                                                        onBlur={=> @setState(bgnumInvalid: @state.bgnum and not utils.luhn_check(utils.parseBgnum(@state.bgnum)))}
                                                        readOnly={@_readOnly()}
                                                        />
                                                     <div className='invalid-feedback'>
                                                        {_('Incorrect Luhn checksum.')}
                                                     </div>
                                                </div> if @state.transferMethod == 'bgnum'}
                                                {<div className="col">
                                                    <input
                                                        type="text"
                                                        id={"pgnum-" + wid}
                                                        className={classnames(
                                                            'form-control': true
                                                            'form-control-sm': true
                                                            'is-invalid': @state.pgnumInvalid
                                                        )}
                                                        value={utils.formatPgnum(@state.pgnum)}
                                                        onChange={@_updatePgnum}
                                                        onBlur={=> @setState(pgnumInvalid: @state.pgnum and not utils.luhn_check(utils.parsePgnum(@state.pgnum)))}
                                                        readOnly={@_readOnly()}
                                                        />
                                                    <div className='invalid-feedback'>
                                                        {_('Incorrect Luhn checksum.')}
                                                    </div>
                                                </div> if @state.transferMethod == 'pgnum'}
                                                {<div className="col">
                                                    <div className='row'>
                                                        <div className='col-3 input-group pr-1'>
                                                            <span
                                                                className="input-group-addon form-control-sm"
                                                                id={"clearingnr"+wid}
                                                                >
                                                                {_('Clearing')}
                                                            </span>
                                                            <input className="form-control form-control-sm"
                                                                type="text"
                                                                id={"bankaccount-clearing" + wid}
                                                                aria-describedby={"clearinr"+wid}
                                                                value={utils.formatClearing(@state.bankclearing)}
                                                                onChange={@_updateBankclearing}
                                                                readOnly={@_readOnly()}
                                                                />
                                                        </div>
                                                        <div className='col input-group pl-0'>
                                                            <span
                                                                className="input-group-addon form-control-sm"
                                                                id={"clearingnr"+wid}
                                                                >
                                                                {_('Account')}
                                                            </span>
                                                            <input className="form-control form-control-sm"
                                                                type="text"
                                                                id={"bankaccount-bnum" + wid}
                                                                value={@state.bankaccount}
                                                                onChange={@_updateBankaccount}
                                                                readOnly={@_readOnly()}
                                                                />
                                                        </div>
                                                    </div>
                                                </div> if @state.transferMethod == 'bankaccount'}
                                                {<div className="col">
                                                    <input className="form-control form-control-sm"
                                                            type="text"
                                                            id={"placeholder-method-" + wid}
                                                            disabled={true}
                                                            readOnly={@_readOnly()}
                                                            /> 
                                                </div> if @state.transferMethod not in ['bgnum', 'pgnum', 'bankaccount']}
                                            </div>
                                        </div>
                                    </div>
                                    { ->
                                                # DATES
                                    }
                                    <div className="form-group row align-items-center">
                                        <label htmlFor={"date-invoice-" + wid}
                                               className="col-2 col-form-label">
                                            {_('Dates')}
                                        </label>
                                        <div className="col-10">
                                            <div className="row">
                                                <div className="col">
                                                    <label
                                                        htmlFor={"date-invoice-" + wid}
                                                        className="col-form-label col-form-label-sm">
                                                            {_('Invoice date')}
                                                    </label>
                                                    <DatePicker
                                                        className={classnames(
                                                            'form-control': true
                                                            'form-control-sm': true
                                                            'is-invalid': not @_isValidDateOrEmpty(@state.invoiceDate)
                                                        )}
                                                        id={"date-invoice-" + wid}
                                                        dateFormat="YYYY-MM-DD"
                                                        value={@state.invoiceDate}
                                                        max={@state.dueDate}
                                                        onChange={@_updateInvoiceDate}
                                                        disabled={@_readOnly()}
                                                        />
                                                    <div className='invalid-feedback'>
                                                        {_('Incorrect date format. Please use YYYY-MM-DD.')}
                                                    </div>
                                                </div>
                                                <div className="col">
                                                    <label htmlFor={"date-transfer-" + wid}
                                                        className="col-form-label col-form-label-sm">
                                                        {_('Transfer date')}
                                                    </label>
                                                    <DatePicker
                                                        className={classnames(
                                                            'form-control': true
                                                            'form-control-sm': true
                                                            'is-invalid': not @_isValidDateOrEmpty(@state.transferDate)
                                                        )}
                                                        id={"date-transfer-" + wid}
                                                        dateFormat="YYYY-MM-DD"
                                                        value={@state.transferDate}
                                                        min={@state.invoiceDate}
                                                        onChange={@_updateTransferDate}
                                                        disabled={@_readOnly()}
                                                        /> {lateTransferDateBadge1} {lateTransferDateBadge2} {nonBankDayBadge}
                                                    <div className='invalid-feedback'>
                                                        Incorrect date format. Please use YYYY-MM-DD.
                                                    </div>
                                                </div>
                                                <div className="col">
                                                    <label htmlFor={"date-due-" + wid}
                                                           className="col-form-label col-form-label-sm">
                                                        {_('Due date')}
                                                    </label>
                                                    <DatePicker
                                                        className={classnames(
                                                            'form-control': true
                                                            'form-control-sm': true
                                                            'is-invalid': not @_isValidDateOrEmpty(@state.dueDate)
                                                        )}
                                                        id={"date-due-" + wid}
                                                        dateFormat="YYYY-MM-DD"
                                                        value={@state.dueDate}
                                                        min={@state.invoiceDate}
                                                        onChange={@_updateDueDate}
                                                        disabled={@_readOnly()}
                                                        />
                                                    <div className='invalid-feedback'>
                                                        {_('Incorrect date format. Please use YYYY-MM-DD.')}
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                    { ->
                                                # IDENTIFIER
                                    }
                                    <div className="d-flex form-group row">
                                        <div className='col-2 d-flex align-items-center'>
                                            <label className="form-check col-form-label">
                                                {_('Invoice identifier')}
                                            </label>
                                        </div>
                                        <div className='col-10'>
                                            <div className='row'>
                                                <div className='col'>
                                                    <label className="form-check-label col-form-label-sm"
                                                           htmlFor={'receiverOCR-' + wid}>
                                                        <input className="form-check-input" type="radio"
                                                               id={"receiverOCR-" + wid}
                                                               name={"radio-identifier-" + wid}
                                                               value={"ocr"}
                                                               checked={@state.invoiceIdentifierType == "ocr"}
                                                               onChange={@_updateInvoiceIdentifierType}
                                                               readOnly={@_readOnly()}
                                                               /> {_('OCR number')}
                                                    </label>
                                                </div>
                                                <div className='col'>
                                                    <label className="form-check-label col-form-label-sm"
                                                           htmlFor={"receiverInvNo-" + wid}>
                                                        <input className="form-check-input" type="radio"
                                                               id={"receiverInvNo-" + wid}
                                                               name={"radio-identifier-" + wid}
                                                               value={"invoiceNumber"}
                                                               checked={@state.invoiceIdentifierType == "invoiceNumber"}
                                                               onChange={@_updateInvoiceIdentifierType}
                                                               readOnly={@_readOnly()}
                                                               /> {_('Invoice number')}
                                                    </label>
                                                </div>
                                                <div className='col'>
                                                    <label className="form-check-label col-form-label-sm"
                                                           htmlFor={'receiverMessage-' + wid}>
                                                        <input className="form-check-input" type="radio"
                                                               id={"receiverMessage-" + wid}
                                                               name={"radio-identifier-" + wid}
                                                               value={"message"}
                                                               checked={@state.invoiceIdentifierType == "message"}
                                                               onChange={@_updateInvoiceIdentifierType}
                                                               readOnly={@_readOnly()}
                                                               /> {_('Message to recipient')}
                                                    </label>
                                                </div>
                                            </div>
                                            <div className='row'>
                                                {<div className="col">
                                                    <input
                                                        type="text"
                                                        className={classnames(
                                                            'form-control': true
                                                            'form-control-sm': true
                                                            'is-invalid': @state.ocrInvalid
                                                        )}
                                                        id={"text-input-ocr-" + wid}
                                                        value={@state.ocr}
                                                        onChange={@_updateOcr}
                                                        onBlur={=> @setState(ocrInvalid: @state.ocr and not utils.luhn_check(@state.ocr))}
                                                        readOnly={@_readOnly()}
                                                        />
                                                    <div className='invalid-feedback'>
                                                        {_('Incorrect Luhn checksum.')}
                                                    </div>
                                                </div> if @state.invoiceIdentifierType == 'ocr'}
                                                {<div className="col">
                                                    <input className="form-control form-control-sm"
                                                            type="text"
                                                            id={"text-input-invoicenumber-" + wid}
                                                            value={@state.invoiceNumber}
                                                            onChange={@_updateInvoiceNumber}
                                                            readOnly={@_readOnly()}
                                                            />
                                                </div> if @state.invoiceIdentifierType == 'invoiceNumber'}
                                                {<div className="col">
                                                    <input className="form-control form-control-sm"
                                                            type="text"
                                                            id={"text-input-message-" + wid}
                                                            value={@state.message}
                                                            onChange={@_updateMessage}
                                                            readOnly={@_readOnly()}
                                                            />
                                                </div> if @state.invoiceIdentifierType == 'message'}
                                                {<div className="col">
                                                    <input className="form-control form-control-sm"
                                                            type="text"
                                                            id={"placeholder-identifier-" + wid}
                                                            disabled={true} />
                                                </div> if @state.invoiceIdentifierType not in ['ocr', 'invoiceNumber', 'message']}
                                            </div>
                                        </div>
                                    </div>
                                    { ->
                                                # ATTACHEMENTS
                                    }
                                    <div className='form-group row align-items-center'>
                                        <label className="col-2 col-form-label">{_('Scanned invoice')}</label>
                                        <div className='col-10'>
                                            <a
                                                data-toggle="collapse"
                                                href={"#collapseScan"+wid}
                                                aria-expanded='true'
                                                aria-controls={"collapseScan"+wid}>
                                                {if @props.images.length > 0
                                                    'Show ' + @props.images.length + ' attached files'
                                                else if @props.accounted
                                                    _('No attached files')
                                                else
                                                    _('Attach invoice files')}
                                            </a>
                                            <div className="collapse" id={"collapseScan"+wid}>
                                                <div className="card card-body">
                                                    {<div className='card-deck'>
                                                        {<div className='card' key={imagetoid}>
                                                            <a
                                                                className='card-link'
                                                                href="/image/#{imagetoid}"
                                                                target="_blank"
                                                                >
                                                            <img
                                                                className="card-img-top"
                                                                src="/image/#{imagetoid}/image/0/200/200"
                                                                alt="Scanned invoice" />
                                                            </a>
                                                            <div className="card-img-overlay close-button-overlay">
                                                                <button
                                                                    type="button"
                                                                    className="close"
                                                                    disabled={@_readOnly()}
                                                                    onClick={generateRemover(imagetoid)}
                                                                    aria-label="Remove">
                                                                    <span aria-hidden="true">&times;</span>
                                                                </button>
                                                            </div>
                                                            <div className="card-footer">
                                                                <a
                                                                    className='card-link'
                                                                    href="/image/#{imagetoid}"
                                                                    target="_blank"
                                                                    >
                                                                <p className="card-text">
                                                                    {yieldImageFilename(imagetoid) or 'Loading...'}
                                                                </p>
                                                                </a>
                                                            </div>
                                                        </div> for imagetoid in @props.images}
                                                        <FileUploader
                                                            toid={@props.toid}
                                                            uploadInvoiceImage={@props.uploadInvoiceImage}
                                                            disabled={@state.invoiceState == ''}
                                                            />
                                                    </div> if @state.invoiceState }
                                                    {<p>
                                                        {_('You need to save the draft before uploading attachements is possible.')}
                                                    </p> if not @state.invoiceState}
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                    { ->
                                                # VERIFICATION 1
                                    }
                                    <div className="form-group row align-items-center">
                                        <label htmlFor="verification-registration" className="col-2 col-form-label">
                                            {_('Verification on registration')}
                                        </label>
                                        <div className="col-10">
                                            <Verification
                                                htmlId={'verification-registration' + wid}
                                                verification={@props.registrationVerification}
                                                verDataAggregator={@registrationVerAggr}
                                                pullData={@_updateRegistrationVerification}
                                                defaultlines={@state.regVerificationLinesPrediction}
                                                showMetadata={true}
                                                showMetadataForm={false}
                                                showButtons={false}
                                                padTables={false}
                                                readOnly={@_readOnly()}
                                                />
                                        </div>
                                    </div>
                                </fieldset>
                                { ->
                                            # PAYMENT
                                }
                                <fieldset disabled={@state.accounted}>
                                    {<div className="form-group row align-items-center">
                                        <label htmlFor={"manual-payment-" + wid} className="col-2 col-form-label">
                                            {_('Payment')}
                                        </label>
                                        <div className="col-10">
                                            {<div className="checkbox" id={'manual-payment-'+wid}>
                                                <label>
                                                    {_('Automated payment failed.')}
                                                    {_('Error message from Bankgirocentralen (BGC):')}<br/>
                                                    {'"'}{@props.rejected_log}{'"'}
                                                </label>
                                            </div> if @state.invoiceState == 'rejected'}
                                            {<div className="checkbox" id={'manual-payment-'+wid}>
                                                <label className='mr-3'>
                                                    <input
                                                        type="checkbox"
                                                        value={'manual-payment-sent'}
                                                        checked={@state.invoiceState in ['sent', 'paid']}
                                                        onChange={@_updateToggleSent}
                                                        /> {_('Manual payment sent.')}
                                                </label>
                                                <label className='ml-3'>
                                                    <input
                                                        type="checkbox"
                                                        value={'manual-payment-done'}
                                                        checked={@state.invoiceState == 'paid'}
                                                        onChange={@_updateTogglePaid}
                                                        /> {_('Manual payment done.')}
                                                </label>
                                            </div> if @state.invoiceState in ['registered', 'sent', 'paid'] and not @props.automated}
                                            {<div className="checkbox" id={'automated-payment-'+wid}>
                                                {<label>
                                                    {_('Automated payment scheduled for')} {@_realisticTransferDate()}.
                                                </label> if @state.invoiceState == 'registered'}
                                                {<label>
                                                    {_('Automated payment order for transfer on')} {@_realisticTransferDate()} {_('has been sent.')}
                                                </label> if @state.invoiceState == 'sent'}
                                                {<label>
                                                    {_('Automated payment completed.')}
                                                </label> if @state.invoiceState == 'paid'}
                                            </div> if @props.automated }
                                        </div>
                                    </div> if @state.invoiceState in ['registered', 'sent', 'paid', 'rejected']}
                                    { ->
                                                # VERIFICATION 2
                                    }
                                    {<div className="form-group row align-items-center">
                                        <label htmlFor="text-transfer" className="col-2 col-form-label">
                                            {_('Verification on transfer complete')}
                                        </label>
                                        <div className="col-10">
                                            <Verification
                                                htmlId={'verification-transfer' + wid}
                                                verification={@props.transferVerification}
                                                verDataAggregator={@transferVerAggr}
                                                showMetadata={true}
                                                showMetadataForm={false}
                                                showButtons={false}
                                                readOnly={true}
                                                padTables={false}
                                                />
                                        </div>
                                    </div> if @state.accounted}
                                    { ->
                                                # BUTTONS
                                    }
                                    {<div className='row'>
                                        <div className='col'>
                                            {<button type="button"
                                                     className="btn btn-outline-dark mr-1"
                                                     onClick={=> @props.removeNewForms([@props.toid])}>
                                                {_('Discard form')}
                                             </button> if @props.toid not in @props.supplierInvoiceList}
                                            {<button type="button"
                                                     className="btn btn-outline-danger mr-1"
                                                     onClick={=> @props.deleteSupplierInvoice([@props.toid])}>
                                                {_('Delete draft')}
                                             </button> if @props.toid in @props.supplierInvoiceList and @props.invoiceState in ['', 'incomplete']}
                                            {<button
                                                type="button"
                                                className="btn btn-outline-dark"
                                                onClick={@_resetForm}
                                                disabled={not @state.dirty}
                                                >
                                                {_('Reset changes')}
                                            </button> if @state.invoiceState in ['registered', 'sent', 'paid'] and not @props.automated}
                                        </div>
                                        {<div className='col d-flex justify-content-center'>
                                            <button type="button"
                                                    className="btn btn-primary"
                                                    onClick={@_generateTransferVerification}
                                                    disabled={not (@state.invoiceState == 'paid')}
                                                    >
                                                {_('Generate transfer verification')}
                                            </button>
                                        </div> if not @props.automated}
                                        <div className='col d-flex justify-content-center'>
                                            {<button type="button"
                                                    className="btn btn-primary"
                                                    onClick={@_enableAutomaticPayment}
                                                    disabled={@state.invoiceState != 'registered'}>
                                                {_('Schedule automatic payment')}
                                            </button> if not @props.automated and @state.invoiceState in ['registered', 'sent', 'paid']}
                                            {<button type="button"
                                                     className="btn btn-primary"
                                                     onClick={@_clearRejected}>
                                                {_('Clear rejected status')}
                                            </button> if not @props.automated and @state.invoiceState in ['rejected']}
                                            {<button type="button"
                                                     className="btn btn-danger"
                                                     onClick={@_disableAutomaticPayment}
                                                     disabled={@state.invoiceState in ['sent', 'paid']}>
                                                {_('Cancel automatic payment')}
                                            </button> if @props.automated}
                                        </div>
                                        <div className='col d-flex justify-content-end'>
                                            {<button
                                                type="button"
                                                className={classnames(
                                                    'btn btn-primary': true
                                                    'has-spinner': true
                                                    'active': @state.saving
                                                )}
                                                onClick={@handleSubmit}
                                                disabled={@state.saving or not @_enableSubmit()}
                                                >
                                                    <span className="spinner">
                                                        <i className="fa fa-spinner fa-spin"
                                                           aria-hidden="true">
                                                        </i>
                                                    </span>
                                                    {_('Submit')}
                                            </button> unless @props.automated or @props.accounted}
                                        </div>
                                    </div> unless @state.accounted}
                                </fieldset>
                            </form>
                        </div>
                    </div>
                </div>
                # End expandbody

            # html
            <div className={
                classnames(
                    'card': true
                    'mb-1': true
                    'border-primary': selected
                    )
                }>
                {headline}
                {expandbody}
            </div>
