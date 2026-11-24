"""Is this link OK to clip? It reads what the site publishes about the video (through yt-dlp) and says one of:

  own              it is on a channel you connected: yours to clip
  creative-commons the site marks it Creative Commons (CC BY): reusable, but give credit to the channel
  ask              the owner keeps the rights (the normal case): you need their OK before you post clips of it
  unknown          we could not read the page: only your own recordings are safe
  blocked          not clippable at all: paid streaming (Netflix, Hotstar, Spotify…), private, members-only or login-only videos

It never says "safe" for someone else's video. Copyright is a question this cannot settle; it only tells you what applies and what to look for.

It also says whether the link is a live stream: "live" (happening now: Auto Clip can record the next few minutes), "upcoming" (not started: nothing to clip yet),
"processing" (just ended, the site has not finished the recording) or "past" (a normal recording of a finished stream)."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from typing import Any

from . import intake, youtube

SITES = [
    ("drm", r"(^|\.)(netflix|primevideo|disneyplus|hotstar|jiohotstar|jiocinema|hulu|hbomax|max|spotify|crunchyroll|sonyliv|zee5|tv\.apple|peacocktv|paramountplus|voot|udemy|coursera|skillshare|masterclass|audible)\.[a-z.]+$"),
    ("youtube", r"(^|\.)(youtube\.com|youtu\.be|youtube-nocookie\.com)$"),
    ("twitch", r"(^|\.)twitch\.tv$"),
    ("kick", r"(^|\.)kick\.com$"),
    ("tiktok", r"(^|\.)tiktok\.com$"),
    ("instagram", r"(^|\.)instagram\.com$"),
    ("facebook", r"(^|\.)(facebook\.com|fb\.watch)$"),
    ("x", r"(^|\.)(twitter\.com|x\.com)$"),
    ("vimeo", r"(^|\.)vimeo\.com$"),
    ("dailymotion", r"(^|\.)(dailymotion\.com|dai\.ly)$"),
    ("rumble", r"(^|\.)rumble\.com$"),
    ("reddit", r"(^|\.)(reddit\.com|redd\.it)$"),
]
NAMES = {"youtube": "YouTube", "twitch": "Twitch", "kick": "Kick", "tiktok": "TikTok", "instagram": "Instagram", "facebook": "Facebook", "x": "X (Twitter)", "vimeo": "Vimeo",
         "dailymotion": "Dailymotion", "rumble": "Rumble", "reddit": "Reddit", "other": "this site", "drm": "this service"}

TIPS = {
    "own": "This is on a channel you connected. You can clip and post it.",
    "creative-commons": "The site marks this video Creative Commons (reuse allowed). Credit the creator in the description and keep the meaning unchanged.",
    "ask": "The creator keeps the rights. Posting clips of it without their OK can get a copyright claim or a strike. Ask them, or look for a clipping programme "
           "(the About page, a pinned comment or their Discord usually link the rules).",
    "unknown": "We couldn't read this page's licence. Only post it if you made it or have written permission.",
    "blocked": "Auto Clip can't clip this one.",
}
BLOCK_WHY = {
    "drm": "Paid streaming services protect their videos (DRM) and forbid copying them. Auto Clip does not clip these.",
    "private": "This video is private or needs a login. Clip only videos that are public, or upload a file you own.",
    "subscriber_only": "This is members-only content. The creator hasn't made it public, so it isn't for clipping.",
    "premium_only": "This is paid (Premium) content. It isn't for clipping.",
    "needs_auth": "This video needs a login to watch, so it isn't for clipping.",
}
PLATFORM_ASK = {
    "twitch": "Twitch streams belong to the streamer. Many welcome clips, but downloading a VOD and reposting it needs their OK. Check their panels or Discord for clip rules.",
    "kick": "Kick streams belong to the streamer. Many welcome clips, but ask or check their rules before reposting.",
    "tiktok": "TikTok videos belong to their creators. Reposting someone's video (even edited) usually needs their permission.",
    "instagram": "Instagram posts belong to their creators. Reposting needs their permission.",
    "facebook": "Facebook videos belong to their creators. Reposting needs their permission.",
    "x": "Videos on X belong to their creators. Reposting needs their permission.",
    "reddit": "Videos on Reddit belong to whoever made them, not to Reddit. Reposting needs their permission.",
}
_CACHE: dict[str, tuple[float, dict]] = {}


def platform(url: str) -> str:
    import urllib.parse
    host = (urllib.parse.urlparse(url.strip()).hostname or "").lower()
    for name, rx in SITES:
        if re.search(rx, host):
            return name
    return "other"


def _meta(url: str) -> dict | None:
    if not intake.have_ytdlp():
        return None
    try:
        r = subprocess.run([sys.executable, "-m", "yt_dlp", "--no-playlist", "--skip-download", "--dump-single-json", "--no-warnings", url],
                           capture_output=True, text=True, timeout=45)
        return json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else None
    except Exception:  # noqa: BLE001 - a failed look is "unknown", never an error the person sees
        return None


def live_state(m: dict) -> str | None:
    st = str(m.get("live_status") or "")
    if m.get("is_live") or st == "is_live":
        return "live"
    if st == "is_upcoming":
        return "upcoming"
    if st == "post_live":
        return "processing"
    if m.get("was_live") or st == "was_live":
        return "past"
    return None


def _blocked(plat: str, why: str, extra: dict | None = None) -> dict:
    return {"verdict": "blocked", "clippable": False, "platform": plat, "tip": BLOCK_WHY.get(why, TIPS["blocked"]), "notes": [], "title": "", "channel": "", "links": {}, "live": None, **(extra or {})}


def check(url: str, extra: dict | None = None) -> dict:
    """The verdict for a link. `extra` lets tests skip the network. Answers are remembered for 10 minutes (the form asks as you type, then again when you press the button)."""
    url = intake.public_url(url)
    hit = _CACHE.get(url)
    if extra is None and hit and time.time() - hit[0] < 600:
        return hit[1]
    res = _check(url, extra)
    if extra is None:
        _CACHE[url] = (time.time(), res)
    return res


def _check(url: str, extra: dict | None) -> dict:
    plat = platform(url)
    if plat == "drm":
        return _blocked(plat, "drm")
    m = extra if extra is not None else _meta(url)
    if not m:
        return {"verdict": "unknown", "clippable": True, "platform": plat, "tip": TIPS["unknown"], "notes": [], "title": "", "channel": "", "links": {}, "live": None}
    avail = str(m.get("availability") or "")
    if avail in BLOCK_WHY:
        return _blocked(plat, avail, {"title": str(m.get("title") or "")[:120], "channel": str(m.get("channel") or m.get("uploader") or "")[:80]})
    lic = str(m.get("license") or "")
    cid = m.get("channel_id") or ""
    mine = {c["id"] for c in youtube.channels()} if plat == "youtube" else set()
    if cid and cid in mine:
        verdict = "own"
    elif re.search(r"creative commons|\bcc[ -]by\b|^by(-[a-z]+)*$", lic.lower()):
        verdict = "creative-commons"
    else:
        verdict = "ask"
    tip = TIPS[verdict]
    if verdict == "ask" and plat in PLATFORM_ASK:
        tip = PLATFORM_ASK[plat] + " " + TIPS["ask"].split(". ", 1)[1]
    links: dict[str, str] = {}
    if m.get("channel_url") or m.get("uploader_url"):
        ch = (m.get("channel_url") or m.get("uploader_url")).rstrip("/")
        links = {"channel": ch, "about": ch + "/about" if plat == "youtube" else ch}
    st = live_state(m)
    notes: list[str] = []
    clippable = True
    if st == "live":
        notes.append("This is live right now. Auto Clip records the next few minutes of it, then clips what it recorded.")
    elif st == "upcoming":
        clippable = False
        notes.append("This stream hasn't started yet. Come back when it is live or finished.")
    elif st == "processing":
        clippable = False
        notes.append("This stream just ended and the site is still preparing the recording. Try again in a while.")
    elif st == "past":
        notes.append("This was a live stream: the streamer's face, voice and chat are theirs.")
    dur = m.get("duration")
    if dur and dur > 3 * 3600 and plat in ("youtube", "twitch"):
        notes.append(f"This is {dur / 3600:.1f} hours long. Set a start and end minute below and only that part is downloaded.")
    if m.get("age_limit"):
        notes.append("Age-restricted: it can't be monetised as Shorts.")
    return {"verdict": verdict, "clippable": clippable, "platform": plat, "tip": tip, "notes": notes, "title": str(m.get("title") or "")[:120],
            "channel": str(m.get("channel") or m.get("uploader") or "")[:80], "license": lic or "Standard licence", "thumbnail": m.get("thumbnail") or "",
            "duration": dur, "links": links, "live": {"state": st} if st else None,
            "tags": [str(x) for x in (m.get("tags") or [])][:25] + re.findall(r"#(\w{3,30})", str(m.get("description") or ""))[:15]}


def permission_for(verdict: str, ack: bool) -> str:
    """What is saved on the job: own | cc | granted (you said you have permission) | unconfirmed (nothing posts from it yet) | blocked."""
    if verdict == "blocked":
        return "blocked"
    if verdict == "own":
        return "own"
    if verdict == "creative-commons":
        return "cc"
    return "granted" if ack else "unconfirmed"


def can_post(job: dict) -> bool:
    return job.get("permission", "granted") not in ("unconfirmed", "blocked")      # jobs made before this check existed are not blocked
