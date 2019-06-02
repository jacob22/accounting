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
if sys.version_info < (3,0,0):
    PYT3 = False
    from itertools import izip as zip
else:
    PYT3 = True

import itertools
import datetime
import os
import py
import tempfile
import urllib
import uuid


from . import support

import members.paymentgen


root = os.path.dirname(os.path.dirname(__file__))


def gen_pg():
    file_id = 1
    start_tid = 1
    while True:
        class TOI(object):
            def __init__(self, **kw):
                self.__dict__.update(kw)

        out = tempfile.NamedTemporaryFile(mode='w')
        members.paymentgen.generate_pg_file(
            provider=TOI(pgnum=['75']),
            purchases=[TOI(total=[10], ocr=[1040],
                           buyerName=None, buyerAddress=None)],
            timestamp=datetime.datetime.now().strftime('%Y%m%d%H%M%S'),
            file_id=file_id,
            start_tid=start_tid,
            out=out)
        out.flush()
        yield out.name
        file_id += 1
        start_tid += 1000


@py.test.mark.usefixtures('cluster', 'clean_db', 'bootstrapped', 'nodes', 'ssh')
def test_incoming_payments(nodes, ssh):
    with open(os.path.expanduser('~/.ssh/id_rsa.pub'), 'r') as f:
        pubkey = f.read()

    def upload_and_check(node, source):
        filename = uuid.uuid4()
        with ssh(node, username='nordea') as client:
            sftp = client.open_sftp()
            destination = 'incoming/%s' % filename
            sftp.put(source, destination, confirm=False)

        with tempfile.NamedTemporaryFile(mode='w') as f:
            f.write(('''
if not blm.members.PGPaymentFile._query(fileName='%s').run():
    raise SystemExit(1)
            ''' % filename))
            f.flush()
            with ssh(node) as client:
                sftp = client.open_sftp()
                sftp.put(f.name, '/tmp/test_incoming.py')
                client.wait('PYTHONPATH=/root/accounting '
                            '/root/accounting/bin/client.py /tmp/test_incoming.py')
        return filename

    source = os.path.join(root, 'members/test/total_in_bas_exempelfil.txt')

    for node, source in zip(nodes, itertools.chain([source], gen_pg())):
        with ssh(node) as client:
            keysfile = '/home/nordea/.ssh/authorized_keys'
            if client.run('grep -q "%s" %s' % (pubkey.strip(), keysfile),
                       raiseonerror=False) != 0:
                print('Installing key')
                client.run("echo -en '\n"
                        "# Test\nno-port-forwarding,command=\"internal-sftp\" '"
                        ">> %s" % keysfile)
                client.run('cat >> %s' % keysfile, pubkey)

            # Upload working file.
            destination = upload_and_check(node, source)
            # wait until file is processed
            client.wait('test -f /home/nordea/archive/%s' % destination)

            # Upload broken file.
            destination = upload_and_check(node, 'test/%s' %
                                           os.path.basename(__file__))

            client.wait('test -f /var/spool/nordea/%s' % destination)

            # make sure error log is flushed (and rotated)
            client.run('sleep 1 && service pgwatcher restart')
            client.wait('grep -q Traceback /var/log/pgwatcher.err')


@py.test.mark.usefixtures('cluster', 'clean_db', 'bootstrapped',
                          'mailssh', 'ssh')
def test_billing_mail(mailssh, ssh):
    orgname1 = str(uuid.uuid4())
    orgname2 = str(uuid.uuid4())

    email1 = 'autotest+%s@openend.se' % orgname1
    email2 = 'autotest+%s@openend.se' % orgname2
    create_org = '''
if not blm.accounting.Org._query(name='%(orgname)s').run():
    blm.accounting.Org(
        name=['%(orgname)s'],
        orgnum=['111111-1111'],
        email=['%(email)s'],
        phone=['111 - 111 111'])
    commit()

blm.accounting.subscribe(
    org=blm.accounting.Org._query(name='%(orgname)s').run(),
    level=['subscriber'])
commit()

'''
    with ssh() as client:
        sftp = client.open_sftp()
        with tempfile.NamedTemporaryFile(mode='w') as f:
            f.write(create_org % {'orgname': orgname1, 'email': email1})
            f.flush()
            sftp.put(f.name, '/tmp/create_org_test_billing_mail1.py')

##X         import pdb;pdb.set_trace()
        client.run('PYTHONPATH=/root/accounting '
                   '/root/accounting/bin/client.py '
                   '/tmp/create_org_test_billing_mail1.py')

        with tempfile.NamedTemporaryFile(mode='w') as f:
            f.write(create_org % {'orgname': orgname2, 'email': email2})
            f.flush()
            sftp.put(f.name, '/tmp/create_org_test_billing_mail2.py')

        client.run('PYTHONPATH=/root/accounting '
                   '/root/accounting/bin/client.py '
                   '/tmp/create_org_test_billing_mail2.py')

        client.run('PYTHONPATH=/root/accounting '
                   '/root/accounting/bin/make_bills.py 2013')

    message, = mailssh.find_and_delete_mail(None, 'TO', email1)
    fromaddr = b'noreply@admin.eutaxia.eu'
    assert fromaddr in message
    if PYT3:
        assert orgname1.encode('ascii') in message
    else:
        assert orgname1 in message

    message, = mailssh.find_and_delete_mail(None, 'TO', email2)
    fromaddr = b'noreply@admin.eutaxia.eu'
    assert fromaddr in message
    if PYT3:
        assert orgname2.encode('ascii') in message
    else:
        assert orgname2 in message


