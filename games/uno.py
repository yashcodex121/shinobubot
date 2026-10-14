"""UNO — lobby + full rules, played through inline mode like @unobot.

Flow: /new -> /join -> /launch (>=2 players) -> everyone plays by typing
@botusername <space> inline (playable cards, draw, ? state, colour picker
after a wild). 90s per turn (auto-skip + /skip). Creator: /close /open
/kick /exit /enable_translations /disable_translations. Multiple groups
at once — inline results are tagged with the group name.
"""
import html
import random
import time

from telegram import InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import ChosenInlineResultHandler, CommandHandler, InlineQueryHandler

import config
from database import mongo, users
from utils.validators import mention_doc

E = "❌"
COLORS = {"r": "🔴", "g": "🟢", "b": "🔵", "y": "🟡"}
CNAME = {"r": "Red", "g": "Green", "b": "Blue", "y": "Yellow"}
VALNAME = {"S": "Skip", "R": "Reverse", "D2": "+2", "W": "Wild", "W4": "+4"}
TURN_SECONDS = 90

GAMES = {}    # chat_id -> game dict (in-memory; restart clears running games)
NOTIFY = set()  # users who want a PM on /new


# ── cards / engine ───────────────────────────────────────────────────────────

def card(c, v):
    return (c, v)


def label(c, v):
    return f"{COLORS.get(c, '🌈')} {v if v in VALNAME else v}"


def _deck():
    d = []
    for col in "rgby":
        d.append((col, "0"))
        for v in "123456789":
            d += [(col, v), (col, v)]
        for v in ("S", "R", "D2"):
            d += [(col, v), (col, v)]
    d += [("w", "W")] * 4 + [("w", "W4")] * 4
    random.shuffle(d)
    return d


def _playable(g, c, v):
    if c == "w":
        return True
    tc, tv = g["top"]
    return c == g["color"] or v == tv


def _refill(g):
    """Reshuffle discard (keep top) into deck when it runs dry."""
    if not g["deck"] and len(g["discard"]) > 1:
        g["deck"] = g["discard"][:-1]
        random.shuffle(g["deck"])
        g["discard"] = g["discard"][-1:]


def _draw(g, n=1):
    out = []
    for _ in range(n):
        _refill(g)
        if g["deck"]:
            out.append(g["deck"].pop())
    return out


def _m(g, uid):
    return f'<a href="tg://user?id={uid}">{html.escape(g["names"].get(uid, "Player"))}</a>'


def _tx(g, en, hi):
    return en + (f"\n{hi}" if g.get("trans") else "")


def _next(g):
    return (g["turn"] + g["dir"]) % len(g["players"])


def _advance(g, times=1):
    for _ in range(times):
        g["turn"] = _next(g)
    g["seq"] += 1
    g["turn_ts"] = time.time()


def state_text(g):
    top = label(*g["top"])
    if g["top"][0] == "w":
        top += f" ({CNAME[g['color']]})" if g.get("color") else ""
    if g.get("color_wait"):
        top += " · 🎨 colour pending"
    cur = g["players"][g["turn"]] if g["players"] else None
    hands = " · ".join(f"{html.escape(g['names'].get(p, '?'))[:12]}({len(g['hands'][p])})"
                       for p in g["players"])
    arrow = "↻" if g["dir"] == 1 else "↺"
    lines = [f"🃏 <b>UNO</b> — {g['title']}",
             f"Top: <b>{top}</b>  |  Direction: {arrow}",
             f"Turn: {_m(g, cur)}  ⏱{TURN_SECONDS}s" if cur else "Turn: —",
             f"Hands: {hands}",
             f"<i>Type @{g['bot']} <code> </code> to play your cards inline.</i>"]
    return "\n".join(lines)


# ── lobby helpers ────────────────────────────────────────────────────────────

async def _send(ctx, chat_id, text, reply_markup=None):
    from telegram.constants import ParseMode
    try:
        return await ctx.bot.send_message(chat_id, text, parse_mode=ParseMode.HTML,
                                          reply_markup=reply_markup)
    except Exception:
        return None


def _lobby(g):
    names = ", ".join(html.escape(g["names"][p]) for p in g["players"])
    lock = "🔒 closed" if not g["open"] else "🟢 open"
    return (f"🃏 <b>UNO lobby</b> — {g['title']}\n"
            f"Players: {names} ({len(g['players'])})\n"
            f"Lobby: {lock}  |  Creator: {_m(g, g['creator'])}\n\n"
            f"/join to join · creator: /launch · /close /open /kick /exit")


# ── commands ─────────────────────────────────────────────────────────────────

