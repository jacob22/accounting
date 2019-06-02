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

import functools

from bson.objectid import ObjectId

from flask import g, jsonify, redirect, request, url_for

from werkzeug.exceptions import Forbidden
from werkzeug.routing import BaseConverter

import accounting.jsonserialization
from members import base64long

class ObjectIdConverter(BaseConverter):
    regex = '[0-9a-fA-F]{24}'

    def to_python(self, value):
        return ObjectId(value)

class Base64LongConverter(BaseConverter):
    regex = '[A-Za-z0-9_-]+'

    def to_python(self, value):
        return base64long.decode(value)

def add_converters(app):
    app.url_map.converters['objectid'] = ObjectIdConverter
    app.url_map.converters['base64long'] = Base64LongConverter


def set_json_encoder(app):
    app.json_encoder = accounting.jsonserialization.JSONEncoder


def set_json_decoder(app):
    app.json_decoder = accounting.jsonserialization.JSONDecoder


def requires_login(redirect_to=None, exception=Forbidden()):
    def decorate(func):
        @functools.wraps(func)
        def check(*args, **kw):
            if not getattr(g, 'user', None):
                if redirect_to is None:
                    raise exception
                else:
                    return redirect(url_for(redirect_to, next=request.base_url))
            return func(*args, **kw)
        return check
    return decorate


def json_result(func):
    @functools.wraps(func)
    def _(*args, **kw):
        return jsonify({'result': func(*args, **kw)})
    return _
