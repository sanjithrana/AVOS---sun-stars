"""Cutting one clip with ffmpeg: 9:16, one of three layouts, captions burned in when there are words to show."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .. import config

SIZES = {"720p": (720, 1280), "1080p": (1080, 1920)}
LAYOUTS = {"auto": "AI Reframe (streamer cam on top, game below; follows faces)", "game": "Gameplay (steady, sharp, most of the screen)", "blur": "Blurred fill", "zoom": "Zoomed in", "fill": "Fill screen"}
from .templates import LAYOUTS as _FRAMED  # noqa: E402
LAYOUTS.update(_FRAMED)
from .captions import LABELS as CAPTIONS, POPCOL  # noqa: E402,F401
FONT = "DejaVu Sans"


def graph(layout: str, w: int, h: int, ass: str | None, game_ar: float = 4 / 3) -> str:
    if layout == "game":
        gh = max(2, int(min(h, w / game_ar)) // 2 * 2)
        g = (f"[0:v]split[a][b];[a]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=30:5,eq=brightness=-0.08[bg];"
             f"[b]crop='min(iw,ih*{game_ar:.4f})':'min(ih,iw/{game_ar:.4f})',scale={w}:{gh}:flags=lanczos,unsharp=5:5:0.6[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2[v]")
    elif layout == "fill":
        g = f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}[v]"
    elif layout == "zoom":
        g = f"[0:v]scale={int(w * 1.3)}:{int(h * 1.3)}:force_original_aspect_ratio=increase,crop={w}:{h}[v]"
    else:
        g = (f"[0:v]split[a][b];[a]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=30:5[bg];"
             f"[b]scale={w}:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2[v]")
    if ass:
        esc = str(ass).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
        fonts = config.FONTS_DIR
        fd = f":fontsdir='{str(fonts).replace(chr(92), '/').replace(':', chr(92) + ':')}'" if fonts and Path(str(fonts)).is_dir() else ""
        g = g.replace("[v]", "[pre]") + f";[pre]subtitles='{esc}'{fd}[v]"
    return g


def ts(t: float) -> str:
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"




def ass_for(words: list[dict], start: float, end: float, style: str, w: int, h: int, hook: str | None = None, cam_top: float | None = None,
            cap: dict | None = None, brand: dict | None = None, roman: bool = False) -> str | None:
    """The captions (and brand text) for [start, end] as an ASS file: see captions.py for the styles and options."""
    from . import captions
    return captions.build(words, start, end, style, w, h, hook, cam_top, cap, brand, roman)


def media_info(src: str) -> tuple[float, bool]:
    """(seconds, has sound) of a media file; (0, False) when it can't be read."""
    r = subprocess.run([config.ffmpeg(), "-hide_banner", "-i", src], capture_output=True, text=True, timeout=60)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0
    return dur, "Audio:" in r.stderr


def has_audio(src: str) -> bool:
    r = subprocess.run([config.ffmpeg(), "-hide_banner", "-i", src], capture_output=True, text=True, timeout=60)
    return "Audio:" in r.stderr


