#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Configure logging before any other modules are loaded
from accounting import config

import sys
if sys.version_info < (3,0,0):
    from io import StringIO         #py2
    from io import BytesIO
    PYT3 = False
else:
    from io import StringIO #py3
    from io import BytesIO
    PYT3 = True

import io
import codecs
import os
import re
import time
import urllib

from bson.objectid import ObjectId
from flask import (
    Flask,
    Response,
    current_app,
    g,
    json,
    jsonify,
    make_response,
    redirect,
    render_template,
    render_template_string,
    request,
    send_from_directory,
    session,
    url_for,
)

try:
    import flaskext.babel
except ImportError:
    import flask_babel

import werkzeug.exceptions

import pymongo
from pytransact import blm
from pytransact.context import ReadonlyContext
from pytransact.commit import CommitContext, CallBlm, CallToi, ChangeToi
from pytransact.commit import wait_for_commit
from pytransact.object.model import BlobVal
from pytransact import queryops

from accounting.flask_utils import requires_login
import accounting.accountspayable_client
import accounting.db
import accounting.direct
import accounting.expense
import accounting.flask_utils
import accounting.invoicing
import accounting.invoke
import accounting.izettle_client
import accounting.lang
import accounting.oauth
import accounting.payson
import accounting.purchase
import accounting.reports
import accounting.rest
import accounting.seqr
import accounting.sie_export
import accounting.stripe
import accounting.swish
import accounting.templating
import accounting.thumbnail

import members  # just to get the blm path right
import members.ticket
from members import base64long
from members.invoice import make_invoice

import blm.fundamental
import blm.accounting
import blm.expense
import blm.members


top = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
log = config.getLogger('wsgi')
templates = os.path.join(top, 'templates')

app = Flask(__name__, template_folder=templates,
            static_folder=os.path.join(top, 'static'))
app.config.update(SEND_FILE_MAX_AGE_DEFAULT=0)  # disable cache


accounting.flask_utils.set_json_encoder(app)
accounting.flask_utils.set_json_decoder(app)
accounting.flask_utils.add_converters(app)

app.register_blueprint(accounting.rest.rest_api, url_prefix='/api/1')
app.register_blueprint(accounting.stripe.stripe_api, url_prefix='/providers/stripe')
app.register_blueprint(accounting.swish.swish_api, url_prefix='/providers/swish')
app.register_blueprint(accounting.expense.app, url_prefix='/expense')
app.register_blueprint(accounting.izettle_client.app, url_prefix='/izettle')
app.register_blueprint(accounting.accountspayable_client.app, url_prefix='/accountspayable')
app.register_blueprint(accounting.purchase.app, url_prefix='/purchase')
app.register_blueprint(accounting.invoicing.app, url_prefix='/invoicing')

try:
    pagedomain = flaskext.babel.Domain(dirname=os.path.join(top, 'locale'),
                                       domain='accounting')
    babel = flaskext.babel.Babel(app, default_domain=pagedomain)
except NameError:
    app.config['BABEL_TRANSLATION_DIRECTORIES'] = os.path.join(top, 'locale')
    babel = flask_babel.Babel(app)

babel.localeselector(lambda: accounting.lang.get_language(request))

try:
    from flask_oldsessions import OldSecureCookieSessionInterface
    app.session_interface = OldSecureCookieSessionInterface()
except ImportError:
    pass


def _set_secret_key(app):
    if getattr(app, 'secret_key', None) is not None:
        return
    accounting.db.connect()  # xxx is this necessary?
    app.secret_key = b'min hemliga nyckel!'

debug = __name__ == '__main__'


USER_ACCESS_RESOLUTION = 12 * 60 * 60  # 12 hours


