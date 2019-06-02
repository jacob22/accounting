#!/usr/bin/env client.py

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
import sys
import uuid

import members  # NOQA; for blm loader
import blm.accounting
import blm.members

orgname = str(uuid.uuid4())
orgnum = '123456-7897'


def setup():
    org = blm.accounting.Org(name=orgname,
                             orgnum=orgnum,
                             subscriptionLevel=['subscriber'])

    pgprovider = blm.accounting.PlusgiroProvider(org=org,
                                                 account='1000',
                                                 series='A',
                                                 pgnum='10181')

    bgprovider = blm.accounting.BankgiroProvider(org=org,
                                                 account='1000',
                                                 series='A',
                                                 bgnum='10181')

    payson_provider = blm.accounting.PaysonProvider(
        org=org,
        account='1000',
        series='A',
        apiUserId='4',
        apiPassword='2acab30d-fe50-426f-90d7-8c60a7eb31d4',
        receiverEmail='testagent-1@payson.se')

    with open('/tmp/swish.crt.pem') as f:
        swish_provider = blm.accounting.SwishProvider(
            org=org,
            account='1000',
            series='A',
            swish_id='1231181189',
            cert=f.read()
        )

    si_provider = blm.accounting.SupplierInvoiceProvider(
        org=org,
        bank_account='1',
        account='1000',
        series='A',
    )


    product = blm.members.Product(name='Good stuff',
                                  org=org,
                                  available=True,
                                  accountingRules={'1000': '666.66'})
    commit()  # NOQA

    return json.dumps({
        'org': str(org.id[0]),
        'orgname': orgname,
        'pgnum': pgprovider.pgnum[0],
        'payson_provider': str(payson_provider.id[0]),
        'swish_provider': str(swish_provider.id[0]),
        'product': str(product.id[0])
    })


def main(argv):
    print setup()


if __name__ == '__main__':
    main(sys.argv)
