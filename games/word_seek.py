"""
WordSeek — Find hidden words in a letter grid.

How it works:
- Bot generates a 10x10 grid with 5 hidden words
- Grid is shown as a monospace text block
- Players type any hidden word to score points
- First to find all words wins, or game ends after time limit
- Each found word = reward coins + XP
"""

import random
import string
import time

import config
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, MessageHandler, filters

from database import mongo, users
from utils.helpers import safe_answer
from utils.validators import mention

HTML = ParseMode.HTML

# ── Word bank ────────────────────────────────────────────────────────────────
WORD_BANK = [
    "PYTHON", "NOVA", "GAME", "COIN", "STAR", "MOON", "FIRE", "WIND",
    "STORM", "BLADE", "GHOST", "TIGER", "EAGLE", "SHARK", "VIPER",
    "POWER", "GLORY", "BRAVE", "CROWN", "ARROW", "MAGIC", "DREAM",
    "FLASH", "SPEED", "NINJA", "LIGHT", "STONE", "WATER", "EARTH",
    "SPACE", "RIDER", "QUEST", "SPELL", "SWORD", "CHAOS", "GUARD",
    "FORCE", "ROUGE", "STEEL", "BLOOM", "FROST", "FLAME", "SMOKE",
    "SWIFT", "CLOUD", "DELTA", "OMEGA", "ALPHA", "ULTRA", "CYBER",
    "RADIO", "SOLAR", "LUNAR", "LASER", "PIXEL", "SONIC", "TURBO",
]

GRID_SIZE = 10
WORDS_COUNT = 5
SEEK_TIME = 120       # seconds
SEEK_REWARD = 80      # coins per word found
SEEK_XP = 8

# Directions: right, down, diagonal down-right, diagonal down-left
DIRECTIONS = [
    (0, 1),   # right
    (1, 0),   # down
    (1, 1),   # diagonal down-right
    (1, -1),  # diagonal down-left
]

# Active games: chat_id -> game state
GAMES: dict[int, dict] = {}


# ── Grid builder ─────────────────────────────────────────────────────────────

