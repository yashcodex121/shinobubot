import os
from dotenv import load_dotenv

load_dotenv()


def _ids(name):
    return {int(x) for x in os.getenv(name, "").replace(" ", "").split(",") if x.isdigit()}


def _keys(name):
    """Parse comma-separated API keys from env. Also checks singular form."""
    raw = os.getenv(name) or os.getenv(name.rstrip("S")) or ""
    return [k.strip() for k in raw.split(",") if k.strip()]


BOT_TOKEN = os.getenv("BOT_TOKEN", "")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "nova_bot")
OWNER_IDS = _ids("OWNER_IDS")
ADMIN_IDS = _ids("ADMIN_IDS") | OWNER_IDS

# ---- Chat / AI ----
GROQ_API_KEYS = _keys("GROQ_API_KEYS")   # comma-separated, supports multiple keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")  # fallback if Groq fails
CHAT_MEMORY_LIMIT = 20        # messages to keep per user
CHAT_TYPING_DELAY = 1.0       # seconds to simulate typing

# ---- Economy (owner configurable) ----
START_CASH = 1000
START_XP = 0
DAILY_REWARD = 500
DAILY_COOLDOWN = 24 * 3600
GIVE_COOLDOWN = 5

# ---- Actions ----
ROB_COOLDOWN = 300
ROB_SUCCESS = 0.65       # 65% success, 35% caught
ROB_MAX = 5000
KILL_COOLDOWN = 600
KILL_SUCCESS = 0.60      # 60% success
KILL_MIN_BOUNTY = 100
KILL_LOOT_PCT = 0.10
SHIELD_COST = 1000
SHIELD_HOURS = 24
REVIVE_COST = 300

# ---- Romance ----
PROPOSAL_TTL = 300

# ---- Games ----
GAME_REWARD_MIN = 50
GAME_REWARD_MAX = 150
MINES_COUNT = 5
MINES_EDGE = 0.97
MINES_MIN_BET = 10
WORD_ROUND_SECONDS = 60
