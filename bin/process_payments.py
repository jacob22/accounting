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

import sys
if sys.version_info < (3,0,0):
    PYT3 = False
else:
    PYT3 = True
import os, shutil
from bson.objectid import ObjectId
import pymongo
from pytransact.context import ReadonlyContext
from pytransact.commit import CommitContext, CallToi, CreateToi, wait_for_commit
import accounting.db, accounting.config
import members
import blm.members


def archive_file(fname):
    archive = accounting.config.config.get('plusgiro', 'archive')
    shutil.move(fname, archive)


def process_file(database, fname):
    if PYT3:
        with open(fname, 'r', encoding='iso-8859-1') as f:
            data = f.read()
    else:
        with open(fname, 'r') as f:
            data = f.read()

    interested_id = ObjectId()

    with CommitContext(database) as ctx:
        interested = 'import-payment-%s' % interested_id
        op = CreateToi('members.PGPaymentFile', None,
                       attrData=dict(fileName=[os.path.basename(fname)],
                                     data=[data]))
        ctx.runCommit([op], interested=interested)
        (toid,), error = wait_for_commit(database, interested=interested)
        if error:
            raise error

    with CommitContext(database) as ctx:
        interested = 'process-payment-file-%s' % interested_id
        op = CallToi(toid, 'process', [])
        ctx.runCommit([op], interested=interested)
        _, error = wait_for_commit(database, interested=interested)
        if error:
            raise error

    with ReadonlyContext(database):
        for paymentFile in blm.members.PGPaymentFile._query(id=toid).run():
            for payment in paymentFile.payments:
                paymentId = payment.id[0]
                interested = 'match-payment-%s-%s' % (interested_id, paymentId)
                with CommitContext(database) as ctx:
                    op = CallToi(paymentId, 'match', [])
                    ctx.runCommit([op], interested)
                _, error = wait_for_commit(database, interested=interested)
                if error:
                    raise error

    with ReadonlyContext(database):
        for payment in blm.members.PGPayment._query(paymentFile=toid).run():
            paymentId = payment.id[0]
            interested = 'send-payment-confirmation-%s-%s' % (
                paymentId, ObjectId())
            with CommitContext(database) as ctx:
                op = CallToi(paymentId, 'sendConfirmationEmail', [])
                ctx.runCommit([op], interested)
            _, error = wait_for_commit(database, interested=interested)
            if error:
                raise error

    archive_file(fname)


def main(args):
    database = accounting.db.connect()
    database = database.client.get_database(
        database.name, read_preference=pymongo.ReadPreference.PRIMARY)
    process_file(database, args[1])


if __name__ == '__main__':
    import sys
    main(sys.argv)
