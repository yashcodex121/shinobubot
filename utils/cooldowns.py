import time

from pymongo.errors import DuplicateKeyError

from database import mongo


async def hit(uid, key, seconds):
    """Returns 0 if allowed (and starts cooldown), else seconds remaining. Atomic."""
    now = time.time()
    _id = f"{uid}:{key}"
    col = mongo.db.cooldowns
    r = await col.find_one_and_update(
        {"_id": _id, "until": {"$lte": now}}, {"$set": {"until": now + seconds}}
    )
    if r:
        return 0
    try:
        await col.insert_one({"_id": _id, "until": now + seconds})
        return 0
    except DuplicateKeyError:
        doc = await col.find_one({"_id": _id})
        return max(1, int(doc["until"] - now))


def fmt(sec):
    h, r = divmod(int(sec), 3600)
    m, s = divmod(r, 60)
    return " ".join(p for p in (f"{h}h" if h else "", f"{m}m" if m else "", f"{s}s" if s or not (h or m) else "") if p)
