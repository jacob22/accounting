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
    'iter',
    'classnames',
    ], (
    React,
    gettext,
    utils,
    iter,
    classnames,
    ) ->

    _ = gettext.gettext

    class Alerts extends React.Component
        @defaultStatus:
            alertList: []

        constructor: (props) ->
            super(props)
            @state = {alertList: []}
            @state = @parseProps(props)

        componentWillReceiveProps: (nextProps) ->
            @setState(@parseProps(nextProps))
            if nextProps.dismiss?
                for alert in nextProps.dismiss
                    @_dismissByKey(alert['key'])

        parseProps: (props) =>
            dismisskeys = []
            updatedkeys = []
            alertList = []
            if props.dismiss?
                for alert in props.dismiss
                    dismisskeys.push(alert.key)
            if props.alerts?
                for alert in props.alerts
                    alertList.push(alert)
                    if alert.key
                        updatedkeys.push(alert.key)
            for alert in @state.alertList
                if alert.key not in dismisskeys and alert.key not in updatedkeys
                    alertList.push(alert)
            return {alertList: alertList}

        _dismissByKey: (key) =>
            newlist = []
            for alert in @state.alertList
                if alert.key isnt key
                    newlist.push(alert)
            @setState(alertList: newlist)

        _dismiss2: (spliceindex) =>
            newlist = []
            for alert, index in @state.alertList
                if index != spliceindex
                    newlist.push(alert)
            @setState(alertList: newlist)

        _dismiss: (spliceindex) =>
            newlist = [].concat(@state.alertList)
            newlist.splice(spliceindex, 1)
            @setState(alertList: newlist)

        render: () ->
            # Close function generator function
            generateCloser = (index) =>
                # Return a function with a dereferenced index (= a number),
                # rather than a reference to whatever index has been
                # assigned when the button is clicked. 
                return () =>
                     @_dismiss(index)

            keycounter = iter.count()
            widgets = []
            for alert, index in @state.alertList
                widget =
                    <div key={keycounter.next()}
                        className={classnames(
                            'alert': true
                            'alert-info': alert.contextcolor == 'info' or not alert.contextcolor?
                            'alert-success': alert.contextcolor == 'success'
                            'alert-warning': alert.contextcolor == 'warning'
                            'alert-danger': alert.contextcolor == 'danger'
                            'alert-dismissible': alert.dismissable or not alert.dismissable?
                        )}
                        role='alert'>
                        <strong className='mr-1'>{alert.title}</strong>
                        <span className="alerttext">
                            <gettext.Message
                                message={_(alert.message)},
                                attributes={alert.messageattrs}
                                />
                        </span>
                        {<button type="button" className="close" aria-label="Close" onClick={generateCloser(index)}>
                            <span aria-hidden="true">&times;</span>
                        </button> if alert.dismissable or not alert.dismissable?}
                    </div>
                widgets.push(widget)

            html =
            <div id='alertsdiv' className='mt-3'>
                {widgets}
            </div>

            return html

    return Alerts
