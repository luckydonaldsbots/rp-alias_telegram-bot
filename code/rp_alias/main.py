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
from pytgbot.api_types.sendable.inline import InlineQueryResultArticle, InputTextMessageContent
from pytgbot.exceptions import TgApiServerException

from pytgbot.api_types.receivable.updates import Update
from pytgbot.api_types.receivable.updates import Message as TGMessage
from pytgbot.api_types.receivable.peer import User as TGUser, Chat as TGChat
from pytgbot.api_types.sendable.reply_markup import ForceReply, ReplyKeyboardRemove

from teleflask.new_messages import TextMessage
from teleflask.messages import HTMLMessage
from teleflask.server import Teleflask

from .secrets import API_KEY, HOSTNAME
from .sentry import add_error_reporting

__author__ = 'luckydonald'

logger = logging.getLogger(__name__)
logging. add_colored_handler(level=logging.DEBUG)

app = Flask(__name__)
app.register_blueprint(version_bp)
sentry = add_error_reporting(app)

bot = Teleflask(API_KEY, app)
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


@app.route("/rp_bot_webhooks/<int:admin_user_id>/<base64_prefix>/<base64_api_key>", methods=['POST'])
def rp_bot_webhooks(admin_user_id: int, base64_prefix: str, base64_api_key: str):
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
    if not update.message and not update.inline_query:
        logger.debug('not an message or inline_query')
        return "OK"
    # end if


    prefix = n(urlsafe_b64decode(base64_prefix))
    api_key = n(urlsafe_b64decode(b(base64_api_key)))
    rp_bot = Bot(api_key)

    if update.inline_query:
        inline_query = update.inline_query
        if inline_query.from_peer.id != admin_user_id:
            rp_bot.answer_inline_query(inline_query_id=inline_query.id, results=[])
            return 'OK'
        # end if
        text = inline_query.query
        id = urlsafe_b64encode(text)
        rp_bot.answer_inline_query(inline_query_id=inline_query.id, results=[
            InlineQueryResultArticle(
                id=id, title='Send as this character',
                input_message_content=InputTextMessageContent(
                    message_text=text,
                    parse_mode='',
                    disable_web_page_preview=True,
                )
            )
        ])
        return 'OK'
    # end if

    assert update.message
    msg: TGMessage = update.message
    if not msg.text and not msg.caption:
        logger.info('not an message with text/caption')
        return "OK"
    # end if

    if msg.chat.type == 'private':
        return process_private_chat(update, admin_user_id, prefix, rp_bot)
    else:
        return process_public_prefix(msg, admin_user_id, prefix, rp_bot)
    # end def
# end def


def process_private_chat(update: Update, admin_user_id: int, prefix: str, rp_bot: Bot):
    msg = update.message
    assert msg.chat.id == msg.from_peer.id
    logger.debug(
        f'message user: {msg.from_peer.id}, admin user: {admin_user_id}, has forward: {msg.reply_to_message is not None}'
    )
    if msg.text and msg.text == '/start':
        # somebody typed the /start command.
        logger.debug('somebody typed the /start command.')
        send_msg = help_cmd(
            update=Update(update_id=-1, message=msg), text='',
        )
        reply_chat, reply_msg = bot.msg_get_reply_params(update)
        # noinspection PyProtectedMember
        send_msg._apply_update_receiver(receiver=reply_chat, reply_id=reply_msg)
        send_msg.send(rp_bot)
    # end if
    if msg.from_peer.id != admin_user_id:
        # other user want to send something to us.
        logger.debug('other user want to send something to us.')
        rp_bot.forward_message(admin_user_id, from_chat_id=msg.chat.id, message_id=msg.message_id)
    else:
        # we wrote the bot
        logger.debug('owner wrote the bot.')
        if msg.reply_to_message and msg.reply_to_message.forward_from:
            # we replied to a forwarded message.
            logger.debug('owner replied to message.')
            copy_message(chat_id=msg.reply_to_message.forward_from.id, msg=msg, reply_to_message_id=None, rp_bot=rp_bot)
        else:
            # we wrote the bot, not as reply -> return as if prefixed.
            logger.debug('owner wrote the bot, not as reply -> return as if prefixed.')
            copy_message(chat_id=msg.from_peer.id, msg=msg, reply_to_message_id=msg.message_id, rp_bot=rp_bot)
        # end if
    # end if
    return 'OK'
# end def


def process_public_prefix(msg: TGMessage, admin_user_id: int, prefix: str, rp_bot: Bot):
    if msg.from_peer.id != admin_user_id:
        logger.info('not an message of an legit user')
        return 'OK'
    # end if
    if msg.text:
        text = msg.text
    else:
        text = msg.caption
    # end if
    if not text.startswith(prefix):
        logger.info(f'text has not the prefix {prefix!r}: {text!r}')
        return "OK"
    # end if

    # remove the prefix from the text
    text = text[len(prefix):].strip()
    chat_id = msg.chat.id
    message_id = msg.message_id
    reply_to_message_id = msg.reply_to_message.message_id if msg.reply_to_message else None

    if message_reply_edit_or_delete(chat_id, message_id, msg, rp_bot, text):
        return 'OK'
    # end if

    message_echo_and_delete_original(chat_id, message_id, msg, reply_to_message_id, rp_bot, text)
    return "OK"
# end def


