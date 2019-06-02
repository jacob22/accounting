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

jQuery(document).ready(
    function($)
    {
        function setCookie(key, value, path) {
            var cookie
            var expires = new Date();
            expires.setTime(expires.getTime() + (1 * 24 * 60 * 60 * 1000));
            cookie = key + '=' + value + ';expires=' + expires.toUTCString();
            if (path != undefined) {
                cookie = cookie + ';path=' + path
            }
            document.cookie = cookie;
        }

        function getCookie(key) {
            var keyValue = document.cookie.match('(^|;) ?' + key + '=([^;]*)(;|$)');
            return keyValue ? keyValue[2] : null;
        }

        function update_autovoid() {
            setCookie('autovoid', this.checked, '/ticket')
        }

        function refocus_input() {
            window.setTimeout(function() {
                $('#scan-box').focus()
            }, 0)
        }

        $('#scan-box').blur(refocus_input)
        $('#autovoid').change(update_autovoid)
        refocus_input()
        if (getCookie('autovoid') == 'true') {
            $('#autovoid')[0].checked = true
        }
    });

