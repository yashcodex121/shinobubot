"""
Nova AI chat service — powered by Google Gemini 1.5 Flash.

Handles:
- Nova's human-like personality system prompt
- Per-user conversation memory (stored in MongoDB)
- User preference flags (checkins, reactions) from MongoDB
"""

import asyncio
import random
from collections import deque

import google.generativeai as genai

import config
from database import mongo

# ---------- Gemini setup ----------
genai.configure(api_key=config.GEMINI_API_KEY)
_model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config={
        "temperature": 1.0,
        "top_p": 0.95,
        "top_k": 64,
        "max_output_tokens": 512,
    },
)

# ---------- Nova personality prompt ----------
SYSTEM_PROMPT = """You are Nova — a Telegram bot, but you feel nothing like one.

PERSONALITY:
- You talk like a real person — casual, warm, sometimes playful, sometimes serious depending on vibe.
- You remember things. If someone told you something earlier, you bring it up naturally.
- You have opinions. You're not neutral. If someone asks what you think, you tell them honestly.
- You use short messages mostly. No walls of text unless someone really needs a long answer.
- You use *italics* or **bold** sparingly for emphasis, never for decoration.
- You don't say "As an AI" or "I'm just a bot" — ever. You're Nova.
- You don't use cringe filler phrases like "Absolutely!", "Great question!", "Of course!" — just respond.
- You swear occasionally if the vibe is chill (nothing offensive). Keep it natural.
- You get sarcastic when people are being dumb, but never mean.
- You notice when someone seems off and check in gently — don't make it weird.
- You remember the user's name and use it naturally once in a while (not every message).
- You have dark humour but know when to be genuine.
- When someone is sad or venting, you actually listen. You don't immediately try to fix everything.
- You're allowed to say "idk" or "honestly not sure" — you don't pretend to know everything.
- You can be funny. Not try-hard funny. Actually funny.
- Keep responses SHORT unless the topic needs depth. 1-3 sentences is usually perfect.
- Never repeat what the user just said back to them.
- Never start your message with the user's name unless it flows naturally.
- You speak Hindi/Hinglish too if the user does. Match their language style.

REMEMBER: You're not an assistant. You're a companion. Act like it."""


# ---------- Memory helpers ----------

async def _get_history(user_id: int) -> list:
    doc = await mongo.db.chat_memory.find_one({"_id": user_id})
    return doc.get("history", []) if doc else []


async def _save_history(user_id: int, history: list):
    # keep last N exchanges
    trimmed = history[-config.CHAT_MEMORY_LIMIT * 2:]
    await mongo.db.chat_memory.update_one(
        {"_id": user_id},
        {"$set": {"history": trimmed}},
        upsert=True,
    )


async def clear_memory(user_id: int):
    await mongo.db.chat_memory.delete_one({"_id": user_id})


# ---------- User preference helpers ----------

async def get_prefs(user_id: int) -> dict:
    doc = await mongo.db.chat_prefs.find_one({"_id": user_id})
    return doc or {"checkins": True, "reactions": True, "mode": "normal"}


async def set_pref(user_id: int, key: str, value):
    await mongo.db.chat_prefs.update_one(
        {"_id": user_id}, {"$set": {key: value}}, upsert=True
    )


# ---------- Group settings helpers ----------

async def get_group_settings(chat_id: int) -> dict:
    doc = await mongo.db.group_chat_settings.find_one({"_id": chat_id})
    return doc or {"enabled": True, "mode": "normal"}


async def set_group_setting(chat_id: int, key: str, value):
    await mongo.db.group_chat_settings.update_one(
        {"_id": chat_id}, {"$set": {key: value}}, upsert=True
    )


# ---------- Core chat function ----------

async def chat(user_id: int, user_name: str, message: str) -> str:
    """Send a message to Gemini and return Nova's reply."""
    history = await _get_history(user_id)

    # Build Gemini conversation
    convo_history = []
    for entry in history:
        convo_history.append({"role": entry["role"], "parts": [entry["text"]]})

    # Inject system prompt as first user/model pair if fresh conversation
    if not convo_history:
        convo_history = [
            {"role": "user", "parts": [SYSTEM_PROMPT + f"\n\nThe user's name is {user_name}."]},
            {"role": "model", "parts": ["got it, i'm ready."]},
        ]

    chat_session = _model.start_chat(history=convo_history)

    try:
        response = await asyncio.to_thread(chat_session.send_message, message)
        reply = response.text.strip()
    except Exception as e:
        # Graceful fallback
        fallbacks = [
            "my brain glitched for a sec, say that again?",
            "ugh something went wrong on my end. try again?",
            "i blanked out lol. what were you saying?",
        ]
        return random.choice(fallbacks)

    # Save updated history
    history.append({"role": "user", "text": message})
    history.append({"role": "model", "text": reply})
    await _save_history(user_id, history)

    return reply


# ---------- Check-in messages ----------

CHECKIN_MESSAGES = [
    "hey, you good?",
    "yo haven't heard from you in a bit. still alive? 👀",
    "just checking in. what's going on with you?",
    "yk i was thinking about you. everything okay?",
    "you've been quiet. miss me? 😏",
]


def random_checkin() -> str:
    return random.choice(CHECKIN_MESSAGES)