async def new_game(update, ctx):
    chat = update.effective_chat
    u = update.effective_user
    if chat.type == "private":
        return await update.effective_message.reply_text("Run /new in a group.")
    if chat.id in GAMES:
        return await update.effective_message.reply_text("A game already exists here — /join it or creator /exit it.")
    try:
        title = (await ctx.bot.get_chat(chat.id)).title or chat.title or "Group"
    except Exception:
        title = chat.title or "Group"
    g = {"players": [u.id], "names": {u.id: u.full_name}, "hands": {}, "deck": _deck(),
         "discard": [], "top": None, "color": None, "dir": 1, "turn": 0, "seq": 0,
         "turn_ts": time.time(), "creator": u.id, "open": True, "started": False,
         "color_wait": None, "trans": False, "title": title, "bot": ctx.bot.username,
         "job": None}
    GAMES[chat.id] = g
    await _send(ctx, chat.id, _lobby(g) + "\n\nAnyone: /join — then creator: /launch")
    # notify_me subscribers
    for uid in list(NOTIFY):
        try:
            await ctx.bot.send_message(uid, f"🎮 New UNO game in <b>{html.escape(title)}</b>! Join with /join there.",
                                       parse_mode="HTML")
        except Exception:
            NOTIFY.discard(uid)


async def join_game(update, ctx):
    chat, u = update.effective_chat, update.effective_user
    g = GAMES.get(chat.id)
    if not g:
        return await update.effective_message.reply_text("No game here — /new to create one.")
    if g["started"]:
        return await update.effective_message.reply_text("Game already started — wait for the next one.")
    if not g["open"]:
        return await update.effective_message.reply_text("🔒 Lobby is closed.")
    if u.id in g["players"]:
        return await update.effective_message.reply_text("You're already in.")
    g["players"].append(u.id)
    g["names"][u.id] = u.full_name
    await _send(ctx, chat.id, _tx(g, f"👋 {html.escape(u.full_name)} joined ({len(g['players'])} players).",
                                  f"👋 {html.escape(u.full_name)} शामिल हुए ({len(g['players'])} खिलाड़ी)."))


async def start_game(update, ctx):
    chat, u = update.effective_chat, update.effective_user
    g = GAMES.get(chat.id)
    if not g or g["started"]:
        return
    if u.id != g["creator"]:
        return await update.effective_message.reply_text("Only the game creator can /launch.")
    if len(g["players"]) < 2:
        return await update.effective_message.reply_text("Need at least 2 players — /join first.")
    # deal 7 each
    for p in g["players"]:
        g["hands"][p] = _draw(g, 7)
    # first card: no +4 / +2 as opener
    while True:
        c = _draw(g, 1)
        if not c:
            return await _send(ctx, chat.id, "❌ Deck ran out — /exit and retry.")
        c = c[0]
        if c[1] not in ("W4", "D2"):
            break
        g["deck"].append(c)
    g["top"] = c
    g["color"] = c[0] if c[0] != "w" else random.choice("rgby")
    g["discard"] = [c]
    g["started"] = True
    _advance(g, 0)
    await _send(ctx, chat.id, _tx(g, f"🎮 Game on! First turn: {_m(g, g['players'][0])}",
                                  f"🎮 खेल शुरू! पहली बारी: {_m(g, g['players'][0])}"))
    await _send(ctx, chat.id, state_text(g))
    await _arm_timer(ctx, chat.id, g)


async def leave_game(update, ctx):
    chat, u = update.effective_chat, update.effective_user
    g = GAMES.get(chat.id)
    if not g or u.id not in g["players"]:
        return await update.effective_message.reply_text("You're not in a game here.")
    was_turn = g["started"] and g["players"][g["turn"]] == u.id
    g["players"].remove(u.id)
    g["hands"].pop(u.id, None)
    if len(g["players"]) < 2:
        GAMES.pop(chat.id, None)
        if g["players"]:
            return await _send(ctx, chat.id, f"🏳️ Game cancelled — {html.escape(g['names'][g['players'][0]])} wins by default.")
        return await _send(ctx, chat.id, "🏳️ Game cancelled.")
    if was_turn:
        _advance(g)
        await _arm_timer(ctx, chat.id, g)
    await _send(ctx, chat.id, f"👋 {html.escape(g['names'].get(u.id, 'Player'))} left.")


async def notify_me(update, ctx):
    u = update.effective_user
    args = [a.lower() for a in (ctx.args or [])]
    if args and args[0] in ("off", "0"):
        NOTIFY.discard(u.id)
        return await update.effective_message.reply_text("🔕 No more UNO game alerts.")
    NOTIFY.add(u.id)
    await update.effective_message.reply_text("🔔 Done — I'll PM you when a new UNO game is created (try /new here).")


