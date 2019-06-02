# -*- coding: utf-8 -*-
from __future__ import absolute_import

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

import paramiko
from accounting import config


class SSHTool():
    def __init__(self, target_host, target_user, target_password, target_key,
                 via_host=None, via_user=None, via_auth=None):
        if via_host:
            t0 = paramiko.Transport((via_host, 22))
            t0.start_client()
            t0.auth_publickey(via_user, via_auth)
            # setup forwarding from 127.0.0.1:<free_random_port> to |host|
            channel = t0.open_channel('direct-tcpip', (target_host, 22), ('127.0.0.1', 0))
            self.transport = paramiko.Transport(channel)
        else:
            self.transport = paramiko.Transport((target_host, 22))
        self.transport.start_client()
        if target_password:
            self.transport.auth_password(target_user, target_password)
        else:
            self.transport.auth_publickey(target_user, target_key)


def sftpBgcOrder(order_signed):
    # Get upload config
    target_user = config.config.get('bankgiro', 'sftp_user')

    try:
        target_authkey = config.config.get('bankgiro', 'sftp_authkey')
    except Exception:
        target_authkey = None

    try:
        target_password = config.config.get('bankgiro', 'sftp_password')
    except Exception:
        target_password = None

    assert target_authkey or target_password

    target_host = config.config.get('bankgiro', 'sftp_server')

    filename = config.config.get('bankgiro', 'filename')
    remote_path_dir = config.config.get('bankgiro', 'remote_path')
    remote_path = remote_path_dir + filename

    via_user = config.config.get('bankgiro', 'upload_user')
    via_host = config.config.get('bankgiro', 'upload_host')
    via_auth = config.config.get('bankgiro', 'upload_user_authkey')

    # Paramiko client configuration
    UseGSSAPI = True             # enable GSS-API / SSPI authentication
    DoGSSAPIKeyExchange = True
    Port = 22

    via_key = paramiko.RSAKey.from_private_key_file(via_auth)

    if not target_password:
        target_key = paramiko.RSAKey.from_private_key_file(target_authkey)
    else:
        target_key = None

    ssht = SSHTool(
        target_host,
        target_user,
        target_password=target_password,
        target_key=target_key,
        via_host=via_host,
        via_user=via_user,
        via_auth=via_key
    )

    sftp = paramiko.SFTPClient.from_transport(ssht.transport)
    with sftp.open(remote_path, 'w') as f:
        f.write(order_signed)

    result = target_host+':'+remote_path
    return result
