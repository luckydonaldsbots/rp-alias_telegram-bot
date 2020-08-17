# -*- coding: utf-8 -*-
from base64 import urlsafe_b64encode, urlsafe_b64decode
from html import escape
from flask import Flask, url_for
from typing import Union
from datetime import datetime, timedelta
from DictObject import DictObject
from luckydonaldUtils.holder import Holder
from luckydonaldUtils.logger import logging
from luckydonaldUtils.encoding import to_native as n, to_binary as b
from luckydonaldUtils.tg_bots.gitinfo import version_bp, version_tbp
from luckydonaldUtils.tg_bots.peer.chat.format import format_chat
from luckydonaldUtils.tg_bots.peer.user.format import format_user
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

from .fake_reply import build_fake_reply
from .anon_reply import build_reply_message, detect_anon_user_id
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
        return process_public_chat(msg, admin_user_id, prefix, rp_bot)
    # end def
# end def


def process_private_chat(update: Update, admin_user_id: int, prefix: str, rp_bot: Bot):
    msg = update.message
    assert msg.chat.id == msg.from_peer.id
    logger.debug(
        f'message user: {msg.from_peer.id}, admin user: {admin_user_id}, has forward: {msg.reply_to_message is not None}'
    )
    if msg.text and msg.text == '/start':
        # somebody typed the /start command - that is either the owner or the user.
        logger.debug('somebody typed the /start command.')
        if msg.chat.id == admin_user_id:
            # owner started the bot
            send_msg = HTMLMessage(
                f'<i>Greetings.\n'
                f'This is your own bot, set up with the prefix {escape(prefix)!r}.\n'
                f'Here I will forward you any messages from users writing to this bot directly.\n'
                f'Reply to those messages to send them an answer.\n'
                f'\n'
                f'If it doesn\'t find the message you replied to (that is you didn\'t reply to any user, or the user\'s privacy settings disallow forwards) it will instead echo what you wrote.</i>'
            )
        else:
            # other user started the bot
            rp_me = rp_bot.get_me()
            send_msg = HTMLMessage(
                f'<i>Greetings.\n'
                f'Your communication with the owner of <b>{escape(rp_me.first_name)!r}</b> is now ready.</i>\n'
                f'<i>PS: You can set up your own with</i> @{bot.username}<i>.</i>'
            )
        # end if
        reply_chat, reply_msg = bot.msg_get_reply_params(update)
        # noinspection PyProtectedMember
        send_msg._apply_update_receiver(receiver=reply_chat, reply_id=reply_msg)
        try:
            send_msg.send(rp_bot)
        except TgApiServerException as e:
            logger.warning('failed to post /start greeting message.', exc_info=True)
        # end try
    # end if
    if msg.from_peer.id != admin_user_id:
        # other user want to send something to us.
        logger.debug('other user want to send something to us.')
        fwd_msg = rp_bot.forward_message(admin_user_id, from_chat_id=msg.chat.id, message_id=msg.message_id)
        if fwd_msg.forward_from is None:
            logger.debug(f'detected anon forward: {msg.chat.id}')
        # end def
        user_name = ""
        user_name += msg.from_peer.first_name if msg.from_peer.first_name else ""
        user_name += " "
        user_name += msg.from_peer.last_name if msg.from_peer.last_name else ""
        user_name = user_name.strip()

        try:
            rp_bot.send_message(
                chat_id=admin_user_id,
                text=build_reply_message(msg.chat.id, user_name, msg.from_peer.username),
                parse_mode='html',
                reply_to_message_id=fwd_msg.message_id,
            )
        except TgApiServerException as e:
            logger.warning('failed to post anon_reply message.', exc_info=True)
        # end try
    else:
        # we wrote the bot
        logger.debug('owner wrote the bot.')
        user_id_holder = Holder()
        if msg.reply_to_message and msg.reply_to_message.forward_from:
            # we replied to a forwarded message.
            logger.debug('owner replied to message.')
            copy_message(chat_id=msg.reply_to_message.forward_from.id, msg=msg, reply_to_message_id=None, rp_bot=rp_bot)
        elif msg.reply_to_message and user_id_holder(detect_anon_user_id(msg.reply_to_message)):
            logger.debug('owner replied to anon_reply message.')
            copy_message(chat_id=user_id_holder.get(), msg=msg, reply_to_message_id=None, rp_bot=rp_bot)
        else:
            # we wrote the bot, not as reply -> return as if prefixed.
            logger.debug('owner wrote the bot, not as reply -> return as if prefixed.')
            copy_message(chat_id=msg.from_peer.id, msg=msg, reply_to_message_id=msg.message_id, rp_bot=rp_bot)
        # end if
    # end if
    return 'OK'
# end def


