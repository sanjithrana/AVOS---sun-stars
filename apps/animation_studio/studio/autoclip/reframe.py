"""AI Reframe: turn a wide video into a vertical one by choosing a layout for every scene, the way Klap's "AI Reframe" does.

  1. split the clip into scenes (ffmpeg scene-change detection)
  2. look at ~3 frames a second: find faces (YuNet, a 230 KB model that ships with the studio, runs on any CPU), measure mouth movement
     (who is talking) and where the picture's detail is (for scenes with no face)
  3. choose a layout for each scene by simple rules:
        1 face                        follow it with a smooth 9:16 crop            "follow"
        2 faces, apart                stacked split screen, one on top of the other "split"
        2 faces close / "speaker"     follow whoever talks                          "follow"
        small face in a corner        the screen or game on top, the face cam under "facecam"
        no face, one clear subject    follow the busiest part                       "salient"
        no face / a crowd             the whole frame over a blurred copy           "blur"
  4. optionally let a vision AI (Ollama qwen2.5-vl, or a paid model) label the scenes the rules are unsure about
  5. one ffmpeg pass renders every scene with its own layout and joins them; the captions go on top.

Everything the renderer needs is saved in the plan (scenes, layouts, smoothed crop paths), so changing one scene's layout re-renders without looking at the video again."""
from __future__ import annotations

import json
import re
import statistics
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable

from .. import config

MODEL = Path(__file__).parent / "assets" / "face_yunet.onnx"
FPS = 3.0
LAYOUTS = {"game": "Gameplay: steady, most of the screen", "camtop": "Face cam on top, game below", "follow": "Follow the speaker", "split": "Split screen", "facecam": "Content + face cam", "salient": "Follow the action",
           "blur": "Whole frame on blur", "fill": "Fill the screen"}
BINS = 64
FOLLOW_FACE = 0.3                                 # in a close shot the face is about this share of the frame's width (a medium close-up, like the big clip channels)


def cam_split(ar: float, w: int, h: int) -> tuple[float, float]:
    """(cam height, game height) as shares of the frame: the game at full width keeps its whole picture, sits above YouTube's title strip
    (the bottom 16%), and the cam gets the rest of the top (between 30% and 55%)."""
    gh = min(0.6, (w / ar) / h)
    hb = max(0.3, min(0.55, 0.84 - gh))
    return hb, min(gh, 1.0 - hb)


GAME_VIEWS = {"whole": 16 / 9, "most": 4 / 3, "close": 1.0}     # how much of a game frame is kept: all of it, the middle three quarters, the middle square
GAME_AR = 1.15                                    # the game under the cam is cropped to this shape (wider than the space, so most of the game stays in) and fills the width
CAM_TOP = 0.38                                    # share of the height the face cam gets when it is on top (cam over game, like the big gaming channels)
CAM_H = 0.38                                      # share of the frame height the face cam gets in the content + face cam layout


# ---------- what is installed ----------
def status() -> dict:
    try:
        import cv2  # noqa: F401
        have_cv = hasattr(cv2, "FaceDetectorYN")
    except Exception:  # noqa: BLE001
        have_cv = False
    return {"ready": bool(have_cv and MODEL.is_file()), "opencv": have_cv, "model": MODEL.is_file(),
            "fix": "" if have_cv else "Face tracking needs OpenCV: docker compose exec animation-studio pip install opencv-python-headless"}


# ---------- reading the video ----------
def probe(src: str) -> tuple[int, int, float]:
    """(width, height, duration) from ffmpeg's own banner: no ffprobe needed."""
    r = subprocess.run([config.ffmpeg(), "-hide_banner", "-i", src], capture_output=True, text=True, timeout=60)
    txt = r.stderr
    m = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", txt)
    d = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", txt)
    if not m:
        raise RuntimeError("Could not read the video's size.")
    return int(m.group(1)), int(m.group(2)), (int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3))) if d else 0.0


