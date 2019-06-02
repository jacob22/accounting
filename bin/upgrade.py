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
import accounting.config
from bson.objectid import ObjectId
import pymongo
from pytransact import commit
import pytransact.mongo
import pytransact.utils
import pytransact.iterate
from pytransact.object.model import *
from pytransact import queryops as q
import accounting.db
import members
import blm.accounting
import blm.members

import logging
log = logging.getLogger('accounting.upgrade')


def cleanup_toirefs(database):
    log.info('Cleaning up toirefs')
    from pytransact.context import ReadonlyContext

    with ReadonlyContext(database) as ctx:
        known_toids = set(toi.id[0] for toi in blm.TO._query().run())
        for _blm in blm.__blms__.values():
            for toc in _blm._tocs.values():
                log.info('Checking %s', toc._fullname)
                query = toc._query()
                query.attrList = []
                query.clear()
                for attr in toc._attributes.values():
                    if isinstance(attr, (ToiRef, ToiRefMap)):
                        query.attrList.append(attr.name)
                        query.pushDict({attr.name: q.NotEmpty()})

                if query:
                    for toi in query.run():
                        for attrName in query.attrList:
                            save = False
                            attr = getattr(toi, attrName)
                            if isinstance(attr, ToiRef):
                                value = attr[:]
                                for ref in value[:]:
                                    if ref.id[0] not in known_toids or ref.__class__ == blm.TO:
                                        value.remove(ref)
                                        save = True
                                if len(set(value)) != len(value):
                                    value = list(pytransact.iterate.uniq(value))
                                    log.info('%s.%s has duplicate values.', toi, attrName)
                                    save = True
                                if save:
                                    log.info('Cleaning up %s.%s: %s', toi, attrName, value)
                                    pytransact.mongo.update(database.tois, {'_id': toi.id[0]},
                                                            {'$set': {attrName: value}})
                            elif isinstance(attr, ToiRefMap):
                                items = attr.items()
                                for k, ref in items:
                                    if ref.id[0] not in known_toids or ref.__class__ == blm.TO:
                                        items.remove((k, ref))
                                        save = True
                                if save:
                                    log.info('Cleaning up %s.%s: %s', toi, attrName, value)
                                    pytransact.mongo.update(database.tois, {'_id': toi.id[0]},
                                                            {'$set': {attrName: dict(items)}})



def ensure_indexes(database):
    pytransact.mongo.ensure_indexes(database)
    for attr in (
        'org',          # Accounting, ProductTag, Product, Purchase, Payment
        'accounting',   # Account, VerificationSeries, Verification
        'series',       # Verification
        'verification', # Transaction
        'purchase',     # PurchaseItem
        ):
        index = '%s.id' % attr
        log.info('Ensuring index in tois: %s', index)
        database.tois.ensure_index(index)


def cleanup_commits(database):
    unreaped = '''
5bed574719971a02fd8003d9
    '''

    ids = list(map(ObjectId, unreaped.split()))
    result = database.commits.delete_many({'_id': {'$in': ids}})
    log.info('Deleted %d stale commits.', result.deleted_count)


def main():
    database = accounting.db.connect()
    if (isinstance(database.connection, pymongo.MongoClient) and
        not pytransact.utils.is_localhost_primary(database.client)):
        sys.stderr.write('Run upgrade.py on the MongoDB primary.\n')
        raise SystemExit()

    ensure_indexes(database)
    cleanup_commits(database)
    pytransact.utils.update_bases(database, blm.accounting.User)
    pytransact.utils.update_bases(database, blm.members.PGPaymentFile)
    pytransact.utils.update_bases(database, blm.members.PGPayment)

    #cleanup_toirefs(database)

    interested = 'upgrade-%s' % ObjectId()
    with commit.CommitContext(database) as ctx:
        ops = [commit.CallBlm('accounting', 'bootstrap', []),
               commit.CallBlm('accounting', 'upgrade', []),
               commit.CallBlm('members', 'upgrade', [])]
        ctx.runCommit(ops, interested=interested)
    result, error = commit.wait_for_commit(database, interested=interested)
    assert not error, error

    log.info('Done.')


if __name__ == '__main__':
    main()
