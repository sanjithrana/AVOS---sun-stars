"""The packaging team: before a clip is posted, look at what already works for the same topic and package the clip the same way.

1. Researcher  - builds the search from what is in the clip (who: "IShowSpeed", what: "GTA 6"), then finds the most-viewed Shorts on it:
                 the YouTube Data API with your connected channel (best), else yt-dlp search (no login needed).
2. Analyst     - scores every hashtag by the views of the Shorts that use it (log views, so one giant video does not decide alone),
                 counts the @mentions and the sounds ("Raya (Slowed) - Zericxxn") those Shorts use, and how their titles look.
3. Writer      - your AI crew (Ollama, Groq, OpenAI, Claude, Gemini) writes the title, description, hashtags and mentions for THIS clip
                 from the clip's own words and that research. With the built-in crew, rules do the same job.
4. Checker     - hashtags must come from the research or from what is really in the clip; mentions must be real handles;
                 the title may not promise what the clip does not show. Anything else the writer returns is dropped.

Sounds: YouTube does not let an app attach a sound from its library, and downloading a song from someone's Short is not allowed.
So the team tells you which sound the top Shorts use, and when a track of that name is on your music shelf it is used automatically."""
from __future__ import annotations

import json
import math
import re
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from . import meta, store

CACHE_HOURS = 12
SPAM = {"shorts", "short", "viral", "trending", "fyp", "foryou", "foryoupage", "explore", "explorepage", "youtubeshorts", "ytshorts", "subscribe", "like",
        "likes", "follow", "share", "comment", "views", "video", "videos", "new", "best", "top"}
HANDLES = {"ishowspeed": "@IShowSpeed", "kaicenat": "@KaiCenat", "xqc": "@xQc", "mrbeast": "@MrBeast", "adinross": "@adinross", "caseoh": "@caseoh_",
           "pewdiepie": "@PewDiePie", "dukedennis": "@DukeDennis", "plaqueboymax": "@PlaqueBoyMax"}
NAMES = {"ishowspeed": "IShowSpeed", "kaicenat": "Kai Cenat", "xqc": "xQc", "mrbeast": "MrBeast", "adinross": "Adin Ross", "caseoh": "CaseOh",
         "pewdiepie": "PewDiePie", "dukedennis": "Duke Dennis", "plaqueboymax": "PlaqueBoyMax"}


# ---------- 1. the search ----------
def people_in(text: str, source_channel: str = "") -> list[str]:
    low = f" {text} ".lower()
    found = [t for p, t in meta.PEOPLE.items() if meta._has(low, p)]
    sc = (source_channel or "").lower().replace(" ", "")
    for key in HANDLES:
        if key in sc and key not in found:
            found.insert(0, key)
    if "speed" in sc and "ishowspeed" not in found:
        found.insert(0, "ishowspeed")
    out: list[str] = []
    for f in found:
        if f not in out:
            out.append(f)
    return out[:3]


def query_for(job: dict, clip: dict) -> str:
    """'IShowSpeed GTA 6': who + which game, from the clip's words, the video's title and the channel. Falls back to the video's main words."""
    src = job.get("source") or {}
    text = " ".join([clip.get("text") or "", clip.get("title") or "", job.get("title") or "", " ".join(src.get("tags") or [])])
    who = [NAMES.get(p, p) for p in people_in(text, src.get("channel") or "")][:1]
    fr = clip.get("franchise") or meta.detect(text, job.get("title") or "")
    game = [meta.FRANCHISES[fr]["name"]] if fr in meta.FRANCHISES else []
    if who or game:
        return " ".join(who + game)
    words = [w for w in meta.keywords(job.get("title") or clip.get("title") or "", 4) if w.lower() not in meta.GENERIC]
    return " ".join(words[:3]) or (clip.get("title") or "")[:40]


def _cache(q: str) -> Any:
    p = store.ROOT / "research" / (re.sub(r"[^a-z0-9]+", "-", q.lower()).strip("-")[:80] + ".json")
    return p


