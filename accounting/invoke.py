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

from pytransact import commit, context
from bson.objectid import ObjectId
from werkzeug.exceptions import InternalServerError
import flask, logging
try:
    import httplib                      #py2
except ImportError:
    from http import client as httplib  #py3
import blm

log = logging.getLogger('invoke')

def _invoke(request, database, user, op):
    interested = 'invoke-%s' % ObjectId()

    with commit.CommitContext(database, user) as ctx:
        cmt = ctx.runCommit([op], interested=interested)

    result, error = commit.wait_for_commit(
        database, interested, onfail=InternalServerError())

    if error:
        raise error

    if result[0]:
        result = result[0][0]

    resp = flask.jsonify(**result)
    return resp

def _get_params(request, method):
    if request.mimetype == 'application/json':
        params = flask.json.loads(request.data)
        return [params.get(attr.name) for attr in method.params]
    else:
        return [request.values.getlist(attr.name) for attr in method.params]


def invoke(request, database, user, blmName, methodName):
    try:
        method = getattr(getattr(blm, blmName), methodName)
    except AttributeError:
        log.debug('No such method: %s.%s', blmName, methodName)
        flask.abort(httplib.NOT_FOUND)

    params = _get_params(request, method)
    op = commit.CallBlm(blmName, methodName, params)
    return _invoke(request, database, user, op)


def invoke_toi(request, database, user, toid, methodName):
    with context.ReadonlyContext(database, user):
        try:
            toi, = blm.TO._query(id=toid).run()
            method = getattr(toi, methodName)
        except (ValueError, AttributeError):
            log.debug('No such toi method: %s.%s', toid, methodName)
            flask.abort(httplib.NOT_FOUND)

    params = _get_params(request, method)
    op = commit.CallToi(toid, methodName, params)
    return _invoke(request, database, user, op)
