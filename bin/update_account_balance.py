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

import os
import signal
import multiprocessing
import accounting.config
import accounting.db
from pytransact import commit
from pytransact import context
from pytransact import iterate
import blm.accounting
log = accounting.config.getLogger('accounting.upgrade')

signal.signal(signal.SIGCLD, signal.SIG_IGN)

def check(pipe):
    database = accounting.db.connect()
    n = 0
    while True:
        interested = pipe.recv()
        if interested is None:
            break
        result, error = commit.wait_for_commit(database, interested=interested)
        if error:
            print 'Could not update balance for %s' % interested
            print error
        else:
            print 'Commit %d successful: %s' % (n, interested)
        n += 1

def main(pipe):
    database = accounting.db.connect()

    with context.ReadonlyContext(database) as ctx:
        print 'Fetching accounts and balances.'
        accounts = [account for account in
                    blm.accounting.Account._query(
                        _attrList=['balance', 'balance_quantity']).run()]
        balances = dict((toi.id[0], (toi.balance[0], toi.balance_quantity[0]))
                        for toi in accounts)
        accounts = [account.id[0] for account in accounts]

    for n, toids in enumerate(iterate.chunks(accounts, 100)):
        interested = 'update-%s' % toids[0]
        print 'Creating commit %d for %s' % (n, interested)
        with commit.CommitContext(database) as ctx:
            blm.accounting.Account._query(id=toids, _attrList=[
                'opening_balance', 'opening_quantity',
                'balance', 'quantity']).run()
            ops = []
            for toid in toids:
                op = commit.CallToi(toid, 'updateBalance', [])
                ops.append(op)
            ctx.runCommit(ops, interested=interested)
        pipe.send(interested)
    pipe.send(None)
    pipe.close()

    with context.ReadonlyContext(database) as ctx:
        print 'Fetching accounts and balances for verification.'
        accounts = [account for account in
                    blm.accounting.Account._query(
                        _attrList=['balance', 'balance_quantity']).run()]
        new_balances = dict((toi.id[0], (toi.balance[0], toi.balance_quantity[0]))
                            for toi in accounts)

    for account, old in balances.iteritems():
        new = new_balances.get(account)
        if new != old:
            print 'DIFF: %s %r -> %r' % (account, old, new)


if __name__ == '__main__':
    parent_conn, child_conn = multiprocessing.Pipe()

    verify_proc = multiprocessing.Process(target=check, args=(child_conn,))
    verify_proc.start()
    main(parent_conn)
    verify_proc.join()
