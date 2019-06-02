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

import pprint
import sys
import pytransact.utils
import accounting.izettle_import


def main():
    org, filename = sys.argv[1:]
    with pytransact.utils.count_db_calls() as counter:
        accounting.izettle_import.import_transactions(org, filename)
    pprint.pprint(counter._copy())


if __name__ == '__main__':
    main()
