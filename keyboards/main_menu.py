from keyboards.ui import BLUE, GREEN, RED, btn, kb


def start_menu(bot_username):
    return kb([
        [btn("💞 Help & Commands", "help:main", BLUE)],
        [btn("➕ Add me to your group", url=f"https://t.me/{bot_username}?startgroup=true", style=GREEN)],
        [btn("🎮 Games", "help:games", RED), btn("💰 Economy", "help:economy", GREEN)],
    ])
