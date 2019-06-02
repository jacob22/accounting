#!/usr/bin/env python

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

import gettext, locale, os, re, sys
from members.billing import Billing

def main(argv=sys.argv):
    year = argv[1]
    if not re.match('^\d{4}$', year):
        raise ValueError

    os.environ['LANGUAGE'] = 'sv_SE.UTF-8'  # for gettext
    locale.setlocale(locale.LC_ALL, 'sv_SE.UTF-8')
    gettext.bindtextdomain(
        'accounting',
        os.path.join(os.path.dirname(__file__), '..', 'locale'))
    gettext.textdomain('accounting')

    billing = Billing()
    billing.connect()
    billing.bootstrap_products()
    billing.process(year)


if __name__ == '__main__':
    main()
