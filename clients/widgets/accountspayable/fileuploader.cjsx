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

define(['react', 'react-dropzone', 'gettext'],(React, Dropzone, gettext) ->

    _ = gettext.gettext
    
    class FileUploader extends React.Component
        onDrop: (files) =>
            file = files[0]
            reader = new FileReader()
            reader.onload = (event) => @fileRead(event, file)
            reader.readAsBinaryString(file)

        fileRead: (event, file) =>
            @props.uploadInvoiceImage(@props.toid, file, event.target.result)
        
        render: () ->
            <div className='card'>
                <Dropzone
                    className='dropzone h-100'
                    onDrop={@onDrop}
                    multiple={false}
                    disabled={@props.disabled}
                    disableClick={@props.disabled}
                    >
                    <div className='card-body' role='button'>
                        <h4 className='card-title'>
                            {_('Upload scanned invoice here.')}
                        </h4>
                        <p className='card-text'>
                            {_('Drag and drop the scanned invoice file to this box, or click to select file.')}
                        </p>
                    </div>
                </Dropzone>
            </div>
)
