"""
WordSeek — Wordle-style word guessing game.

How it works:
- Bot picks a hidden word (4, 5 or 6 letters)
- Players type words to guess it
- Each guess gets feedback: ✅ right letter right spot, 🟡 right letter wrong spot, ❌ wrong letter
- First to guess correctly wins coins + XP
- Game ends after 6 wrong guesses or /end

Commands:
  /wordseek or /ws  — 5-letter game
  /ws4              — 4-letter game
  /ws6              — 6-letter game
  /end              — end active game
"""

import random
import time

from telegram.constants import ParseMode
from telegram.ext import CommandHandler, MessageHandler, filters

from database import users
from utils.validators import mention

HTML = ParseMode.HTML

# ── Word banks by length ──────────────────────────────────────────────────────

WORDS = {
    4: [
        "FIRE", "WIND", "STAR", "MOON", "GAME", "COIN", "BOLT", "DARK",
        "GOLD", "IRON", "JADE", "KING", "LION", "MIST", "NOVA", "PEAK",
        "RAID", "SAGE", "TIDE", "VOID", "WOLF", "ZINC", "CAVE", "DAWN",
        "DUSK", "ECHO", "FANG", "GLOW", "HAWK", "ISLE", "JOLT", "KNOT",
        "LAVA", "MAZE", "NOIR", "ORBS", "PYRE", "REEF", "SNOW", "TUSK",
    ],
    5: [
        "FLAME", "STORM", "BLADE", "GHOST", "TIGER", "EAGLE", "SHARK", "VIPER",
        "POWER", "GLORY", "BRAVE", "CROWN", "ARROW", "MAGIC", "DREAM", "FLASH",
        "SPEED", "NINJA", "LIGHT", "STONE", "WATER", "EARTH", "SPACE", "RIDER",
        "QUEST", "SPELL", "SWORD", "CHAOS", "GUARD", "FORCE", "STEEL", "BLOOM",
        "FROST", "SMOKE", "SWIFT", "CLOUD", "DELTA", "OMEGA", "ALPHA", "ULTRA",
        "CYBER", "SOLAR", "LUNAR", "LASER", "PIXEL", "SONIC", "TURBO", "ROUGE",
        "BRAVE", "CREST", "DRIFT", "EMBER", "FLARE", "GRIND", "HAVEN", "IVORY",
    ],
    6: [
        "BLAZED", "STORMY", "BLADES", "MIGHTY", "DRAGON", "FROZEN", "HUNTER",
        "SILVER", "GOLDEN", "MYSTIC", "SHADOW", "BRIDGE", "CASTLE", "FALCON",
        "GLACER", "HERALD", "IMPACT", "JUNGLE", "KNIGHT", "LAUNCH", "METEOR",
        "NEBULA", "ORACLE", "PILLAR", "QUARTZ", "RAFTER", "SHIELD", "THRONE",
        "ULTIMA", "VECTOR", "WIZARD", "XENITH", "YELLOW", "ZENITH", "ARCHER",
    ],
}

MAX_TRIES = 6
REWARD = 150
XP = 15

# Active games: chat_id -> state
GAMES: dict[int, dict] = {}


# ── Game logic ────────────────────────────────────────────────────────────────

def _feedback(guess: str, answer: str) -> str:
    """Return emoji feedback line for a guess."""
    result = []
    answer_chars = list(answer)
    guess_chars = list(guess)
    marks = [""] * len(guess)

    # First pass: correct position
    for i in range(len(guess)):
        if guess_chars[i] == answer_chars[i]:
            marks[i] = "✅"
            answer_chars[i] = None
            guess_chars[i] = None

    # Second pass: wrong position
    for i in range(len(guess)):
        if marks[i]:
            continue
        if guess_chars[i] and guess_chars[i] in answer_chars:
            marks[i] = "🟡"
            answer_chars[answer_chars.index(guess_chars[i])] = None
        else:
            marks[i] = "❌"

    emoji_line = " ".join(marks)
    letter_line = " ".join(f"`{c}`" for c in guess)
    return f"{emoji_line}\n{letter_line}"


