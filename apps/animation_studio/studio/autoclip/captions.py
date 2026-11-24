"""Captions and on-screen branding, written as one ASS subtitle file that ffmpeg burns in.

A *style* is a starting point (font, case, colours, outline, how many words, how they arrive). The *cap* options change any of it per job:
  font, size (% of the style's own), x / y (0..1, where the caption's centre sits), upper, bold, italic, outline (px), shadow (px), glow,
  text / hi (#RRGGBB: the words, and the word being said), offset_ms (captions earlier < 0 < later), anim, words (per line, 1..4).
*brand* adds a burned-in watermark (text; a logo picture is overlaid by cut.py), a lower-third name tag and a "follow" end card.

Rules that always hold: one caption on screen at a time, one line (a long line gets a smaller font, it never wraps or runs off the frame),
and the junk YouTube puts in auto-captions ([ __ ] bleeps, >> marks, [Music]) is dropped."""
from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

ASSETS = Path(__file__).parent / "assets" / "fonts"

# family name (what ASS asks for) -> (file in assets, average glyph width as a share of the font size, natural weight is bold)
FONTS: dict[str, tuple[str, float, bool]] = {
    "Poppins": ("Poppins-Bold.ttf", 0.62, True),
    "Montserrat Black": ("Montserrat-Black.ttf", 0.72, False),
    "Montserrat ExtraBold": ("Montserrat-ExtraBold.ttf", 0.70, False),
    "Anton": ("Anton-Regular.ttf", 0.47, False),
    "Bebas Neue": ("BebasNeue.ttf", 0.42, False),
    "Bangers": ("Bangers.ttf", 0.52, False),
    "Luckiest Guy": ("LuckiestGuy.ttf", 0.74, False),
    "Oswald": ("Oswald-Bold.ttf", 0.50, True),
    "Archivo Black": ("ArchivoBlack-Regular.ttf", 0.74, False),
    "Lilita One": ("LilitaOne.ttf", 0.56, False),
    "Permanent Marker": ("PermanentMarker.ttf", 0.64, False),
    "Playfair Display": ("PlayfairDisplay-Bold.ttf", 0.56, True),
    "DM Serif Display": ("DMSerifDisplay.ttf", 0.5, False),
    "Pacifico": ("Pacifico.ttf", 0.6, False),
    "JetBrains Mono": ("JetBrainsMono-Bold.ttf", 0.62, True),
    "Inter ExtraBold": ("Inter-ExtraBold.ttf", 0.62, False),
    "Kanit Black": ("Kanit-BlackItalic.ttf", 0.66, False),
    "Baloo 2 ExtraBold": ("Baloo2-ExtraBold.ttf", 0.58, False),
    "Noto Sans Devanagari": ("NotoSansDevanagari-Bold.ttf", 0.62, True),
    "DejaVu Sans": ("", 0.66, True),
}
ANIMS = {"none": "None", "fade": "Fade in", "slide": "Slide up", "pop": "Pop", "zoom": "Zoom", "bounce": "Soft bounce", "elastic": "Elastic",
         "pulse": "Pulse", "karaoke": "Karaoke fill", "typewriter": "Typewriter", "shake": "Shake"}
MODES = {"": "Style default", "pop_in": "Pop-In (one word)", "pop_line": "Pop-In Line", "one_by_one": "One by one", "build_up": "Build up",
         "highlight": "Highlight box", "full_line": "Full line (two lines)"}
POPCOL = ["&H0050E050", "&H002020FF", "&H0000F0FF", "&H00FFFFFF"]      # green, red, yellow, white: the colour moves on with every word

W, Y, R, G, C, K = "&H00FFFFFF", "&H0000F0FF", "&H002020FF", "&H0040FF7A", "&H00FFE600", "&H00000000"
from .caption_styles import STYLES  # noqa: E402  (the library of looks: plain data)
LABELS = {k: v["label"] for k, v in STYLES.items()} | {"none": "No captions"}
POSITIONS = {"tl": (0.08, 0.06), "tc": (0.5, 0.06), "tr": (0.92, 0.06), "ml": (0.08, 0.5), "mc": (0.5, 0.5), "mr": (0.92, 0.5),
             "bl": (0.08, 0.93), "bc": (0.5, 0.93), "br": (0.92, 0.93)}
