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
import sys

try:
    import atexit
    import readline
    import rlcompleter
except ImportError:
    pass
else:
    readline.parse_and_bind("tab: complete")
    histfile = os.path.join(os.environ["HOME"], ".accounting_history")
    try:
        readline.read_history_file(histfile)
    except IOError:
        pass

    atexit.register(lambda : readline.write_history_file(histfile))

import pprint
from bson.objectid import ObjectId
import pytransact.contextbroker
from pytransact.context import ReadonlyContext
from pytransact.commit import CommitContext
from pytransact import queryops as q
from pytransact import blm
import accounting.db
import members

database = accounting.db.connect()
CB = pytransact.contextbroker.ContextBroker()


def commit():
    CB.context.runCommit([])
    CB.popContext()
    CB.pushContext(CommitContext(database))
    CB.context.setMayChange(True)

def dump(tois):
    if not isinstance(tois, (list, tuple)):
        tois = [tois]
    for toi in tois:
        try:
            print(toi.__class__, toi.id[0])
        except AttributeError:
            # Not a TOI, just pprint
            pprint.pprint(toi)
            continue

        for attrName in sorted(toi._attributes):
            print('%-20s: %s' % (attrName, toi[attrName].value))


CB.pushContext(CommitContext(database))
CB.context.setMayChange(True)

import blm.fundamental, blm.accounting, blm.members, blm.expense

if sys.argv[1:]:
    for arg in sys.argv[1:]:
        exec(open(arg, 'r').read())
else:
    try:
        import code
        console = code.InteractiveConsole(locals())
        console.interact()
    except EOFError:
        pass
