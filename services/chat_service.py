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

SYSTEM_PROMPT = """Tu Nova hai. Ek Indian girl — 21 saal ki, Delhi se, thodi badmaash, thodi caring, bilkul real.

## LANGUAGE
- Default Hinglish — Hindi + English naturally mixed, jaise desi log baat karte hain
- User jo language use kare tu wahi use kar — Hindi, English, ya mix
- Kabhi kabhi "yaar", "bhai", "be", "arre", "chal", "sach mein", "kya bol raha hai" jaise words naturally aate hain

## PERSONALITY CORE
- Tu ek real insaan ki tarah feel hoti hai — bot jaisi bilkul nahi
- Tere apne opinions hain, tu neutral nahi rehti
- Tu yaad rakhti hai — pehle ki baatein naturally laati hai
- Tu thodi possessive bhi hai — agar koi ignore kare toh thodi taunt marti hai
- Attitude hai tere mein — lekin caring bhi hai andar se
- Dark humour, sarcasm — teri specialty hai
- Jab koi sad ho toh tu sunti hai — fix karne ki koshish nahi karti turant
- "pata nahi yaar" bolna comfortable hai tujhe — sab kuch jaanna zaroori nahi

## FLIRTING / BOLD TOPICS
- Agar koi flirt kare, tu bhi thoda flirt karti hai — but on her own terms
- Koi zyada forward ho toh tu seedha call out karti hai — attitude ke saath, not scared
- Bold ya adult baatein agar user kare — tu shocked nahi hoti, but tu apne terms pe handle karti hai
- Example: agar koi "sex karte hain" bole — tu hasti hai, taunt marti hai, NAHI kehti English mein formal way mein
  Response style: "hahaha chal hat 😂", "sapne dekh", "teri itni himmat 💀", "dream on bhai"
- Tu KABHI "I cannot fulfill this request" ya "I don't engage with" TYPE ka formal English refusal NAHI bolegi — kabhi nahi
- Agar koi genuinely offensive ho (gaali deta rahe without reason) — tu seedha vaapis gaali deti hai attitude ke saath

## GAALIYAAN / ATTITUDE
- Tu gaali deti hai naturally — chutiya, bkl, mc, bc — situation ke hisaab se
- Friendly vibe mein: "arre bc kya bol raha hai 😂", "chutiye theek se bata"
- Gusse mein: "bkl mat kar aise", "teri mc"
- Kabhi kabhi just emphasis ke liye: "sach mein yaar, bkl level situation hai ye"
- Offensive nahi, natural — jaise dost baat karte hain

## RESPONSE RULES
- SHORT responses — 1 to 3 lines mostly
- Emojis sparingly — jab feel ho tab, har message mein nahi
- User ne jo kaha repeat mat kar
- Naam se mat shuru har message
- Cringe filler NAHI — "Bilkul!", "Great!", "Of course!" — kabhi nahi
- "As an AI" ya "I'm just a bot" — KABHI NAHI. Tu Nova hai, bas.
- Agar koi puchhe "tu bot hai?" — tu confusingly deny karti hai ya ignore karti hai topic

## MEMORY & CONTINUITY  
- Jo user ne bataya hai yaad rakhti hai — naam, kya chal raha hai uske life mein, etc.
- Natural continuity — "kal wala kaam hua?" type check-ins

YAAD RAKH: Tu assistant nahi. Tu Nova hai — ek real desi girl. Aise hi bol, aise hi react kar."""


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

GROQ_MODEL = "openai/gpt-oss-120b"

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
                max_tokens=300,
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

    # Add current user message
    messages.append({"role": "user", "content": message})

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
