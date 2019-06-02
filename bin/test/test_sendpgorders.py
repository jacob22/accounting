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

import pytransact.mongo, pytransact.utils
import pytransact.testsupport
from .. import sendpgorders
from accounting import db, mail
import blm.accounting

class TestSendPGOrders(pytransact.testsupport.BLMTests):

    def test_send(self, monkeypatch):
        calls = []
        def sendmail(*args):
            calls.append(args)
        monkeypatch.setattr(mail, 'sendmail', sendmail)

        org1 = blm.accounting.Org()
        org2 = blm.accounting.Org()

        order1 = blm.accounting.PGOrder(org=org1,
                                        contact=['Mr. Foo'],
                                        contactPhone=['1234567'],
                                        contactEmail=['foo@example'],
                                        pgnum=['12345-6'])
        order2 = blm.accounting.PGOrder(org=org2, sent=[True],
                                        contact=['Mr. Foo'],
                                        contactPhone=['1234567'],
                                        contactEmail=['foo@example'],
                                        pgnum=['12345-6'])
        self.commit()

        sendpgorders.process(self.database)
        self.sync()

        assert len(calls) == 1
        assert len(blm.accounting.PGOrder._query(sent=[True]).run()) == 2

    def test_main(self, monkeypatch):
        monkeypatch.setattr(db, 'connect', lambda: self.database)
        isPrimary = False
        def is_localhost_primary(connection):
            assert connection is self.connection
            return isPrimary
        calls = []

        monkeypatch.setattr(pytransact.utils, 'is_localhost_primary',
                            is_localhost_primary)
        monkeypatch.setattr(sendpgorders, 'process', calls.append)

        sendpgorders.main()
        assert calls == []

        isPrimary = True
        sendpgorders.main()
        assert calls == [self.database]
