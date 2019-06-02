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
else:
    PYT3 = True
try:
    from StringIO import StringIO  # Python 2
except ImportError:
    from io import StringIO  # Python 3
import argparse
import contextlib
import email
import email.header
import glob
import imaplib
import itertools
import json
import logging
import os
import py
import socket
import subprocess
import sys
import tempfile
import textwrap
import time
import uuid

import paramiko.client

import accounting.utils
import hetzner


logging.getLogger('paramiko').setLevel(logging.WARNING)


def pytest_addoption(parser):

    class parse_nodes(argparse.Action):
        def __call__(self, parser, namespace, value, option_string):
            setattr(namespace, self.metavar, value.split(','))

    parser.addoption('--nodes', default=['eucltest1', 'eucltest2',
                                         'eucltest3'],
                     metavar='nodes',
                     type='string', action=parse_nodes)
    parser.addoption('--domain', default='acctest.openend.se')
    parser.addoption('--run-integration-tests', action='store_true')

    parser.addoption('--reload-vms', action='store_true', dest='reload_vms',
                     default=False)
    parser.addoption('--master-vol', dest='master_vol',
                     default='eucltest_master')
    parser.addoption('--repo-dist-method', default='push',
                     choices=['push', 'archive'])
    parser.addoption('--hetzner-token', dest='hetzner_token')
    parser.addoption('--hetzner', action='store_true')
    parser.addoption('--cleanup-hetzner', action='store_true')


def pytest_configure(config):
    if config.option.hetzner or config.option.hetzner_token:
        config.option.domain = 'hetzner.openend.se'
        config.option.nodes = ['hetzner1', 'hetzner2', 'hetzner3']

def pytest_unconfigure(config):
    if py.test.config.option.cleanup_hetzner:
        cleanup_hetzner_test_vms()


class IgnoreMissingHost(paramiko.client.MissingHostKeyPolicy):

    def missing_host_key(self, client, hostname, key):
        pass


class SSHClient(paramiko.client.SSHClient):

    def __init__(self):
        super(SSHClient, self).__init__()
        self.load_host_keys(self.known_hosts)
        self.set_missing_host_key_policy(IgnoreMissingHost())

    @property
    def config(self):
        config = paramiko.config.SSHConfig()
        with open(os.path.expanduser('~/.ssh/config')) as f:
            config.parse(f)
        return config

    @property
    def known_hosts(self):
        return os.path.expanduser('~/.ssh/known_hosts')

    def connect(self, hostname, **kw):
        config = self.config.lookup(hostname)
        try:
            kw.setdefault('username', config['user'])
        except KeyError:
            pass
        print('Connect', hostname, kw)
        return super(SSHClient, self).connect(hostname, **kw)

    def run(self, command, stdin='', stdout=sys.stdout, stderr=sys.stderr,
            raiseonerror=True):
        _stdin, _stdout, _stderr = self.exec_command(command)
        channel = _stdout.channel

        for part in stdin:
            _stdin.write(part)
        _stdin.write('\x04')
        channel.shutdown_write()

        while not channel.exit_status_ready():
            if channel.recv_ready():
                stdout.write(_stdout.readline())
            if channel.recv_stderr_ready():
                stderr.write(_stderr.readline())

        stdout.write(_stdout.readline())
        stderr.write(_stderr.readline())

        exit_status = channel.recv_exit_status()
        if exit_status != 0 and raiseonerror:
            raise RuntimeError('Exit status: %d' % exit_status)
        return exit_status

    def wait(self, command, timeout=60, interval=2):
        stop = time.time() + timeout
        while time.time() < stop:
            try:
                self.run(command)
                break
            except RuntimeError as exc:
                time.sleep(interval)
        else:
            raise exc


