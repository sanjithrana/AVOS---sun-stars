"""Puts one of the ready-made 2D characters on a scene's backdrop IN CODE, so the character in every scene is exactly the character you picked
(same face, hair, suit) and never depends on a picture model following a reference.

characters/<id>/<pose>.png   transparent cut-outs of the character from his model sheet (all at the same scale, feet at the bottom)
characters/<id>_2d.jpg    the picture shown on the create page

choose() maps a scene's three gestures ("pointing toward the right", "hand on chin, thinking"…) to the poses that character has;
place() stands the chosen pose in the left third of the backdrop with a soft ground shadow, leaving the right half for the paper cards."""
from __future__ import annotations

import io
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

DIR = Path(__file__).with_name("characters")
# first match wins; order matters ("holding a phone" before "holding a tablet")
INTENTS = [("phone", r"phone|\bcall"), ("device", r"tablet|laptop|computer|screen|paper|document|read|sketch|writ|napkin|notebook|hold"),
           ("cheer", r"cheer|celebrat|triumph|fist|victory|jump|excit|success|punch"), ("think", r"think|chin|ponder|worr|doubt|stare|puzzl|concern|plan"),
           ("open", r"open|wide|welcom|spread|embrace|greet|proud|shrug"), ("point", r"point|direct|toward|stretch|show|explain|present|chart|gestur")]
CANDIDATES = {"phone": ["call"], "device": ["laptop", "tablet"], "cheer": ["celebrate", "point"], "think": ["think"], "open": ["welcome"],
              "point": ["present", "explain", "point"], "neutral": ["front", "front34"]}
FALLBACK = ["welcome", "front34", "think", "front", "present", "explain"]


def sprites(cid: str) -> dict[str, Path]:
    return {f.stem: f for f in sorted((DIR / cid).glob("*.png"))} if (DIR / cid).is_dir() else {}


def intent(text: str) -> str:
    t = (text or "").lower()
    return next((k for k, rx in INTENTS if re.search(rx, t)), "neutral")


def choose(cid: str, texts: list[str], n: int = 3) -> list[str]:
    """n different pose names for this character, following the gestures in `texts` as far as the character has them."""
    pool = sprites(cid)
    if not pool:
        raise RuntimeError(f"The character “{cid}” has no pose pictures (animation_studio/studio/skilllab/characters/{cid}/).")
    used: list[str] = []
    for i in range(n):
        wanted = CANDIDATES.get(intent(texts[i] if i < len(texts) else ""), []) + CANDIDATES["neutral"] + FALLBACK
        pick = next((w for w in wanted if w in pool and w not in used), None) or next((k for k in pool if k not in used), next(iter(pool)))
        used.append(pick)
    return used


def _cover(img: Image.Image, W: int, H: int) -> Image.Image:
    img = img.convert("RGBA")
    s = max(W / img.width, H / img.height)
    img = img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))), Image.LANCZOS)
    x, y = (img.width - W) // 2, (img.height - H) // 2
    return img.crop((x, y, x + W, y + H))


def place(backdrop: bytes, cid: str, name: str, W: int, H: int, height: float = 0.78, cx: float = 0.20, floor: float = 0.975) -> bytes:
    """The backdrop with pose `name` standing in the left third (about `height` of the frame tall, feet at `floor`), as PNG bytes."""
    pool = sprites(cid)
    ref = Image.open(pool.get("front") or next(iter(pool.values()))).height            # the standing figure's height: poses keep one scale
    sp = Image.open(pool[name]).convert("RGBA")
    s = min(height * H / ref, 0.46 * W / sp.width)
    sp = sp.resize((max(1, round(sp.width * s)), max(1, round(sp.height * s))), Image.LANCZOS)
    out = _cover(Image.open(io.BytesIO(backdrop)), W, H)
    x = min(max(round(cx * W - sp.width / 2), round(0.01 * W)), round(0.5 * W - sp.width))
    y = round(floor * H - sp.height)
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse((x + sp.width * 0.12, floor * H - H * 0.022, x + sp.width * 0.88, floor * H + H * 0.018), fill=(20, 25, 40, 95))
    out.alpha_composite(sh.filter(ImageFilter.GaussianBlur(max(2, H * 0.008))))
    out.alpha_composite(sp, (x, y))
    b = io.BytesIO()
    out.convert("RGB").save(b, "PNG")
    return b.getvalue()


def sheet(cid: str) -> bytes | None:
    """The user's full model sheet (all angles, expressions, poses) - handed to the video model as a reference."""
    f = DIR / cid / "sheet.jpg"
    return f.read_bytes() if f.exists() else None
