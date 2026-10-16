from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import CallbackQueryHandler, CommandHandler

from handlers.start import WELCOME_CARD, WELCOME_CARD_PLAIN
from keyboards.games_menu import GAME_MAP, game_page_menu, games_menu
from keyboards.help_menu import back_to_help, help_menu
from keyboards.main_menu import start_menu
from utils.helpers import safe_answer

MAIN = "💞 <b>Help & Commands</b>\n\nChoose a category below to explore Nova's features and commands."

PAGES = {
    "economy": (
        "💰 <b>Economy</b>\n\n"
        "/balance or /bal — balance & XP\n/daily — daily reward (24h)\n"
        "/give &lt;amount&gt; — reply to a user to pay them\n"
        "/toprich — top 3 richest\n/leaderboard — top 10 richest\n/rank — your XP rank"
    ),
    "actions": (
        "⚡ <b>Actions</b>\n\n"
        "/rob &lt;amount&gt; — steal from a user (reply)\n"
        "/kill &lt;amount&gt; — bounty attack (reply)\n"
        "/protect — buy a shield\n/shield or /protection — protection status\n"
        "/revive — revive a dead user (reply) or yourself\n/topkill — top assassins"
    ),
    "romance": (
        "💗 <b>Romance</b>\n\n"
        "/propose — reply to someone to propose\n/divorce — end your marriage\n"
        "/marriage or /married — marriage status (reply for others)\n"
        "/couple or /shipering — ship two members (reply to fix one)"
    ),
    "admins": (
        "🛡️ <b>Admins</b>\n\n"
        "/admin — dashboard\n/stats — bot statistics\n/ban /unban — manage access (reply or id)\n"
        "/addsudo — (owner) promote a user to sudo\n/sudolist — list all sudo users\n"
        "/broadcast — announce\n/maintenance — toggle maintenance\n/setwelcome — welcome message"
    ),
}


async def _safe_edit(q, text, parse_mode=ParseMode.HTML, reply_markup=None):
    """Edit the message **in place** — never delete + re-create.

    The welcome banner is a video message, so its text lives in the caption:
    media messages get `edit_message_caption`, plain text messages get
    `edit_message_text`. Same message, same position in the chat.
    """
    msg = q.message
    is_media = any(getattr(msg, m, None) for m in
                   ("video", "photo", "animation", "document", "audio", "voice", "video_note"))
    try:
        if is_media:
            await q.edit_message_caption(caption=text, parse_mode=parse_mode,
                                         reply_markup=reply_markup)
        else:
            await q.edit_message_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
    except BadRequest as e:
        if "message is not modified" in str(e).lower():
            return  # already showing this page — nothing to do
        raise


async def help_cmd(update, ctx):
    await update.effective_message.reply_text(MAIN, parse_mode=ParseMode.HTML, reply_markup=help_menu())


async def games_cmd(update, ctx):
    await update.effective_message.reply_text(
        "🎮 <b>Game commands</b> 🎮\n\nChoose a game below to see how to play and its commands! 👇",
        parse_mode=ParseMode.HTML, reply_markup=games_menu())


CHAT_TEXT = (
    "💀 <b>Chatting With Nova</b>\n\n"
    "I'm not your average bot — I actually <b>remember you</b>. As we talk, I quietly save the things worth keeping "
    "(what you're into, what's going on with you) so you never repeat yourself. No setup, no format — just talk to me, "
    "and the more we chat, the better I know you. 🖤\n\n"
    "🔔 <b>Check-ins &amp; reactions</b>\n"
    "<code>/checkins on|off</code> — my occasional check-ins\n"
    "<code>/reactions on|off</code> — emoji reactions on your messages\n\n"
    "👥 <b>In group chats</b>\n"
    "I reply when you @mention me, call my name, or reply to me — otherwise I chime in now and then (never spam).\n"
    "<code>/quiet</code> — I'll hang back (just for you)\n"
    "<code>/chatty</code> — I'll join in more (just for you)\n\n"
    "🔧 <b>Group admins</b>\n"
    "<code>/groupbot on|off</code> — turn me on/off for the whole group\n"
    "<code>/groupmode quiet|chatty|normal</code> — set how chatty I am for everyone\n\n"
    "<i>An admin's choice takes priority over personal /quiet or /chatty.</i>"
)


async def on_chat(update, ctx):
    q = update.callback_query
    await safe_answer(q)
    from keyboards.ui import RED, btn, kb
    back_kb = kb([[btn("◀️ Back", "help:start", RED)]])
    await _safe_edit(q, CHAT_TEXT, reply_markup=back_kb)


async def on_help(update, ctx):
    q = update.callback_query
    await safe_answer(q)
    page = q.data.split(":", 1)[1]
    if page == "main":
        await _safe_edit(q, MAIN, reply_markup=help_menu())
    elif page == "start":
        # Back to Main: edit the same message back to the welcome card.
        # Premium emoji first, plain fallback if custom emoji is rejected.
        markup = start_menu(ctx.bot.username)
        for body in (WELCOME_CARD, WELCOME_CARD_PLAIN):
            try:
                await _safe_edit(q, body, reply_markup=markup)
                break
            except BadRequest:
                continue
    elif page == "games":
        await _safe_edit(q,
            "🎮 <b>Game commands</b> 🎮\n\nChoose a game below to see how to play and its commands! 👇",
            reply_markup=games_menu())
    elif page in PAGES:
        await _safe_edit(q, PAGES[page], reply_markup=back_to_help())


async def on_game_page(update, ctx):
    q = update.callback_query
    await safe_answer(q)
    key, label, desc, cmd, ready = GAME_MAP[q.data.split(":", 1)[1]]
    status = "✅ Available" if ready else "🚧 Coming soon"
    await _safe_edit(q,
        f"<b>{label}</b>\n\n{desc}\n\n<b>Command:</b> <code>{cmd}</code>\n<b>Status:</b> {status}",
        reply_markup=game_page_menu())


def register(app):
    app.add_handler(CommandHandler(["help", "commands"], help_cmd))
    app.add_handler(CommandHandler("games", games_cmd))
    app.add_handler(CallbackQueryHandler(on_chat, pattern=r"^chat:"))
    app.add_handler(CallbackQueryHandler(on_help, pattern=r"^help:"))
    app.add_handler(CallbackQueryHandler(on_game_page, pattern=r"^g:"))
