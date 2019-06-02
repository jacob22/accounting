#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

import cStringIO
import datetime
import pprint
import bson
from bson.objectid import ObjectId
import pytransact.blm
import pytransact.commit
import pytransact.context
import accounting.db
import members
import blm.accounting, blm.members


def connect():
    return accounting.db.connect()


def is_empty(commit):
    return (commit.get('generation', 0) == 0 and
            commit.get('interested') is None and
            commit.get('traceback') is None and
            commit.get('error') is None)


def get_data(commit):
    try:
        blob = commit['_griddata']
    except KeyError:
        return

    return bson.BSON(commit['_griddata'].getvalue()).decode()


def analyze_commit_done(commit):
    if commit['results'] == [ObjectId('531f547726ccb366100003c0')]:
        # Strange empty commit from 2014-03-11, all with the same return value.
        # The return value points to a non existing TOI
        return 'delete'

    if commit['results'] == [ObjectId('52e3e82226ccb346af0000dc')]:
        # Returns the UG for the org "Ett företags Namn", nothing else
        # interesting
        return 'delete'

    if commit['_id'] == ObjectId('55df0020a979ef197c742d2c'):
        # Old transaction text index query
        return 'delete'

    if commit['_id'] == ObjectId('53201cba67e5484d5e000003'):
        # Old AttrPermError (Accounting.start) from 2014-03-12
        return 'delete'

    if commit['error'] is None:
        if str(commit['_id'].generation_time)[:10] < '2016-03-01':
            # Old unreaped commits
            return 'delete'


def analyze_commit_failed(commit):
    if commit['_id'] == ObjectId('53f84b4e19971a7e84000b45'):
        # Failed accounting.accountingFromTemplate() from 2014-08-23
        return 'delete'

    data = get_data(commit)
    if data is not None:
        ops = data['operations']
        if (len(ops) == 1 and
            isinstance(ops[0], pytransact.commit.ChangeToi) and
            ops[0].attrData.keys() == ['lastAccess']):
            # Failed set lastAccess
            return 'delete'

    else:
        if commit['interested'].startswith('stripe-balance.available-evt_'):
            if commit['_id'] in {ObjectId('57021b8567e548203545631c'),
                                 ObjectId('5701efb167e5482035456316'),
                                 ObjectId('580b0d2c67e54873bdea0882'),
                                 ObjectId('5701e4e967e5482035456313'),
                                 ObjectId('580b5d1167e54873bdea088c'),
                                 ObjectId('5701d62da979ef764e27ed9d')}:
                # Stripe webhooks that lead to empty commits
                return 'delete'
        if commit['interested'].startswith('stripe-transfer.paid-evt_'):
            if commit['_id'] in {ObjectId('5702131567e5482035456319')}:
                # Stripe webhooks that lead to empty commits
                return 'delete'
    if commit['_id'] in {ObjectId('580b2402a979ef77ab8392f9'),
                         ObjectId('560399f926ccb3150be590be'),
                         ObjectId('580b1fe0a979ef77aad12a19'),}:
        # Failed invitation accept, but the users has managed to accept now
        return 'delete'

    if commit['_id'] in {ObjectId('55ffb28619971a6dcc4a3897'),
                         ObjectId('57f7bad8a979ef301eb20961')}:
        # Failed edit of verification, but user has apparently tried again
        return 'delete'

    if commit['_id'] in {ObjectId('580a7fab67e5486f63edca7a')}:
        # Failed PG import, has been imported now
        return 'delete'


def analyze_commit_new(commit):
    data = get_data(commit)
    ops = data['operations']
    if (len(ops) == 1 and
        isinstance(ops[0], pytransact.commit.ChangeToi)):
        if ops[0].attrData.keys() == ['lastAccess']:
            # print 'Commit %s is a lastAccess only commit' % commit['_id']
            return 'delete'
        else:
            if ops[0].toi.id[0] == ObjectId('53160c9319971a156c000016'):
                # This TOI does not exist.
                return 'delete'


def analyze_commit(commit):
    return {
        'done': analyze_commit_done,
        'failed': analyze_commit_failed,
        'new': analyze_commit_new
    }[commit['state']](commit)


def iter_commits(db):
    with pytransact.context.ReadonlyContext(db):
        for commit in db.commits.find():
            if analyze_commit(commit) == 'delete':
                command = 'delete'
            else:
                command = None
            assert command == 'delete'
            yield command, commit['_id']


def delete_commits(db, commits):
    db.commits.delete_many({'_id': {'$in': list(commits)}})



def main():
    db = connect()
    delete = set()
    for command, commit in iter_commits(db):
        if command == 'delete':
            delete.add(commit)

    if delete:
        print('\n'.join(map(str, delete)))
    #delete_commits(db, delete)


if __name__ == '__main__':
    main()
