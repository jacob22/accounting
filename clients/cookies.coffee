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

define [], () ->

    set: (name, value, seconds) ->
        if seconds
            date = new Date()
            date.setTime date.getTime() + (seconds * 1000)
            expires = '; expires=' + date.toGMTString()
        else
            expires = ''
        document.cookie = name + '=' + value + expires + '; path=/'

    get: (name) ->
        nameEQ = name + '='
        ca = document.cookie.split(';')
        i = 0

        while i < ca.length
            c = ca[i]
            c = c.substring(1, c.length)  while c.charAt(0) is ' '
            return c.substring(nameEQ.length, c.length)  if c.indexOf(nameEQ) is 0
            i++
        null

    delete: (name) ->
        @set name, "", -1
