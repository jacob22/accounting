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

import logging
import logging.config
import os
try:
    import ConfigParser                 #py2
except ImportError:
    import configparser as ConfigParser #py3
try:
    from StringIO import StringIO   #py2
except ImportError:
    from io import StringIO         #py3

config = None
here = os.path.dirname(__file__)
default_cfg = os.path.join(here, 'defaults.cfg')
default_log_cfg = os.path.join(here, 'logging.cfg')
del here

load_paths =[p for p in ['/etc/accounting.cfg',
                           os.path.expandvars('$HOME/.accounting.cfg'),
                           os.environ.get('ACCOUNTING_CONFIG')
                           ] if p]
                           #  filter(None, ['/etc/accounting.cfg',
                           # os.path.expandvars('$HOME/.accounting.cfg'),
                           # os.environ.get('ACCOUNTING_CONFIG')
                           # ])
log_load_paths = ['/etc/accounting-log.cfg', os.path.expandvars('$HOME/.accounting-log.cfg')]

from os.path import abspath, dirname, join
template_dir = join(dirname(dirname(abspath(__file__))), 'templates')
del abspath, dirname, join


def get_smtp_domain():
    if config.has_option('accounting', 'smtp_domain'):
        return config.get('accounting', 'smtp_domain')


def load_config(defaults, files):
    config = ConfigParser.ConfigParser()
    with open(defaults, 'r') as f:
        config.readfp(f)
    config.read(files)

    if 'ACCOUNTING_CLIENT_DIR' in os.environ:
        # hack to make it possible to find client dir in buildbot
        if config.has_section('accounting'):
            config.set('accounting', 'client_dir',
                       os.environ['ACCOUNTING_CLIENT_DIR'])

    return config


def setup_config():
    global config
    config = load_config(default_cfg, load_paths)


def setup_logging():
    logging.config.fileConfig([default_log_cfg] + log_load_paths)


def save():
    f = StringIO()
    config.write(f)
    f.seek(0)
    return f


def restore(f):
    config.readfp(f)


getLogger = logging.getLogger  # so lazy code don't have to import logging


setup_config()
setup_logging()
