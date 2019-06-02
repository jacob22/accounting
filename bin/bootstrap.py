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
import pymongo
from pytransact.commit import CallBlm, CommitContext, wait_for_commit
from accounting import db
import blm.accounting


def main():
    database = db.connect()
    interested = 'bootstrap-%s' % ObjectId()
    with CommitContext(database) as ctx:
        ctx.set_read_preference(pymongo.ReadPreference.PRIMARY)
        op = CallBlm('accounting', 'bootstrap', [])
        ctx.runCommit([op], interested=interested)
    result, error = wait_for_commit(database, interested)
    if error:
        raise error


if __name__ == '__main__':
    main()
