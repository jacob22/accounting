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

import decimal
from bson.objectid import ObjectId
import pytransact.runtime as ri
from pytransact.object.model import *
import blm.accounting


class Member(TO):  # jag bor inte i members!

    class user(ToiRef(ToiType(blm.accounting.User), QuantityMax(1))):
        pass

    class name(String(QuantityMax(1))):
        pass

    class emailAddress(String()):
        pass

    # class expenseReports(Relation()):
    #     related = 'Report.member'


class BaseCategory(TO):

    class org(ToiRef(ToiType(blm.accounting.Org), Quantity(1))):
        pass

    class account(String(Regexp(r'\d{4}'), Quantity(1))):
        pass

    class name(String(Quantity(1))):
        pass

    @method(None)
    def save(self, data=Serializable(Quantity(1))):
        data, = data
        try:
            data['price'] = decimal.Decimal(data['price']) / 100
        except KeyError:
            pass
        self(**data)

    @method(None)
    def delete(self):
        self._delete()

    def on_create(self):
        self.allowRead = self.org[0].ug


class Category(BaseCategory):
    pass


class CategoryCountable(BaseCategory):

    class price(Decimal(Quantity(1))):
        precision = 2

    class unit(String(Quantity(1))):
        pass


class CategoryOne(BaseCategory):

    class price(Decimal(Quantity(1))):
        precision = 2


@method(ToiRef(ToiType(BaseCategory), Quantity(1)))
def createCategory(tocName=String(Quantity(1)),
                   data=Serializable(Quantity(1))):
    tocName, = tocName
    data, = data
    toc = {
        'Category': Category,
        'CategoryCountable': CategoryCountable,
        'CategoryOne': CategoryOne
    }[tocName]
    try:
        data['price'] = decimal.Decimal(data['price']) / 100
    except KeyError:
        pass
    return [toc(**data)]


class Verification(TO):

    class date(String(Quantity(1), Regexp(blm.accounting.date_re))):
        pass

    class state(Enum(Quantity(1))):
        values = ['new', 'approved', 'denied', 'handling', 'accounted']
        default = ['new']

    @method(None)
    def setState(self, state=String(Quantity(1))):
        self.state = state

    class lines(Relation()):
        related = 'Line.verification'

    class receipt(Blob()):
        pass

    class receipts(Int()):
        def on_computation(attr, self):
            return [len(self.receipt)]

    class text(String(QuantityMax(1))):
        pass

    class amount(Decimal(Quantity(1))):
        precision = 2

        def on_computation(attr, self):
            return [sum((line.amount[0] for line in self.lines),
                        decimal.Decimal(0))]

    def on_create(self):
        self.allowRead = [ri.getClientUser()]

    @method(None)
    def create_accounting_verification(self, data=Serializable()):
        data, = data
        org, = blm.accounting.Org._query(id=data['org']).run()
        verification = blm.accounting.Verification(
            series=data['series'],
            transaction_date=data['date'],
            accounting=org.current_accounting,
            externalRef=map(str, self.id))

        for line in data['lines']:
            try:
                text = [line['text']]
            except KeyError:
                text = []

            account = blm.accounting.Account._query(
                id=ObjectId(line['account'])).run()

            amount = decimal.Decimal(line['amount']) / 100

            blm.accounting.Transaction(
                verification=[verification],
                version=[0],
                amount=[amount],
                text=text,
                account=account
            )
        self.state = ['accounted']


class Line(TO):

    class verification(Relation()):
        related = Verification.lines

    class category(ToiRef(ToiType(BaseCategory), Quantity(1), Weak())):
        # Categories can be removed after an expense report has been created.
        # Property Weak has no technical meaning a.t.m. but servers mainly
        # as documentation.
        pass

    class amount(Decimal(Quantity(1))):
        precision = 2

    class count(Int(QuantityMax(1))):
        pass

    class text(String(QuantityMax(1))):
        pass

    def on_create(self):
        self.allowRead = self.verification[0].allowRead


@method(ToiRef(ToiType(Verification), Quantity(1)))
def fileExpenseReport(date=String(Quantity(1)),
                      text=String(QuantityMax(1)),
                      lines=Serializable(),
                      receipt=Serializable()):
    params = {'date': date,
              'text': text,
              'receipt': []}

    for part in receipt:
        b = BlobVal(part['data'].decode('base64'),
                    filename=part['name'],
                    content_type=part['type'])
        params['receipt'].append(b)

    verification = Verification(**params)

    for line in lines:
        try:
            count = [line['count']]
        except KeyError:
            count = []

        try:
            text = [line['text']]
        except KeyError:
            text = []

        category = BaseCategory._query(id=line['category']).run()

        Line(category=category,
             amount=[decimal.Decimal(line['amount']) / 100],
             text=text,
             count=count,
             verification=verification)

    return [verification]


@method(ToiRef(ToiType(Verification), Quantity(1)))
def updateExpenseReport(
        verification=ToiRef(ToiType(Verification), Quantity(1)),
        date=String(Quantity(1)),
        text=String(QuantityMax(1)),
        lines=Serializable(),
        newFiles=Serializable(),
        oldFiles=Serializable()):

    verification, = verification

    params = {'date': date,
              'text': text,
              'lines': []}

    params['receipt'] = receipt = []
    assert len(verification.receipt) == len(oldFiles)
    for stored, updated in zip(verification.receipt, oldFiles):
        if not updated.get('deleted', False):
            receipt.append(stored)  # Keep receipt

    for part in newFiles:
        b = BlobVal(part['data'].decode('base64'),
                    filename=part['name'],
                    content_type=part['type'])
        receipt.append(b)

    for line in verification.lines:
        verification.lines.remove(line)
        line._delete()

    verification(**params)

    for line in lines:
        try:
            count = [line['count']]
        except KeyError:
            count = []

        try:
            text = [line['text']]
        except KeyError:
            text = []

        category = BaseCategory._query(id=line['category']).run()

        Line(category=category,
             amount=[decimal.Decimal(line['amount']) / 100],
             text=text,
             count=count,
             verification=verification)

    return [verification]
