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

define(['react', 'react-dom', 'axios', 'gettext', 'widgets/swish'], ->
    [React, ReactDOM, axios, gettext, Swish] = arguments

    gettext.install('client')

    provider = document.getElementById('swish-provider').value
    purchase = document.getElementById('swish-purchase').value
    is_test = document.getElementById('swish-is-test').value == 'True'

    poll = (refid) ->
        axios.post("/providers/swish/poll/#{ provider }/#{ refid }",
            url: refid
        ).then((response) ->
            status = response.data.status
            if status == 'PAID'
                document.location.reload()
            else if status == 'CREATED'
                setTimeout(poll, 1000, refid)
            else if status == 'DECLINED'
                render(null, false, true)
        ).catch((error) ->
            render(error.data)
        )

    submit = (phone, code) ->
        param = phone: phone
        if code?
            param.code = code
        axios.post("/providers/swish/charge/#{ provider }/#{ purchase }", param
        ).then((response) ->
            setTimeout(poll, 1000, response.data.id)
        ).catch((error) ->
            render(error.data)
        )
        render(null, true)


    render = (errors, submitting=false, aborted=false) ->
        ReactDOM.render(
            <Swish.Swish
                submit=submit
                errors=errors
                submitting=submitting
                aborted=aborted
                is_test=is_test
             />,
            document.getElementById('swish-react')
        )

    render()
)
