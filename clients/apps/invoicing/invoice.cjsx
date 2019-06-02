/*
Copyright 2019 Open End AB

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
*/

define([
    'react', 'react-dom', 'reactstrap',
    'jslink/JsLink', 'jslink/commit',
    'gettext', 'signals', 'utils',
    'data/webshop/products', 'data/webshop/cart',
    'widgets/product/list', 'widgets/product/cart', 'widgets/product/order'
    ], ->
    [React, ReactDOM, rs,
     JsLink, commit,
     gettext, signals, utils,
    # Data
    ProductData, Cart,
    # Widgets
    ProductList, ShoppingCart, Order,
    ] = arguments

    gettext.install('client')  # xxx
    _ = gettext.gettext

    jsLink = new JsLink('/jslink')
    [orgid] = document.location.pathname.split('/')[-1..]

    place_order = (order) ->
        invoice =
            org: orgid
            items: (utils.update({product: item.id}, item) for item in order.items)
            buyerName: order.name

        if order.address?
            invoice.buyerAddress = order.address
        if order.email?
            invoice.buyerEmail = order.email
        if order.phone?
            invoice.buyerPhone = order.phone
        if order.annotation?
            invoice.buyerAnnotation = order.annotation

        # oh, hack.. this should be somewhat late during the day in CET/CEST, no
        # matter if DST is active or not.
        midnight = (date) -> new Date(date + 'T21:59:59Z').valueOf() / 1000

        if order.date?
            invoice.date = midnight(order.date)
        if order.expiryDate?
            invoice.expiryDate = midnight(order.expiryDate)

        ReactDOM.render(
            <div>
                <rs.Modal isOpen=true>
                    <rs.ModalHeader>{_('Submitting order...')}</rs.ModalHeader>
                    <rs.ModalBody>
                        {_('Please wait while your order is being processed.')}
                    </rs.ModalBody>
                </rs.Modal>
            </div>,
            document.getElementById('modal'))

        commit.callBlmMethod(
            jsLink,
            'members.invoice',
            [[invoice]], (response) ->
                if response.error?
                    ReactDOM.render(
                        <div>
                            <rs.Modal isOpen=true>
                                <rs.ModalHeader>{_('Order failed')}</rs.ModalHeader>
                                <rs.ModalBody>
                                    {_('Your order could not be placed.
                                        Please try again at a later time.')}
                                </rs.ModalBody>
                            </rs.Modal>
                        </div>,
                        document.getElementById('modal'))
                else
                    url = response.result[0].invoiceUrl
                    cart.clear()
                    document.location = url
    )

    product_data = new ProductData.Products(jsLink, orgid)
    cart = new Cart.Cart(window.localStorage, "eutaxia-cart-#{orgid}")
    cart.load()

    do rerender = ->
        ReactDOM.render(
            <div className='container-fluid'>
                <h1 className='text-center py-3'>{product_data.org_name}</h1>
                <div className='row'>
                    <div className='col-7'>
                        <h2 className='text-center pb-3'>{_('Products')}</h2>
                        <ProductList.List
                            data_source=product_data
                            cart=cart
                            />
                    </div>
                    <div className='col cart-and-order-form'>
                        <h2 className='text-center pb-3'>
                            {_('Shopping cart')}
                        </h2>
                        <ShoppingCart.List
                            cart=cart
                            currency=product_data.currency
                            />
                        <Order.Form
                            cart=cart
                            place_order=place_order
                            />
                    </div>
                </div>
            </div>,
            document.getElementById('document')
        )

    signals.connect(product_data, 'refresh', rerender)

    jsLink.ready.then(->
        product_data.start()
    )
)