def _board_text(g: dict, reveal=False) -> str:
    length = len(g["answer"])
    tries_left = MAX_TRIES - len(g["guesses"])
    header = (
        f"🔎 <b>WordSeek</b> — Guess the <b>{length}-letter</b> word!\n"
        f"Tries left: <b>{tries_left}/{MAX_TRIES}</b>\n\n"
    )
    history = "\n\n".join(g["history"]) if g["history"] else "<i>No guesses yet. Type a word!</i>"
    footer = f"\n\n<i>Type a {length}-letter word to guess!</i>"
    if reveal:
        footer = f"\n\n💡 The word was: <b>{g['answer']}</b>"
    return header + history + footer


# ── Commands ──────────────────────────────────────────────────────────────────

async def _start_game(update, ctx, length: int):
    chat_id = update.effective_chat.id
    msg = update.effective_message

    if chat_id in GAMES:
        g = GAMES[chat_id]
        return await msg.reply_text(
            f"🔎 A WordSeek game is already running! ({len(g['answer'])}-letter word)\n"
            f"Use /end to stop it first.",
        )

    answer = random.choice(WORDS[length])
    GAMES[chat_id] = {
        "answer": answer,
        "guesses": [],
        "history": [],
        "start": time.time(),
        "started_by": update.effective_user.id,
    }
    await msg.reply_text(_board_text(GAMES[chat_id]), parse_mode=HTML)


async def ws(update, ctx):
    await _start_game(update, ctx, 5)


async def ws4(update, ctx):
    await _start_game(update, ctx, 4)


async def ws6(update, ctx):
    await _start_game(update, ctx, 6)


async def end_game(update, ctx):
    chat_id = update.effective_chat.id
    g = GAMES.pop(chat_id, None)
    if not g:
        return await update.effective_message.reply_text("No active WordSeek game.")
    await update.effective_message.reply_text(
        _board_text(g, reveal=True), parse_mode=HTML
    )


# ── Answer checker ────────────────────────────────────────────────────────────

async def check_wordseek(update, ctx):
    chat_id = update.effective_chat.id
    g = GAMES.get(chat_id)
    if not g:
        return

    text = (update.effective_message.text or "").strip().upper()
    length = len(g["answer"])

    if len(text) != length or not text.isalpha():
        return  # not a valid guess length, ignore silently

    if text in g["guesses"]:
        return await update.effective_message.reply_text(
            f"Already guessed <b>{text}</b>! Try another word.", parse_mode=HTML
        )

    u = update.effective_user
    g["guesses"].append(text)

    fb = _feedback(text, g["answer"])
    g["history"].append(f"<b>{mention(u)}:</b> {text}\n{fb}")

    # Win
    if text == g["answer"]:
        GAMES.pop(chat_id, None)
        await users.ensure_user(u)
        await users.add_balance(u.id, REWARD, "wordseek_win")
        await users.add_xp(u.id, XP)
        tries = len(g["guesses"])
        await update.effective_message.reply_text(
            f"🎉 {mention(u)} guessed it in <b>{tries}</b> tr{'y' if tries == 1 else 'ies'}!\n"
            f"Word was: <b>{g['answer']}</b> — +${REWARD} 🪙 +{XP} XP",
            parse_mode=HTML,
        )
        return

    # Out of tries
    if len(g["guesses"]) >= MAX_TRIES:
        GAMES.pop(chat_id, None)
        await update.effective_message.reply_text(
            _board_text({**g, "guesses": g["guesses"], "history": g["history"]}, reveal=True)
            + f"\n\n💀 No more tries! Better luck next time.",
            parse_mode=HTML,
        )
        return

    # Still going
    await update.effective_message.reply_text(
        _board_text(g), parse_mode=HTML
    )


def register(app):
    app.add_handler(CommandHandler(["wordseek", "ws"], ws))
    app.add_handler(CommandHandler("ws4", ws4))
    app.add_handler(CommandHandler("ws6", ws6))
    app.add_handler(CommandHandler("end", end_game))
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS,
            check_wordseek,
            block=False,
        ),
        group=4,
    )
