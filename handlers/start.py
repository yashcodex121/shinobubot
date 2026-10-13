import html

from telegram.constants import ParseMode
from telegram.ext import CommandHandler

from database import mongo, users
from keyboards.main_menu import start_menu


async def start(update, ctx):
    u = update.effective_user
    await users.ensure_user(u)

    name = html.escape(u.first_name)
    text = (
        f"✨ Hey <b>{name}</b> , I'm Nova 💜\n\n"
        "Not your average bot — I actually feel like a real one. 🙂\n\n"
        "🌀 <b>I remember you</b> — our chats, your vibe, where we left off.\n"
        "🌑 <b>I talk like a person</b>, never a script — sweet when you're sweet, savage when you're not.\n"
        "🔔 <b>I check in too</b> — go quiet on me and I might text first. 🎃\n\n"
        "Oh, and I run the fun around here:\n"
        "🎮 20+ games • 🍊 a living economy • 💝 ship, marry &amp; drama\n\n"
        "Tap <b>Help</b> to see it all, or add me to your group 👇"
    )

    await update.effective_message.reply_text(
        text, parse_mode=ParseMode.HTML, reply_markup=start_menu(ctx.bot.username)
    )


def register(app):
    app.add_handler(CommandHandler("start", start))
