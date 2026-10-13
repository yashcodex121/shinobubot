from telegram import BotCommand
from telegram.ext import Application

import config
from database import mongo
from handlers import actions, admin, economy, games, help as help_h, romance, start
from utils.logger import log


async def post_init(app):
    await mongo.init()
    await app.bot.set_my_commands([
        BotCommand("start", "Start Nova"), BotCommand("help", "Help & Commands"),
        BotCommand("games", "Game list"), BotCommand("bal", "Your balance"),
        BotCommand("daily", "Daily reward"), BotCommand("rob", "Rob a user"),
        BotCommand("propose", "Propose marriage"), BotCommand("mines", "Play Mines"),
    ])
    log.info("Nova is online as @%s", app.bot.username)


async def on_error(update, ctx):
    log.exception("Unhandled error", exc_info=ctx.error)


def main():
    if not config.BOT_TOKEN:
        raise SystemExit("Set BOT_TOKEN in .env")
    app = Application.builder().token(config.BOT_TOKEN).post_init(post_init).build()
    for m in (admin, start, help_h, economy, actions, romance, games):
        m.register(app)
    app.add_error_handler(on_error)
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
