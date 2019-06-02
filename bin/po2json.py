#!/usr/bin/env python

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

import json
import polib
import sys


def main(argv=sys.argv, out=sys.stdout):
    po = argv[1]
    translations = {}
    for entry in polib.pofile(po):
        translations[entry.msgid] = [None, entry.msgstr]

    out.write('define([], function() {\n')
    json.dump(translations, out, indent=4)
    out.write('\n')
    out.write('});\n')


if __name__ == '__main__':
    main()
