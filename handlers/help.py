from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, CommandHandler

from keyboards.games_menu import GAME_MAP, game_page_menu, games_menu
from keyboards.help_menu import back_to_help, help_menu
from keyboards.main_menu import start_menu

MAIN = "💞 <b>Help & Commands</b>\n\nChoose a category below to explore Nova's features and commands."

PAGES = {
    "economy": (
        "💰 <b>Economy</b>\n\n"
        "/balance or /bal — balance & XP\n/daily — daily reward (24h)\n"
        "/give &lt;amount&gt; — reply to a user to pay them\n"
        "/toprich or /leaderboard — richest players\n/rank — your XP rank"
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
        "/couple or /shippering — ship two random group members"
    ),
    "admins": (
        "🛡️ <b>Admins</b>\n\n"
        "/admin — dashboard\n/stats — bot statistics\n/ban /unban — manage access (reply or id)\n"
        "/broadcast — announce\n/maintenance — toggle maintenance\n/setwelcome — welcome message"
    ),
}


async def help_cmd(update, ctx):
    await update.effective_message.reply_text(MAIN, parse_mode=ParseMode.HTML, reply_markup=help_menu())


async def games_cmd(update, ctx):
    await update.effective_message.reply_text(
        "🎮 <b>Game commands</b> 🎮\n\nChoose a game below to see how to play and its commands! 👇",
        parse_mode=ParseMode.HTML, reply_markup=games_menu())


async def on_help(update, ctx):
    q = update.callback_query
    await q.answer()
    page = q.data.split(":", 1)[1]
    if page == "main":
        await q.edit_message_text(MAIN, parse_mode=ParseMode.HTML, reply_markup=help_menu())
    elif page == "start":
        await q.edit_message_text("💞 <b>Welcome to Nova!</b>", parse_mode=ParseMode.HTML,
                                  reply_markup=start_menu(ctx.bot.username))
    elif page == "games":
        await q.edit_message_text(
            "🎮 <b>Game commands</b> 🎮\n\nChoose a game below to see how to play and its commands! 👇",
            parse_mode=ParseMode.HTML, reply_markup=games_menu())
    elif page in PAGES:
        await q.edit_message_text(PAGES[page], parse_mode=ParseMode.HTML, reply_markup=back_to_help())


async def on_game_page(update, ctx):
    q = update.callback_query
    await q.answer()
    key, label, desc, cmd, ready = GAME_MAP[q.data.split(":", 1)[1]]
    status = "✅ Available" if ready else "🚧 Coming soon"
    await q.edit_message_text(
        f"<b>{label}</b>\n\n{desc}\n\n<b>Command:</b> <code>{cmd}</code>\n<b>Status:</b> {status}",
        parse_mode=ParseMode.HTML, reply_markup=game_page_menu())


def register(app):
    app.add_handler(CommandHandler(["help", "commands"], help_cmd))
    app.add_handler(CommandHandler("games", games_cmd))
    app.add_handler(CallbackQueryHandler(on_help, pattern=r"^help:"))
    app.add_handler(CallbackQueryHandler(on_game_page, pattern=r"^g:"))
