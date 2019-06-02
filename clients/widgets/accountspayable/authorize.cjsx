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

define(['react', 'react-dom', 'classnames', 'jslink/commit', 'gettext'], ->

    [React, ReactDOM, classnames, commit, gettext] = arguments

    _ = gettext.gettext

    class AuthorizationWidget extends React.Component

        @defaultProps:
            signRef: null
            jsLink: null
            submitting: false
            unmount: ->
            pollInterval: 1000

        constructor: (props) ->
            super(props)
            @state = {}

        componentDidMount: ->
            setTimeout(@poll, @props.pollInterval)

        poll: =>
            commit.callBlmMethod(
                @props.jsLink,
                'accounting.getSignatureResultAndApprovePayment',
                [[@props.signRef]], (result) =>
                    if @state.stopped
                        @done()
                    else if result.error?
                        debugger
                    else
                        status = result.result[0]
                        if status != 'PENDING'
                            @done()
                        else
                            setTimeout(@poll, @props.pollInterval)
            )

        stop: =>
            @setState(stopped: true)
            $('#authorizationModal').modal('hide')

        done: ->
            $('#authorizationModal').modal('hide')
            @props.unmount()

        render: ->
            <div
                id='authorizationModal'
                className={classnames(modal: true, fade: true)}
                tabIndex="-1"
                role='dialog'
                aria-hidden='true'
            >
                <div className="modal-dialog modal-lg">
                    <div className="modal-content" role="document">
                        <div className='modal-header'>
                            <h4 className="modal-title"><img src="/static/freja.png" /></h4>
                        </div>
                        <div className='modal-body'>

                            <p>
                                {_('You need to sign the autmatic payment using Freja eID.')}
                            </p>
                            <button
                                type="button"
                                className="btn btn-cancel"
                                onClick=@stop
                            >{_('Cancel')}</button>
                        </div>
                        <div className='modal-footer'>
                        </div>
                    </div>
                </div>
            </div>

    module =
        AuthorizationWidget: AuthorizationWidget

    return module
)
