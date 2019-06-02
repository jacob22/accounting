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

from bson.objectid import ObjectId
from pytransact.commit import CommitContext, CallToi, wait_for_commit
from pytransact.context import ReadonlyContext
import pytransact.utils
from accounting import db
import blm.accounting

def process(database):
    with ReadonlyContext(database):
        for order in blm.accounting.PGOrder._query(sent=[False]).run():
            with CommitContext.clone() as ctx:
                op = CallToi(order.id[0], 'send', [])
                interested = 'sendpg-%s' % ObjectId()
                ctx.runCommit([op], interested)
                result, error = wait_for_commit(database, interested)
                if error:
                    raise error


def main():
    database = db.connect()
    if pytransact.utils.is_localhost_primary(database.client):
        process(database)


if __name__ == '__main__':
    main()
