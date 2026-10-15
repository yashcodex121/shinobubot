from motor.motor_asyncio import AsyncIOMotorClient

import config

client = None
db = None


async def init():
    global client, db
    client = AsyncIOMotorClient(config.MONGO_URI)
    db = client[config.DB_NAME]
    await db.users.create_index("balance")
    await db.users.create_index("xp")
    await db.users.create_index("kills")
    await db.marriages.create_index([("a", 1), ("status", 1)])
    await db.marriages.create_index([("b", 1), ("status", 1)])
    await db.group_members.create_index([("chat", 1), ("uid", 1)], unique=True)
    await db.file_ids.create_index("n", unique=True)  # numeric file-id codes
