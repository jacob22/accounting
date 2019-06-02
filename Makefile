

default: update-pot update-po update-mo client-locale

update-po: locale/sv_SE/LC_MESSAGES/accounting.po

.PHONY: update-pot
update-pot:
	pybabel extract -F babel.cfg --omit-header -o accounting.pot .

locale/%/LC_MESSAGES/accounting.po: accounting.pot
	pybabel update -D accounting -i accounting.pot -l $* -d locale/

locale/%/LC_MESSAGES/messages.po: locale/%/LC_MESSAGES/accounting.po
	cp $< $@

.PHONY: update-mo
update-mo: locale/sv_SE/LC_MESSAGES/accounting.mo locale/sv_SE/LC_MESSAGES/messages.mo

locale/sv_SE/LC_MESSAGES/%.mo: locale/sv_SE/LC_MESSAGES/%.po
	pybabel compile -D $* -l sv_SE -d locale/

clients/locale/client.pot: clientjs
	xgettext \
		--omit-header \
		-o $@ \
		--no-location \
		--from-code utf-8 \
		--sort-output \
		$$(find static/clients/ -name \*.js)

clients/locale/%/LC_MESSAGES/client.po: clients/locale/client.pot
	msgmerge -qU $@ $<

.PHONY: client-locale
client-locale: clients/locale/sv_SE/LC_MESSAGES/client.po


# to init a new locale:
# pybabel init -D accounting -i accounting.pot -l <locale> -d locale/

JS_DEST = static/clients
JS_SRC = clients
JS_SOURCES = $(shell find $(JS_SRC) -name locale -prune -o -type f -print)
COFFEE_TESTS = $(shell find $(JS_SRC) -name jstest_*.coffee)
JS_TESTS = $(COFFEE_TESTS:.coffee=.js)

CJSX = node_modules/.bin/cjsx
COFFEELINT = node_modules/.bin/coffeelint
R = node_modules/.bin/r.js
WEBPACK = node_modules/.bin/webpack

client: clientjs compile-tests webpack

static/clients/locale/%.js: clients/locale/%.po
	mkdir -p $(shell dirname $@)
	bin/po2json.py $< > $@

$(JS_SRC)/%.js: $(JS_SRC)/%.coffee $(CJSX)
	echo -n > $@
	$(CJSX) --compile --bare --map $<


# Certain modules can not be imported directly CommonJS style (which
# is used by tests). We need to convert them. See:
# http://requirejs.org/docs/commonjs.html#autoconversion
COMMON_JS = static/clients/lib/country-calling-code
.PHONY: common-js
.ONESHELL: common-js
common-js : $(R)
	for target in $(COMMON_JS); do
		module=$$(basename $$target)
		$(R) -convert node_modules/$$module $$target
	done


compile-tests: common-js $(JS_TESTS) static/clients/locale/sv_SE/LC_MESSAGES/client.js

webpack: $(WEBPACK)
	PRODUCTION=1 $(WEBPACK) --no-color

webpack-watch: $(WEBPACK)
	$(WEBPACK) --watch

coffeelint: $(COFFEELINT)
	$(COFFEELINT) --quiet $(JS_SRC)

.ONESHELL: cjsx-watch
cjsx-watch: $(CJSX) $(COFFEELINT)
	while
		$(MAKE) compile-tests;
		$(MAKE) clientjs;
	do inotifywait -q --recursive --event close_write \
		--exclude '^#.*#$$' --exclude '^\..*' $(JS_SRC);
	done;

watch: $(WEBPACK) $(CJSX) $(COFFEELINT)
	$(MAKE) -j2 _watch
_watch: webpack-watch cjsx-watch

clientjs: $(JS_DEST)/.build
$(JS_DEST)/.build: $(JS_SOURCES) $(CJSX) $(WEBPACK)
	$(CJSX) --compile --bare --map --output $(JS_DEST) $(JS_SRC)
	touch $@

.PHONY: node
node: $(CJSX) $(COFFEELINT) $(R) $(WEBPACK)
$(CJSX) $(COFFEELINT) $(R) $(WEBPACK):
	npm install

.PHONY: react-clients.tar.gz
react-clients.tar.gz:
	$(MAKE) squeaky-clean
	$(MAKE) webpack
	( cd static/ && tar cz clients/apps ) > $@

.PHONY: publish-react-clients
publish-react-clients: react-clients.tar.gz
	ssh theraft.openend.se /bin/rm -f /srv/salt/admin/react/$<
	scp $< theraft.openend.se:/srv/salt/admin/react/$<

DEPLOY.html: DEPLOY.md
	markdown_py < $< > $@

.PHONY: clean-client
clean-client:
	rm -rf static/clients/

.PHONY: clean
clean:
	find . -type d -name .cache | xargs -r rm -rf
	rm -f node-deps.tar.gz
	rm -f react-clients.tar.gz

.PHONY: squeaky-clean
squeaky-clean: clean-client clean
	rm -rf node_modules/
