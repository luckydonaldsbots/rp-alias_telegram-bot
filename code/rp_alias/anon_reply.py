#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
from html import escape
from typing import Union

from luckydonaldUtils.logger import logging

__author__ = 'luckydonald'

from pytgbot.api_types.receivable.updates import Message

logger = logging.getLogger(__name__)
if __name__ == '__main__':
    logging.add_colored_handler(level=logging.DEBUG)
# end if

LINK = '<a href="{link}">{label}</a>'

ZERO_WIDTH_SPACE = "‎"
ZERO_WIDTH_SPACE = "⤷ "
INVISIBLE_LINK = LINK.format(link='{link}', label=ZERO_WIDTH_SPACE)

USER_URL_TEMPLATE = "tg://user?id={user_id}"
USER_URL_REGEX_STR = "tg://user\?id=(?P<user_id>\d+)"
USER_URL_REGEX = re.compile(USER_URL_REGEX_STR)


def build_reply_message(user_id: int, user_name: str, username: Union[str, None]):
    user_url = USER_URL_TEMPLATE.format(user_id=user_id)
    at_user_url = f"https://t.me/{username}" if username else user_url
    invisible_link = INVISIBLE_LINK.format(link=user_url)
    visible_link = LINK.format(link=at_user_url, label=escape(user_name))
    return f"{invisible_link}Sent by user {visible_link}."


# end def

def detect_anon_user_id(msg: Message) -> Union[None, int]:
    if msg.text and msg.text.startswith(ZERO_WIDTH_SPACE):
        logger.debug('found ZERO_WIDTH_SPACE.')
    else:
        logger.debug('no ZERO_WIDTH_SPACE.')
        return None
    # end if

    if msg.entities and len(msg.entities) > 1 and msg.entities[0].offset == 0 and msg.entities[0].length == 1 and \
        msg.entities[0].type in ("url", "text_mention"):
        logger.debug('Is indeed a link.')
    else:
        logger.debug('no link at first position.')
        return None
    # end if

    link = msg.entities[0]
    if link.type == 'text_mention':
        logger.debug(f'got mention of user {link.user}.')
        return link.user.id
    else:
        assert link.type == 'url'
        url = link.url
        m = USER_URL_REGEX.match(url)
        if not m:
            logger.debug('regex didn\'t match.')
            return None
        # end if
        return m.groupdict().get('user_id', None)
    # end def
# end def


def __test():
    assert detect_anon_user_id(
            Message.from_array({
            'message_id': 119741,
            'from': {
                'id': 133378542, 'is_bot': True, 'first_name': 'Test Bot i do tests with', 'username': 'test4458bot'
            },
            'chat': {
                'id': 10717954, 'first_name': 'luckydonald', 'username': 'luckydonald', 'type': 'private'
            }, 'date': 1592231305, 'text': '\u200eSent by user Luckydonald.',
            'entities': [
                {
                    'offset': 0, 'length': 1, 'type': 'text_mention',
                    'user': {
                        'id': 10717954, 'is_bot': False, 'first_name': 'luckydonald', 'username': 'luckydonald',
                        'language_code': 'de'
                    }
                },
                {
                    'offset': 14, 'length': 11, 'type': 'text_link',
                    'url': 'https://t.me/luckydonald'
                }
            ]
        })
    ) == 10717954
