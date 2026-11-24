"""Frames around the clip: a canvas behind it (blur, colour, gradient, your picture), padding and rounded corners, a headline
pinned above it, and layouts for two or three people. The ideas come from clip tools such as YIZERGE; the code is ours.

Templates        what it looks like
---------------  -----------------------------------------------------------------
x_light / x_dark the clip as a post: plain white / black page, your handle and the headline above a rounded 16:9 clip
tiktok_hook      blurred fill, the headline in a white box on top (black words), the clip in the middle
breaking         dark red page, a red BREAKING tag and the headline in a black bar, the clip under it

Layouts (added to cut.LAYOUTS): centered (the clip on the canvas), wide (16:9 clip under the headline), split (two people
side by side in the source: left one on top, right one below), pip (left person fills the screen, right one in a corner),
trio (three people side by side: stacked)."""
from __future__ import annotations

from pathlib import Path

TEMPLATES: dict[str, dict] = {
    "none": {"label": "No template", "cat": "all", "desc": "Just the clip."},
    # ---- social posts: a post card above a 16:9 clip ----
    "x_light": {"label": "Twitter / X (light)", "cat": "social", "card": True, "bg": "color", "color": "#FFFFFF", "pad": 4, "radius": 24, "video_y": 0.5,
                "desc": "Crisp white card, verified tick, handle and a centred 16:9 clip",
                "head": {"text": "#0F1419", "sub": "#536471", "box": None, "align": "left", "size": 0.04}},
    "x_dark": {"label": "Twitter / X (dark)", "cat": "social", "card": True, "bg": "color", "color": "#000000", "pad": 4, "radius": 24, "video_y": 0.5,
               "desc": "OLED black card, verified tick, bright text and a centred 16:9 clip",
               "head": {"text": "#E7E9EA", "sub": "#71767B", "box": None, "align": "left", "size": 0.04}},
    "linkedin": {"label": "LinkedIn post (pro)", "cat": "social", "card": True, "bg": "color", "color": "#F3F2EF", "pad": 4, "radius": 16, "video_y": 0.5,
                 "desc": "Professional card with the LinkedIn mark, your headline and an insightful hook"},
    "threads": {"label": "Threads minimalist", "cat": "social", "card": True, "bg": "color", "color": "#101010", "pad": 4, "radius": 20, "video_y": 0.5,
                "desc": "Sleek dark Threads-style card with refined type"},
    "yt_banner": {"label": "YouTube Shorts banner", "cat": "social", "card": True, "bg": "color", "color": "#0F0F0F", "pad": 4, "radius": 20, "video_y": 0.5,
                  "desc": "Red YT badge, bold channel name, high-retention hook and a clean frame"},
    "comment": {"label": "Viral comment spotlight", "cat": "social", "card": True, "bg": "gradient", "color": "#141821", "color2": "#07080B", "pad": 4, "radius": 20, "video_y": 0.52,
                "desc": "A viewer's comment card on top (name, likes), the clip answering it"},
    # ---- viral hooks / broadcast ----
    "tiktok_hook": {"label": "TikTok hook", "cat": "hooks", "bg": "blur", "pad": 0, "radius": 0, "video_y": 0.5, "desc": "Blurred fill, the hook in a white box on top",
                    "head": {"text": "#000000", "sub": None, "box": "#FFFFFF", "align": "center", "size": 0.04}},
    "breaking": {"label": "Breaking news", "cat": "broadcast", "bg": "gradient", "color": "#8B0000", "color2": "#140000", "pad": 3, "radius": 16, "video_y": 0.47,
                 "desc": "Red BREAKING tag and the headline in a news bar",
                 "head": {"text": "#FFFFFF", "sub": None, "box": "#000000", "align": "center", "size": 0.036, "tag": "BREAKING NEWS", "tag_box": "#E10600"}},
    # ---- podcasts ----
    "podcast": {"label": "Podcast close-up", "cat": "podcasts", "bg": "blur", "pad": 0, "radius": 0, "layout": "podcast", "pin_top": True,
                "desc": "Speaker big on top, blurred below, small title pinned at the top",
                "head": {"text": "#FFFFFF", "sub": None, "box": "#000000", "align": "center", "size": 0.022}},
    "podcast_show": {"label": "Podcast / studio show", "cat": "podcasts", "card": True, "bg": "color", "color": "#121214", "pad": 4, "radius": 18, "video_y": 0.5,
                     "desc": "PODCAST pill, episode number, speaker names and the hook"},
    # ---- aesthetic & tech ----
    "quote": {"label": "Minimalist cinema quote", "cat": "aesthetic", "card": True, "bg": "color", "color": "#0B0B0F", "pad": 4, "radius": 12, "video_y": 0.56,
              "desc": "Editorial serif quote with quote marks and the speaker's name"},
    "phone": {"label": "Smartphone mockup frame", "cat": "aesthetic", "card": True, "bg": "color", "color": "#15161C", "pad": 5, "radius": 22, "video_y": 0.48,
              "desc": "Phone bezel with notch and status bar, the hook on top"},
    "glow": {"label": "Creator studio glow", "cat": "aesthetic", "card": True, "bg": "gradient", "color": "#2A1460", "color2": "#0D0820", "pad": 4, "radius": 22, "video_y": 0.56,
             "desc": "Creator gradient, glowing glass card and sleek type"},
    "terminal": {"label": "Developer terminal", "cat": "aesthetic", "card": True, "bg": "color", "color": "#070B11", "pad": 4, "radius": 14, "video_y": 0.56,
                 "desc": "A code window with `$ bash run.sh --viral`, mono type and a progress bar"},
}
CATEGORIES = {"all": "All", "social": "Social posts", "hooks": "Viral hooks", "podcasts": "Podcasts", "broadcast": "Broadcast", "aesthetic": "Aesthetic & tech"}
CARD_KEYS = {"name": 40, "handle": 40, "headline": 60, "hook": 220, "font": 20, "episode": 10, "speakers": 60, "likes": 10}


