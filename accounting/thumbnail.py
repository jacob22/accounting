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

import io

import sys
if sys.version_info >= (3,0):
    PYT3 = True
    import io
else:
    PYT3 = False
    import cStringIO
import tempfile
import subprocess
from PIL import Image


def thumbnail(data, content_type, width, height):
    content_type = content_type.lower()
    if content_type == 'application/pdf':
        return from_pdf(data, width, height)
    elif content_type.startswith('image/'):
        return from_image(data, width, height)


def from_pdf(data, width, height):
    with tempfile.NamedTemporaryFile(suffix='.pdf') as f:
        f.write(data)
        f.flush()
        cmd = 'pdftoppm -singlefile -scale-to %d -png %s' % (min(width, height),
                                                             f.name)
        proc = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE)
        output = proc.stdout.read()
        proc.wait()
        return output, 'image/png'


def from_image(data, width, height):
    image = Image.open(io.BytesIO(data))
    image.thumbnail((width, height), Image.ANTIALIAS)
    if PYT3:
        buf = io.BytesIO()
    else:
        buf = cStringIO.StringIO()
    image.save(buf, format=image.format)
    return buf.getvalue(), image.format
