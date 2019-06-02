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

import itertools
import sys
import pytransact.commit
import pytransact.context
from pytransact.queryops import Empty
import accounting.db
import members
import blm.accounting
import blm.members


def fixproducts(database, org):
    with pytransact.context.ReadonlyContext(database) as ctx:
        try:
            org, = blm.accounting.Org._query(id=org).run()
        except ValueError:
            org = blm.accounting.Org._query(name=unicode(org, 'utf8')).run()[0]

        accounts = blm.accounting.Account._query(
            accounting=org.current_accounting).run()
        assert accounts

        accounts = itertools.cycle(accounts)

        if (set(org.subscriptionLevel) &
            set([blm.accounting.IzettleProvider.requiredSubscriptionLevel])):
            op = pytransact.commit.ChangeToi(org, {
                'subscriptionLevel': [
                    blm.accounting.IzettleProvider.requiredSubscriptionLevel
                ]
            })
            interested = 'raise-subscription-level-%s' % org.id[0]
            with pytransact.commit.CommitContext.clone(ctx) as cctx:
                cctx.runCommit([op], interested=interested)
            result, error = pytransact.commit.wait_for_commit(database,
                                                              interested)
            assert not error

        if not blm.accounting.IzettleProvider._query(org=org).run():
            series = [
                s.name[0] for s in
                blm.accounting.VerificationSeries._query(
                    accounting=org.current_accounting).run()
            ] + ['A']
            op = pytransact.commit.CreateToi(
                'accounting.IzettleProvider',
                None,
                {
                    'org': org.id[:],
                    'account': accounts.next().number[:],
                    'fee_account': accounts.next().number[:],
                    'cash_account': accounts.next().number[:],
                    'series': series[:1],
                })
            interested = 'create-provider-%s' % org.id[0]
            with pytransact.commit.CommitContext.clone(ctx) as cctx:
                cctx.runCommit([op], interested=interested)
            result, error = pytransact.commit.wait_for_commit(database,
                                                              interested)
            assert not error

        for product in blm.members.IzettleProduct._query(
                org=org, accountingRules=Empty()).run():
            op = pytransact.commit.ChangeToi(product, {
                'accountingRules': {
                    str(accounts.next().number[0]): product.izPrice[0] / 2,
                    str(accounts.next().number[0]): product.izPrice[0] / 2,
                }
            })
            interested = 'update-accountingRules-%s' % product.id[0]
            with pytransact.commit.CommitContext.clone(ctx) as cctx:
                cctx.runCommit([op], interested=interested)
            result, error = pytransact.commit.wait_for_commit(database,
                                                              interested)
            print 'Updated %s: %s' % (product.name[0], result)
            assert not error


def main():
    database = accounting.db.connect()
    fixproducts(database, sys.argv[1])


if __name__ == '__main__':
    main()
