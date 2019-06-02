// -*- indent-tabs-mode: nil -*-
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

    var getJsLink = function(url) {
        if (!url) {
            url = '/jslink'
        }
        var jsLink = new JsLink(url)
        var d = new Deferred()

        jsLink.ready.then(function() {
            d.callback(jsLink)
        }, function (err) {
            d.errback(err)
        })

        return d
    }

    Tests.callback({

        test_makeLink: function() {
            var d = new MochiKit.Async.Deferred()
            var jsLink_def = getJsLink()
            jsLink_def.addCallback(function(jsLink) {
                d_try(d, function () {
                    var link = jsLink.makeLink('foo', {}, null, true)
                    ais(jsLink.links[link.id], link)

                    link.ready.then(function(data) {
                        d_fulfill(d, function() {
                            ais(data['new'], link.id)
                        })
                    }).catch(function (err) {
                        d.errback(err)
                    })
                })
                return jsLink
            })
            return d
        },

        // test_makeUpload: function() {
        //     if (OpenEnd.Support._is_webkit()) {
        //         return // skip on iphone for now
        //     }
        //     var node = insertTestNode()
        //     var d = new MochiKit.Async.Deferred()
        //     var jsLink_def = getJsLink('/jslink')
        //     jsLink_def.addCallback(function(jsLink) {
        //         d_try(d, function () {
        //             var uploadform = FORM({method: 'POST',
        //                                    target: 'blah',
        //                                    enctype: "multipart/form-data",
        //                                    encoding: "multipart/form-data" })
        //             appendChildNodes(uploadform,
        //                              INPUT({'type': 'file',
        //                                     'name': 'filearg'}))
        //             appendChildNodes(node, uploadform)

        //             var link = jsLink.makeUpload('foo', {'arg':['val']},
        //                                          uploadform, null, true)
        //             ais(jsLink.links[link.id], link)

        //             link.setupDeferred.addCallback(function (data) {
        //                 d_fulfill(d, function() {
        //                     ais(data['new'], link.id)
        //                 })
        //             })

        //             d_chainErr(link.setupDeferred, d)
        //         })
        //         return jsLink
        //     })
        //     return d
        // },

        // test_deliver_errorHandling: function() {
        //     var TestJsLink = function() {
        //         this.pending = {}
        //     }
        //     TestJsLink.prototype = JsLink.prototype
        //     var jsLink = new TestJsLink()

        //     var calls = []
        //     var errors = []
        //     jsLink._msg_foo = function(msg) { calls.push(msg) }
        //     jsLink._msg_bar = function(msg) { throw 'bad callback' }

        //     OpenEnd.Support.errorHandler = function(msg) { errors.push(msg) }
        //     var data = [[{'type': 'bar', 'value': 'stuff'},
        //                  {'type': 'foo', 'value': 'other stuff'}]]
        //     var res = jsLink.deliver(data)
        //     ais(res, 'delivered')
        //     aisDeeply(calls, [{'type': 'foo', 'value': 'other stuff'}])
        //     aok(errors.length == 1)
        //     aok(errors[0].indexOf('bad callback') != -1)
        //     OpenEnd.Support.cleanup()
        // },

        test_update: function() {
            var d = new MochiKit.Async.Deferred()
            var jsLink_def = getJsLink()
            jsLink_def.addCallback(function(jsLink) {
                d_try(d, function () {
                    var link = jsLink.makeLink('foo', {}, null, true)

                    link.ready.then(function(data) {
                        d_try(d, function() {
                            ais(jsLink.nPending, 0)
                            var up_d = link.update('m', {'arg': 'bar'}, true)
                            ais(jsLink.nPending, 1)
                            up_d.then(function (data) {
                                d_fulfill(d, function() {
                                    ais(data['link_update'], link.id)
                                })
                            }).catch(function(err) {
                                d.errback(err)
                            })
                        })
                    }).catch(function(err) {
                        d.errback(err)
                    })
                })
                return jsLink
            })
            return d
        },

        // test_registerBusy: function() {
        //     var jsLink = new OpenEnd.JsLink('/jslink', -1)

        //     function myfun(state) {}

        //     jsLink.registerBusy(myfun)
        //     ais(jsLink._busyFunction, myfun)
        //     jsLink.unRegisterBusy()
        //     ais(jsLink._busyFunction, null)
        // },

        // test_busyCallback: function() {
        //     var calls = []
        //     var d = new MochiKit.Async.Deferred()
        //     var jsLink_def = getJsLink()

        //     function myfun(state) {
        //         if (state) {
        //             calls.push('hepp!')
        //         } else {
        //             calls.push('hupp!')
        //         }
        //     }

        //     jsLink_def.addCallback(function(jsLink) {
        //         jsLink.registerBusy(myfun)
        //         d_try(d, function () {
        //             var link = jsLink.makeLink('foo', {}, null, true)

        //             link.setupDeferred.addCallback(function (data) {
        //                 d_try(d, function() {
        //                     ais(jsLink.nPending, 0)
        //                     var up_d = link.update('m', {'arg': 'bar'}, true)
        //                     aisDeeply(calls, ['hepp!'])
        //                     ais(jsLink.nPending, 1)

        //                     d_chainErr(up_d, d)
        //                     up_d.addCallback(function (data) {
        //                         d_fulfill(d, function() {
        //                             ais(data['link_update'], link.id)
        //                         })
        //                     })

        //                     link.deactivate('deactivate')
        //                     aisDeeply(calls, ['hepp!', 'hupp!'])
        //                 })
        //             })

        //             d_chainErr(link.setupDeferred, d)
        //         })
        //         return jsLink
        //     })
        //     return d
        // },

        test_push: function() {
            var d = new MochiKit.Async.Deferred()
            var jsLink_def = getJsLink()
            jsLink_def.addCallback(function(jsLink) {
                d_try(d, function () {
                    var link = jsLink.makeLink('foo', {}, function(args) {
                        d_fulfill(d, function() {
                            ais(jsLink.nPending, 0)
                            ais(args['arg'], 'quux')
                        })
                    })
                    ais(jsLink.nPending, 1)

                    link.ready.then(function (data) {
                        d_try(d, function() {
                            var up_d = link.update('pushback', {'arg': 'quux'})
                            up_d.catch(function(err) {
                                d.errback(err)
                            })
                        })
                    }).catch(function(err) {
                        d.errback(err)
                    })
                })
                return jsLink
            })

            return d
        },

        test_two: function() {
            var d_start = new MochiKit.Async.Deferred()
            var d_quux1 = new MochiKit.Async.Deferred()
            var d_quux2 = new MochiKit.Async.Deferred()

            var dfrs = {'quux1': d_quux1, 'quux2': d_quux2}

            var jsLink_def = getJsLink()
            var theJsLink
            jsLink_def.addCallback(function(jsLink) {
                theJsLink = jsLink

                d_try(d_start, function () {
                    var link = jsLink.makeLink('foo', {}, function(args) {
                        var which = args['arg']
                        aok(true, which)
                        dfrs[which].callback()
                    })

                    link.ready.then(function (data) {
                        d_try(d_start, function() {
                            link.update('pushback', {'arg': 'quux2'})
                            link.update('pushback', {'arg': 'quux1'})

                            d_start.callback()
                        })
                    }).catch(function(err) {
                        d_start.errback()
                    })
                })
                return jsLink
            })

            var dl = new DeferredList([d_start, d_quux1, d_quux2], false, true)
            return dl
        },

        test_new_link_pending_logic: function() {
            var jsLink = new JsLink('/nosuchurl')
            jsLink.sendReq = function() {}

            var link1 = jsLink.makeLink()
            aok(link1.id in jsLink.links)
            ais(jsLink.nPending, 1)

            var link2 = jsLink.makeLink('name', {'args': 1}, function() {}, true)
            aok(link2.id in jsLink.links)
            ais(jsLink.nPending, 1)  // Not incremented

            jsLink._resetPending(link2.id + 1)
            ais(jsLink.nPending, 1)

            jsLink._resetPending(link1.id)
            ais(jsLink.nPending, 0)

            jsLink._resetPending(link1.id)
            ais(jsLink.nPending, 0)

            jsLink._setPending(link1.id)
            ais(jsLink.nPending, 1)

            jsLink._setPending(link1.id)
            ais(jsLink.nPending, 1)
        },

        test_deliver_pending: function() {
            var jsLink = new JsLink('/nosuchurl')
            jsLink.sendReq = function() {}
            jsLink.nPending = 3
            jsLink.pending = {2:null, 3:null, 4:null}
            jsLink._msg_update2 = function(msg) {}

            var data = [{'type': 'update2', 'id': 3},
                        {'type': 'update2', 'id': 4}]
            jsLink.deliver(data)

            ais(jsLink.nPending, 1)
        },

        test_deactivate: function() {
            var d = new MochiKit.Async.Deferred()
            var jsLink_def = getJsLink()
            jsLink_def.addCallback(function(jsLink) {
                d_try(d, function () {
                    var link = jsLink.makeLink('foo', {})
                    aok(link.id in jsLink.links, "check presence")
                    ais(jsLink.nPending, 1)

                    link.ready.then(function (data) {
                        d_try(d, function() {
                            var deactivate_d = link.deactivate('deactivate')
                            aok(!(link.id in jsLink.links), "check removal")
                            ais(jsLink.nPending, 0)

                            deactivate_d.then(function (data) {
                                d_fulfill(d, function() {
                                    ais(data['link_deactivate'], link.id)
                                })

                            }).catch(function (err) {
                                d.errback(err)
                            })
                        })
                    }).catch(function (err) {
                        d.errback(err)
                    })
                })
                return jsLink
            })

            return d
        },

        test_detach: function() {
            var jsLink = new JsLink('/nosuchurl')
            jsLink.sendReq = function() {}
            var link = jsLink.makeLink()
            var calls = []
            jsLink._detach = function(id) { calls.push(id) }
            link.detach()
            aisDeeply(calls, [link.id])
        }
    })
})
