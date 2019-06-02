# Copyright 2019 Open End AB
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import py
import uuid

root = os.path.dirname(os.path.dirname(__file__))

# hack - assume http if explicit port is given
if ':' in py.test.config.option.domain:
    url = 'http://%s/' % py.test.config.option.domain
else:
    url = 'https://%s/' % py.test.config.option.domain

def emailaddr():
    return 'autotest+%s@openend.se' % uuid.uuid4()

def setup_module(module):
    if not py.test.config.option.run_integration_tests:
        py.test.skip('Skipping integration tests')


def accenv(arg):
    return 'PYTHONPATH=/root/accounting %s' % arg

def clientcmd(arg):
    return accenv('/root/accounting/bin/client.py %s' % arg)
