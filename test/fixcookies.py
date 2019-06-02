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

# To update with new cookies:
# 1) Start Firefox
# 2) Clear Cookies
# 3) Log in with chosen provider at http://localhost.admin.eutaxia.eu:5000/
# 4) Log in with existing user, specified in /u/common/openend.kdbx
# 5) Export cookies
# 6) Run this script to format the cookies file so that Python can
#    parse it like so:
#    $ python fixcookies.py facebook < cookies.txt > cookies.facebook.txt

import sys


def filter_cookies(filter_func, stdin, stdout):
    stdout.write('# Netscape HTTP Cookie File\n')
    for line in stdin:
        line = line.strip()
        if line == '# Netscape HTTP Cookie File':
            continue
        if line and line[0] != '#':
            try:
                (domain, domain_specified, path,
                 secure, expires, name, value) = line.split('\t')
            except ValueError:
                continue
            if not filter_func(domain):
                continue
            expires = str(int(float(expires)))

            line = '\t'.join((domain, domain_specified, path,
                              secure, expires, name, value))

        stdout.write(line)
        stdout.write('\n')


def main(argv=sys.argv, stdin=sys.stdin, stdout=sys.stdout):
    if argv[1] == 'facebook':
        filter_func = lambda domain: domain.startswith('.facebook.com')
    elif argv[1] == 'google':
        filter_func = lambda domain: domain.endswith('.google.com')
    elif argv[1] == 'live':
        filter_func = lambda domain: domain.endswith('.live.com')

    filter_cookies(filter_func, stdin, stdout)


if __name__ == '__main__':
    main()
