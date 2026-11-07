"""Reference-guided clips, the way the SJinn Amber Noir skill makes them: Seedance 2.0 (fal.ai, reference-to-video) gets the clip's
approved opening image, the character identity sheet, the fixed location reference and the previous clip, plus one prompt that
names what each reference is for, the fixed appearance, timed action and camera, the exact narration and the audio direction.
With generate_audio the model returns the narration, music, ambience and sound effects in the clip (native audio).

fal endpoint: bytedance/seedance-2.0/mini/reference-to-video (needs FAL_KEY with credit). References are named @Image1… @Video1."""
from __future__ import annotations

import os

from .. import models
from ..series import media

ENDPOINT = os.environ.get("SEEDANCE_REF_ENDPOINT") or "bytedance/seedance-2.0/mini/reference-to-video"
MAX_VIDEO_REF = 8 * 1024 * 1024


def ready(s: dict) -> bool:
    """Seedance can be used: a fal key is set, video isn't switched off, and you didn't restrict the run to this PC."""
    if media.local_only(s) or media.choice(s, "motion")[0] == "off":
        return False
    picked = media.choice(s, "motion")[0]
    return bool(os.environ.get("FAL_KEY")) and picked in ("auto", "seedance-2-mini")


def clip(prompt: str, images: list[bytes], prev: bytes | None, seconds: int, aspect: str, audio: bool) -> bytes:
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
