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


    class TransactionsHistory extends React.Component

        formatDate = (date) ->
            normalisedDate = new Date(date - (date.getTimezoneOffset() * 60 * 1000))
            # Easiest way to get sane date format is to regex from
            # "2011-12-19T15:28:46.493Z" to "2011-12-19 15:28:46"
            normalisedDate.toISOString().replace(/\..+Z/g, '').replace(/[T]/g, ' ')

        
        render: () ->
            widgets = []
            for toid in @props.transactionsHistory.result
                uploadTime = formatDate(new Date(
                    @props.transactionsHistory.toiData[toid].uploadTime[0] * 1000)
                )
                filename = @props.transactionsHistory.toiData[toid].filename[0]
                resultingPayments =  @props.transactionsHistory.toiData[toid].resultingPayments[0]
                widgets.push(
                    <li key={toid}>
                        <span className='uploadData'>
                            {uploadTime}
                        </span>
                        <span className='uploadNum'>
                            {resultingPayments}
                        </span>
                        <span className='uploadData'>
                            {_('new payments:')}
                        </span>
                        <span className='uploadData'>
                            {filename}
                        </span>
                    </li>)

            
            if widgets[0]?
                heading = <h5>{_('Log of uploaded files')}</h5>
            else
                heading = null

            html = <div>
                {heading}
                <ul className='simplelist'>
                    {widgets}
                </ul>
            </div>
            return html
            
                
    return TransactionsHistory