def _api_search(q: str, n: int) -> list[dict] | None:
    """Top Shorts by views from the YouTube Data API, through your first connected channel (100 quota units a search)."""
    from . import youtube
    chans = [c for c in youtube.channels() if not c.get("needs_login")]
    if not chans:
        return None
    tok = youtube.token(chans[0]["id"])
    h = {"Authorization": "Bearer " + tok}
    rows: dict[str, dict] = {}
    for after in ((datetime.now(timezone.utc) - timedelta(days=120)).strftime("%Y-%m-%dT%H:%M:%SZ"), None):     # recent first, then all-time
        params = {"part": "snippet", "q": q + " #shorts", "type": "video", "videoDuration": "short", "order": "viewCount", "maxResults": min(50, n), "safeSearch": "moderate"}
        if after:
            params["publishedAfter"] = after
        r = youtube._req("GET", f"{youtube.API}/search", params=params, headers=h)
        if r.status_code != 200:
            raise RuntimeError("YouTube search refused: " + youtube._err(r))
        for it in r.json().get("items") or []:
            vid = (it.get("id") or {}).get("videoId")
            if vid:
                rows.setdefault(vid, {"id": vid})
        if len(rows) >= n:
            break
    ids = list(rows)[: n]
    if not ids:
        return []
    r = youtube._req("GET", f"{youtube.API}/videos", params={"part": "snippet,statistics,contentDetails", "id": ",".join(ids)}, headers=h)
    if r.status_code != 200:
        raise RuntimeError("YouTube refused the video details: " + youtube._err(r))
    out = []
    for v in r.json().get("items") or []:
        sn, st = v.get("snippet") or {}, v.get("statistics") or {}
        m = re.match(r"PT(?:(\d+)M)?(?:(\d+)S)?$", (v.get("contentDetails") or {}).get("duration") or "")
        dur = (int(m.group(1) or 0) * 60 + int(m.group(2) or 0)) if m else None
        out.append({"id": v["id"], "title": sn.get("title") or "", "description": (sn.get("description") or "")[:1500], "tags": sn.get("tags") or [],
                    "channel": sn.get("channelTitle") or "", "views": int(st.get("viewCount") or 0), "duration": dur, "published": sn.get("publishedAt")})
    return out


def _ytdlp(args: list[str], timeout: int = 90) -> str:
    from .intake import ytdlp_base
    r = subprocess.run(ytdlp_base() + ["--no-warnings", *args], capture_output=True, text=True, timeout=timeout)
    return r.stdout if r.returncode == 0 else ""


def _ytdlp_search(q: str, n: int) -> list[dict]:
    """Search without a login: yt-dlp's YouTube search, best by views."""
    raw = _ytdlp(["--flat-playlist", "--dump-single-json", f"ytsearch{n}:{q} #shorts"], 120)
    try:
        ents = json.loads(raw).get("entries") or []
    except ValueError:
        return []
    out = []
    for e in ents:
        if not e or not e.get("id"):
            continue
        dur = e.get("duration")
        if dur and dur > 180:
            continue
        out.append({"id": e["id"], "title": e.get("title") or "", "description": (e.get("description") or "")[:1500], "tags": [], "channel": e.get("channel") or e.get("uploader") or "",
                    "views": int(e.get("view_count") or 0), "duration": dur})
    return out


def _details(ids: list[str]) -> dict[str, dict]:
    """Description, tags and the sound (track / artist) of a few Shorts, read with yt-dlp (no download)."""
    out: dict[str, dict] = {}
    for vid in ids:
        raw = _ytdlp(["--skip-download", "--dump-single-json", f"https://www.youtube.com/shorts/{vid}"], 60)
        try:
            d = json.loads(raw)
        except ValueError:
            continue
        out[vid] = {"description": (d.get("description") or "")[:1500], "tags": d.get("tags") or [], "track": d.get("track") or "", "artist": d.get("artist") or d.get("creator") or ""}
    return out


