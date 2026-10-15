import html
import random
import time

import config
from bson import ObjectId
from telegram.constants import ChatType, ParseMode
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler, filters

from database import mongo, users
from keyboards.ui import BLUE, GREEN, RED, btn, kb
from services.romance_service import active_marriage, partner_of
from utils.validators import mention, mention_doc, reply_target

HTML = ParseMode.HTML


PROPOSE_GIFS = [
    "CgACAgQAAxkBAAPUas814aNjcToWI4d4tf-vL4abTEsAAuQCAAIfAAEUU_o6VElEQe6LPQQ",
    "CgACAgQAAxkBAAPYas83Pvi8HzMnGAtBxMxe1EWFuYoAAncDAAIBonxTpH0uKXqroLs9BA",
    "CgACAgQAAxkBAAPaas83UYOTMstmWyPBiQAB3QQRUvQSAAIRCwACF1ycUFLrJgRzhLbuPQQ",
    "CgACAgQAAxkBAAPcas83ZpnOIfMSxcWLzmNTaXB5iSEAAjMFAAKR221QTvfqrOlmgQk9BA",
]


async def propose(update, ctx):
    me, tgt = update.effective_user, reply_target(update)
    msg = update.effective_message
    if not tgt or tgt.id == me.id:
        return await msg.reply_text("💍 Reply to someone else's message with /propose.")
    await users.ensure_user(me)
    await users.ensure_user(tgt)
    if await active_marriage(me.id) or await active_marriage(tgt.id):
        return await msg.reply_text("❌ One of you is already married.")
    doc = await mongo.db.marriages.insert_one(
        {"a": me.id, "b": tgt.id, "status": "pending", "expires": time.time() + config.PROPOSAL_TTL, "ts": time.time()})
    pid = str(doc.inserted_id)
    text = f"💍 {mention(me)} proposes to {mention(tgt)}!\nDo you accept?"
    markup = kb([[btn("💖 Accept", f"mr:y:{pid}", GREEN), btn("💔 Decline", f"mr:n:{pid}", RED)]])
    gif_url = random.choice(PROPOSE_GIFS)
    await msg.reply_animation(
        animation=gif_url,
        caption=text,
        parse_mode=HTML,
        reply_markup=markup,
    )


async def _edit_proposal_msg(q, text):
    """The proposal message is an animation + caption — edit its caption
    (edit_message_text fails on media messages: 'no text in the message to edit').
    The empty keyboard removes Accept/Decline once the proposal is decided."""
    await q.edit_message_caption(caption=text, parse_mode=HTML, reply_markup=kb([]))


async def on_proposal(update, ctx):
    q = update.callback_query
    _, ans, pid = q.data.split(":")
    p = await mongo.db.marriages.find_one({"_id": ObjectId(pid), "status": "pending"})
    if not p:
        return await q.answer("This proposal is no longer valid.", show_alert=True)
    if q.from_user.id != p["b"]:
        return await q.answer("This proposal isn't for you 😉", show_alert=True)
    if time.time() > p["expires"]:
        await mongo.db.marriages.update_one({"_id": p["_id"]}, {"$set": {"status": "expired"}})
        return await _edit_proposal_msg(q, "⌛ Proposal expired.")
    if ans == "n":
        await mongo.db.marriages.update_one({"_id": p["_id"]}, {"$set": {"status": "declined"}})
        return await _edit_proposal_msg(q, "💔 Proposal declined.")
    if await active_marriage(p["a"]) or await active_marriage(p["b"]):
        await mongo.db.marriages.update_one({"_id": p["_id"]}, {"$set": {"status": "cancelled"}})
        return await _edit_proposal_msg(q, "❌ One of you is already married.")
    await mongo.db.marriages.update_one({"_id": p["_id"]}, {"$set": {"status": "active", "since": time.time()}})
    await _edit_proposal_msg(q, "💞 <b>Congratulations!</b> You are now married! 🎉")


