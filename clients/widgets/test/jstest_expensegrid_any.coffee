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

require ['react', 'react-dom', 'widgets/expensegrid'], (React, ReactDOM, ExpenseGrid) ->

    Tests.callback

        test_simple: () ->
            root = insertTestNode()
            comp = React.createElement(ExpenseGrid.ExpenseGrid)
            ReactDOM.render(comp, root)

        test_categories: () ->
            root = insertTestNode()
            comp = React.createElement(ExpenseGrid.ExpenseGrid, {
                categories:
                    '1':
                        name: 'foo'
                    '2':
                        name: 'bar'
            })
            node = ReactDOM.render(comp, root)
            options = getElementsByTagAndClassName('option', null,
                ReactDOM.findDOMNode(node))
            ais(options.length, 3)
            ais(options[0].value, 0)
            ais(options[1].value, '1')
            ais(options[1].text, 'foo')
            ais(options[2].value, '2')
            ais(options[2].text, 'bar')
