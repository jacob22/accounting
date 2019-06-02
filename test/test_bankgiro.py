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

import datetime
import tempfile

import py


@py.test.mark.usefixtures('cluster', 'clean_db', 'bootstrapped', 'ssh', 'org')
def test_bgupload(ssh, org):
    expected_ul_path = 'bankgiro/upload/BFEP.ILBZZ.K0940737'
    with ssh('theraft.openend.se', username='autotest') as client:
        # Clean up previous failed test
        client.run('rm -f %s' % expected_ul_path)

    print(org)
    with tempfile.NamedTemporaryFile(mode='w') as f:
        f.write('''
si = blm.accounting.SupplierInvoice(
        org=blm.accounting.Org._query(id="{orgid}").run(),
        invoiceState=['registered'],
        automated=[True],
        recipient=['Happy Customer Inc.'],
        amount=[100.00],
        transferMethod=['bgnum'],
        transferDate=['{transferDate}'],
        bgnum=['8888885'],
        invoiceIdentifierType=['message'],
        message=['Be a Happy Customer!'],
        invoiceDate=['1970-01-01'],
)
commit()
        '''.format(orgid=org.id,
                   transferDate=datetime.datetime.now().strftime('%Y-%m-%d')))
        f.flush()

        with ssh() as client:
            sftp = client.open_sftp()
            sftp.put(f.name, '/tmp/create_supplier_invoice.py')
            client.wait('PYTHONPATH=/root/accounting '
                        '/root/accounting/bin/client.py '
                        '/tmp/create_supplier_invoice.py')

        with ssh('hetzner1.openend.se') as client:
            client.wait('PYTHONPATH=/root/accounting '
                        '/root/accounting/bin/sendbgorders.py --test-sign')

    with ssh('theraft.openend.se', username='autotest') as client:
        stdin, stdout, stderr = client.exec_command('cat %s' % expected_ul_path)
        contents = stdout.read()
        print(contents)
        error = stderr.read()
        assert not error, error
        assert b'Happy Customer' in contents
        client.run('rm -f %s' % expected_ul_path)  # Clean up
