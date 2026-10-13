from telegram.ext import MessageHandler, filters

from games import (charades, ludo, mines, rps, uno, word_chain, word_grid,
                   word_jumble, word_scrambler, word_seek, xoxo)
from games._wordround import check_answer


def register(app):
    for m in (xoxo, mines, rps, word_jumble, word_scrambler, uno, word_grid, ludo, word_seek, charades, word_chain):
        m.register(app)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, check_answer, block=False), group=2)
