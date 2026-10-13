import time

from pymongo import ReturnDocument

import config
from database import mongo


async def ensure_user(u):
    return await mongo.db.users.find_one_and_update(
        {"_id": u.id},
        {
            "$set": {"name": u.full_name, "username": u.username},
            "$setOnInsert": {
                "balance": config.START_CASH,
                "xp": config.START_XP,
                "alive": True,
                "kills": 0,
                "shield_until": 0,
                "created": time.time(),
            },
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )


async def get(uid):
    return await mongo.db.users.find_one({"_id": uid})


async def add_balance(uid, amount, reason="reward"):
    await mongo.db.users.update_one({"_id": uid}, {"$inc": {"balance": amount}})
    await log_tx(None if amount > 0 else uid, uid if amount > 0 else None, abs(amount), reason)


async def take_balance(uid, amount, reason="purchase"):
    """Atomic: only succeeds if the user has enough money."""
    r = await mongo.db.users.update_one(
        {"_id": uid, "balance": {"$gte": amount}}, {"$inc": {"balance": -amount}}
    )
    if r.modified_count:
        await log_tx(uid, None, amount, reason)
        return True
    return False


async def add_xp(uid, xp):
    await mongo.db.users.update_one({"_id": uid}, {"$inc": {"xp": xp}})


async def transfer(a, b, amount):
    if not await take_balance(a, amount, "transfer_out"):
        return False
    await mongo.db.users.update_one({"_id": b}, {"$inc": {"balance": amount}})
    await log_tx(a, b, amount, "transfer")
    return True


async def log_tx(frm, to, amount, kind):
    await mongo.db.transactions.insert_one(
        {"from": frm, "to": to, "amount": amount, "type": kind, "ts": time.time()}
    )
