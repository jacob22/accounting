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

import argparse
import os
import socket
import sys

from bson.objectid import ObjectId
from pytransact.commit import CommitContext, CallBlm, wait_for_commit
from pytransact.context import ReadonlyContext
from pytransact.queryops import NotEmpty, Empty
from accounting import config, db
import blm.accounting


def createOrders(database):
    with ReadonlyContext(database):
        for org in blm.accounting.identifyOrgsWithDueTransfers():
            supInvList = blm.accounting.identifyDueTransfers(org=org)
            with CommitContext.clone() as ctx:
                op = CallBlm('accounting', 'createSignedBgcOrder',
                             [[org], supInvList])
                interested = 'createSignedBgcOrder_org-%s_%s' % (org.id[0],
                                                                 ObjectId())
                ctx.runCommit([op], interested)
            result, error = wait_for_commit(database, interested)
            if error:
                raise error


def sendOrders(database, out):
    with ReadonlyContext(database):
        for order in blm.accounting.BgcOrder._query(
                order_signed=NotEmpty(), sent=Empty()).run():
            with CommitContext.clone() as ctx:
                op = CallBlm('accounting', 'sendBgcOrder', [[order]])
                interested = 'sendBgcOrder_order-%s_%s' % (order.id[0],
                                                           ObjectId())
                ctx.runCommit([op], interested)
            result, error = wait_for_commit(database, interested)
            if error:
                raise error
            for r in result:
                out.write('Sent {}\n'.format(r))


def main(out=sys.stdout):
    parser = argparse.ArgumentParser()
    parser.add_argument('--test-sign', action='store_true')

    args = parser.parse_args()

    signer_host = config.config.get('bankgiro', 'signer_host')
    me = socket.getfqdn()
    if args.test_sign:
        if me == signer_host and os.path.exists('/dev/bgsigner'):
            raise SystemExit('Can not test sign on signer host.')
    else:
        if me != signer_host:
            if sys.stderr.isatty():
                raise SystemExit('Must run in in test mode on non signer host.')
            else:
                raise SystemExit(1)
        if not os.path.exists('/dev/bgsigner'):
            raise SystemExit('/dev/bgsigner missing on signer host.')

    database = db.connect()
    createOrders(database)

    upload_host = config.config.get('bankgiro', 'upload_host')
    if me == upload_host:
        sendOrders(database, out=out)


if __name__ == '__main__':
    main()