def find_scenes(src: str, start: float, dur: float, thr: float = 0.32, min_len: float = 1.2) -> list[float]:
    """Cut times (seconds from the clip start), always beginning with 0 and ending with dur."""
    r = subprocess.run([config.ffmpeg(), "-hide_banner", "-nostdin", "-ss", f"{start:.2f}", "-t", f"{dur:.2f}", "-i", src, "-an", "-vf",
                        f"scale=320:-2,select='gt(scene,{thr})',showinfo", "-f", "null", "-"], capture_output=True, text=True, timeout=900)
    cuts = sorted({round(float(x), 2) for x in re.findall(r"pts_time:(\d+\.?\d*)", r.stderr) if 0 < float(x) < dur})
    out = [0.0]
    for c in cuts:
        if c - out[-1] >= min_len and dur - c >= min_len:
            out.append(c)
    return out + [round(dur, 2)]


def sample_frames(src: str, start: float, dur: float, folder: Path, fps: float = FPS) -> list[Path]:
    subprocess.run([config.ffmpeg(), "-v", "error", "-nostdin", "-y", "-ss", f"{start:.2f}", "-t", f"{dur:.2f}", "-i", src, "-an", "-vf", f"fps={fps},scale=640:-2",
                    "-q:v", "4", str(folder / "f%05d.jpg")], capture_output=True, timeout=1800)
    return sorted(folder.glob("f*.jpg"))


def look(files: list[Path], fps: float = FPS) -> list[dict]:
    """Per frame: faces [{cx,cy,w,h,m}] (all as 0..1 fractions; m = mouth movement) and the column detail profile."""
    import cv2
    import numpy as np
    out: list[dict] = []
    det = None
    prev = None
    for i, f in enumerate(files):
        im = cv2.imread(str(f))
        if im is None:
            out.append({"t": i / fps, "faces": [], "col": [0.0] * BINS})
            continue
        h, w = im.shape[:2]
        if det is None:
            det = cv2.FaceDetectorYN.create(str(MODEL), "", (w, h), 0.72, 0.3, 50)
        det.setInputSize((w, h))
        _, res = det.detect(im)
        gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
        faces = []
        for r in (res if res is not None else []):
            x, y, fw, fh = [float(v) for v in r[:4]]
            if fw < w * 0.025 or fh < h * 0.04:
                continue
            mx, my = float(np.mean(r[[10, 12]])), float(np.mean(r[[11, 13]]))          # the two mouth corners
            x0, x1 = int(max(0, mx - fw * 0.28)), int(min(w, mx + fw * 0.28))
            y0, y1 = int(max(0, my - fh * 0.16)), int(min(h, my + fh * 0.16))
            m = float(np.mean(np.abs(gray[y0:y1, x0:x1].astype(np.int16) - prev[y0:y1, x0:x1].astype(np.int16)))) if prev is not None and y1 > y0 and x1 > x0 else 0.0
            faces.append({"cx": (x + fw / 2) / w, "cy": (y + fh / 2) / h, "w": fw / w, "h": fh / h, "m": m})
        sm = cv2.resize(gray, (160, max(2, int(160 * h / w))))
        g = np.abs(cv2.Sobel(sm, cv2.CV_32F, 1, 0)) + np.abs(cv2.Sobel(sm, cv2.CV_32F, 0, 1))
        col = [float(v) for v in np.add.reduceat(g.sum(axis=0), np.linspace(0, 160, BINS, endpoint=False).astype(int))]
        out.append({"t": i / fps, "faces": faces, "col": col})
        prev = gray
    return out


# ---------- smoothing ----------
def smooth(vals: list[float], fps: float = FPS, dead: float = 0.035, alpha: float = 0.4, slew: float = 0.45) -> list[float]:
    """Median of 3, an exponential average, a dead zone (the crop holds still for small moves) and a speed limit (fraction of the frame per second)."""
    if not vals:
        return []
    v = [statistics.median(vals[max(0, i - 1): i + 2]) for i in range(len(vals))]
    out = [v[0]]
    ema = v[0]
    for x in v[1:]:
        ema = alpha * x + (1 - alpha) * ema
        if abs(ema - out[-1]) < dead:
            out.append(out[-1])
        else:
            step = slew / fps
            out.append(out[-1] + max(-step, min(step, ema - out[-1])))
    return out


