"""File-ID tools: /gid, /sid, /fid — the classic file-id bot flow.

Works in groups and in the bot's DM. Three ways to point at the media:
  1. Reply to it with the command
  2. Send the media with the command as its caption (/gid on a GIF)
  3. Just send the media first, then type the command (last media is
     remembered per user per chat)
Replies carry an inline-Support button; premium stickers also get a blue
"View All" button that dumps every sticker file_id in that pack.
"""
import html
import time

from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler, filters

from keyboards.ui import BLUE, btn, kb

HTML = ParseMode.HTML

LAST = {}     # (chat_id, user_id) -> {"kind", "file_id", "set", "premium", "ts"}
PACKS = {}    # token -> sticker set name (for the View All callback)
_seq = [0]

KINDS = ("gif", "sticker", "photo", "video", "document", "audio", "voice", "video_note")


def _media_of(msg):
    """(kind, file_id, set_name, premium) for the media on this message."""
    g = lambda name: getattr(msg, name, None)
    if g("animation"):
        return "gif", g("animation").file_id, None, False
    if g("sticker"):
        st = g("sticker")
        return "sticker", st.file_id, st.set_name, bool(st.premium_animation)
    if g("photo"):
        return "photo", g("photo")[-1].file_id, None, False
    if g("video"):
        return "video", g("video").file_id, None, False
    if g("document"):
        return "document", g("document").file_id, None, False
    if g("audio"):
        return "audio", g("audio").file_id, None, False
    if g("voice"):
        return "voice", g("voice").file_id, None, False
    if g("video_note"):
        return "video_note", g("video_note").file_id, None, False
    return None


async def remember(update, ctx):
    m = update.effective_message
    u = update.effective_user
    got = _media_of(m) if m else None
    if not got or not u:
        return
    kind, fid, set_name, prem = got
    LAST[(m.chat_id, u.id)] = {"kind": kind, "file_id": fid, "set": set_name,
                               "premium": prem, "ts": time.time()}
    if len(LAST) > 500:  # crude bound — drop oldest
        for k in sorted(LAST, key=lambda x: LAST[x]["ts"])[:100]:
            LAST.pop(k, None)


def _resolve(update, want):
    """Find the target media: the command msg itself, its reply, or last seen."""
    msg = update.effective_message
    u = update.effective_user
    got = _media_of(msg) if msg else None
    if got and got[0] == want:
        return got
    r = msg.reply_to_message
    if r:
        got = _media_of(r)
        if got and got[0] == want:
            return got
        # replying to something else while wanting another kind — keep looking
    last = LAST.get((msg.chat_id, u.id))
    if last and last["kind"] == want and time.time() - last["ts"] <= 1800:
        return want, last["file_id"], last["set"], last["premium"]
    return None


def _support_kb():
    return kb([[btn("🔹 Inline Support", switch="")]])


async def _reply_id(update, title, file_id, markup=None):
    text = f"{title}\n<code>{html.escape(file_id)}</code>"
    await update.effective_message.reply_text(
        text, parse_mode=HTML, reply_markup=markup or _support_kb())


async def gid(update, ctx):
    """/gid — GIF (animation) file_id."""
    got = _resolve(update, "gif")
    if not got:
        return await update.effective_message.reply_text(
            "Send me a GIF first (or reply to one) — then /gid.\n"
            "You can also send the GIF with /gid as its caption.")
    await _reply_id(update, "🎬 <b>GIF file_id</b>", got[1])


async def fid(update, ctx):
    """/fid — file_id of any media (photo, video, document, audio, voice...)."""
    msg = update.effective_message
    u = update.effective_user
    got = _media_of(msg)
    if not got:
        r = msg.reply_to_message
        got = _media_of(r) if r else None
    if not got:
        last = LAST.get((msg.chat_id, u.id))
        if last and time.time() - last["ts"] <= 1800:
            got = (last["kind"], last["file_id"], last["set"], last["premium"])
    if not got:
        return await msg.reply_text(
            "Send any file (photo, video, document, audio, voice, GIF, sticker) "
            "then /fid — or reply to it with /fid.")
    kind = {"gif": "🎬 GIF", "sticker": "🏷 Sticker", "photo": "📷 Photo", "video": "🎥 Video",
            "document": "📄 Document", "audio": "🎵 Audio", "voice": "🎤 Voice",
            "video_note": " round video note"}[got[0]]
    await _reply_id(update, f"{kind} <b>file_id</b>", got[1])


