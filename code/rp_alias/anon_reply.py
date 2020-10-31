#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
from html import escape
from typing import Union

from luckydonaldUtils.logger import logging

__author__ = 'luckydonald'

from pytgbot.api_types.receivable.media import MessageEntity

from pytgbot.api_types.receivable.updates import Message

logger = logging.getLogger(__name__)
if __name__ == '__main__':
    logging.add_colored_handler(level=logging.DEBUG)
# end if

LINK = '<a href="{link}">{label}</a>'

ZERO_WIDTH_SPACE = "‎"
ZERO_WIDTH_SPACE = "⤷ "
ZERO_WIDTH_SPACE_LEN = len(ZERO_WIDTH_SPACE)
INVISIBLE_LINK = LINK.format(link='{link}', label=ZERO_WIDTH_SPACE)

USER_URL_TEMPLATE = "tg://user?id={user_id}"
USER_URL_REGEX_STR = "tg://user\?id=(?P<user_id>\d+)"
USER_URL_REGEX = re.compile(USER_URL_REGEX_STR)


def build_reply_message(user_id: int, user_name: str, username: Union[str, None]):
    user_url = USER_URL_TEMPLATE.format(user_id=user_id)
    at_user_url = f"https://t.me/{username}" if username else user_url
    invisible_link = INVISIBLE_LINK.format(link=user_url)
    visible_link = LINK.format(link=at_user_url, label=escape(user_name))
    return f"{invisible_link}Sent by user {visible_link} (<code>{user_id}</code>)."  # TODO: l18n
# end def


def detect_anon_user_id(reply_to_message: Message) -> Union[None, int]:
    if not reply_to_message:
        logger.debug('no reply.')
        return None
    if reply_to_message.text and reply_to_message.text.startswith(ZERO_WIDTH_SPACE):
        logger.debug('found ZERO_WIDTH_SPACE.')
    else:
        logger.debug('no ZERO_WIDTH_SPACE.')
        return None
    # end if
    if not reply_to_message.entities:
        logger.debug('no entities')
        return None
    # end if
    if not len(reply_to_message.entities) > 0:
        logger.debug('at least one entity')
        return None
    # end if

    entity: MessageEntity = reply_to_message.entities[0]
    if entity.type == "code" and len(reply_to_message.entities) == 1:
        logger.debug('looks like code only')
        number_str = reply_to_message.text[entity.offset: entity.offset + entity.length]
        try:
            return int(number_str)
        except (ValueError, TypeError):
            logger.debug(f'could not parse code: {number_str!r}')
        # end try
    # end if

    if not len(reply_to_message.entities) > 1:
        logger.debug('not enough entities for non-code')
        return None
    # end if

    if not entity.offset == 0:
        logger.debug('offset not zero')
        return None
    # end if
    if not entity.length == ZERO_WIDTH_SPACE_LEN:
        logger.debug('length of entity wrong.')
        return None
    # end if
    if not entity.type in ("url", "text_mention"):
        logger.debug('wrong entity type')
        return None
    # end if
    if not len(reply_to_message.entities) > 1:
        logger.debug('not enough entities')
        return None
    # end if

    logger.debug('Is indeed a link.')

    if entity.type == 'text_mention':
        logger.debug(f'got direct mention of user {entity.user}.')
        return entity.user.id
    else:
        logger.debug(f'got tg:// link with url {entity.url!r}.')
        assert entity.type == 'url'
        url = entity.url
        m = USER_URL_REGEX.match(url)
        if not m:
            logger.debug('regex didn\'t match.')
            return None
        # end if
        user_id = m.groupdict().get('user_id', None)
        logger.debug(f'got user via match: {user_id}.')
        return user_id
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