def top_shorts(q: str, n: int = 25, log: Callable[[str], None] | None = None, fresh: bool = False) -> dict:
    """{"query", "source": "api"|"search", "rows": [...]} cached for 12 hours per search."""
    p = _cache(q)
    hit = store._read(p, None)
    if hit and not fresh and time.time() - float(hit.get("t", 0)) < CACHE_HOURS * 3600:
        return hit
    rows, how = None, "search"
    try:
        rows = _api_search(q, n)
        how = "api"
    except Exception as e:  # noqa: BLE001 - fall back to the search that needs no login
        if log:
            log(f"Research: the YouTube API search failed ({str(e)[:100]}); using a plain search instead.")
        rows = None
    if rows is None:
        rows, how = _ytdlp_search(q, n), "search"
    rows = sorted([r for r in rows if r["views"] > 0], key=lambda r: -r["views"])[:n]
    need = [r["id"] for r in rows[:8] if how == "search" or not r.get("description")]
    sound_ids = [r["id"] for r in rows[:6]]
    try:
        det = _details(list(dict.fromkeys(need + sound_ids)))
    except Exception:  # noqa: BLE001
        det = {}
    for r in rows:
        if r["id"] in det:
            d = det[r["id"]]
            r["description"] = r["description"] or d["description"]
            r["tags"] = r["tags"] or d["tags"]
            r["track"], r["artist"] = d["track"], d["artist"]
    res = {"query": q, "source": how, "t": time.time(), "rows": rows}
    p.parent.mkdir(parents=True, exist_ok=True)
    store._write(p, res)
    return res


