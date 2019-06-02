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

import py.test
from pytransact.exceptions import ClientError
from pytransact.testsupport import BLMTests
import blm, blm.accounting

class PermissionTests(BLMTests):

    def check(self, toc, params, edit, allow=None, deny=None):
        orig_user = self.ctx.user

        if isinstance(allow, (blm.TO, type(None))):
            allow = [allow]

        if isinstance(deny, blm.TO):
            deny = [deny]
        elif deny is None:
            deny = [blm.accounting.User()]

        if params is not None:
            toi = toc(**params)
            self.commit()
        else:
            toi = toc

        for user in allow:
            self.pushnewctx()
            self.ctx.setUser(user)
            if params is not None:
                toc(**params)
                self.commit()
            if edit is not None:
                toi._clear()
                toi(**edit)

        for user in deny:
            self.pushnewctx()
            self.ctx.setUser(user)
            if params is not None:
                with py.test.raises(ClientError):
                    toc(**params)

            if edit is not None:
                toi._clear()
                with py.test.raises(ClientError):
                    toi(**edit)

        self.ctx.setUser(orig_user)

    def check_delete(self, toc, params={}, allow=None, deny=None):
        orig_user = self.ctx.user

        if isinstance(allow, (blm.TO, type(None))):
            allow = [allow]

        if isinstance(deny, blm.TO):
            deny = [deny]
        elif deny is None:
            deny = [blm.accounting.User()]

        for user in allow:
            self.pushnewctx()
            self.ctx.setUser(None)
            toi = toc(**params)
            self.commit()

            self.ctx.setUser(user)
            toi._clear()
            toi._delete()

        for user in deny:
            self.pushnewctx()
            self.ctx.setUser(None)
            toi = toc(**params)
            self.commit()

            self.ctx.setUser(user)
            toi._clear()
            with py.test.raises(ClientError):
                toi._delete()