@app.before_request
def lookup_current_user():
    result = None
    g.user = None
    if getattr(current_app, 'connection', None) is None:
        current_app.connection = accounting.db.get_connection()
        current_app.dbname = config.config.get('accounting', 'mongodb_dbname')
    g.database = current_app.connection[current_app.dbname]
    auth = request.headers.get('Authorization')
    userid = session.get('userid')
    with ReadonlyContext(g.database):
        if auth:
            _, key = auth.split()
            try:
                g.user = blm.accounting.APIUser._query(
                    key=key, _attrList={'lastAccess'}).run()[0]
            except IndexError:
                raise werkzeug.exceptions.Forbidden()
        elif userid:
            try:
                g.user = blm.accounting.User._query(
                    id=session['userid'], _attrList={'lastAccess'}
                ).run()[0]
            except IndexError:
                del session['userid']
            else:
                invitation = session.pop('invitation', None)
                if invitation:
                    result = acceptInvitation(g.user, invitation)
        if g.user:
            if g.user.lastAccess[0] + USER_ACCESS_RESOLUTION < time.time():
                op = ChangeToi(g.user, {'lastAccess': [time.time()]})
                with CommitContext.clone() as ctx:
                    ctx.runCommit([op])  # not interested

    return result


def acceptInvitation(user, code):
    with ReadonlyContext(g.database):
        q = blm.accounting.Invitation._query(inviteCode=code)
        for invitation in q.run():
            user, = blm.accounting.User._query(id=user.id).run()
            op = CallToi(invitation.id[0], 'accept', [[user]])
            interested = ObjectId()
            with CommitContext.clone() as ctx:
                ctx.runCommit([op], interested=interested)
            result, error = wait_for_commit(g.database, interested)
            if error:
                return redirect(url_for('invitation_expired'))


