import random
import time

import config
from telegram.constants import ParseMode
from telegram.ext import CommandHandler

from database import mongo, users
from services import leaderboard_service
from utils import cooldowns
from utils.validators import mention, mention_doc, parse_amount, reply_target

HTML = ParseMode.HTML


async def _prep(update, ctx, need_amount=True):
    """Returns (me_doc, target_doc, amount) or None after replying with an error."""
    msg = update.effective_message
    me, tgt = update.effective_user, reply_target(update)
    amt = parse_amount(ctx.args) if need_amount else 0
    if not tgt or (need_amount and not amt):
        await msg.reply_text("Reply to a user's message and add an amount, e.g. /rob 200")
        return None
    if tgt.id == me.id:
        await msg.reply_text("❌ You can't target yourself.")
        return None
    md, td = await users.ensure_user(me), await users.ensure_user(tgt)
    if not md["alive"]:
        await msg.reply_text("💀 You're dead. Use /revive first.")
        return None
    if not td["alive"]:
        await msg.reply_text("💀 That user is already dead.")
        return None
    if td["shield_until"] > time.time():
        await msg.reply_text("🛡️ Target is protected by a shield.")
        return None
    return md, td, amt


async def rob(update, ctx):
    p = await _prep(update, ctx)
    if not p:
        return
    md, td, amt = p
    amt = min(amt, config.ROB_MAX)
    if td["balance"] < amt:
        return await update.effective_message.reply_text("❌ Target doesn't have that much.")
    left = await cooldowns.hit(md["_id"], "rob", config.ROB_COOLDOWN)
    if left:
        return await update.effective_message.reply_text(f"⏳ Rob cooldown: {cooldowns.fmt(left)}")
    me, tgt = update.effective_user, update.message.reply_to_message.from_user
    if random.random() < config.ROB_SUCCESS:
        if await users.take_balance(td["_id"], amt, "robbed"):
            await users.add_balance(md["_id"], amt, "rob")
            await users.add_xp(md["_id"], 5)
            await mongo.db.action_stats.insert_one({"type": "rob", "ok": True, "by": md["_id"], "ts": time.time()})
            return await update.effective_message.reply_text(
                f"🦹 {mention(me)} robbed <b>${amt:,}</b> from {mention(tgt)}!", parse_mode=HTML)
    fine = min(md["balance"], max(1, amt // 2))
    if await users.take_balance(md["_id"], fine, "rob_fine"):
        await users.add_balance(td["_id"], fine, "rob_fine")
    await mongo.db.action_stats.insert_one({"type": "rob", "ok": False, "by": md["_id"], "ts": time.time()})
    await update.effective_message.reply_text(
        f"🚨 {mention(me)} got caught and paid <b>${fine:,}</b> to {mention(tgt)}!", parse_mode=HTML)


async def kill(update, ctx):
    p = await _prep(update, ctx)
    if not p:
        return
    md, td, bounty = p
    if bounty < config.KILL_MIN_BOUNTY:
        return await update.effective_message.reply_text(f"❌ Minimum bounty is ${config.KILL_MIN_BOUNTY}.")
    left = await cooldowns.hit(md["_id"], "kill", config.KILL_COOLDOWN)
    if left:
        return await update.effective_message.reply_text(f"⏳ Kill cooldown: {cooldowns.fmt(left)}")
    if not await users.take_balance(md["_id"], bounty, "bounty"):
        return await update.effective_message.reply_text("❌ You can't afford that bounty.")
    me, tgt = update.effective_user, update.message.reply_to_message.from_user
    if random.random() < config.KILL_SUCCESS:
        await mongo.db.users.update_one({"_id": td["_id"]}, {"$set": {"alive": False}})
        loot = int(td["balance"] * config.KILL_LOOT_PCT)
        if loot and await users.take_balance(td["_id"], loot, "killed"):
            await users.add_balance(md["_id"], loot + bounty, "kill_reward")
        else:
            await users.add_balance(md["_id"], bounty, "kill_refund")
        await mongo.db.users.update_one({"_id": md["_id"]}, {"$inc": {"kills": 1, "xp": 25}})
        await update.effective_message.reply_text(
            f"🔪 {mention(me)} eliminated {mention(tgt)}! Loot: <b>${loot:,}</b>", parse_mode=HTML)
    else:
        await users.add_balance(td["_id"], bounty, "bounty_received")
        await update.effective_message.reply_text(
            f"😵 {mention(me)}'s attack failed. {mention(tgt)} kept the <b>${bounty:,}</b> bounty!", parse_mode=HTML)


async def protect(update, ctx):
    u = update.effective_user
    d = await users.ensure_user(u)
    if not await users.take_balance(u.id, config.SHIELD_COST, "shield"):
        return await update.effective_message.reply_text(f"❌ A shield costs ${config.SHIELD_COST:,}.")
    base = max(time.time(), d["shield_until"])
    await mongo.db.users.update_one({"_id": u.id}, {"$set": {"shield_until": base + config.SHIELD_HOURS * 3600}})
    await update.effective_message.reply_text(f"🛡️ Shield active for {config.SHIELD_HOURS}h more!")


async def shield(update, ctx):
    d = await users.ensure_user(update.effective_user)
    left = d["shield_until"] - time.time()
    txt = f"🛡️ Protected for {cooldowns.fmt(left)}" if left > 0 else "🔓 No active shield. Use /protect."
    await update.effective_message.reply_text(txt + ("\n💀 You are dead." if not d["alive"] else ""))


async def revive(update, ctx):
    me = update.effective_user
    await users.ensure_user(me)
    tgt = reply_target(update) or me
    td = await users.ensure_user(tgt)
    if td["alive"]:
        return await update.effective_message.reply_text("💚 That user is alive.")
    if not await users.take_balance(me.id, config.REVIVE_COST, "revive"):
        return await update.effective_message.reply_text(f"❌ Revival costs ${config.REVIVE_COST:,}.")
    await mongo.db.users.update_one({"_id": tgt.id}, {"$set": {"alive": True}})
    await update.effective_message.reply_text(f"✨ {mention(tgt)} is back from the dead!", parse_mode=HTML)


async def topkill(update, ctx):
    rows = await leaderboard_service.top("kills")
    if not rows:
        return await update.effective_message.reply_text("No kills yet.")
    text = "🔪 <b>Top assassins</b>\n\n" + "\n".join(
        f"{i+1}. {mention_doc(d)} — <b>{d['kills']}</b> kills" for i, d in enumerate(rows))
    await update.effective_message.reply_text(text, parse_mode=HTML)


def register(app):
    app.add_handler(CommandHandler("rob", rob))
    app.add_handler(CommandHandler("kill", kill))
    app.add_handler(CommandHandler("protect", protect))
    app.add_handler(CommandHandler(["shield", "protection"], shield))
    app.add_handler(CommandHandler("revive", revive))
    app.add_handler(CommandHandler("topkill", topkill))
