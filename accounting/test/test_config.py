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
from textwrap import dedent
from accounting import config

class TestConfig(object):

    def setup_method(self, method):
        self.orig_config = config.config

    def teardown_method(self, method):
        config.config = self.orig_config

    def test_defaults(self):
        cfg = config.load_config(config.default_cfg, [])
        defaults = dict(cfg.items('accounting'))
        assert 'mongodb_uri' in defaults
        assert 'client_dir' in defaults

    def test_load_config(self, tmpdir, monkeypatch):
        monkeypatch.delenv('ACCOUNTING_CLIENT_DIR', raising=False)
        cfg1 = tmpdir.join('cfg1')
        cfg2 = tmpdir.join('cfg2')
        cfg1.write(dedent('''\
             [accounting]
             mongodb_uri = mongodb://foo.example/
             '''))
        cfg2.write(dedent('''\
             [accounting]
             client_dir = /foo
             '''))

        cfg = config.load_config(config.default_cfg, map(str, [cfg1, cfg2]))
        assert cfg.get('accounting', 'mongodb_uri') == 'mongodb://foo.example/'
        assert cfg.get('accounting', 'client_dir') == '/foo'

    def test_get_smtp_domain(self, tmpdir):
        config.config = config.load_config(config.default_cfg, [])

        cfg = tmpdir.join('cfg')
        cfg.write(dedent('''\
             [accounting]
             smtp_domain = openend.example
             '''))
        config.config = config.load_config(config.default_cfg, [str(cfg)])

        domain = config.get_smtp_domain()
        assert domain == 'openend.example'

    def test_accounting_client_dir_hack(self, tmpdir, monkeypatch):
        monkeypatch.setenv('ACCOUNTING_CLIENT_DIR', '/tmp/foo')
        config.config = config.load_config(config.default_cfg, [])

        assert config.config.get('accounting', 'client_dir') == '/tmp/foo'

    def test_template_dir(self):
        template_dir = config.template_dir
        assert os.path.exists(os.path.join(template_dir, 'login.html'))
