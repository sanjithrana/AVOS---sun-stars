"""The numbered storyboard overview: every shot's starting picture in one grid, built in code
(so the numbers and the order are always right, never drawn by an image model)."""
from __future__ import annotations

import io

from PIL import Image, ImageDraw, ImageFont


def _font(size: int):
    for name in ("DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def grid(n: int, aspect: float) -> tuple[int, int]:
    """(columns, rows): about five across for a wide sheet, three for a tall picture."""
    cols = 5 if aspect >= 1 else 3
    cols = min(cols, max(1, n))
    return cols, -(-n // cols)


def build(frames: list[tuple[str, bytes | None]], title: str = "", cell_w: int = 360) -> bytes:
    """frames: [(label like "S01", png bytes or None if not drawn yet)]. Returns a PNG."""
    imgs = [(lab, Image.open(io.BytesIO(b)).convert("RGB") if b else None) for lab, b in frames]
    first = next((i for _, i in imgs if i), None)
    aspect = (first.width / first.height) if first else 9 / 16
    cols, rows = grid(len(imgs), aspect)
    cell_h = max(60, round(cell_w / aspect))
    gap, head = 8, (44 if title else 8)
    W, H = cols * cell_w + (cols + 1) * gap, head + rows * cell_h + (rows + 1) * gap
    sheet = Image.new("RGB", (W, H), (20, 20, 24))
    d = ImageDraw.Draw(sheet)
    if title:
        d.text((gap + 4, 10), title[:80].upper(), fill=(235, 235, 235), font=_font(22))
    f = _font(max(14, cell_w // 14))
    for i, (lab, im) in enumerate(imgs):
        x, y = gap + (i % cols) * (cell_w + gap), head + gap + (i // cols) * (cell_h + gap)
        if im:
            sheet.paste(im.resize((cell_w, cell_h)), (x, y))
        else:
            d.rectangle([x, y, x + cell_w, y + cell_h], outline=(90, 90, 100), width=2)
        tag = lab.lstrip("S").lstrip("0") or lab
        d.rectangle([x, y, x + len(tag) * (cell_w // 14) + 14, y + cell_w // 10], fill=(0, 0, 0))
        d.text((x + 6, y + 2), tag, fill=(255, 255, 255), font=f)
    out = io.BytesIO()
    sheet.save(out, "PNG")
    return out.getvalue()


# ---------------------------------------------------------------------------------------------------------------------
# The production board: poster, shot-by-shot frames with ACTION / CAMERA / LIGHTING / MOOD, character sheets, set, palette, notes.
# Built in code from the real pictures, so every word is readable and every number is right.
# ---------------------------------------------------------------------------------------------------------------------
PAPER, INK, MUTED, COPPER, LINE = (248, 242, 230), (58, 44, 36), (125, 108, 92), (176, 110, 48), (214, 196, 168)


def _ttf(names: tuple[str, ...], size: int):
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _serif(size: int):
    return _ttf(("DejaVuSerif-Bold.ttf", "georgiab.ttf", "timesbd.ttf"), size)


def _sans(size: int, bold: bool = False):
    return _ttf(("DejaVuSans-Bold.ttf", "arialbd.ttf") if bold else ("DejaVuSans.ttf", "arial.ttf"), size)


def _wrap(text: str, font, width: int, lines: int) -> list[str]:
    words, out, cur = str(text or "").split(), [], ""
    for w in words:
        t = f"{cur} {w}".strip()
        if font.getlength(t) <= width:
            cur = t
            continue
        out.append(cur)
        cur = w
    out.append(cur)
    out = [x for x in out if x]
    if len(out) > lines:
        out = out[:lines]
        while out[-1] and font.getlength(out[-1] + "…") > width:
            out[-1] = out[-1][:-1]
        out[-1] = out[-1].rstrip() + "…"
    return out


def _img(b: bytes | None):
    try:
        return Image.open(io.BytesIO(b)).convert("RGB") if b else None
    except Exception:  # noqa: BLE001
        return None


def _cover(im: Image.Image, w: int, h: int) -> Image.Image:
    k = max(w / im.width, h / im.height)
    r = im.resize((max(w, round(im.width * k)), max(h, round(im.height * k))))
    x, y = (r.width - w) // 2, (r.height - h) // 2
    return r.crop((x, y, x + w, y + h))


def _contain(im: Image.Image, w: int, h: int, bg=(30, 28, 32)) -> Image.Image:
    k = min(w / im.width, h / im.height)
    r = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))))
    c = Image.new("RGB", (w, h), bg)
    c.paste(r, ((w - r.width) // 2, (h - r.height) // 2))
    return c


def _stamp(d: ImageDraw.ImageDraw, box: tuple[int, int, int, int], msg: str) -> None:
    x0, y0, x1, y1 = box
    d.rectangle(box, fill=(232, 224, 208), outline=LINE, width=2)
    f = _sans(18)
    d.text(((x0 + x1) / 2, (y0 + y1) / 2), msg, fill=MUTED, font=f, anchor="mm")


def _panel(d: ImageDraw.ImageDraw, box: tuple[int, int, int, int], title: str) -> int:
    x0, y0, x1, y1 = box
    d.rounded_rectangle(box, radius=14, outline=COPPER, width=3, fill=(252, 248, 238))
    d.text((x0 + 22, y0 + 16), title.upper(), fill=COPPER, font=_serif(24))
    d.line([(x0 + 22, y0 + 52), (x1 - 22, y0 + 52)], fill=LINE, width=2)
    return y0 + 66


def _dominant(images: list[Image.Image], n: int = 5) -> list[dict]:
    """A palette taken from the real pictures when the plan has none."""
    if not images:
        return []
    strip = Image.new("RGB", (64 * len(images), 64))
    for i, im in enumerate(images):
        strip.paste(im.resize((64, 64)), (64 * i, 0))
    q = strip.quantize(colors=n, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette() or []
    counts = sorted(q.getcolors() or [], reverse=True)
    out = []
    for _, idx in counts[:n]:
        r, g, b = pal[idx * 3: idx * 3 + 3]
        out.append({"name": f"Colour {len(out) + 1}", "hex": f"#{r:02X}{g:02X}{b:02X}"})
    return out


def _secs(t: float) -> str:
    return f"{int(t) // 60}:{int(t) % 60:02d}"


def _palette(raw) -> list[dict]:
    """Palette entries as {name, hex}, whatever shape the plan used (strings, {hex} only, bad hex)."""
    import re as _re
    out = []
    for c in raw or []:
        hx = (c.get("hex") if isinstance(c, dict) else c) or ""
        hx = str(hx).strip()
        if _re.fullmatch(r"#?[0-9a-fA-F]{6}", hx):
            out.append({"hex": "#" + hx.lstrip("#"), "name": str((c.get("name") if isinstance(c, dict) else "") or hx)})
    return out


def board(plan: dict, frames: list[bytes | None], poster: bytes | None = None, sheets: list[bytes | None] | None = None,
          world: bytes | None = None, props: list[bytes | None] | None = None, aspect: str = "9:16") -> bytes:
    shots = plan.get("shots") or []
    W, M, G = 2400, 40, 24
    wide = aspect != "9:16" and aspect != "1:1" or aspect == "16:9"
    fr = [_img(b) for b in frames]
    # --- measure -------------------------------------------------------------------------------------------------
    pw = 760
    cols = 3
    cw = (W - 2 * M - pw - G * (cols + 1)) // cols
    box_h = round(cw * (0.5625 if wide else 0.95))
    label_f, text_f = _sans(17, True), _sans(17)
    cap_h = 44 + 4 * 2 * 23 + 10
    rows = max(1, -(-len(shots) // cols))
    main_h = rows * (box_h + cap_h) + (rows + 1) * G
    head_h = 150
    bottom_h = 560
    H = M + head_h + G + main_h + G + bottom_h + M
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    # --- header ----------------------------------------------------------------------------------------------------
    total = sum(float(s.get("seconds") or 0) for s in shots)
    d.text((M, M), str(plan.get("title") or "Storyboard").upper()[:70], fill=INK, font=_serif(54))
    for i, ln in enumerate(_wrap(plan.get("logline") or plan.get("hook") or "", _sans(26), W - 2 * M - 520, 2)):
        d.text((M, M + 72 + i * 36), ln, fill=MUTED, font=_sans(26))
    meta = f"{len(shots)} SHOTS  ·  {total:.0f} SECONDS  ·  {aspect}"
    d.text((W - M, M + 16), meta, fill=COPPER, font=_sans(26, True), anchor="ra")
    d.line([(M, M + head_h - 10), (W - M, M + head_h - 10)], fill=COPPER, width=3)
    y0 = M + head_h + G
    # --- poster (left) ---------------------------------------------------------------------------------------------
    px0, px1 = M, M + pw
    pim = _img(poster) or next((i for i in fr if i), None)
    if pim:
        img.paste(_cover(pim, pw, main_h), (px0, y0))
        shade = Image.new("RGBA", (pw, 360), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shade)
        for k in range(360):
            sd.line([(0, k), (pw, k)], fill=(20, 12, 8, int(215 * k / 360)))
        img.paste(shade, (px0, y0 + main_h - 360), shade)
        d = ImageDraw.Draw(img)
        ty = y0 + main_h - 40
        for ln in reversed(_wrap(plan.get("logline") or "", _sans(26), pw - 60, 3)):
            ty -= 34
            d.text((px0 + 30, ty), ln, fill=(240, 230, 210), font=_sans(26))
        ty -= 14
        for ln in reversed(_wrap(str(plan.get("title") or "").upper(), _serif(50), pw - 60, 3)):
            ty -= 62
            d.text((px0 + 30, ty), ln, fill=(255, 255, 255), font=_serif(50))
    else:
        _stamp(d, (px0, y0, px1, y0 + main_h), "key visual is drawn with the design")
    # --- shots grid (right) ------------------------------------------------------------------------------------------
    gx = M + pw + G
    t = 0.0
    for i, sh in enumerate(shots):
        r, c = divmod(i, cols)
        x, y = gx + c * (cw + G), y0 + G // 2 + r * (box_h + cap_h + G)
        d.rounded_rectangle((x - 6, y - 6, x + cw + 6, y + box_h + cap_h), radius=10, outline=LINE, width=2, fill=(252, 248, 238))
        if fr[i]:
            img.paste(_contain(fr[i], cw, box_h) if not wide else _cover(fr[i], cw, box_h), (x, y))
        else:
            _stamp(d, (x, y, x + cw, y + box_h), "not drawn yet")
        end = t + float(sh.get("seconds") or 0)
        tag, tf = f"{i + 1:02d}  {_secs(t)}-{_secs(end)}", _sans(20, True)
        d.rectangle((x, y, x + tf.getlength(tag) + 20, y + 38), fill=(30, 20, 14))
        d.text((x + 10, y + 5), tag, fill=(255, 255, 255), font=tf)
        t = end
        cy = y + box_h + 10
        cm = sh.get("camera") or {}
        cam = sh.get("cam_note") or ", ".join(x for x in (str(cm.get("type") or "").replace("_", " "), str(cm.get("movement") or "").replace("_", " "),
                                                         f"{cm['lens_mm']}mm" if cm.get("lens_mm") else "") if x) or "-"
        for lab, val in (("ACTION", sh.get("action")), ("CAMERA", cam), ("LIGHTING", sh.get("lighting") or sh.get("mood")),
                         ("MOOD", sh.get("mood") if sh.get("lighting") else sh.get("emotion"))):
            if not val:
                val = "-"
            lines = _wrap(f"{lab}: {val}", text_f, cw - 6, 2)
            for ln in lines:
                if ln.startswith(lab + ":"):
                    d.text((x, cy), lab + ":", fill=COPPER, font=label_f)
                    d.text((x + label_f.getlength(lab + ": "), cy), ln[len(lab) + 2:], fill=INK, font=text_f)
                else:
                    d.text((x, cy), ln, fill=INK, font=text_f)
                cy += 23
    # --- bottom row --------------------------------------------------------------------------------------------------
    by = y0 + main_h + G
    bw = W - 2 * M
    wd = [round(bw * k) for k in (0.40, 0.22, 0.15)]
    x1 = M + wd[0]
    x2 = x1 + G + wd[1]
    x3 = x2 + G + wd[2]
    cy = _panel(d, (M, by, x1, by + bottom_h), "Character design")
    sh_imgs = [_img(b) for b in (sheets or [])]
    have = [s for s in sh_imgs if s]
    if have:
        sw = (wd[0] - 44 - 14 * (len(have) - 1)) // len(have)
        for k, s in enumerate(have):
            img.paste(_contain(s, sw, by + bottom_h - cy - 22, (238, 230, 214)), (M + 22 + k * (sw + 14), cy))
    else:
        _stamp(d, (M + 22, cy, x1 - 22, by + bottom_h - 22), "character sheets are drawn with the design")
    cy = _panel(d, (x1 + G, by, x1 + G + wd[1], by + bottom_h), "Setting design")
    wim = _img(world)
    ww = wd[1] - 44
    if wim:
        hh = round(ww * wim.height / wim.width)
        img.paste(wim.resize((ww, hh)), (x1 + G + 22, cy))
        cy += hh + 14
    pi = [_img(b) for b in (props or [])]
    pi = [p for p in pi if p][:3]
    if pi:
        left = by + bottom_h - 22 - cy
        pwid = min((ww - 12 * (len(pi) - 1)) // len(pi), left)
        for k, p in enumerate(pi) if pwid > 60 else []:
            img.paste(_contain(p, pwid, pwid, (238, 230, 214)), (x1 + G + 22 + k * (pwid + 12), cy))
    if not wim and not pi:
        _stamp(d, (x1 + G + 22, cy, x1 + G + wd[1] - 22, by + bottom_h - 22), "set is drawn with the design")
    cy = _panel(d, (x2 + G, by, x2 + G + wd[2], by + bottom_h), "Colour palette")
    pal = _palette(plan.get("palette")) or _dominant([i for i in [_img(poster)] + fr if i])
    for k, c in enumerate(pal[:6]):
        yy = cy + k * 70
        d.rounded_rectangle((x2 + G + 22, yy, x2 + G + 22 + 84, yy + 56), radius=8, fill=c["hex"], outline=LINE)
        d.text((x2 + G + 124, yy + 4), str(c["name"])[:20], fill=INK, font=_sans(18, True))
        d.text((x2 + G + 124, yy + 30), c["hex"], fill=MUTED, font=_sans(17))
    cy = _panel(d, (x3 + G, by, W - M, by + bottom_h), "Direction notes")
    nw = W - M - (x3 + G) - 44
    for lab, val in (("Camera", plan.get("camera_language")), ("Lighting & mood", plan.get("lighting_note")), ("Sound", plan.get("sound_design") or plan.get("music")),
                     ("Narrative", plan.get("note") or plan.get("hook"))):
        if not val:
            continue
        d.text((x3 + G + 22, cy), lab.upper(), fill=COPPER, font=_sans(17, True))
        cy += 26
        for ln in _wrap(val, _sans(18), nw, 4):
            d.text((x3 + G + 22, cy), ln, fill=INK, font=_sans(18))
            cy += 24
        cy += 14
    out = io.BytesIO()
    img.save(out, "PNG", optimize=True)
    return out.getvalue()