DEFAULT_Y = 0.77


# ---------- fonts ----------
def user_fonts() -> Path:
    from . import store
    p = store.ROOT / "fonts"
    p.mkdir(parents=True, exist_ok=True)
    return p


def fonts_dir() -> Path:
    """One folder with every font a caption can ask for: the bundled ones, the studio's caption fonts and the ones you uploaded (libass reads one folder)."""
    from .. import config
    from . import store
    out = store.ROOT / "fonts_all"
    out.mkdir(parents=True, exist_ok=True)
    srcs = [ASSETS, user_fonts()]
    if config.FONTS_DIR and Path(str(config.FONTS_DIR)).is_dir():
        srcs.append(Path(str(config.FONTS_DIR)))
    for d in srcs:
        for f in d.iterdir():
            if f.suffix.lower() in (".ttf", ".otf") and not (out / f.name).is_file():
                shutil.copy2(f, out / f.name)
    return out


def family_of(path: Path) -> str:
    """The family name inside a .ttf/.otf (name table, id 16 if present, else 1), so an uploaded font can be asked for by name."""
    import struct
    data = path.read_bytes()
    try:
        n = struct.unpack(">H", data[4:6])[0]
        for i in range(n):
            tag, _, off, _ = struct.unpack(">4sLLL", data[12 + 16 * i: 28 + 16 * i])
            if tag != b"name":
                continue
            _, count, so = struct.unpack(">HHH", data[off: off + 6])
            names: dict[int, str] = {}
            for k in range(count):
                pid, eid, lid, nid, ln, no = struct.unpack(">HHHHHH", data[off + 6 + 12 * k: off + 18 + 12 * k])
                if nid not in (1, 16):
                    continue
                raw = data[off + so + no: off + so + no + ln]
                s = raw.decode("utf-16-be", "ignore") if pid in (0, 3) else raw.decode("latin-1", "ignore")
                if s and (nid not in names or pid == 3):
                    names[nid] = s
            return (names.get(16) or names.get(1) or path.stem).strip()
    except Exception:  # noqa: BLE001
        pass
    return path.stem


def font_list() -> list[dict]:
    """Fonts to pick from: the bundled ones, then yours."""
    out = [{"name": k, "mine": False, "file": v[0]} for k, v in FONTS.items() if v[0]]
    for f in sorted(user_fonts().iterdir()):
        if f.suffix.lower() in (".ttf", ".otf"):
            out.append({"name": family_of(f), "mine": True, "file": f.name})
    return out


# ---------- small helpers ----------
def ass_colour(v: Any, default: str) -> str:
    """'#RRGGBB' (or an ASS colour already) -> ASS &H00BBGGRR."""
    s = str(v or "").strip()
    if re.fullmatch(r"&H[0-9A-Fa-f]{8}", s):
        return s.upper().replace("&H", "&H")
    m = re.fullmatch(r"#?([0-9A-Fa-f]{6})", s)
    if not m:
        return default
    rr, gg, bb = m.group(1)[0:2], m.group(1)[2:4], m.group(1)[4:6]
    return f"&H00{bb}{gg}{rr}".upper()


def box_colour(v: str) -> tuple[str, str]:
    """'#RRGGBB' or '#RRGGBBAA' (AA = how solid) -> (ASS colour, ASS alpha)."""
    m = re.fullmatch(r"#?([0-9A-Fa-f]{6})([0-9A-Fa-f]{2})?", str(v or ""))
    if not m:
        return K, "&H00&"
    a = 255 - int(m.group(2), 16) if m.group(2) else 0
    return ass_colour("#" + m.group(1), K), f"&H{a:02X}&"


