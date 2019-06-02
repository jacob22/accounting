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

import os
from accounting.test.fake_bg_response import fakeResponseSuccess, fakeResponseRejected

def main(infname):
    outfname = infname.replace('ILB', 'ULB')
    with open(infname, 'r') as fp:
        inlines = fp.readlines()
    outlines = fakeResponseSuccess(inlines)
    with open(outfname, 'w') as fp:
        fp.writelines(outlines)
    success = outfname

    outfname = infname.replace('ILBZZ', 'ULBU1')
    with open(infname, 'r') as fp:
        inlines = fp.readlines()
    outlines = fakeResponseRejected(inlines)
    with open(outfname, 'w') as fp:
        fp.writelines(outlines)
    rejected = outfname
    return success, rejected

if __name__ == '__main__':
    import sys
    try:
        infile = sys.argv[1]
    except IndexError:
        print 'Need an LBin file as argument.'
    outfile = main(infile)
    print outfile
    
