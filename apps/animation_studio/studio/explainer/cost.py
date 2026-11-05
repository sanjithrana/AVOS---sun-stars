"""A plain estimate of what a video will cost on paid providers, from the prices in the model catalog.
It is a guide, not a bill: retries and provider changes move it."""
from __future__ import annotations

import re

from .. import models
from ..series import media

NUM = re.compile(r"\$\s*([0-9]*\.?[0-9]+)")
FAL_BILLED_BLOCK = 6.0          # LTX on fal.ai bills a clip in blocks of at least 6 s


def _price(mid: str, default: float) -> float:
    try:
        m = NUM.search(str((models.get(mid).get("fal") or {}).get("price") or ""))
        return float(m.group(1)) if m else default
    except Exception:  # noqa: BLE001
        return default


def estimate(seconds: int, s: dict) -> dict:
    shots = max(3, round(seconds / 4))
    pics = shots + 4                                    # a picture per shot + presenter, props, set
    pic_model, _ = media.choice(s, "pictures")
    free_pics = media.local_only(s) or any(x for x in [pic_model] if x in ())
    per_pic = 0.0 if free_pics else _price(pic_model if pic_model != "auto" else "qwen-image", 0.02) * 1.0     # about one megapixel
    vid_model, _ = media.choice(s, "motion")
    video_shots = 0 if vid_model == "off" or media.local_only(s) else (shots if vid_model != "auto" else max(1, shots // 2))
    vm = vid_model if vid_model not in ("auto", "off") else "ltx-2.3"
    per_second = _price(vm, 0.08)
    video = video_shots * max(FAL_BILLED_BLOCK if vm == "ltx-2.3" else 2.0, seconds / shots) * per_second
    pics_cost = 0.0 if media.local_only(s) else pics * per_pic
    lo, hi = (pics_cost + video) * 0.8, (pics_cost + video) * 1.5
    return {"usd_low": round(lo, 2), "usd_high": round(hi, 2), "shots": shots, "pictures": pics, "video_shots": video_shots,
            "note": ("Free on your own GPU worker." if media.local_only(s) else
                     "Pictures on Cloudflare's free daily allowance cost nothing. Video is billed per second by the provider, "
                     "and a short clip is billed as at least 6 s on LTX-2.3. Retries add to it.")}
