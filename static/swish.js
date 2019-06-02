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

function submit_swish() {
    var provider = $("#swish-form [name=provider]").val()
    var purchase = $("#swish-form [name=purchase]").val()
    var phone = $("#swish-form [name=phone]").val()
    var url = "/providers/swish/charge/" + provider + "/" + purchase
    var data = {"phone": phone}
    $.post(url, data, function(response) {
        var refid = response
        var data = {"url": response}
        var tid
        var poll = function() {
            console.log('poll')
            clearTimeout(tid)
            var url = "/providers/swish/poll/" + provider + "/" + refid
            $.post(url, data, function(response) {
                console.log(response)
                if (response == 'PAID') {
                    console.log('reloading')
                    document.location = document.location
                } else if (response == 'CREATED') {
                    tid = setTimeout(poll, 1000)
                } else {
                    debugger
                }

            })
        }
        tid = setTimeout(poll, 1000)
    })
}