def simplify(pts: list[tuple[float, float]], eps: float = 0.006) -> list[tuple[float, float]]:
    """Ramer-Douglas-Peucker: keep only the points that bend the path, so the ffmpeg expression stays short."""
    if len(pts) < 3:
        return pts
    (t0, v0), (t1, v1) = pts[0], pts[-1]
    worst, idx = 0.0, 0
    for i in range(1, len(pts) - 1):
        t, v = pts[i]
        line = v0 + (v1 - v0) * ((t - t0) / (t1 - t0) if t1 != t0 else 0)
        if abs(v - line) > worst:
            worst, idx = abs(v - line), i
    if worst <= eps:
        return [pts[0], pts[-1]]
    return simplify(pts[: idx + 1], eps)[:-1] + simplify(pts[idx:], eps)


def _fill(series: list[float | None], default: float) -> list[float]:
    first = next((x for x in series if x is not None), default)
    out, last = [], first
    for x in series:
        last = x if x is not None else last
        out.append(last)
    return out


def _track(times: list[float], xs: list[float | None], ys: list[float | None], ss: list[float | None], fps: float) -> list[list[float]]:
    """[[t, x, y, size], ...]: the smoothed path of one subject, with only the points where it bends."""
    x = smooth(_fill(xs, 0.5), fps)
    y = smooth(_fill(ys, 0.5), fps)
    keep = {t for t, _ in simplify(list(zip(times, x)))} | {t for t, _ in simplify(list(zip(times, y)))}
    sz = statistics.median(_fill(ss, 0.15))
    return [[round(t, 2), round(x[i], 3), round(y[i], 3), round(sz, 3)] for i, t in enumerate(times) if t in keep]


# ---------- planning ----------
def _best_window(col: list[float], frac: float) -> float:
    k = max(1, int(round(BINS * frac)))
    tot = sum(col) or 1.0
    best, bi = -1.0, BINS // 2
    for i in range(0, BINS - k + 1):
        s = sum(col[i: i + k])
        if s > best:
            best, bi = s, i
    return (bi + k / 2) / BINS if tot else 0.5


def refine_cuts(frames: list[dict], cuts: list[float], fps: float = FPS, min_len: float = 1.2) -> list[float]:
    """A shot that stays the same picture can still change who is in it (a second person walks in, a face cam appears). Where the number of
    faces changes and stays changed for at least min_len seconds, start a new scene: it gets its own layout."""
    out = [cuts[0]]
    need = max(2, int(round(min_len * fps)))
    for a, b in zip(cuts, cuts[1:]):
        fr = [min(3, len(f["faces"])) for f in frames if a <= f["t"] < b]
        sm = [statistics.median(fr[max(0, i - 2): i + 3]) if fr else 0 for i in range(len(fr))]
        last = 0
        for i in range(1, len(sm)):
            if sm[i] != sm[i - 1] and i - last >= need and len(sm) - i >= need and len(set(sm[i: i + need])) == 1:
                out.append(round(a + i / fps, 2))
                last = i
        out.append(b)
    return out


