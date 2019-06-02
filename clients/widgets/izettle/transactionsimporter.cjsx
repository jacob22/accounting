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

define(['react', 'react-dropzone', 'classnames', 'gettext'],(React, Dropzone, classnames, gettext) ->

    _ = gettext.gettext
    
    class TransactionsImporter extends React.Component
        constructor: (props) ->
            super(props)
            @state={working: false}

        onDrop: (files) =>
            file = files[0]
            @setState('filename': file.name)
            reader = new FileReader()
            reader.onload = @fileRead
            reader.readAsBinaryString(file)

        fileRead: (event) =>
            callback = () =>
                @setState(working: false)
            @setState(working: true)
            @props.importTransactions(@state.filename, event.target.result, callback)
        
        render: () ->
            <div>
                <fieldset disabled={@state.working}>
                    <Dropzone
                        className='dropzone'
                        onDrop={@onDrop}
                        multiple=false >
                        <div className='card card-body instruction' role='button'>
                            <div className={classnames(
                                'has-spinner': true
                                'spinner-overlay': true
                                'd-none': not @state.working
                                'active': @state.working
                                )}>
                                <span className='spinner'>
                                    <i className="fa fa-spinner fa-spin" aria-hidden="true"></i> {_('Importing... ')}
                                </span>
                            </div>
                            <h4 className='card-title'>
                                {_('Upload iZettle transactions file here.')}
                            </h4>
                            <p className='card-text'>
                                {_('Drag and drop the Excel transactions file to this box, or click to select file.')}
                            </p>
                        </div>
                    </Dropzone>
                </fieldset>
            </div>
)
