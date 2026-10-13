from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, CommandHandler

from database import mongo, users
from keyboards.ui import BLUE, GREEN, RED, btn, kb
from utils.validators import mention, reply_target

GAMES = {}  # (chat_id, message_id) -> state
LINES = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]


def winner(b):
    for l in LINES:
        if b[l[0]] != " " and b[l[0]] == b[l[1]] == b[l[2]]:
            return b[l[0]], l
    return None, ()


def board_kb(g, win_line=(), over=False):
    rows = []
    for r in range(3):
        row = []
        for c in range(3):
            i = r * 3 + c
            v = g["b"][i]
            if v == "X":
                row.append(btn("❌", "xo:x", GREEN if i in win_line else RED))
            elif v == "O":
                row.append(btn("⭕", "xo:x", GREEN if i in win_line else BLUE))
            else:
                row.append(btn("▫️", f"xo:{i}"))
        rows.append(row)
    if over:
        rows.append([btn("🔁 Rematch", "xo:re", GREEN)])
    return kb(rows)


def header(g):
    return (f"❌⭕ <b>XOXO</b>\n❌ {mention(g['p']['X'])}  vs  ⭕ {mention(g['p']['O'])}\n")


async def xoxo(update, ctx):
    me, tgt = update.effective_user, reply_target(update)
    if not tgt or tgt.id == me.id:
        return await update.effective_message.reply_text("Reply to a user's message with /xoxo to challenge them.")
    g = {"b": [" "] * 9, "turn": "X", "p": {"X": me, "O": tgt}}
    m = await update.effective_message.reply_text(
        header(g) + f"Turn: ❌ {mention(me)}", parse_mode=ParseMode.HTML, reply_markup=board_kb(g))
    GAMES[(m.chat_id, m.message_id)] = g


async def on_move(update, ctx):
    q = update.callback_query
    key = (q.message.chat_id, q.message.message_id)
    g = GAMES.get(key)
    arg = q.data.split(":")[1]
    if not g:
        return await q.answer("Game expired.", show_alert=True)
    if arg == "x":
        return await q.answer()
    if arg == "re":
        if q.from_user.id not in (g["p"]["X"].id, g["p"]["O"].id):
            return await q.answer("Only players can rematch.", show_alert=True)
        g["p"] = {"X": g["p"]["O"], "O": g["p"]["X"]}
        g["b"], g["turn"] = [" "] * 9, "X"
        await q.answer()
        return await q.edit_message_text(
            header(g) + f"Turn: ❌ {mention(g['p']['X'])}", parse_mode=ParseMode.HTML, reply_markup=board_kb(g))
    cur = g["p"][g["turn"]]
    if q.from_user.id != cur.id:
        return await q.answer("Not your turn!", show_alert=True)
    i = int(arg)
    if g["b"][i] != " ":
        return await q.answer("Cell taken.", show_alert=True)
    g["b"][i] = g["turn"]
    w, line = winner(g["b"])
    if w:
        await users.ensure_user(cur)
        await users.add_balance(cur.id, 100, "xoxo_win")
        await users.add_xp(cur.id, 10)
        await mongo.db.game_stats.update_one({"_id": f"xoxo:{cur.id}"}, {"$inc": {"wins": 1}}, upsert=True)
        return await q.edit_message_text(header(g) + f"🏆 {mention(cur)} wins! +$100", parse_mode=ParseMode.HTML,
                                         reply_markup=board_kb(g, line, True))
    if " " not in g["b"]:
        return await q.edit_message_text(header(g) + "🤝 It's a draw!", parse_mode=ParseMode.HTML,
                                         reply_markup=board_kb(g, (), True))
    g["turn"] = "O" if g["turn"] == "X" else "X"
    nxt = g["p"][g["turn"]]
    await q.answer()
    await q.edit_message_text(header(g) + f"Turn: {'❌' if g['turn']=='X' else '⭕'} {mention(nxt)}",
                              parse_mode=ParseMode.HTML, reply_markup=board_kb(g))


def register(app):
    app.add_handler(CommandHandler("xoxo", xoxo))
    app.add_handler(CallbackQueryHandler(on_move, pattern=r"^xo:"))
