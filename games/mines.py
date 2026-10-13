import random

import config
from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, CommandHandler

from database import users
from keyboards.ui import GREEN, RED, btn, kb
from utils.helpers import safe_answer
from utils.validators import parse_amount

SESSIONS = {}  # (chat, msg) -> state. Mines are placed server-side; clients only send tile ids.
N = 25


def multiplier(safe):
    m = 1.0
    for i in range(safe):
        m *= (N - i) / (N - config.MINES_COUNT - i)
    return round(m * (config.MINES_EDGE ** (1 if safe else 0)), 2)


def build(g, reveal=False):
    rows = []
    for r in range(5):
        row = []
        for c in range(5):
            i = r * 5 + c
            if i in g["open"]:
                row.append(btn("💎", "mn:x", GREEN))
            elif reveal and i in g["mines"]:
                row.append(btn("💣", "mn:x", RED))
            elif reveal:
                row.append(btn("▫️", "mn:x"))
            else:
                row.append(btn("⬜", f"mn:{i}"))
        rows.append(row)
    if not reveal and g["open"]:
        rows.append([btn(f"💰 Cash out ${int(g['bet'] * multiplier(len(g['open']))):,}", "mn:cash", GREEN)])
    return kb(rows)


async def mines(update, ctx):
    u = update.effective_user
    bet = parse_amount(ctx.args)
    if not bet or bet < config.MINES_MIN_BET:
        return await update.effective_message.reply_text(f"Usage: /mines &lt;bet&gt; (min ${config.MINES_MIN_BET})")
    await users.ensure_user(u)
    if not await users.take_balance(u.id, bet, "mines_bet"):
        return await update.effective_message.reply_text("❌ Not enough balance.")
    g = {"uid": u.id, "bet": bet, "open": set(), "mines": set(random.sample(range(N), config.MINES_COUNT))}
    m = await update.effective_message.reply_text(
        f"💣 <b>Mines</b> — wager <b>${bet:,}</b>, {config.MINES_COUNT} mines hidden.\nPick a tile!",
        parse_mode=ParseMode.HTML, reply_markup=build(g))
    SESSIONS[(m.chat_id, m.message_id)] = g


async def on_tile(update, ctx):
    q = update.callback_query
    key = (q.message.chat_id, q.message.message_id)
    g = SESSIONS.get(key)
    if not g:
        return await safe_answer(q, "Game expired.", show_alert=True)
    if q.from_user.id != g["uid"]:
        return await safe_answer(q, "This isn't your game!", show_alert=True)
    arg = q.data.split(":")[1]
    if arg == "x":
        return await safe_answer(q)
    if arg == "cash":
        if not g["open"]:
            return await safe_answer(q, "Reveal a tile first.", show_alert=True)
        SESSIONS.pop(key)
        win = int(g["bet"] * multiplier(len(g["open"])))
        await users.add_balance(g["uid"], win, "mines_win")
        await users.add_xp(g["uid"], 10)
        await safe_answer(q)
        return await q.edit_message_text(f"💰 Cashed out <b>${win:,}</b> ({multiplier(len(g['open']))}x)!",
                                         parse_mode=ParseMode.HTML, reply_markup=build(g, True))
    i = int(arg)
    if i in g["open"]:
        return await safe_answer(q)
    if i in g["mines"]:
        SESSIONS.pop(key)
        await safe_answer(q)
        return await q.edit_message_text(f"💥 BOOM! You lost <b>${g['bet']:,}</b>.",
                                         parse_mode=ParseMode.HTML, reply_markup=build(g, True))
    g["open"].add(i)
    await safe_answer(q)
    if len(g["open"]) == N - config.MINES_COUNT:
        SESSIONS.pop(key)
        win = int(g["bet"] * multiplier(len(g["open"])))
        await users.add_balance(g["uid"], win, "mines_win")
        return await q.edit_message_text(f"🏆 Perfect clear! Won <b>${win:,}</b>!",
                                         parse_mode=ParseMode.HTML, reply_markup=build(g, True))
    await q.edit_message_text(
        f"💎 Safe! Multiplier <b>{multiplier(len(g['open']))}x</b> — keep going or cash out.",
        parse_mode=ParseMode.HTML, reply_markup=build(g))


def register(app):
    app.add_handler(CommandHandler("mines", mines))
    app.add_handler(CallbackQueryHandler(on_tile, pattern=r"^mn:"))
