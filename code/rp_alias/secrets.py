# -*- coding: utf-8 -*-
from luckydonaldUtils.logger import logging
import os

__author__ = 'luckydonald'
logger = logging.getLogger(__name__)


API_KEY = os.getenv('TG_API_KEY', None)
assert(API_KEY is not None)  # TG_API_KEY environment variable

HOSTNAME = os.getenv('URL_HOSTNAME', None)
# can be None

URL_PATH = os.getenv('URL_PATH', None)
assert(URL_PATH is not None)  # URL_PATH environment variable

MONGO_HOST = os.getenv('MONGO_HOST', None)
assert MONGO_HOST is not None  # MONGO_HOST environment variable

MONGO_USER = os.getenv('MONGO_USER', None)
assert MONGO_USER is not None  # MONGO_USER environment variable

MONGO_PASSWORD = os.getenv('MONGO_PASSWORD', None)
assert MONGO_PASSWORD is not None  # MONGO_PASSWORD environment variable

MONGO_DB = os.getenv('MONGO_DB', None)
assert MONGO_DB is not None  # MONGO_DB environment variable

