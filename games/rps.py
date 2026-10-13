import random

from telegram.ext import CallbackQueryHandler, CommandHandler

from database import users
from keyboards.ui import BLUE, GREEN, RED, btn, kb
from utils.helpers import safe_answer

E = {"r": "🪨 Rock", "p": "📄 Paper", "s": "✂️ Scissors"}
BEATS = {"r": "s", "p": "r", "s": "p"}


async def rps(update, ctx):
    await update.effective_message.reply_text("Choose your weapon:", reply_markup=kb([[
        btn(E["r"], "rps:r", RED), btn(E["p"], "rps:p", BLUE), btn(E["s"], "rps:s", GREEN)]]))


async def on_pick(update, ctx):
    q = update.callback_query
    me, bot = q.data.split(":")[1], random.choice("rps")
    if me == bot:
        res = "🤝 Draw!"
    elif BEATS[me] == bot:
        res = "🏆 You win! +$25"
        await users.ensure_user(q.from_user)
        await users.add_balance(q.from_user.id, 25, "rps_win")
    else:
        res = "😈 Bot wins!"
    await safe_answer(q)
    await q.edit_message_text(f"{q.from_user.first_name}: {E[me]}\nBot: {E[bot]}\n\n{res}",
                              reply_markup=kb([[btn("🔁 Play again", "rps:again", GREEN)]]) if False else None)


async def again(update, ctx):
    q = update.callback_query
    await safe_answer(q)
    await q.edit_message_text("Choose your weapon:", reply_markup=kb([[
        btn(E["r"], "rps:r", RED), btn(E["p"], "rps:p", BLUE), btn(E["s"], "rps:s", GREEN)]]))


def register(app):
    app.add_handler(CommandHandler("rps", rps))
    app.add_handler(CallbackQueryHandler(on_pick, pattern=r"^rps:[rps]$"))
