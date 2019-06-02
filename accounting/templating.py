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
import os
import jinja2
import time
import urllib
from . import config
from . import mail

class formatters:

    @classmethod
    def apply(cls, env, *filters):
        for filtername in filters:
            env.filters[filtername] = getattr(cls, filtername)

    @staticmethod
    def money(amount, thousandsep=False):
        try:
            d = decimal.Decimal(amount)
        except decimal.InvalidOperation:
            return amount
        if not thousandsep:
            return '{:.2f}'.format(d).replace('.', ',')
        else:
            return '{:,.2f}'.format(d).replace(',', ' ').replace('.', ',')

    @staticmethod
    def date(timestamp):
        return time.strftime('%Y-%m-%d', time.localtime(timestamp))

    @staticmethod
    def datetime(timestamp):
        return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))

    @staticmethod
    def email(name_addr):
        realname, addr = name_addr
        return mail.makeAddressHeader('From', [(realname, addr)])

    @staticmethod
    def pgnum(s):
        return ''.join([s[:-5], ' ', s[-5:-3], ' ', s[-3:-1], '-', s[-1:]])

    @staticmethod
    def vatpercentage(percentage):
        s = str(decimal.Decimal(percentage).quantize(decimal.Decimal('.01')))
        return s.rstrip('.0')

    @staticmethod
    def urlencode(d):
        return urllib.urlencode(d)

    @staticmethod
    def date(timestamp):
        return time.strftime('%Y-%m-%d', time.localtime(timestamp))


formatters.all = [s for s in dir(formatters) if not (s.startswith('__') or s == 'apply')]
                #filter(lambda s: not (s.startswith('__') or s == 'apply'),
                        # #dir(formatters))

def render_template(template, *args, **kw):
    if os.path.exists(template):
        def load_template(template):
            with open(template, 'r') as f:
                return f.read()
        loader = jinja2.FunctionLoader(load_template)
    else:
        loader = jinja2.FileSystemLoader(config.template_dir)

    env = jinja2.Environment(loader=loader)
    formatters.apply(env, *formatters.all)
    template = env.get_template(template)
    return template.render(*args, **kw)


def as_mail_data(template, *args, **kw):
    kw.setdefault('trim_blocks', True)
    data = render_template(template, *args, **kw)
    header, body = data.split('\n\n', 1)
    headers = {}
    for line in header.splitlines():
        name, value = line.split(':', 1)
        headers[name] = value.strip()

    return body, headers
