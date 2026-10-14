import asyncio
import time

from telegram.constants import ParseMode
from telegram.ext import (ApplicationHandlerStop, CallbackQueryHandler, CommandHandler, MessageHandler, TypeHandler, filters)
from telegram import Update

from database import mongo
from keyboards.ui import BLUE, GREEN, RED, btn, kb
from utils.permissions import is_admin
from utils.helpers import safe_answer

HTML = ParseMode.HTML


async def guard(update, ctx):
    u = update.effective_user
    if not u or await is_admin(u.id):
        return
    if await mongo.db.banned.find_one({"_id": u.id}):
        raise ApplicationHandlerStop
    s = await mongo.db.settings.find_one({"_id": "maintenance"})
    if s and s.get("on"):
        if update.effective_message and update.effective_message.text and update.effective_message.text.startswith("/"):
            await update.effective_message.reply_text("🛠️ Nova is under maintenance. Back soon!")
        raise ApplicationHandlerStop


def admin_only(fn):
    async def w(update, ctx):
        if not await is_admin(update.effective_user.id):
            return await update.effective_message.reply_text("🚫 Admins only.")
        return await fn(update, ctx)
    return w


async def _stats_text():
    u = await mongo.db.users.count_documents({})
    g = await mongo.db.group_members.distinct("chat")
    tx = await mongo.db.transactions.count_documents({})
    m = await mongo.db.marriages.count_documents({"status": "active"})
    return f"📊 <b>Nova stats</b>\n👤 Users: {u}\n👥 Groups seen: {len(g)}\n💸 Transactions: {tx}\n💍 Marriages: {m}"


async def _dash_kb():
    on = ((await mongo.db.settings.find_one({"_id": "maintenance"})) or {}).get("on")
    return kb([[btn("📊 Stats", "adm:stats", BLUE)],
               [btn("🟢 Maintenance: OFF" if not on else "🔴 Maintenance: ON", "adm:maint", GREEN if not on else RED)]])


@admin_only
async def admin(update, ctx):
    await update.effective_message.reply_text("🛡️ <b>Admin dashboard</b>", parse_mode=HTML, reply_markup=await _dash_kb())


@admin_only
async def stats(update, ctx):
    await update.effective_message.reply_text(await _stats_text(), parse_mode=HTML)


async def on_admin(update, ctx):
    q = update.callback_query
    if not await is_admin(q.from_user.id):
        return await safe_answer(q, "Admins only.", show_alert=True)
    if q.data == "adm:stats":
        await safe_answer(q)
        return await q.edit_message_text(await _stats_text(), parse_mode=HTML, reply_markup=await _dash_kb())
    on = ((await mongo.db.settings.find_one({"_id": "maintenance"})) or {}).get("on")
    await mongo.db.settings.update_one({"_id": "maintenance"}, {"$set": {"on": not on}}, upsert=True)
    await safe_answer(q, "Toggled")
    await q.edit_message_reply_markup(await _dash_kb())


@admin_only
async def get_file_id(update, ctx):
    """Reply with file_id of any media/sticker/GIF sent or forwarded."""
    msg = update.effective_message
    file_id = file_type = None

    if msg.sticker:
        file_id = msg.sticker.file_id
        file_type = "🎭 Sticker"
    elif msg.animation:
        file_id = msg.animation.file_id
        file_type = "🎞 GIF / Animation"
    elif msg.video:
        file_id = msg.video.file_id
        file_type = "🎬 Video"
    elif msg.photo:
        file_id = msg.photo[-1].file_id
        file_type = "🖼 Photo"
    elif msg.audio:
        file_id = msg.audio.file_id
        file_type = "🎵 Audio"
    elif msg.voice:
        file_id = msg.voice.file_id
        file_type = "🎤 Voice"
    elif msg.video_note:
        file_id = msg.video_note.file_id
        file_type = "📹 Video Note"
    elif msg.document:
        file_id = msg.document.file_id
        file_type = "📄 Document"
    else:
        return

    support_kb = kb([[btn("🔧 Support", url="https://t.me/NovaSupport", style=BLUE)]])
    await msg.reply_text(
        f"{file_type}\n<code>{file_id}</code>",
        parse_mode=HTML,
        reply_markup=support_kb,
    )
    r = update.effective_message.reply_to_message
    if r and r.from_user:
        return r.from_user.id
    return int(ctx.args[0]) if ctx.args and ctx.args[0].lstrip("-").isdigit() else None


@admin_only
async def ban(update, ctx):
    uid = _target_id(update, ctx)
    if not uid:
        return await update.effective_message.reply_text("Reply to a user or pass an ID.")
    await mongo.db.banned.update_one({"_id": uid}, {"$set": {"ts": time.time()}}, upsert=True)
    await update.effective_message.reply_text(f"🔨 Banned {uid}.")


@admin_only
async def unban(update, ctx):
    uid = _target_id(update, ctx)
    if not uid:
        return await update.effective_message.reply_text("Reply to a user or pass an ID.")
    await mongo.db.banned.delete_one({"_id": uid})
    await update.effective_message.reply_text(f"✅ Unbanned {uid}.")


@admin_only
async def maintenance(update, ctx):
    on = not (ctx.args and ctx.args[0].lower() in ("off", "0"))
    await mongo.db.settings.update_one({"_id": "maintenance"}, {"$set": {"on": on}}, upsert=True)
    await update.effective_message.reply_text(f"🛠️ Maintenance {'ON' if on else 'OFF'}.")


@admin_only
async def setwelcome(update, ctx):
    text = update.effective_message.text.partition(" ")[2].strip()
    if not text:
        return await update.effective_message.reply_text("Usage: /setwelcome <HTML text> ({name} = user's name)")
    await mongo.db.settings.update_one({"_id": "welcome"}, {"$set": {"text": text}}, upsert=True)
    await update.effective_message.reply_text("✅ Welcome message updated.")


@admin_only
async def broadcast(update, ctx):
    r = update.effective_message.reply_to_message
    text = update.effective_message.text.partition(" ")[2].strip()
    if not r and not text:
        return await update.effective_message.reply_text("Usage: /broadcast <text> (or reply to a message)")
    ok = fail = 0
    async for d in mongo.db.users.find({}, {"_id": 1}):
        try:
            if r:
                await r.copy(d["_id"])
            else:
                await ctx.bot.send_message(d["_id"], text, parse_mode=HTML)
            ok += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05)
    await mongo.db.broadcast_logs.insert_one({"by": update.effective_user.id, "ok": ok, "fail": fail, "ts": time.time()})
    await update.effective_message.reply_text(f"📢 Done. Delivered: {ok}, failed: {fail}")


def register(app):
    app.add_handler(TypeHandler(Update, guard), group=-1)
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("unban", unban))
    app.add_handler(CommandHandler("maintenance", maintenance))
    app.add_handler(CommandHandler("setwelcome", setwelcome))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CallbackQueryHandler(on_admin, pattern=r"^adm:"))
    # File ID extractor — any media in private chat (admin only)
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & (
            filters.ANIMATION | filters.Sticker.ALL | filters.VIDEO |
            filters.PHOTO | filters.AUDIO | filters.VOICE |
            filters.VIDEO_NOTE | filters.Document.ALL
        ),
        get_file_id,
    ), group=2)
