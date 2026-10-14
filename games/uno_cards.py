"""Render classic-style UNO card PNGs into static/uno/.

Run once after changing the design:
    python3 -m games.uno_cards
Output: static/uno/{r,g,b,y}{0-9,S,R,D2}.png + wW.png + wW4.png (54 files).
Inline results then reference these via raw.githubusercontent.com so the
group message shows the actual card, like @unobot.
"""
import os

from PIL import Image, ImageDraw, ImageFont

W, H = 320, 480
FACE = {"r": (219, 38, 46), "g": (27, 141, 72), "b": (26, 102, 199), "y": (240, 166, 20), "w": (26, 26, 32)}
WHITE = (255, 255, 255)
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "uno")

_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\segoeuib.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def _font(size):
    for p in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _text(d, cx, cy, s, font, color):
    bb = d.textbbox((0, 0), s, font=font)
    d.text((cx - (bb[2] - bb[0]) / 2 - bb[0], cy - (bb[3] - bb[1]) / 2 - bb[1]), s, font=font, fill=color)


def _skip(d, cx, cy, s, color):
    w = max(6, s // 9)
    d.ellipse((cx - s / 2, cy - s / 2, cx + s / 2, cy + s / 2), outline=color, width=w)
    d.line((cx - s / 2 + w, cy + s / 2 - w, cx + s / 2 - w, cy - s / 2 + w), fill=color, width=w)


def _arrow(size, color):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    h = size // 4
    d.rounded_rectangle((size // 10, size // 2 - h // 2, size * 5 // 8, size // 2 + h // 2),
                        radius=h // 2, fill=color)
    d.polygon([(size // 2, size // 2 - h), (size * 7 // 8, size // 2), (size // 2, size // 2 + h)],
              fill=color)
    return im


def _reverse(layer, cx, cy, s, color):
    """Two clean stacked arrows: <- on top, -> below (classic reverse)."""
    a = _arrow(int(s * 1.05), color)
    ah = a.size[1]
    top = a.transpose(Image.FLIP_LEFT_RIGHT)
    layer.paste(top, (int(cx - top.size[0] / 2), int(cy - ah * 1.05)), top)
    layer.paste(a, (int(cx - a.size[0] / 2), int(cy + ah * 0.05)), a)


def _glyph(layer, cx, cy, s, v, color):
    """Draw the card value centred at (cx, cy) with height ~s into `layer`."""
    d = ImageDraw.Draw(layer)
    if v.isdigit():
        _text(d, cx, cy, v, _font(int(s * 1.35)), color)
    elif v == "S":
        _skip(d, cx, cy, s, color)
    elif v == "R":
        _reverse(layer, cx, cy, s, color)
    elif v == "D2":
        _text(d, cx, cy, "+2", _font(int(s * 0.95)), color)
    elif v == "W4":
        _text(d, cx, cy, "+4", _font(int(s * 0.95)), color)
    elif v == "W":
        _text(d, cx, cy, "WILD", _font(int(s * 0.46)), color)


def render(c, v):
    face = FACE[c]
    card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle((2, 2, W - 3, H - 3), radius=44, fill=WHITE, outline=(205, 205, 205), width=3)
    d.rounded_rectangle((16, 16, W - 17, H - 17), radius=34, fill=face)

    if c == "w":  # four-colour quarter discs behind the corners
        q = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        qd = ImageDraw.Draw(q)
        qd.pieslice((-60, -60, 220, 220), 0, 90, fill=FACE["r"])
        qd.pieslice((W - 220, -60, W + 60, 220), 90, 180, fill=FACE["y"])
        qd.pieslice((W - 220, H - 220, W + 60, H + 60), 180, 270, fill=FACE["g"])
        qd.pieslice((-60, H - 220, 220, H + 60), 270, 360, fill=FACE["b"])
        mask = Image.new("L", (W, H), 0)
        ImageDraw.Draw(mask).rounded_rectangle((16, 16, W - 17, H - 17), radius=34, fill=255)
        card.paste(q, (0, 0), Image.composite(q.split()[3], Image.new("L", (W, H), 0), mask))

    # tilted white ellipse with the value
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    od.ellipse((10, 108, W - 10, H - 108), fill=WHITE)
    ov = ov.rotate(-25, resample=Image.BICUBIC, center=(W // 2, H // 2))
    card.paste(ov, (0, 0), ov)
    gl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    _glyph(gl, W // 2, H // 2, 150, v, face if c != "w" else FACE["w"])
    card.paste(gl, (0, 0), gl)

    # corner mini-glyphs (top-left + bottom-right rotated 180°)
    tl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    _glyph(tl, 82, 120, 62, v, WHITE if c != "w" else WHITE)
    card.paste(tl, (0, 0), tl)
    br = tl.rotate(180)
    card.paste(br, (0, 0), br)
    return card


def generate_all():
    os.makedirs(OUT, exist_ok=True)
    n = 0
    for c in "rgby":
        for v in [str(i) for i in range(10)] + ["S", "R", "D2"]:
            render(c, v).save(os.path.join(OUT, f"{c}{v}.png"))
            n += 1
    for v in ("W", "W4"):
        render("w", v).save(os.path.join(OUT, f"w{v}.png"))
        n += 1
    print(f"generated {n} cards -> {OUT}")


if __name__ == "__main__":
    generate_all()
