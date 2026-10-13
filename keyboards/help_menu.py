from keyboards.ui import BLUE, GREEN, RED, btn, kb


def help_menu():
    return kb([
        [btn("💀 Chat With Me", "chat:start", BLUE)],
        [btn("🎮 Games", "help:games", BLUE), btn("⚡ Actions", "help:actions", RED)],
        [btn("💰 Economy", "help:economy", GREEN), btn("💗 Romance", "help:romance", RED)],
        [btn("🛡️ Admins", "help:admins", BLUE)],
        [btn("⬅️ Back to Main", "help:start", GREEN)],
    ])


def back_to_help():
    return kb([
        [btn("⬅️ Back to categories", "help:main", BLUE)],
        [btn("🏠 Main Menu", "help:start", GREEN)],
    ])
