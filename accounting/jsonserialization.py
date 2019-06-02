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

import decimal
from bson.objectid import ObjectId
import flask.json

from pytransact import query
from pytransact.object import attribute
from pytransact.object import to
from bson import objectid
import pytransact.exceptions
from pytransact.difftoi import DiffTOI

opValueKind = {
    'Empty': None,
    'NotEmpty': None,
    'Exact': 'list',
    'In': 'list',
    'NotIn': 'list',
    'NoneOf': 'list',
    'Fulltext': 'single',
    'Like': 'single',
    'NotLike': 'single',
    'Ilike': 'single',
    'NotIlike': 'single',
    'Less': 'single',
    'LessEq': 'single',
    'GreaterEq': 'single',
    'Greater': 'single',
    'Between': 'between'
     # map stuff:  'HasKey', 'LacksKey', 'NotIlikeMap', 'InMap',
     #             'LikeMap', 'NotLikeMap', 'IlikeMap', 'NoneOfMap'
     # 'Readable'
    }


class JSONDecoder(flask.json.JSONDecoder):

    def __init__(self, **kw):
        kw['object_hook'] = objectDecode
        super(JSONDecoder, self).__init__(**kw)


def objectDecode(dic):
    if '_cls_' not in dic:
        return dic

    cls = dic['_cls_']

    import blm
    Query = pytransact.query

    if cls in opValueKind:
        kind = opValueKind[cls]
        claz = getattr(Query, cls)
        if kind is None:
            return claz()
        value = dic['value']
        if kind == 'between':
            return Query.Between(value[0], value[1])
        return claz(value)

    elif cls == 'Now':
        return Query.Now(dic['delta'], dic.get('resolution', 1))

    elif cls == 'ConditionGroup':
        conds = dic.copy()
        conds.pop('_cls_')
        cg = Query.ConditionGroup(conds)
        return cg

    elif cls == 'Query':
        tocName = dic['toc']
        cgs = dic['cgs']
        qry = Query.Query(tocName)
        qry.clear()
        for cg in cgs:
            qry.pushDict(cg)
        return qry

    elif cls == 'TO':
        import blm
        toc = blm.getTocByFullname(dic['toc'])
        toi = toc._create(objectid.ObjectId(dic['id']))
        return toi

    elif cls == 'DiffTOI':
        import blm
        toc = blm.getTocByFullname(dic['toc'])
        difftoi = DiffTOI()
        difftoi.toc = toc
        difftoi.toc_fullname = toc._fullname
        difftoi.toid = dic['toid']
        difftoi.diffAttrs = dic['attrs']
        difftoi.orgAttrs = dic['orgAttrs']
        return difftoi

    return dic


class JSONEncoder(flask.json.JSONEncoder):

    def __init__(self, *args, **kwargs):
        kwargs['use_decimal'] = False
        super(JSONEncoder, self).__init__(*args, **kwargs)

    def _getAttrName(self, attr):
        if isinstance(attr, basestring):
            return attr
        else:
            return attr.name

    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            return str(obj)

        elif isinstance(obj, query.Query):
            return {
                '__class__': 'Query',
                'toc' : obj.tocName,
                'cgs' : obj[:],
                }
        elif isinstance(obj, query.ConditionGroup):
            # The keys need fixing
            obj = dict((self._getAttrName(k), v) for k,v in obj.iteritems())
            obj['__class__'] = 'ConditionGroup'
            return obj

        elif isinstance(obj, query.Operator):
            opName = obj.__class__.__name__
            kind = opValueKind[opName]
            dic = {'__class__': opName }
            if kind is None:
                pass
            elif kind == 'list' or kind == 'between':
                dic['value'] = list(obj.value)
            elif kind == 'single':
                dic['value'] = iter(obj.value).next()
            return dic
        elif isinstance(obj, query.Now):
            return {'__class__': 'Now', 'delta': obj.delta,
                    'resolution': obj.resolution }
        elif isinstance(obj, DiffTOI):
            return {'__class__': 'DiffTOI',
                    'toc': obj.toc_fullname,
                    'toid': obj.toid,
                    'attrs': obj.diffAttrs,
                    'orgAttrs': obj.orgAttrs}
        elif isinstance(obj, attribute.EnumVal): # xxx be more precise?
            return obj.name
        elif isinstance(obj, attribute.BlobVal):
            return {
                'content_type': obj.content_type,
                'filename': obj.filename,
                'size': obj.length
            }
        elif isinstance(obj, to.TO):
            # xxx it appears that the only time we send TO to the
            # client is in the form of toirefs, and there the client
            # expects toids rather than TO structures.
            # we may want to revisit this
            return str(obj.id[0])
            #return {'__class__': 'TO',
            #        'toc' : obj._fullname,
            #        'id' : str(obj.id[0]),
            #        }
        if isinstance(obj, ObjectId):
            return str(obj)
        elif isinstance(obj, Exception):
            return {'__class__': obj.__class__.__name__, 'args': obj.args}
        return super(JSONEncoder, self).default(obj)
