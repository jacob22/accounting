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

from flask import Blueprint, g, render_template, request
from pytransact.context import ReadonlyContext
import accounting.lang
import blm.accounting

app = Blueprint('invoicing', __name__)


@app.route('/invoice/<objectid:org>')
def invoice(org):
    language = accounting.lang.get_language(request)
    with ReadonlyContext(g.database, g.user):
        org, = blm.accounting.Org._query(id=org).run()
        return render_template('invoicing/invoice.html',
                               app='invoicing/invoice',
                               css_files=[
                                   'webshop2.css',
                                   'product-list.css',
                                   'shopping-cart.css',
                                   'order.css',
                               ],
                               language=language,
                               org=org)
