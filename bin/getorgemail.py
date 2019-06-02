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

# This must be runnable without any special environment set up

import sys, os.path
import pytransact

try:
    import accounting
except ImportError:
    pathdir = os.path.dirname(os.path.dirname(sys.argv[0]))
    sys.path.append(pathdir)

import pymongo

from bson.objectid import ObjectId
from pytransact import blm, mongo, context
import accounting.db

import blm.fundamental, blm.accounting

def main(args):
    database = accounting.db.connect()

    with context.ReadonlyContext(database) as ctx:
        for org in args:
            org = blm.accounting.Org._query(id=ObjectId(org))
            org = org.run()
            if org:
                print ', '.join(org[0].email)


if __name__ == '__main__':
    main(sys.argv[1:])
