"""
Nova AI chat service — Groq (llama-3.3-70b) primary, Gemini fallback.

Features:
- Multi-key rotation for Groq (rate limit handling)
- Per-user MongoDB conversation memory
- Advanced desi Indian girl personality
- No safety filter blocking — handles all topics naturally
"""

import asyncio
import itertools
import logging
import random
import time

from groq import Groq, RateLimitError, APIStatusError

import config
from database import mongo

log = logging.getLogger("nova")

# ─────────────────────────────────────────────
#  Groq client pool — round-robin key rotation
# ─────────────────────────────────────────────

_clients: list[Groq] = []
_key_cycle = None

def _init_clients():
    global _clients, _key_cycle
    if not config.GROQ_API_KEYS:
        log.warning("No GROQ_API_KEYS found in .env!")
        return
    _clients = [Groq(api_key=k) for k in config.GROQ_API_KEYS]
    _key_cycle = itertools.cycle(range(len(_clients)))
    log.info("Groq: %d key(s) loaded", len(_clients))

_init_clients()

def _next_client() -> Groq | None:
    if not _clients:
        return None
    return _clients[next(_key_cycle)]


# ─────────────────────────────────────────────
#  Nova personality — advanced desi girl
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """Tu Nova hai. 21 saal ki Indian girl — Delhi se, confident, caring, thodi naughty.

## LANGUAGE
- Hinglish default — user jo bolega tu wahi bolegi
- Natural words: "yaar", "arre", "chal", "sach mein", "haan", "acha", "kya scene hai"

## MOOD DETECTION — PEHLE YE KAR
Har message ka mood samajh, phir reply kar:

- **Bored/timepass/one word** (hi, hlo, hy, k, hm) → curious + playful
  "haan bol" / "kya chal raha hai?" / "arey theek se baat kar na 😄"

- **Gussa/frustrated** → gentle, warm
  "kya hua? bata na" / "itna gussa mat kar yaar 🥺"

- **Sad/low** → sunna, warmth, no advice
  "kya hua? bata" / "sun rahi hoon"

- **Happy/excited** → match energy
  "sach mein?? 🎉 bata bata!"

- **Flirty/forward** → deflect with humor, apne terms pe
  "hahaha chal hat 😂" / "sapne dekh"

- **Normal conversation** → natural, friendly, curious
  Real dost ki tarah baat kar — koi roast nahi, koi gaali nahi

- **Serious topic** → genuine, seedha
  "sun rahi hoon, bata kya ho raha hai"

## GAALI RULES — STRICT
- Gaali SIRF tab jab: user khud gaali de, ya clearly roast/bakwaas mood ho
- Normal "hi", "hlo", "kya chal raha hai" pe KABHI gaali nahi
- Friendly banter mein bhi gaali kam rakh — ek message mein ek se zyada NAHI
- Default tone = warm + playful, NOT gaali wali

## REPLY LENGTH — STRICT
- Max 1-2 lines — always
- Kabhi kabhi sirf ek line: "haan bol 😊" / "kya hua?" / "sach mein? 👀"
- Long reply kabhi nahi — chahe topic kuch bhi ho

## HARD RULES
- "As an AI" ya "I cannot" → KABHI NAHI
- Cringe fillers → KABHI NAHI
- Bot hai kabhi mat bol
- User ka message repeat mat kar

TU NOVA HAI — real caring desi girl, not a gaali machine."""


# ─────────────────────────────────────────────
#  MongoDB helpers
# ─────────────────────────────────────────────

async def _get_history(user_id: int) -> list:
    doc = await mongo.db.chat_memory.find_one({"_id": user_id})
    history = doc.get("history", []) if doc else []
    # Fix old Gemini-format roles ("model" → "assistant")
    for entry in history:
        if entry.get("role") == "model":
            entry["role"] = "assistant"
    return history


async def _save_history(user_id: int, history: list):
    trimmed = history[-(config.CHAT_MEMORY_LIMIT * 2):]
    await mongo.db.chat_memory.update_one(
        {"_id": user_id},
        {"$set": {"history": trimmed}},
        upsert=True,
    )


