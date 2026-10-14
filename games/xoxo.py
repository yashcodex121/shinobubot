from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, CommandHandler

from database import mongo, users
from keyboards.ui import BLUE, GREEN, RED, btn, kb
from utils.helpers import safe_answer
from utils.validators import mention, reply_target

GAMES = {}  # (chat_id, message_id) -> state


def _win_lines(n):
    """Generate all winning lines for an n×n grid."""
    lines = []
    # Rows
    for r in range(n):
        lines.append(tuple(r * n + c for c in range(n)))
    # Cols
    for c in range(n):
        lines.append(tuple(r * n + c for r in range(n)))
    # Diagonal top-left to bottom-right
    lines.append(tuple(i * n + i for i in range(n)))
    # Diagonal top-right to bottom-left
    lines.append(tuple(i * n + (n - 1 - i) for i in range(n)))
    return lines


def winner(b, n):
    for line in _win_lines(n):
        vals = [b[i] for i in line]
        if vals[0] != " " and all(v == vals[0] for v in vals):
            return vals[0], line
    return None, ()


def board_kb(g, win_line=(), over=False, bot_username=""):
    n = g["n"]
    rows = []
    for r in range(n):
        row = []
        for c in range(n):
            i = r * n + c
            v = g["b"][i]
            if v == "X":
                row.append(btn("  ❌  ", "xo:x", GREEN if i in win_line else RED))
            elif v == "O":
                row.append(btn("  ⭕  ", "xo:x", GREEN if i in win_line else BLUE))
            else:
                row.append(btn("  ▫️  ", f"xo:{i}"))
        rows.append(row)
    if over:
        rows.append([btn("🔁 Rematch", "xo:re", GREEN)])
    if bot_username:
        rows.append([btn("➕ Add me to your group", url=f"https://t.me/{bot_username}?startgroup=true")])
    return kb(rows)


def header(g):
    n = g["n"]
    size_label = f"{n}×{n}" if n != 3 else ""
    return f"❌⭕ <b>XOXO</b> {size_label}\n❌ {mention(g['p']['X'])}  vs  ⭕ {mention(g['p']['O'])}\n"


async def xoxo(update, ctx):
    me, tgt = update.effective_user, reply_target(update)
    if not tgt or tgt.id == me.id:
        return await update.effective_message.reply_text(
            "Reply to a user's message with /xoxo to challenge them.\n"
            "Optional grid size: /xoxo 4 or /xoxo 5"
        )

    # Parse grid size from args
    n = 3
    if ctx.args:
        try:
            n = int(ctx.args[0])
            if n not in (3, 4, 5):
                return await update.effective_message.reply_text("❌ Grid size must be 3, 4 or 5.")
        except ValueError:
            pass

    g = {"b": [" "] * (n * n), "turn": "X", "p": {"X": me, "O": tgt}, "n": n}
    m = await update.effective_message.reply_text(
        header(g) + f"Turn: ❌ {mention(me)}", parse_mode=ParseMode.HTML,
        reply_markup=board_kb(g, bot_username=ctx.bot.username))
    GAMES[(m.chat_id, m.message_id)] = g


async def on_move(update, ctx):
    q = update.callback_query
    key = (q.message.chat_id, q.message.message_id)
    g = GAMES.get(key)
    arg = q.data.split(":")[1]

    if not g:
        return await safe_answer(q, "Game expired.", show_alert=True)
    if arg == "x":
        return await safe_answer(q)
    if arg == "re":
        if q.from_user.id not in (g["p"]["X"].id, g["p"]["O"].id):
            return await safe_answer(q, "Only players can rematch.", show_alert=True)
        n = g["n"]
        g["p"] = {"X": g["p"]["O"], "O": g["p"]["X"]}
        g["b"] = [" "] * (n * n)
        g["turn"] = "X"
        await safe_answer(q)
        return await q.edit_message_text(
            header(g) + f"Turn: ❌ {mention(g['p']['X'])}", parse_mode=ParseMode.HTML,
            reply_markup=board_kb(g, bot_username=q.bot.username))

    cur = g["p"][g["turn"]]
    if q.from_user.id != cur.id:
        return await safe_answer(q, "Not your turn!", show_alert=True)

    i = int(arg)
    if g["b"][i] != " ":
        return await safe_answer(q, "Cell taken.", show_alert=True)

    g["b"][i] = g["turn"]
    n = g["n"]
    w, line = winner(g["b"], n)

    if w:
        await users.ensure_user(cur)
        await users.add_balance(cur.id, 100, "xoxo_win")
        await users.add_xp(cur.id, 10)
        await mongo.db.game_stats.update_one(
            {"_id": f"xoxo:{cur.id}"}, {"$inc": {"wins": 1}}, upsert=True)
        return await q.edit_message_text(
            header(g) + f"🏆 {mention(cur)} wins! +$100",
            parse_mode=ParseMode.HTML,
            reply_markup=board_kb(g, line, over=True, bot_username=q.bot.username))

    if " " not in g["b"]:
        return await q.edit_message_text(
            header(g) + "🤝 It's a draw!",
            parse_mode=ParseMode.HTML,
            reply_markup=board_kb(g, (), over=True, bot_username=q.bot.username))

    g["turn"] = "O" if g["turn"] == "X" else "X"
    nxt = g["p"][g["turn"]]
    await safe_answer(q)
    await q.edit_message_text(
        header(g) + f"Turn: {'❌' if g['turn'] == 'X' else '⭕'} {mention(nxt)}",
        parse_mode=ParseMode.HTML,
        reply_markup=board_kb(g, bot_username=q.bot.username))


def register(app):
    app.add_handler(CommandHandler("xoxo", xoxo))
    app.add_handler(CallbackQueryHandler(on_move, pattern=r"^xo:"))
