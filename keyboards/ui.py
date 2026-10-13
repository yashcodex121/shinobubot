"""Colourful inline buttons.

Telegram Bot API (9.4+) lets every InlineKeyboardButton carry a `style`:
  primary -> blue, success -> green, danger -> red  (None = default grey)
python-telegram-bot forwards unknown fields through `api_kwargs`, so this
works on any recent PTB release.
"""
from itertools import cycle

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

BLUE, GREEN, RED = "primary", "success", "danger"


def btn(text, data=None, style=None, url=None):
    kw = {"api_kwargs": {"style": style}} if style else {}
    if url:
        return InlineKeyboardButton(text, url=url, **kw)
    return InlineKeyboardButton(text, callback_data=data, **kw)


def kb(rows):
    return InlineKeyboardMarkup(rows)


def rainbow():
    return cycle([BLUE, GREEN, RED])
