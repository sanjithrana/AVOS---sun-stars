"""Reference-guided clips, the way the SJinn Amber Noir skill makes them: Seedance 2.0 (fal.ai, reference-to-video) gets the clip's
approved opening image, the character identity sheet, the fixed location reference and the previous clip, plus one prompt that
names what each reference is for, the fixed appearance, timed action and camera, the exact narration and the audio direction.
With generate_audio the model returns the narration, music, ambience and sound effects in the clip (native audio).

fal endpoint: bytedance/seedance-2.0/mini/reference-to-video (needs FAL_KEY with credit). References are named @Image1… @Video1."""
from __future__ import annotations

import os
import threading

from .. import models
from ..series import media

ENDPOINT = os.environ.get("SEEDANCE_REF_ENDPOINT") or "bytedance/seedance-2.0/mini/reference-to-video"
MAX_VIDEO_REF = 8 * 1024 * 1024


OPEN = ["wan-2.2", "ltx-2.3"]          # the fabric's open video models: your GPU worker, ComfyUI, or fal.ai when allowed
SIZES = {"9:16": (480, 832), "16:9": (832, 480), "1:1": (640, 640)}     # multiples of 32, what Wan and LTX both accept
_now = threading.local()


def _stock(s: dict) -> bool:
    """You chose Footage = Stock (Pexels, free): real stock clips matched by keywords. Never automatic, never under Paid or "This PC only"."""
    from ..series import stock
    return (media.choice(s, "footage")[0] == "stock" and stock.ready() and media.choice(s, "motion")[0] != "off"
            and media.tier(s) != "paid" and not media.local_only(s))


def _seedance(s: dict) -> bool:
    """Seedance can be used: a fal key is set, video isn't switched off, and you didn't restrict the run to this PC."""
    picked = media.choice(s, "motion")[0]
    return bool(os.environ.get("FAL_KEY")) and not media.local_only(s) and media.tier(s) != "free" and picked in ("auto", "seedance-2-mini")


def open_models(s: dict) -> list[str]:
    """Open video models this run may use. You picked one: only that one. Automatic: only when Seedance isn't available, so a
    run with a fal key behaves exactly as before and a run without one uses a free model if one is installed."""
    picked = media.choice(s, "motion")[0]
    if picked == "off":
        return []
    if picked in OPEN:
        return [picked] if media.tier(s) != "paid" or media.fal_ok(picked) else []
    if picked != "auto" or _seedance(s):
        return []
    ok = [m for m in OPEN if media.usable(s, "motion", m)]
    return [m for m in ok if media.fal_ok(m)] if media.tier(s) == "paid" else ok


def ready(s: dict) -> bool:
    """True when some video engine can make clips for this run (Seedance first, then an open model). Remembers the run
    so clip() knows which settings it was asked under."""
    ok = _stock(s) or _seedance(s) or bool(open_models(s))
    _now.s = s if ok else None
    return ok


def why_not(s: dict) -> str:
    """One plain sentence for the shot note when no video engine is ready."""
    t, picked = media.tier(s), media.choice(s, "motion")[0]
    if picked == "off":
        return "video clips are switched off"
    if media.choice(s, "footage")[0] == "stock":
        return "Footage is set to Stock, but there is no Pexels key (Settings), or Cost is Paid, or \"This PC only\" is on"
    if t == "free":
        return "Cost is Free, so Seedance and fal.ai were not used, and no open video model (Wan 2.2 / LTX 2.3) is running on your GPU worker or ComfyUI"
    if t == "paid":
        return "Cost is Paid, so no free stand-in was used, but there is no fal.ai key with credit (Settings)"
    return "no fal.ai key, and no open video model is running on your GPU worker or ComfyUI"


def engine(s: dict) -> str:
    if _stock(s):
        return "pexels-stock"
    return "seedance-2-mini" if _seedance(s) else (open_models(s) or ["none"])[0]


def _open_clip(s: dict, prompt: str, images: list[bytes], seconds: int, aspect: str) -> bytes:
    """Wan / LTX animate the first picture only (no references, no native audio: the pipeline lays foley and music under it)."""
    W, H = SIZES.get(aspect, SIZES["9:16"])
    errors: list[str] = []
    for mid in open_models(s):
        n, fps = media.frames_for(mid, seconds)
        try:
            return models.run_model(mid, task="video", want="video", prompt=prompt, w=W, h=H, seconds=seconds, frames=n, fps=fps,
                                    seed=media.seed_of(prompt, mid), inputs={"image": images[0]}, timeout=2400, tag="skill-clip",
                                    backend=media.where(s, "motion", mid))
        except Exception as e:  # noqa: BLE001 - a model that is down: the next one, else the caller's still-picture path
            errors.append(f"{mid}: {str(e)[:160]}")
    raise RuntimeError("No open video model could make the clip: " + ("; ".join(errors) or "none is ready"))


def clip(prompt: str, images: list[bytes], prev: bytes | None, seconds: int, aspect: str, audio: bool) -> bytes:
    s = getattr(_now, "s", None)
    if s is not None and _stock(s):
        from ..series import stock
        return stock.clip(prompt, seconds, aspect, media.seed_of(prompt, "stock"))
    if s is not None and not _seedance(s):
        return _open_clip(s, prompt, images, seconds, aspect)
    data = {"prompt": prompt, "image_urls": [models.data_uri(b) for b in images[:9]], "resolution": os.environ.get("SEEDANCE_RESOLUTION") or "720p",
            "duration": str(max(4, min(15, int(round(seconds))))), "aspect_ratio": aspect if aspect in ("16:9", "9:16", "1:1") else "auto",
            "generate_audio": bool(audio)}
    if prev and len(prev) <= MAX_VIDEO_REF:
        data["video_urls"] = [models.data_uri(prev)]
    url = models._first_url(models.fal_run(ENDPOINT, data, timeout=1800), "video", "videos")
    if not url:
        raise RuntimeError("Seedance returned no video")
    return models._download(url)


def has_audio(path) -> bool:
    import subprocess
    from .. import config
    r = subprocess.run([config.ffprobe() if hasattr(config, "ffprobe") else "ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return bool(r.stdout.strip())
