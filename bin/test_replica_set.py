#!/usr/bin/env python
from __future__ import print_function

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

# Check that the mongodb cluster is up and accepting queries.
#
# Relies on python exiting with an exit code when unhandled exception
# is raised.

import sys, time
from accounting import db


def is_up():
    database = db.connect(
        connectTimeoutMS=1000,
        serverSelectionTimeoutMS=2000,
    )
    try:
        # Force connection to db by running query, as MongoClient
        # connects lazily
        database.foo.find().next()
    except StopIteration:
        pass
    conn = database.client
    if conn.primary is None:
        raise RuntimeError('No primary')
    if {conn.primary} | conn.secondaries | conn.arbiters != conn.nodes:
        raise RuntimeError('Confusing node information. Primary: %s, '
                           'secondaries: %s, arbiters: %s, nodes: %s' % (
                               conn.primary, conn.secondaries, conn.arbiters,
                               conn.nodes))
    print(':'.join(map(str, conn.primary)))


def wait(timeout, interval=1):
    stop = time.time() + timeout
    while time.time() < stop:
        try:
            is_up()
        except Exception as e:
            time.sleep(interval)
        else:
            return
    print(e, file = sys.stderr)
    raise SystemExit('Timeout, replica set is not available.')


if __name__ == '__main__':
    if sys.argv[1:]:
        wait(int(sys.argv[1]))
    else:
        is_up()


def test_dummy():
    """I exist so that py.test doesn't get annoyed by the fact that it
    finds a file that matches the test_*.py pattern, but doesn't
    contain any tests."""
