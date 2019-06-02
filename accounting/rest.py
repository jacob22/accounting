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

import flask, json, time
try:
    import httplib
except ImportError:
    from http import client as httplib
from flask import g
from bson.objectid import ObjectId
from pytransact.commit import (CommitContext, CallBlm, CreateToi, ChangeToi, DeleteToi,
                               wait_for_commit)
from pytransact.exceptions import PermissionError, AttrPermError
from pytransact.context import ReadonlyContext
from pytransact.object import model
from accounting import direct, exceptions, invoke
from accounting.flask_utils import json_result, requires_login
from werkzeug.exceptions import Forbidden, NotFound
import members
import blm.members


class Router(object):

    def __init__(self, database):
        self.database = database

    def route(self, path, request):
        fn = 'do_%s' % path
        try:
            return getattr(self, fn)(request)
        except AttributeError:
            return '', 404

    def do_purchase(self, request):
        try:
            return invoke.invoke(request, self.database, None,
                                 'members', 'purchase')
        except exceptions.JSONError as exc:
            resp = flask.jsonify(exc.message)
            resp.status_code = 500
            return resp

    def do_Product(self, request):
        with ReadonlyContext(self.database) as ctx:
            result = {}
            query = blm.members.Product._query(org=request.values['org'],
                                               available=True)
            displayAttrs = ['currentStock', 'description', 'hasImage',
                            'name', 'price', 'optionFields', 'tags']

            query.attrList = displayAttrs + ['accountingRules',
                                             'availableFrom', 'availableTo']
            now = time.strftime('%Y-%m-%d')
            for toi in query.run():
                if toi.availableFrom and toi.availableFrom[0] > now:
                    continue
                if toi.availableTo and toi.availableTo[0] < now:
                    continue
                result[str(toi.id[0])] = direct.Router._get_toidata(toi, displayAttrs)

        return json.dumps(result)


rest_api = flask.Blueprint('rest_api', __name__)


def jsonify_toi(toi, attrs=set(), list_attrs=set()):
    attrs = set(attrs)
    list_attrs = set(list_attrs)
    toidata = {'id': str(toi.id[0])}
    for attrname in attrs | list_attrs:
        attr = getattr(toi, attrname)
        value = attr.value
        if isinstance(attr, model.Enum):
            value = list(map(str, attr.value))
        elif isinstance(attr, model.ToiRef):
            value = [str(t.id[0]) for t in attr.value]
        elif isinstance(attr, model.ToiRefMap):
            value = {key: str(t.id[0]) for (key, t) in attr.items()}
        elif isinstance(attr, model.Decimal):
            value = [str(v) for v in attr.value]
        elif isinstance(attr, model.DecimalMap):
            value = dict((k, str(v)) for (k,v) in attr.value.items())

        if attrname in attrs:
            toidata[attrname] = value[0] if value else None
        else:
            toidata[attrname] = value
    return toidata


@rest_api.route('/product/list')
@requires_login()
@json_result
def product_list():
    with ReadonlyContext(g.database, g.user):
        attrs = ['name', 'price', 'vatAccount']
        list_attrs = []
        return [jsonify_toi(toi, attrs, list_attrs) for toi in
                blm.members.Product._query().run()]


@rest_api.route('/product/status/<objectid:toid>')
@requires_login()
@json_result
def product_status(toid):
    with ReadonlyContext(g.database):
        try:
            toi, = blm.members.Product._query(id=toid).run()
        except ValueError:
            raise NotFound
        return jsonify_toi(toi, ['name', 'description', 'price', 'vatAccount'],
                           ['accountingRules'])


def getAttrData(request, toc, whitelist):
    whitelist = set(whitelist)
    try:
        data = request.data.decode('utf-8')
    except AttributeError:
        data = request.data
    data = json.loads(data)
    for key in data.keys():
        if key not in whitelist:
            raise Forbidden
    return toc._getArgData(data)


product_whitelist = '''name available availableFrom availableTo description
notes optionFields makeTicket tags totalStock accountingRules vatAccount
'''.split()