async def settings(update, ctx):
    chat = update.effective_chat
    g = GAMES.get(chat.id)
    base = (f"⚙️ <b>UNO settings</b>\n"
            f"Language: English\nTurn time: {TURN_SECONDS}s\n"
            f"Translations: /enable_translations · /disable_translations")
    if g:
        base += (f"\nThis game — lobby: {'open' if g['open'] else 'closed'}, "
                 f"translations: {'on' if g['trans'] else 'off'}")
    await update.effective_message.reply_text(base, parse_mode="HTML")


async def _creator_cmd(update, ctx, fn_name):
    chat, u = update.effective_chat, update.effective_user
    g = GAMES.get(chat.id)
    if not g:
        await update.effective_message.reply_text("No game here.")
        return None
    if u.id != g["creator"]:
        await update.effective_message.reply_text("Only the game creator can do that.")
        return None
    return g


async def close_lobby(update, ctx):
    g = await _creator_cmd(update, ctx, "close")
    if g:
        g["open"] = False
        await _send(ctx, update.effective_chat.id, "🔒 Lobby closed.")


async def open_lobby(update, ctx):
    g = await _creator_cmd(update, ctx, "open")
    if g:
        g["open"] = True
        await _send(ctx, update.effective_chat.id, "🔓 Lobby open.")


async def kill_game(update, ctx):
    g = await _creator_cmd(update, ctx, "exit")
    if g:
        if g.get("job"):
            try:
                g["job"].schedule_removal()
            except Exception:
                pass
        GAMES.pop(update.effective_chat.id, None)
        await _send(ctx, update.effective_chat.id, "☠️ Game terminated by the creator.")


async def kick_player(update, ctx):
    chat, u = update.effective_chat, update.effective_user
    g = GAMES.get(chat.id)
    if not g:
        return
    if u.id != g["creator"]:
        return await update.effective_message.reply_text("Only the creator can /kick.")
    r = update.effective_message.reply_to_message
    if not r or not r.from_user:
        return await update.effective_message.reply_text("Reply to a player's message with /kick.")
    tid = r.from_user.id
    if tid == g["creator"]:
        return await update.effective_message.reply_text("You can't kick yourself — /exit instead.")
    if tid not in g["players"]:
        return await update.effective_message.reply_text("That user isn't in the game.")
    g["players"].remove(tid)
    g["hands"].pop(tid, None)
    if len(g["players"]) < 2:
        GAMES.pop(chat.id, None)
        return await _send(ctx, chat.id, f"👢 {html.escape(g['names'].get(tid, 'P'))} kicked — game cancelled.")
    await _send(ctx, chat.id, f"👢 {html.escape(g['names'].get(tid, 'P'))} kicked.")


async def translations(update, ctx, on):
    g = await _creator_cmd(update, ctx, "trans")
    if g:
        g["trans"] = on
        await _send(ctx, update.effective_chat.id,
                    "🌐 Translations enabled (English + Hindi)." if on else "🇺🇸 Translations disabled — English only.")


async def enable_trans(update, ctx):
    await translations(update, ctx, True)


async def disable_trans(update, ctx):
    await translations(update, ctx, False)


async def my_hand(update, ctx):
    u = update.effective_user
    g = next((x for x in GAMES.values() if u.id in x.get("hands", {})), None)
    if not g:
        return await update.effective_message.reply_text("You're not in a started game.")
    cards = "  ".join(f"{i+1}.{label(*c)}" for i, c in enumerate(g["hands"][u.id]))
    await update.effective_message.reply_text(f"🂠 Your cards ({len(g['hands'][u.id])}):\n{cards}")


async def skip_cmd(update, ctx):
    chat, u = update.effective_chat, update.effective_user
    g = GAMES.get(chat.id)
    if not g or not g["started"]:
        return
    cur = g["players"][g["turn"]]
    if cur == u.id:
        return await update.effective_message.reply_text("It's your turn — play or draw.")
    if u.id != g["creator"] and time.time() - g["turn_ts"] < TURN_SECONDS:
        return await update.effective_message.reply_text(f"Only after {TURN_SECONDS}s of their turn (or by the creator).")
    await _timeout_turn(ctx, chat.id, g["seq"], manual=True)


# ── turn timer ───────────────────────────────────────────────────────────────

async def _arm_timer(ctx, chat_id, g):
    if g.get("job"):
        try:
            g["job"].schedule_removal()
        except Exception:
            pass
    g["job"] = ctx.job_queue.run_once(_timeout_job, TURN_SECONDS,
                                      data={"chat": chat_id, "seq": g["seq"]})


