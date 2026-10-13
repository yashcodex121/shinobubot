from telegram.ext import CallbackQueryHandler, CommandHandler

from games import _wordround as wr
from keyboards.ui import GREEN, btn, kb


async def jumble(update, ctx):
    hard = bool(ctx.args) and ctx.args[0].lower() == "hard"
    await wr.start_round(update, ctx, "jumble", hard, kb([[btn("💡 Hint", "jb:hint", GREEN)]]))


async def hint(update, ctx):
    r = wr.ROUNDS.get(update.effective_chat.id)
    if not r:
        return await update.callback_query.answer("No active round.", show_alert=True)
    w = r["word"]
    await update.callback_query.answer(f"Starts with '{w[0].upper()}', {len(w)} letters", show_alert=True)


def register(app):
    app.add_handler(CommandHandler("jumble", jumble))
    app.add_handler(CallbackQueryHandler(hint, pattern=r"^jb:hint"))
