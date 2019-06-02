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

define(['react', 'gettext', 'utils', 'iter',
        'widgets/accountselector', 'widgets/amount'], ->
    [React, gettext, utils, iter, AccountSelector, Amount] = arguments

    _ = gettext.gettext

    class AccountingRuleEditor extends React.Component

        @defaultProps:
            editable: false

        constructor: (props) ->
            super(props)
            @state = {'accountNo': @props.accountNo, 'amount': @props.amount}

        saveAmount: (amount) =>
            @setState({'amount': amount})
            @setRule(@state['accountNo'], amount)

        saveAccount: (accountid) =>
            accountToi = @props.accountsQuery.toiData[accountid]
            accountNo = accountToi['number'][0]
            @setState({'accountNo': accountNo})
            @setRule(accountNo, @state['amount'])

        setRule: (accountNo, amount) ->
            if accountNo? and amount?
                @props.onUpdate(@props.index, accountNo, amount)

        delete: () =>
            @setState({'amount': null, 'accountNo': null})
            @props.onDelete(@props.index)

        render: () ->
            selected = null
            
            for toid, toi of @props.accountsQuery.toiData
                if toi.number[0] == @state.accountNo
                    selected = toid
                    break

            <div className='py-1 row no-gutters align-items-center'>
                <div className='col-6 form-group mb-0 px-1'>
                    <label className='sr-only'>{_('Account')}</label>
                    <AccountSelector
                        query={@props.accountsQuery}
                        selected={selected}
                        handleChange={@saveAccount}
                        className='w-100 h-100'
                        disabled={not @props.editable}
                        />
                </div>
                <div className='col-3 form-group mb-0 px-1'>
                    <label className='sr-only'>{_('Amount')}</label>
                    <Amount
                        value={@state.amount}
                        onUpdate={@saveAmount}
                        className='form-control text-right w-100 h-100'
                        readOnly={not @props.editable}
                        />
                </div>
                {<div className='col-auto form-group mb-0 px-1'>
                    <button
                        type='button'
                        className='btn btn-danger btn-sm'
                        onClick=@delete>
                            {_('Delete')}
                    </button>
                 </div> if @props.editable and (selected? or @state.amount?)}
            </div>


    class AccountingRules extends React.Component
        constructor: (props) ->
            super(props)
            @state = @setupRules(props)
            @state.counter = iter.count()

        componentWillReceiveProps: (nextProps) ->
            @setState(@setupRules(nextProps))

        setupRules: (props) ->
            indexedRules = {}
            i = 0
            for accountnr, amount of props.rules
                # Convert Decimal to integer '10.00' * 100 -> 1000
                amount = utils.parseCurrency(amount)
                indexedRules[i] = [accountnr, amount]
                i++
            indexedRules[i] = [null, null]
            return {indexedRules: indexedRules}

        ruleChanged: (index, newaccount, newamount) =>
            updatedRules = {}
            for i, [accountno, amount] of @state.indexedRules
                if i == index
                    updatedRules[newaccount] = newamount
                else if accountno? and amount?
                    updatedRules[accountno] = amount
            @props.onUpdate(updatedRules)

        deleteRule: (index) =>
            updatedRules = {}
            for i, [accountno, amount] of @state.indexedRules
                if i != index and accountno? and amount?
                    updatedRules[accountno] = amount
            @props.onUpdate(updatedRules)
            
        priceDiff: () ->
            if @props.izPrice.length != 0
                diff = utils.parseCurrency(@props.izPrice[0]) - utils.parseCurrency(@props.price[0])
            else
                diff = null
            return diff

        render: () ->
            widgets = []
            for index, [accountNo, amount] of @state.indexedRules
                widgets.push(
                    <AccountingRuleEditor
                        key={@state.counter.next()}
                        index=index
                        accountsQuery={@props.accountsQuery}
                        accountNo={accountNo}
                        handleChange={@saveAccount}
                        onDelete={@deleteRule}
                        amount={amount}
                        onUpdate={@ruleChanged}
                        editable={@props.editable}
                        />
                )
            # Empty box
            widgets.push(
                <div className='row no-gutters' key='{@state.counter.next()}'>
                    <div className='col-9 form-control-static align-self-right text-right py-1'>
                        {
                            <span>
                                {_('Diff')}: {utils.formatCurrency(@priceDiff())}
                            </span> if @priceDiff()
                        }
                        <span className='mx-3'>
                            {_('Sum')}: {utils.formatCurrency(utils.parseCurrency(@props.price[0]))}
                        </span>
                    </div>
                    
                </div>
            )
            return <div className='col-auto flex-column mr-3 form'>{widgets}</div>

    class Row extends React.Component

        _rowClicked: () =>
            @props.rowClicked(@props.toid)

        rulesChanged: (rules) =>
            @props.onUpdate(@props.toid, {'accountingRules': rules})

        accountsMissing: () ->
            if not @props.accountMap?
                return false
            for accountNumber, amount of @props.toi.accountingRules
                if accountNumber not of @props.accountMap
                    return true
            return false

        render: () ->
            if @props.toi.izPrice.length
                izPrice = @props.toi.izPrice[0]
                printedprice = utils.formatCurrency(utils.parseCurrency(izPrice))
            else
                izPrice = 0
                printedprice = null
                
            if @props.selected
                editproduct = <tr>
                    <td colSpan='4' className='nohover'>
                        <div className='row no-gutters d-flex align-content-around flex-wrap'>
                            <AccountingRules
                                rules={@props.toi.accountingRules}
                                price={@props.toi.price}
                                izPrice={@props.toi.izPrice}
                                onUpdate={@rulesChanged}
                                productId={@props.toi.productId}
                                accountsQuery={@props.accountsQuery}
                                editable={@props.editable}
                                />
                            <div className='col col-lg-4 ml-auto px-0'>
                                <div className='card card-block m-1'>
                                    <ul className='simplelist smallfont infobox'>
                                        <li>
                                            {_('iZettle product identifier:')}
                                            <span className='productId'>{@props.toi.productId[0]}</span>
                                        </li>
                                        <li>
                                            {_('Barcode:')}
                                            <span className='barcode'>{@props.toi.barcode}</span>
                                        </li>
                                        <li>
                                            {_('Custom unit:')}
                                            <span className='otherunit'>{@props.toi.customUnit}</span>
                                        </li>
                                        <li>
                                            {_('VAT percentage:')}
                                            <span className='vatpercentage'>{@props.toi.vatPercentage}</span>
                                        </li>
                                        {
                                            <li>
                                                {_('Note:')}
                                                <span className='izpnote'>
                                                    {_('iZettle price not specified. Product can not
                                                    be evaluated in verification import.')}
                                                </span>
                                            </li> if not izPrice}
                                    </ul>
                                </div>
                            </div>
                        </div>
                    </td>
                </tr>
            else
                editproduct = null

            if @props.toi.price[0] == izPrice or not @props.toi.izPrice.length
                priceCheck = null
            else
                priceCheck = <i className='fa fa-exclamation-triangle' aria-hidden='true'></i>
                    
            if @accountsMissing()
                accountCheck = <i className='fa fa-bug' aria-hidden='true'></i>
            else
                accountCheck = null
            
            myhtml = <tbody>
                <tr className={'table-info' if @props.selected}
                    onClick={@_rowClicked}
                    role='button'>
                    <td className='name'>{@props.toi.name[0]}</td>
                    <td className='variant'>{@props.toi.variant[0]}</td>
                    <td>{accountCheck}{priceCheck}</td>
                    <td className='amount text-right'>
                        {printedprice}
                    </td>
                </tr>
                {editproduct}
            </tbody>
                

    class ProductList extends React.Component

        constructor: (props) ->
            super(props)
            @state = {}

        _rowClicked: (toid) ->
            if @state.selected == toid
                @setState(selected: null)
            else
                @setState(selected: toid)

        rulesChanged: (toid, rules) =>
            @props.onUpdate(toid, rules)


        render: () ->
            rows = (
                <Row
                    accountsQuery=@props.accountsQuery
                    key={toid}
                    rowClicked={@_rowClicked.bind(this)}
                    onUpdate={@rulesChanged}
                    toid={toid}
                    accountMap={@props.accountMap}
                    toi={@props.toiData[toid]}
                    selected={toid == @state.selected}
                    editable={@props.editable}
                    /> for toid in @props.toilist
            )

            if not rows.length
                <div className='productlist empty'>
                    {_('There are no iZettle products yet.')}
                </div>
            else
                <div className='productlist'>
                    <table className='table table-hover'>
                        <thead>
                            <tr>
                                <th>{_('Name')}</th>
                                <th>{_('Variant')}</th>
                                <th>{_('Status')}</th>
                                <th className='text-right'>{_('Price')}</th>
                            </tr>
                        </thead>
                        {rows}
                    </table>
                </div>

     return ProductList
)
