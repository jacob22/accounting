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

    connect: (object, signal, target) ->
        unless object.__signals__?
            object.__signals__ = {}

        unless object.__signals__[signal]?
            object.__signals__[signal] = []

        object.__signals__[signal].push(target)

    disconnect: (object, signal, target) ->
        if object.__signals__?
            if object.__signals__[signal]
                i = object.__signals__[signal].indexOf(target)
                object.__signals__[signal].splice(i, 1)

                if object.__signals__[signal].length == 0
                    delete object.__signals__[signal]

                    if Object.keys(object.__signals__).length == 0
                        delete object.__signals__

    disconnectAll: (object) ->
        delete object.__signals__

    signal: (object, signal, args...) ->
        unless object.__signals__?
            return

        unless object.__signals__[signal]?
            return

        for callback in object.__signals__[signal]
            callback.apply(object, args)
