# -*- coding: utf-8 -*-
from luckydonaldUtils.logger import logging
from raven.contrib.flask import Sentry


__author__ = 'luckydonald'
logger = logging.getLogger(__name__)


def add_error_reporting(app):
    sentry = Sentry(app)  # set SENTRY_DSN env!
    app.add_url_rule('/sentry', 'is_sentry', is_sentry(sentry))
    return sentry
# end def


def is_sentry(sentry):
    def view():
        return "{}".format(sentry)
    # end if
# end if