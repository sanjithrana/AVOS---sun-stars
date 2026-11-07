"""The storyboard in levels, the way a real production hands it over (built in code, so every word and number is right):

  cast   : one board per character - identity portrait, design sheet, the locked look, voice, palette
  world  : the set and every prop, with the set's look
  scenes : one board per scene - objective, the shots in order with their first frames, action, camera and timing
  clips  : one card per shot - first frame -> last frame, what moves, the camera move, timed beats, the line

Each board is a separate picture, so each model (and you) looks at one clear thing at a time instead of one crowded sheet."""
from __future__ import annotations

import io
from typing import Callable

from PIL import Image, ImageDraw

from .contactsheet import _contain, _cover, _img, _palette, _sans, _secs, _serif, _wrap

BG, PANEL, INK, MUTED, ACCENT, LINE = (6, 5, 16), (16, 13, 36), (240, 238, 255), (160, 154, 200), (168, 152, 255), (52, 44, 96)


def _canvas(w: int, h: int) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    im = Image.new("RGB", (w, h), BG)
    return im, ImageDraw.Draw(im)


def _head(d: ImageDraw.ImageDraw, w: int, kicker: str, title: str, meta: str = "") -> int:
    d.text((48, 40), kicker, fill=ACCENT, font=_sans(22, True))
    d.text((48, 72), title[:70], fill=INK, font=_serif(52))
    if meta:
        d.text((w - 48, 52), meta, fill=MUTED, font=_sans(22, True), anchor="ra")
    d.line([(48, 148), (w - 48, 148)], fill=LINE, width=2)
    return 172


