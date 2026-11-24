"""Post cards and frames drawn above the clip (social post headers, comment card, quote, phone, terminal, podcast show).

Each is one transparent picture made per clip (the clip's own title goes in it as the hook unless you typed one), laid over
the canvas and the video for the whole clip. Ideas from clip editors such as YIZERGE; the drawing is ours."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONTS_DIR = Path(__file__).parent / "assets" / "fonts"
FONT_FILES = {"Inter": "Inter-ExtraBold.ttf", "Poppins": "Poppins-Bold.ttf", "Montserrat": "Montserrat-ExtraBold.ttf",
              "Serif": "DMSerifDisplay.ttf", "Playfair": "PlayfairDisplay-Bold.ttf", "Mono": "JetBrainsMono-Bold.ttf", "Oswald": "Oswald-Bold.ttf"}

THEMES = {   # page text, secondary text, card colour, accent
    "x_light": ("#0F1419", "#536471", None, "#1D9BF0"),
    "x_dark": ("#E7E9EA", "#71767B", None, "#1D9BF0"),
    "linkedin": ("#191919", "#666666", None, "#0A66C2"),
    "threads": ("#F3F5F7", "#8A8D91", None, "#0095F6"),
    "yt_banner": ("#F1F1F1", "#AAAAAA", None, "#FF0033"),
    "comment": ("#F1F1F1", "#AAAAAA", "#1F1F1F", "#3EA6FF"),
    "quote": ("#F5F1E8", "#9A9488", None, "#C8FF3A"),
    "phone": ("#FFFFFF", "#BBBBBB", None, "#FFFFFF"),
    "glow": ("#FFFFFF", "#C9B8FF", "#FFFFFF1A", "#B794FF"),
    "terminal": ("#D7E3F4", "#6B7A90", "#0E1621", "#4FD1C5"),
    "podcast_show": ("#FFFFFF", "#C8FF3A", None, "#C8FF3A"),
}


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    f = FONTS_DIR / FONT_FILES.get(name, name if name.endswith(".ttf") else "Inter-ExtraBold.ttf")
    try:
        return ImageFont.truetype(str(f if f.is_file() else FONTS_DIR / "Inter-ExtraBold.ttf"), max(8, size))
    except OSError:
        return ImageFont.load_default()


def _rgba(c: str) -> tuple[int, int, int, int]:
    c = c.lstrip("#")
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), int(c[6:8], 16) if len(c) >= 8 else 255)


def wrap(d: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, width: int, lines: int) -> list[str]:
    out, cur = [], ""
    for wd in " ".join((text or "").split()).split(" "):
        test = (cur + " " + wd).strip()
        if cur and d.textlength(test, font=font) > width:
            out.append(cur)
            cur = wd
        else:
            cur = test
    if cur:
        out.append(cur)
    if len(out) > lines:
        out = out[:lines]
        while out[-1] and d.textlength(out[-1] + "…", font=font) > width:
            out[-1] = out[-1][:-1]
        out[-1] = out[-1].rstrip(" ,.") + "…"
    return out


def _avatar(img: Image.Image, path: str | None, x: int, y: int, size: int, colour: str, letter: str) -> None:
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, size - 1, size - 1], fill=255)
    if path and Path(path).is_file():
        try:
            av = Image.open(path).convert("RGBA")
            s = min(av.size)
            av = av.crop(((av.width - s) // 2, (av.height - s) // 2, (av.width - s) // 2 + s, (av.height - s) // 2 + s)).resize((size, size))
            img.paste(av, (x, y), mask)
            return
        except OSError:
            pass
    disc = Image.new("RGBA", (size, size), _rgba(colour))
    ImageDraw.Draw(disc).text((size / 2, size / 2), (letter or "?")[:1].upper(), font=_font("Inter", int(size * 0.45)), fill=(255, 255, 255, 255), anchor="mm")
    img.paste(disc, (x, y), mask)


def _badge(d: ImageDraw.ImageDraw, kind: str, x: int, cy: int, s: int, accent: str) -> int:
    """A verified tick / LinkedIn / YouTube mark after the name; returns its width."""
    if kind == "yt":
        w = int(s * 1.5)
        d.rounded_rectangle([x, cy - s // 2, x + w, cy + s // 2], radius=s // 5, fill=_rgba("#FF0033"))
        d.text((x + w / 2, cy), "YT", font=_font("Inter", int(s * 0.62)), fill=(255, 255, 255, 255), anchor="mm")
        return w
    if kind == "in":
        d.rounded_rectangle([x, cy - s // 2, x + s, cy + s // 2], radius=s // 6, fill=_rgba("#0A66C2"))
        d.text((x + s / 2, cy + 1), "in", font=_font("Inter", int(s * 0.62)), fill=(255, 255, 255, 255), anchor="mm")
        return s
    d.ellipse([x, cy - s // 2, x + s, cy + s // 2], fill=_rgba(accent))
    d.line([(x + s * 0.27, cy + s * 0.02), (x + s * 0.44, cy + s * 0.2), (x + s * 0.75, cy - s * 0.2)], fill=(255, 255, 255, 255), width=max(2, s // 7), joint="curve")
    return s


def render(tpl: str, f: dict, hook: str, w: int, h: int, box: tuple[int, int, int, int], out: Path) -> Path | None:
    """Draw the card for this template above the clip box. f: name, handle, verified, avatar, font, size (%), episode, speakers, likes."""
    kind = {"x_light": "post", "x_dark": "post", "linkedin": "post", "threads": "post", "yt_banner": "post"}.get(tpl, tpl)
    if tpl not in THEMES:
        return None
    text_c, sub_c, card_c, accent = THEMES[tpl]
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    k = w / 720 * max(0.6, min(1.6, float(f.get("size") or 100) / 100))
    name = (f.get("name") or "").strip() or "Your Channel"
    handle = (f.get("handle") or "").strip()
    if handle and not handle.startswith("@"):
        handle = "@" + handle
    hook = " ".join((f.get("hook") or hook or "").split())
    fam = f.get("font") or ("Serif" if kind == "quote" else "Mono" if kind == "terminal" else "Inter")
    bx, by, bw, bh = box
    m = int(40 * w / 720)
    top_limit = int(h * 0.04)

    if kind == "post":
        av = int(64 * k)
        hf, nf, sf = _font(fam, int(34 * k)), _font("Inter", int(26 * k)), _font("Poppins", int(21 * k))
        lines = wrap(d, hook, hf, w - 2 * m, 6)
        lh = int(34 * k * 1.28)
        block = av + int(18 * k) + lh * len(lines)
        y0 = max(top_limit, by - int(26 * k) - block)
        _avatar(img, f.get("avatar"), m, y0, av, accent if tpl != "threads" else "#333333", name)
        nx, ncy = m + av + int(14 * k), y0 + av // 2 - int(12 * k)
        d.text((nx, ncy), name, font=nf, fill=_rgba(text_c), anchor="lm")
        bxp = nx + int(d.textlength(name, font=nf)) + int(8 * k)
        mark = {"linkedin": "in", "yt_banner": "yt"}.get(tpl, "tick")
        if f.get("verified", True) or mark != "tick":
            _badge(d, mark, bxp, ncy, int(24 * k), accent)
        sub = handle or ("@" + name.lower().replace(" ", ""))
        if tpl == "linkedin":
            sub = (f.get("headline") or handle or "Founder") + " • 1st"
        d.text((nx, ncy + int(30 * k)), sub, font=sf, fill=_rgba(sub_c), anchor="lm")
        y = y0 + av + int(18 * k)
        for ln in lines:
            d.text((m, y), ln, font=hf, fill=_rgba(text_c))
            y += lh

    elif kind == "comment":
        cf, nf, sf = _font(fam, int(28 * k)), _font("Inter", int(22 * k)), _font("Poppins", int(17 * k))
        cw = w - 2 * m
        lines = wrap(d, hook, cf, cw - int(48 * k), 4)
        lh = int(28 * k * 1.3)
        ch = int(118 * k) + lh * len(lines)
        y0 = max(top_limit, by - int(40 * k) - ch)
        d.rounded_rectangle([m, y0, m + cw, y0 + ch], radius=int(22 * k), fill=_rgba(card_c), outline=_rgba("#3A3A3A"), width=2)
        p = m + int(24 * k)
        ay0 = y0 + int(26 * k)                               # a small reply arrow, then the label
        d.line([(p + int(14 * k), ay0 - int(6 * k)), (p + int(4 * k), ay0 - int(6 * k)), (p + int(4 * k), ay0 + int(5 * k))], fill=_rgba(sub_c), width=max(2, int(2 * k)))
        d.polygon([(p, ay0 + int(1 * k)), (p + int(8 * k), ay0 + int(1 * k)), (p + int(4 * k), ay0 + int(7 * k))], fill=_rgba(sub_c))
        d.text((p + int(22 * k), ay0), "REPLYING TO COMMENT", font=sf, fill=_rgba(sub_c), anchor="lm")
        av = int(36 * k)
        ay = y0 + int(50 * k)
        _avatar(img, f.get("avatar"), p, ay, av, accent, name)
        nx = p + av + int(12 * k)
        d.text((nx, ay + av // 2), name, font=nf, fill=_rgba(text_c), anchor="lm")
        tx = nx + int(d.textlength(name, font=nf)) + int(8 * k)
        if f.get("verified", True):
            tx += _badge(d, "tick", tx, ay + av // 2, int(20 * k), accent) + int(8 * k)
        d.text((tx, ay + av // 2), "• 2h", font=sf, fill=_rgba(sub_c), anchor="lm")
        likes = str(f.get("likes") or "48.2K")
        lf = _font("Inter", int(20 * k))
        rx = m + cw - int(24 * k)
        d.text((rx, ay + av // 2), likes, font=lf, fill=_rgba("#FF4D67"), anchor="rm")
        hx, hy, r = rx - int(d.textlength(likes, font=lf)) - int(22 * k), ay + av // 2 - int(3 * k), int(6 * k)   # a heart: two dots and a point
        d.ellipse([hx - 2 * r, hy - r, hx, hy + r], fill=_rgba("#FF4D67"))
        d.ellipse([hx, hy - r, hx + 2 * r, hy + r], fill=_rgba("#FF4D67"))
        d.polygon([(hx - 2 * r + 1, hy + int(r * 0.4)), (hx + 2 * r - 1, hy + int(r * 0.4)), (hx, hy + int(r * 2.6))], fill=_rgba("#FF4D67"))
        y = ay + av + int(14 * k)
        for ln in lines:
            d.text((p, y), ln, font=cf, fill=_rgba(text_c))
            y += lh

    elif kind in ("quote", "glow"):
        qf = _font(fam, int(42 * k))
        lines = wrap(d, hook, qf, w - 2 * m - (int(40 * k) if kind == "glow" else 0), 5)
        lh = int(42 * k * 1.22)
        block = int(70 * k) + lh * len(lines) + int(50 * k)
        y0 = max(top_limit, by - int(30 * k) - block)
        if kind == "glow":
            d.rounded_rectangle([m - int(14 * k), y0 - int(14 * k), w - m + int(14 * k), y0 + block], radius=int(28 * k), fill=_rgba(card_c), outline=_rgba("#FFFFFF33"), width=2)
        d.text((m, y0 - int(10 * k)), "“", font=_font("Serif", int(110 * k)), fill=_rgba(accent))
        y = y0 + int(70 * k)
        for ln in lines:
            d.text((m, y), ln, font=qf, fill=_rgba(text_c))
            y += lh
        d.text((m, y + int(10 * k)), "— " + name, font=_font("Playfair", int(24 * k)), fill=_rgba(sub_c))

    elif kind == "phone":
        sb = _font("Inter", int(22 * k))
        d.rounded_rectangle([6, 6, w - 7, h - 7], radius=int(70 * w / 720), outline=_rgba("#2B2B2E"), width=int(14 * w / 720))
        d.text((int(70 * w / 720), int(52 * w / 720)), "9:41", font=sb, fill=_rgba(text_c), anchor="lm")
        d.text((w - int(70 * w / 720), int(52 * w / 720)), "100%", font=sb, fill=_rgba(text_c), anchor="rm")
        d.rounded_rectangle([w // 2 - int(80 * w / 720), int(34 * w / 720), w // 2 + int(80 * w / 720), int(70 * w / 720)], radius=int(18 * w / 720), fill=(0, 0, 0, 255))
        hf = _font(fam, int(34 * k))
        lines = wrap(d, hook or "Watch what happens next…", hf, w - 2 * m, 4)
        lh = int(34 * k * 1.28)
        y = max(int(110 * w / 720), by - int(30 * k) - lh * len(lines))
        for ln in lines:
            d.text((w / 2, y), ln, font=hf, fill=_rgba(text_c), anchor="ma")
            y += lh

    elif kind == "terminal":
        mf = _font("Mono", int(22 * k))
        hf = _font(fam, int(28 * k))
        lines = wrap(d, hook, hf, w - 2 * m - int(40 * k), 5)
        lh = int(28 * k * 1.35)
        ch = int(150 * k) + lh * len(lines)
        y0 = max(top_limit, by - int(34 * k) - ch)
        d.rounded_rectangle([m, y0, w - m, y0 + ch], radius=int(16 * k), fill=_rgba(card_c), outline=_rgba("#24344A"), width=2)
        for i, c in enumerate(("#FF5F57", "#FEBC2E", "#28C840")):
            cx = m + int(26 * k) + i * int(24 * k)
            d.ellipse([cx - int(7 * k), y0 + int(24 * k) - int(7 * k), cx + int(7 * k), y0 + int(24 * k) + int(7 * k)], fill=_rgba(c))
        d.text((m + int(110 * k), y0 + int(24 * k)), "~/dev/run.sh", font=_font("Mono", int(17 * k)), fill=_rgba(sub_c), anchor="lm")
        d.text((m + int(20 * k), y0 + int(62 * k)), "$ bash run.sh --viral", font=mf, fill=_rgba(accent), anchor="lm")
        y = y0 + int(92 * k)
        for ln in lines:
            d.text((m + int(20 * k), y), ln, font=hf, fill=_rgba(text_c))
            y += lh
        d.rounded_rectangle([m + int(20 * k), y + int(16 * k), w - m - int(20 * k), y + int(26 * k)], radius=int(5 * k), fill=_rgba("#1C2A3C"))
        d.rounded_rectangle([m + int(20 * k), y + int(16 * k), int(m + int(20 * k) + (w - 2 * m - int(40 * k)) * 0.82), y + int(26 * k)], radius=int(5 * k), fill=_rgba("#3B82F6"))

    elif kind == "podcast_show":
        pf = _font("Inter", int(18 * k))
        hf = _font(fam, int(34 * k))
        lines = wrap(d, hook, hf, w - 2 * m, 5)
        lh = int(34 * k * 1.28)
        block = int(90 * k) + lh * len(lines)
        y0 = max(top_limit, by - int(30 * k) - block)
        x = m
        for label, bg, fg in (("PODCAST", "#FFFFFF", "#111111"), (("EP. " + str(f.get("episode"))) if f.get("episode") else "", "#C8FF3A", "#111111")):
            if not label:
                continue
            tw = int(d.textlength(label, font=pf)) + int(22 * k)
            d.rounded_rectangle([x, y0, x + tw, y0 + int(32 * k)], radius=int(8 * k), fill=_rgba(bg))
            d.text((x + tw / 2, y0 + int(16 * k)), label, font=pf, fill=_rgba(fg), anchor="mm")
            x += tw + int(10 * k)
        d.text((m, y0 + int(54 * k)), (f.get("speakers") or name), font=_font("Poppins", int(22 * k)), fill=_rgba(sub_c), anchor="lm")
        y = y0 + int(84 * k)
        for ln in lines:
            d.text((m, y), ln, font=hf, fill=_rgba(text_c))
            y += lh
    else:
        return None
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out