def clean_card(f: dict | None) -> dict:
    """The post-card fields from the form: text trimmed to size, a known font, size 60-160 %, verified on/off."""
    from .cards import FONT_FILES
    f = f if isinstance(f, dict) else {}
    out: dict = {k: " ".join(str(f.get(k) or "").split())[:n] for k, n in CARD_KEYS.items() if str(f.get(k) or "").strip()}
    if out.get("font") not in FONT_FILES:
        out.pop("font", None)
    try:
        out["size"] = max(60, min(160, int(float(f.get("size") or 100))))
    except (TypeError, ValueError):
        out["size"] = 100
    out["verified"] = str(f.get("verified", True)).lower() not in ("0", "false", "no", "off")
    return out
BACKGROUNDS = {"blur": "Blurred video", "color": "Solid colour", "gradient": "Gradient", "image": "My picture"}
LAYOUTS = {"podcast": "Podcast: speaker big on top, blurred below (captions on the seam)", "centered": "Centered on a canvas (padding, rounded corners)", "wide": "16:9 clip under a headline",
           "split": "Two people: host on top, guest below", "pip": "Picture in picture (guest in the corner)", "trio": "Three people stacked"}
CANVAS_KEYS = ("bg", "color", "color2", "pad", "radius", "dim", "image")


def _hex(c: str | None, default: str = "#000000") -> tuple[int, int, int]:
    c = str(c or default).lstrip("#")
    try:
        return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    except (ValueError, IndexError):
        return _hex(default)


