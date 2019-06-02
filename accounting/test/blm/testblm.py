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

from pytransact.object.model import *

class Foo(TO):

    class string(String()):
        pass

    class int(Int()):
        pass

    class decimal(Decimal()):
        pass

    class decimalmap(DecimalMap()):
        pass

    class toirefmap(ToiRefMap()):
        pass

    @method(Serializable(Quantity(1)))
    def method1(self, k1=String()):
        return [{'k1': k1, 'string': self.string}]


class Bar(TO):

    class dont_delete(Bool()):
        default = [False]

    def on_delete(self):
        if self.dont_delete[0]:
            raise cBlmError('no way')


class Baz(Foo):

    class bazattr(Int()):
        pass



@method(Serializable(Quantity(1)))
def method1():
    return [{'name': 'method1'}]

@method(Serializable)
def the_method(k1=String(), k2=String()):
    return [{'k1': k1, 'k2': k2}]
