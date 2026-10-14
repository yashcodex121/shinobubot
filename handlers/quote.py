"""/q — turn a replied message into a quote-card sticker (avatar + name + text)."""
import io

from PIL import Image, ImageDraw, ImageFont
from telegram.ext import CommandHandler

W = H = 512
CARD = (23, 33, 43, 255)        # dark card background (matches the example)
ACCENT = (136, 175, 255, 255)   # name colour / fallback avatar
WHITE = (255, 255, 255, 255)

# (bold, regular) pairs, first existing wins — DejaVu on the VPS/Linux, Arial on Windows/macOS
_FONT_PAIRS = [
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ("C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf"),
    ("/System/Library/Fonts/Supplemental/Arial Bold.ttf",
     "/System/Library/Fonts/Supplemental/Arial.ttf"),
]


def _fonts():
    for bold, regular in _FONT_PAIRS:
        try:
            return ImageFont.truetype(bold, 30), ImageFont.truetype(regular, 34)
        except OSError:
            continue
    return ImageFont.load_default(), ImageFont.load_default()


_NAME_F, _TEXT_F = _fonts()


def _renderable(text, font):
    """Drop characters the font cannot draw (emoji etc.):
    blank-notdef fonts (Arial) render them invisibly, box-notdef fonts
    (DejaVu) draw tofu — strip either way, but keep whitespace."""
    try:
        notdef = bytes(font.getmask("\ue010"))
        has_notdef = any(notdef)
        out = []
        for ch in text:
            if ch.isspace():
                out.append(ch)
                continue
            m = bytes(font.getmask(ch))
            if has_notdef and m == notdef:       # font draws a box for it
                continue
            if not any(m) and ord(ch) > 0x2000:  # invisible: missing glyph
                continue
            out.append(ch)
        return "".join(out)
    except Exception:
        return text


def _wrap(text, font, max_w):
    """Greedy word wrap; hard-break words wider than the line."""
    draw = ImageDraw.Draw(Image.new("L", (8, 8)))
    lines, line = [], ""
    for word in text.split():
        probe = f"{line} {word}".strip()
        if draw.textlength(probe, font=font) <= max_w:
            line = probe
            continue
        if line:
            lines.append(line)
            line = ""
        while draw.textlength(word, font=font) > max_w:
            cut = len(word)
            while cut > 1 and draw.textlength(word[:cut], font=font) > max_w:
                cut -= 1
            lines.append(word[:cut])
            word = word[cut:]
        line = word
    if line:
        lines.append(line)
    return lines


def _circle_avatar(data: bytes, size=96):
    """Circular-crop a downloaded profile photo; returns RGBA or None."""
    try:
        img = Image.open(io.BytesIO(data)).convert("RGBA")
        side = min(img.size)
        img = img.crop(((img.width - side) // 2, (img.height - side) // 2,
                        (img.width + side) // 2, (img.height + side) // 2)).resize((size, size))
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
        img.putalpha(mask)
        return img
    except Exception:
        return None


def _fallback_avatar(name: str, size=96):
    av = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(av)
    d.ellipse((0, 0, size, size), fill=ACCENT)
    letter = (name.strip() or "?")[0].upper()
    f = _NAME_F
    for bold, _ in _FONT_PAIRS:            # 44px bold letter, first font that exists
        try:
            f = ImageFont.truetype(bold, 44)
            break
        except OSError:
            continue
    bb = d.textbbox((0, 0), letter, font=f)
    d.text(((size - (bb[2] - bb[0])) // 2 - bb[0], (size - (bb[3] - bb[1])) // 2 - bb[1]),
           letter, font=f, fill=WHITE)
    return av


def _quote_png(name: str, text: str, avatar: bytes = None) -> io.BytesIO:
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle((0, 0, W - 1, H - 1), radius=40, fill=CARD)

    av = _circle_avatar(avatar) if avatar else None
    if av is None:
        av = _fallback_avatar(name)
    canvas.paste(av, (32, 32), av)

    name = _renderable(name, _NAME_F)
    full = name
    max_name_px = W - 32 - 148 - 8
    while name and d.textlength(name, font=_NAME_F) > max_name_px:
        name = name[:-1]
    if name != full:
        name += "…"
    d.text((148, 56), name, font=_NAME_F, fill=ACCENT)

    body = _renderable(text, _TEXT_F)
    lines = _wrap(body, _TEXT_F, W - 64)
    max_lines = 7
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip("…") + "…"
    y = 168
    for ln in lines:
        d.text((32, y), ln, font=_TEXT_F, fill=WHITE)
        y += 44

    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    buf.seek(0)
    buf.name = "quote.png"
    return buf


async def quote(update, ctx):
    """Reply to a message with /q to turn it into a quote-card sticker."""
    msg = update.effective_message
    r = msg.reply_to_message
    if not r:
        return await msg.reply_text("Usage: reply to a message with /q to make it a quote sticker.")
    src = r.from_user or getattr(r, "sender_chat", None)
    name = getattr(src, "full_name", None) or getattr(src, "title", None) or "Anonymous"
    text = (r.text or r.caption or "").strip()
    if not text:
        return await msg.reply_text("Only text messages can be quoted.")
    avatar = None
    uid = getattr(src, "id", None)
    if uid and not getattr(src, "is_bot", False):
        try:
            photos = await ctx.bot.get_user_profile_photos(uid, limit=1)
            if photos.total_count:
                f = await ctx.bot.get_file(photos.photos[0][-1].file_id)
                avatar = bytes(await f.download_as_bytearray())
        except Exception:
            avatar = None
    await msg.reply_sticker(sticker=_quote_png(name, text, avatar))


def register(app):
    app.add_handler(CommandHandler(["q", "quote"], quote))
