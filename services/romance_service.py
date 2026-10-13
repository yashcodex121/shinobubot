from database import mongo


async def active_marriage(uid):
    return await mongo.db.marriages.find_one(
        {"status": "active", "$or": [{"a": uid}, {"b": uid}]})


def partner_of(m, uid):
    return m["b"] if m["a"] == uid else m["a"]
