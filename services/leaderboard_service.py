from database import mongo


async def top(field, n=10):
    return await mongo.db.users.find({field: {"$gt": 0}}).sort(field, -1).limit(n).to_list(n)
