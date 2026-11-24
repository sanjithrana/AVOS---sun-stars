"""Designed callouts instead of emoji: bold word badges, tags and bursts drawn here with a bundled font (Poppins, OFL), in a small set of palettes.

A sticker is {"kind", "text", "color"}; the picture is drawn once and cached by those three values, so a clip can be re-rendered without redrawing."""
from __future__ import annotations

import hashlib
from pathlib import Path

from . import store

FONT = Path(__file__).parent / "assets" / "fonts" / "Poppins-Bold.ttf"
PALETTES = {
    "sun": ("#FFD60A", "#111111"),      # yellow, black text
    "hot": ("#FF2D55", "#FFFFFF"),      # red-pink, white text
    "ice": ("#00D4FF", "#06202B"),      # cyan
    "lime": ("#B6FF3B", "#0B1A00"),     # lime
    "snow": ("#FFFFFF", "#111111"),     # white
}
KINDS = ("pill", "tag", "burst", "outline")
# what the speaker says -> what the callout says. Short, upper case, the kind of word an editor would pop on screen.
LABELS = {
    "$$$": "money cash rich dollar dollars paisa profit income salary crore lakh million billion", "INSANE": "crazy insane unreal mad unbelievable pagal",
    "WOW!": "wow omg whoa shocked shock suddenly", "SECRET": "secret hidden truth exposed", "NEVER": "never nobody", "WINNER": "win won winner champion victory trophy",
    "THE BEST": "best greatest legend goat", "PRO TIP": "tip trick hack lesson learn", "WARNING": "warning careful danger risk beware", "WAIT FOR IT": "wait watch",
    "LOL": "funny lol laugh laughing hilarious haha joke", "FREE": "free", "NEW": "new latest", "#1": "first number-one", "FAIL": "fail failed mistake wrong",
    "FAST": "fast quick speed rocket", "BIG": "huge massive giant big", "LIVE": "live", "HARD": "hard difficult impossible tough", "LEVEL UP": "level upgrade grow growth",
    "REAL": "real actually honestly", "BOOM": "boom explosion blast bomb", "GOAL!": "goal", "CLUTCH": "clutch ace headshot",
}
_W2L = {w: lab for lab, ws in LABELS.items() for w in ws.split()}


def label_for(word: str) -> str | None:
    return _W2L.get(word)


def _hex(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def path_for(sp: dict, width: int) -> Path:
    key = hashlib.md5(f"{sp['kind']}|{sp['text']}|{sp['color']}|{width}".encode()).hexdigest()[:14]
    return store.ROOT / "cache" / "stickers" / f"{key}.png"


def ensure(sp: dict, width: int) -> Path:
    """The PNG for one sticker, drawn if it is not cached yet. `width` is the clip's width: stickers are about 40% of it."""
    p = path_for(sp, width)
    if p.is_file():
        return p
    p.parent.mkdir(parents=True, exist_ok=True)
    img = draw(sp["kind"], sp["text"], sp["color"], int(width * 0.4))
    tmp = p.with_suffix(".tmp.png")
    img.save(tmp)
    tmp.replace(p)
    return p


def draw(kind: str, text: str, color: str, target_w: int):
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    import math
    fill, ink = PALETTES.get(color, PALETTES["sun"])
    S = 3                                                    # draw 3x and shrink: smooth edges
    fs = 96 * S
    font = ImageFont.truetype(str(FONT), fs)
    text = text.upper()
    d0 = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    l, t, r, b = d0.textbbox((0, 0), text, font=font)
    tw, th = r - l, b - t
    pad_x, pad_y = int(fs * 0.55), int(fs * 0.34)
    if kind == "burst":
        side = int(max(tw * 1.3, th * 2.3))
        W = H = side + 80 * S
    else:
        W, H = tw + 2 * pad_x + 80 * S, th + 2 * pad_y + 80 * S
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cx, cy = W // 2, H // 2
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    dr = ImageDraw.Draw(img)
    if kind == "burst":
        pts = []
        rad = side / 2
        for i in range(32):
            a = math.pi * 2 * i / 32 - math.pi / 2
            rr = rad if i % 2 == 0 else rad * 0.78
            pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
        sd.polygon([(x + 10 * S, y + 12 * S) for x, y in pts], fill=(0, 0, 0, 150))
        dr.polygon(pts, fill=_hex(fill) + (255,), outline=(17, 17, 17, 255))
        dr.polygon(pts, outline=(17, 17, 17, 255), width=5 * S)
        dr.text((cx - tw / 2 - l, cy - th / 2 - t), text, font=font, fill=_hex(ink))
    elif kind == "tag":
        x0, y0, x1, y1 = cx - tw // 2 - pad_x, cy - th // 2 - pad_y, cx + tw // 2 + pad_x, cy + th // 2 + pad_y
        sd.rounded_rectangle((x0 + 8 * S, y0 + 10 * S, x1 + 8 * S, y1 + 10 * S), radius=int(fs * 0.16), fill=(0, 0, 0, 150))
        dr.rounded_rectangle((x0, y0, x1, y1), radius=int(fs * 0.16), fill=_hex(fill) + (255,))
        dr.rectangle((x0, y0, x0 + int(fs * 0.16), y1), fill=(17, 17, 17, 255))            # a dark spine on the left, like a label
        dr.text((cx - tw / 2 - l + fs * 0.06, cy - th / 2 - t), text, font=font, fill=_hex(ink))
    elif kind == "outline":
        for dx, dy in ((10, 12),):
            sd.text((cx - tw / 2 - l + dx * S, cy - th / 2 - t + dy * S), text, font=font, fill=(0, 0, 0, 170), stroke_width=int(fs * 0.12), stroke_fill=(0, 0, 0, 170))
        dr.text((cx - tw / 2 - l, cy - th / 2 - t), text, font=font, fill=(255, 255, 255, 255), stroke_width=int(fs * 0.12), stroke_fill=(17, 17, 17, 255))
        uy = cy + th // 2 + int(fs * 0.22)                                              # an accent underline
        dr.rounded_rectangle((cx - tw // 2, uy, cx + tw // 2, uy + int(fs * 0.12)), radius=int(fs * 0.06), fill=_hex(fill) + (255,))
    else:                                                                                # pill
        x0, y0, x1, y1 = cx - tw // 2 - pad_x, cy - th // 2 - pad_y, cx + tw // 2 + pad_x, cy + th // 2 + pad_y
        rr = (y1 - y0) // 2
        sd.rounded_rectangle((x0 + 8 * S, y0 + 10 * S, x1 + 8 * S, y1 + 10 * S), radius=rr, fill=(0, 0, 0, 150))
        dr.rounded_rectangle((x0, y0, x1, y1), radius=rr, fill=_hex(fill) + (255,))
        dr.rounded_rectangle((x0, y0, x1, y1), radius=rr, outline=(17, 17, 17, 255), width=4 * S)
        dr.text((cx - tw / 2 - l, cy - th / 2 - t), text, font=font, fill=_hex(ink))
    sh = sh.filter(ImageFilter.GaussianBlur(7 * S))
    out = Image.alpha_composite(sh, img)
    bbox = out.getbbox()
    if bbox:
        out = out.crop(bbox)
    k = target_w / out.width if kind != "burst" else (target_w * 0.62) / out.width
    k = min(k, 1.0) if out.width * k > 4 else k
    return out.resize((max(4, int(out.width * k)), max(4, int(out.height * k))), Image.LANCZOS)
