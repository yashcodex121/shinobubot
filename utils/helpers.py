"""Shared utility helpers."""
from telegram.error import BadRequest


async def safe_answer(q, text=None, show_alert=False):
    """Answer a callback query, silently ignoring expired/invalid query errors."""
    try:
        if text:
            await q.answer(text, show_alert=show_alert)
        else:
            await q.answer()
    except BadRequest:
        pass
