"""/q — turn a replied message into a quote-card sticker (avatar + name + text)."""
import io

from PIL import Image, ImageDraw, ImageFont
from telegram.ext import CommandHandler

W = 512                          # sticker side that must stay exactly 512
HMAX = 512
TEXT_C = (38, 38, 54, 255)       # dark text reads on the pale holo card
NAME_C = (106, 66, 186, 255)     # deep purple name
WHITE = (255, 255, 255, 255)
# holographic pastel stops (pink -> lilac -> sky -> mint -> cream)
HOLO = [(255, 178, 221), (214, 178, 255), (173, 216, 255), (174, 255, 234), (255, 240, 199)]

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


def _holo_bg(w, h):
    """Iridescent pastel gradient (holographic look), blended across width."""
    stops = len(HOLO) - 1
    row = []
    for x in range(w):
        t = x / max(1, w - 1) * stops
        i = min(int(t), stops - 1)
        f = t - i
        a, b = HOLO[i], HOLO[i + 1]
        row.append(tuple(int(a[c] + (b[c] - a[c]) * f) for c in range(3)))
    base = Image.new("RGB", (w, 1))
    base.putdata(row)
    return base.resize((w, h))


def _fallback_avatar(name: str, size=72):
    av = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(av)
    d.ellipse((0, 0, size, size), fill=WHITE)
    letter = (name.strip() or "?")[0].upper()
    f = _NAME_F
    for bold, _ in _FONT_PAIRS:            # ~46% of the circle, first font that exists
        try:
            f = ImageFont.truetype(bold, max(18, int(size * 0.46)))
            break
        except OSError:
            continue
    bb = d.textbbox((0, 0), letter, font=f)
    d.text(((size - (bb[2] - bb[0])) // 2 - bb[0], (size - (bb[3] - bb[1])) // 2 - bb[1]),
           letter, font=f, fill=NAME_C)
    return av


def _quote_png(name: str, text: str, avatar: bytes = None) -> io.BytesIO:
    pad, av_size = 28, 72

    name = _renderable(name, _NAME_F)
    max_name_px = W - pad - av_size - 16 - pad
    if _NAME_F.getlength(name) > max_name_px:
        while name and _NAME_F.getlength(name + "…") > max_name_px:  # ellipsis inside the budget
            name = name[:-1]
        name += "…"

    body = _renderable(text, _TEXT_F)
    all_lines = _wrap(body, _TEXT_F, W - 2 * pad)
    lines = all_lines[:7]
    if len(all_lines) > 7:
        lines[-1] = lines[-1].rstrip("…") + "…"

    # adaptive height: hug the content instead of a fixed square
    top = pad + av_size + 24
    h = min(HMAX, max(200, top + len(lines) * 40 + 22))
    canvas = Image.new("RGBA", (W, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)
    mask = Image.new("L", (W, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, W - 1, h - 1), radius=28, fill=255)
    canvas.paste(_holo_bg(W, h), (0, 0), mask)

    av = _circle_avatar(avatar, size=av_size) if avatar else None
    if av is None:
        av = _fallback_avatar(name or "?", size=av_size)
    canvas.paste(av, (pad, pad), av)

    d.text((pad + av_size + 16, pad + 14), name, font=_NAME_F, fill=NAME_C)
    y = top
    for ln in lines:
        d.text((pad, y), ln, font=_TEXT_F, fill=TEXT_C)
        y += 40

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