def reload_vm(vmname, mastervol=None, vmhost='bruce.openend.se', wait=True):

    if mastervol is None:
        cmd = '/usr/local/bin/reloadvm -y {vmname} -pubkey - '
    else:
        cmd = '/usr/local/bin/reloadvm -y {vmname} -pubkey - {mastervol}'

    with SSHClient() as client:
        client.connect(vmhost)
        keys = list(map(open, glob.glob(os.path.expanduser('~/.ssh/id_*.pub'))))
        with contextlib.nested(*keys):
            client.run(cmd.format(**locals()), stdin=itertools.chain(*keys))

    stop = time.time() + 60
    while True:
        try:
            with SSHClient() as client:
                client.connect(vmname)
                stdout = StringIO()
                client.run('/bin/hostname', stdout=stdout)
                assert stdout.getvalue().strip() == vmname
        except paramiko.ssh_exception.NoValidConnectionsError:
            if time.time() > stop:
                raise
            continue
        else:
            break

user_data = '''#cloud-config

hostname: {hostname}

fqdn: {fqdn}

resolv_conf:
  searchdomains:
    openend.se

write_files:
  - content: |
        auto eth0:1
        iface eth0:1 inet static
            address {ip}/32
    path: /etc/network/interfaces.d/10-floating-ip.cfg

runcmd:
  - rm /etc/ssh/ssh_host_ed25519_key /etc/ssh/ssh_host_ed25519_key.pub
  - rm /etc/ssh/ssh_host_rsa_key /etc/ssh/ssh_host_rsa_key.pub
  - ifdown eth0
  - ifup eth0:1
  - ifup eth0

ssh_deletekeys: false

ssh_keys:
  ecdsa_private: |
    -----BEGIN EC PRIVATE KEY-----
    MHcCAQEEIHn2eNJ2DAjikOwObyPFd2F8WMz8u4LhViJ8XT+IDroWoAoGCCqGSM49
    AwEHoUQDQgAElOpmpz9PkgBQ8lGxt00Rrpz1UOtAFV0VYlMhD5VE2vw/r6UXUv1B
    aFelT83wqqAIfAleY4iZQ4B79vcryBAVFw==
    -----END EC PRIVATE KEY-----
  ecdsa_public: ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABBBJTqZqc/T5IAUPJRsbdNEa6c9VDrQBVdFWJTIQ+VRNr8P6+lF1L9QWhXpU/N8KqgCHwJXmOImUOAe/b3K8gQFRc= root@bruce

ssh_genkeytypes:
'''

'''
  - ip address add {ip}/32 dev eth0:1
  - sh -c "ip addr del $(ip address show dev eth0 scope global | awk '/inet/ {{print $2; exit}}') dev eth0"
'''

def cleanup_hetzner_test_vms():
    hc = hetzner.HetznerCloud(token=py.test.config.option.hetzner_token)

    # Clean up previous servers
    for server in hc.servers:
        with logline('Deleting %s... ' % server['name'], 'deleted.\n'):
            hc.delete(server['id'])


@contextlib.contextmanager
def logline(before, after, stream=sys.stdout, iterations=20, sleep=1):
    stream.write(time.strftime('%H:%M:%S '))
    stream.write(before)
    stream.flush()

    def next():
        for _ in range(iterations):
            stream.write('.')
            stream.flush()
            yield
            time.sleep(sleep)
        raise StopIteration

    try:
        yield next
    except StopIteration:
        pass
    stream.write(after)
    stream.flush()


def indent(string, spaces=8):
    prefix = ' ' * spaces
    return prefix + prefix.join(s + '\n' for s in string.splitlines())


def get_hostkeys(domain):
    ssh_dir = os.path.join('sysconf', domain, 'ssh')
    r = {}
    for filename in glob.glob('%s/ssh_host_*_key*' % ssh_dir):
        with open(filename) as f:
            data = f.read()
        r[os.path.basename(filename).replace('.', '_')] = indent(data)
    return r


