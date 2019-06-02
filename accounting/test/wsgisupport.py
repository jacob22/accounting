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

import flask
from pytransact.testsupport import BLMTests
import accounting.flask_utils
import blm


class WSGITests(BLMTests):

    def setup_wsgi(self, app=None):
        if not app:
            app = self.app
        accounting.flask_utils.add_converters(app)
        accounting.flask_utils.set_json_encoder(app)
        app.before_request(self.fake_login)

    def fake_login(self):
        flask.g.database = self.database
        flask.g.user, = blm.TO._query(id=self.user).run()