@app.route('/invitation_expired')
def invitation_expired():
    return render_template('invitation_expired.html',
                           url=config.config.get('accounting', 'baseurl'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    next_url = request.values.get('next') or session.get('login_next') or request.url_root
    session['login_next'] = next_url
    if g.user is not None:
        del session['login_next']
        return redirect(next_url)
    if request.method == 'POST':
        oauth_provider = request.form.get('oauth')
        if oauth_provider:
            return accounting.oauth.authorize(oauth_provider)

    page = 'login.html'
    return render_template(page)


def create_or_login(resp):
    try:
        with ReadonlyContext(g.database):
            user = blm.accounting.User._query(openid=resp.identity_url).run()[0]
            session['userid'] = user.id[0]
    except IndexError:
        pass
    else:
        response = redirect(session.pop('login_next', request.url_root))
        return response

    # if 'userid' in session:
    #     return Server.addProvider(request, g.database, g.user,
    #                               session, oid, resp)

    session['openid'] = resp.identity_url
    return redirect(url_for(
        'create_profile', name=resp.fullname, email=resp.email))

# Set up oauth providers
accounting.oauth.init(app, '/login/', create_or_login)


@app.route('/create_profile', methods=['GET', 'POST'])
def create_profile():
    error = ''

    if request.method == 'POST':
        name = request.values['name']
        email = request.values['email']
        op = CallBlm('accounting', 'registerUser',
                     [[name], [email], [session['openid']]])

        interested = ObjectId()
        with CommitContext(g.database) as ctx:
            ctx.setMayChange(True)
            ctx.runCommit([op], interested=interested)

        result, error = wait_for_commit(g.database, interested)
        session['userid'] = result[0][0]
        del session['openid']
        return redirect(session.pop('login_next', request.url_root))

    return render_template('create_profile.html', error=error)


@app.route('/logout')
def logout():
    session.pop('userid', None)
    session.permanent = False
    g.user = None
    response = redirect(request.values.get('next') or '/?foo=bar')
    return response


@app.route('/main/invoke/<string:blm>/<string:toc>/<string:toid>/<string:method>', methods=['GET', 'POST'])
@requires_login()
def main_invoke_toi(toid, method, **kw):
    return accounting.invoke.invoke_toi(request, g.database, g.user,
                                        toid, method)


# setup reporting routes
accounting.reports.route(app, requires_login)


@app.route('/<path:filename>')
def client_resource(filename):
    return send_from_directory(config.config.get('accounting', 'client_dir'),
                               filename, cache_timeout=0)

if debug:
    @app.route('/clients/<path:filename>')
    def clients(filename):
        return send_from_directory(os.path.join(top, 'clients'),
                                   filename, cache_timeout=0)


@app.route('/')
@app.route('/index.html')
@requires_login('login')
def index():
    client_dir = config.config.get('accounting', 'client_dir')
    if os.path.exists(os.path.join(client_dir, 'compiled.html')):
        page = 'compiled.html'
    else:
        page = 'index.html'

    with open(os.path.join(client_dir, page), 'r') as f:
        source = f.read()

    language = accounting.lang.get_language(request)
    translation_files = []
    for p in 'ext/locale/ext-lang-%s.js', 'app/locale/%s.js':
        fname = p % language
        if os.path.exists(os.path.join(client_dir, *(fname.split('/')))):
            translation_files.append(fname)

    html = render_template_string(source, translation_files=translation_files)
    resp = Response(response=html, mimetype='text/html')
    resp.set_cookie('userid', str(g.user.id[0]))
    return resp


@app.route('/api')
@requires_login()
def direct_api():
    js = accounting.direct.api(url_for('router'), [
        'accounting.Account',
        'accounting.Accounting',
        'accounting.ChartOfAccounts',
        'accounting.Invitation',
        'accounting.Org',
        'accounting.PGOrder',
        'accounting.PaymentProvider',
        'accounting.PaysonProvider',
        'accounting.PlusgiroProvider',
        'accounting.SeqrProvider',
        'accounting.SimulatorProvider',
        'accounting.StripeProvider',
        'accounting.SwishProvider',
        'accounting.IzettleProvider',
        'accounting.Transaction',
        'accounting.User',
        'accounting.VatCode',
        'accounting.Verification',
        'accounting.VerificationSeries',
        'accounting.accountingFromTemplate',
        'accounting.createAPIUser',
        'accounting.newAccountingFromLastYear',
        'accounting.next_verification_data',
        'accounting.orderPG',
        'accounting.removeMembers',
        'accounting.createVerification',
        'accounting.editVerification',
        'accounting.subscribe',
        'accounting.transactionIndex',
        'accounting.updateMemberRoles',
        'members.PGAddress',
        'members.Payment',
        'members.Product',
        'members.ProductTag',
        'members.BasePurchase',
        'members.PurchaseItem',
        'members.approvePayment',
        'members.approvePayments',
        'members.copyProduct',
        'members.createCreditInvoice',
        'members.manualPayment',
        'members.refundCredited',
        'members.sendPaymentConfirmationEmail',
        'members.sendReminderEmail',
        'members.suggestVerification'
    ])
    return Response(response=js, mimetype='application/javascript')


@app.route("/router/<string:blmname>", methods=['POST'])
@app.route('/router/')  # for the benefit of url_for
@requires_login()
def router(blmname):
    router = accounting.direct.Router(g.database, g.user)
    return router.route(blmname, request)


@app.route('/accountingImport', methods=['POST'])
@requires_login()
def accountingImport():
    orgId = request.form['org']

    interested = ObjectId()

    try:
        with CommitContext(g.database, g.user) as ctx:
            org, = blm.accounting.Org._query(id=orgId).run()
            ctx.setMayChange(True)
            data = BlobVal(request.files['siefile'])
            op = CallBlm('accounting', 'accountingImport', [[org], [data]])
            ctx.runCommit([op], interested=interested)
        result, errors = wait_for_commit(g.database, interested=interested)
        if errors:
            result = {'success': False}
            log.error('Error while importing SIE file: %s', errors)
        else:
            result = {'success': True, 'id': str(result[0][0])}
    except Exception:
        result = {'success': False}
        log.error('Error while importing SIE file', exc_info=True)
    return jsonify(**result)


@app.route('/imageUpload', methods=['POST'])
@requires_login()
def imageUpload():
    ownerId = request.form['owner']

    interested = ObjectId()
    with CommitContext(g.database, g.user) as ctx:
        toi, = blm.TO._query(id=ownerId).run()
        ctx.setMayChange(True)
        if request.form['delete']:
            val = []
        else:
            imgfile = request.files['image']
            val = [BlobVal(imgfile, imgfile.mimetype)]
        op = ChangeToi(toi, {'image': val})
        ctx.runCommit([op], interested=interested)
    result, errors = wait_for_commit(g.database, interested=interested)
    assert not errors, errors

    result = {'success': True}
    return jsonify(**result)


@app.route('/image/<objectid:toid>')
def image(toid):
    with ReadonlyContext(g.database):
        toi = blm.TO._query(id=toid).run()
        if not toi or not hasattr(toi[0], 'image'):
            raise werkzeug.exceptions.NotFound()

        try:
            response = Response(response=toi[0].image[0].getvalue(),
                                content_type=toi[0].image[0].content_type)
            response.headers['Cache-Control'] = 'no-cache'
        except IndexError:
            raise werkzeug.exceptions.NotFound()

        filename = toi[0].image[0].filename
        if filename is not None:
            response.headers['Content-Disposition'] = (
                "inline; filename*=UTF-8''%s" %
                urllib.quote(filename.encode('utf-8')))

        return response


@app.route('/image/<objectid:toid>/<string:attribute>/<int:index>',
           defaults={'width': None, 'height': None})
@app.route('/image/<objectid:toid>/<string:attribute>/<int:index>/'
           '<int:width>/<int:height>')
@requires_login()
def image2(toid, attribute, index, width, height):
    with ReadonlyContext(g.database):
        try:
            toi, = blm.TO._query(id=toid, _attrList=[attribute]).run()
        except ValueError:
            raise werkzeug.exceptions.NotFound()

        try:
            attr = getattr(toi, attribute)[index]
        except AttributeError:
            raise werkzeug.exceptions.NotFound()

        if not isinstance(attr, BlobVal):
            raise werkzeug.exceptions.Forbidden()

        content_type = attr.content_type
        if width and height:
            data, content_type = accounting.thumbnail.thumbnail(
                attr.getvalue(), content_type, width, height)
        else:
            data = attr.getvalue()

        response = Response(response=data,
                            content_type=content_type)
        response.headers['Cache-Control'] = 'no-cache'
        return response


@app.route('/thumbnail/<int:width>/<int:height>', methods=['POST'])
def _thumbnail(width, height):
    file = request.files['file']
    content_type = 'application/pdf'
    data = file.read()
    data = data.decode('base64')

    thumb, content_type = accounting.thumbnail.thumbnail(
        data, content_type, width, height)
    response = Response(response=thumb,
                        content_type=content_type)
    return response


@app.route('/export/<string:toid>')
@requires_login()
def export(toid):
    fp = codecs.getwriter('cp437')(BytesIO(), 'backslashreplace')
    with ReadonlyContext(g.database, g.user):
        accyear, = blm.accounting.Accounting._query(id=toid).run()
        filename = u'%s - %s.sie' % (accyear.org[0].name[0], accyear.name[0])
        accounting.sie_export.sie_export(fp, accyear)

    response = Response(response=fp.getvalue(),
                        content_type='text/plain; charset=cp437')
    if PYT3:
        response.headers['Content-Disposition'] = (
                "attachment; filename*=UTF-8''%s" %
                urllib.parse.quote(filename.encode('utf-8')))
    else:
        response.headers['Content-Disposition'] = (
            "attachment; filename*=UTF-8''%s" %
            urllib.quote(filename.encode('utf-8')))
    return response


@app.route('/invite', methods=['POST'])
def invite():
    # xxx this shares a lot of code with accountingImport - think about generalising
    orgId = request.form['org']

    interested = ObjectId()
    with CommitContext(g.database, g.user) as ctx:
        org, = blm.accounting.Org._query(id=orgId).run()
        ctx.setMayChange(True)
        email = request.form['email']
        roles = request.form.getlist('roles')
        op = CallToi(ObjectId(orgId), 'invite', [[email], roles])
        ctx.runCommit([op], interested=interested)
    result, errors = wait_for_commit(g.database, interested=interested)
    assert not errors, errors

    result = {'success': True}
    return jsonify(**result)


@app.route('/register', methods=['GET'])
def register():
    session['invitation'] = request.args['code']
    return redirect('/login')


@app.route('/webshop/<objectid:orgid>')
def webshop(orgid):
    translation_files = []
    language = accounting.lang.get_language(request)
    fname = '/webshop/%s.js' % language
    client_dir = config.config.get('accounting', 'client_dir')
    if os.path.exists(os.path.join(client_dir, *(fname.split('/')))):
        translation_files.append(fname)

    with ReadonlyContext(g.database):
        org, = blm.accounting.Org._query(id=orgid).run()
        return make_response(
            render_template('webshop.html', org=org,
                            translation_files=translation_files))


@app.route('/invoice/<objectid:purchase>')
@app.route('/invoice/<objectid:purchase>.')  # easier copypasta from invoice mail
@app.route('/invoice/<objectid:purchase>/<int:random>')
@app.route('/invoice/<objectid:purchase>/<int:random>.')  # easier copypasta from invoice mail
@app.route('/webshop/invoice/<objectid:purchase>')
@app.route('/invoice/<objectid:purchase>/<int:random>.pdf')
def invoice(purchase, random=None):
    accounting.templating.formatters.apply(
        current_app.jinja_env,
        'date', 'pgnum', 'urlencode', 'vatpercentage')

    if 'TOKEN' in request.values:
        accounting.payson.update_payment(request.values['TOKEN'], g.database,
                                         purchase=purchase)

    with ReadonlyContext(g.database):
        toi, = blm.members.BasePurchase._query(id=purchase, random=random).run()
        org = toi.org[0]

        payment = blm.members.Payment._query(matchedPurchase=toi).run()

        query_params = {
            'org': org,
            'currency': toi.currency
        }

        pgprovider = blm.accounting.PlusgiroProvider._query(
            pgnum=queryops.NotEmpty(), **query_params).run()
        if g.user:
            simprovider = blm.accounting.SimulatorProvider._query(**query_params).run()
        else:
            simprovider = []
        paysonprovider = blm.accounting.PaysonProvider._query(**query_params).run()
        seqrprovider = blm.accounting.SeqrProvider._query(**query_params).run()
        stripeprovider = blm.accounting.StripeProvider._query(**query_params).run()
        swishprovider = blm.accounting.SwishProvider._query(
            cert=queryops.NotEmpty(),
            **query_params).run()

        pgnum = pgprovider[0].pgnum[0] if pgprovider else ''

        providers = (pgprovider + simprovider + paysonprovider + seqrprovider +
                     stripeprovider + swishprovider)

        paymentInfoWidth = max(len(providers) * 200, 250)
        for item in toi.items:
            if item.paid[0] and item.product[0].makeTicket[0]:
                tickets = True
                break
        else:
            tickets = False

        language = accounting.lang.get_language(request)

        if request.path.endswith('.pdf'):
            fp = BytesIO()
            make_invoice(fp, toi, org, pgnum, tickets)
            response = Response(response=fp.getvalue(),
                                content_type='application/pdf')
            return response
        else:
            import jinja2.utils
            try:
                # Python 3 compatibility
                jinja2.utils.Cycler.next = jinja2.utils.Cycler.__next__
            except AttributeError:
                pass
            return make_response(render_template('invoice/invoice.html',
                                                 language=language,
                                                 purchase=toi,
                                                 payment=payment,
                                                 org=org,
                                                 pgnum=pgnum, simprovider=simprovider,
                                                 paysonprovider=paysonprovider,
                                                 seqrprovider=seqrprovider,
                                                 stripeprovider=stripeprovider,
                                                 swishprovider=swishprovider,
                                                 paymentInfoWidth=paymentInfoWidth,
                                                 tickets=tickets))


@app.route('/getTickets/<objectid:purchase>')
@app.route('/getTickets/<objectid:purchase>/<int:random>')
def getTickets(purchase, random=None):
    database = g.database.client.get_database(
        g.database.name,
        read_preference=pymongo.ReadPreference.PRIMARY)

    interested = 'get-tickets-%s' % ObjectId()
    with CommitContext(database) as ctx:
        toi, = blm.members.BasePurchase._query(id=purchase, random=random).run()
        op = CallToi(toi.id[0], 'maketickets', [])
        ctx.runCommit([op], interested=interested)
    result, error = wait_for_commit(database, interested)
    if error:
        raise error
    pdf = io.BytesIO()
    with ReadonlyContext(database) as ctx:
        tickets = blm.members.Ticket._query(id=result[0]).run()
        members.ticket.generate(pdf, tickets)

    return Response(response=pdf.getvalue(), mimetype='application/pdf')


@app.route('/getTicket/<objectid:ticket>/<base64long:random>')
def getTicket(ticket, random):
    pdf = StringIO.StringIO()
    with ReadonlyContext(g.database):
        tickets = blm.members.Ticket._query(id=ticket, random=random).run()
        members.ticket.generate(pdf, tickets)

    return Response(response=pdf.getvalue(), mimetype='application/pdf')


ticketurlre = re.compile(r'^.*/ticket/(?P<ticket>[^/]*)/(?P<random>[^/]*)')


@app.route('/ticket/', methods=['GET', 'POST'])
@requires_login('login')
def ticket_simple():
    autovoid = bool(json.loads(request.cookies.get('autovoid', 'false')) or
                    request.values.get('autovoid'))
    scan = request.values.get('scan', '')
    resp = None
    if scan.isdigit():
        resp = redirect(url_for('ticket', ticket=scan))

    if not resp:
        m = ticketurlre.match(scan)
        if m:
            resp = redirect(url_for('ticket', ticket=m.group('ticket'),
                                    random=m.group('random')))

    if not resp:
        accounting.templating.formatters.apply(current_app.jinja_env,
                                               'datetime')
        resp = make_response(
            render_template(
                'ticket.html', nodata=True, ticket=None,
                canvoid=bool(g.user), autovoid=autovoid,
                ticket_url=url_for('ticket_simple', _external=True)
            )
        )

    resp.set_cookie('autovoid', json.dumps(autovoid), path='/ticket',
                    expires=time.time() + 24 * 3600)
    return resp


@app.route('/ticket/<int:ticket>',
           defaults={'random': None, 'product': None, 'sig1': None, 'sig2': None},
           methods=['GET', 'POST'])
@app.route('/ticket/<objectid:ticket>/<base64long:random>',
           defaults={'product': None, 'sig1': None, 'sig2': None},
           methods=['GET', 'POST'])
@app.route('/ticket/<objectid:ticket>/<base64long:random>/<objectid:product>/<base64long:sig1>/<base64long:sig2>',
           methods=['GET', 'POST'])
def ticket(ticket, random, product, sig1, sig2):
    if random is None:
        random = ticket & 0xffffffff
        ticket = ObjectId('%024x' % (ticket >> 32))

    accounting.templating.formatters.apply(current_app.jinja_env, 'datetime')

    autovoid = bool(json.loads(request.cookies.get('autovoid', 'false')) or
                    request.values.get('autovoid'))

    with ReadonlyContext(g.database) as ctx:
        ticket = blm.members.Ticket._query(id=ticket, random=random).run()
        if not ticket:
            resp = make_response(
                render_template('ticket.html', ticket=None,
                                canvoid=bool(g.user), autovoid=autovoid))
            resp.set_cookie('autovoid', json.dumps(autovoid), path='/ticket',
                            expires=time.time() + 24 * 3600)
            return resp

        ticket, = ticket

        if 'print' in request.values:
            return redirect(url_for('getTicket', ticket=ticket.id[0],
                                    random=base64long.encode(ticket.random[0])))

        canvoid = False
        voided = False
        if g.user:
            canvoid = ticket.canWrite(g.user, 'void')
            if canvoid:
                if 'unvoid' in request.values:
                    interested = 'ticket-unvoid-%s' % ObjectId()
                    with CommitContext(g.database, g.user) as ctx:
                        op = CallToi(ticket.id[0], 'unvoid', [])
                        ctx.runCommit([op], interested)
                    result, error = wait_for_commit(g.database, interested)
                    if error:
                        raise error
                elif autovoid or 'void' in request.values:
                    interested = 'ticket-void-%s' % ObjectId()
                    with CommitContext(g.database, g.user) as ctx:
                        op = CallToi(ticket.id[0], 'void', [])
                        ctx.runCommit([op], interested)
                    result, error = wait_for_commit(g.database, interested)
                    voided = result[0][0]
                    if error:
                        raise error

        resp = make_response(
            render_template(
                'ticket.html', ticket=ticket, canvoid=canvoid,
                autovoid=autovoid, voided=voided,
                ticket_url=url_for('ticket_simple', _external=True)
            )
        )
        resp.set_cookie('autovoid', json.dumps(autovoid), path='/ticket',
                        expires=time.time() + 24 * 3600)
        return resp


@app.route('/simulatePayment/<objectid:provider>/<objectid:purchase>', methods=['GET', 'POST'])
@requires_login()
def simulatePayment(provider, purchase):
    interested = 'simulatePayment-%s' % ObjectId()
    amount = request.values['amount']
    with CommitContext(g.database, g.user) as ctx:
        op = CallBlm('members', 'generateFakePayment',
                     [[provider], [purchase], [amount]])
        ctx.runCommit([op], interested=interested)
    result, error = wait_for_commit(g.database, interested)
    if error:
        raise error

    paymentId = result[0]
    with CommitContext(g.database) as ctx:
        op = CallToi(paymentId, 'sendConfirmationEmail', [])
        interested = 'send-sim-payment-confirmation-%s' % ObjectId()
        ctx.runCommit([op], interested=interested)
    result, error = wait_for_commit(g.database, interested=interested)
    if error:
        raise error

    return redirect(request.values['returnurl'])


@app.route('/paysonPayment/<objectid:provider>/<objectid:purchase>',
           methods=['GET', 'POST'])
def paysonPayment(provider, purchase):
    return accounting.payson.pay(g.database, provider, purchase,
                                 request.values['returnurl'])


@app.errorhandler(accounting.seqr.SeqrError)
def seqr_error(error):
    return 'SEQR operation failed: %s %s' % (error.code, error.description), 500


@app.route('/seqrPayment/<objectid:provider>/<objectid:purchase>',
           methods=['GET', 'POST'])
def seqrPayment(provider, purchase):
    return accounting.seqr.invoice(provider, purchase,
                                   request.values['returnurl'],
                                   database=g.database)


@app.route('/seqrPoll/<objectid:provider>/<objectid:purchase>/<invoiceref>',
           methods=['GET', 'POST'])
def seqrPoll(provider, purchase, invoiceref):
    return accounting.seqr.poll(g.database, provider, purchase, invoiceref)


@app.route('/seqrNotification/<objectid:provider>/<objectid:purchase>',
           methods=['GET', 'POST'])
def seqrNotification(provider, purchase):
    print(request.values)
    invoiceref = request.values['invoiceReference']
    return accounting.seqr.notification(g.database, provider, purchase, invoiceref)


@app.route('/seqrCancel/<objectid:provider>/<objectid:purchase>/<string:invoiceref>')
def seqrCancel(provider, purchase, invoiceref):
    return accounting.seqr.cancel(g.database, provider, purchase, invoiceref)


def ordered_storage(f):
    import werkzeug.datastructures
    import flask

    def decorator(*args, **kwargs):
        flask.request.parameter_storage_class = werkzeug.datastructures.ImmutableOrderedMultiDict
        return f(*args, **kwargs)
    return decorator


@app.route('/paysonipn', methods=['GET', 'POST'])
@ordered_storage
def paysonipn():
    print('paysonipn:', request.values)
    return accounting.payson.payson_ipn(request, g.database)


@app.route('/rest/<string:typ>', methods=['GET', 'POST'])
def rest(typ):
    router = accounting.rest.Router(g.database)
    response = router.route(typ, request)
    try:
        basestring
    except NameError:
        basestring = str
    if isinstance(response, basestring):
        response = Response(response=response, mimetype='application/json')
        if 'origin' in request.headers:
            # xxx let administrator define this per organisation
            response.headers['Access-Control-Allow-Origin'] = request.headers['origin']
            response.headers['Access-Control-Allow-Credentials'] = 'true'

    response.headers['Cache-Control'] = 'no-cache'
    return response


@app.route('/me')
@requires_login('login')
def me():
    with ReadonlyContext(g.database, g.user):
        return render_template('me.html', g=g)


@app.route('/current-user')
@requires_login('login')
def current_user():
    with ReadonlyContext(g.database, g.user):
        user, = blm.accounting.User._query(id=g.user).run()
        return jsonify(name=user.name[0])


@app.route('/jslink', methods=['GET', 'POST'])
@requires_login()
def jslink():
    import pytransact.link
    import accounting.jslink
    factory = pytransact.link.LinkFactory()
    jslink = accounting.jslink.JsLink(linkFactory=factory)
    with CommitContext(g.database, g.user):
        result = jslink.render(request)
    return result


@app.route('/phone')
@requires_login()
def phone():
    # response = accounting.oauth.authproviders['google'].app.get('https://www.googleapis.com/auth/user.phonenumbers.read')
    oauth_app = accounting.oauth.authproviders['google']
    token, _ = oauth_app.tokengetter()
    api_key = 'AIzaSyBok5ugb38bJAhibQmxJyvb2fpWQCz2PIM'

    url = (
        'https://people.googleapis.com/v1/'
        # 'people/113483767979339564649'
        'people/me'
        '?personFields=phoneNumbers'
        # '&key={api_key}'
    ).format(**locals())
    response = oauth_app.app.get(url)
    if response.status != 200:
        return accounting.oauth.authorize(
            'google',
            scope='openid email profile https://www.googleapis.com/auth/contacts.readonly')
    return response.raw_data

_set_secret_key(app)


def application(environ, start_response):
    return app.wsgi_app(environ, start_response)


if __name__ == '__main__':
    debug = True

    if config.config.has_section('standalone'):
        port = config.config.getint('standalone', 'port')
        threaded = config.config.getboolean('standalone', 'threaded')
        reloader = config.config.getboolean('standalone', 'reloader')
    else:
        port = 5000
        threaded = True
        reloader = True

    extra_files = []
    if reloader:
        extensions = '.html .mo'.split()
        for directory in templates, os.path.join(top, 'locale'):
            for root, dirs, files in os.walk(directory):
                for name in files:
                    if any(name.endswith(ext) for ext in extensions):
                        extra_files.append(os.path.join(root, name))

    if not debug or os.environ.get('WERKZEUG_RUN_MAIN'):
        log.info('Application starting on port %d', port)
    app.run(debug=debug, host='127.0.0.1', port=port, threaded=threaded,
            use_reloader=reloader, extra_files=extra_files)
