"""
Nova chat handler — all chat commands + AI message listener.

Commands:
  /checkins on|off   — toggle Nova's occasional check-in messages
  /reactions on|off  — toggle emoji reactions on user messages
  /quiet             — Nova goes quiet in group (just for you)
  /chatty            — Nova joins in more in group (just for you)
  /groupbot on|off   — admin: toggle Nova for entire group
  /groupmode quiet|chatty|normal — admin: set group-wide chat mode
  /forget            — clear your conversation memory with Nova
"""

import asyncio
import html
import random

from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config
from services.chat_service import (
    chat,
    clear_memory,
    get_group_settings,
    get_prefs,
    random_checkin,
    set_group_setting,
    set_pref,
)
from utils.permissions import is_admin

# Emoji reactions Nova can send
REACTIONS = ["❤️", "🔥", "😂", "👀", "💀", "🫡", "🤙", "😭", "✨", "🥺"]


# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────

def _is_private(update: Update) -> bool:
    return update.effective_chat.type == "private"


def _bot_mentioned(update: Update, bot_username: str) -> bool:
    """True if bot is @mentioned or replied to in a group message."""
    msg = update.effective_message
    if not msg:
        return False
    # Direct reply to bot
    if msg.reply_to_message and msg.reply_to_message.from_user:
        if msg.reply_to_message.from_user.username == bot_username:
            return True
    # @mention in text
    text = msg.text or msg.caption or ""
    if f"@{bot_username}".lower() in text.lower():
        return True
    # Mention via entities
    for entity in (msg.entities or []):
        if entity.type == "mention":
            mention = text[entity.offset: entity.offset + entity.length]
            if mention.lower() == f"@{bot_username}".lower():
                return True
    return False


async def _should_respond_group(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    """Decide whether Nova should respond in a group message."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    bot_username = ctx.bot.username

    group_settings = await get_group_settings(chat_id)
    if not group_settings.get("enabled", True):
        return False

    group_mode = group_settings.get("mode", "normal")
    user_prefs = await get_prefs(user_id)
    user_mode = user_prefs.get("mode", "normal")

    # Admin group-wide mode takes priority
    if group_mode == "quiet":
        # Only respond when directly mentioned
        return _bot_mentioned(update, bot_username)
    if group_mode == "chatty":
        return True

    # Normal group mode — user personal preference
    if user_mode == "quiet":
        return _bot_mentioned(update, bot_username)
    if user_mode == "chatty":
        return True

    # Default normal: respond to mentions + 15% random chime-in
    if _bot_mentioned(update, bot_username):
        return True
    return random.random() < 0.15


# ─────────────────────────────────────────────
#  Commands
# ─────────────────────────────────────────────

async def cmd_checkins(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args
    user_id = update.effective_user.id
    if not args or args[0].lower() not in ("on", "off"):
        return await update.effective_message.reply_text(
            "Usage: /checkins on|off"
        )
    val = args[0].lower() == "on"
    await set_pref(user_id, "checkins", val)
    msg = "✅ I'll check in on you sometimes. 🖤" if val else "👋 Got it, I'll leave you alone. You know where to find me."
    await update.effective_message.reply_text(msg)


async def cmd_reactions(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args
    user_id = update.effective_user.id
    if not args or args[0].lower() not in ("on", "off"):
        return await update.effective_message.reply_text(
            "Usage: /reactions on|off"
        )
    val = args[0].lower() == "on"
    await set_pref(user_id, "reactions", val)
    msg = "✅ Reactions are on — I'll vibe react to your messages." if val else "👌 No more reactions from me."
    await update.effective_message.reply_text(msg)


async def cmd_quiet(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await set_pref(user_id, "mode", "quiet")
    await update.effective_message.reply_text(
        "🤫 I'll hang back. I'm still here if you need me."
    )


async def cmd_chatty(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await set_pref(user_id, "mode", "chatty")
    await update.effective_message.reply_text(
        "😏 Okay I'm joining in more. Don't say I didn't warn you."
    )


async def cmd_groupbot(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if _is_private(update):
        return await msg.reply_text("This command works in groups only.")
    if not await is_admin(update.effective_user.id):
        return await msg.reply_text("❌ Only group admins can use this.")
    args = ctx.args
    if not args or args[0].lower() not in ("on", "off"):
        return await msg.reply_text("Usage: /groupbot on|off")
    val = args[0].lower() == "on"
    await set_group_setting(update.effective_chat.id, "enabled", val)
    msg_text = "✅ Nova is active in this group." if val else "🔕 Nova has gone silent in this group."
    await msg.reply_text(msg_text)


async def cmd_groupmode(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if _is_private(update):
        return await msg.reply_text("This command works in groups only.")
    if not await is_admin(update.effective_user.id):
        return await msg.reply_text("❌ Only group admins can use this.")
    args = ctx.args
    valid = ("quiet", "chatty", "normal")
    if not args or args[0].lower() not in valid:
        return await msg.reply_text("Usage: /groupmode quiet|chatty|normal")
    mode = args[0].lower()
    await set_group_setting(update.effective_chat.id, "mode", mode)
    descriptions = {
        "quiet": "🤫 Group mode: quiet — I'll only speak when mentioned.",
        "chatty": "💬 Group mode: chatty — I'll join in freely.",
        "normal": "👌 Group mode: normal — I'll be chill.",
    }
    await msg.reply_text(descriptions[mode])


async def cmd_forget(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await clear_memory(update.effective_user.id)
    await update.effective_message.reply_text(
        "🧹 Done. Fresh start — I don't remember anything we talked about."
    )


# ─────────────────────────────────────────────
#  Main message listener
# ─────────────────────────────────────────────

async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    user = update.effective_user
    if not msg or not user or user.is_bot:
        return

    text = msg.text or msg.caption or ""
    if not text.strip():
        return

    is_private = _is_private(update)

    # Group: check if Nova should respond
    if not is_private:
        if not await _should_respond_group(update, ctx):
            return

    # Strip bot mention from text before sending to AI
    bot_username = ctx.bot.username
    clean_text = text.replace(f"@{bot_username}", "").strip()
    if not clean_text:
        clean_text = "hey"

    user_name = html.escape(user.first_name)

    # Show typing indicator
    await ctx.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.TYPING
    )

    # Small human-like delay
    await asyncio.sleep(config.CHAT_TYPING_DELAY)

    # Get AI reply
    reply = await chat(user.id, user_name, clean_text)

    # Send reaction if enabled (private chat only)
    if is_private:
        prefs = await get_prefs(user.id)
        if prefs.get("reactions", True) and random.random() < 0.35:
            try:
                from telegram import ReactionTypeEmoji
                await msg.set_reaction(
                    [ReactionTypeEmoji(random.choice(REACTIONS))]
                )
            except Exception:
                pass  # reactions not supported on all clients/versions

    await msg.reply_text(reply)


# ─────────────────────────────────────────────
#  Register
# ─────────────────────────────────────────────

def register(app):
    app.add_handler(CommandHandler("checkins", cmd_checkins))
    app.add_handler(CommandHandler("reactions", cmd_reactions))
    app.add_handler(CommandHandler("quiet", cmd_quiet))
    app.add_handler(CommandHandler("chatty", cmd_chatty))
    app.add_handler(CommandHandler("groupbot", cmd_groupbot))
    app.add_handler(CommandHandler("groupmode", cmd_groupmode))
    app.add_handler(CommandHandler("forget", cmd_forget))

    # Message listener — private DMs + group messages (text only)
    app.add_handler(
        MessageHandler(
            (filters.TEXT | filters.CAPTION) & ~filters.COMMAND,
            on_message,
        )
    )
