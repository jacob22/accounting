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

import accounting.config
import accounting.db
import pytransact.context
import blm.accounting


def main():
    database = accounting.db.connect()
    with pytransact.context.ReadonlyContext(database) as ctx:
        for org in blm.accounting.Org._query(_attrList=['name']).run():
            accs = blm.accounting.Accounting._query(org=org, _attrList=['start', 'end']).run()
            accs.sort(key=lambda t: t['start'])
            for acc in accs:
                print(('%24s %-34s %s - %s' % (acc.id[0], org.name[0], acc.start[0], acc.end[0])).encode('utf-8'))


if __name__ == '__main__':
    main()
