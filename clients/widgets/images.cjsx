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

define ['react', 'utils'], (React, utils) ->

    class Images extends React.Component

        constructor: (props) ->
            super props

        render: () ->
            previews = []
            {toid, attribute, width, height} = @props

            for index, info of @props.imageInfo
                content_type = info.content_type
                url = utils.imageUrl(toid, attribute, index,
                    @props.nocache)
                thumb = utils.imageUrl(toid, attribute, index, width, height,
                    @props.nocache)
                preview = <img src={thumb} />
                anchor = <a key={index} href={url} target='_blank'>{preview}</a>
                previews.push(anchor)
            <div className='images text-xs-center'>
                {previews}
            </div>
