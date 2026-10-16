import config
from keyboards.ui import BLUE, GREEN, RED, btn, kb


def start_menu(bot_username):
    return kb([
        [btn("💀 Chat With Me", "chat:start", BLUE)],
        [btn("💝 Help & Commands", "help:main", RED)],
        [
            btn("👥 Updates", url=config.UPDATES_CHANNEL, style=GREEN),
            btn("🔧 Support", url=config.SUPPORT_CHANNEL, style=BLUE),
        ],
        [btn("🟢 Add me to your group", url=f"https://t.me/{bot_username}?startgroup=true", style=GREEN)],
    ])
