from telegram.ext import CommandHandler

from games import _wordround as wr


async def scramble_cmd(update, ctx):
    hard = bool(ctx.args) and ctx.args[0].lower() == "hard"
    await wr.start_round(update, ctx, "scramble", hard)


def register(app):
    app.add_handler(CommandHandler(["scramble", "wordscramble"], scramble_cmd))