@rest_api.route('/product/create', methods=['POST'])
@requires_login()
@json_result
def product_create():
    interested = 'rest-product-create-%s' % ObjectId()
    with ReadonlyContext(g.database, g.user):
        org, = blm.accounting.Org._query().run()
    attrData = getAttrData(flask.request, blm.members.Product,
                           product_whitelist)
    attrData['org'] = [org]
    op = CreateToi('members.Product', None, attrData)
    with CommitContext(g.database, g.user) as ctx:
        ctx.runCommit([op], interested=interested)
    result, error = wait_for_commit(g.database, interested)
    if error:
        if isinstance(error, (PermissionError, AttrPermError)):
            raise Forbidden
        else:
            raise error
    toid, = result
    return {'id': toid}


@rest_api.route('/product/update/<objectid:toid>', methods=['POST'])
@requires_login()
@json_result
def product_update(toid):
    attrData = getAttrData(flask.request, blm.members.Product,
                           product_whitelist)
    interested = 'rest-product-update-%s' % ObjectId()
    with CommitContext(g.database, g.user) as ctx:
        toi, = blm.members.Product._query(id=toid).run()
        op = ChangeToi(toi, attrData)
        ctx.runCommit([op], interested=interested)
    result, error = wait_for_commit(g.database, interested)
    if error:
        print(error)
        if isinstance(error, (PermissionError, AttrPermError)):
            raise Forbidden
        else:
            raise error
    return {'id': toi.id[0]}


@rest_api.route('/product/delete/<objectid:toid>', methods=['POST'])
@requires_login()
@json_result
def product_delete(toid):
    interested = 'rest-product-delete-%s' % ObjectId()
    with CommitContext(g.database, g.user) as ctx:
        toi, = blm.members.Product._query(id=toid).run()
        op = DeleteToi(toi)
        ctx.runCommit([op], interested=interested)
    result, error = wait_for_commit(g.database, interested)
    if error:
        if isinstance(error, (PermissionError, AttrPermError)):
            raise Forbidden
        else:
            raise error
    return {'id': toi.id[0]}


@rest_api.route('/invoice/status/<objectid:toid>')
@requires_login()
@json_result
def invoice_status(toid):
    with ReadonlyContext(g.database, g.user):
        try:
            toi, = blm.members.BasePurchase._query(id=toid).run()
        except ValueError:
            raise NotFound
        return jsonify_toi(toi, ['ocr', 'invoiceUrl', 'paymentState'])


@rest_api.route('/invoice/list')
@requires_login()
@json_result
def invoice_list():
    with ReadonlyContext(g.database, g.user):
        ids = flask.request.values.getlist('id')
        if ids:
            query = {'id': ids}
        else:
            query = {}
        tois = blm.members.BasePurchase._query(**query).run()
        return [jsonify_toi(toi, ['ocr', 'invoiceUrl', 'paymentState'])
                for toi in tois]


@rest_api.route('/invoice/create', methods=['POST'])
@requires_login()
@json_result
def invoice_create():
    interested = 'rest-invoice-create-%s' % ObjectId()
    try:
        data = flask.request.data.decode('utf-8')
    except AttributeError:
        data = flask.request.data
    op = CallBlm('members', 'invoice', [[json.loads(data)]])
    with CommitContext(g.database, g.user) as ctx:
        ctx.runCommit([op], interested=interested)
    result, error = wait_for_commit(g.database, interested)
    if error:
        if isinstance(error, (PermissionError, AttrPermError)):
            raise Forbidden
        else:
            raise error
    toid = result[0][0]['invoice']
    return {'id': toid}


@rest_api.route('/invoice/credit/<objectid:toid>', methods=['POST'])
@requires_login()
@json_result
def invoice_credit(toid):
    interested = 'rest-invoice-credit-%s' % ObjectId()
    op = CallBlm('members', 'createCreditInvoice', [[toid]])
    with CommitContext(g.database, g.user) as ctx:
        ctx.runCommit([op], interested=interested)
    result, error = wait_for_commit(g.database, interested)
    if error:
        if isinstance(error, (PermissionError, AttrPermError)):
            raise Forbidden
        else:
            raise error
    toid = result[0][0]
    return {'id': toid}


@rest_api.route('/<objectid:accounting>/series/list')
@requires_login()
@json_result
def series_list(accounting):
    with ReadonlyContext(g.database, g.user):
        attrs = ['name', 'description']
        return [jsonify_toi(toi, attrs) for toi in
                blm.accounting.VerificationSeries._query(accounting=accounting).run()]