def process_public_chat(msg: TGMessage, admin_user_id: int, prefix: str, rp_bot: Bot):
    rp_bot_id = int(rp_bot.api_key.split(":")[0])
    rmsg = msg.reply_to_message

    if msg.from_peer.id != admin_user_id:
        # if someone replied to us, notify the owner.
        if rmsg and rmsg.from_peer and rmsg.from_peer.id == rp_bot_id:
            # is indeed a reply to this bot.
            logger.debug(f'is reply: from {msg.from_peer.id!r} to bot {rp_bot_id!r} of user {admin_user_id!r}.')
            chat_html = format_chat(msg.chat)
            user_html = format_user(
                msg.from_peer,
                do_link=True, prefer_username=False, id_fallback=True, user_tag='b', id_tag='code', html_escape=True
            )
            message_text = f'In chat {chat_html} user {user_html} replied to this bot\'s message'

            if msg.chat.type == 'supergroup':
                if msg.chat.username:
                    chat_link = msg.chat.username  # t.me/username
                else:
                    # -1001309571967
                    # =>  1309571967
                    chat_link = str(msg.chat.id)
                    if chat_link.startswith('-100'):
                        chat_link = chat_link[4:]
                    # end if
                    chat_link = "c/" + chat_link  # t.me/c/123456/123
                # end if
                message_text = (
                    f'{message_text}:\n'
                    f'<a href="https://t.me/{chat_link}/{msg.message_id}">→ Go to message</a>'
                )
            else:
                # regular groups don't support this.
                message_text = f'{message_text}.'
            # end if

            try:
                rp_bot.send_message(
                    chat_id=admin_user_id,
                    text=message_text, parse_mode='html',
                )
            except:
                logger.warning('failed to notify about reply', exc_info=True)
            # end try
            return 'OK'
        # end if
        logger.info(f'not an message of an legit user: is {msg.from_peer.id!r}, should be {admin_user_id!r}.')
        return 'OK'  # we ignored or reacted.
    # end if

    if msg.text:
        text = msg.text
    else:
        text = msg.caption
    # end if
    chat_id = msg.chat.id
    message_id = msg.message_id
    reply_to_message_id = rmsg.message_id if rmsg else None

    if text.startswith('/delete') or text.startswith('/edit'):
        if not rmsg or not rmsg.from_peer or not rmsg.from_peer.id == rp_bot_id:
            logger.info(f'text is a \'/delete\' or \'/edit\' command, but reply is not existent or that message is not from  this bot ({rp_bot_id}): {text!r}')
            # TODO: maybe yell "reply this to a valid command", if it was not replied to something?
            return 'OK'  # not relevant
        # end if

        if text.startswith('/delete') and (
            text == '/delete' or
            text.startswith('/delete ') or
            (text.startswith('/delete@') and text.startswith(f'/delete@{rp_bot.username}'))  # rp_bot.username is a costly API operation, so only do that if really needed.
        ):
            try:
                rp_bot.delete_message(
                    message_id=rmsg.message_id, chat_id=chat_id,
                )
            except:
                logger.warning('deletion of RP message failed', exc_info=True)
            # end if
            failsafe_multibot_delete(rp_bot=rp_bot, message_id=message_id, chat_id=chat_id, of_something='/delete message')
            return 'OK'  # we're done
        # end if
        if text == '/edit':
            # TODO: send 'You can't edit to empty, use /delete to delete.'
            return 'OK'
        if text.startswith('/edit') and (
            text.startswith('/edit ') or
            (text.startswith('/edit@') and text.startswith(f'/edit@{rp_bot.username} '))  # rp_bot.username is a costly API operation, so only do that if really needed.
        ):
            text = text.split(' ', maxsplit=1)[1].strip()  # remove the '/edit ' part of '/edit foo', including any following leading whitespaces.
            fake_reply = ''  # TODO: keep old reply.

            try:
                if rmsg.text:
                    # text message
                    rp_bot.edit_message_text(
                        text=fake_reply + escape(text), parse_mode='html',
                        message_id=rmsg.message_id, chat_id=chat_id,
                    )
                elif rmsg.caption or rmsg.photo or rmsg.document:
                    rp_bot.edit_message_caption(
                        caption=fake_reply + escape(text), parse_mode='html',
                        message_id=rmsg.message_id, chat_id=chat_id,
                    )
                # end if
                failsafe_multibot_delete(rp_bot=rp_bot, message_id=message_id, chat_id=chat_id, of_something='/edit message')
                return 'OK'  # we're done
            except:
                logger.warning('edit failed', exc_info=True)
                return 'OK'  # at least we tried...
            # end if
        # end if
    # end if

    # now we have the commands done, it's all about posting a new post.
    if not text.startswith(prefix):
        # not a suffix, so no posting.
        logger.info(f'text has not the required prefix {prefix!r}: {text!r}')
        return "OK"
    # end if

    fake_reply = ''
    if rmsg.from_peer.is_bot and rmsg.from_peer.id != rp_bot_id if rmsg else False:
        fake_reply = build_fake_reply(chat_id=chat_id if rmsg.chat.type == 'supergroup' else None, user_id=rmsg.from_peer.id, name=rmsg.from_peer.first_name, reply_id=reply_to_message_id, old_text=rmsg.caption if rmsg.caption else rmsg.text)
    # end if

    # remove the prefix from the text
    text = text[len(prefix):].strip()
    message_echo_and_delete_original(chat_id, message_id, msg, reply_to_message_id, rp_bot, fake_reply + escape(text))
    return "OK"