@py.test.fixture(scope='session')
def cluster():
    if not py.test.config.option.reload_vms:
        return

    nodes = py.test.config.option.nodes
    root = os.path.dirname(os.path.dirname(__file__))

    if py.test.config.option.hetzner or py.test.config.option.hetzner_token:
        cleanup_hetzner_test_vms()

        hc = hetzner.HetznerCloud(token=py.test.config.option.hetzner_token)

        ips = {ip['description']: ip for ip in hc.floating_ips}
        servers = []
        ip_assignments = []
        for node in nodes:
            with logline('Creating %s... ' % node,
                         'created.\n'):
                server = hc.create(
                    node,
                    start_after_create=False,
                    user_data=user_data.format(
                        hostname=node,
                        fqdn='%s.openend.se' % node,
                        ip=ips[node]['ip'],
                        domain=py.test.config.option.domain,
                    )
                )
                ip = ips[node]['id']
                result = hc.assign_ip_to_server(ip, server['id'])
                ip_assignments.append((node, ip, result['id'], server['id']))
                servers.append(server)


        for server in servers:
            with logline('Initializing %s' % server['name'],
                         ' initialized.\n', iterations=600) as wait:
                for _ in wait():
                    if hc.server(server['id'])['status'] != 'initializing':
                        break

        for node, ip, action, server in ip_assignments:
            with logline('Waiting for IP assignmet to %s' % node,
                         ' done.\n') as wait:
                result = hc.floating_ip_action(ip, action)
                for _ in wait():
                    status = result['status']
                    if status == 'success':
                        break
                    elif status == 'error':
                        result = hc.assign_ip_to_server(ip, server)
                        action = result['id']
                        time.sleep(1)
                    elif status == 'running':
                        time.sleep(1)
                        result = hc.floating_ip_action(ip, action)
                else:
                    assert False

        for server in servers:
            with logline('Starting %s' % server['name'],
                         ' started.\n') as wait:
                for _ in wait():
                    status = hc.server(server['id'])['status']
                    if hc.server(server['id'])['status'] == 'off':
                        hc.poweron(server['id'])
                        break
                else:
                    assert False

        for server in servers:
            with logline('Waiting for %s' % server['name'],
                         ' running.\n') as wait:
                for _ in wait():
                    status = hc.server(server['id'])['status']
                    if hc.server(server['id'])['status'] == 'running':
                        break
                else:
                    assert False

        for node in nodes:
            fqdn = '%s.openend.se' % node
            with logline('Connecting to %s' % fqdn,
                         ' connected.\n') as wait:
                for _ in wait():
                    try:
                        s = socket.create_connection((fqdn, 22), timeout=10)
                    except socket.error:
                        pass
                    else:
                        s.close()
                        break
                else:
                    assert False

        task = 'deploy_hetzner'

    else:
        assert nodes and all(nodes), 'Need at least one node!'
        for node in nodes:
            reload_vm(node, mastervol=py.test.config.option.master_vol)

        task = 'deploy_test'

    cmd = '/usr/bin/fab -f misc/fabfile.py ' + task
    print(cmd)
    subprocess.Popen(cmd.split(), cwd=root).wait()


@py.test.fixture(scope='function')
def ssh(nodes):
    def ssh(hostname=None, username=None):
        client = SSHClient()
        kw = {'hostname': hostname or nodes[0]}
        if username:
            kw['username'] = username
        client.connect(**kw)
        return client
    return ssh


@py.test.fixture(scope='function')
def nodes():
    return ['%s.openend.se' % node for node in py.test.config.option.nodes]


@py.test.fixture(scope='function')
def clean_db(nodes):
    with SSHClient() as client:
        client.connect(nodes[0])
        client.run('PYTHONPATH=/root/accounting '
                   '/root/accounting/bin/test_replica_set.py 300')
        with tempfile.NamedTemporaryFile(mode='w') as f:
            f.write(textwrap.dedent('''\
                import accounting.db
                database = accounting.db.connect()
                print 'Removing database %s.' % database.name
                database.client.drop_database(database.name)
                print 'Database %s removed.' % database.name
                '''))
            f.flush()
            sftp = client.open_sftp()
            sftp.put(f.name, '/tmp/clean_db.py')
        client.run('PYTHONPATH=/root/accounting python /tmp/clean_db.py')


