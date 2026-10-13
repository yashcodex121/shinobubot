"""Shared engine for Jumble / Wordscrambler (one active round per chat)."""
import random

import config
from telegram.constants import ParseMode

from database import mongo, users
from games.words import EASY, HARD

ROUNDS = {}  # chat_id -> dict


def scramble(word):
    for _ in range(10):
        l = random.sample(word, len(word))
        if "".join(l) != word:
            break
    return "".join(l).upper()


async def start_round(update, ctx, kind, hard=False, markup=None):
    chat = update.effective_chat.id
    if chat in ROUNDS:
        return await update.effective_message.reply_text("⚠️ A round is already running here!")
    word = random.choice(HARD if hard else EASY)
    ROUNDS[chat] = {"word": word, "kind": kind}
    msg = await update.effective_message.reply_text(
        f"{'🔤' if kind == 'jumble' else '🔀'} <b>Unscramble:</b> <code>{scramble(word)}</code>\n"
        f"⏱️ {config.WORD_ROUND_SECONDS}s — type your answer in chat!",
        parse_mode=ParseMode.HTML, reply_markup=markup)
    ROUNDS[chat]["job"] = ctx.job_queue.run_once(_timeout, config.WORD_ROUND_SECONDS, data=chat)


async def _timeout(ctx):
    chat = ctx.job.data
    r = ROUNDS.pop(chat, None)
    if r:
        await ctx.bot.send_message(chat, f"⌛ Time's up! The word was <b>{r['word']}</b>.", parse_mode=ParseMode.HTML)


async def check_answer(update, ctx):
    chat = update.effective_chat.id
    r = ROUNDS.get(chat)
    if not r or not update.effective_message.text:
        return
    if update.effective_message.text.strip().lower() != r["word"]:
        return
    if ROUNDS.pop(chat, None) is None:  # first correct answer wins
        return
    r["job"].schedule_removal()
    u = update.effective_user
    await users.ensure_user(u)
    reward = random.randint(config.GAME_REWARD_MIN, config.GAME_REWARD_MAX)
    await users.add_balance(u.id, reward, "game_reward")
    await users.add_xp(u.id, 5)
    await mongo.db.game_stats.update_one({"_id": f"{r['kind']}:{u.id}"}, {"$inc": {"wins": 1}}, upsert=True)
    await update.effective_message.reply_text(
        f"🎉 <b>{u.full_name}</b> got it: <b>{r['word']}</b>! +${reward}", parse_mode=ParseMode.HTML)