# end def


def message_echo_and_delete_original(chat_id, message_id, msg, reply_to_message_id, rp_bot, text):
    try:
        copy_message(chat_id, msg, reply_to_message_id, rp_bot, text)
    except TgApiServerException as e:
        logger.warn('sending failed', exc_info=True)
    # end try
    failsafe_multibot_delete(rp_bot=rp_bot, message_id=message_id, chat_id=chat_id, of_something='original message')
# end def


def failsafe_multibot_delete(rp_bot, message_id, chat_id, of_something='message'):
    try:
        bot.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except TgApiServerException as e:
        logger.debug(f'deletion of {of_something} with bot.bot failed', exc_info=True)
    # end try
    try:
        rp_bot.delete_message(chat_id=chat_id, message_id=message_id)
    except TgApiServerException as e:
        logger.debug(f'deletion of {of_something} with rp_bot failed', exc_info=True)
    # end try
# end def


def copy_message(chat_id, msg, reply_to_message_id, rp_bot: Bot, text: Union[str, None] = None):
    if not text:
        text = escape(msg.text) if msg.text else msg.caption
    # end def
    if msg.text:
        return rp_bot.send_message(
            text=text, parse_mode='html',
            chat_id=chat_id,
            disable_notification=False, reply_to_message_id=reply_to_message_id,
        )
    # end if
    if msg.photo:
        return rp_bot.send_photo(
            photo=msg.photo[0].file_id,
            chat_id=chat_id,
            caption=text, parse_mode='html',
            disable_notification=False, reply_to_message_id=reply_to_message_id,
        )
    # end if
    if msg.document:
        return rp_bot.send_document(
            document=msg.document.file_id,
            chat_id=chat_id,
            caption=text, parse_mode='html',
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
        '\n'
        '<b>1.</b> Write <code>/addbot</code> to @BotFather, set your <u>character\'s name</u> and then a <u>fitting username</u>.\n'
        '<i>E.g.<code>Character Name</code> and then as username <code>CharacterName_RPBot</code></i>.\n'
        '\n'
        '<b>2.</b> Make sure you\'re set up the <u>privacy of your bot</u> (<code>/setprivacy</code>) to <u>disabled</u>, so this service can receive your messages, even if you don\'t mention the bot\'s @username.\n'
        '<i>The alternative, of you don\'t want to disavle the privacy mode, is to use the bot\'s @username (in our example <code>@CharacterName_RPBot</code> of your bot as the prefix later.</i>\n'
        '\n'
        '<b>3.</b> You can set up a <u>profile picture</u> there too with <code>/setuserpic</code>.\n'
        '\n'
        '<b>4.</b> It is helpful to others if you add a <u>about text</u> (bio) for your bot with <code>/setabouttext</code>.\n'
        f'<i>Usually that should contain a description about the character, maybe a @username of the owner for direct contact and a "Powered by</i> @{bot.username}<i>" would be really supportive!</i>\n'
        '\n'
        '<b>5.</b> After that, <u>come back to this bot</u> and use /add_bot to finally let it listen and respond to messages.\n'
        '<b>6.</b> To test, you should then start your bot (either there\'s a big start button where usually the text box would be, or send /start to it). It should respond to your messages there.'
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
            "So on the <b>same line with the /add_bot</b> you put your bot API key, "
            "and on the <b>second line</b> the prefix you wanna use.\n"
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
        return [
            HTMLMessage(
            f"Successfully registered {rp_me.first_name}.\n"
            f"Please now start your own bot (@{rp_me.username}) by sending <code>/start</code> to it.\n"
            ),
            HTMLMessage(
                f"<b>How to use our bot @{rp_me.username} in groups</b> (The bot needs to be member of the group, additional admin to clean up your messages)\n"
                f""
                f"Start any message with <b>{escape(prefix)!r}</b> to have it be echoed by the bot.\n"
                f"\n"
                f"You can then reply with <code>/edit NEW TEXT</code> to a post by the bot to replace text or caption with <code>NEW TEXT</code>.\n"
                f"Reply <code>/delete</code> to a message of the bot to have it deleted.\n"
                f"\n"
                f"If you allow either your bot @{rp_me.username} or this bot @{bot.username} as admin in the chat you're "
                f"roleplaying in, it will delete your original message (the one with the prefix) automatically, so you don't end up with the text always being there twice."
            ),
        ]
    except TgApiServerException as e:
        return f"Error: {e!s}"
    # end try
# end def



if __name__ == "__main__":  # no nginx
    # "__main__" means, this python file is called directly.
    # not to be confused with "main" (because main.py) when called from from nginx
    app.run(host='0.0.0.0', debug=True, port=80)  # python development server if no nginx
# end if
