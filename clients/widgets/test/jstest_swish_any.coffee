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
require(['react', 'react-dom', 'widgets/swish'], ->
    [React, ReactDOM, Swish] = arguments
    ReactTestUtils = React.addons.TestUtils

    render = (Component, props={}) ->
        root = insertTestNode()
        component = React.createElement(Component, props)
        element = ReactDOM.render(component, root)
        return [root, component, element]


    Tests.callback(

        test_SwishButton: () ->
            [root, component, element] = render(Swish.SwishButton)

            button = ReactTestUtils.findRenderedDOMComponentWithTag(element, 'button')
            aok(!button.disabled)
    )
)
