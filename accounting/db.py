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

import pymongo
import pymongo.helpers
from pytransact import mongo, utils
from . import config

pymongo.helpers.shuffled = utils.shuffle_is_sort

database = None
def connect(**kw):
    global database
    if database:
        return database
    connection = get_connection(**kw)
    dbname = config.config.get('accounting', 'mongodb_dbname')
    database = connection[dbname]
    return database


def get_connection(**kw):
    dburi = config.config.get('accounting', 'mongodb_uri')
    conn_info = pymongo.uri_parser.parse_uri(dburi)
    if 'replicaset' in conn_info['options']:
        kw.setdefault('read_preference',
                      pymongo.ReadPreference.SECONDARY_PREFERRED)
    return mongo.connect(dburi, **kw)
