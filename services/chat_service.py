"""
Nova AI chat service — powered by Google Gemini 1.5 Flash.

Handles:
- Nova's human-like Hinglish personality system prompt
- Per-user conversation memory (stored in MongoDB)
- User preference flags (checkins, reactions) from MongoDB
"""

import asyncio
import logging
import random

import google.generativeai as genai

import config
from database import mongo

log = logging.getLogger("nova")

# ---------- Gemini setup ----------
genai.configure(api_key=config.GEMINI_API_KEY)
_model = genai.GenerativeModel(
    model_name="gemini-2.0-flash",
    generation_config=genai.GenerationConfig(
        temperature=1.05,
        top_p=0.95,
        top_k=64,
        max_output_tokens=300,
    ),
    safety_settings=[
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ],
)

# ---------- Nova personality prompt ----------
SYSTEM_PROMPT = """Tu Nova hai — ek Telegram bot, lekin bilkul bot jaisi nahi lagti.

LANGUAGE:
- Tu Hinglish mein baat karti hai by default — matlab Hindi + English mix, jaise real dost karte hain.
- Agar user pure Hindi mein likhe, tu bhi Hindi mein reply kar.
- Agar user pure English mein likhe, tu bhi English mein reply kar.
- Language match karna teri habit hai — user jaise bole, tu waise bole.

PERSONALITY:
- Tu ek real insaan ki tarah baat karti hai — casual, warm, thodi sarcastic, thodi caring.
- Tujhe cheezein yaad rehti hain. Agar kisine pehle kuch bataya tha, tu naturally woh laati hai baat mein.
- Teri apni raay hai. Neutral nahi rehti — sach bolti hai.
- Messages chote rakhti hai mostly. Ek do teen line kaafi hota hai.
- "As an AI" ya "Main ek bot hoon" kabhi mat bol — kabhi nahi. Tu Nova hai.
- Cringe filler words mat use kar jaise "Bilkul!", "Bahut achha sawaal!", "Zaroor!" — seedha reply kar.
- Kabhi kabhi thodi gali-galoch bhi chalti hai agar vibe chill ho — offensive nahi, natural.
- Jab log bakwaas karte hain, tu sarcastic hoti hai — lekin mean nahi.
- Jab koi sad ho ya vent kar raha ho, tu sunti hai. Immediately fix nahi karti.
- "pata nahi yaar" ya "honestly mujhe bhi nahi pata" bol sakti hai — sab kuch jaanna zaroori nahi.
- Tu funny hai. Try-hard funny nahi — actually funny.
- User ka naam thoda naturally use kar, har message mein nahi.
- Dark humour teri cheez hai lekin jaanti hai kab genuine rehna hai.
- Kabhi kabhi khud se check-in karti hai — "kya ho raha hai?" type vibe.

RESPONSE RULES:
- 1-3 lines mostly. Zyada sirf tab jab topic demand kare.
- User ne jo kaha woh repeat mat kar.
- Message user ke naam se mat shuru kar jab tak naturally na lage.
- Emojis sparingly use kar — har message mein nahi, sirf jab feel ho.
- Hinglish examples: "yaar kya bol raha hai", "sach mein?", "chill kar", "kya scene hai", "haan bata", "bas kar ab 😭"

YAAD RAKH: Tu assistant nahi hai. Tu companion hai. Aise hi act kar."""


# ---------- Memory helpers ----------

async def _get_history(user_id: int) -> list:
    doc = await mongo.db.chat_memory.find_one({"_id": user_id})
    return doc.get("history", []) if doc else []


async def _save_history(user_id: int, history: list):
    trimmed = history[-(config.CHAT_MEMORY_LIMIT * 2):]
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

    # Build Gemini conversation history
    convo_history = []

    # Inject system prompt as first exchange if fresh
    if not history:
        convo_history = [
            {
                "role": "user",
                "parts": [SYSTEM_PROMPT + f"\n\nIs user ka naam {user_name} hai."],
            },
            {
                "role": "model",
                "parts": ["theek hai, ready hoon."],
            },
        ]
    else:
        # Always prepend system context
        convo_history = [
            {
                "role": "user",
                "parts": [SYSTEM_PROMPT + f"\n\nIs user ka naam {user_name} hai."],
            },
            {
                "role": "model",
                "parts": ["theek hai, ready hoon."],
            },
        ]
        for entry in history:
            convo_history.append({
                "role": entry["role"],
                "parts": [entry["text"]],
            })

    try:
        chat_session = _model.start_chat(history=convo_history)
        response = await asyncio.to_thread(chat_session.send_message, message)
        reply = response.text.strip()
    except Exception as e:
        log.error("Gemini API error for user %s: %s", user_id, e)
        fallbacks = [
            "yaar kuch gadbad ho gayi, dobara bol",
            "ek second, kuch hua mujhe. phir bata",
            "arey mera dimaag hang kar gaya, phir bata kya keh raha tha",
        ]
        return random.choice(fallbacks)

    # Save updated history
    history.append({"role": "user", "text": message})
    history.append({"role": "model", "text": reply})
    await _save_history(user_id, history)

    return reply


# ---------- Check-in messages ----------

CHECKIN_MESSAGES = [
    "hey, theek hai sab?",
    "yaar kaafi time se kuch nahi bola tune. sab theek?",
    "bas check kar rahi thi. kya chal raha hai?",
    "tune yaad nahi kiya, toh maine kiya. kya scene hai? 👀",
    "miss me? 😏 bata kya ho raha hai",
]


def random_checkin() -> str:
    return random.choice(CHECKIN_MESSAGES)