def _empty_grid():
    return [["." for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]


def _place_word(grid, word):
    """Try to place a word randomly in the grid. Returns True on success."""
    dirs = DIRECTIONS[:]
    random.shuffle(dirs)
    for dr, dc in dirs:
        rows = list(range(GRID_SIZE))
        cols = list(range(GRID_SIZE))
        random.shuffle(rows)
        random.shuffle(cols)
        for r in rows:
            for c in cols:
                end_r = r + dr * (len(word) - 1)
                end_c = c + dc * (len(word) - 1)
                if not (0 <= end_r < GRID_SIZE and 0 <= end_c < GRID_SIZE):
                    continue
                # Check all cells are free or match
                ok = True
                for i, ch in enumerate(word):
                    if grid[r + dr * i][c + dc * i] not in (".", ch):
                        ok = False
                        break
                if ok:
                    for i, ch in enumerate(word):
                        grid[r + dr * i][c + dc * i] = ch
                    return True
    return False


def _build_grid(words):
    grid = _empty_grid()
    placed = []
    for w in words:
        if _place_word(grid, w):
            placed.append(w)
    # Fill blanks with random letters
    for r in range(GRID_SIZE):
        for c in range(GRID_SIZE):
            if grid[r][c] == ".":
                grid[r][c] = random.choice(string.ascii_uppercase)
    return grid, placed


def _render(grid, found: set) -> str:
    """Render grid as monospace. Found words' cells shown as · (dot)."""
    header = "   " + " ".join(str(i) for i in range(GRID_SIZE))
    rows = [header]
    for i, row in enumerate(grid):
        rows.append(f"{i:2} " + " ".join(row))
    return "\n".join(rows)


def _game_text(g: dict) -> str:
    found = g["found"]
    words = g["words"]
    remaining = [w for w in words if w not in found]
    found_list = " ".join(f"✅ {w}" for w in found) or "none yet"
    remain_list = " ".join(f"❓" for _ in remaining)
    elapsed = int(time.time() - g["start"])
    left = max(0, SEEK_TIME - elapsed)
    return (
        f"🔎 <b>WordSeek</b> — Find <b>{len(words)}</b> hidden words!\n"
        f"⏱ Time left: <b>{left}s</b>\n\n"
        f"<pre>{_render(g['grid'], set())}</pre>\n\n"
        f"Found: {found_list}\n"
        f"Remaining: {remain_list} ({len(remaining)} left)\n\n"
        f"<i>Type any word you find in the grid!</i>"
    )


# ── Handlers ─────────────────────────────────────────────────────────────────

async def wordseek(update, ctx):
    chat_id = update.effective_chat.id
    msg = update.effective_message

    if chat_id in GAMES:
        g = GAMES[chat_id]
        if time.time() - g["start"] < SEEK_TIME:
            return await msg.reply_text(
                "🔎 A WordSeek game is already running!\n"
                "Type the words you find to score.",
                parse_mode=HTML,
            )
        else:
            GAMES.pop(chat_id, None)

    words = random.sample(WORD_BANK, WORDS_COUNT)
    grid, placed = _build_grid(words)

    if len(placed) < WORDS_COUNT:
        words = placed  # use however many got placed

    g = {
        "grid": grid,
        "words": placed,
        "found": set(),
        "found_by": {},      # word -> user_id
        "start": time.time(),
        "msg_id": None,
        "chat_id": chat_id,
    }
    GAMES[chat_id] = g

    sent = await msg.reply_text(_game_text(g), parse_mode=HTML)
    g["msg_id"] = sent.message_id

    # Schedule auto-end
    ctx.job_queue.run_once(
        _timeout, SEEK_TIME, data=chat_id, name=f"ws_{chat_id}"
    )


async def _timeout(ctx):
    chat_id = ctx.job.data
    g = GAMES.pop(chat_id, None)
    if not g:
        return
    found = g["found"]
    words = g["words"]
    missed = [w for w in words if w not in found]
    text = (
        f"⌛ <b>WordSeek ended!</b>\n\n"
        f"✅ Found: {', '.join(found) if found else 'none'}\n"
        f"❌ Missed: {', '.join(missed) if missed else 'none'}\n\n"
    )
    if g["found_by"]:
        # Scoreboard
        scores: dict[int, int] = {}
        for uid in g["found_by"].values():
            scores[uid] = scores.get(uid, 0) + 1
        top = sorted(scores.items(), key=lambda x: -x[1])
        text += "🏆 <b>Top finders:</b>\n"
        for uid, cnt in top[:5]:
            d = await mongo.db.users.find_one({"_id": uid})
            name = d.get("name", str(uid)) if d else str(uid)
            text += f"  • {name} — {cnt} word(s)\n"
    await ctx.bot.send_message(chat_id, text, parse_mode=HTML)


async def check_wordseek(update, ctx):
    """Check if a message text matches a hidden word in the active game."""
    chat_id = update.effective_chat.id
    g = GAMES.get(chat_id)
    if not g:
        return

    # Expired?
    if time.time() - g["start"] > SEEK_TIME:
        GAMES.pop(chat_id, None)
        return

    word = (update.effective_message.text or "").strip().upper()
    if word not in g["words"]:
        return
    if word in g["found"]:
        return  # already found

    # Valid find!
    u = update.effective_user
    g["found"].add(word)
    g["found_by"][word] = u.id

    await users.ensure_user(u)
    await users.add_balance(u.id, SEEK_REWARD, "wordseek_find")
    await users.add_xp(u.id, SEEK_XP)

    remaining = [w for w in g["words"] if w not in g["found"]]

    if not remaining:
        # All found — end game
        GAMES.pop(chat_id, None)
        # Cancel timeout job
        jobs = ctx.job_queue.get_jobs_by_name(f"ws_{chat_id}")
        for j in jobs:
            j.schedule_removal()

        await update.effective_message.reply_text(
            f"🎉 {mention(u)} found the last word <b>{word}</b> and wins! +${SEEK_REWARD}\n\n"
            f"All {len(g['words'])} words found! Game over.",
            parse_mode=HTML,
        )
        return

    await update.effective_message.reply_text(
        f"✅ {mention(u)} found <b>{word}</b>! +${SEEK_REWARD}\n"
        f"<i>{len(remaining)} word(s) remaining...</i>",
        parse_mode=HTML,
    )


def register(app):
    app.add_handler(CommandHandler("wordseek", wordseek))
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS,
            check_wordseek,
            block=False,
        ),
        group=4,
    )
