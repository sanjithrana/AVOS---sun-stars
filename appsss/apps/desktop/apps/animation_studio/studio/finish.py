"""AI finish: run a finished film through an open video model, shot by shot, keeping its timing and soundtrack.

    wan-vace         re-style each shot with Wan VACE (depth control): same motion and framing, richer rendering
    wan-2.2-animate  each shot's first frame performs the shot's motion (Wan 2.2 Animate, move mode)
    scail-2          the same job with SCAIL-2 (your GPU server only)
    ltx-2.3          re-animate each shot from its first frame with LTX-2.3

The engine's film (out/video.mp4) stays as it is; the result is out/video_ai.mp4. A shot whose AI pass fails keeps
the engine's version, so the film is always complete. Progress is in out/finish.json (shown in the project page).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from . import config, models
from .render.images import STYLE_PROMPT

RUNNING: dict[str, threading.Thread] = {}


def status_path(d: Path) -> Path:
    return d / "out" / "finish.json"


def read_status(d: Path) -> dict | None:
    try:
        return json.loads(status_path(d).read_text("utf-8"))
    except Exception:
        return None


def _write(d: Path, st: dict) -> None:
    p = status_path(d)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, ensure_ascii=False, indent=1), "utf-8")
    os.replace(tmp, p)


def _ff(args: list[str]) -> None:
    r = subprocess.run([config.ffmpeg(), "-y", "-loglevel", "error", *args], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[-400:])


def shot_prompt(shot: dict, engine: str) -> str:
    bits = [str(shot.get(k) or "") for k in ("summary", "action")]
    return ", ".join(b for b in bits if b) + f". {STYLE_PROMPT.get(engine, STYLE_PROMPT['hyperframes'])}, smooth consistent motion"


def check(d: Path, model_id: str) -> str | None:
    """Why this finish can't start (None = it can)."""
    if model_id not in models.finish_choices():
        return f"model must be one of {', '.join(models.finish_choices())}"
    if not (d / "out" / "video.mp4").exists():
        return "Finish the film first (out/video.mp4 doesn't exist yet)."
    if (st := read_status(d)) and st.get("state") == "running" and d.name in RUNNING and RUNNING[d.name].is_alive():
        return "An AI finish is already running for this project."
    ok, why = models.ready(model_id)
    return None if ok else why


def concurrency(model_id: str) -> int:
    """FINISH_CONCURRENCY=<n> fixes it. Otherwise: two shots per online GPU worker, 3 on fal.ai, 1 on a single
    ComfyUI server (it runs one job at a time anyway)."""
    raw = (os.environ.get("FINISH_CONCURRENCY") or "").strip()
    if raw.isdigit():
        return max(1, min(8, int(raw)))
    try:
        backend = models.backend_for(model_id)
    except Exception:  # noqa: BLE001
        return 1
    if backend == "gpu":
        from . import gpu
        online = [w for w in gpu.workers() if gpu.status(w).get("online")]
        return max(1, min(8, 2 * len(online)))
    return 3 if backend in ("fal", "replicate") else 1


def start(d: Path, model_id: str) -> dict:
    plan = json.loads((d / "plan.json").read_text("utf-8"))
    shots = plan.get("shots") or []
    st = {"model": model_id, "name": models.get(model_id)["name"], "state": "running", "done": 0, "total": len(shots),
          "shots": {}, "video": None, "error": None, "startedAt": time.time()}
    _write(d, st)
    th = threading.Thread(target=_run, args=(d, model_id, plan, st), daemon=True)
    RUNNING[d.name] = th
    th.start()
    return st


def _run(d: Path, model_id: str, plan: dict, st: dict) -> None:
    fmt = plan.get("format") or {}
    W, H, fps = int(fmt.get("width") or 1280), int(fmt.get("height") or 720), int(fmt.get("fps") or 24)
    engine = plan.get("engine") or "hyperframes"
    work = d / "build" / "finish" / model_id
    work.mkdir(parents=True, exist_ok=True)
    shots = plan.get("shots") or []
    lock = threading.Lock()

    def one(i: int, s: dict) -> Path:
        sid, dur = s["id"], max(0.4, float(s["end_s"]) - float(s["start_s"]))
        src = d / "build" / "shots" / f"{sid}.mp4"
        fitted = work / f"{sid}.fit.mp4"
        fit_args = ["-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={fps},"
                           f"tpad=stop_mode=clone:stop_duration={dur:.3f},format=yuv420p",
                    "-t", f"{dur:.3f}", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18"]
        try:
            with tempfile.TemporaryDirectory() as tmp:
                clip, first = Path(tmp) / "clip.mp4", Path(tmp) / "first.png"
                _ff(["-i", str(src), "-t", f"{dur:.3f}", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(clip)])
                _ff(["-i", str(src), "-frames:v", "1", str(first)])
                out = models.finish_shot(model_id, shot_prompt(s, engine), first_frame=first.read_bytes(),
                                         clip=clip.read_bytes(), seconds=dur, w=W, h=H, seed=i + 1)
                raw = work / f"{sid}.ai.mp4"
                raw.write_bytes(out)
            _ff(["-i", str(raw), *fit_args, str(fitted)])
            result = {"ok": True}
        except Exception as e:   # keep the engine's shot
            _ff(["-i", str(src), *fit_args, str(fitted)])
            result = {"ok": False, "error": str(e)[:300]}
        with lock:
            st["shots"][sid] = result
            st["done"] += 1
            _write(d, st)
        return fitted

    try:
        # Several shots at once: spread over your GPU workers (or hosted in parallel on fal.ai).
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=concurrency(model_id)) as pool:
            parts = list(pool.map(lambda a: one(*a), enumerate(shots)))
        if not any(v["ok"] for v in st["shots"].values()):
            first_err = next(iter(st["shots"].values()), {}).get("error") or "no shots"
            raise RuntimeError(f"No shot came back from {st['name']}: {first_err}")
        lst = work / "list.txt"
        lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), "utf-8")
        silent = work / "silent.mp4"
        _ff(["-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(silent)])
        final = d / "out" / "video_ai.mp4"
        tmp = d / "out" / "video_ai.tmp.mp4"
        _ff(["-i", str(silent), "-i", str(d / "out" / "video.mp4"), "-map", "0:v", "-map", "1:a?", "-c:v", "copy",
             "-c:a", "copy", "-shortest", "-movflags", "+faststart", str(tmp)])
        os.replace(tmp, final)
        st.update(state="done", video="out/video_ai.mp4", finishedAt=time.time())
    except Exception as e:
        st.update(state="error", error=str(e)[:500])
    finally:
        _write(d, st)
        RUNNING.pop(d.name, None)
        shutil.rmtree(work / "tmp", ignore_errors=True)