def _even(v: float) -> int:
    return max(2, int(v) // 2 * 2)


def clean(tpl: str | None, canvas: dict | None) -> tuple[str, dict]:
    """The template name and the canvas settings: the template's own, then the user's changes (unknown keys and bad values dropped)."""
    t = tpl if tpl in TEMPLATES else "none"
    base = {k: v for k, v in TEMPLATES[t].items() if k in CANVAS_KEYS}
    base.setdefault("bg", "blur")
    c = canvas if isinstance(canvas, dict) else {}
    if c.get("bg") in BACKGROUNDS:
        base["bg"] = c["bg"]
    for k in ("color", "color2"):
        if isinstance(c.get(k), str) and len(c[k].lstrip("#")) == 6:
            base[k] = "#" + c[k].lstrip("#")
    for k, lo, hi in (("pad", 0, 15), ("radius", 0, 80), ("dim", 0, 80)):
        try:
            if c.get(k) not in (None, ""):
                base[k] = max(lo, min(hi, float(c[k])))
        except (TypeError, ValueError):
            pass
    if c.get("image"):
        base["image"] = str(c["image"])
    return t, base


def box(layout: str, tpl: str, canvas: dict, w: int, h: int) -> tuple[int, int, int, int]:
    """(x, y, width, height) of the 16:9 clip on the canvas."""
    pad = int(w * float(canvas.get("pad") or 0) / 100)
    vw = _even(w - 2 * pad)
    vh = _even(vw * 9 / 16)
    cy = TEMPLATES.get(tpl, {}).get("video_y") or (0.42 if layout == "wide" else 0.5)
    y = _even(max(0, min(h - vh, cy * h - vh / 2)))
    return (w - vw) // 2, y, vw, vh


def images(canvas: dict, w: int, h: int, vw: int, vh: int, folder: Path) -> tuple[Path | None, Path | None]:
    """The background picture (None for the blurred video) and the rounded-corner mask (None for square corners)."""
    from PIL import Image, ImageDraw, ImageFilter
    folder.mkdir(parents=True, exist_ok=True)
    bgf = None
    kind = canvas.get("bg") or "blur"
    if kind == "image" and canvas.get("image") and Path(canvas["image"]).is_file():
        im = Image.open(canvas["image"]).convert("RGB")
        s = max(w / im.width, h / im.height)
        im = im.resize((max(w, int(im.width * s + 1)), max(h, int(im.height * s + 1))))
        im = im.crop(((im.width - w) // 2, (im.height - h) // 2, (im.width - w) // 2 + w, (im.height - h) // 2 + h)).filter(ImageFilter.GaussianBlur(6))
        kind = "image"
    elif kind == "gradient":
        a, b = _hex(canvas.get("color"), "#1E1E2E"), _hex(canvas.get("color2"), "#000000")
        im = Image.new("RGB", (w, h))
        dr = ImageDraw.Draw(im)
        for y in range(h):
            f = y / max(1, h - 1)
            dr.line([(0, y), (w, y)], fill=tuple(int(a[i] + (b[i] - a[i]) * f) for i in range(3)))
    elif kind in ("color", "image"):
        im = Image.new("RGB", (w, h), _hex(canvas.get("color"), "#000000"))
    else:
        im = None
    if im is not None:
        dim = float(canvas.get("dim") or 0) / 100
        if dim:
            im = Image.blend(im, Image.new("RGB", (w, h), (0, 0, 0)), dim)
        bgf = folder / "canvas-bg.png"
        im.save(bgf)
    maskf = None
    r = int(canvas.get("radius") or 0)
    if r > 0:
        m = Image.new("L", (vw, vh), 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, vw - 1, vh - 1], radius=min(r, vh // 2), fill=255)
        maskf = folder / "canvas-mask.png"
        m.save(maskf)
    return bgf, maskf


def graph(layout: str, tpl: str, canvas: dict, w: int, h: int, folder: Path, overlay: Path | None = None) -> tuple[str, list[Path]]:
    """A filter graph ending in [v] and the pictures it needs as extra inputs. The graph names them {IMG0}, {IMG1}...: cut.py
    puts in their input numbers once it knows them."""
    hw = _even(h / 2)
    if layout == "split":
        return (f"[0:v]split[a][b];[a]crop=iw/2:ih:0:0,scale={w}:{hw}:force_original_aspect_ratio=increase,crop={w}:{hw},setsar=1[t];"
                f"[b]crop=iw/2:ih:iw/2:0,scale={w}:{h - hw}:force_original_aspect_ratio=increase,crop={w}:{h - hw},setsar=1[u];[t][u]vstack[v]"), []
    if layout == "trio":
        t3 = _even(h / 3)
        parts = [f"[s{i}]crop=iw/3:ih:{i}*iw/3:0,scale={w}:{t3 if i < 2 else h - 2 * t3}:force_original_aspect_ratio=increase,crop={w}:{t3 if i < 2 else h - 2 * t3},setsar=1[r{i}]" for i in range(3)]
        return "[0:v]split=3[s0][s1][s2];" + ";".join(parts) + ";[r0][r1][r2]vstack=inputs=3[v]", []
    if layout == "pip":
        iw_ = _even(w * 0.36)
        ih_ = _even(iw_ * 16 / 9 * 0.62)
        return (f"[0:v]split[a][b];[a]crop=iw/2:ih:0:0,scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1[m];"
                f"[b]crop=iw/2:ih:iw/2:0,scale={iw_}:{ih_}:force_original_aspect_ratio=increase,crop={iw_}:{ih_},pad={iw_ + 8}:{ih_ + 8}:4:4:white,setsar=1[p];"
                f"[m][p]overlay=W-w-28:{int(h * 0.1)}[v]"), []
    if layout == "podcast":                              # the shot fills the top 70%, the same video blurred below, like the big podcast clip channels
        vh = _even(h * 0.7)
        dim = float(canvas.get("dim") or 0) / 100
        return (f"[0:v]split[s0][s1];[s0]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=30:5,eq=brightness={-0.12 - 0.5 * dim:.2f},setsar=1[bg];"
                f"[s1]crop='min(iw,ih*{w}/{vh})':'min(ih,iw*{vh}/{w})',scale={w}:{vh},setsar=1[fg];[bg][fg]overlay=0:0:shortest=1,format=yuv420p[v]"), []
    x, y, vw, vh = box(layout, tpl, canvas, w, h)
    bgf, maskf = images(canvas, w, h, vw, vh, folder)
    extra: list[Path] = []
    g = "[0:v]split[s0][s1];"
    if bgf:
        extra.append(bgf)
        g += f"[{{IMG0}}:v]scale={w}:{h},setsar=1,format=yuv420p[bg];[s0]nullsink;"
    else:
        dim = float(canvas.get("dim") or 0) / 100
        g += f"[s0]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=30:5,eq=brightness={-0.08 - 0.5 * dim:.2f},setsar=1[bg];"
    g += f"[s1]crop='min(iw,ih*16/9)':'min(ih,iw*9/16)',scale={vw}:{vh},setsar=1"
    if maskf:
        k = len(extra)
        extra.append(maskf)
        g += f",format=yuva420p[fv];[{{IMG{k}}}:v]scale={vw}:{vh},format=gray[mk];[fv][mk]alphamerge[fg];"
    else:
        g += "[fg];"
    if overlay and Path(overlay).is_file():                  # the post card / frame drawn over everything
        k = len(extra)
        extra.append(Path(overlay))
        g += f"[bg][fg]overlay={x}:{y}:shortest=1[cv];[{{IMG{k}}}:v]scale={w}:{h},format=rgba[ov];[cv][ov]overlay=0:0:shortest=1,format=yuv420p[v]"
    else:
        g += f"[bg][fg]overlay={x}:{y}:shortest=1,format=yuv420p[v]"
    return g, extra


def _ass_col(c: str, alpha: int = 0) -> str:
    r, g, b = _hex(c)
    return f"&H{alpha:02X}{b:02X}{g:02X}{r:02X}"


def _esc(t: str) -> str:
    return t.replace("\\", "/").replace("{", "(").replace("}", ")").replace("\n", " ")


def _wrap(text: str, per_line: int, lines: int = 3) -> list[str]:
    out, cur = [], ""
    for wd in text.split():
        if cur and len(cur) + 1 + len(wd) > per_line:
            out.append(cur)
            cur = wd
        else:
            cur = (cur + " " + wd).strip()
    if cur:
        out.append(cur)
    if len(out) > lines:
        out = out[:lines]
        out[-1] = out[-1].rstrip(".,") + "…"
    return out


def head_events(tpl: str, text: str, handle: str, dur: float, w: int, h: int, top_of_video: int) -> tuple[list[str], list[str]]:
    """(ASS styles, ASS events) for the headline pinned above the clip the whole time."""
    spec = TEMPLATES.get(tpl, {}).get("head")
    text = " ".join((text or "").split())[:120]
    if not spec or not text:
        return [], []
    fs = int(h * spec["size"])
    per = max(12, int((w - 80) / (fs * 0.5)))
    rows = _wrap(text, per)
    boxed = bool(spec.get("box"))
    styles = [f"Style: Head,Poppins,{fs},{_ass_col(spec['text'])},{_ass_col(spec['text'])},{_ass_col(spec['box'] or '#000000')},"
              f"{_ass_col(spec['box'] or '#000000', 0 if boxed else 255)},-1,0,0,0,100,100,0,0,{3 if boxed else 1},{int(fs * 0.3) if boxed else 0},0,7,40,40,0,1"]
    ev = []
    gap = int(h * 0.02)
    line_h = int(fs * 1.25)
    y_text = max(int(h * 0.04), top_of_video - gap - line_h * len(rows))
    left = spec.get("align") == "left"
    x = 44 if left else w // 2
    an = 7 if left else 8
    if spec.get("sub") and handle:
        sfs = int(fs * 0.72)
        styles.append(f"Style: HeadSub,Poppins,{sfs},{_ass_col(spec['sub'])},{_ass_col(spec['sub'])},&H00000000,&HFF000000,0,0,0,0,100,100,0,0,1,0,0,7,40,40,0,1")
        y_sub = y_text - int(sfs * 1.6)
        ev.append(f"Dialogue: 3,0:00:00.00,{_ts(dur)},HeadSub,,0,0,0,,{{\\an{an}\\pos({x},{y_sub})}}{_esc(handle[:40])}")
    if spec.get("tag"):
        tfs = int(fs * 0.8)
        styles.append(f"Style: HeadTag,Poppins,{tfs},&H00FFFFFF,&H00FFFFFF,{_ass_col(spec['tag_box'])},{_ass_col(spec['tag_box'])},-1,0,0,0,100,100,2,0,3,{int(tfs * 0.3)},0,7,40,40,0,1")
        ev.append(f"Dialogue: 3,0:00:00.00,{_ts(dur)},HeadTag,,0,0,0,,{{\\an{an}\\pos({x},{y_text - int(tfs * 1.9)})}}{spec['tag']}")
    for i, row in enumerate(rows):
        ev.append(f"Dialogue: 3,0:00:00.00,{_ts(dur)},Head,,0,0,0,,{{\\an{an}\\pos({x},{y_text + i * line_h})}}{_esc(row)}")
    return styles, ev


def _ts(t: float) -> str:
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def add_to_ass(ass: str | None, styles: list[str], events: list[str], w: int, h: int) -> str | None:
    if not events:
        return ass
    if not ass:
        ass = ("[Script Info]\nScriptType: v4.00+\nPlayResX: %d\nPlayResY: %d\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\n"
               "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
               "\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n") % (w, h)
    head, _, rest = ass.partition("\n[Events]")
    return head.rstrip("\n") + "\n" + "\n".join(styles) + "\n\n[Events]" + rest.rstrip("\n") + "\n" + "\n".join(events) + "\n"
