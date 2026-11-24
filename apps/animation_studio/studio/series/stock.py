"""Free stock footage from Pexels, for runs that have no GPU and no paid video model.

Pexels (https://www.pexels.com/api/) gives a free key instantly; the limit is 200 requests an hour and 20,000 a month, and its terms ask for
a visible link to Pexels and, where you can, a credit to the film-maker. This module searches by a few keywords taken from the shot, picks a
clip that fits the shape and length, and downloads it. It does NOT draw anything: a stock clip matches the keywords, not your character, so
it is a choice you make (Footage = Stock) and never a silent stand-in for a model.
"""
from __future__ import annotations

import os
import re
import threading

import httpx

API = "https://api.pexels.com/v1/videos/search"
ATTRIBUTION = "Stock video from Pexels (https://www.pexels.com)"
ORIENT = {"9:16": "portrait", "16:9": "landscape", "1:1": "square"}
SKIP = set("""a an the and or of to in on at by for with from into onto over under about as is are was were be been it its this that these those
starting attached image picture shot camera push pull pan tilt zoom slow slowly steady static move moves moving movement close closeup wide medium
frame frames keep same style look sound sounds seconds second scene clip video then while his her their he she they we you i no not never without text
logo watermark subtitle caption""".split())
_lock = threading.Lock()
CREDITS: list[dict] = []          # who filmed what, for the end card or the description


def ready() -> bool:
    return bool(os.environ.get("PEXELS_API_KEY"))


def query_of(prompt: str, n: int = 4) -> str:
    """A short search from a long shot prompt: its first few content words, in order."""
    words = [w for w in re.findall(r"[a-zA-Z][a-zA-Z'-]{2,}", prompt.lower()) if w not in SKIP]
    return " ".join(list(dict.fromkeys(words))[:n])


def pick(videos: list[dict], seconds: float, aspect: str, seed: int = 0) -> tuple[dict, dict] | None:
    """(video, file): clips long enough for the shot first, the right shape, an mp4 near 1080 wide; the seed picks among the best."""
    want_w = 1080 if aspect == "9:16" else 1920 if aspect == "16:9" else 1080
    ranked = []
    for v in videos:
        files = [f for f in v.get("video_files") or [] if f.get("file_type") == "video/mp4" and f.get("link") and f.get("quality") in ("hd", "sd")]
        if not files:
            continue
        f = min(files, key=lambda f: abs(int(f.get("width") or 0) - want_w))
        long_enough = float(v.get("duration") or 0) >= seconds
        ranked.append((0 if long_enough else 1, abs(int(f.get("width") or 0) - want_w), v, f))
    if not ranked:
        return None
    ranked.sort(key=lambda r: (r[0], r[1]))
    best = [r for r in ranked if r[0] == ranked[0][0]][:5]
    _, _, v, f = best[seed % len(best)]
    return v, f


def clip(prompt: str, seconds: float, aspect: str, seed: int = 0) -> bytes:
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        raise RuntimeError("Add a free Pexels key (Settings, Images & video) to use stock footage.")
    q = query_of(prompt) or "nature"
    r = httpx.get(API, params={"query": q, "orientation": ORIENT.get(aspect, "portrait"), "size": "medium", "per_page": 15},
                  headers={"Authorization": key}, timeout=60)
    if r.status_code == 429:
        raise RuntimeError("Pexels says the hourly limit (200 requests) is used up; try again later.")
    r.raise_for_status()
    got = pick(r.json().get("videos") or [], seconds, aspect, seed)
    if not got:
        raise RuntimeError(f"Pexels has no clip for '{q}'.")
    v, f = got
    data = httpx.get(f["link"], timeout=300, follow_redirects=True)
    data.raise_for_status()
    with _lock:
        CREDITS.append({"query": q, "page": v.get("url"), "by": (v.get("user") or {}).get("name"), "by_url": (v.get("user") or {}).get("url")})
    return data.content


def credit_lines() -> list[str]:
    seen, out = set(), [ATTRIBUTION]
    for c in CREDITS:
        line = f"{c.get('by') or 'a Pexels film-maker'}: {c.get('page') or c.get('by_url') or ''}".strip()
        if line not in seen:
            seen.add(line)
            out.append(line)
    return out
