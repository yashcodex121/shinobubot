import html

import config
from telegram.constants import ParseMode
from telegram.ext import CommandHandler

from database import users
from services import economy_service, leaderboard_service
from utils import cooldowns
from utils.validators import mention, mention_doc, parse_amount, reply_target

HTML = ParseMode.HTML


async def balance(update, ctx):
    t = reply_target(update) or update.effective_user
    d = await users.ensure_user(t)
    await update.effective_message.reply_text(
        f"💳 <b>{html.escape(t.full_name)}</b>\n💰 Cash: <b>${d['balance']:,}</b>\n✨ XP: <b>{d['xp']:,}</b>"
        f"\n{'💚 Alive' if d['alive'] else '💀 Dead'}", parse_mode=HTML)


async def daily(update, ctx):
    u = update.effective_user
    await users.ensure_user(u)
    left = await cooldowns.hit(u.id, "daily", config.DAILY_COOLDOWN)
    if left:
        return await update.effective_message.reply_text(f"⏳ Already claimed. Come back in {cooldowns.fmt(left)}.")
    await users.add_balance(u.id, config.DAILY_REWARD, "daily")
    await users.add_xp(u.id, 10)
    await update.effective_message.reply_text(f"🎁 You claimed <b>${config.DAILY_REWARD:,}</b> and +10 XP!", parse_mode=HTML)


async def give(update, ctx):
    me, tgt = update.effective_user, reply_target(update)
    amt = parse_amount(ctx.args)
    if not tgt or not amt:
        return await update.effective_message.reply_text("Usage: reply to a user with /give <amount>")
    if tgt.id == me.id:
        return await update.effective_message.reply_text("❌ You can't pay yourself.")
    await users.ensure_user(me)
    await users.ensure_user(tgt)
    if await cooldowns.hit(me.id, "give", config.GIVE_COOLDOWN):
        return await update.effective_message.reply_text("⏳ Slow down.")
    if not await users.transfer(me.id, tgt.id, amt):
        return await update.effective_message.reply_text("❌ Not enough balance.")
    await update.effective_message.reply_text(f"✅ {mention(me)} sent <b>${amt:,}</b> to {mention(tgt)}.", parse_mode=HTML)


async def toprich(update, ctx):
    rows = await economy_service.top_rich()
    medals = ["🥇", "🥈", "🥉"] + ["🔹"] * 7
    text = "🏆 <b>Richest players</b>\n\n" + "\n".join(
        f"{medals[i]} {mention_doc(d)} — <b>${d['balance']:,}</b>" for i, d in enumerate(rows))
    await update.effective_message.reply_text(text, parse_mode=HTML)


async def rank(update, ctx):
    d = await users.ensure_user(update.effective_user)
    r = await economy_service.xp_rank(d["_id"], d["xp"])
    await update.effective_message.reply_text(f"🌍 Your global rank: <b>#{r}</b> ({d['xp']:,} XP)", parse_mode=HTML)


def register(app):
    app.add_handler(CommandHandler(["balance", "bal"], balance))
    app.add_handler(CommandHandler("daily", daily))
    app.add_handler(CommandHandler("give", give))
    app.add_handler(CommandHandler(["toprich", "leaderboard"], toprich))
    app.add_handler(CommandHandler("rank", rank))
