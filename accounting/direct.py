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

import decimal, logging, textwrap
import simplejson as json
try:
    import urlparse                     #py2
except ImportError:
    from urllib import parse as urlparse   #py3
try:
    from cStringIO import StringIO  #py2
except ImportError:
    from io import StringIO         #py3
from bson.objectid import ObjectId
from pytransact.commit import CommitContext, wait_for_commit
from pytransact.commit import CallBlm, ChangeToi, CreateToi, DeleteToi
from pytransact.context import ReadonlyContext
from pytransact.object import model
from pytransact.utils import count_db_calls
import pytransact.queryops as qops
from .jsonserialization import JSONEncoder
import blm
from functools import reduce
log = logging.getLogger('direct')


def api(baseurl, names):
    apis = {}
    for name in names:
        blmname, name = name.split('.')
        apis.setdefault(blmname, {'url': urlparse.urljoin(baseurl, blmname),
                                  'type': 'remoting',
                                  'namespace': 'blm.%s' % blmname,
                                  'maxRetries': 0,
                                  'actions': {}})
        actions = apis[blmname]['actions']
        obj = getattr(getattr(blm, blmname), name)

        if isinstance(obj, type) and issubclass(obj, blm.TO):
            actions[name] = [{ 'name': 'create', 'len':1},
                             { 'name': 'read', 'len':1},
                             { 'name': 'update', 'len':1},
                             { 'name': 'destroy', 'len':1}]
        else:  # this should be an external method
            actions[name] = [{ 'name': 'call', 'len': len(obj.params)}]

    buf = StringIO()
    for api in apis.values():
        buf.write("Ext.ns('%s')\n" % api['namespace'])
        buf.write('Ext.Direct.addProvider(')
        json.dump(api, buf, indent=4)
        buf.write(')\n')

    return buf.getvalue()


