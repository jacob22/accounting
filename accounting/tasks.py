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

import celery
import celery.app.amqp
import socket
import time
from . import celeryconfig
from . import config

app = celery.Celery('tasks', broker='amqp://guest@localhost//')
app.config_from_object(celeryconfig)


if 'eucltest3' not in socket.getfqdn():
    @app.task(name='get_hostname')
    def get_hostname():
        return socket.getfqdn()


@app.task
def add(x, y):
    return x + y


@app.task(name='write-file')
def write_file():
    with open('/tmp/task-test', 'a') as f:
        f.write(time.ctime())
        f.write(' ')
        f.write(socket.getfqdn())
        f.write('\n')



if __name__ == '__main__':
    import sys
    try:
        n = int(sys.argv[1])
    except (ValueError, IndexError):
        n = 10

    results = [get_hostname.delay() for _ in xrange(n)]
    while results:
        for result in results:
            if result.ready():
                break
        result.get()
        results.remove(result)
