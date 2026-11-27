"""Which stretches to cut. Loudness first (ffmpeg measures every second), then the edges move to where somebody stops talking."""
from __future__ import annotations

import json
import re
import subprocess
from typing import Any

from .. import config

LEVEL = re.compile(r"lavfi\.astats\.Overall\.RMS_level=(-?[\d.]+|-?inf|nan)")


def _growth() -> str:
    from . import growth
    g = growth.rules()
    return "\n\n" + g if g else ""


def duration(path: str) -> float:
    r = subprocess.run([config.ffprobe(), "-v", "error", "-show_entries", "format=duration", "-of", "json", path], capture_output=True, text=True, timeout=120)
    try:
        return float(json.loads(r.stdout)["format"]["duration"])
    except Exception as e:  # noqa: BLE001
        raise RuntimeError("That file could not be read as a video.") from e


def loudness(path: str, start: float = 0, end: float | None = None) -> list[float]:
    """RMS level in dB for each second from `start` (index 0 = `start`)."""
    cmd = [config.ffmpeg(), "-v", "error", "-nostdin"]
    if start:
        cmd += ["-ss", f"{start:.2f}"]
    cmd += ["-i", path]
    if end:
        cmd += ["-t", f"{max(1.0, end - start):.2f}"]
    cmd += ["-vn", "-ac", "1", "-af", "aresample=8000,asetnsamples=n=8000:p=0,astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-",
            "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    out = []
    for m in LEVEL.finditer(r.stdout):
        v = m.group(1)
        out.append(-90.0 if "inf" in v or "nan" in v else max(-90.0, float(v)))
    if not out:
        raise RuntimeError("No audio was found in that video, so there is nothing to pick clips from.")
    return out


def _smooth(levels: list[float], k: int = 3) -> list[float]:
    amp = [10 ** (v / 20) for v in levels]                 # dB to amplitude, so one shout counts for more than a long mumble
    return [sum(amp[max(0, i - k): i + k + 1]) / len(amp[max(0, i - k): i + k + 1]) for i in range(len(amp))]


def choose(levels: list[float], count: int, min_s: int, max_s: int, cues: list[dict] | None = None, offset: float = 0.0) -> list[dict]:
    """The `count` best non-overlapping windows: score = how loud and how lively (loud on average, with peaks). Times are in the source's clock."""
    n = len(levels)
    if n < 3:
        return []
    amp = _smooth(levels)
    floor = sorted(amp)[len(amp) // 4] or 1e-9
    norm = [min(a / floor, 50) for a in amp]
    length = max(min_s, min(max_s, (min_s + max_s) // 2 if max_s > min_s else min_s, n))
    length = min(length, n)
    pre = [0.0]
    for x in norm:
        pre.append(pre[-1] + x)
    cand = []
    for s in range(0, n - length + 1):
        mean = (pre[s + length] - pre[s]) / length
        peak = max(norm[s: s + length])
        cand.append((mean + 0.15 * peak, s))
    cand.sort(reverse=True)
    taken: list[tuple[int, int]] = []
    for score, s in cand:
        e = s + length
        if all(e + 3 <= a or s >= b + 3 for a, b in taken):
            taken.append((s, e))
            if len(taken) >= count:
                break
    taken.sort()
    out = []
    for s, e in taken:
        a, b = _snap(s + offset, e + offset, cues or [], min_s, max_s)
        out.append({"start": round(a, 2), "end": round(b, 2), "score": round(sum(norm[s:e]) / max(1, e - s), 2)})
    return out


def _snap(a: float, b: float, cues: list[dict], min_s: int, max_s: int) -> tuple[float, float]:
    """Start where a sentence starts (up to 6 s earlier) and end where one ends (up to 6 s later), inside [min_s, max_s]."""
    if not cues:
        return a, b
    starts = [c["start"] for c in cues if a - 6 <= c["start"] <= a + 2]
    if starts:
        a = min(starts, key=lambda x: abs(x - a))
    ends = [c["end"] for c in cues if b - 2 <= c["end"] <= b + 6]
    if ends:
        b = min(ends, key=lambda x: abs(x - b))
    if b - a > max_s:
        b = a + max_s
    if b - a < min_s:
        b = a + min_s
    return a, b


PROFANE = re.compile(r"\b(?:fuck\w*|shit\w*|bitch\w*|asshole|dick|pussy|cunt|nigg\w*|fag\w*|retard\w*|slut|whore|porn\w*|sex\w*)\b", re.I)
FILLER_START = {"and", "but", "so", "uh", "um", "like", "yeah", "okay", "ok", "well", "oh", "then", "because"}
HYPE_WORDS = {"no way", "what", "bro", "wait", "crazy", "insane", "dead", "dying", "never", "first", "stop", "look", "help", "scared", "caught", "won", "lost", "cheat"}


def _line_score(sent: str) -> float:
    ws = re.findall(r"[A-Za-z0-9']+", sent)
    if not 3 <= len(ws) <= 12:
        return -1.0
    low = sent.lower()
    sc = 1.0 + 0.6 * ("!" in sent) + 0.4 * ("?" in sent) + 0.5 * sum(h in low for h in HYPE_WORDS)
    sc -= 0.8 * (ws[0].lower() in FILLER_START) + 0.3 * abs(len(ws) - 6) / 6
    sc -= 1.5 * bool(PROFANE.search(sent)) + 0.8 * (len({w.lower() for w in ws}) < len(ws) * 0.6)      # a line of repeats ("no no no no") is not a title
    return sc


MOMENT_EMOJI = {"funny": "😂", "rage": "😡", "fail": "💀", "chase": "🚔", "crash": "💥", "win": "🏆", "clutch": "🔥", "scare": "😱", "reaction": "😳"}


def fallback_title(src_title: str, moment: str | None, n: int) -> str:
    """A title when nothing usable is said: the show's name (before its "|" or "-" parts), what kind of moment, and an emoji. Never "Highlight N"."""
    name = re.split(r"\s[|\-–—:]\s|\s+ft\.?\s|\s#", src_title or "")[0]
    name = re.sub(r"[\[\]()🔴•]+", " ", name)
    ws = name.split()
    shouty = ws and sum(w.isupper() for w in ws) >= 0.6 * len(ws)              # an ALL-CAPS title reads better in normal case
    keep = {"GTA", "IPL", "UFC", "NBA", "NFL", "WWE", "AI", "USA", "UK", "FIFA", "PUBG", "BGMI", "MLA", "CEO", "TV"}
    name = " ".join(w.capitalize() if shouty and w.isupper() and w not in keep and not any(ch.isdigit() for ch in w) and len(w) > 1 else w for w in ws)[:45].strip()
    kind = (moment or "").replace("_", " ").strip()
    emo = next((e for k, e in MOMENT_EMOJI.items() if k in kind.lower()), "🔥")
    if name and kind:
        return f"{name}: {kind} {emo}"
    if name:
        return f"{name} {('moment ' + str(n)) if n > 1 else 'best moment'} {emo}"
    return f"You have to see this {emo}"


def title_for(text: str, n: int, src_title: str = "", moment: str | None = None) -> str:
    """No AI crew: the best short line of what is said (a hook, not the first words, never swearing), trimmed on a word edge;
    with nothing usable said, a title from the video's name and the kind of moment."""
    flat = " ".join(text.split())
    sents = [x.strip(" .,-") for x in re.split(r"(?<=[.!?])\s+", flat) if x.strip(" .,-")]
    best = max(sents, key=_line_score, default="")
    if _line_score(best) < 0:
        best = sents[0] if sents else ""
    t = PROFANE.sub(lambda m: m.group(0)[0] + "*" * (len(m.group(0)) - 1), best)
    t = re.sub(r"\s+", " ", re.sub(r"[\[\]>_]+", " ", t)).strip(" .,-")
    if len(t) > 60:
        t = t[:60].rsplit(" ", 1)[0]
    while t.split() and t.split()[-1].lower().strip(".,!?") in FILLER_START | {"the", "a", "an", "of", "to", "with", "that", "this", "in", "at", "for", "is", "was", "my"}:
        t = " ".join(t.split()[:-1])
    return (t[:1].upper() + t[1:]) if t and len(t.split()) >= 2 else fallback_title(src_title, moment, n)


TITLER = ("You write titles for short vertical videos cut from a longer one. For each numbered clip transcript, write one title: at most 8 words, specific, "
          "no clickbait lies, no emojis, no quotation marks, not just a repeat of the first words. "
          "Best titles name who (a person or team named in the words) plus the concrete thing they did or said, or the number; a short line said in the clip that people would argue about works too. Never invent a claim. "
          'Answer ONE JSON object: {"titles":["title for clip 1","title for clip 2", ...]} in the same order.')


def ai_titles(s: dict, texts: list[str], log: Any = None) -> list[str] | None:
    from ..series import writers
    if not writers.uses_ai(s) or not any(texts):
        return None
    data = writers.ask(s, "story", writers.system("avos-autoclip-titles", TITLER) + _growth(),
                       "\n".join(f"Clip {i + 1}: {t[:900]}" for i, t in enumerate(texts)), log, max_tokens=700, temperature=0.6)
    t = (data or {}).get("titles") if isinstance(data, dict) else None
    if isinstance(t, list) and len(t) == len(texts):
        return [" ".join(str(x).split())[:80] or title_for(texts[i], i + 1) for i, x in enumerate(t)]
    return None



RANKER = ("You choose the best moments of a long video to become short vertical clips (TikTok, Reels, Shorts). You get numbered candidate transcripts. "
          "Score each 0-10 for how likely strangers (not only fans) are to watch it to the end, react and share it: a hook in the first sentence, emotion, surprise or a curiosity gap, a clear payoff, and making sense on its own without the rest of the video. "
          "Score low: slow setup, inside jokes, talk that needs earlier context, and moments with nothing happening. "
          "Also write a specific title (at most 8 words, no emojis, no quotation marks): who + the concrete act or number, or a line said in the clip, lead with the feeling or the surprise, and name the game or a person ONLY when the transcript or the source title says so; never name a game version the footage is not. "
          "Then a one-sentence description and 3 or 4 hashtags (single words, no # sign): the game or subject exactly as said, the kind of moment, and who is in it; no tag for anything that is not in the clip. "
          'Answer ONE JSON object: {"clips":[{"n":1,"score":7,"title":"...","description":"...","hashtags":["...","..."]}, ...]} with one entry per candidate.')


def ai_rank(s: dict, moments: list[dict], texts: list[str], count: int, log: Any = None, source_title: str = "") -> tuple[list[int], list[dict]] | None:
    """Ask the crew to score the candidates. Returns (indexes of the best `count`, best first; their metadata) or None when the AI gave nothing usable.
    The AI's score is mixed 70/30 with the loudness score so a quiet but well-said moment can win and a loud, empty one cannot."""
    from ..series import writers
    if not writers.uses_ai(s) or not any(texts):
        return None
    cand = (f"Source video title: {source_title}\n" if source_title else "") + "\n".join(f"Candidate {i + 1} ({m['end'] - m['start']:.0f}s): {t[:700] or '(no words)'}" for i, (m, t) in enumerate(zip(moments, texts)))
    data = writers.ask(s, "story", writers.system("avos-autoclip-ranker", RANKER), cand, log, max_tokens=min(3500, 140 * len(texts) + 400), temperature=0.3)
    rows = (data or {}).get("clips") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return None
    top = max((float(m.get("score") or 0) for m in moments), default=1.0) or 1.0
    got: dict[int, dict] = {}
    for r in rows:
        try:
            i = int(r.get("n")) - 1
            sc = max(0.0, min(10.0, float(r.get("score"))))
        except (TypeError, ValueError, AttributeError):
            continue
        if 0 <= i < len(moments):
            tags = [re.sub(r"[^\w]", "", str(x))[:24] for x in (r.get("hashtags") or []) if str(x).strip()][:4]
            got[i] = {"ai": sc, "title": " ".join(str(r.get("title") or "").split())[:80], "description": " ".join(str(r.get("description") or "").split())[:300],
                      "tags": [t for t in tags if t]}
    if len(got) < max(1, len(moments) // 2):
        return None
    final = {i: 0.7 * g["ai"] / 10 + 0.3 * float(moments[i].get("score") or 0) / top for i, g in got.items()}
    keep = sorted(final, key=lambda i: -final[i])[:count]
    return keep, [got[i] for i in keep]


ALT = ("You write YouTube Shorts titles. You get a clip's transcript and its current title. Write ONE different title for the same clip with a different angle "
       "(a question, a number, or a curiosity gap if the current one is a plain statement; otherwise a plain statement). At most 8 words, no clickbait lies, no emojis, no quotation marks, "
       'must be true to the transcript. Answer ONE JSON object: {"title":"..."}.')


def alt_title(s: dict, text: str, title: str, log: Any = None) -> str | None:
    """A second title for the same clip, for a title test. None without an AI helper (then only the cover can be tested)."""
    from ..series import writers
    if not writers.uses_ai(s) or not text:
        return None
    data = writers.ask(s, "story", writers.system("avos-autoclip-alt-title", ALT), f"Current title: {title}\nTranscript: {text[:900]}", log, max_tokens=120, temperature=0.8)
    t = (data or {}).get("title") if isinstance(data, dict) else None
    t = " ".join(str(t or "").split()).strip("\"'")[:80]
    return t if t and t.lower() != title.lower() else None
