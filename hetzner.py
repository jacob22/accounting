import argparse
import json
import os
import pprint
import sys
import requests
try:
    from urlparse import urljoin  # Python 2
except ImportError:
    from urllib.parse import urljoin  # Python 3


class HetznerCloud(object):

    root = 'https://api.hetzner.cloud/v1/'

    def __init__(self, token):
        if token is None:
            with open(os.path.expanduser('~/.HETZNER_TOKEN')) as f:
                token = f.read().strip()
        self.token = token

    # internals

    def urljoin(self, *parts):
        return urljoin(self.root, *parts)

    @property
    def headers(self):
        return {
            'Authorization': 'Bearer %s' % self.token,
            'Content-Type': 'application/json'
        }

    def call(func):
        def _(self, endpoint, **kw):
            kw.setdefault('headers', self.headers)
            return func(self, self.urljoin(endpoint), **kw).json()
        return _

    @call
    def DELETE(self, endpoint, **kw):
        return requests.delete(endpoint, **kw)

    @call
    def GET(self, endpoint, **kw):
        return requests.get(endpoint, **kw)

    @call
    def POST(self, endpoint, data={}, **kw):
        return requests.post(endpoint, data=json.dumps(data), **kw)

    # Public API

    @property
    def servers(self):
        return self.GET('servers')['servers']

    @property
    def images(self):
        return self.GET('images')['images']

    @property
    def isos(self):
        return self.GET('isos')['isos']

    @property
    def floating_ips(self):
        return self.GET('floating_ips')['floating_ips']

    @property
    def locations(self):
        return self.GET('locations')['locations']

    @property
    def ssh_keys(self):
        return self.GET('ssh_keys')['ssh_keys']

    def assign_ip_to_server(self, id, server):
        return self.POST('floating_ips/{id}/actions/assign'.format(id=id), data={
            'server': server
        })['action']

    def create(self, name, server_type='cx11', image='debian-9',
               location='fsn1', start_after_create=False, user_data=None):
        data = {
            'name': name,
            'server_type': server_type,
            'image': image,
            'ssh_keys': [key['id'] for key in self.ssh_keys],
            'start_after_create': start_after_create
        }
        if user_data is not None:
            assert len(json.dumps(user_data)) < 2 ** 15 - 1
            data['user_data'] = user_data

        return self.POST('servers', data=data)['server']

    def delete(self, id):
        return self.DELETE('servers/%d' % id)

    def floating_ip_action(self, id, action):
        return self.GET('floating_ips/{id}/actions/{action}'.format(
            id=id, action=action))['action']

    def floating_ip_actions(self, id):
        return self.GET('floating_ips/{id}/actions/'.format(id=id))['actions']

    def poweron(self, id):
        return self.POST('servers/{id}/actions/poweron'.format(id=id))

    def reset_password(self, id):
        return self.POST('servers/%d/actions/reset_password' % id)

    def server(self, id):
        return self.GET('servers/%d' % id)['server']


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('-a', '--assign-ip-to-server', type=int, nargs=2)
    parser.add_argument('-t', '--token', dest='token')
    parser.add_argument('-c', '--create', dest='create', action='append')
    parser.add_argument('-d', '--delete', dest='delete', action='append')
    parser.add_argument('--delete-all', action='store_true')
    parser.add_argument('-f', '--floating-ips', action='store_true')
    parser.add_argument('--floating-ip-actions', type=int)
    parser.add_argument('-i', '--images', action='store_true')
    parser.add_argument('--isos', action='store_true')
    parser.add_argument('-k', '--ssh-keys', action='store_true')
    parser.add_argument('-l', '--locations', action='store_true')
    parser.add_argument('-p', '--poweron', type=int)
    parser.add_argument('--reset-password')
    parser.add_argument('-s', '--servers', action='store_true')
    args = parser.parse_args()

    hc = HetznerCloud(args.token)

    for arg in args.delete or []:
        for server in hc.servers:
            if arg in list(map(str, [server['id'], server['name']])):
                pprint.pprint(hc.delete(server['id']))

    if args.delete_all:
        for server in hc.servers:
            pprint.pprint(hc.delete(server['id']))

    for arg in args.create or []:
        pprint.pprint(hc.create(arg))

    if args.assign_ip_to_server:
        ip, server = args.assign_ip_to_server
        pprint.pprint(hc.assign_ip_to_server(ip, server))

    if args.floating_ips:
        pprint.pprint(hc.floating_ips)

    if args.floating_ip_actions:
        pprint.pprint(hc.floating_ip_actions(args.floating_ip_actions))

    if args.images:
        pprint.pprint(hc.images)

    if args.isos:
        pprint.pprint(hc.isos)

    if args.locations:
        pprint.pprint(hc.locations)

    if args.poweron:
        pprint.pprint(hc.poweron(args.poweron))

    if args.reset_password:
        pprint.pprint(hc.reset_password(int(args.reset_password)))

    if args.servers:
        pprint.pprint(hc.servers)

    if args.ssh_keys:
        pprint.pprint(hc.ssh_keys)


if __name__ == '__main__':
    main(sys.argv)