async def sid(update, ctx):
    """/sid — sticker file_id (+ View All for premium packs)."""
    got = _resolve(update, "sticker")
    if not got:
        return await update.effective_message.reply_text(
            "Send me a sticker first (or reply to one) — then /sid.\n"
            "Premium stickers work too.")
    _, fid_, set_name, premium = got
    rows = [[btn("🔹 Inline Support", switch="")]]
    if premium and set_name:  # premium pack — dump every id in the pack
        _seq[0] += 1
        PACKS[str(_seq[0])] = set_name
        if len(PACKS) > 200:
            for k in list(PACKS)[:100]:
                PACKS.pop(k, None)
        rows.append([btn("🔵 View All (Premium)", f"sidpack:{_seq[0]}", BLUE)])
    lines = [f"🏷 <b>Sticker file_id</b>" + ("  ·  ⭐ Premium" if premium else "")]
    if set_name:
        lines.append(f"Pack: <i>{html.escape(set_name)}</i>")
    lines.append(f"<code>{html.escape(fid_)}</code>")
    await update.effective_message.reply_text(
        "\n".join(lines), parse_mode=HTML, reply_markup=kb(rows))


async def on_pack(update, ctx):
    """/sid's View All — dump every sticker file_id in the pack."""
    q = update.callback_query
    token = q.data.split(":", 1)[1]
    set_name = PACKS.get(token)
    if not set_name:
        return await q.answer("Expired — run /sid again.", show_alert=True)
    try:
        sset = await ctx.bot.get_sticker_set(set_name)
    except Exception:
        return await q.answer("Couldn't fetch that sticker pack.", show_alert=True)
    await q.answer()
    stickers = list(sset.stickers)
    header = (f"📦 <b>{html.escape(sset.title or sset.name)}</b>\n"
              f"{len(stickers)} sticker(s) in this pack\n"
              f"<i>Tap &amp; hold any id to copy.</i>\n\n")
    chunk, n = header, 0
    for i, st in enumerate(stickers, 1):
        line = f"{i}. {st.emoji or ''} <code>{html.escape(st.file_id)}</code>\n"
        if len(chunk) + len(line) > 3800:
            await ctx.bot.send_message(q.message.chat_id, chunk, parse_mode=HTML)
            chunk, n = "", 0
        chunk += line
        n += 1
    if chunk:
        await ctx.bot.send_message(q.message.chat_id, chunk, parse_mode=HTML)


async def caption_dispatch(update, ctx):
    """Media sent with /gid | /sid | /fid as its caption (commands in captions)."""
    cap = (update.effective_message.caption or "").split()
    if not cap:
        return
    word = cap[0].split("@")[0].lstrip("/").lower()
    if word == "gid":
        return await gid(update, ctx)
    if word == "sid":
        return await sid(update, ctx)
    if word == "fid":
        return await fid(update, ctx)


def register(app):
    app.add_handler(CommandHandler(["gid", "gifid"], gid, block=False))
    app.add_handler(CommandHandler(["sid", "stickerid"], sid, block=False))
    app.add_handler(CommandHandler(["fid", "fileid"], fid, block=False))
    app.add_handler(MessageHandler(filters.CaptionRegex(r"^/(gid|sid|fid|gifid|stickerid|fileid)(?:@\w+)?(?:\s|$)"),
                                   caption_dispatch, block=False))
    app.add_handler(CallbackQueryHandler(on_pack, pattern=r"^sidpack:"), )
    app.add_handler(MessageHandler(
        (filters.ChatType.GROUP | filters.ChatType.SUPERGROUP | filters.ChatType.PRIVATE) &
        (filters.ANIMATION | filters.Sticker.ALL | filters.PHOTO |
         filters.VIDEO | filters.Document.ALL | filters.AUDIO |
         filters.VOICE | filters.VIDEO_NOTE),
        remember, block=False), group=5)
