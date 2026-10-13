from keyboards.ui import BLUE, GREEN, RED, btn, kb


def start_menu(bot_username):
    return kb([
        [btn("💀 Chat With Me", "chat:start")],
        [btn("💝 Help & Commands", "help:main")],
        [
            btn("👥 Updates", url="https://t.me/NovaUpdates"),
            btn("🔧 Support", url="https://t.me/NovaSupport"),
        ],
        [btn("🟢 Add me to your group", url=f"https://t.me/{bot_username}?startgroup=true")],
    ])