def message_reply_edit_or_delete(chat_id, message_id, msg, rp_bot: Bot, text):
    """

    :param api_key:
    :param chat_id:
    :param msg:
    :param rp_bot:
    :param text:
    :return: if we had to act, or at least tried. I.e. if it should not be echoed.
    """
    rmsg = msg.reply_to_message
    api_key = rp_bot.api_key
    rp_bot_id = int(api_key.split(":")[0])
    if not msg.text or not rmsg or not rmsg.from_peer or not rmsg.from_peer.id == rp_bot_id:
        return False  # not relevant
    # end if
    # they replied to a message of the rp_bot.
    try:
        try:
            rp_bot.delete_message(  # delete /delete or edit command message.
                message_id=message_id, chat_id=chat_id,
            )
        except TgApiServerException as e:
            logger.warn('deleting edit message failed', exc_info=True)
        # end try

        if text == "/delete":
            rp_bot.delete_message(
                message_id=rmsg.message_id, chat_id=chat_id,
            )
            return True  # we did
        elif rmsg.text:
            # text message
            rp_bot.edit_message_text(
                text=text, parse_mode='',
                message_id=rmsg.message_id, chat_id=chat_id,
            )
            return True  # we did
        elif rmsg.caption or rmsg.photo or rmsg.document:
            rp_bot.edit_message_caption(
                caption=text, parse_mode='',
                message_id=rmsg.message_id, chat_id=chat_id,
            )
            return True  # we did
        # end if
    except TgApiServerException as e:
        logger.warn('editing failed', exc_info=True)
        return True  # we did try
    # end try
    pass
# end def


def message_echo_and_delete_original(chat_id, message_id, msg, reply_to_message_id, rp_bot, text):
    try:
        copy_message(chat_id, msg, reply_to_message_id, rp_bot, text)
    except TgApiServerException as e:
        logger.warn('sending failed', exc_info=True)
    # end try
    try:
        bot.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except TgApiServerException as e:
        logger.debug('deletion with bot.bot failed', exc_info=True)
    # end try
    try:
        rp_bot.delete_message(chat_id=chat_id, message_id=message_id)
    except TgApiServerException as e:
        logger.debug('deletion with rp_bot failed', exc_info=True)
    # end try
# end def


def copy_message(chat_id, msg, reply_to_message_id, rp_bot: Bot, text: Union[str, None] = None):
    if not text:
        text = msg.text if msg.text else msg.caption
    # end def
    if msg.text:
        return rp_bot.send_message(
            text=text,
            chat_id=chat_id, parse_mode='',
            disable_notification=False, reply_to_message_id=reply_to_message_id,
        )
    # end if
    if msg.photo:
        return rp_bot.send_photo(
            photo=msg.photo[0].file_id,
            chat_id=chat_id, parse_mode='',
            caption=text,
            disable_notification=False, reply_to_message_id=reply_to_message_id,
        )
    # end if
    if msg.document:
        return rp_bot.send_document(
            document=msg.document.file_id,
            chat_id=chat_id, parse_mode='',
            caption=text,
            disable_notification=False, reply_to_message_id=reply_to_message_id,
        )
    # end if
# end def


@bot.command("start")
def start(update, text):
    return HTMLMessage('Hello. Do you seek /help?')
# end def


@bot.command("help")
def help_cmd(update: Update, text: str):
    assert isinstance(update, Update)
    return HTMLMessage(
        'Go ahead, set up your bot you wanna use for RPing with @BotFather first:\n'
        'Write <code>/addbot</code> to @BotFather, set your name and a username (e.g. <code>CharacterName_RPBot</code>).\n'
        'You can set up a profile picture there too with <code>/setuserpic</code>.\n'
        'Make sure you\'re set up the privacy of your bot (<code>/setprivacy</code>) to disabled, so this service can receive your messages.'
        ' The alternative is to use the @username (in our example <code>@CharacterName_RPBot</code> of your bot as an prefix when registering your bot.\n\n'
        'After that, use /add_bot.'
    )
# end def


@bot.command("add_bot")
def cmd_set_welcome(update, text):
    if not text:
        text = ""  # fix None.split(…)
    # end if
    texts = text.split('\n')
    if len(texts) != 2:
        text = None  # cheap way to get the error message.^
    elif not text[0] or not text[1]:
        text = None  # cheap way to get the error message.
    # end if

    if not text:
        return HTMLMessage(
            "Please send your bot and prefix like this:\n"
            "<pre>/add_bot {API-KEY}\n"
            "{PREFIX}</pre>\n"
            "So on the line with the /add_bot you put your bot API key, "
            "and on the second line the prefix you wanna use.\n"
            # "\n"
            # "<i>For example, if you have a character called Littlepip, you could register the prefix <code>pip</code>.</i>\n"
            # "<i>That would look like </i>"
        )
    # end if
    api_key, prefix = texts
    prefix_based = n(urlsafe_b64encode(b(prefix)))
    api_key_based = n(urlsafe_b64encode(b(api_key)))
    rp_bot = Bot(api_key)
    try:
        rp_me = rp_bot.get_me()
        webhook_url = url_for('rp_bot_webhooks', admin_user_id=update.message.from_peer.id, base64_prefix=prefix_based, base64_api_key=api_key_based)
        webhook_url = f"https://{HOSTNAME}{webhook_url}"
        logger.debug(f'setting webhook to {webhook_url!r}')
        rp_bot.set_webhook(webhook_url)
        return (
            f"Successfully registered {rp_me.first_name}.\n"
            f"Start any message with {prefix!r} to have it be replied by the bot.\n"
            f"If you allow either your bot @{rp_me.username} or this bot @{bot.username} as admin in the chat you're "
            f"roleplaying in, it will delete your original message automatically."
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
