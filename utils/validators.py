import html


def mention(u):
    return f'<a href="tg://user?id={u.id}">{html.escape(u.full_name)}</a>'


def mention_doc(doc):
    return f'<a href="tg://user?id={doc["_id"]}">{html.escape(doc.get("name") or "User")}</a>'


def parse_amount(args):
    if not args or not args[0].isdigit():
        return None
    v = int(args[0])
    return v if v > 0 else None


def reply_target(update):
    r = update.effective_message.reply_to_message
    if r and r.from_user and not r.from_user.is_bot:
        return r.from_user
    return None
