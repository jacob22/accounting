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

import argparse
import json
import pprint
import requests
import urlparse


def request(root, bearer, endpoint, data=None):
    headers = {
        'Authorization': 'Bearer %s' % bearer,
        'Content-type': 'application/json',
    }
    url = urlparse.urljoin(root, endpoint)
    if data is None:
        result = requests.get(url, headers=headers)
    else:
        result = requests.post(url, data=json.dumps(data), headers=headers)

    if result.status_code != requests.codes.ok:
        result.raise_for_status()

    return result.json()['result']


def list_products(root, bearer):
    return request(root, bearer, 'product/list')


def create_product(root, bearer, product):
    return request(root, bearer, 'product/create', product)


def modify_product(root, bearer, id, product):
    return request(root, bearer, 'product/update/%s' % id, product)


PRODUCTS = [
    {
        'name': 'Teddybear',
        'description': 'A very cuddly teddybear',
        'accountingRules': {'3200': '199.99'},
        'optionFields': [
            '\x1f'.join([
                'Color',
                '',
                'text',
                '',
                '',
            ])
        ],
    }
]


def setup_products(root, bearer):
    products = request(root, bearer, 'product/list')
    existing_products_by_name = dict((p['name'], p) for p in products)
    for product in PRODUCTS:
        name = product['name']
        try:
            existing = existing_products_by_name[name]
        except KeyError:
            print 'create', create_product(root, bearer, product)
        else:
            print 'modify', modify_product(root, bearer, existing['id'],
                                           product)


def create_invoice(root, bearer, product, buyer_name, buyer_address,
                   buyer_phone, buyer_email, buyer_reference, buyer_annotation,
                   extra_text, expiryDate, *options):
    for p in request(root, bearer, 'product/list'):
        if p['name'] == product:
            break
    else:
        raise ValueError('Unknown product: %s' % product)

    data = {
        'buyerName': buyer_name,
        'buyerAddress': buyer_address,
        'buyerPhone': buyer_phone,
        'buyerEmail': buyer_email,
        'buyerReference': buyer_reference,
        'buyerAnnotation': buyer_annotation,
        'extraText': extra_text,
        'items':[
            {
                'product': p['id'],
                'options': options
            }
        ]
    }

    if expiryDate:
        data['expiryDate'] = expiryDate

    return request(root, bearer, 'invoice/create', data)


def list_invoices(root, bearer, *ids):
    if ids:
        query_params = '?' + '&'.join('id=%s' % id for id in ids)
    else:
        query_params = ''
    return request(root, bearer, 'invoice/list' + query_params)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--url', dest='url',
                        default='https://acctest.openend.se/')
    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true')
    parser.add_argument('bearer', metavar='BEARER')
    parser.add_argument('command', metavar='COMMAND')
    parser.add_argument('args', metavar='ARGUMENTS', nargs='*')
    args = parser.parse_args()

    bearer = args.bearer
    url = args.url
    root = urlparse.urljoin(url, 'api/1/')

    command = {
        'prodlist': list_products,
        'prodsetup': setup_products,
        'invcreate': create_invoice,
        'invlist': list_invoices,
    }[args.command]

    result = command(root, bearer, *args.args)
    if args.verbose:
        pprint.pprint(result)


if __name__ == '__main__':
    main()
