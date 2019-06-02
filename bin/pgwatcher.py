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

import errno
import logging.handlers
import os
import pyinotify
import shutil
import signal
import subprocess
import sys
import accounting.config
import accounting.mail


def process_file(source):
    directory = accounting.config.config.get('pgwatcher', 'spool')
    processor = accounting.config.config.get('pgwatcher', 'processor')
    destination = os.path.join(directory, os.path.basename(source))
    shutil.move(source, destination)
    try:
        subprocess.check_call([processor, destination],
                              stdout=sys.stdout,
                              stderr=sys.stderr)
    except subprocess.CalledProcessError:
        send_failure_mail('Failed to process incoming PG file: %s\n' % source)


def send_failure_mail(body):
    to = accounting.config.config.get('pgwatcher', 'failure_mails')
    accounting.mail.sendmail(*accounting.mail.makemail(
        body, subject='Failed to process PG file', to=to))


def check_spool():
    directory = accounting.config.config.get('pgwatcher', 'spool')
    files = os.listdir(directory)
    if files:
        send_failure_mail('Found unprocessed PG files:\n%s\n' %
                          '\n'.join(files))


def check_directory():
    directory = accounting.config.config.get('pgwatcher', 'incoming')
    for fname in os.listdir(directory):
        process_file(os.path.join(directory, fname))


def handle_event(event):
    process_file(event.pathname)


def setup_watcher():
    watcher = pyinotify.WatchManager()
    directory = accounting.config.config.get('pgwatcher', 'incoming')
    watcher.add_watch(directory, pyinotify.IN_CLOSE_WRITE)
    return watcher


def setup_notifier(watcher):
    return pyinotify.Notifier(watcher, handle_event)


def run(notifier):
    log_base = accounting.config.config.get('pgwatcher', 'watcherlog_base')

    log = log_base + '.log'
    err = log_base + '.err'

    sys.stdout = open(log, 'a')
    sys.stderr = open(err, 'a')

    notifier.loop()


def setup_term_handler():
    # This is needed otherwise pyinotify won't remove its pid file.
    # Apparently atexit signals do not run on SIGTERM alone.
    def handler(signum, stack_frame):
        raise SystemExit
    return signal.signal(signal.SIGTERM, handler)


def main():
    check_spool()
    check_directory()
    watcher = setup_watcher()
    notifier = setup_notifier(watcher)
    setup_term_handler()
    run(notifier)


if __name__ == '__main__':
    main()
