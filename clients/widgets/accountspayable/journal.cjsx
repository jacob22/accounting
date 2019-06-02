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

    _ = gettext.gettext

    class Journal extends React.Component
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

        _runDebugger: () =>
            debugger

        _checkPaid: () =>
            if @state.invoiceState in ['sent', 'paid']
                return true
            else
                return false

        _readOnly: () =>
            return true

        _updateValue: (key, value) =>
            if @state[key] != value
                newstate = {dirty: true}
                newstate[key] = value
                @setState(newstate)
                @props.deSelect(@props.toid)
                console.log(key, value)

        _updateTogglePaid: (event) =>
            old = @state.invoiceState
            if old == 'registered'
                @setState(invoiceState: 'paid', dirty: true)
            else if old == 'paid'
                @setState(invoiceState: 'registered', dirty: true)
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

        _checkDueToday: () =>
            if moment().format('YYYY-MM-DD') == @state.transferDate
                return true
            else
                return false

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

        render: () ->
            wid=@props.toid
            collapseId = 'collapse-' + wid
            collapseCssId = '#' + collapseId

            selected = @props.toid of @props.selected

            # Status badges
            if @state.invoiceState == ''
                stateBadge = <span className='badge badge-info'>New</span>
            if @state.invoiceState == 'incomplete'
                stateBadge = <span className='badge badge-secondary'>Draft</span>
            if @state.invoiceState == 'registered' and @props.automated == false
                stateBadge = <span className='badge badge-secondary'>Registered</span>
            if @state.invoiceState == 'registered' and @props.automated == true
                stateBadge = <span className='badge badge-secondary'>Scheduled</span>
            if @state.invoiceState == 'sent' and @props.automated == false
                stateBadge = <span className='badge badge-secondary'>Sent</span>
            if @state.invoiceState == 'sent' and @props.automated == true
                stateBadge = <span className='badge badge-secondary'>Payment order sent</span>
            if @state.invoiceState == 'paid' and @state.accounted == false
                stateBadge = <span className='badge badge-success'>Paid</span>
            if @state.invoiceState == 'paid' and @state.accounted == true
                stateBadge = <span className='badge badge-secondary'>Paid</span>
            if @state.invoiceState == 'rejected'
                stateBadge = <span className='badge badge-danger'>Rejected</span>

            # Automation badge
            if @props.automated == true
                automatedBadge = <span className='badge badge-secondary'>Automated</span>
            else
                automatedBadge = null

            # Date badges
            nonBankDayBadge = null
            if moment(@state.transferDate).isValid() and not @_isWeekday(@state.transferDate)
                nonBankDayBadge = <span className='badge badge-danger'>Not a banking day</span>
            lateTransferDateBadge1 = null
            if @state.invoiceState != 'paid'
                if moment(@state.transferDate).isAfter(moment(@state.dueDate))
                    lateTransferDateBadge1 = <span className='badge badge-danger'>Overdue date</span>
            lateTransferDateBadge2 = null
            if @state.invoiceState != 'paid'
                if moment(@state.transferDate).isBefore(moment(moment().format('YYYY-MM-DD')))
                    lateTransferDateBadge2 = <span className='badge badge-warning'>Past date</span>

            if @state.invoiceState == 'paid'
                dueBadge = null
            else
                if @_checkOverdue()
                    dueBadge = <span className='badge badge-danger'>Overdue</span>
                else if @_checkDueToday()
                    dueBadge = <span className='badge badge-warning'>Due</span>
                else
                    dueBadge = null

            # Misc. badges
            if @state.accounted == true
                accountedBadge = <span className='badge badge-secondary'>Accounted</span>
            else
                accountedBadge = null

            if @state.dirty
                dirtyBadge = <span className='badge badge-warning'>Unsaved changes</span>
            else
                dirtyBadge = null

            if @state.invoiceType == 'credit'
                creditBadge = <span className='badge badge-secondary'>Credit</span>
            else
                creditBadge = null

            if @props.images.length > 0
                attacheIcons = []
                for image in @props.images
                    attacheIcons.push(<i key=image className="fa fa-paperclip" aria-hidden="true"></i>)
            else
                attacheIcons = null

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
                        <div className='col text-center'><small>{@state.invoiceNumber or @state.ocr}</small></div>
                        <div className='col text-right'>{creditBadge} {utils.formatCurrency(@state.amount)}</div>
                    </div>
                </div>

            # Expanded body
            expandbody =
                <div>
                    <div className="card-body">
                        <div className="d-flex flex-column">
                            <form className='form'>
                                <fieldset disabled={@props.accounted or @props.automated or @state.invoiceState == 'paid'}>
                                    <div className="d-flex row">
                                        <label htmlFor={"text-typeahead-recipient-" + wid}
                                               className="col-2 col-form-label">
                                            Recipient name
                                        </label>
                                        <div className="col-10">
                                            <label className="col-form-label">
                                                    {@state.recipient}
                                            </label>
                                        </div>
                                    </div>
                                    <div className="d-flex row">
                                        <label htmlFor={"amount-input-" + wid}
                                               className="col-2 col-form-label">
                                            Amount
                                        </label>
                                        <div className="col">
                                            <label className="col-form-label">
                                                {utils.formatCurrency(@state.amount)}
                                            </label>
                                            {<label className="form-check-label col-form-label">
                                                Debit
                                            </label> if @state.invoiceType == 'debit'}
                                            {<label className="form-check-label col-form-label">
                                                Credit
                                            </label> if @state.invoiceType == 'credit'}
                                        </div>
                                    </div>
                                    { ->
                                                # TRANSFER METHOD
                                    }
                                    <div className="d-flex row">
                                        <div className='col-2 d-flex align-items-center'>
                                            <label className="form-check col-form-label">
                                                Transfer method
                                            </label>
                                        </div>
                                        <div className='col'>
                                            <div className='row'>
                                                <div className='col'>
                                                    {<label className="col-form-label">
                                                        Bankgiro
                                                    </label> if @state.transferMethod == 'bgnum'}
                                                    {<label className="col-form-label">
                                                        Plusgiro
                                                    </label> if @state.transferMethod == 'pgnum'}
                                                    {<label className="col-form-label">
                                                        Bank account number
                                                    </label> if @state.transferMethod == 'bankaccount'}
                                                    {<label className="form-check-label col-form-label">
                                                        {utils.formatBgnum(@state.bgnum)}
                                                    </label> if @state.transferMethod == 'bgnum'}
                                                    {<label className="form-check-label col-form-label">
                                                        value={utils.formatPgnum(@state.pgnum)}
                                                    </label> if @state.transferMethod == 'pgnum'}
                                                    {<div>
                                                        <label className="form-check-label col-form-label">
                                                            Clearing
                                                        </label>
                                                        <label className="form-check-label col-form-label">
                                                            {utils.formatClearing(@state.bankclearing)}
                                                        </label>
                                                        <label className="form-check-label col-form-label">
                                                            Account
                                                        </label>
                                                        <label className="form-check-label col-form-label">
                                                            {@state.bankaccount}
                                                        </label>
                                                    </div> if @state.transferMethod == 'bankaccount'}
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                    { ->
                                                # DATES
                                    }
                                    <div className="row align-items-center">
                                        <label htmlFor={"date-invoice-" + wid}
                                               className="col-2 col-form-label">
                                            Dates
                                        </label>
                                        <div className="col-10">
                                            <div className="row">
                                                <div className="col">
                                                    <label className="col-form-label">
                                                        Invoice date
                                                    </label>
                                                    <label className="form-check-label col-form-label">
                                                        {@state.invoiceDate}
                                                    </label>
                                                </div>
                                                <div className="col">
                                                    <label className="col-form-label">
                                                        Transfer date
                                                    </label>
                                                    <label className="form-check-label col-form-label">
                                                        {@state.transferDate} {lateTransferDateBadge1} {lateTransferDateBadge2} {nonBankDayBadge}
                                                     </label>
                                                </div>
                                                <div className="col">
                                                    <label className="col-form-label">
                                                        Due date
                                                    </label>
                                                    <label className="form-check-label col-form-label">
                                                        {@state.dueDate}
                                                    </label>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                    { ->
                                                # IDENTIFIER
                                    }
                                    <div className="d-flex row">
                                        <div className='col-2 d-flex align-items-center'>
                                            <label className="form-check col-form-label">
                                                Invoice identifier
                                            </label>
                                        </div>
                                        <div className='col-10'>
                                            <div className='row'>
                                                <div className='col'>
                                                    {<label className="col-form-label">
                                                        OCR number
                                                    </label> if @state.invoiceIdentifierType == "ocr"}
                                                    {<label className="col-form-label">
                                                        Invoice number
                                                    </label> if @state.invoiceIdentifierType == "invoiceNumber"}
                                                    {<label className="col-form-label">
                                                       Message to recipient
                                                    </label> if @state.invoiceIdentifierType == "message"}
                                                    {<label className="form-check-label col-form-label">
                                                        {@state.ocr}
                                                    </label> if @state.invoiceIdentifierType == 'ocr'}
                                                    {<label className="form-check-label col-form-label">
                                                            {@state.invoiceNumber}
                                                    </label> if @state.invoiceIdentifierType == 'invoiceNumber'}
                                                    {<label className="form-check-label col-form-label">
                                                            {@state.message}
                                                    </label> if @state.invoiceIdentifierType == 'message'}
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                    { ->
                                                # ATTACHEMENTS
                                    }
                                    <div className='row align-items-center'>
                                        <label className="col-2 col-form-label">Scanned invoice</label>
                                        <div className='col-10'>
                                            <a
                                                data-toggle="collapse"
                                                href={"#collapseScan"+wid}
                                                aria-expanded='true'
                                                aria-controls={"collapseScan"+wid}>
                                                {if @props.images.length > 0
                                                    'Show ' + @props.images.length + ' attached files'
                                                else
                                                    'No attached files'}
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
                                                    </div> if @props.images.length > 0 }
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                    { ->
                                                # VERIFICATION 1
                                    }
                                    <div className="row align-items-center">
                                        <label htmlFor="verification-registration" className="col-2 col-form-label">
                                            Verification on registration
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
                                                readOnly={true}
                                                />
                                        </div>
                                    </div>
                                </fieldset>
                                { ->
                                            # PAYMENT
                                }
                                    {<div className="row align-items-center">
                                        <label htmlFor={"manual-payment-" + wid} className="col-2 col-form-label">
                                            Payment
                                        </label>
                                        <div className="col-10">
                                            {<div className="checkbox" id={'manual-payment-'+wid}>
                                                <label>
                                                    Automated payment failed.
                                                    Error message from Bankgirocentralen (BGC):<br/>
                                                    {'"'}{@props.rejected_log}{'"'}
                                                </label>
                                            </div> if @state.invoiceState == 'rejected'}
                                            {<div className="checkbox" id={'manual-payment-'+wid}>
                                                <label>
                                                    <input
                                                        type="checkbox"
                                                        value={'manual-payment-done'}
                                                        checked={@state.invoiceState == 'paid'}
                                                        onChange={@_updateTogglePaid}
                                                        /> Manual payment done.
                                                </label>
                                            </div> if @state.invoiceState in ['registered', 'sent', 'paid'] and not @props.automated}
                                        </div>
                                    </div> if @state.invoiceState in ['registered', 'sent', 'paid', 'rejected']}
                                    { ->
                                                # VERIFICATION 2
                                    }
                                    {<div className="row align-items-center">
                                        <label htmlFor="text-transfer" className="col-2 col-form-label">
                                            Verification on transfer complete
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