@py.test.mark.usefixtures('cluster', 'clean_db', 'bootstrapped',
                          'mailssh', 'nodes', 'ssh')
def test_pgorder_mail(mailssh, nodes, ssh):
    orgname = str(uuid.uuid4())

    with ssh() as client:
        with tempfile.NamedTemporaryFile(mode='w') as f:
            f.write('''
if not blm.accounting.Org._query(name='%(orgname)s').run():
    blm.accounting.Org(
        subscriptionLevel=['subscriber'],
        name=['%(orgname)s'],
        orgnum=['666666-6668'],
        email=['autotest@openend.se'],
        phone=['666 - 666 666'])
    commit()

blm.accounting.orderPG(
    org=blm.accounting.Org._query(name='%(orgname)s').run(),
    contact=['Mr. Test'],
    contactPhone=['666 - 666 667'],
    contactEmail=['autotest+mrtest@openend.se'],
    pgnum=['234-5'],
    pgaccount=['1000'],
    pgseries=['A'])
commit()

''' % {'orgname': orgname})
            f.flush()
            sftp = client.open_sftp()
            sftp.put(f.name, '/tmp/create_org.py')

        client.run('PYTHONPATH=/root/accounting '
                   '/root/accounting/bin/client.py '
                   '/tmp/create_org.py')

    for node in nodes:
        # run sendpgorders on all machines as we do not know which one
        # is primary
        with ssh(node) as client:
            client.run('/etc/cron.hourly/sendpgorders')

    message, = mailssh.find_and_delete_mail_text(orgname)
    fromaddr = 'autotest+nordeatest-from@openend.se'
    assert fromaddr in message['From']
    if PYT3:
        assert orgname in message.get_payload()
    else:
        assert orgname in message.get_payload(decode=True)


@py.test.mark.usefixtures('cluster', 'nodes', 'ssh')
def test_import_dump_and_find_stale_commits(nodes, ssh):
    backup_dir = '/backup/eucl/accountingdata'

    with ssh() as client:
        with ssh('ukod.openend.se') as ukod:
            stdin, stdout, stderr = ukod.exec_command('ls -t %s' % backup_dir)
            for line in stdout:
                if line[:15] in ['acc%d.openend.se' % d for d in [1, 2, 3, 4]]:
                    fname = line.strip()
                    break
            else:
                assert False

            with tempfile.NamedTemporaryFile(mode='w') as f:
                ukod.open_sftp().get('%s/%s' % (backup_dir, fname), f.name)
                client.open_sftp().put(f.name, fname)

        client.run('tar -xf %s' % fname)

    for node in nodes:
        with ssh(node) as client:
            client.run('systemctl stop mongodb')
            client.run('rm -rf /data/*')

    for node in nodes:
        with ssh(node) as client:
            client.run('systemctl start mongodb')

    with ssh() as client:
        node_js = "{_id: %d, host: '%s:27017'}"
        initiate_js = "rs.initiate({_id: 'accounting', members: [ %s ]})"
        members = [node_js % (index, node)
                   for (index, node) in enumerate(nodes)]
        js = initiate_js % (', '.join(members))

        client.run('''
            while ! tail -20 /var/log/mongodb/mongodb.log | \
                    grep -q 'waiting for connections'; do
                sleep 1;
            done;
            mongo --ssl \
                  --sslPEMKeyFile /etc/accounting-mongodb.crt+key \
                  --sslAllowInvalidCertificates \
                  --quiet --eval "%s;"; ''' % js)

        client.run('PYTHONPATH=/root/accounting '
                   '/root/accounting/bin/test_replica_set.py 60')

        client.run('mongorestore \
                    --ssl \
                    --sslPEMKeyFile /etc/accounting-mongodb.crt+key \
                    --sslAllowInvalidCertificates \
                    --drop --oplogReplay accounting-dump/')

        client.run('PYTHONPATH=/root/accounting '
                   '/root/accounting/bin/test_replica_set.py 1200')
        client.run('PYTHONPATH=/root/accounting '
                   '/root/accounting/bin/upgrade.py')

        if PYT3:
            response = urllib.request.urlopen(support.url)
        else:
            response = urllib.urlopen(support.url)


        assert response.getcode() == 200

        with tempfile.NamedTemporaryFile(mode='w') as f:
            f.write('''
assert database.commits.find().count() == 0
''')
            f.flush()
            client.open_sftp().put(f.name, '/tmp/check_stale_commits.py')

        client.run('PYTHONPATH=/root/accounting '
                   '/root/accounting/bin/client.py '
                   '/tmp/check_stale_commits.py')
