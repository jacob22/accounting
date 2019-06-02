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

"""
SMTP over pipes (to e.g. sendmail -bs)
"""

import subprocess, socket
from smtplib import SMTP as BaseSMTP

def sockerr(func):
    def _(*args, **kw):
        try:
            func(*args, **kw)
        except IOError as e:
            raise socket.error(*e.args)

    return _

class PipeSocket(object):
    """
    Use two pipes to emulate a socket. This socket is also file-like,
    so makefile simply returns self.

    We implement just enough to work with smtplib.
    """

    def __init__(self, readpipe, writepipe):
        self.readpipe = readpipe
        self.writepipe = writepipe

    def makefile(self, mode='r'):
        return self

    @sockerr
    def sendall(self, data):
        self.writepipe.write(data)
        self.writepipe.flush()

    @sockerr
    def close(self):
        self.readpipe.close()
        self.writepipe.close()

    def readline(self, size=-1):
        return self.readpipe.readline(size)


class SMTP(BaseSMTP):
    """
    This SMTP class will talk smtp over a pipe to a specified program.

    This version cannot fall back to TCP.
    """

    def __init__(self, command=''):
        """Initialize a new instance.

        command is process to talk smtp to on stdio
        """

        # Abuse host as command string
        BaseSMTP.__init__(self, command, local_hostname='localhost')

    def connect(self, command='/usr/sbin/sendmail -bs', port=0):
        "Connect to process stdio"

        try:
            pipe = subprocess.Popen(command, shell=True, stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE, close_fds=True)
        except (IOError, OSError) as e:
            if self.debuglevel > 0:
                print >>stderr, 'pipe failed:', str(e)
            raise socket.error(*e.args)

        self.sock = PipeSocket(pipe.stdout, pipe.stdin)

        (code, msg) = self.getreply()
        if self.debuglevel > 0:
            print >>stderr, "connect:", msg

        return (code, msg)
