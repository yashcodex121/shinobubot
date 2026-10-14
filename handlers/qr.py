"""Text → QR code sticker: /qr <text> (or reply to a message with /qr)."""
import io

import qrcode
from PIL import Image
from telegram.ext import CommandHandler

STICKER_PX = 512  # Telegram sticker canvas (single side must be 512)


def _qr_png(data: str) -> io.BytesIO:
    """QR-encode data and return a 512x512 PNG buffer (Telegram sticker size)."""
    qr = qrcode.QRCode(border=2, box_size=1)
    qr.add_data(data)
    qr.make(fit=True)
    total = qr.modules_count + 2 * qr.border          # rendered size in modules
    qr.box_size = max(1, (STICKER_PX - 48) // total)  # fit with margin, integer scale
    out = qr.make_image(fill_color="black", back_color="white")
    img = getattr(out, "image", None) or out.get_image()
    img = img.convert("RGB")
    canvas = Image.new("RGB", (STICKER_PX, STICKER_PX), "white")
    canvas.paste(img, ((STICKER_PX - img.width) // 2, (STICKER_PX - img.height) // 2))
    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    buf.seek(0)
    buf.name = "qr.png"
    return buf


async def qr(update, ctx):
    """Make a QR sticker from text — pass it as args or reply to a message."""
    msg = update.effective_message
    text = " ".join(ctx.args).strip()
    if not text and msg.reply_to_message:
        text = (msg.reply_to_message.text or msg.reply_to_message.caption or "").strip()
    if not text:
        return await msg.reply_text(
            "Usage: /qr <text>\nOr reply to a message with /qr to turn its text into a QR sticker.")
    try:
        buf = _qr_png(text)
    except Exception:
        return await msg.reply_text("❌ That text is too long for a QR code.")
    await msg.reply_sticker(sticker=buf)


def register(app):
    app.add_handler(CommandHandler("qr", qr))
