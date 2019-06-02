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

require('./common.css')
require('./report.css')

define [
    'react', 'react-dom', 'moment',
    'gettext', 'signals', 'utils',
    'jslink/JsLink', 'jslink/commit', 'jslink/query', 'jslink/ToiSetWatcher',
    'widgets/expensereport', 'widgets/expense/reportlist',
    'moment/locale/sv'  # this just needs to be loaded
    ], (
    React, ReactDOM, moment,
    gettext, signals, utils,
    JsLink, commit, query, ToiSetWatcher,
    ExpenseReport, ReportList) ->

    moment.locale(window.navigator.languages.concat(['sv-SE']))
    gettext.install('client')
    _ = gettext.gettext

    jsLink = new JsLink('/jslink')
    categories = {}

    lineWatcher = new ToiSetWatcher(jsLink, 'expenses.Line',
        ['category', 'amount', 'count', 'text'])

    categoryQuery = new query.SortedQuery(jsLink, 'expense.Category')
    categoryQuery.attrList = ['name']

    countableCategoryQuery = new query.SortedQuery(jsLink,
        'expense.CategoryCountable')
    countableCategoryQuery.attrList = ['name', 'price', 'unit']

    categoryOneQuery = new query.SortedQuery(jsLink, 'expense.CategoryOne')
    categoryOneQuery.attrList = ['name', 'price']

    categoryUpdated = ->
        utils.clear(categories)
        for q in [categoryQuery, countableCategoryQuery, categoryOneQuery]
            for toid, toiData of q.toiData
                categories[toid] =
                    name: toiData.name[0]
                    _tocName: toiData._tocName

                if toiData.price? and toiData.price.length
                    categories[toid].price = utils.parseCurrency(toiData.price[0])

                if toiData.unit? and toiData.unit.length
                    categories[toid].unit = toiData.unit[0]

    signals.connect(categoryQuery, 'update', categoryUpdated)
    signals.connect(categoryOneQuery, 'update', categoryUpdated)
    signals.connect(countableCategoryQuery, 'update', categoryUpdated)

    reportsQuery = new query.SortedQuery(jsLink, 'expense.Verification',
        {state: ['new', 'handling']})
    reportsQuery.attrList = ['state', 'amount', 'date', 'text', 'lines',
        'receipt']
    signals.connect(reportsQuery, 'update', () ->
        if @result.length
            selected = reportList.props.selected if reportList?
            renderList(selected)
            ReactDOM.render(
                <button
                    className='btn'
                    onClick={-> showVerification()}>
                    Skapa ny rapport
                </button>,
                document.getElementById('newreport')
            )
            if selected?
                showVerificationByToid(selected)
        else
            showVerification()
    )

    reportList = null
    renderList = (selected=null) ->
        reportList = ReactDOM.render(
            <ReportList
                empty_text={_('You have no expense reports that are being processed.')}
                selected={selected}
                verificationSelected={(toid) ->
                    showVerification(@toiData[toid])}
                toilist={@result}
                toiData={@toiData}/>,
            document.getElementById('reports'))
    renderList = renderList.bind(reportsQuery)

    showVerificationByToid = (toid) ->
        toiData = reportsQuery.toiData[toid]
        if toiData?
            showVerification(toiData)
        else
            update = (add) ->
                toiData = @toiData[toid]
                if toiData?
                    showVerification(toiData)
                    signals.disconnect(reportsQuery, 'update', update)
            signals.connect(reportsQuery, 'update', update)

    showVerification = (toiData) ->
        renderList(toiData._id[0] if toiData?)
        if toiData? and toiData['state']? and toiData['state'].length
            readOnly = toiData['state'][0] in ['denied', 'approved']
        else
            readOnly = false

        ReactDOM.render(
            <ExpenseReport
                readOnly={readOnly}
                lineWatcher={lineWatcher}
                toiData={toiData}
                categories={categories}
                save={save} />,
            document.getElementById('reportview')
        )

    save = (report, callback) ->
        date = [report.state.date.format('YYYY-MM-DD')]
        text = [report.state.text]
        lines = ({
            category: line.category,
            text: line.text,
            count: line.count,
            amount: line.amount
        } for line in report.state.lines when line.category and
                                              line.amount or line.count)

        newFiles = ({
            name: fileData.file.name
            type: fileData.file.type
            data: btoa(fileData.data)
        } for fileData in report.state.newFiles)

        unless report.state.id?  # Create report
            receipt = newFiles
            commit.callBlmMethod(
                jsLink,
                'expense.fileExpenseReport',
                [date, text, lines, receipt],
                (result) ->
                    if result.error?
                        debugger
                    else
                        showVerificationByToid(result.result[0])
                    callback(result)
            )

        else  # Edit existing report
            id = [report.state.id]
            oldFiles = report.state.oldFiles

            commit.callBlmMethod(
                jsLink,
                'expense.updateExpenseReport',
                [id, date, text, lines, newFiles, oldFiles],
                (result) ->
                    if result.error?
                        debugger
                    # else
                    #     showVerificationByToid(result.result[0])
                    callback(result)
            )

    jsLink.ready.then(->
        countableCategoryQuery.start()
        categoryQuery.start()
        categoryOneQuery.start()
        reportsQuery.start()
    )
