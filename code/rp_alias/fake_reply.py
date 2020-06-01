#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
from html import escape
from typing import Union, Optional

from luckydonaldUtils.logger import logging

__author__ = 'luckydonald'

logger = logging.getLogger(__name__)
if __name__ == '__main__':
    logging.add_colored_handler(level=logging.DEBUG)
# end if

SPACES = '                                                                                    '
BAR = '┃'
ELLIPSIS = '…'
MAX_LEN = 18

REGEX_STR = rf'{BAR}.+{ELLIPSIS}{SPACES[0]}\s*+\n{BAR} .+\n'
REGEX = re.compile(REGEX_STR)


def build_fake_reply(chat_id: Union[int, str], name: str, reply_id: int, old_text: str) -> str:
    old_text = remove_fake_reply(old_text)
    chat_id = str(chat_id)
    assert chat_id.startswith('-100')
    chat_id = chat_id[4:]
    text = old_text[:MAX_LEN-1] + ELLIPSIS
    url = f't.me/c/{chat_id}/{reply_id}'
    link = lambda t: f'<b><a href="{url}">{{text}}</a></b>'.format(text=escape(t))
    html = link(BAR + ' ' + name + SPACES + '\n' + BAR + ' ')
    html += text + '\n'
    return html
# end def


def remove_fake_reply(text: str) -> str:
    """ if it starts with two lines of fake reply, remove that; otherwise return unchanged. """
    return REGEX.sub(text, '')
# end def


def detect_fake_reply(text: str) -> Optional[str]:
    """ Returns the actual text if we detected a fake reply """
    cut = remove_fake_reply(text)
    if text != cut:
        return cut
    else:
        return None
    # end if
# end def
