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
from pytransact.commit import CommitContext, ChangeToi, wait_for_commit
import accounting.db
import accounting.luhn
import blm.accounting


def addocr(database, orgnum, pgnum_real, pgnum):
    orgnum = blm.accounting.normalize_orgnum(orgnum)
    pgnum = blm.accounting.normalize_pgnum(pgnum)
    pgnum_real = blm.accounting.normalize_pgnum(pgnum_real)

    if accounting.luhn.luhn_checksum(pgnum):
        raise ValueError('Checksum mismatch: %s' % pgnum)

    with CommitContext(database) as ctx:
        interested = 'addocrgpg-%s' % ObjectId()
        org, = blm.accounting.Org._query(orgnum=orgnum).run()
        pgp, = blm.accounting.PlusgiroProvider._query(
            org=org, pgnum_real=pgnum_real).run()
        op = ChangeToi(pgp, {'pgnum': [pgnum]})
        ctx.runCommit([op], interested=interested)
    result, error = wait_for_commit(database, interested)
    if error:
        raise error


def main(args):
    database = accounting.db.connect()
    addocr(database, *args)


if __name__ == '__main__':
    import sys
    main(sys.argv[1:])