async def _timeout_job(ctx):
    d = ctx.job.data
    g = GAMES.get(d["chat"])
    if g and g.get("started"):
        await _timeout_turn(ctx, d["chat"], d["seq"])


async def _timeout_turn(ctx, chat_id, seq, manual=False):
    g = GAMES.get(chat_id)
    if not g or not g.get("started") or g["seq"] != seq:
        return
    cur = g["players"][g["turn"]]
    _advance(g)
    await _send(ctx, chat_id, _tx(g, f"⏰ {_m(g, cur)} timed out — skipped.",
                                  f"⏰ {_m(g, cur)} का समय समाप्त — छोड़ा गया."))
    await _send(ctx, chat_id, state_text(g))
    await _arm_timer(ctx, chat_id, g)


# ── play actions (shared by inline chosen results) ───────────────────────────

async def _do_play(ctx, chat_id, uid, c, v, inline_message_id=None):
    g = GAMES.get(chat_id)
    note = None
    if not g or not g.get("started") or g.get("color_wait"):
        note = "No active game here (anymore)."
    elif g["players"][g["turn"]] != uid:
        note = "Not your turn!"
    elif (c, v) not in g["hands"].get(uid, []):
        note = "You don't have that card."
    elif not _playable(g, c, v):
        note = "That card can't be played on this top card."
    if note:
        if inline_message_id:
            try:
                await ctx.bot.edit_message_text(inline_message_id=inline_message_id,
                                                text=f"🎴 {label(c, v)} — ✗ {note}")
            except Exception:
                pass
        else:
            await _send(ctx, chat_id, f"✗ {note}")
        return
    g["hands"][uid].remove((c, v))
    g["top"] = (c, v)
    g["discard"].append((c, v))
    if c == "w":
        g["color_wait"] = uid  # colour stays until the player picks inline
    else:
        g["color"] = c
    await _after_play(ctx, chat_id, g, uid, c, v, inline_message_id)


async def _after_play(ctx, chat_id, g, uid, c, v, inline_message_id=None):
    if inline_message_id:
        try:
            await ctx.bot.edit_message_text(inline_message_id=inline_message_id,
                                            text=f"🎴 {label(c, v)} ✓")
        except Exception:
            pass
    if not g["hands"][uid]:
        GAMES.pop(chat_id, None)
        prize = random.randint(config.GAME_REWARD_MIN, config.GAME_REWARD_MAX)
        try:
            await users.ensure_user(_Pseudo(uid, g["names"].get(uid, "Player")))
            await users.add_balance(uid, prize, "uno_win")
            await users.add_xp(uid, 10)
            await mongo.db.game_stats.update_one({"_id": f"uno:{uid}"}, {"$inc": {"wins": 1}}, upsert=True)
        except Exception:
            pass
        return await _send(ctx, chat_id, _tx(
            g, f"🏆 {_m(g, uid)} played the last card and WON! +${prize:,}",
            f"🏆 {_m(g, uid)} ने आख़िरी कार्ड खेला और जीत गए! +${prize:,}"))
    if g.get("color_wait"):
        return await _send(ctx, chat_id, f"🎨 {_m(g, uid)} played a wild — pick the colour inline (@{g['bot']} <code> </code>).")
    n = len(g["players"])
    extra = 0
    victim = _next(g)
    if v == "R":
        g["dir"] *= -1
        if n == 2:
            extra = 1
    elif v == "S":
        extra = 1
    elif v == "D2":
        g["hands"][g["players"][victim]] += _draw(g, 2)
        extra = 1
    elif v == "W4":
        g["hands"][g["players"][victim]] += _draw(g, 4)
        extra = 1
    _advance(g, 1 + extra)
    msg = f"🎴 {_m(g, uid)} played {label(c, v)}"
    if v in ("D2", "W4"):
        msg += f" → {_m(g, g['players'][victim])} draws {v[1:]}"
    if len(g["hands"][uid]) == 1:
        msg += "  ·  📣 UNO!"
    await _send(ctx, chat_id, msg)
    await _send(ctx, chat_id, state_text(g))
    await _arm_timer(ctx, chat_id, g)


async def _do_color(ctx, chat_id, uid, color):
    g = GAMES.get(chat_id)
    if not g or g.get("color_wait") != uid or color not in "rgby":
        return
    g["color"] = color
    g["color_wait"] = None
    await _send(ctx, chat_id, f"🎨 Colour set to {COLORS[color]} <b>{CNAME[color]}</b> by {_m(g, uid)}.")
    _advance(g)
    await _send(ctx, chat_id, state_text(g))
    await _arm_timer(ctx, chat_id, g)


