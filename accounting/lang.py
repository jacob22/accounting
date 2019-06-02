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

import werkzeug.datastructures

def get_language(request):
    def _value_matches(value, item):
        def _normalize(language):
            return werkzeug.datastructures._locale_delim_re.split(
                language.lower())
        if item == '*':
            return True
        for x, y in zip(_normalize(value), _normalize(item)):
            if x != y:
                return False
        return True
    request.accept_languages._value_matches = _value_matches
    lang = request.accept_languages.best_match(['en', 'sv_SE'], default='en')
    return lang
