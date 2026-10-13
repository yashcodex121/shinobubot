"""Helpers for persisting long-running game sessions (UNO/Ludo) — used when those games are implemented."""
import time

from database import mongo


async def save(game, chat_id, state):
    await mongo.db.game_sessions.update_one(
        {"_id": f"{game}:{chat_id}"}, {"$set": {"state": state, "ts": time.time()}}, upsert=True)


async def load(game, chat_id):
    d = await mongo.db.game_sessions.find_one({"_id": f"{game}:{chat_id}"})
    return d["state"] if d else None


async def cleanup(max_age=3600):
    await mongo.db.game_sessions.delete_many({"ts": {"$lt": time.time() - max_age}})
