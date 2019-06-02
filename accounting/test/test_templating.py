# -*- coding: utf-8 -*-

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

import sys
if sys.version_info >= (3,0):
    PYT3 = True
else:
    PYT3 = False

import decimal
import jinja2
from accounting import config
from .. import templating


class TestFormatters(object):

    def test_apply(self):
        env = jinja2.Environment()
        templating.formatters.apply(env, 'pgnum')
        assert env.filters['pgnum'] == templating.formatters.pgnum
        assert 'date' not in env.filters

        env = jinja2.Environment()
        templating.formatters.apply(env, 'pgnum', 'date')
        assert env.filters['pgnum'] == templating.formatters.pgnum
        assert env.filters['date'] == templating.formatters.date

    def test_date(self):
        # xxx this test is not tz aware
        f = templating.formatters.date
        assert f(0) == '1970-01-01'
        assert f(1000000000) == '2001-09-09'

    def test_email(self):
        f = templating.formatters.email

        r = f((u'Raksmorgas, Ake', 'ake@test'))
        assert r == '"Raksmorgas, Ake" <ake@test>'

        r = f((u'Räksmörgås, Åke', 'ake@test'))
        if PYT3:
            assert r == '=?utf-8?b?UsOka3Ntw7ZyZ8Olcywgw4VrZQ==?= <ake@test>'
        else:
            assert r == '=?iso-8859-1?q?R=E4ksm=F6rg=E5s=2C_=C5ke?= <ake@test>'

    def test_money(self):
        f = templating.formatters.money
        assert f(0) == '0,00'
        assert f(decimal.Decimal(0)) == '0,00'
        assert f('0') == '0,00'
        assert f(12345.67) == '12345,67'
        assert f(decimal.Decimal('12345.67')) == '12345,67'

        # special case:
        assert f('-') == '-'
        assert f('random gorp') == 'random gorp' # ???

    def test_pgnum(self):
        f = templating.formatters.pgnum
        assert f('34567890') == '345 67 89-0'
        assert f('4567890') == '45 67 89-0'

    def test_vatpercentage(self):
        f = templating.formatters.vatpercentage
        # strip unneded decimals
        assert f(decimal.Decimal('25.00')) == '25'
        assert f('25.00') == '25'
        assert f(25) == '25'

        # but keep needed ones
        assert f(decimal.Decimal('7.50')) == '7.5'
        assert f('7.50') == '7.5'


class TestTemplates(object):

    def test_render_template(self, tmpdir, monkeypatch):
        template_dir = tmpdir
        template = template_dir.join('thetemplate')
        template.write('''
        foo
        {% if somecond %}
           bar
        {% else %}
           baz
        {% endif %}
        {{ val }}
        ''')

        template_path = str(template)

        monkeypatch.setattr(config, 'template_dir', str(template_dir))

        rendered = templating.render_template('thetemplate',
                                              somecond=True, val='quz')
        assert 'bar' in rendered
        assert 'baz' not in rendered
        assert 'quz' in rendered

        rendered2 = templating.render_template(template_path,
                                               somecond=True, val='quz')
        assert rendered2 == rendered

    def test_as_mail(self, tmpdir, monkeypatch):
        template_dir = tmpdir
        template = template_dir.join('thetemplate')
        template.write('''From: {{fromaddr}}
To: {{toaddr}}
Subject: {{subject}}

{{body}}

signature
''')

        monkeypatch.setattr(config, 'template_dir', str(template_dir))

        text, headers = templating.as_mail_data('thetemplate',
                                                fromaddr='from@test',
                                                toaddr='to@test',
                                                subject=u'sübjëct',
                                                body=u'bödy')
        assert text == u'bödy\n\nsignature'
        assert headers == dict(
            From='from@test',
            To='to@test',
            Subject=u'sübjëct')