@py.test.fixture(scope='function')
def bootstrapped(nodes):
    with SSHClient() as client:
        client.connect(nodes[0])
        print('Bootstrapping system.')
        client.run('PYTHONPATH=/root/accounting '
                   '/root/accounting/bin/bootstrap.py')


@py.test.fixture(scope='function')
def emailaddress():
    return 'autotest+%s@openend.se' % uuid.uuid4()


class MailSSH(object):

    mailtimeout = 60

    def __init__(self, hostname, username):
        self.hostname = hostname
        self.username = username

    @staticmethod
    def parse(msgdata):
        if PYT3:
            msg = email.message_from_bytes(msgdata)
        else:
            msg = email.message_from_string(msgdata)
        headers = accounting.utils.cidict()
        for name, val in msg._headers:
            parts = email.header.decode_header(val)
            header = headers.setdefault(name, [])
            for decoded, charset in parts:
                if PYT3:
                    header.append(decoded)
                else:
                    header.append(decoded.decode(charset or 'ascii'))


        payload = msg.get_payload(decode=True)
        payload = payload.decode(msg.get_content_charset())

        return payload, headers

    @property
    def command(self):
        return ' '.join([
            'ssh',
            '-o', 'StrictHostKeyChecking=false',
            '-o', 'BatchMode=true',
            '-o', 'ForwardX11=false',
            '-l', self.username,
            self.hostname,
            '/usr/sbin/rimapd'
        ])

    def find_and_delete_mail_text(self, text):
        mb = imaplib.IMAP4_stream(self.command)

        start = time.time()
        found = False
        mails = []

        while not found and time.time() - start < self.mailtimeout:
            status, count = mb.select()
            count = int(count[0])

            for msgnum in range(count, max(count - 5, 0), -1):
                status, message = mb.fetch(str(msgnum), '(RFC822)')
                if PYT3:
                    message = email.message_from_bytes(message[0][1])
                else:
                    message = email.message_from_string(message[0][1])
                for part in message.walk():
                    if PYT3:
                        data = part.get_payload()
                    else:
                        data = part.get_payload(decode=True)
                    if data and text in data:
                        found = True
                        mb.store(str(msgnum), '+FLAGS', '\\Deleted')
                        mails.append(message)
                    if found:
                        break
                if found:
                    break

            if not found:
                time.sleep(0.5)

        mb.expunge()
        mb.close()
        mb.logout()

        return mails

    def find_and_delete_mail(self, charset, *criteria):
        mb = imaplib.IMAP4_stream(self.command)

        start = time.time()
        found = False

        mails = []

        while not found and time.time() - start < self.mailtimeout:
            mb.select()
            status, messages = mb.search(charset, *criteria)
            assert status == 'OK'

            for msgnum in messages[0].split():
                found = True
                status, message = mb.fetch(msgnum, '(RFC822)')
                message = message[0][1]
                mb.store(msgnum, '+FLAGS', '\\Deleted')
                mails.append(message)

            if not found:
                time.sleep(0.5)

        mb.expunge()
        mb.close()
        mb.logout()

        return mails


@py.test.fixture(scope='function')
def mailssh():
    return MailSSH('theraft.openend.se', username='autotest')


class Container(object):

    def __init__(self, **kw):
        self.__dict__.update(kw)


@py.test.fixture(scope='function')
def org(ssh):
    here = os.path.dirname(__file__)
    with ssh() as client:
        sftp = client.open_sftp()
        sftp.put(os.path.join(here, 'setup_org.py'), '/tmp/setup_org.py')
        sftp.put(os.path.join(here, '..', 'accounting', 'test',
                              'swish.crt.pem'),
                 '/tmp/swish.crt.pem')
        stdin, stdout, stderr = client.exec_command(
            'PYTHONPATH=/root/accounting '
            '/root/accounting/bin/client.py '
            '/tmp/setup_org.py')
        data = json.load(stdout)
    return Container(id=data['org'],
                     name=data['orgname'],
                     pgnum=data['pgnum'],
                     payson_provider=data['payson_provider'],
                     swish_provider=data['swish_provider'],
                     product=data['product'])
