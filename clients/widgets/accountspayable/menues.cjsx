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
    'widgets/date',
    'classnames',
    ], (
    React,
    ReactDOM,
    gettext,
    utils,
    iter,
    moment,
    signals,
    DatePicker,
    classnames,
    ) ->

    _ = gettext.gettext

    class Menues extends React.Component
        constructor: (props) ->
            super(props)
            @state = {
               searchString: '',
               startdatestring: '',
               stopdatestring: '',
            }

        _printSelected: () =>
            console.log(@props.selected)

        _filterNew: (selection) =>
            selection = utils.copyobj(selection)
            for toid of selection
                if toid in @props.newformlist
                    delete selection[toid]
            return selection

        _changeQueryStartDate: (event) =>
            date = event.target.value
            @setState(startdatestring: date)
            @props.setQueryDates(date, @state.stopdatestring)

        _changeQueryStopDate: (event) =>
            date = event.target.value
            @setState(stopdatestring: date)
            @props.setQueryDates(@state.startdatestring, date)


        # BLM METHODS CALLS

        _setRegistered: (selected) =>
            callback = () =>
                @setState(working: false)
            @setState(working: true)
            if selected.length >= 1
                @props.setSIState(selected, 'registered', callback)

        _setSent: (selected) =>
            callback = () =>
                @setState(working: false)
            @setState(working: true)
            if selected.length >= 1
                @props.setSIState(selected, 'sent', callback)

        _setPaid: (selected) =>
            callback = () =>
                @setState(working: false)
            @setState(working: true)
            if selected.length >= 1
                @props.setSIState(selected, 'paid', callback)

        render: () =>
            selectedCount = Object.keys(@props.selected).length
            if selectedCount > 0
                selectedCountBadge = <span className="badge badge-info">{selectedCount} {_('invoices selected')}</span>
            else
                selectedCountBadge = null

            working = @state.working or @props.working
            noneSelected = Object.keys(@_filterNew(@props.selected)).length == 0

            html =
                <div>
                    <div className='row'>
                        <div className='col'>
                            <nav className="navbar fixed-top navbar-light bg-light navbar-border">
                                <ul className="nav nav-pills">
                                    <li className="nav-item">
                                        <a
                                            className={classnames(
                                                'nav-link': true
                                                'disabled': not @props.enableNew
                                            )}
                                            href="#"
                                            onClick={=> @props.createNewForm() if @props.enableNew}
                                            >{_('New')}</a>
                                    </li>
                                    <li className="nav-item dropdown">
                                        <a
                                            href="#"
                                            className={classnames(
                                                'nav-link': true
                                                'dropdown-toggle': true
                                            )}
                                            id="navbarDropdownMenuLinkView"
                                            data-toggle="dropdown"
                                            aria-haspopup="true"
                                            aria-expanded="false"
                                            >
                                            {_('View')}
                                        </a>
                                        <div
                                            className="dropdown-menu"
                                            aria-labelledby="navbarDropdownMenuLinkView"
                                            >
                                            <a
                                                className={classnames(
                                                    'dropdown-item': true,
                                                )}
                                                href="#"
                                                onClick={=> @props.setParentState(viewJournal: undefined)}
                                                >{_('Show ledger')}</a>
                                            <a
                                                className={classnames(
                                                    'dropdown-item': true,
                                                )}
                                                href="#"
                                                onClick={=> @props.setParentState(viewJournal: true)}
                                                >{_('Show manual payment journal')}</a>
                                            <div className="dropdown-divider"></div>
                                            <a
                                                className={classnames(
                                                    'dropdown-item': true,
                                                )}
                                                href="#"
                                                onClick={=> @props.setParentState(sortingOrder: 1)}
                                                >{_('Sort ascending (current first)')}</a>
                                            <a
                                                className={classnames(
                                                    'dropdown-item': true,
                                                )}
                                                href="#"
                                                onClick={=> @props.setParentState(sortingOrder: -1)}
                                                >{_('Sort descending (futuremost first)')}</a>
                                            <div className="dropdown-divider"></div>
                                            <a
                                                className={classnames(
                                                    'dropdown-item': true,
                                                    'disabled': 'automated' not of @props.filterArguments
                                                )}
                                                href="#"
                                                onClick={=> @props.delFilter('automated')}
                                                >{_('Show automated invoices (default)')}</a>
                                            <a
                                                className={classnames(
                                                    'dropdown-item': true,
                                                    'disabled': 'automated' of @props.filterArguments
                                                )}
                                                href="#"
                                                onClick={=> @props.setFilter('automated', false)}
                                                >{_('Hide automated invoices')}</a>
                                            <div className="dropdown-divider"></div>
                                            <a
                                                className={classnames(
                                                    'dropdown-item': true,
                                                    'disabled': 'accounted' of @props.filterArguments
                                                )}
                                                href="#"
                                                onClick={=> @props.setFilter('accounted', false)}
                                                >{_('Hide accounted invoices (default)')}</a>
                                            <a
                                                className={classnames(
                                                    'dropdown-item': true,
                                                    'disabled': 'accounted' not of @props.filterArguments
                                                )}
                                                href="#"
                                                onClick={=> @props.delFilter('accounted')}
                                                >{_('Show accounted invoices')}</a>
                                            <div className="dropdown-divider"></div>
                                            <a
                                                className={classnames(
                                                    'dropdown-item': true,
                                                )}
                                                href="#"
                                                onClick={=> $('#settingsModal').modal('toggle')}
                                                >{_('Settings')}</a>
                                        </div>
                                    </li>
                                    <li className="nav-item dropdown">
                                        <a
                                            href="#"
                                            className={classnames(
                                                'nav-link': true
                                                'dropdown-toggle': true
                                                'disabled': @props.supplierInvoiceList.length + @props.newformlist.length < 1
                                            )}
                                            id="navbarDropdownMenuLinkSelect"
                                            data-toggle="dropdown"
                                            aria-haspopup="true"
                                            aria-expanded="false"
                                            >{_('Select')}</a>
                                        <div
                                            className="dropdown-menu"
                                            aria-labelledby="navbarDropdownMenuLinkSelect"
                                            >
                                            <a
                                                className="dropdown-item"
                                                href="#"
                                                onClick={@props.selectNone}
                                                >{_('Clear selection')}</a>
                                            <a
                                                className="dropdown-item"
                                                href="#"
                                                onClick={@props.selectInvert}
                                                >{_('Invert selection')}</a>
                                            <a
                                                className="dropdown-item"
                                                href="#"
                                                onClick={@props.selectAll}
                                                >{_('Select all')}</a>
                                            <a
                                                className="dropdown-item"
                                                href="#"
                                                onClick={@props.selectAllUnaccounted}
                                                >{_('Select all unaccounted')}</a>
                                            <div className="dropdown-divider"></div>
                                            <a
                                                className="dropdown-item"
                                                href="#"
                                                onClick={@props.selectDue}
                                                >{_('Select invoices due today')}</a>
                                            <a
                                                className="dropdown-item"
                                                href="#"
                                                onClick={@props.selectPaid}
                                                >{_('Select invoices for accounting')}</a>
                                        </div>
                                    </li>
                                    <li className="nav-item dropdown">
                                        <a
                                            href="#"
                                            className={classnames(
                                                'nav-link': true
                                                'dropdown-toggle': true
                                            )}
                                            id="navbarDropdownMenuLinkAction"
                                            data-toggle="dropdown"
                                            aria-haspopup="true"
                                            aria-expanded="false"
                                            >
                                            {_('Action')}
                                        </a>
                                        <div
                                            className="dropdown-menu"
                                            aria-labelledby="navbarDropdownMenuLinkAction"
                                            >
                                            <a
                                                className={classnames(
                                                    'dropdown-item': true,
                                                    'disabled': Object.keys(@props.selected).length == 0
                                                )}
                                                href="#"
                                                onClick={=> @props.deleteSupplierInvoice(Object.keys(@props.selected))}
                                                >{_('Delete draft')}</a>
                                            <div className="dropdown-divider"></div>
                                            <a
                                                className={classnames(
                                                    'dropdown-item': true,
                                                    'disabled': noneSelected
                                                )}
                                                href="#"
                                                onClick={=> @_setRegistered(Object.keys(@_filterNew(@props.selected)))}
                                                >{_('Mark as registered')}</a>
                                            <a
                                                className={classnames(
                                                    'dropdown-item': true,
                                                    'disabled': noneSelected
                                                )}
                                                href="#"
                                                onClick={=> @_setSent(Object.keys(@_filterNew(@props.selected)))}
                                                >{_('Mark as sent')}</a>
                                            <a
                                                className={classnames(
                                                    'dropdown-item': true,
                                                    'disabled': noneSelected
                                                )}
                                                href="#"
                                                onClick={=> @_setPaid(Object.keys(@_filterNew(@props.selected)))}
                                                >{_('Mark as paid')}</a>
                                            <div className="dropdown-divider"></div>
                                            <a
                                                className={classnames(
                                                    'dropdown-item': true,
                                                    'disabled': noneSelected
                                                )}
                                                href="#"
                                                onClick={=> @props.createTransferVerification(Object.keys(@_filterNew(@props.selected)))}
                                                >{_('Create transfer verification')}</a>
                                            <div className="dropdown-divider"></div>
                                            <a
                                                className={classnames(
                                                    'dropdown-item': true,
                                                    'disabled': noneSelected
                                                )}
                                                href="#"
                                                onClick={=> @props.enableAutomation(Object.keys(@_filterNew(@props.selected)))}
                                                >{_('Schedule automatic payment')}</a>
                                            <a
                                                className={classnames(
                                                    'dropdown-item': true,
                                                    'disabled': noneSelected
                                                )}
                                                href="#"
                                                onClick={=> @props.disableAutomation(Object.keys(@_filterNew(@props.selected)))}
                                                >{_('Unschedule automatic payment')}</a>
                                            <div className="dropdown-divider"></div>
                                            <a
                                                className={classnames(
                                                    'dropdown-item': true,
                                                    'disabled': noneSelected
                                                )}
                                                href="#"
                                                onClick={=> @props.generatePlusgiroFile(Object.keys(@_filterNew(@props.selected)))}
                                                >{_('Download Plusgiro file')}</a>
                                        </div>
                                    </li>
                                    <li>
                                        <div className="form-inline">
                                            <div className="input-group">
                                                <DatePicker
                                                    id='querystartdate-datepicker'
                                                    className={classnames(
                                                        'form-control': true
                                                        'form-control-sm': true
                                                        'ml-2': true
                                                        'my-1': true
                                                    )}
                                                    value={@state.startdatestring}
                                                    onChange={@_changeQueryStartDate}
                                                    onBlur={=> @props.setQueryDates(@state.startdatestring, @state.stopdatestring)}
                                                    />
                                                <DatePicker
                                                    id='querystopdate-datepicker'
                                                    className={classnames(
                                                        'form-control': true
                                                        'form-control-sm': true
                                                        'mr-2': true
                                                        'my-1': true
                                                    )}
                                                    value={@state.stopdatestring}
                                                    onChange={@_changeQueryStopDate}
                                                    onBlur={=> @props.setQueryDates(@state.startdatestring, @state.stopdatestring)}
                                                    />
                                            </div>
                                        </div>
                                    </li>
                                    <li>
                                        <div className="form-inline">
                                            <input
                                                id='filter-box'
                                                className={classnames(
                                                    'form-control': true
                                                    'form-control-sm': true
                                                    'mx-2': true
                                                    'my-1': true
                                                )}
                                                type='search'
                                                value={@state.searchString}
                                                onKeyDown={
                                                    (event) =>
                                                        if event.keyCode == 27
                                                            @setState(searchString: '')
                                                            event.target.blur()
                                                            @props.setSearchTerm(undefined)
                                                        if event.keyCode in [13, 9]
                                                            event.target.blur()
                                                    }
                                                onChange={(event) => @setState(searchString: event.target.value)}
                                                onBlur={() => @props.setSearchTerm(@state.searchString)}
                                                />
                                        </div>
                                    </li>
                                    <li>
                                        <div className='h-100 d-flex align-items-center'>
                                            {selectedCountBadge}
                                        </div>
                                    </li>
                                </ul>
                                <div className={classnames(
                                    'has-spinner': true
                                    'float-right': true
                                    'mr-0': true
                                    'd-none': not @state.working and not @props.working
                                    'active': @state.working or @props.working
                                    )}>
                                    <span className='spinner'>
                                        <i className="fa fa-spinner fa-spin" aria-hidden="true"></i> {_('Working...')}
                                    </span>
                                </div>
                            </nav>
                        </div>
                    </div>
                </div>
            return html