# ---------- 2. what works ----------
def analyse(rows: list[dict]) -> dict:
    """Hashtags scored by the views of the Shorts using them; mentions and sounds counted the same way."""
    tag_score: Counter = Counter()
    tag_uses: Counter = Counter()
    men: Counter = Counter()
    snd: Counter = Counter()
    snd_name: dict[str, dict] = {}
    lens, emoji = [], 0
    for r in rows:
        w = math.log10(max(10, r["views"]))
        text = f"{r['title']} {r['description']}"
        tags = {t.lower() for t in re.findall(r"#(\w{2,40})", text)} | {re.sub(r"\W", "", t.lower()) for t in (r.get("tags") or [])[:15] if len(t) <= 30}
        for t in tags:
            if t and t not in SPAM and t not in meta.GENERIC and not t.isdigit():
                tag_score[t] += w
                tag_uses[t] += 1
        for m in set(re.findall(r"(?<![\w.])@([A-Za-z0-9_.]{3,30})", text)):
            men["@" + m] += w
        if r.get("track"):
            k = (r["track"] + " - " + (r.get("artist") or "")).lower()
            snd[k] += w
            snd_name.setdefault(k, {"title": r["track"], "artist": r.get("artist") or "", "uses": 0, "views": 0})
            snd_name[k]["uses"] += 1
            snd_name[k]["views"] += r["views"]
        lens.append(len(r["title"]))
        emoji += bool(re.search(r"[\U0001F300-\U0001FAFF☀-➿]", r["title"]))
    hashtags = [{"tag": t, "score": round(s, 1), "uses": tag_uses[t]} for t, s in tag_score.most_common(30) if tag_uses[t] >= 2 or len(rows) < 6]
    return {"hashtags": hashtags[:20], "mentions": [m for m, _ in men.most_common(8)], "sounds": [snd_name[k] for k, _ in snd.most_common(5)],
            "title_len": int(sorted(lens)[len(lens) // 2]) if lens else 0, "emoji_share": round(emoji / len(rows), 2) if rows else 0.0,
            "examples": [{"id": r["id"], "title": r["title"], "views": r["views"], "channel": r["channel"]} for r in rows[:8]]}


# ---------- 3 + 4. write and check ----------
WRITER = ("You are a YouTube Shorts packaging team: a researcher, a title writer, a description writer and a strict checker. "
          "You get ONE clip (its spoken words and what is in it) and research on the most-viewed Shorts about the same topic. "
          "Write the packaging for THIS clip. Answer ONE JSON object only: "
          '{"title": "...", "description": "...", "hashtags": ["...", "..."], "mentions": ["@..."], "hook": "..."}. Rules: '
          "title: under 60 characters, says what really happens in the clip (no invented events, no clickbait the clip does not deliver), in the style of the top titles "
          "(names first, emoji only if the top titles use them); the strongest form is a person + a concrete act or number, or a short line said word for word in the clip that people would argue about; "
          "description: 1-2 short lines a viewer reads, naming who and what, then the mentions; no hashtags in it; "
          "hashtags: 3 to 5, chosen ONLY from the candidate list, most important first, without the # sign; "
          "mentions: only handles from the candidate mentions or the known handles; "
          "hook: the on-screen line for the first second, 2 to 5 words.")


def _rules_pack(clip: dict, cand: list[str], mentions: list[str]) -> dict:
    from .pick import title_for
    body = re.sub(r"\s*#\w+", "", clip.get("description") or "").strip()          # a description the AI ranker already wrote is kept
    line = body or (title_for(clip.get("text") or "", clip.get("n") or 1) or clip.get("title") or "").strip()
    desc = line + ((" " + " ".join(mentions)) if mentions else "")
    return {"title": None, "description": desc.strip(), "hashtags": cand[:5], "mentions": mentions, "hook": None, "by": "rules"}


def recommend(job: dict, clip: dict, research: dict, ask: Callable[[str, str], Any] | None = None) -> dict:
    """The packaging for one clip: {title|None, description, hashtags, mentions, hook|None, sound|None, query, by}."""
    src = job.get("source") or {}
    text = " ".join([clip.get("text") or "", clip.get("title") or "", job.get("title") or ""])
    ppl = people_in(text, src.get("channel") or "")
    fr = clip.get("franchise") or meta.detect(text, job.get("title") or "")
    a = research.get("analysis") or analyse(research.get("rows") or [])
    core = [p for p in ppl] + (meta.FRANCHISES[fr]["tags"][:1] if fr in meta.FRANCHISES else [])
    if clip.get("moment") in meta.MOMENT_TAGS:
        core.append(meta.MOMENT_TAGS[clip["moment"]])
    wrong = {t for k, v in meta.FRANCHISES.items() if k != fr for t in v["tags"]} if fr else set()
    found = [h["tag"] for h in a["hashtags"] if h["tag"] not in wrong]
    had = [t for t in meta.clean_ai_tags(re.findall(r"#(\w+)", clip.get("description") or ""), fr or None) if t.lower() not in SPAM]   # what the AI ranker already wrote from the transcript
    cand: list[str] = []
    for t in core[:2] + found[:6] + core[2:] + found[6:12] + had[:4]:
        if t and t.lower() not in {x.lower() for x in cand}:
            cand.append(t)
    known = [HANDLES[p] for p in ppl if p in HANDLES]
    ment_c = list(dict.fromkeys(known + [m for m in a["mentions"] if m.lower().lstrip("@") in {p for p in ppl} | {h.lower().lstrip("@") for h in known}]))
    pack = _rules_pack(clip, cand, ment_c[:2])
    if ask:
        prompt = json.dumps({"clip_words": (clip.get("text") or "")[:900], "clip_title_now": clip.get("title"), "moment": clip.get("moment"),
                             "source_video": job.get("title"), "source_channel": src.get("channel"), "who": [NAMES.get(p, p) for p in ppl], "game": meta.FRANCHISES.get(fr, {}).get("name") if fr else None,
                             "top_shorts": [{"title": e["title"], "views": e["views"]} for e in a["examples"]], "candidate_hashtags": cand[:14],
                             "candidate_mentions": ment_c[:6], "known_handles": known, "top_title_length": a["title_len"], "top_titles_use_emoji": a["emoji_share"] >= 0.4},
                            ensure_ascii=False)
        try:
            out = ask(WRITER, prompt)
        except Exception:  # noqa: BLE001 - the rules' pack stands
            out = None
        if isinstance(out, dict):
            okc = {c.lower() for c in cand}
            tags = [re.sub(r"[^\w]", "", str(t)) for t in (out.get("hashtags") or []) if isinstance(t, str)]
            tags = [t for t in tags if t.lower() in okc][:5]
            menu = {m.lower() for m in ment_c}
            ments = [m if str(m).startswith("@") else "@" + str(m) for m in (out.get("mentions") or []) if isinstance(m, str)]
            ments = [m for m in ments if m.lower() in menu][:2]
            title = " ".join(str(out.get("title") or "").split())[:70]
            if title and fr in meta.FRANCHISES:                  # never name a game the footage is not
                for k, v in meta.FRANCHISES.items():
                    if k != fr and v["pat"].search(title):
                        title = ""
            desc = re.sub(r"\s*#\w+", "", " ".join(str(out.get("description") or "").split()))[:300]
            hook = " ".join(str(out.get("hook") or "").split()[:6])[:40]
            pack = {"title": title or None, "description": (desc or pack["description"]).strip(), "hashtags": tags if len(tags) >= 2 else pack["hashtags"],
                    "mentions": ments or pack["mentions"], "hook": hook or None, "by": "ai"}
            if pack["mentions"] and not all(m.lower() in pack["description"].lower() for m in pack["mentions"]):
                pack["description"] = (pack["description"] + " " + " ".join(m for m in pack["mentions"] if m.lower() not in pack["description"].lower())).strip()
    pack["sound"] = a["sounds"][0] if a.get("sounds") else None
    pack["query"] = research.get("query")
    return pack


def sound_on_shelf(sound: dict | None) -> str | None:
    """The id of a track on your music shelf whose name matches the sound the top Shorts use."""
    if not sound:
        return None
    from . import music
    want = re.sub(r"[^a-z0-9]", "", str(sound.get("title") or "").lower())
    if len(want) < 3:
        return None
    for t in music.tracks():
        if t.get("builtin"):
            continue
        have = re.sub(r"[^a-z0-9]", "", str(t.get("name") or "").lower())
        if have and (want in have or have in want):
            return t["id"]
    return None


def run(job: dict, clips: list[dict], ask: Callable[[str, str], Any] | None, log: Callable[[str], None], fresh: bool = False) -> dict:
    """Research once per search, then a pack per clip. Returns {query: research summary}. The clips are changed in place (clip["seo"])."""
    done: dict[str, dict] = {}
    for c in clips:
        q = query_for(job, c)
        if not q:
            continue
        if q not in done:
            try:
                res = top_shorts(q, 25, log, fresh)
            except Exception as e:  # noqa: BLE001 - packaging falls back to the clip's own words
                log(f"Research for '{q}' failed ({str(e)[:120]}).")
                res = {"query": q, "rows": [], "source": "none"}
            res["analysis"] = analyse(res.get("rows") or [])
            done[q] = res
            a = res["analysis"]
            log(f"Research: {len(res.get('rows') or [])} top Shorts for '{q}'. Best hashtags: {', '.join('#' + h['tag'] for h in a['hashtags'][:5]) or 'none found'}"
                + (f". Top sound: {a['sounds'][0]['title']}" + (f" - {a['sounds'][0]['artist']}" if a['sounds'][0]['artist'] else "") if a["sounds"] else "") + ".")
        c["seo"] = recommend(job, c, done[q], ask)
        mid = sound_on_shelf(c["seo"].get("sound"))
        if mid:
            c["seo"]["music_id"] = mid
    return {q: {"query": q, "source": r.get("source"), "analysis": r["analysis"]} for q, r in done.items()}
