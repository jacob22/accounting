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

define ['functools'], (functools) ->

    _cleanLinkAndCallback = (linkCont, callback, result) ->
        linkCont.link.detach()
        if callback?
            return callback(result)
        else if result.error
            null  # xxx


    _wrapMethodCall = (methodName, makeLink, callback) ->
        linkCont = {}
        lowprio = if callback? then false else true
        decoratedCallback = functools.partial(_cleanLinkAndCallback, linkCont, callback)
        linkCont.methodName = methodName
        linkCont.link = makeLink(decoratedCallback, lowprio)
        return linkCont.link


    callBlmMethod = (jsLink, blmMethod, args, callback) ->
        nameParts = blmMethod.split('.')
        params =
            blmName: nameParts[0]
            methodName: nameParts[1]
            args: args

        makeLink = functools.partial(jsLink.makeLink, 'CallMethod', params: params)
        return _wrapMethodCall(blmMethod, makeLink, callback)


    callToiMethod = (jsLink, toid, methodName, args, callback) ->
        params =
            toid: toid
            methodName: methodName
            args: args
        makeLink = functools.partial(jsLink.makeLink, 'CallMethod', params: params)
        return _wrapMethodCall(methodName, makeLink, callback)


    commit =
        callBlmMethod: callBlmMethod
        callToiMethod: callToiMethod
