import re

from telegram.constants import ParseMode
from telegram.ext import CommandHandler

from database import mongo, users
from keyboards.main_menu import start_menu

HTML = ParseMode.HTML

# Banner video for /start (direct mp4 URL; empty = text-only card)
WELCOME_VIDEO = "https://files.catbox.moe/67cn97.mp4"

# The fancy welcome card — [NNN] numbers are premium (custom) emoji ids
PUZZLE_PIECES = (
    "5332740426753418006", "5332793770247233984", "5334823198129168314",
    "5332386152081038791", "5332491133966659316", "5334749990411608332",
)
# the 6 sticker pieces, one line lower and shifted further right:
# 3 next to "Romance & Flirt", 3 next to "20+ Games Available"
_PAD = "\u00a0"
_PUZZLE_R1 = "".join(f'<tg-emoji emoji-id="{n}">\U0001f9e9</tg-emoji>' for n in PUZZLE_PIECES[:3])
_PUZZLE_R2 = "".join(f'<tg-emoji emoji-id="{n}">\U0001f9e9</tg-emoji>' for n in PUZZLE_PIECES[3:])

_WELCOME = (
    '<tg-emoji emoji-id="5999025042753590996">✨</tg-emoji>𝑯̲𝒆̲𝒚̲, 𝑾̲𝒆̲𝒍̲𝒄̲𝒐̲𝒎̲𝒆̲ 𝑻̲𝒐̲ 𝑺̲𝒉̲𝒊̲𝒏̲𝒐̲𝒃̲𝒖̲ '
    '<tg-emoji emoji-id="6174884334114182449">✨</tg-emoji>\n\n'
    '<tg-emoji emoji-id="6001564910318786723">✨</tg-emoji> 𝗖̲𝗵̲𝗮̲𝘁̲ &𝗙̲𝗿̲𝗶̲𝗲̲𝗻̲𝗱̲𝘀̲\n'
    '<tg-emoji emoji-id="6127558265573218459">✨</tg-emoji> 𝑹̲𝒐̲𝒎̲𝒂̲𝒏̲𝒄̲𝒆̲ &𝑭̲𝒍̲𝒊̲𝒓̲𝒕̲'
    + _PAD * 16 + _PUZZLE_R1 + '\n'
    '<tg-emoji emoji-id="5258508428212445001">✨</tg-emoji> 𝟮𝟬+ 𝗚̲𝗮̲𝗺̲𝗲̲𝘀̲ 𝗔̲𝘃̲𝗮̲𝗶̲𝗹̲𝗮̲𝗯̲𝗹̲𝗲'
    + _PAD * 10 + _PUZZLE_R2 + '\n\n'
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
    # try: video+premium card -> video+plain card -> text+premium -> text plain
    video = WELCOME_VIDEO
    attempts = []
    if video:
        attempts += [("video", _WELCOME), ("video", _plain(_WELCOME))]
    attempts += [("text", _WELCOME), ("text", _plain(_WELCOME))]
    for kind, body in attempts:
        try:
            if kind == "video":
                await msg.reply_video(
                    video, caption=body, parse_mode=HTML,
                    reply_markup=markup, supports_streaming=True)
            else:
                await msg.reply_text(body, parse_mode=HTML, reply_markup=markup)
            return
        except Exception:
            continue  # next fallback — the last plain-text attempt always delivers


def register(app):
    app.add_handler(CommandHandler("start", start))