def ts(t: float) -> str:
    cs = int(round(max(0.0, t) * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def esc(t: str) -> str:
    return str(t).replace("{", "(").replace("}", ")").replace("\\", "")


def _num(v: Any, lo: float, hi: float, default: float) -> float:
    try:
        return max(lo, min(hi, float(v)))
    except (TypeError, ValueError):
        return default


def _bool(v: Any, default: bool) -> bool:
    if v is None or v == "":
        return default
    return str(v).lower() in ("1", "true", "yes", "on")


def resolve(style: str, cap: dict | None = None) -> dict:
    """The style with the job's changes applied. Unknown keys and out-of-range values are ignored."""
    st = dict(STYLES.get(style) or STYLES["bounce"])
    c = cap or {}
    known = {f["name"] for f in font_list()}
    if c.get("font") and str(c["font"]) in known:
        st["font"] = str(c["font"])
    st["scale"] = _num(c.get("size"), 50, 160, 100) / 100
    st["x"] = _num(c.get("x"), 0.05, 0.95, 0.5)
    st["y"] = _num(c.get("y"), 0.05, 0.95, DEFAULT_Y)
    st["user_y"] = c.get("y") not in (None, "")
    st["upper"] = _bool(c.get("upper"), st["upper"])
    st["italic"] = _bool(c.get("italic"), bool(st.get("italic")))
    st["bold"] = _bool(c.get("bold"), st["bold"] if "bold" in st else FONTS.get(st["font"], ("", 0.6, True))[2])
    st["outline"] = _num(c.get("outline"), 0, 16, st["outline"])
    st["shadow"] = _num(c.get("shadow"), 0, 8, st["shadow"])
    st["text"] = ass_colour(c.get("text") or st["text"], W)
    st["hi"] = "cycle" if st["hi"] == "cycle" and not c.get("hi") else ass_colour(c.get("hi") or st["hi"], Y)
    st["glow"] = st.get("glow") if not _bool(c.get("glow"), True) is False else None
    if _bool(c.get("glow"), False) and not st.get("glow"):
        st["glow"] = c.get("hi") or "#00E6FF"
    st["offset"] = _num(c.get("offset_ms"), -1000, 1000, 0) / 1000
    if c.get("anim") in ANIMS:
        st["anim"] = c["anim"]
    st["words"] = int(_num(c.get("words"), 1, 4, st["words"]))
    mode = str(c.get("mode") or "")
    if mode == "pop_in":
        st.update(anim="pop", words=1)
    elif mode == "pop_line":
        st.update(anim="pop", words=4)
    elif mode == "one_by_one":
        st.update(anim="none", words=1)
    elif mode == "build_up":                                  # the line builds word by word as it is said
        st.update(anim="typewriter", words=max(4, st["words"]))
    elif mode == "highlight":
        st.update(hi_box=st.get("hi_box") or "#FFE000", hi="&H00111111", words=max(3, st["words"]))
    elif mode == "full_line":                                 # the whole sentence, two lines broken at a comma or the middle
        st.update(layout="two", words=10, anim=st["anim"] if st["anim"] != "typewriter" else "none")
    return st


def _width(font: str, upper: bool) -> float:
    return FONTS.get(font, ("", 0.62, True))[1] * (1.1 if upper else 1.0)


def fit(n_chars: int, size: int, w: int, font: str, upper: bool, margin: int = 50) -> int:
    """The font size at which n_chars fit on one line inside the side margins."""
    room = w - 2 * margin
    return max(int(size * 0.45), min(size, int(room / max(1, n_chars) / _width(font, upper))))


def _dedupe(ws: list[dict]) -> list[dict]:
    """Words in time order, once each: YouTube's rolling auto-captions repeat each line in the next cue."""
    out: list[dict] = []
    for w in sorted(ws, key=lambda x: (x["s"], x["e"])):
        if out and w["w"].lower() == out[-1]["w"].lower() and w["s"] < out[-1]["e"] + 0.3:
            continue
        if out and w["s"] < out[-1]["s"] + 0.04:
            continue
        out.append(w)
    return out


# ---------- the file ----------
def _key(grp: list[dict]) -> int:
    """The key word of a caption: the longest one (it carries the meaning), the first of equals."""
    ln = [len(re.sub(r"\W", "", z["w"])) for z in grp]
    return ln.index(max(ln)) if ln else 0


def _lines(grp: list[dict], layout: str, kw: int) -> list[list[int]]:
    n = len(grp)
    idx = list(range(n))
    if layout in ("top", "bottom", "mid") and n > 1:
        rest = [i for i in idx if i != kw]
        if layout == "top":
            return [[kw], rest]
        if layout == "bottom":
            return [rest, [kw]]
        return [x for x in ([i for i in idx if i < kw], [kw], [i for i in idx if i > kw]) if x]
    if layout in ("each", "cascade"):
        return [[i] for i in (sorted(idx, key=lambda i: i != kw) if layout == "cascade" else idx)]
    if layout in ("two", "twokw") and n > 2:
        h2 = (n + 1) // 2
        marks = [i + 1 for i in range(n - 1) if str(grp[i]["w"]).rstrip().endswith((",", ";", ":", ".", "?", "!", "—"))]
        near = [m for m in marks if abs(m - h2) <= max(1, n // 4)]
        if near:                                              # break where the speaker pauses, not mid-phrase
            h2 = min(near, key=lambda m: abs(m - h2))
        return [idx[:h2], idx[h2:]]
    return [idx]


def build(words: list[dict], start: float, end: float, style: str, w: int, h: int, hook: str | None = None, cam_top: float | None = None,
          cap: dict | None = None, brand: dict | None = None, roman: bool = False) -> str | None:
    from .transcript import clean_words
    ws = _dedupe(clean_words([x for x in words if x["e"] > start and x["s"] < end])) if style != "none" else []
    if roman and ws:
        from .translit import roman_words
        ws = roman_words(ws)
    hook = " ".join((hook or "").split())[:60]
    br = brand or {}
    has_brand = bool((br.get("wm") or {}).get("kind") == "text" and (br.get("wm") or {}).get("text")) or bool((br.get("end") or {}).get("on")) or bool((br.get("lower") or {}).get("on"))
    if not ws and not hook and not has_brand:
        return None
    st = resolve(style if style in STYLES else "bounce", cap)
    dur = max(0.5, end - start)
    upper, font = st["upper"], st["font"]
    size = int(h * st["size"] * st["scale"])
    outline = int(round(st["outline"] * st["scale"]))
    hi_cycle = st["hi"] == "cycle"
    hi = Y if hi_cycle else st["hi"]
    text = st["text"]
    glow = st.get("glow")
    out_col = ass_colour(st.get("out") or (glow if glow else "#000000"), K)
    bold, italic = -1 if st["bold"] else 0, -1 if st["italic"] else 0
    boxed = bool(st.get("box") or st.get("tiles") or st.get("hi_box"))
    if boxed:                                     # boxes are drawn with the opaque-box border; the box colour is set per word
        bcol, balpha = box_colour(st.get("box") or "#00000000")
    pad = max(6, int(size * 0.16))
    hook_size = int(h * 0.042)
    hook_v = int(h * 0.05) if cam_top else int(h * 0.12)        # with a cam on top the hook sits at the very top; the seam is for the captions
    hook_font = font if font in FONTS else "Poppins"
    head = ("[Script Info]\nScriptType: v4.00+\nPlayResX: %d\nPlayResY: %d\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
            "Style: Default,%s,%d,%s,%s,%s,&H64000000,%d,%d,0,0,100,100,%d,0,%d,%d,%d,5,50,50,0,1\n"
            "Style: Hook,%s,%d,&H0000F0FF,&H0000F0FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,5,2,8,50,50,%d,1\n"
            "Style: Brand,Poppins,%d,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,1,5,30,30,0,1\n"
            "Style: Lower,Poppins,%d,&H00FFFFFF,&H00FFFFFF,&H50000000,&H50000000,-1,0,0,0,100,100,0,0,3,14,0,4,40,40,0,1\n"
            "Style: End,Poppins,%d,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,4,2,5,40,40,0,1\n\n[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n") % (
        w, h, font, size, text, text, (bcol if boxed else out_col), bold, italic, int(st.get("spacing") or 0), (3 if boxed else 1), (pad if boxed else outline), int(st["shadow"]),
        hook_font, hook_size, hook_v, int(h * 0.026), int(h * 0.034), int(h * 0.05))
    lines: list[str] = []
    if hook:
        hw = hook.upper().split()
        if len(hook) > 24 and len(hw) > 1:
            cut_at = min(range(1, len(hw)), key=lambda i: abs(len(" ".join(hw[:i])) - len(" ".join(hw[i:]))))
            ht, longest = esc(" ".join(hw[:cut_at])) + "\\N" + esc(" ".join(hw[cut_at:])), max(len(" ".join(hw[:cut_at])), len(" ".join(hw[cut_at:])))
        else:
            ht, longest = esc(" ".join(hw)), len(hook)
        fs = fit(longest, hook_size, w, hook_font, True)
        lines.append(f"Dialogue: 1,{ts(0)},{ts(min(2.8, max(1.0, dur)))},Hook,,0,0,0,,{{\\fad(120,250)\\fs{fs}}}{ht}")
    # the words, a few at a time
    off = st["offset"]
    sh = [{**x, "s": x["s"] + off, "e": x["e"] + off} for x in ws]
    layout = st.get("layout") or "line"
    multi = layout not in ("line", "inline")
    maxc = int((16 if upper else 20) * (1.0 if st["scale"] <= 1 else 1 / st["scale"]) * (1.6 if multi else 1) + 0.5)
    if layout == "twokw":
        maxc = int(56 * (1.0 if st["scale"] <= 1 else 1 / st["scale"]))
    groups: list[list[dict]] = []
    cur: list[dict] = []
    for wd in sh:
        ends = bool(cur) and str(cur[-1]["w"]).rstrip("\"'”’)").endswith((".", "!", "?", ",", ";", ":", "—", "…", "।"))
        if cur and (ends or len(cur) >= st["words"] or sum(len(x["w"]) + 1 for x in cur) + len(wd["w"]) > maxc or wd["s"] - cur[-1]["e"] > 0.9):
            groups.append(cur)
            cur = []
        cur.append(wd)
    if cur:
        groups.append(cur)
    x, y = int(st["x"] * w), int(st["y"] * h)
    if not st["user_y"]:
        y = int((0.72 if multi else DEFAULT_Y) * h)
        if cam_top:                                           # streamer on top: the captions sit on the line between the cam and the game
            y = int(cam_top * h)          # a two- or three-line caption sits a little higher, clear of YouTube's title
    anim = st["anim"]
    kwmode = layout in ("top", "bottom", "mid", "inline", "cascade", "twokw")
    kcol = ass_colour(st.get("kw") or "", hi)
    rcol = ass_colour(st.get("rest") or "", text)
    tiles = [box_colour(c) for c in (st.get("tiles") or [])]
    tile_text = ass_colour(st.get("tile_text") or "", text)
    hbox = box_colour(st["hi_box"]) if st.get("hi_box") else None
    order = {id(wd): i for i, wd in enumerate(sh)}
    ev: list[list] = []
    for grp in groups:
        kw = _key(grp)
        rows = _lines(grp, layout, kw)
        g1 = min(end, grp[-1]["e"] + 0.25) - start
        states = [-1] if anim == "karaoke" else list(range(len(grp)))
        for j in states:
            a = (max(start, grp[0]["s"]) if j < 0 else max(start, grp[j]["s"])) - start
            b = g1 if j < 0 else ((grp[j + 1]["s"] if j + 1 < len(grp) else min(end, grp[j]["e"] + 0.25)) - start)
            enter = ""
            if j <= 0:
                enter = {"fade": "\\fad(140,0)", "slide": f"\\move({x},{y + int(h * 0.03)},{x},{y},0,160)", "zoom": "\\fscx70\\fscy70\\t(0,150,\\fscx100\\fscy100)",
                         "elastic": "\\fscx135\\fscy135\\t(0,90,\\fscx92\\fscy92)\\t(90,190,\\fscx100\\fscy100)",
                         "shake": "\\t(0,50,\\frz4)\\t(50,100,\\frz-4)\\t(100,150,\\frz2)\\t(150,200,\\frz0)"}.get(anim, "")
            out_rows = []
            for ri, row in enumerate(rows):
                is_kw_row = kwmode and layout != "inline" and kw in row
                if layout == "cascade":
                    scale = st.get("kw_scale", 1.5) if ri == 0 else max(0.45, st.get("rest_scale", 0.6) * (1.0 - 0.15 * (ri - 1)))
                elif layout == "twokw":                       # a plain two-line subtitle: same size, only the key word in colour
                    scale = 1.0
                elif kwmode and layout != "inline":
                    scale = st.get("kw_scale", 1.6) if is_kw_row else max(0.62, st.get("rest_scale", 0.55))      # the small words stay readable on a phone
                else:
                    scale = 1.0
                row_txt = [grp[i]["w"].upper() if (upper or (is_kw_row and st.get("kw_upper"))) else grp[i]["w"] for i in row]
                rfont = (st.get("kw_font") if is_kw_row else st.get("rest_font")) or font
                fs = fit(len(" ".join(row_txt)), int(size * scale), w, rfont, upper)
                parts = []
                for pos_i, i in enumerate(row):
                    q = grp[i]
                    t = esc(row_txt[pos_i])
                    sp = []
                    isk = kwmode and i == kw
                    spoken = (j == i) if j >= 0 else False
                    if layout == "inline":
                        sp.append(f"\\fs{fit(len(t), int(size * (st.get('kw_scale', 1.4) if isk else st.get('rest_scale', 0.75))), w, font, upper)}")
                    if kwmode:
                        col = kcol if isk else rcol
                        if isk and st.get("kw_font"):
                            sp.append(f"\\fn{st['kw_font']}")
                        if isk and st.get("kw_italic"):
                            sp.append("\\i1")
                    else:
                        col = (POPCOL[order.get(id(q), 0) % len(POPCOL)] if hi_cycle else hi) if spoken else text
                    if tiles:
                        tc, ta = tiles[i % len(tiles)]
                        sp.append(f"\\3c{tc}\\3a{ta}")
                        col = tile_text if not spoken or len(tiles) > 1 else hi
                    elif hbox:
                        sp.append(f"\\3c{hbox[0]}\\3a{hbox[1] if spoken else '&HFF&'}")
                        if spoken:
                            col = hi
                    sp.append(f"\\c{col}")
                    if spoken:
                        if st.get("underline"):
                            sp.append("\\u1")
                        if st.get("hi_font"):
                            sp.append(f"\\fn{st['hi_font']}")
                        if st.get("hi_italic"):
                            sp.append("\\i1")
                        sp.append({"bounce": "\\t(0,90,\\fscx115\\fscy115)\\t(90,180,\\fscx100\\fscy100)", "pop": "\\t(0,80,\\fscx122\\fscy122)\\t(80,170,\\fscx100\\fscy100)",
                                   "pulse": "\\t(0,120,\\fscx110\\fscy110)\\t(120,240,\\fscx100\\fscy100)"}.get(anim, ""))
                    elif j >= 0:
                        if st.get("dim"):
                            sp.append(f"\\alpha&H{int(st['dim']):02X}&")
                        if st.get("blur"):
                            sp.append(f"\\blur{int(st['blur'])}")
                        if anim == "typewriter" and i > j:
                            sp.append("\\alpha&HFF&")
                    if anim == "karaoke":
                        k = max(1, int(round((q["e"] - q["s"]) * 100)))
                        sp = [f"\\kf{k}\\1c{hi}\\2c{text if not kwmode else (kcol if isk else rcol)}"] + [z for z in sp if not z.startswith("\\c")]
                    reset = "\\u0\\i0\\alpha&H00&\\blur0\\fscx100\\fscy100" + (f"\\fn{font}" if (st.get("hi_font") or st.get("kw_font")) else "")
                    space = ("{\\3a&HFF&} " if (tiles or hbox) else " ") if pos_i < len(row) - 1 else ""
                    parts.append("{" + "".join(sp) + "}" + t + "{" + reset + (f"\\3c{bcol}\\3a{balpha}" if boxed else "") + "}" + space)
                out_rows.append((f"{{\\fs{fs}}}" if fs != size else "") + "".join(parts))
            gl = f"\\blur3" if glow else ""
            ev.append([a, b, f"{{\\an5\\pos({x},{y}){gl}{enter}}}" + "\\N".join(out_rows)])
    ev.sort(key=lambda e: e[0])
    for i, e in enumerate(ev):                    # one caption at a time
        if i + 1 < len(ev):
            e[1] = min(e[1], ev[i + 1][0])
        e[0] = max(0.0, e[0])
        if e[1] - e[0] < 0.06:
            continue
        if st.get("glitch") or st.get("echo"):      # extra copies behind the words (same layer, written first, so drawn underneath)
            plain = re.sub(r"\\(?:1?c|3c|alpha|3a)&H[0-9A-Fa-f]+&", "", e[2])
            copies = [("&H0000FF&", -4, 0, "&H70&"), ("&H00FFFF00&", 4, 0, "&H70&")] if st.get("glitch") else [("&H00FFFFFF&", 0, int(size * 0.18), "&HB0&"), ("&H00FFFFFF&", 0, int(size * 0.36), "&HD8&")]
            for col, dx, dy, al in copies:
                cp = plain.replace(f"\\pos({x},{y})", f"\\pos({x + dx},{y + dy})", 1)
                lines.append(f"Dialogue: 0,{ts(e[0])},{ts(e[1])},Default,Echo,0,0,0,,{{\\1c{col}\\3a&HFF&\\4a&HFF&\\alpha{al}}}" + cp)
        lines.append(f"Dialogue: 0,{ts(e[0])},{ts(e[1])},Default,,0,0,0,,{e[2]}")
    lines += brand_events(br, dur, w, h)
    return head + "\n".join(lines) + "\n"


def brand_events(br: dict, dur: float, w: int, h: int) -> list[str]:
    """Watermark text (whole clip), lower-third name tag, end card. The logo picture is overlaid in cut.py, not here."""
    out: list[str] = []
    wm = br.get("wm") or {}
    if wm.get("kind") == "text" and str(wm.get("text") or "").strip():
        px, py = POSITIONS.get(str(wm.get("pos") or "br"), POSITIONS["br"])
        an = {0.08: 4, 0.5: 5, 0.92: 6}[px] if py == 0.5 else ({0.08: 7, 0.5: 8, 0.92: 9}[px] if py < 0.5 else {0.08: 1, 0.5: 2, 0.92: 3}[px])
        fs = int(h * 0.026 * _num(wm.get("size"), 40, 300, 100) / 100)
        alpha = 255 - int(255 * _num(wm.get("opacity"), 10, 100, 75) / 100)
        out.append(f"Dialogue: 2,{ts(0)},{ts(dur)},Brand,,0,0,0,,{{\\an{an}\\pos({int(px * w)},{int(py * h)})\\fs{fs}\\alpha&H{alpha:02X}&}}{esc(str(wm['text']).strip()[:40])}")
    lo = br.get("lower") or {}
    if lo.get("on") and str(lo.get("name") or "").strip():
        t0 = _num(lo.get("at"), 0, max(0.0, dur - 1), 0.6)
        t1 = min(dur, t0 + _num(lo.get("secs"), 1, 10, 3))
        sub = esc(str(lo.get("sub") or "").strip()[:40])
        name = esc(str(lo["name"]).strip()[:30])
        txt = name + (f"\\N{{\\fs{int(h * 0.022)}\\c&H0000F0FF&}}{sub.upper()}" if sub else "")
        out.append(f"Dialogue: 3,{ts(t0)},{ts(t1)},Lower,,0,0,0,,{{\\an4\\pos({int(w * 0.07)},{int(h * 0.62)})\\move({-int(w * 0.3)},{int(h * 0.62)},{int(w * 0.07)},{int(h * 0.62)},0,250)\\fad(0,200)}}{txt}")
    en = br.get("end") or {}
    if en.get("on") and str(en.get("text") or "").strip():
        secs = _num(en.get("secs"), 1, 5, 2)
        t0 = max(0.0, dur - secs)
        box = f"m 0 0 l {w} 0 {w} {h} 0 {h}"
        out.append(f"Dialogue: 4,{ts(t0)},{ts(dur)},End,,0,0,0,,{{\\an7\\pos(0,0)\\1c&H000000&\\1a&H38&\\bord0\\shad0\\fad(250,0)\\p1}}{box}{{\\p0}}")
        main = esc(str(en["text"]).strip()[:40])
        fs = fit(len(main), int(h * 0.05), w, "Poppins", False)
        sub = esc(str(en.get("sub") or "").strip()[:50])
        out.append(f"Dialogue: 5,{ts(t0)},{ts(dur)},End,,0,0,0,,{{\\an5\\pos({w // 2},{int(h * 0.47)})\\fs{fs}\\fad(250,0)\\fscx80\\fscy80\\t(0,220,\\fscx100\\fscy100)}}{main}")
        if sub:
            out.append(f"Dialogue: 5,{ts(t0)},{ts(dur)},End,,0,0,0,,{{\\an5\\pos({w // 2},{int(h * 0.54)})\\fs{int(h * 0.026)}\\c&H0000F0FF&\\fad(400,0)}}{sub}")
    return out