def plan_scenes(frames: list[dict], cuts: list[float], src_w: int, src_h: int, words: list[dict] | None = None, clip_start: float = 0.0,
                multi: str = "split", fps: float = FPS, whole: bool = False) -> list[dict]:
    """The rules (see the module doc). Returns one dict per scene with its layout, why, and the crop paths for every possible layout."""
    scenes = []
    crop_frac = min(1.0, (src_h * 9 / 16) / src_w)             # how much of the width a 9:16 crop covers
    speaking = lambda t: not words or any(w["s"] <= clip_start + t <= w["e"] for w in words)      # noqa: E731
    for i in range(len(cuts) - 1):
        t0, t1 = cuts[i], cuts[i + 1]
        fr = [f for f in frames if t0 <= f["t"] < t1] or [f for f in frames if abs(f["t"] - t0) < 1.0][:1]
        counts: dict[int, int] = {}
        for f in fr:
            counts[len(f["faces"])] = counts.get(len(f["faces"]), 0) + 1
        seen = sum(v for k, v in counts.items() if k > 0)
        n = max((k for k in counts if k > 0), key=lambda k: counts[k], default=0) if seen >= max(1, 0.35 * len(fr)) else 0
        conf = counts.get(n, 0) / max(1, len(fr)) if n else (counts.get(0, 0) / max(1, len(fr)))
        times = [f["t"] - t0 for f in fr]
        slots: list[list[dict | None]] = [[], []]
        for f in fr:
            fs = sorted(sorted(f["faces"], key=lambda z: -z["w"])[:2], key=lambda z: z["cx"])
            if n >= 2 and len(fs) == 2:
                slots[0].append(fs[0]); slots[1].append(fs[1])
            elif n >= 2 and len(fs) == 1:
                k = 0 if fs[0]["cx"] < 0.5 else 1
                slots[k].append(fs[0]); slots[1 - k].append(None)
            elif fs:
                slots[0].append(max(fs, key=lambda z: z["w"])); slots[1].append(None)
            else:
                slots[0].append(None); slots[1].append(None)
        tr: dict[str, Any] = {}
        for k, name in enumerate(("a", "b")):
            if any(slots[k]):
                tr[name] = _track(times, [z["cx"] if z else None for z in slots[k]], [z["cy"] if z else None for z in slots[k]], [z["w"] if z else None for z in slots[k]], fps)
        sal_x = [_best_window(f["col"], crop_frac) for f in fr]
        tr["sal"] = _track(times, sal_x, [0.5] * len(fr), [0.2] * len(fr), fps)
        conc = 0.0
        if fr:
            avg = [sum(f["col"][j] for f in fr) / len(fr) for j in range(BINS)]
            k = max(1, int(round(BINS * crop_frac)))
            conc = max(sum(avg[a: a + k]) for a in range(0, BINS - k + 1)) / (sum(avg) or 1.0)
        speaker, who = 0, ""
        if n >= 2 and "a" in tr and "b" in tr:
            ms = []
            for k in (0, 1):
                v = [z["m"] for f, z in zip(fr, slots[k]) if z and speaking(f["t"] + t0)]
                ms.append(sum(v) / len(v) if v else 0.0)
            speaker = 0 if ms[0] >= ms[1] else 1
        face_w = statistics.median([z["w"] for z in slots[0] if z]) if any(slots[0]) else 0.0
        cx0 = statistics.median([z["cx"] for z in slots[0] if z]) if any(slots[0]) else 0.5
        cy0 = statistics.median([z["cy"] for z in slots[0] if z]) if any(slots[0]) else 0.5
        unclear = False
        if src_h > src_w * 0.9:
            layout, why = "fill", "already vertical or square"
        elif n == 0:
            layout, why = ("salient", "one clear subject, no faces") if conc >= (0.9 if whole else 0.8) else ("blur", "no faces: the whole frame, so nothing important is cropped away")
            unclear = conc > 0.45 and seen > 0 or (0.5 < conc < 0.75)
        elif n == 1:
            corner = face_w < 0.16 and (cx0 < 0.3 or cx0 > 0.7) and (cy0 < 0.3 or cy0 > 0.7)
            if whole and face_w < 0.3:          # a streamer's cam sitting in a game frame: the whole frame already shows it, cropping would throw the game away
                if corner and conf >= 0.7:      # the cam is really there the whole time: cam on top, the whole game below
                    layout, why = "camtop", "face cam on top, the whole game below"
                else:
                    layout, why = "blur", "whole picture: the game and the cam together"
            else:
                layout, why = ("facecam", "small face in a corner: content on top, face cam below") if corner else ("follow", "one speaker")
            unclear = face_w < 0.16 or conf < 0.6
        elif n == 2:
            apart = abs(tr["a"][-1][1] - tr["b"][-1][1]) >= 0.22 if "a" in tr and "b" in tr else False
            if not apart or multi == "speaker":
                layout, why = "follow", "two people close together: follow the one talking" if not apart else "following whoever talks"
                who = "b" if speaker else "a"
            else:
                layout, why = "split", "two people: one above the other"
            unclear = conf < 0.6
        else:
            layout, why = "blur", f"{n} people: the whole group"
            unclear = True
        sc = {"i": i, "t0": round(t0, 2), "t1": round(t1, 2), "faces": n, "layout": layout, "auto": layout, "why": why, "conf": round(conf, 2), "unclear": bool(unclear),
              "speaker": speaker, "follow": who or "a", "face_w": round(face_w, 3), "conc": round(conc, 2), "tracks": tr}
        scenes.append(sc)
    return scenes


