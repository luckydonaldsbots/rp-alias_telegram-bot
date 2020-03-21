# -*- coding: utf-8 -*-
from base64 import urlsafe_b64encode, urlsafe_b64decode
from html import escape
from flask import Flask, url_for
from typing import Union
from datetime import datetime, timedelta
from DictObject import DictObject
from luckydonaldUtils.logger import logging
from luckydonaldUtils.encoding import to_native as n, to_binary as b
from luckydonaldUtils.tg_bots.gitinfo import version_bp, version_tbp
from pytgbot import Bot
from pytgbot.exceptions import TgApiServerException

logging.add_colored_handler(level=logging.DEBUG)
from pytgbot.api_types.receivable.updates import Update
from pytgbot.api_types.receivable.updates import Message as TGMessage
from pytgbot.api_types.receivable.peer import User as TGUser, Chat as TGChat
from pytgbot.api_types.sendable.reply_markup import ForceReply, ReplyKeyboardRemove

from teleflask.new_messages import TextMessage
from teleflask.messages import HTMLMessage
from teleflask.server import Teleflask

from .secrets import API_KEY
from .sentry import add_error_reporting

__author__ = 'luckydonald'

logger = logging.getLogger(__name__)
logging.add_colored_handler(level=logging.DEBUG)

app = Flask(__name__)
app.register_blueprint(version_bp)
sentry = add_error_reporting(app)

bot = Teleflask(API_KEY, app)
bot.register_tblueprint(version_tbp)
# bot.on_startup(set_up_mongodb)
bot.register_tblueprint(version_tbp)


@app.route("/")
def hello():
    return "Your advertisements could be here!"
# end def


@app.route("/healthcheck")
def url_healthcheck():
    """
    :return:
    """
    return 'kk', 200
# end def

@app.route("/bot_webhooks/{int:user_id}/{base64_prefix}/{api_key}")
def other_bot_updates(self, user_id: int, base64_prefix: str, api_key: str):
    """
    This processes incoming telegram updates.

    :return:
    """
    from pprint import pformat
    from flask import request

    logger.debug("INCOME:\n{}\n\nHEADER:\n{}".format(
        pformat(request.get_json()),
        request.headers if hasattr(request, "headers") else None
    ))
    update = Update.from_array(request.get_json())
    if not update.message:
        logger.debug('not an message')
        return
    # end if
    msg: TGMessage = update.message
    if msg.from_peer.id != user_id:
        logger.debug('not an message of an legit user')
    if not msg.text and not msg.caption:
        logger.debug('not an message with text/caption')
        return
    # end if

    if msg.text:
        text = msg.text
    else:
        text = msg.caption
    # end if
    prefix = n(urlsafe_b64decode(base64_prefix))
    if not text.startswith(prefix):
        logger.debug('not the prefix')
        return
    # end if

    # remove the prefix from the text
    text = text[len(prefix):].strip()
    message_id = msg.reply_to_message.message_id if msg.reply_to_message else None

    rp_bot = Bot(api_key)
    try:
        if msg.text:
            rp_bot.send_message(
                text=text,
                chat_id=msg.chat.id, parse_mode='markdownv2',
                disable_notification=False, reply_to_message_id=message_id,
            )
        # end if
        if msg.photo:
            rp_bot.send_photo(
                photo=msg.photo[0].file_id,
                chat_id=msg.chat.id, parse_mode='markdownv2',
                disable_notification=False, reply_to_message_id=message_id,
            )
        # end if
        if msg.document:
            rp_bot.send_document(
                document=msg.document.file_id,
                chat_id=msg.chat.id, parse_mode='markdownv2',
                disable_notification=False, reply_to_message_id=message_id,
            )
        # end if
    except TgApiServerException as e:
        logger.warn('sending failed', exc_info=True)
    # end try
    return
# end def


@bot.command("start")  # /start {chat_id}_{do_not_track}
def start(update, text):
    return TextMessage('hello.', parse_mode="html")
# end def


@bot.command("help")
def help_cmd(update: Update, text: str):
    assert isinstance(update, Update)
    return HTMLMessage(
        'currently, I\'m not helpful.\n'
        'But go ahead, set up your bot you wanna use for RPing with @BotFather.\n'
        'You can set up a profile picture there too (<code>/setuserpic</code>).\n'
        'Make sure you\'re set up the privacy of your bot (<code>/setprivacy</code>) to disabled, so it can receive your messages.'
        ' The alternative is to use the @username of your bot as an prefix when registering your bot.\n\n'
        'After that, use /add_bot.'
    )
# end def


@bot.command("add_bot")
def cmd_set_welcome(update, text):
    texts = text.split('\n')
    if len(texts) != 2:
        text = None  # cheap way to get the error message.^
    # end if
    if not text[0] or not text[1]:
        text = None  # cheap way to get the error message.
    # end def
    if not text:
        return "Please send your bot and prefix like this:\n" \
               "<pre>/add_bot {API-KEY}\n" \
               "{PREFIX}</pre>\n" \
               "So on the line with the /add_bot you put your bot API key, and on the second line the prefix you wanna use."
    # end if
    api_key, prefix = texts
    prefix = n(urlsafe_b64encode(b(prefix)))
    rp_bot = Bot(api_key)
    try:
        rp_me = rp_bot.get_me()
        webhook_url = url_for('other_bot_updates', user_id=update.message.from_peer.id, base64_prefix=prefix, api_key=api_key)
        logger.debug(f'setting webhook to {webhook_url!r}')
        rp_bot.set_webhook(webhook_url)
        return (
            f"Successfully registered {rp_me.first_name}.\n"
            f"Start any message with {prefix!r} to have it be replied by the bot.\n"
            f"If you allow either your bot @{rp_me.username} or this bot @{bot.username} in the chat you're roleplaying"
            f", it will delete your original message automatically."
        )
    except TgApiServerException as e:
        return f"Error: {e!s}"
    # end try
# end def



if __name__ == "__main__":  # no nginx
    # "__main__" means, this python file is called directly.
    # not to be confused with "main" (because main.py) when called from from nginx
    app.run(host='0.0.0.0', debug=True, port=80)  # python development server if no nginx
# end if
