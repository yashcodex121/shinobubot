import html

from telegram.constants import ParseMode
from telegram.ext import CommandHandler

from database import mongo, users
from keyboards.main_menu import start_menu


async def start(update, ctx):
    u = update.effective_user
    await users.ensure_user(u)
    s = await mongo.db.settings.find_one({"_id": "welcome"})
    text = (s or {}).get("text") or (
        "💞 <b>Welcome to Nova!</b>\n\nEconomy, actions, romance and 10+ games — all in one bot.\n"
        "Tap <b>Help & Commands</b> to explore."
    )
    text = text.replace("{name}", html.escape(u.first_name))
    await update.effective_message.reply_text(
        text, parse_mode=ParseMode.HTML, reply_markup=start_menu(ctx.bot.username)
    )


def register(app):
    app.add_handler(CommandHandler("start", start))
