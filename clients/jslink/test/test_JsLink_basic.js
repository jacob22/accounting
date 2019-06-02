// -*- indent-tabs-mode: nil -*-
//
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


Tests = new Deferred()

require(["jslink/JsLink"], function(JsLink) {

    function insertTestForm() {
        var node = insertTestNode()
        var uploadform = FORM({method: 'POST',
                               enctype: "multipart/form-data",
                               encoding: "multipart/form-data" })
        appendChildNodes(uploadform,
                         INPUT({'type': 'file',
                                'name': 'filearg'}))
        appendChildNodes(node, uploadform)
        return uploadform
    }

    if (typeof(console) == "undefined") {
        console = null
    }

    Tests.callback({

        test_instantiate_failure: function() {
            var jsLink = new JsLink('/not-existent')
            var d = new Deferred()

            jsLink.ready.then(function() {
                d.errback()
            }, function (err) {
                ais(err.status, 404)
                jsLink.close()
                d.callback()
            })

            return d
        },

        test_handshake: function() {
            var d = new Deferred()
            var jsLink = new JsLink('/jslink', -1)
            var calls = []
            jsLink.setupPolling = function() {
                calls.push('setupPolling')
            }
            jsLink.ready.then(function (data) {
                aok(jsLink.clientId)
                aok(jsLink.extraInfo)
                ais(data.clientId, jsLink.clientId)
                ais(data.extraInfo, jsLink.extraInfo)
                aisDeeply(calls, ['setupPolling'])
                jsLink.close()
                aok(!jsLink.clientId)
                d.callback()
            }, function() {
                d.errback()
            })

            return d
        },

        test_logout: function() {
            var calls = []
            var proto = JsLink.prototype
            var d = new Deferred()
            var p = Promise.resolve(42)
            var fakeJsLink = {
                sendReq: function (args) {
                    calls.push(args)
                    return p
                },
                close: function() {
                    d.callback()
                }
            }
            var out = proto.logout.call(fakeJsLink)
            aok(out === p)
            aisDeeply(calls, [{'type': 'logout'}])

            return d
        },

        test_deactivate: function() {
            var calls = []
            var proto = JsLink.prototype
            var d = new Deferred()
            var p = Promise.resolve(42)
            var fakeJsLink = {
                clientId: 66,
                sendReq: function (args) {
                    calls.push(args)
                    return p
                },
                close: function() {
                    d.callback()
                }
            }
            var out = proto.deactivate.call(fakeJsLink)
            aok(out === p)
            aisDeeply(calls, [{'type': 'client_deactivate', 'clientId': 66}])
        },

        test_do_poll: function() {

            var jsLink = new JsLink('/jslink', -1)
            var d = new Deferred()

            jsLink.ready.then(function (data) {
                jsLink.pollingErrors = 1
                var p = jsLink._do_poll()
                p.then(function (marker) {
                    ais(jsLink.pollingErrors, 0)
                    ais(marker, 'delivered')
                    jsLink.close()
                    d.callback()
                }).catch(function (err) {
                    d.errback(err)
                })
                return d
            }, function(reason) {
                d.errback(reason)
            })

            return d
        },

        test_restartPolling: function() {
            var proto = JsLink.prototype
            var calls = []
            var fakeJsLink = {
                stopPolling: function() { calls.push('stop') },
                setupPolling: function() { calls.push('setup') }
            }
            proto.restartPolling.call(fakeJsLink)
            aisDeeply(calls, ['stop', 'setup'])
        },

        test_stopPolling: function() {
            var proto = JsLink.prototype
            var calls = []

            var fakeJsLink = {
                window: {
                    clearTimeout: function(id) {
                        calls.push(id)
                    }
                }
            }

            proto.stopPolling.call(fakeJsLink)
            aisDeeply(calls, [])
            fakeJsLink.pollwait = 42
            proto.stopPolling.call(fakeJsLink)
            aisDeeply(calls, [42])
            ais(fakeJsLink.pollwait, null)
        },


        test__wait: function() {
            var d = new Deferred()
            var proto = JsLink.prototype
            var calls = []

            var fakeJsLink = {
                window: {
                    setTimeout: function(func, timeout) {
                        calls.push([func, timeout])
                        return 42
                    }
                }
            }

            var p = proto._wait.call(fakeJsLink, 2)
            p.then(function () { d.callback() })
            aisDeeply(calls[0][1], 2000)  // 2 -> 2000, seconds -> milliseconds
            ais(fakeJsLink.pollwait, 42)
            calls[0][0]()

            return d
        },

        test_setupPolling: function() {
            var d = new Deferred()
            var proto = JsLink.prototype
            var calls = []
            var wait_d = null
            var poll_d = null

            var fakeJsLink = {
                pollingInterval: 11,

                _wait: function(interval) {
                    var d = new Promise(function(resolve, reject) {
                        calls.push([interval, [resolve, reject]])
                    })
                    wait_d = d
                    return d
                },

                _do_poll: function() {
                    var d = new Promise(function(resolve, reject) {
                        calls.push(['poll', [resolve, reject]])
                    })
                    poll_d = d
                    return d
                },

                restartPolling: function() {
                    calls.push('restartPolling')
                }
            }


            fakeJsLink.clientId = "ID"
            fakeJsLink.nPending = 3

            delete fakeJsLink.pollwait
            proto.setupPolling.call(fakeJsLink)
            ais(calls.length, 1)
            ais(calls[0][0], 0.3)
            calls =[]

            delete fakeJsLink.pollwait
            fakeJsLink.clientId = null
            proto.setupPolling.call(fakeJsLink)
            ais(calls.length, 0)

            fakeJsLink.clientId = "ID"
            fakeJsLink.nPending = 0

            proto.setupPolling.call(fakeJsLink)
            ais(calls.length, 1)
            ais(calls[0][0], 11)
            var waitd = calls[0][1]
            calls =[]

            waitd[0]() // resolve
            wait_d.then(function () {
                ais(calls.length, 1)
                var polld = calls[0][1]
                calls = []
                polld[0]() // resolve
                poll_d.then(function () {
                    aisDeeply(calls, ['restartPolling'])
                    calls = []
                    d.callback()
                }).catch(function (err) { d.errback(err) });
            }).catch(function (err) { d.errback(err) });

            return d
        },

        // poll_errors: function(resource, expected) {
        //     var errors = []
        //     OpenEnd.Support.errorHandler = function(msg, errData) {
        //         errors.push([msg, errData])
        //     }

        //     var TestJsLink = function() {
        //     }
        //     TestJsLink.prototype = OpenEnd.JsLink.prototype
        //     var jsLink = new TestJsLink()
        //     jsLink.clientId = 10
        //     jsLink.url = resource
        //     jsLink.pollingErrors = 0
        //     jsLink._maxPollingErrors = 0
        //     jsLink.poller = OpenEnd.Support.postData

        //     var d = jsLink._do_poll()

        //     d.addBoth(function () {
        //         OpenEnd.Support.cleanup()
        //         aisDeeply(errors, [expected])
        //     })

        //     return d
        // },

        // test_do_poll_errors: function() {
        //     var expected = 'lost-connection'
        //     return Tests.poll_errors('/not-existent',
        //                              ["Connection problem: "+expected,
        //                               ['jsLinkConnectionError', expected]])
        // },

        // test_do_poll_errors_forbidden: function() {
        //     var expected = 'logged-out'
        //     return Tests.poll_errors('/forbidden',
        //                              ["Connection problem: "+expected,
        //                               ['jsLinkConnectionError', expected]])
        // },

        // test_do_poll_errors_not_allowed: function() {
        //     var expected = 'logged-out'
        //     return Tests.poll_errors('/not_allowed',
        //                              ["Connection problem: "+expected,
        //                               ['jsLinkConnectionError', expected]])
        // },

        // test_do_poll_errors_outdated: function() {
        //     var expected = 'client-outdated'
        //     return Tests.poll_errors('/outdated',
        //                              ["Connection problem: "+expected,
        //                               ['jsLinkConnectionError', expected]])
        // },

        // test_do_poll_json_error: function() {
        //     return Tests.poll_errors('/borken',
        //                              ["Broken JSON data from server",
        //                               ['jsLinkBrokenServerData', null]])
        // },

        // test_do_poll_retry: function() {
        //     var errors = []
        //     OpenEnd.Support.errorHandler = function(msg, errData) {
        //         errors.push([msg, errData])
        //     }

        //     var TestJsLink = function() { }
        //     TestJsLink.prototype = OpenEnd.JsLink.prototype
        //     var jsLink = new TestJsLink()
        //     jsLink.clientId = 10
        //     jsLink.url = '/non-existent'
        //     jsLink.pollingErrors = 0
        //     jsLink._maxPollingErrors = 10
        //     jsLink.poller = OpenEnd.Support.postData

        //     var d = new Deferred()
        //     var p = null

        //     var poll = function() {
        //         ais(errors.length, 0)
        //         p = jsLink._do_poll()
        //         p.addCallback(poll)
        //         p.addErrback(function(e) {
        //             d_fulfill(d, function() {
        //                 ais(errors.length, 1)
        //                 ais(jsLink.pollingErrors, 11 /* max + 1 */)
        //             })
        //         })
        //     }
        //     poll()
        //     return d
        // },

        test_forcePoll: function() {
            var proto = JsLink.prototype
            var calls = []
            var d = new Deferred()
            var poll_resolve = null;

            var fakeJsLink = {
                _do_poll: function() {
                    var p = new Promise(function(resolve, reject) {
                        poll_resolve = resolve
                    })
                    return p
                },
                stopPolling: function() {
                    calls.push('stop')
                },
                restartPolling: function() {
                    d.callback()
                }
            }
            proto.forcePoll.call(fakeJsLink)
            aisDeeply(calls, ['stop'])

            calls = []
            poll_resolve()
            return d
        },

        // test__startBusy_stopBusy: function() {
        //     var ctr = function() {}
        //     ctr.prototype = OpenEnd.JsLink.prototype
        //     var jsLink = new ctr()
        //     aok(jsLink._busyStarted === null)

        //     var calls = []

        //     jsLink._busyFunction = function(state) {
        //         calls.push(state)
        //     }

        //     jsLink.nPending = 0

        //     jsLink._startBusy()
        //     aisDeeply(calls, [true])
        //     jsLink.nPending++

        //     calls = []
        //     jsLink._startBusy()
        //     aisDeeply(calls, [])

        //     jsLink._stopBusy()
        //     aisDeeply(calls, [])

        //     jsLink.nPending--

        //     jsLink._stopBusy()
        //     aisDeeply(calls, [false])
        //     calls = []

        //     jsLink._busyFunction = null

        //     var ts = 1000


        //     jsLink._timestamp = function() {
        //         return ts
        //     }
        //     jsLink._submitResponseTime = function(delta) {
        //         calls.push(delta)
        //     }

        //     jsLink._startBusy()
        //     ais(jsLink._busyStarted, 1000)

        //     ts = 2600
        //     jsLink.nPending++

        //     jsLink._startBusy()
        //     ais(jsLink._busyStarted, 1000)

        //     jsLink._stopBusy()
        //     ais(jsLink._busyStarted, 1000)
        //     aisDeeply(calls, [])

        //     jsLink.nPending--
        //     jsLink._stopBusy()
        //     aok(jsLink._busyStarted === null)
        //     aisDeeply(calls, [1600])


        // },

        // timing_log: function(delta, url) {
        //     // the timing log tests are overly ambitious as they in effect
        //     // re-test OpenEnd.Support.postData() given that they integrate with the
        //     // python side - they could be rewritten as smaller unit tests if
        //     // we trust _post_data enough
        //     var TestJsLink = function() {
        //     }
        //     TestJsLink.prototype = OpenEnd.JsLink.prototype
        //     var jsLink = new TestJsLink()

        //     jsLink.submitResponseTimeURL = url
        //     var d = jsLink._submitResponseTime(delta)

        //     if (d) {
        //         d.addBoth(function (arg) {
        //             OpenEnd.Support.cleanup()
        //             ais(arg.statusText, 'OK')
        //             ais(arg.responseText, delta)
        //         })
        //     }

        //     return d
        // },

        // test__submitResponseTime_simple: function() {
        //     return Tests.timing_log(3000, '/timing_')
        // },

        // test__submitResponseTime_no_url: function() {
        //     // this doesn't strictly test that no request has been
        //     // sent.. but can't think of any better way to do that
        //     var d = Tests.timing_log(4000, null)
        //     aok(!d)
        // }
    })
})
