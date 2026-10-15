import re

from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import CommandHandler

from database import mongo, users
from keyboards.main_menu import start_menu

HTML = ParseMode.HTML

# Photo link for the /start card (empty = text only until the owner drops a URL here)
WELCOME_PHOTO = ""

# The fancy welcome card — [NNN] numbers are premium (custom) emoji ids
_WELCOME = (
    '<tg-emoji emoji-id="5999025042753590996">✨</tg-emoji>𝑯̲𝒆̲𝒚̲, 𝑾̲𝒆̲𝒍̲𝒄̲𝒐̲𝒎̲𝒆̲ 𝑻̲𝒐̲ 𝑺̲𝒉̲𝒊̲𝒏̲𝒐̲𝒃̲𝒖̲ '
    '<tg-emoji emoji-id="6174884334114182449">✨</tg-emoji>\n\n'
    '<tg-emoji emoji-id="6001564910318786723">✨</tg-emoji> 𝗖̲𝗵̲𝗮̲𝘁̲ &𝗙̲𝗿̲𝗶̲𝗲̲𝗻̲𝗱̲𝘀̲\n'
    '<tg-emoji emoji-id="6127558265573218459">✨</tg-emoji> 𝑹̲𝒐̲𝒎̲𝒂̲𝒏̲𝒄̲𝒆̲ &𝑭̲𝒍̲𝒊̲𝒓̲𝒕̲\n'
    '<tg-emoji emoji-id="5258508428212445001">✨</tg-emoji> 𝟮𝟬+ 𝗚̲𝗮̲𝗺̲𝗲̲𝘀̲ 𝗔̲𝘃̲𝗮̲𝗶̲𝗹̲𝗮̲𝗯̲𝗹̲𝗲\n\n'
    '<tg-emoji emoji-id="6124898345082165755">✨</tg-emoji> 𝑪𝒉𝒂𝒕 • 𝑭𝒍𝒊𝒓𝒕 • 𝑷𝒍𝒂𝒚 '
    '<tg-emoji emoji-id="6127546175240280564">✨</tg-emoji>'
)


def _plain(text):
    """Drop tg-emoji entities (keep the fallback emoji) — used if this bot
    can't send custom emoji (owner without Telegram Premium, dead id, ...)."""
    return re.sub(r"<tg-emoji[^>]*>([^<]*)</tg-emoji>", r"\1", text)


async def start(update, ctx):
    u = update.effective_user
    await users.ensure_user(u)

    msg = update.effective_message
    markup = start_menu(ctx.bot.username)
    try:
        if WELCOME_PHOTO:
            await msg.reply_photo(WELCOME_PHOTO, caption=_WELCOME, parse_mode=HTML, reply_markup=markup)
        else:
            await msg.reply_text(_WELCOME, parse_mode=HTML, reply_markup=markup)
    except BadRequest:
        # custom emoji rejected — same card without premium emojis
        if WELCOME_PHOTO:
            await msg.reply_photo(WELCOME_PHOTO, caption=_plain(_WELCOME), parse_mode=HTML, reply_markup=markup)
        else:
            await msg.reply_text(_plain(_WELCOME), parse_mode=HTML, reply_markup=markup)


def register(app):
    app.add_handler(CommandHandler("start", start))