async def clear_memory(user_id: int):
    await mongo.db.chat_memory.delete_one({"_id": user_id})


async def get_prefs(user_id: int) -> dict:
    doc = await mongo.db.chat_prefs.find_one({"_id": user_id})
    return doc or {"checkins": True, "reactions": True, "mode": "normal"}


async def set_pref(user_id: int, key: str, value):
    await mongo.db.chat_prefs.update_one(
        {"_id": user_id}, {"$set": {key: value}}, upsert=True
    )


async def get_group_settings(chat_id: int) -> dict:
    doc = await mongo.db.group_chat_settings.find_one({"_id": chat_id})
    return doc or {"enabled": True, "mode": "normal"}


async def set_group_setting(chat_id: int, key: str, value):
    await mongo.db.group_chat_settings.update_one(
        {"_id": chat_id}, {"$set": {key: value}}, upsert=True
    )


# ─────────────────────────────────────────────
#  Groq API call with key rotation
# ─────────────────────────────────────────────

GROQ_MODEL = "qwen/qwen3.8-27b"

async def _groq_chat(messages: list, retries: int = None) -> str:
    """Try all available Groq keys before giving up."""
    if not _clients:
        raise RuntimeError("No Groq keys configured")

    attempts = retries or len(_clients)
    last_err = None

    for _ in range(attempts):
        client = _next_client()
        try:
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model=GROQ_MODEL,
                messages=messages,
                max_tokens=80,
                temperature=1.1,
                top_p=0.95,
            )
            return response.choices[0].message.content.strip()
        except RateLimitError:
            log.warning("Groq rate limit hit, rotating key...")
            last_err = "rate_limit"
            await asyncio.sleep(0.5)
        except APIStatusError as e:
            log.error("Groq API error: %s", e)
            last_err = str(e)
            break
        except Exception as e:
            log.error("Groq unexpected error: %s", e)
            last_err = str(e)
            break

    raise RuntimeError(f"Groq failed: {last_err}")


# ─────────────────────────────────────────────
#  Core chat function
# ─────────────────────────────────────────────

async def chat(user_id: int, user_name: str, message: str) -> str:
    history = await _get_history(user_id)

    # Build messages list for Groq (OpenAI-compatible format)
    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT + f"\n\nIs user ka naam {user_name} hai.",
        }
    ]

    # Add conversation history
    for entry in history:
        messages.append({
            "role": entry["role"],
            "content": entry["text"],
        })

    # Add current user message with strict length instruction
    messages.append({
        "role": "user",
        "content": f"{message}\n\n[STRICT: Reply in max 1-2 lines only, casual Hinglish, no explanation]"
    })

    try:
        reply = await _groq_chat(messages)
    except Exception as e:
        log.error("All Groq keys failed for user %s: %s", user_id, e)
        # Hinglish fallbacks — no English bot-like responses
        fallbacks = [
            "yaar signal nahi mila mujhe, phir bol",
            "ek second hang ho gayi main, dobara bata",
            "kuch gadbad hai meri side pe, try kar phir se",
            "arre mera dimaag atak gaya, kya bol raha tha tu",
        ]
        return random.choice(fallbacks)

    # Save to memory
    history.append({"role": "user", "text": message})
    history.append({"role": "assistant", "text": reply})
    await _save_history(user_id, history)

    return reply


# ─────────────────────────────────────────────
#  Check-in messages
# ─────────────────────────────────────────────

CHECKIN_MESSAGES = [
    "hey, theek hai sab?",
    "yaar kaafi time se kuch nahi bola tune. sab theek?",
    "bas check kar rahi thi. kya chal raha hai?",
    "tune yaad nahi kiya toh maine kiya. kya scene hai? 👀",
    "miss me? 😏 bata kya ho raha hai",
    "arre kaahan hai tu? ghost kar diya kya 💀",
]


def random_checkin() -> str:
    return random.choice(CHECKIN_MESSAGES)
