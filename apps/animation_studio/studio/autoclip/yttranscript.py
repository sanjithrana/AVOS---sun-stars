"""YouTube's own transcript for a video, read in a second without downloading anything.

Uses youtube-transcript-api (github.com/jdepoix/youtube-transcript-api, MIT). Order of preference: captions a person wrote
in English or Hindi, then any written captions, then YouTube's automatic captions in those languages, then the automatic
captions in whatever language is spoken. It gives lines with a start and a length, not word times, so each line's time is
shared between its words by their length: close enough to pick moments; the final captions are still listened to per clip.

yt-dlp stays the tool for the video, the replay graph, live chat, comments and json3 captions (which do have word times);
this is the quick first try and the fallback when yt-dlp's caption download is refused."""
from __future__ import annotations

import re
from typing import Any

LANGS = ("en", "en-US", "en-GB", "en-IN", "hi")
_ID = re.compile(r"(?:v=|youtu\.be/|/shorts/|/live/|/embed/|/v/)([A-Za-z0-9_-]{11})")
_NOISE = re.compile(r"\[(?:music|applause|laughter|laughs|__|inaudible|noise|cheering)[^\]]*\]|♪+", re.I)


def available() -> bool:
    try:
        import youtube_transcript_api  # noqa: F401
        return True
    except ImportError:
        return False


def video_id(url: str) -> str | None:
    m = _ID.search(url or "")
    if m:
        return m.group(1)
    return url if re.fullmatch(r"[A-Za-z0-9_-]{11}", url or "") else None


def _session() -> Any:
    """A web session carrying your cookies.txt (if you added one), so videos that need a signed-in viewer still work."""
    import requests
    from http.cookiejar import MozillaCookieJar
    from .intake import _cookies
    s = requests.Session()
    path = _cookies()
    if path:
        try:
            jar = MozillaCookieJar(path)
            jar.load(ignore_discard=True, ignore_expires=True)
            s.cookies.update(jar)
        except Exception:  # noqa: BLE001 - a broken cookies file is the same as none
            pass
    return s


def pick(tl: Any, langs: tuple[str, ...] = LANGS) -> Any:
    """The best transcript in a TranscriptList: written before automatic, your languages before others."""
    items = list(tl)
    if not items:
        return None
    rank = {c: i for i, c in enumerate(langs)}

    def score(t: Any) -> tuple[int, int]:
        code = str(getattr(t, "language_code", "") or "")
        lang = rank.get(code, rank.get(code.split("-")[0], len(langs)))
        return (1 if getattr(t, "is_generated", False) else 0, lang)
    written_mine = [t for t in items if not t.is_generated and score(t)[1] < len(langs)]
    if written_mine:
        return min(written_mine, key=score)
    written = [t for t in items if not t.is_generated]
    auto_mine = [t for t in items if t.is_generated and score(t)[1] < len(langs)]
    if written:
        return min(written, key=score)
    if auto_mine:
        return min(auto_mine, key=score)
    return items[0]                                           # the automatic captions in the spoken language


def to_cues(snips: list[dict]) -> list[dict]:
    """Lines {text, start, duration} into our cues, with each word's time estimated from its length."""
    cues: list[dict] = []
    for i, sn in enumerate(snips):
        text = " ".join(_NOISE.sub(" ", str(sn.get("text") or "")).replace("\n", " ").split())
        if not text:
            continue
        t0 = float(sn.get("start") or 0.0)
        dur = float(sn.get("duration") or 0.0) or 2.0
        nxt = float(snips[i + 1].get("start") or 0.0) if i + 1 < len(snips) else t0 + dur
        end = min(t0 + dur, nxt) if nxt > t0 else t0 + dur     # auto-captions overlap; stop where the next line starts
        end = max(end, t0 + 0.3)
        ws = text.split()
        total = sum(len(w) + 1 for w in ws)
        t, words = t0, []
        for w in ws:
            span = (end - t0) * (len(w) + 1) / total
            words.append({"w": w, "s": round(t, 3), "e": round(t + max(0.08, span * 0.92), 3)})
            t += span
        cues.append({"start": round(t0, 3), "end": round(end, 3), "text": text, "words": words})
    return cues


def fetch(url: str, langs: tuple[str, ...] = LANGS, log: Any = None) -> tuple[list[dict] | None, str]:
    """(cues, what was used) or (None, why not). Never raises."""
    vid = video_id(url)
    if not vid:
        return None, "not a YouTube video"
    if not available():
        return None, "youtube-transcript-api is not installed"
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        api = YouTubeTranscriptApi(http_client=_session())
        t = pick(api.list(vid), langs)
        if t is None:
            return None, "this video has no captions"
        got = t.fetch()
        raw = got.to_raw_data() if hasattr(got, "to_raw_data") else list(got)
        cues = to_cues(raw)
        label = f"YouTube's {'automatic' if t.is_generated else 'written'} {getattr(t, 'language', t.language_code)} captions"
        if log:
            log(f"Read {label} ({len(cues)} lines) without downloading anything.")
        return (cues or None), label
    except Exception as e:  # noqa: BLE001 - disabled captions, blocked IP, age gate: the other ways still work
        why = type(e).__name__
        msg = {"TranscriptsDisabled": "captions are turned off for this video", "NoTranscriptFound": "no captions in a usable language",
               "VideoUnavailable": "the video is unavailable", "RequestBlocked": "YouTube blocked the request (add cookies.txt or try later)",
               "IpBlocked": "YouTube blocked this computer's address for now", "AgeRestricted": "the video is age-restricted (add cookies.txt)"}.get(why, f"{why}: {str(e)[:120]}")
        return None, msg
