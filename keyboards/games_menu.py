from keyboards.ui import RED, btn, kb, rainbow

# key, label, how-to, commands, implemented?
GAMES = [
    ("uno", "🃏 UNO", "Multiplayer card game. /new opens a lobby, others /join, creator /start (2+ players). Play by typing the bot's @username inline — tap your cards, draw, or ? for game state. /leave to quit · /skip after 90s · /notify_me for new-game alerts · creator: /close /open /kick /kill /enable_translations /disable_translations", "/new", True),
    ("mines", "💣 Mines", "Reveal safe tiles to grow your multiplier. Hit a mine and you lose the bet. Cash out anytime.", "/mines &lt;bet&gt;", True),
    ("rps", "🪨 RPS", "Rock-Paper-Scissors against the bot.", "/rps", True),
    ("wordseek", "🔎 Wordseek", "A word-guessing game (like Wordle). Guess the hidden word by typing it in chat!\n\n/wordseek or /ws — Start a 5-letter game.\n/ws4 or /ws6 — Start a 4-letter or 6-letter game.\n/end — End any active game.", "/wordseek or /ws", True),
    ("wordgrid", "🔢 Wordgrid", "Find as many words as you can in a letter grid before time runs out.", "/wordgrid", False),
    ("tap", "⚡ Tap", "Tap faster than everyone else.", "/tap", False),
    ("crash", "💥 Crash", "Cash out before the multiplier crashes.", "/crash &lt;bet&gt;", False),
    ("jumble", "🔤 Jumble", "Unscramble the word. Hints &amp; difficulty levels available.", "/jumble [easy|hard]", True),
    ("charades", "🎭 Charades", "Act out a secret word; others guess in chat.", "/charades", False),
    ("wordchain", "🔗 Wordchain", "Each word must start with the last letter of the previous word.", "/wordchain", False),
    ("wordscramble", "🔀 Wordscramble", "First to unscramble the letters wins the round.", "/scramble", True),
    ("hack", "💻 Hack", "Hack another player's wallet mini-game.", "/hack", False),
    ("card", "🂡 Card", "High/low card guessing game.", "/card &lt;bet&gt;", False),
    ("chess", "♟️ Chess", "Classic chess duel.", "/chess", False),
    ("scribble", "🖌️ Scribble", "Draw &amp; guess.", "/scribble", False),
    ("subway", "🏃 Subway", "Endless runner with inline controls.", "/subway", False),
    ("bet", "🎰 Bet", "Bet your coins on a coin flip.", "/bet &lt;amount&gt;", False),
    ("xoxo", "❌⭕ XOXO", "Tic-Tac-Toe. Reply to a user's message with /xoxo to challenge them.", "/xoxo", True),
    ("ludo", "🎲 Ludo", "Classic dice board game for up to 4 players.", "/ludo", False),
]
GAME_MAP = {g[0]: g for g in GAMES}


def games_menu():
    col = rainbow()
    rows, row = [], []
    for key, label, *_ in GAMES:
        row.append(btn(label, f"g:{key}", next(col)))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([btn("⬅️ Back to categories", "help:main", RED)])
    return kb(rows)


def game_page_menu():
    return kb([[btn("⬅️ Back to games", "help:games", RED)]])
