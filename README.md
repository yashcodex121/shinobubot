# 💞 Nova Bot

Telegram bot: Economy, Actions, Romance, Games, Admin — MongoDB + python-telegram-bot v22.

## Colourful inline buttons
Buttons use Telegram's native `style` field (`primary` blue, `success` green, `danger` red).
See `keyboards/ui.py` → `btn(text, data, style)`. Needs a recent Telegram client; older clients show grey buttons.

## Run
```bash
cp .env.example .env      # fill BOT_TOKEN, OWNER_IDS
pip install -r requirements.txt
python main.py
# or: docker compose up -d --build
```

## Status
| Module | Status |
|---|---|
| Economy, Actions, Romance, Admin | ✅ |
| XOXO, Mines, RPS, Jumble, Wordscramble | ✅ |
| UNO, Ludo, Wordgrid, Wordseek, Charades, Wordchain | 🚧 stub in `games/` (menu page shows "Coming soon") |
| Tap, Crash, Hack, Card, Chess, Scribble, Subway, Bet | 🚧 menu entry only |

To add a game: create `games/<name>.py` with `register(app)`, import it in `handlers/games.py`,
and set its `implemented` flag to `True` in `keyboards/games_menu.py`.
All economy numbers are in `config.py`.