def cut(src: str, out: str, start: float, end: float, layout: str = "blur", quality: str = "720p", ass_text: str | None = None, plan: dict | None = None,
        edit: dict | None = None, logo: dict | None = None, game_ar: float = 4 / 3, frame: dict | None = None) -> None:
    """edit: the polish spec from polish.plan_edit (zooms, stickers, grade, music) or None for a plain cut.
    logo: {"path", "pos" (tl..br), "size" (% of the width), "opacity" (%)}: a picture burned into every frame.
    frame: {"tpl", "canvas"} from templates.clean: the canvas / template / people layouts (see templates.py)."""
    from . import captions, polish
    w, h = SIZES.get(quality, SIZES["720p"])
    outp = Path(out)
    ass = None
    if ass_text:
        ass = outp.with_suffix(".ass")
        ass.write_text(ass_text, "utf-8")
    asss = None
    if ass:
        esc = str(ass).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
        try:
            fonts = captions.fonts_dir()
        except Exception:  # noqa: BLE001 - captions still render with the system fonts
            fonts = config.FONTS_DIR
        fd = f":fontsdir='{str(fonts).replace(chr(92), '/').replace(':', chr(92) + ':')}'" if fonts and Path(str(fonts)).is_dir() else ""
        asss = f"'{esc}'{fd}"
    imgs: list = []
    if plan and plan.get("scenes"):             # AI Reframe: a layout per scene
        from . import reframe
        g = reframe.graph(plan, w, h, None)
    elif layout in _FRAMED or (frame and frame.get("tpl") not in (None, "none")):
        from . import templates
        fr = frame or {}
        tdef = templates.TEMPLATES.get(fr.get("tpl") or "none", {}).get("layout") or "wide"
        g, imgs = templates.graph(layout if layout in _FRAMED else tdef, fr.get("tpl") or "none", fr.get("canvas") or {"bg": "blur"}, w, h, outp.parent / f".{outp.stem}-canvas", fr.get("overlay"))
    else:
        g = graph(layout if layout in LAYOUTS and layout != "auto" else "blur", w, h, None, game_ar)
    inputs: list[str] = ["-ss", f"{start:.2f}", "-t", f"{end - start:.2f}", "-i", src]
    maps = ["-map", "[v]", "-map", "0:a:0?"]
    assert g.endswith("[v]")
    g = g[:-3] + "[base]"
    last = "[base]"
    if edit:
        audio = has_audio(src)
        pv, extra, alabel = polish.build(edit, w, h, audio, end - start, "[base]", "[pv]")
        inputs += extra
        g += ";" + pv
        last = "[pv]"
        if alabel:
            maps = ["-map", "[v]", "-map", alabel]
    lp = Path(str((logo or {}).get("path") or ""))
    if logo and lp.is_file():                    # the brand logo: scaled to a share of the width, faded to its opacity, in its corner
        idx = sum(1 for x in inputs if x == "-i")
        inputs += ["-loop", "1", "-i", str(lp)]
        lw = _even2(w * max(0.05, min(0.6, float(logo.get("size") or 18) / 100)))
        op = max(0.1, min(1.0, float(logo.get("opacity") or 75) / 100))
        px, py = captions.POSITIONS.get(str(logo.get("pos") or "br"), captions.POSITIONS["br"])
        xe = "24" if px < 0.3 else ("(W-w)/2" if px == 0.5 else "W-w-24")
        ye = "36" if py < 0.3 else ("(H-h)/2" if py == 0.5 else "H-h-48")
        g += f";[{idx}:v]scale={lw}:-1,format=rgba,colorchannelmixer=aa={op:.2f}[lg];{last}[lg]overlay={xe}:{ye}:shortest=1[lgo]"
        last = "[lgo]"
    g += f";{last}subtitles={asss}[v]" if asss else f";{last}null[v]"
    for k, img in enumerate(imgs):              # the canvas pictures go last, so the effect and logo inputs keep their numbers
        g = g.replace(f"{{IMG{k}}}", str(sum(1 for x in inputs if x == "-i")))
        inputs += ["-loop", "1", "-i", str(img)]
    script = outp.with_suffix(".graph")
    script.write_text(g, "utf-8")
    cmd = [config.ffmpeg(), "-v", "error", "-y", "-nostdin", *inputs, "-filter_complex_script", str(script), *maps,
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-t", f"{end - start:.2f}",
           "-movflags", "+faststart", str(outp)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    script.unlink(missing_ok=True)
    if r.returncode != 0 or not outp.is_file():
        tail = [ln.strip() for ln in r.stderr.strip().splitlines() if ln.strip()][-5:] or ["unknown error"]
        raise RuntimeError("ffmpeg could not cut the clip: " + " | ".join(tail)[:700] + f" [input: {Path(src).name}, {start:.1f}s to {end:.1f}s]")
    subprocess.run([config.ffmpeg(), "-v", "error", "-y", "-nostdin", "-ss", "1", "-i", str(outp), "-frames:v", "1", "-vf", "scale=360:-2",
                    str(outp.with_suffix(".jpg"))], capture_output=True, timeout=120)


def _even2(v: float) -> int:
    return max(2, int(v) // 2 * 2)


FONT_FILE = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def cover(video: str, out: str, title: str = "", at: float = 1.2, style: str = "a") -> bool:
    """A thumbnail: a real frame from the clip (not the first, which is usually black) with the title on it in big wrapped letters."""
    import textwrap
    import tempfile
    o = Path(out)
    vf = "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280"
    tf = None
    if title and Path(FONT_FILE).is_file():
        lines = textwrap.wrap(" ".join(title.split()).upper(), 16)[:4]
        tf = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8")
        tf.write("\n".join(lines))
        tf.close()
        if style == "b":              # variant B for tests: the words at the top in yellow, no dark band, a stronger colour grade
            vf += (f",eq=saturation=1.25:contrast=1.08,drawtext=fontfile={FONT_FILE}:textfile={tf.name}:fontcolor=#FFD60A:fontsize=72:"
                   "line_spacing=12:borderw=7:bordercolor=black:x=(w-text_w)/2:y=h*0.08")
        else:
            vf += (f",drawbox=x=0:y=ih*0.56:w=iw:h=ih*0.30:color=black@0.55:t=fill,drawtext=fontfile={FONT_FILE}:textfile={tf.name}:fontcolor=white:fontsize=64:"
                   "line_spacing=10:borderw=5:bordercolor=black:x=(w-text_w)/2:y=h*0.58")
    r = subprocess.run([config.ffmpeg(), "-v", "error", "-y", "-nostdin", "-ss", f"{at}", "-i", video, "-frames:v", "1", "-vf", vf, "-q:v", "3", str(o)],
                       capture_output=True, text=True, timeout=120)
    if tf:
        Path(tf.name).unlink(missing_ok=True)
    return r.returncode == 0 and o.is_file()
