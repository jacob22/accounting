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

require('./reportlist.css')

define ['react', 'gettext'], (React, gettext) ->

    _ = gettext.gettext

    class ReportRow extends React.Component

        _rowClicked: () =>
            @props.rowClicked(@props.toid)

        render: () ->
            <tr
                className={'table-info' if @props.selected}
                onClick={@_rowClicked}>
                <td className='name'>Tage Test</td>
                <td className='date'>{@props.toi.date}</td>
                <td className='state'>{@props.toi.state}</td>
                <td className='amount'>{@props.toi.amount}</td>
            </tr>


    class ReportList extends React.Component

        @defaultProps:
            selected: null
            empty_text: _('There are no reports')

        constructor: (props) ->
            super(props)
            @state = selected: props.selected

        componentWillReceiveProps: (props) ->
            @setState(selected: props.selected)

        _rowClicked: (toid) ->
            @setState(selected: toid)
            @props.verificationSelected(toid)

        render: () ->
            rows = (
                <ReportRow
                    key={toid}
                    rowClicked={@_rowClicked.bind(this)}
                    toid={toid}
                    toi={@props.toiData[toid]}
                    selected={toid == @state.selected} /> for toid in @props.toilist
            )

            if not rows.length
                <div className='reportlist empty'>
                    {@props.empty_text}
                </div>
            else
                <div className='reportlist'>
                    <table className='table table-striped table-hover'>
                        <tbody>
                            {rows}
                        </tbody>
                    </table>
                </div>
