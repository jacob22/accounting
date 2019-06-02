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

import py
import urllib
import sys
if sys.version_info >= (3,0):
    PYT3 = True
    import urllib.parse
else:
    PYT3 = False
    import urlparse

from . import support


@py.test.mark.usefixtures('cluster')
def test_is_running():
    if PYT3:
        response = urllib.request.urlopen(support.url)
    else:
        response = urllib.urlopen(support.url)
    assert response.getcode() == 200


@py.test.mark.usefixtures('cluster')
def test_static_files():
    if PYT3:
        url = urllib.parse.urljoin(support.url, 'static/login.css')
        response = urllib.request.urlopen(url)
    else:
        url = urlparse.urljoin(support.url, 'static/login.css')
        response = urllib.urlopen(url)
    assert response.getcode() == 200