async def _do_draw(ctx, chat_id, uid, inline_message_id=None):
    g = GAMES.get(chat_id)
    if not g or not g.get("started") or g.get("color_wait"):
        return
    if g["players"][g["turn"]] != uid:
        return await _send(ctx, chat_id, "Not your turn!")
    got = _draw(g, 1)
    if not got:
        return await _send(ctx, chat_id, "Deck is empty.")
    g["hands"][uid] += got
    await _send(ctx, chat_id, f"➕ {_m(g, uid)} drew a card ({len(g['hands'][uid])} in hand).")
    _advance(g)
    await _send(ctx, chat_id, state_text(g))
    await _arm_timer(ctx, chat_id, g)


class _Pseudo:
    def __init__(self, uid, name):
        self.id = uid
        self.full_name = name
        self.username = None


# ── inline mode ──────────────────────────────────────────────────────────────

def _art(rid, title, desc, text):
    return InlineQueryResultArticle(
        id=rid, title=title, description=desc,
        input_message_content=InputTextMessageContent(text, parse_mode="HTML"))


async def on_inline(update, ctx):
    q = update.inline_query
    u = q.from_user
    mine = [(cid, x) for cid, x in GAMES.items() if x.get("started") and u.id in x.get("hands", {})]
    results = []
    for chat_id, g in mine:
        tag = f"[{g['title'][:16]}]"
        if g.get("color_wait") == u.id:
            for col in "rgby":
                results.append(_art(f"c:{chat_id}:{col}", f"{tag} {CNAME[col]}",
                                    "Set wild colour", f"🎨 {COLORS[col]} {CNAME[col]}"))
        else:
            your_turn = g["players"][g["turn"]] == u.id
            for c, v in g["hands"][u.id]:
                ok = your_turn and _playable(g, c, v)
                results.append(_art(
                    f"p:{chat_id}:{c}{v}", f"{tag} {label(c, v)}",
                    "✅ Play this card" if ok else ("⌛ Not your turn" if not your_turn else "❌ Can't play now"),
                    f"🎴 {label(c, v)}"))
            if your_turn:
                results.append(_art(f"d:{chat_id}", f"{tag} ➕ Draw a card",
                                    "Draw 1 from the deck", "➕ Drawing…"))
        results.append(_art(f"s:{chat_id}", f"{tag} ❓ Game state",
                            "Top card, turn, hands",
                            state_text(g)))
    if not results:
        results = [_art("x", "No active UNO game", "Start with /new, join with /join",
                        "🃏 No active UNO game here — /new or /join!")]
    try:
        await q.answer(results[:50], cache_time=0, is_personal=True)
    except Exception:
        pass


async def on_chosen(update, ctx):
    r = update.chosen_inline_result
    parts = r.result_id.split(":")
    kind = parts[0]
    try:
        chat_id = int(parts[1])
    except (IndexError, ValueError):
        return
    uid = r.from_user.id
    if kind == "p" and len(parts) == 3:
        enc = parts[2]
        c, v = enc[0], enc[1:]
        await _do_play(ctx, chat_id, uid, c, v, r.inline_message_id)
    elif kind == "c" and len(parts) == 3:
        await _do_color(ctx, chat_id, uid, parts[2])
    elif kind == "d":
        await _do_draw(ctx, chat_id, uid, r.inline_message_id)
    # "s" (state) and "x" need no action — the inline message already shows it


def register(app):
    app.add_handler(CommandHandler("new", new_game, block=False))
    app.add_handler(CommandHandler("join", join_game, block=False))
    app.add_handler(CommandHandler("launch", start_game, block=False))
    app.add_handler(CommandHandler("leave", leave_game, block=False))
    app.add_handler(CommandHandler("notify_me", notify_me, block=False))
    app.add_handler(CommandHandler("settings", settings, block=False))
    app.add_handler(CommandHandler("close", close_lobby, block=False))
    app.add_handler(CommandHandler("open", open_lobby, block=False))
    app.add_handler(CommandHandler("exit", kill_game, block=False))
    app.add_handler(CommandHandler("kick", kick_player, block=False))
    app.add_handler(CommandHandler("enable_translations", enable_trans, block=False))
    app.add_handler(CommandHandler("disable_translations", disable_trans, block=False))
    app.add_handler(CommandHandler("hand", my_hand, block=False))
    app.add_handler(CommandHandler("skip", skip_cmd, block=False))
    app.add_handler(InlineQueryHandler(on_inline, block=False))
    app.add_handler(ChosenInlineResultHandler(on_chosen, block=False))
