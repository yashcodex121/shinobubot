from database import mongo


async def top_rich(n=10):
    return await mongo.db.users.find().sort("balance", -1).limit(n).to_list(n)


async def xp_rank(uid, xp):
    return await mongo.db.users.count_documents({"xp": {"$gt": xp}}) + 1
