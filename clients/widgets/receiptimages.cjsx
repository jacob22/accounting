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

define ['react', 'react-dropzone', 'axios', 'gettext', 'iter', 'utils'], (
    React, Dropzone, axios, gettext, iter, utils) ->

    _ = gettext.gettext

    class ReceiptImages extends React.Component

        @defaultProps:
            newFiles: []
            oldFiles: []

        constructor: (props) ->
            super(props)
            @state =
                newFiles: props.newFiles
                oldFiles: props.oldFiles
                imageCacheCtr: 1
            # The imageCacheCtr is an arbitrary token added to the
            # image URLs when an image's URL changes. This happens
            # when already stored images are removed; then any
            # subsequent images will have their numerical index
            # decreased by one, effectively getting the previous URL
            # of their sibling.

        componentWillReceiveProps: (props) ->
            if props.oldFiles?
                @setState(oldFiles: props.oldFiles)
            if props.newFiles?
                @setState(newFiles: props.newFiles)

        addFile: (file) ->
            reader = new FileReader()
            reader.onload = (event) => @fileRead(event, file)
            reader.readAsBinaryString(file)

        fileRead: (event, file) =>
            fileData =
                file: file
                data: event.target.result

            _addFile = (fileData) =>
                newFiles = @state.newFiles.concat([fileData])
                @setState(newFiles: newFiles)
                @props.handleChange(newFiles, @state.oldFiles)

            if file.type == 'application/pdf'
                data = new FormData()
                encoded = btoa(event.target.result)
                blob = new Blob([encoded], type: file.type)
                data.append('file', blob)
                p = axios.post('/thumbnail/160/200', data,
                    responseType: 'blob'
                )
                p.then((response) =>
                    reader = new FileReader()
                    reader.onload = (event) =>
                        fileData.file.preview = event.target.result
                        _addFile(fileData)
                    reader.readAsDataURL(response.data)
                )
            else
                _addFile(fileData)

        remove: (event, fileData) =>
            # Removes an existing file
            event.stopPropagation()
            fileData.deleted = true
            @props.handleChange(@state.newFiles, @state.oldFiles)
            @setState(imageCacheCtr: @state.imageCacheCtr + 1)

        forget: (event, fileData) =>
            # Removes a newly added file
            event.stopPropagation()
            newFiles = []
            for fd in @state.newFiles
                unless fd is fileData
                    newFiles.push(fd)
            @props.handleChange(newFiles, @state.oldFiles)

        onDrop: (files) =>
            for file in files
                @addFile(file)

        render: () ->
            existing = []
            previews = []
            keys = iter.count(1)

            attribute = 'receipt'
            width = 160
            height = 200
            nocache = @state.imageCacheCtr

            for index, info of @state.oldFiles
                if info.deleted
                    continue

                url = utils.imageUrl(@props.toid, attribute, index, width, height,
                    nocache)
                style = backgroundImage: "url(#{ url })"
                remove = do (info) =>
                    (event) =>
                        @remove(event, info)
                existing.push(
                    <div key={keys.next()} className='preview' style={style} >
                        <div>
                            {<div
                                className='fa fa-remove fa-2x remove'
                                onClick={remove}/> if not @props.readOnly}
                            <div className='filename'>{info.filename}</div>
                        </div>
                    </div>
                )

            for fileData in @state.newFiles
                style = backgroundImage: "url(#{ fileData.file.preview })"
                remove = do (fileData) =>
                    (event) =>
                        @forget(event, fileData)
                previews.push(
                    <div key={keys.next()} className='preview' style={style} >
                        <div>
                            <div
                                className='fa fa-remove fa-2x remove'
                                onClick={remove} />
                            <div className='filename'>{fileData.file.name}</div>
                        </div>
                    </div>
                )

            <div>
                <Dropzone
                    className='dropzone'
                    onDrop={this.onDrop if not @props.readOnly}
                    accept='application/pdf,image/*'
                    disableClick={@props.readOnly} >
                    {<div className='instruction'>
                        {_('Upload your receipts here.')}
                     </div> if not @props.readOnly}
                    {existing}
                    {previews}
                </Dropzone>
            </div>

    return {
        ReceiptImages: ReceiptImages
    }