class Router(object):

    def __init__(self, database, user):
        self.database = database
        self.user = user

    def route(self, blmname, request):
        requests = json.loads(request.data)

        if isinstance(requests, dict):
            requests = [requests]

        responses = []
        for req in requests:
            func = getattr(self, 'do_' + req['method'])
            with count_db_calls() as c:
                try:
                    result = func(blmname, req['action'], req['data'])
                except Exception:
                    log.error('Failure when processing request: %r', req)
                    raise
            if sum(c.values()) > 1000:
                log.info('req provoked > 1000 db invokations: %s, %s', req, c)
            elif c.stop - c.start > 1:
                log.info('req took more than 1 second: %s, %s', req, c)
            responses.append({
                'type':'rpc',
                'tid': req['tid'],
                'action': req['action'],
                'method': req['method'],
                'result': result
                })

        return json.dumps(responses, cls=JSONEncoder)

    def do_call(self, blmname, methodname, params):
        interested = 'direct-call-%s' % ObjectId()
        with CommitContext(self.database, self.user) as ctx:
            if params is None:
                params = []
            for i, param in enumerate(params):
                if not isinstance(param, list):
                    params[i] = [param]
            op = CallBlm(blmname, methodname, params)
            ctx.runCommit([op], interested=interested)

        with ReadonlyContext(self.database, self.user) as ctx:
            result, error = wait_for_commit(self.database, interested)
            assert not error, error
            return result[0]

    def do_create(self, blmname, tocname, params):
        tocname = '%s.%s' % (blmname, tocname)
        toc = blm.getTocByFullname(tocname)
        interested = 'direct-create-%s' % ObjectId()
        with CommitContext(self.database, self.user) as ctx:
            createops = params[0]
            if isinstance(createops, dict):
                createops = [createops]
            ops = []
            for attrdata in createops:
                toid = list(filter(None, attrdata.pop('id', []) + [ObjectId()]))[0]
                self._toidata_from_json(toc, attrdata)
                op = CreateToi(tocname, toid, attrdata)
                ops.append(op)
            ctx.runCommit(ops, interested=interested)
        with ReadonlyContext(self.database, self.user) as ctx:
            result, error = wait_for_commit(self.database, interested)
            if error:
                return {'success': False}
            for i, toid in enumerate(result):
                query = toc._query(id=toid)
                query.attrList = toc._attributes.keys()
                toi, = query.run()
                result[i] = self._get_toidata(toi, query.attrList)
            return {'success': True, 'tois': result}

    def do_destroy(self, blmname, tocname, params):
        assert len(params) == 1
        deleteops = params[0]
        if isinstance(deleteops, dict):
            deleteops = [deleteops]
        ids = sum((attrdata['id'] for attrdata in deleteops), [])
        with CommitContext(self.database, self.user) as ctx:
            ops = []
            for toi in blm.TO._query(id=ids).run():
                ops.append(DeleteToi(toi))
            interested = 'direct-destroy-%s' % ObjectId()
            ctx.runCommit(ops, interested=interested)
        result, error = wait_for_commit(self.database, interested)
        return {'success': not error}

    def do_read(self, blmname, tocname, params):
        tocname = '%s.%s' % (blmname, tocname)
        result = []
        assert len(params) == 1
        params, = params
        success = True

        with ReadonlyContext(self.database, self.user) as ctx:
            toc = blm.getTocByFullname(tocname)
            query_params = {}

            if 'id' in params:
                query_params['id'] = params['id']
                if query_params['id'] is None:
                    success = False
            for filter in params.get('filter', []):
                try:
                    attr, cond = filter2cond(filter)
                    query_params[attr] = cond
                except IgnoreFilter:
                    pass
            if 'query' in params:
                if isinstance(params['query'], dict):
                    query_params.update(params['query'])

            # xxx
            # We need a real design for complex queries, this exists
            # to support transaction text searching, see
            # Bokf.lib.TransactionTextEditor
            for attr, string in params.get('like', {}).items():
                query_params[attr] = qops.Ilike(string)

            # find first sorter, or None
            sort = reduce(lambda x, y: x, params.get('sort', []) + [None])

            query = toc._query(**query_params)

            if sort and sort['property'] != 'id':
                query.attrList = params['attributes'] + [sort['property']]
            else:
                query.attrList = params['attributes']

            tois = query.run()

            if sort:
                if sort['property'] == 'id':
                    key = lambda toi: toi[sort['property']]
                else:
                    key = lambda toi: toi[sort['property']].value

                tois.sort(key=key, reverse=sort['direction'] == 'DESC')

            for toi in tois:
                result.append(self._get_toidata(toi, params['attributes'],
                                                params.get('polymorph', False)))

        return {'success': success, 'tois': result}

    def do_update(self, blmname, tocname, params):
        tocname = '%s.%s' % (blmname, tocname)
        interested = 'direct-update-%s' % ObjectId()
        with CommitContext(self.database, self.user) as ctx:
            updateops = params[0]
            if isinstance(updateops, dict):
                updateops = [updateops]
            opdata = {}
            toc = blm.getTocByFullname(tocname)
            attrList = set()

            for attrdata in updateops:
                toid, = map(ObjectId, attrdata.pop('id'))
                self._toidata_from_json(toc, attrdata)
                opdata[toid] = attrdata
                attrList.update(attrdata)

            q = toc._query(id=[toid for toid in opdata])
            q.attrList = attrList
            ops = []
            for toi in q.run():
                op = ChangeToi(toi, opdata[toi.id[0]])
                ops.append(op)
            ctx.runCommit(ops, interested=interested)
        with ReadonlyContext(self.database, self.user) as ctx:
            result, error = wait_for_commit(self.database, interested)
            if error:
                return {'success': False, 'message': error}
            for i, (toid, sentdata) in enumerate(zip(result, updateops)):
                query = toc._query(id=toid)
                query.attrList = sentdata.keys()
                toi, = query.run()
                result[i] = self._get_toidata(toi, query.attrList)
            return {'success': True, 'tois': result}

    @staticmethod
    def _toidata_from_json(toc, attrdata):
        for attrName, value in attrdata.items():
            attr = getattr(toc, attrName)
            if not isinstance(attr, model.MapAttribute):
                attrdata[attrName] = [v for v in value if v is not None]
            if isinstance(attr, model.Decimal):
                attrdata[attrName] = [decimal.Decimal(v) / 100
                                      for v in value]
            if isinstance(attr, model.DecimalMap):
                attrdata[attrName] = dict(
                    (k, decimal.Decimal(v) / 100)
                    for (k, v) in value.items())

    @staticmethod
    def _get_toidata(toi, attrList, polymorph=False):
        toidata = {'id': list(map(str, toi.id))}
        if polymorph:
            toidata['_toc'] = toi._fullname
        for attrname in attrList:
            try:
                attr = getattr(toi, attrname)
            except AttributeError:
                if polymorph: continue
                raise

            value = attr.value
            if isinstance(attr, model.Enum):
                value = list(map(str, attr.value))
            elif isinstance(attr, model.ToiRef):
                value = [str(t.id[0]) for t in attr.value]
            elif isinstance(attr, model.ToiRefMap):
                value = {key: str(t.id[0]) for (key, t) in attr.items()}

            # Decimals are sent as integers appropriately scaled
            elif isinstance(attr, model.Decimal):
                value = [int((v*100).quantize(1)) for v in attr.value]
            elif isinstance(attr, model.DecimalMap):
                value = dict((k, int((v*100).quantize(1))) for (k,v)
                             in attr.value.items())

            toidata[attrname] = value
        return toidata


class IgnoreFilter(Exception):
    pass


def filter2cond(filter):
    try:
        attr = filter['property']
        value = filter['value']
    except KeyError:
        raise IgnoreFilter

    if isinstance(value, dict):
        op = value['op']
        if op == 'Empty':
            value = qops.Empty()
        elif op == 'NotEmpty':
            value = qops.NotEmpty()
        elif op == 'NotIn':
            value = qops.NotIn(value['value'])
        elif op == 'GreaterEq':
            value = qops.GreaterEq(value['value'])
        elif op == 'LessEq':
            value = qops.LessEq(value['value'])
        elif op == 'Between':
            value = qops.Between(value['value'])
        else:
            raise ValueError('Unknown filter op: %r' % op)

    return attr, value