async def divorce(update, ctx):
    m = await active_marriage(update.effective_user.id)
    if not m:
        return await update.effective_message.reply_text("You're not married.")
    uid = update.effective_user.id
    await update.effective_message.reply_text(
        "💔 Are you sure you want to divorce?",
        reply_markup=kb([[btn("✅ Yes, divorce", f"dv:y:{uid}", RED), btn("↩️ Cancel", f"dv:n:{uid}", GREEN)]]))


async def on_divorce(update, ctx):
    q = update.callback_query
    _, ans, uid = q.data.split(":")
    if q.from_user.id != int(uid):
        return await q.answer("Not your decision.", show_alert=True)
    if ans == "n":
        return await q.edit_message_text("💞 Divorce cancelled.")
    m = await active_marriage(int(uid))
    if m:
        await mongo.db.marriages.update_one({"_id": m["_id"]}, {"$set": {"status": "divorced", "ended": time.time()}})
    await q.edit_message_text("💔 You are now divorced.")


async def marriage(update, ctx):
    t = reply_target(update) or update.effective_user
    m = await active_marriage(t.id)
    if not m:
        return await update.effective_message.reply_text(f"💔 {mention(t)} is single.", parse_mode=HTML)
    p = await users.get(partner_of(m, t.id))
    days = int((time.time() - m["since"]) // 86400)
    await update.effective_message.reply_text(
        f"💞 {mention(t)} is married to {mention_doc(p)}\n📅 Together for {days} day(s)", parse_mode=HTML)


async def track(update, ctx):
    u = update.effective_user
    if u and not u.is_bot:
        await mongo.db.group_members.update_one(
            {"chat": update.effective_chat.id, "uid": u.id}, {"$set": {"name": u.full_name}}, upsert=True)


async def couple(update, ctx):
    if update.effective_chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return await update.effective_message.reply_text("👥 This command works in groups only.")
    msg = update.effective_message
    me = update.effective_user
    tgt = reply_target(update)
    if tgt and tgt.id == me.id:
        tgt = None
    rows = await mongo.db.group_members.find({"chat": update.effective_chat.id}).to_list(500)
    if tgt:  # replied to someone -> ship them with a random active member
        others = [r for r in rows if r["uid"] != tgt.id]
        if not others:
            return await msg.reply_text("Need at least 2 active members first. Chat a bit!")
        a = {"uid": tgt.id, "name": tgt.full_name}
        b = random.choice(others)
    else:
        if len(rows) < 2:
            return await msg.reply_text("Need at least 2 active members first. Chat a bit!")
        a, b = random.sample(rows, 2)
    score = random.randint(1, 100)
    bar = "💖" * (score // 10) + "🖤" * (10 - score // 10)
    text = (
        f'💘 <b>Couple of the moment</b>\n\n'
        f'<a href="tg://user?id={a["uid"]}">{html.escape(a["name"])}</a> ❤️ '
        f'<a href="tg://user?id={b["uid"]}">{html.escape(b["name"])}</a>\n\n'
        f'Potential: {bar} <b>{score}%</b>'
    )
    markup = kb([[btn("🔧 Support", url="https://t.me/NovaSupport", style=BLUE)]])
    await msg.reply_animation(
        animation=random.choice(PROPOSE_GIFS),
        caption=text,
        parse_mode=HTML,
        reply_markup=markup,
    )


def register(app):
    app.add_handler(CommandHandler("propose", propose))
    app.add_handler(CommandHandler("divorce", divorce))
    app.add_handler(CommandHandler(["marriage", "married"], marriage))
    app.add_handler(CommandHandler(["couple", "shippering"], couple))
    app.add_handler(CallbackQueryHandler(on_proposal, pattern=r"^mr:"))
    app.add_handler(CallbackQueryHandler(on_divorce, pattern=r"^dv:"))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & ~filters.COMMAND, track, block=False), group=3)
