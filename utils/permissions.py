import config
from database import mongo


async def is_admin(uid):
    if uid in config.ADMIN_IDS:
        return True
    return bool(await mongo.db.admins.find_one({"_id": uid}))


def is_owner(uid):
    return uid in config.OWNER_IDS