def _box(d: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    d.rounded_rectangle(box, radius=18, fill=PANEL, outline=LINE, width=2)


def _text(d: ImageDraw.ImageDraw, x: int, y: int, label: str, value: str, width: int, lines: int = 3, size: int = 22) -> int:
    if not value:
        return y
    d.text((x, y), label, fill=ACCENT, font=_sans(18, True))
    y += 28
    for ln in _wrap(value, _sans(size), width, lines):
        d.text((x, y), ln, fill=INK, font=_sans(size))
        y += size + 8
    return y + 12


def _missing(d: ImageDraw.ImageDraw, box: tuple[int, int, int, int], msg: str) -> None:
    d.rounded_rectangle(box, radius=14, outline=LINE, width=2, fill=(10, 8, 24))
    d.text(((box[0] + box[2]) / 2, (box[1] + box[3]) / 2), msg, fill=MUTED, font=_sans(20), anchor="mm")


def _png(im: Image.Image) -> bytes:
    out = io.BytesIO()
    im.save(out, "PNG", optimize=True)
    return out.getvalue()


def cast(c: dict, portrait: bytes | None, sheet: bytes | None, palette: list, remembered: bool) -> bytes:
    W, H = 2400, 1400
    im, d = _canvas(W, H)
    y = _head(d, W, "CAST" + ("  ·  REMEMBERED" if remembered else ""), c["name"], (c.get("role") or "").upper())
    pw = 620
    _box(d, (48, y, 48 + pw, H - 48))
    p = _img(portrait)
    if p:
        im.paste(_contain(p, pw - 40, H - 48 - y - 40, PANEL), (68, y + 20))
    else:
        _missing(d, (68, y + 20, 48 + pw - 20, H - 68), "portrait is drawn with the design")
    sx = 48 + pw + 32
    sw = W - 48 - sx
    sh_h = 760
    _box(d, (sx, y, W - 48, y + sh_h))
    s = _img(sheet)
    if s:
        im.paste(_contain(s, sw - 40, sh_h - 40, PANEL), (sx + 20, y + 20))
    else:
        _missing(d, (sx + 20, y + 20, W - 68, y + sh_h - 20), "design sheet is drawn with the design")
    ty = y + sh_h + 32
    _box(d, (sx, ty, W - 48, H - 48))
    col = (sw - 80) // 2
    yy = _text(d, sx + 30, ty + 26, "LOCKED LOOK (pasted first into every picture)", c.get("look") or "", col, 6)
    _text(d, sx + 30, yy, "VOICE", c.get("voice") or "", col, 2)
    px = sx + 50 + col
    d.text((px, ty + 26), "COLOURS", fill=ACCENT, font=_sans(18, True))
    for k, cc in enumerate(_palette(palette)[:5]):
        yy = ty + 64 + k * 64
        d.rounded_rectangle((px, yy, px + 72, yy + 48), radius=10, fill=cc["hex"], outline=LINE)
        d.text((px + 92, yy + 2), str(cc["name"])[:22], fill=INK, font=_sans(20, True))
        d.text((px + 92, yy + 26), cc["hex"], fill=MUTED, font=_sans(17))
    return _png(im)


def world(w: dict, plate: bytes | None, props: list[tuple[dict, bytes | None]]) -> bytes:
    W, H = 2400, 1500
    im, d = _canvas(W, H)
    y = _head(d, W, "WORLD", w.get("name") or "Set", f"{len(props)} PROPS")
    lw = 1500
    _box(d, (48, y, 48 + lw, H - 48))
    pl = _img(plate)
    inner_h = H - 48 - y - 220
    if pl:
        im.paste(_cover(pl, lw - 40, inner_h), (68, y + 20))
    else:
        _missing(d, (68, y + 20, 48 + lw - 20, y + 20 + inner_h), "set is drawn with the design")
    _text(d, 72, y + inner_h + 44, "SET", w.get("look") or "", lw - 60, 4)
    rx = 48 + lw + 32
    rw = W - 48 - rx
    n = max(1, len(props))
    ch = min(420, (H - 48 - y - 24 * (n - 1)) // n)
    for i, (x, b) in enumerate(props):
        top = y + i * (ch + 24)
        _box(d, (rx, top, W - 48, top + ch))
        pim = _img(b)
        side = ch - 40
        if pim:
            im.paste(_contain(pim, side, side, PANEL), (rx + 20, top + 20))
        else:
            _missing(d, (rx + 20, top + 20, rx + 20 + side, top + 20 + side), "not drawn")
        _text(d, rx + 40 + side, top + 24, x["name"].upper(), x.get("look") or "", rw - side - 80, 5, 20)
    if not props:
        _missing(d, (rx, y, W - 48, y + 300), "no props in this video")
    return _png(im)


def scene(no: int, title: str, shots: list[dict], frames: list[bytes | None], start: float, aspect: str) -> bytes:
    W = 2400
    tall = aspect == "9:16"
    cols = 4 if tall else 3
    cw = (W - 96 - 32 * (cols - 1)) // cols
    fh = round(cw * (16 / 9 if tall else 9 / 16)) if tall else round(cw * 9 / 16)
    fh = min(fh, 760)
    cap = 330
    rows = max(1, -(-len(shots) // cols))
    head = 172
    obj = next((s.get("objective") for s in shots if s.get("objective")), "")
    note_h = 150 if obj else 40
    H = head + note_h + rows * (fh + cap + 32) + 48
    im, d = _canvas(W, H)
    total = sum(float(s.get("seconds") or 0) for s in shots)
    y = _head(d, W, f"SCENE {no:02d}", title or f"Scene {no}", f"{len(shots)} SHOTS  ·  {total:.1f} S")
    if obj:
        y = _text(d, 52, y, "WHAT THIS SCENE MUST DO", obj, W - 120, 2, 24)
    y += 8
    t = start
    for i, sh in enumerate(shots):
        r, c = divmod(i, cols)
        x, top = 48 + c * (cw + 32), y + r * (fh + cap + 32)
        _box(d, (x, top, x + cw, top + fh + cap))
        f = _img(frames[i] if i < len(frames) else None)
        if f:
            im.paste(_cover(f, cw - 24, fh - 24), (x + 12, top + 12))
        else:
            _missing(d, (x + 12, top + 12, x + cw - 12, top + fh - 12), "not drawn yet")
        end = t + float(sh.get("seconds") or 0)
        tag = f"{sh['id']}  {_secs(t)}-{_secs(end)}"
        tf = _sans(20, True)
        d.rounded_rectangle((x + 20, top + 20, x + 40 + tf.getlength(tag), top + 56), radius=8, fill=(0, 0, 0))
        d.text((x + 30, top + 25), tag, fill=INK, font=tf)
        t = end
        cm = sh.get("camera") or {}
        cam = sh.get("cam_note") or f"{str(cm.get('type', '')).replace('_', ' ')}, {str(cm.get('movement', '')).replace('_', ' ')}"
        cy = top + fh + 6
        cy = _text(d, x + 22, cy, "ACTION", sh.get("action") or "", cw - 44, 3, 19)
        cy = _text(d, x + 22, cy, "CAMERA", cam, cw - 44, 2, 19)
        _text(d, x + 22, cy, "LINE", sh.get("narration") or "", cw - 44, 2, 19)
    return _png(im)


def clip(sh: dict, first: bytes | None, last: bytes | None, motion: str, start: float, aspect: str) -> bytes:
    W = 2400
    tall = aspect == "9:16"
    fw = 560 if tall else 840
    fh = round(fw * 16 / 9) if tall else round(fw * 9 / 16)
    H = 172 + fh + 64 + 48
    H = max(H, 900)
    im, d = _canvas(W, H)
    cm = sh.get("camera") or {}
    end = start + float(sh.get("seconds") or 0)
    y = _head(d, W, f"CLIP {sh['id']}", (sh.get("scene_title") or sh.get("shot_type") or "").replace("_", " ").title() or sh["id"],
              f"{_secs(start)}-{_secs(end)}  ·  {float(sh.get('seconds') or 0):.1f} S")
    for k, (lab, b) in enumerate((("FIRST FRAME", first), ("LAST FRAME", last))):
        x = 48 + k * (fw + 120)
        _box(d, (x, y, x + fw, y + fh + 48))
        d.text((x + 20, y + 12), lab, fill=ACCENT, font=_sans(18, True))
        f = _img(b)
        if f:
            im.paste(_cover(f, fw - 40, fh - 20), (x + 20, y + 44))
        else:
            _missing(d, (x + 20, y + 44, x + fw - 20, y + fh + 24), "same as the first frame" if k else "not drawn yet")
    ax = 48 + fw + 20
    ay = y + fh // 2 + 24
    d.line([(ax, ay), (ax + 80, ay)], fill=ACCENT, width=6)
    d.polygon([(ax + 80, ay - 16), (ax + 104, ay), (ax + 80, ay + 16)], fill=ACCENT)
    tx = 48 + 2 * fw + 120 + 40
    tw = W - 48 - tx
    _box(d, (tx - 20, y, W - 48, H - 48))
    yy = _text(d, tx + 10, y + 24, "WHAT MOVES", motion, tw - 40, 7, 21)
    yy = _text(d, tx + 10, yy, "CAMERA", sh.get("cam_note") or f"{str(cm.get('movement', '')).replace('_', ' ')}, {cm.get('lens_mm', 35)}mm", tw - 40, 2, 21)
    yy = _text(d, tx + 10, yy, "ENDS ON", sh.get("end_state") or "", tw - 40, 2, 21)
    yy = _text(d, tx + 10, yy, "LINE", sh.get("narration") or "", tw - 40, 3, 21)
    _text(d, tx + 10, yy, "SOUND", sh.get("audio") or sh.get("sfx") or "", tw - 40, 2, 21)
    return _png(im)


def build_all(p: dict, read: Callable[[str | None], bytes | None], save: Callable[[str, bytes], str], motion_of: Callable[[dict], str],
              remembered: set[str]) -> dict:
    """Every board for project p. read(rel) gives a file, save(rel, bytes) stores one. Returns the {level: path} map."""
    plan, a = p["plan"], p.get("assets") or {}
    aspect = p.get("aspect") or "9:16"
    out: dict = {"cast": {}, "world": None, "scenes": {}, "clips": {}}
    for c in plan["characters"]:
        out["cast"][c["id"]] = save(f"boards/cast_{c['id']}.png", cast(c, read(a.get(f"ref:{c['id']}")), read(a.get(f"char:{c['id']}")),
                                                                         plan.get("palette") or [], c["id"] in remembered))
    out["world"] = save("boards/world.png", world(plan["world"], read(a.get("world")), [(x, read(a.get(f"prop:{x['id']}"))) for x in plan["props"]]))
    groups: dict[int, list[dict]] = {}
    for sh in plan["shots"]:
        groups.setdefault(int(sh.get("scene") or 1), []).append(sh)
    t = 0.0
    starts: dict[str, float] = {}
    for sh in plan["shots"]:
        starts[sh["id"]] = t
        t += float(sh.get("seconds") or 0)
    for no, shots in sorted(groups.items()):
        title = next((s.get("scene_title") for s in shots if s.get("scene_title")), "") or f"Scene {no}"
        out["scenes"][str(no)] = save(f"boards/scene_{no:02d}.png", scene(no, title, shots, [read(s.get("frame")) for s in shots], starts[shots[0]["id"]], aspect))
    for sh in plan["shots"]:
        out["clips"][sh["id"]] = save(f"boards/clip_{sh['id']}.png", clip(sh, read(sh.get("frame")), read(sh.get("end_frame")), motion_of(sh), starts[sh["id"]], aspect))
    return out
