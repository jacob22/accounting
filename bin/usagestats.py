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

import time

from pytransact.query import *
from pytransact.context import ReadonlyContext
from accounting import db, config
import blm.accounting

log = config.getLogger('usagestats')

def main():
    database = db.connect()
    database.local.foo.find().count()  # force connection to initialize
    with ReadonlyContext(database):
        users = len(blm.accounting.User._query().run())
        activeusers = len(blm.accounting.User._query(
                lastAccess=Greater(time.time() - 24*60*60)).run())
        orgs = len(blm.accounting.Org._query().run())
        suborgs = len(blm.accounting.Org._query(
                subscriptionLevel='subscriber').run())

        log.info('users: %(users)s active: %(activeusers)s orgs: %(orgs)s subscribers: %(suborgs)s',
                 locals())

if __name__ == '__main__':
    main()
