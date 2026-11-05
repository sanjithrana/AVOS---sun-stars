"""Render a whole shot to MP4 (+ review sheet, character crops and measurements), character sheets and stills."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable

import numpy as np
import skia
from PIL import Image, ImageDraw, ImageFont

from .. import config
from . import actions, rig
from .backgrounds import Background
from .color import skc
from .pen import Pen
from .scene import Ctx, render_frame
from .text import draw_line, typeface


def size_for(plan: dict) -> tuple[int, int]:
    f = plan.get("format") or {}
    w, h = int(f.get("width") or 1920), int(f.get("height") or 1080)
    q = config.render_settings()["quality"]
    long_side = 1920 if q == "1080p" else 1280
    k = long_side / max(w, h)
    W, H = int(round(w * k / 2) * 2), int(round(h * k / 2) * 2)
    return max(320, W), max(320, H)


def _font(size: int) -> ImageFont.ImageFont:
    for f in ("DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except Exception:
            continue
    return ImageFont.load_default()


def render_shot(spec: dict, ctx: Ctx, out_mp4: Path, fps: int = 24, handle: float = 0.0,
                progress: Callable[[float], None] | None = None, abort: Callable[[], bool] | None = None) -> dict:
    W, H = ctx.W, ctx.H
    dur = spec["duration"] + handle
    n = max(1, int(round(dur * fps)))
    step = max(1, int(ctx.lk.get("step", 1)))
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    cmd = [config.ffmpeg(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out_mp4)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    bg = Background(spec["setting"], ctx.roles, spec["time"], W, H, ctx.lk, seed=ctx.seed,
                    no_sky={p["kind"] for p in spec["props"] if p["kind"] in ("moon", "sun")})
    samples, luma, diff = [], [], []
    sample_every = max(1, int(fps * 0.25))
    last = None
    prev_small = None
    try:
        for i in range(n):
            if abort and abort():
                raise RuntimeError("cancelled")
            if i % step == 0 or last is None:
                t = (i - i % step) / fps
                img, m = render_frame(spec, ctx, t, i - i % step, bg)
                last = img
                if i % sample_every == 0 or i == n - 1:
                    samples.append(m)
            img = last
            proc.stdin.write(img.tobytes())  # type: ignore[union-attr]
            small = img[::8, ::8].astype(np.float32)
            luma.append(float(small.mean()))
            diff.append(float(np.abs(small - prev_small).mean()) if prev_small is not None else 0.0)
            prev_small = small
            if progress and i % 12 == 0:
                progress(i / n)
        proc.stdin.close()  # type: ignore[union-attr]
        err = proc.stderr.read().decode(errors="replace")  # type: ignore[union-attr]
        if proc.wait() != 0:
            raise RuntimeError(f"ffmpeg failed: {err[-400:]}")
    except BaseException:
        proc.kill()
        raise
    return {"id": spec.get("id"), "duration": spec["duration"], "handle": handle, "fps": fps, "frames": n, "W": W, "H": H,
            "samples": samples, "luma": luma, "diff": diff, "blank": _blank_ratio(last) if last is not None else 0.0}


def _blank_ratio(img: np.ndarray, tile: int = 40) -> float:
    h, w = img.shape[:2]
    g = img.mean(axis=2)
    n = flat = 0
    for y in range(0, h - tile + 1, tile):
        for x in range(0, w - tile + 1, tile):
            n += 1
            if g[y:y + tile, x:x + tile].std() < 2.5:
                flat += 1
    return flat / max(1, n)


def still(spec: dict, ctx: Ctx, t: float, out: Path, frame: int | None = None) -> dict:
    img, m = render_frame(spec, ctx, t, frame if frame is not None else int(t * 24))
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(img).save(out, quality=90)
    return m


def shot_sheet(spec: dict, ctx: Ctx, out: Path, n: int = 6) -> list[dict]:
    """A strip of n moments of the shot with timestamps (what a reviewer looks at)."""
    dur = spec["duration"]
    tw = 480
    th = int(tw * ctx.H / ctx.W)
    cols = 3
    rows = (n + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw + (cols + 1) * 8, rows * (th + 26) + 8), (24, 24, 28))
    d = ImageDraw.Draw(sheet)
    f = _font(16)
    ms = []
    for i in range(n):
        t = dur * (i + 0.5) / n
        img, m = render_frame(spec, ctx, t, int(t * 24))
        ms.append(m)
        im = Image.fromarray(img).resize((tw, th), Image.LANCZOS)
        x, y = 8 + (i % cols) * (tw + 8), 8 + (i // cols) * (th + 26)
        sheet.paste(im, (x, y))
        d.text((x + 4, y + th + 4), f"{spec.get('id', '')}  {t:.2f}s", fill=(230, 230, 235), font=f)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, quality=88)
    return ms


def crop(spec: dict, ctx: Ctx, t: float, box: list[float], out: Path, pad: float = 0.15) -> Path:
    img, _ = render_frame(spec, ctx, t, int(t * 24))
    h, w = img.shape[:2]
    x0, y0, x1, y1 = box
    px, py = (x1 - x0) * pad, (y1 - y0) * pad
    x0, y0, x1, y1 = max(0, int(x0 - px)), max(0, int(y0 - py)), min(w, int(x1 + px)), min(h, int(y1 + py))
    if x1 - x0 < 8 or y1 - y0 < 8:
        x0, y0, x1, y1 = 0, 0, w, h
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(img[y0:y1, x0:x1]).save(out)
    return out


# ---------- character sheets ----------
def _label(c: skia.Canvas, text: str, x: float, y: float, size: float = 18, color: str = "#55556A") -> None:
    tf = typeface("inter")
    draw_line(c, text, x, y, tf, size, color)


def cast_sheet(cd: dict, lk: dict, roles: dict, out: Path, poses: list[str] | None = None, expressions: list[str] | None = None) -> dict:
    """Front / 3/4 / side, 8 expressions and the poses this film uses. Returns a measurement report for the reviewer."""
    W, H = 1800, 1100
    surf = skia.Surface.MakeRaster(skia.ImageInfo.Make(W, H, skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType))
    c = surf.getCanvas()
    paper = "#FFFFFF" if lk["look"] == "whiteboard" else "#FAF7F0"
    c.clear(skc(paper))
    _label(c, f"{cd['name']}  ·  {cd['id']}", 30, 44, 30, "#2A2430")
    _label(c, (cd.get("design") or "")[:110], 30, 76, 17)
    report = {"views": [], "expressions": [], "poses": []}

    def put(x: float, y: float, s: float, pose: rig.Pose, expr: str, label: str, kind: str) -> None:
        pen = Pen(c, lk, 0, aa=lk["look"] != "pixel", line_color=cd["colors"]["line"])
        c.save()
        c.translate(x, y)
        c.scale(s, s)
        dr = rig.draw(pen, cd, pose, expr, 0.6)
        m = c.getTotalMatrix()
        c.restore()
        pen.flush()
        b = m.mapRect(dr.bounds)
        report[kind].append({"label": label, "box": [b.left(), b.top(), b.right(), b.bottom()]})
        _label(c, label, x - 40, y + 34, 16)
    # turnaround
    for i, (turn, lab) in enumerate(((0.0, "front"), (0.5, "3/4"), (1.0, "side"))):
        p = actions.pose_for("idle", 0.0, 3)
        p.turn = turn
        p.blink = False
        put(140 + i * 230, 470, 3.3 * (1 / cd["height"] ** 0.3), p, "neutral", lab, "views")
    # expressions: head close-ups
    exprs = (expressions or cd.get("expressions") or [])[:8]
    exprs = (exprs + [e for e in ("happy", "laugh", "sad", "surprised", "angry", "love", "shy", "scream") if e not in exprs])[:8]
    for i, e in enumerate(exprs):
        p = actions.pose_for("idle", 0.0, 3)
        p.blink = False
        x, y = 900 + (i % 4) * 225, 250 + (i // 4) * 250
        c.save()
        c.clipRect(skia.Rect.MakeXYWH(x - 105, y - 220, 210, 225))
        put(x, y + 210 if cd["body"] != "tall" else y + 330, 4.2 if cd["body"] != "tall" else 5.5, p, e, "", "expressions")
        c.restore()
        _label(c, e, x - 30, y + 26, 16)
    # poses
    plist = list(dict.fromkeys((poses or []) + (cd.get("poses") or [])))[:7]
    for i, a in enumerate(plist):
        p = actions.pose_for(a, 0.55, 3)
        put(110 + i * 245, 1010, 2.6 * (1 / cd["height"] ** 0.3), p, actions.ACTION_EXPR.get(actions.canon(a), "happy"), a, "poses")
    out.parent.mkdir(parents=True, exist_ok=True)
    img = surf.makeImageSnapshot().toarray()[..., :3]
    Image.fromarray(img).save(out, quality=90)
    report["size"] = [W, H]
    return report


def lineup_sheet(cast: list[dict], lk: dict, out: Path) -> dict:
    W, H = 1800, 900
    surf = skia.Surface.MakeRaster(skia.ImageInfo.Make(W, H, skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType))
    c = surf.getCanvas()
    c.clear(skc("#FFFFFF" if lk["look"] == "whiteboard" else "#FAF7F0"))
    p = skia.Paint(AntiAlias=True, Color=skc("#C9C4D6"), StrokeWidth=1.5)
    for k in range(0, 6):
        y = 800 - k * 120
        c.drawLine(40, y, W - 40, y, p)
    n = max(1, len(cast))
    boxes = []
    for i, cd in enumerate(cast):
        x = W * (i + 0.5) / n
        pen = Pen(c, lk, 0, line_color=cd["colors"]["line"])
        c.save()
        c.translate(x, 800)
        s = 5.6 * cd["height"]
        c.scale(s, s)
        dr = rig.draw(pen, cd, actions.pose_for("idle", 0.3, 3), "happy", 0.3)
        m = c.getTotalMatrix()
        c.restore()
        pen.flush()
        b = m.mapRect(dr.bounds)
        boxes.append({"id": cd["id"], "box": [b.left(), b.top(), b.right(), b.bottom()], "height_px": b.height()})
        _label(c, cd["name"], x - 40, 850, 22, "#2A2430")
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(surf.makeImageSnapshot().toarray()[..., :3]).save(out, quality=90)
    return {"cast": boxes}


def silhouette_parts(cd: dict, lk: dict, pose_name: str = "wave") -> int:
    """Count separate pieces of the character's silhouette (1 = everything is attached)."""
    import cv2
    W, H = 400, 400
    surf = skia.Surface.MakeRaster(skia.ImageInfo.Make(W, H, skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType))
    c = surf.getCanvas()
    c.clear(skia.ColorTRANSPARENT)
    plain = {**lk, "fill": "flat", "jitter": 0, "line": True, "look": "vector", "reveal": False}
    pen = Pen(c, plain, 0, line_color="#000000")
    c.translate(200, 360)
    c.scale(3, 3)
    pose = actions.pose_for(pose_name, 0.5, 3)
    pose.symbols = []
    rig.draw(pen, cd, pose, "neutral", 0.5, symbols=False)
    a = surf.makeImageSnapshot().toarray()[..., 3]
    mask = (a > 20).astype(np.uint8)
    n, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    return int(sum(1 for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] > 30))