# ---------- the picture ----------
def _pl(points: list[list[float]], col: int) -> str:
    """An ffmpeg expression of t: the path through the points, straight lines between them, held still before and after."""
    pts = [(p[0], p[col]) for p in points]
    if len(pts) == 1 or all(abs(v - pts[0][1]) < 1e-6 for _, v in pts):
        return f"{pts[0][1]:.4f}"
    terms = [f"lt(t,{pts[0][0]:.3f})*{pts[0][1]:.4f}"]
    for (ta, va), (tb, vb) in zip(pts, pts[1:]):
        if tb > ta:
            terms.append(f"gte(t,{ta:.3f})*lt(t,{tb:.3f})*({va:.4f}+({vb - va:.4f})*(t-{ta:.3f})/{tb - ta:.3f})")
    terms.append(f"gte(t,{pts[-1][0]:.3f})*{pts[-1][1]:.4f}")
    return "(" + "+".join(terms) + ")"


def _even(v: float) -> int:
    return max(2, int(v) // 2 * 2)


def _crop(src_w: int, src_h: int, aspect: float, xe: str, ye: str, zoom: float = 1.0) -> str:
    """crop to width/height = aspect following the centre (xe, ye as expressions in 0..1)."""
    cw = min(src_w, src_h * aspect) / zoom
    ch = cw / aspect
    cw, ch = _even(cw), _even(ch)
    return f"crop={cw}:{ch}:x='min(max({xe}*iw-{cw / 2:.1f},0),iw-{cw})':y='min(max({ye}*ih-{ch / 2:.1f},0),ih-{ch})'"


def resolve(sc: dict) -> str:
    """The layout that can really be drawn for this scene (an override needing tracks that do not exist falls back to the whole frame)."""
    lay, tr = sc["layout"], sc.get("tracks") or {}
    if lay == "split" and not ("a" in tr and "b" in tr):
        return "blur"
    if lay in ("follow", "facecam", "camtop") and "a" not in tr:
        return "salient" if lay == "follow" else "blur"
    return lay if lay in LAYOUTS else "blur"


def scene_graph(sc: dict, k: int, w: int, h: int, sw: int, sh: int) -> str:
    """Filters for one scene: input [s{k}] (already trimmed), output [v{k}] at w x h."""
    lay, tr = resolve(sc), sc.get("tracks") or {}
    s, o = f"[s{k}]", f"[v{k}]"
    fin = ",setsar=1,format=yuv420p" + o
    if lay == "follow":                               # a close shot of the person: head and shoulders fill the frame, the face in the upper third
        t = tr[sc.get("follow", "a")] if sc.get("follow", "a") in tr else tr["a"]
        base = min(sw, sh * w / h)
        face = max(0.01, float(t[0][3] if t and len(t[0]) > 3 else sc.get("face_w") or 0.1)) * sw
        far = face / sw < 0.045                       # a whole person far away (sport, stage, outdoors): keep them head to toe, no zoom
        zoom = 1.0 if far else max(1.0, min(2.4, FOLLOW_FACE * base / face))
        crop_h = base / (w / h) / zoom
        down = 0.0 if far else 0.13 * crop_h / sh                     # the crop sits lower than the face, so the face lands about a third of the way down
        return f"{s}{_crop(sw, sh, w / h, _pl(t, 1), f'({_pl(t, 2)}+{down:.4f})', zoom)},scale={w}:{h}:flags=lanczos{fin}"
    if lay == "salient":
        t = tr["sal"]
        return f"{s}{_crop(sw, sh, w / h, _pl(t, 1), '0.5')},scale={w}:{h}{fin}"
    if lay == "split":
        hh = _even(h / 2)
        a, b = tr["a"], tr["b"]
        zoom = lambda t: max(1.0, min(2.2, min(sw, sh * w / hh) / max(1.0, t[0][3] * sw * 3.6)))      # noqa: E731 - each person fills about a quarter of their tile
        return (f"{s}split[a{k}][b{k}];[a{k}]{_crop(sw, sh, w / hh, _pl(a, 1), _pl(a, 2), zoom(a))},scale={w}:{hh}[ta{k}];"
                f"[b{k}]{_crop(sw, sh, w / hh, _pl(b, 1), _pl(b, 2), zoom(b))},scale={w}:{hh}[tb{k}];[ta{k}][tb{k}]vstack{fin}")
    if lay == "facecam":
        hb = _even(h * CAM_H)
        ht = h - hb
        a = tr["a"]
        fx = statistics.median([p[1] for p in a])
        fy = statistics.median([p[2] for p in a])
        zoom = max(1.0, min(3.0, 0.4 / max(0.04, sc.get("face_w") or 0.12)))      # fill ~40% of the cam frame's width with the face
        cam = _crop(sw, sh, w / hb, f"{fx:.4f}", f"{fy:.4f}", zoom)
        return (f"{s}split=3[c{k}][d{k}][e{k}];[c{k}]scale={w}:{ht}:force_original_aspect_ratio=increase,crop={w}:{ht},boxblur=20:4[bg{k}];"
                f"[d{k}]scale={w}:-2[fg{k}];[bg{k}][fg{k}]overlay=(W-w)/2:(H-h)/2[top{k}];[e{k}]{cam},scale={w}:{hb}[bot{k}];[top{k}][bot{k}]vstack{fin}")
    if lay == "camtop":                               # streamer on top, the whole game right under them, a blurred strip at the very bottom (where YouTube's title sits)
        ar = float(sc.get("ar") or 16 / 9)
        hb_f, gh_f = cam_split(ar, w, h)
        hb, gh = _even(h * hb_f), _even(h * gh_f)
        rest = h - hb - gh
        a = tr["a"]
        fx = statistics.median([p[1] for p in a])
        fy = statistics.median([p[2] for p in a])
        zoom = max(1.0, min(4.0, 0.32 / max(0.03, sc.get("face_w") or 0.1)))      # the face fills about a third of the cam's width: head, shoulders and a bit of room
        cam = _crop(sw, sh, w / hb, f"{fx:.4f}", f"{fy:.4f}", zoom)
        game = _crop(sw, sh, ar, "0.5", "0.5")
        if rest < 4:
            return (f"{s}split=2[d{k}][e{k}];[d{k}]{game},scale={w}:{h - hb}:flags=lanczos[bot{k}];[e{k}]{cam},scale={w}:{hb}:flags=lanczos[top{k}];[top{k}][bot{k}]vstack{fin}")
        return (f"{s}split=3[c{k}][d{k}][e{k}];[c{k}]scale={w}:{rest}:force_original_aspect_ratio=increase,crop={w}:{rest},boxblur=24:4,eq=brightness=-0.1[low{k}];"
                f"[d{k}]{game},scale={w}:{gh}:flags=lanczos,unsharp=5:5:0.5[mid{k}];[e{k}]{cam},scale={w}:{hb}:flags=lanczos[top{k}];[top{k}][mid{k}][low{k}]vstack=inputs=3{fin}")
    if lay == "game":                                 # the game: one steady crop of the middle, full width, sharp; a blurred copy fills the rest
        ar = float(sc.get("ar") or 4 / 3)
        gh = _even(min(h, w / ar))
        return (f"{s}split[a{k}][b{k}];[a{k}]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=30:5,eq=brightness=-0.08[bg{k}];"
                f"[b{k}]{_crop(sw, sh, ar, '0.5', '0.5')},scale={w}:{gh}:flags=lanczos,unsharp=5:5:0.6[fg{k}];[bg{k}][fg{k}]overlay=(W-w)/2:(H-h)/2{fin}")
    if lay == "fill":
        return f"{s}scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}{fin}"
    return (f"{s}split[a{k}][b{k}];[a{k}]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=30:5[bg{k}];"
            f"[b{k}]scale={w}:-2[fg{k}];[bg{k}][fg{k}]overlay=(W-w)/2:(H-h)/2{fin}")


def graph(plan: dict, w: int, h: int, ass: str | None, esc: Callable[[str], str] | None = None) -> str:
    """The whole filtergraph: trim each scene out of [0:v], give it its layout, join them, put the captions on."""
    sw, sh = plan["src"]
    sc = plan["scenes"]
    parts = [f"[0:v]split={len(sc)}" + "".join(f"[i{k}]" for k in range(len(sc))) + ";"] if len(sc) > 1 else []
    for k, s in enumerate(sc):
        head = f"[i{k}]" if len(sc) > 1 else "[0:v]"
        parts.append(f"{head}trim=start={s['t0']:.3f}:end={s['t1']:.3f},setpts=PTS-STARTPTS[s{k}];")
        parts.append(scene_graph(s, k, w, h, sw, sh) + ";")
    g = "".join(parts)
    ends = "[post]" if ass else "[v]"
    g += (("".join(f"[v{k}]" for k in range(len(sc))) + f"concat=n={len(sc)}:v=1:a=0{ends}") if len(sc) > 1 else "[v0]null" + ends)
    if ass:
        g += f";[post]subtitles={ass}[v]"
    return g


# ---------- the vision AI (optional) ----------
VISION_SYSTEM = ("You look at ONE frame from a video and say how to frame it as a vertical 9:16 short. Answer ONE JSON object: "
                 '{"kind":"talking_heads|gameplay|screencast|presentation|product|scenery|other","people":N,"layout":"follow|split|facecam|camtop|salient|blur"}. '
                 "follow = one main person; split = two people side by side; facecam = a small webcam face over a game or screen; "
                 "salient = one clear subject to centre on; blur = show the whole frame (many people, gameplay, slides, text).")
KIND_LAYOUT = {"gameplay": "blur", "screencast": "blur", "presentation": "blur", "scenery": "salient", "product": "salient"}


def label_scenes(plan: dict, src: str, start: float, ask: Callable[[str, str, list[Path]], Any], say: Callable[[str], None], limit: int = 6) -> int:
    """Show one frame of each unclear scene to a vision AI and apply what it says (only where it fits what the rules measured)."""
    done = 0
    with tempfile.TemporaryDirectory() as td:
        for sc in [s for s in plan["scenes"] if s.get("unclear")][:limit]:
            mid = (sc["t0"] + sc["t1"]) / 2
            img = Path(td) / f"s{sc['i']}.jpg"
            r = subprocess.run([config.ffmpeg(), "-v", "error", "-nostdin", "-y", "-ss", f"{start + mid:.2f}", "-i", src, "-frames:v", "1", "-vf", "scale=768:-2", "-q:v", "4", str(img)],
                               capture_output=True, timeout=120)
            if r.returncode != 0 or not img.is_file():
                continue
            try:
                a = ask(VISION_SYSTEM, f"The rules measured {sc['faces']} face(s) in this scene. How should it be framed?", [img])
            except Exception as e:  # noqa: BLE001 - a label is a bonus, never a reason to stop
                say(f"The AI could not look at scene {sc['i'] + 1} ({str(e)[:80]}).")
                continue
            if not isinstance(a, dict):
                continue
            lay = KIND_LAYOUT.get(str(a.get("kind")), str(a.get("layout") or ""))
            if lay in LAYOUTS and lay != "fill":
                tr = sc.get("tracks") or {}
                need_ok = (lay != "split" or ("a" in tr and "b" in tr)) and (lay not in ("follow", "facecam", "camtop") or "a" in tr)
                if need_ok:
                    sc.update(layout=lay, auto=lay, why=f"AI: {a.get('kind', 'scene')}", unclear=False, label=str(a.get("kind") or "")[:20])
                    done += 1
    return done


# ---------- the entry points ----------
def stream_cam(frames: list[dict], src_w: int, src_h: int) -> list[float] | None:
    """[cx, cy, w] of a streamer's face cam that sits in the same place for most of the clip (an overlay on a game), else None.
    A face cam does not move: most frames have a small face within a few percent of one spot."""
    if not frames or src_h > src_w * 0.9:
        return None
    pts = [z for f in frames for z in f["faces"] if 0.02 <= z["w"] <= 0.28]
    if len(pts) < max(3, 0.4 * len(frames)):
        return None
    cx = statistics.median(z["cx"] for z in pts)
    cy = statistics.median(z["cy"] for z in pts)
    near = [f for f in frames if any(abs(z["cx"] - cx) < 0.06 and abs(z["cy"] - cy) < 0.08 and z["w"] <= 0.28 for z in f["faces"])]
    if len(near) < 0.5 * len(frames):
        return None
    if 0.36 < cx < 0.64 and 0.3 < cy < 0.7:          # a face in the middle of the picture is the content, not a cam
        return None
    fw = statistics.median(z["w"] for z in pts if abs(z["cx"] - cx) < 0.06 and abs(z["cy"] - cy) < 0.08)
    return [round(cx, 4), round(cy, 4), round(fw, 4)]


def use_game(plan: dict, ar: float) -> dict:
    """Gameplay with no cam: every scene shows the same steady, sharp middle part of the game (no crop chasing people around)."""
    for sc in plan["scenes"]:
        sc.update(layout="game", auto="game", why="gameplay: the game, steady and sharp", unclear=False, ar=ar)
    plan["game"] = ar
    return plan


def use_cam(plan: dict, cam: list[float]) -> dict:
    """Every scene: the streamer's cam on top, the game below, with one fixed cam crop (no jumping between scenes)."""
    cx, cy, fw = cam
    for sc in plan["scenes"]:
        tr = sc.setdefault("tracks", {})
        tr["a"] = [[0.0, cx, cy, fw]]
        sc.update(layout="camtop", auto="camtop", why="streamer cam on top, the game below", face_w=fw, unclear=False)
    plan["cam"] = cam
    ar = float((plan["scenes"][0].get("ar") if plan["scenes"] else None) or 16 / 9)
    plan["cam_h"] = round(cam_split(ar, 720, 1280)[0], 4)          # where the captions go: on the line between the cam and the game
    return plan


def analyse(src: str, start: float, end: float, words: list[dict] | None = None, multi: str = "split", fps: float = FPS,
            labeller: Callable[[str, str, list[Path]], Any] | None = None, say: Callable[[str], None] | None = None, whole: bool = False,
            game: bool = False, game_ar: float = 4 / 3, cam_ar: float = 16 / 9) -> dict:
    """Look at [start, end] of src and return the plan. Raises RuntimeError if face tracking is not installed (the caller falls back to a fixed layout)."""
    st = status()
    if not st["ready"]:
        raise RuntimeError(st["fix"] or "Face tracking is not available.")
    say = say or (lambda t: None)
    sw, sh, _ = probe(src)
    dur = end - start
    cuts = find_scenes(src, start, dur)
    with tempfile.TemporaryDirectory() as td:
        files = sample_frames(src, start, dur, Path(td), fps)
        if not files:
            raise RuntimeError("Could not read frames from the video.")
        frames = look(files, fps)
    cuts = refine_cuts(frames, cuts, fps)
    scenes = plan_scenes(frames, cuts, sw, sh, words, start, multi, fps, whole)
    plan = {"v": 1, "src": [sw, sh], "dur": round(dur, 2), "multi": multi, "scenes": scenes}
    cam = stream_cam(frames, sw, sh)
    if cam:
        say("Found the streamer's face cam: it goes on top, the game below.")
        for sc in plan["scenes"]:
            sc["ar"] = cam_ar
        return use_cam(plan, cam)
    if game and sw > sh:
        say("Gameplay: the game is shown steady and sharp, without following people around.")
        return use_game(plan, game_ar)
    if labeller and any(s["unclear"] for s in scenes):
        n = label_scenes(plan, src, start, labeller, say)
        if n:
            say(f"A vision AI helped with {n} unclear scene{'s' if n != 1 else ''}.")
    return plan


def apply_overrides(plan: dict, overrides: dict[str, str]) -> dict:
    for s in plan["scenes"]:
        v = overrides.get(str(s["i"]))
        if v == "auto":
            s["layout"], s["pinned"] = s["auto"], False
        elif v in LAYOUTS:
            s["layout"], s["pinned"] = v, True
    return plan


def summary(plan: dict) -> list[dict]:
    """What the UI shows: one row per scene (no crop paths)."""
    return [{"i": s["i"], "t0": s["t0"], "t1": s["t1"], "faces": s["faces"], "layout": resolve(s), "auto": s["auto"], "why": s["why"], "pinned": bool(s.get("pinned")),
             "label": s.get("label", ""), "can": [k for k in LAYOUTS if _can(s, k)]} for s in plan["scenes"]]


def _can(s: dict, k: str) -> bool:
    tr = s.get("tracks") or {}
    return (k != "split" or ("a" in tr and "b" in tr)) and (k not in ("follow", "facecam", "camtop") or "a" in tr)
