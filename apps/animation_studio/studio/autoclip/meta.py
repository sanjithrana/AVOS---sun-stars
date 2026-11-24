"""What goes on YouTube with a clip besides the video: the description, the hashtags, the tags and a credit line when the source asks for one."""
from __future__ import annotations

import re
from collections import Counter

STOP = set("the a an and or but if so to of in on at for with is are was were be been it this that these those i you he she we they my your his her our their as by from not no yes do does did have has had will would can could just very really like get got go going what when where who why how there here about into out up down then than too also more most some any all one".split())
BASE = ["Shorts"]
GENERIC = {"moment", "moments", "first", "time", "impossible", "discovery", "firsttime", "this", "that", "thing", "clip", "video", "highlight", "watch"}      # never a hashtag: nobody searches them
GAME_TAGS = ["gaming", "gamingshorts"]

FRANCHISES = {
    "gta6": {"name": "GTA 6", "tags": ["gta6", "gtavi"], "pat": re.compile(r"\bgta\s*(?:6|vi|six)\b|grand theft auto\s*(?:6|vi|six)\b", re.I)},
    "gta5": {"name": "GTA 5", "tags": ["gta5", "gtav"], "pat": re.compile(r"\bgta\s*(?:5|v|five)\b|grand theft auto\s*(?:5|v|five)\b|\bgta\s*online\b", re.I)},
}
MOMENT_TAGS = {"cop chase": "copchase", "crash": "carcrash", "epic fail": "fails", "glitch": "glitch", "funny moment": "funny", "first-time discovery": "firsttime",
               "rage moment": "rage", "impossible stunt": "stunt"}
TOPICS = {"npc": "npc", "physics": "physics", "helicopter": "helicopter", "tank": "tank", "plane": "plane", "police": "police", "graphics": "graphics", "trailer": "trailer",
          "leak": "leaks", "basketball": "basketball", "heist": "heist", "robbery": "robbery"}
PEOPLE = {"kai cenat": "kaicenat", "kaicenat": "kaicenat", "ishowspeed": "ishowspeed", "i show speed": "ishowspeed", "adin ross": "adinross", "xqc": "xqc", "pewdiepie": "pewdiepie",
          "mrbeast": "mrbeast", "caseoh": "caseoh", "plaqueboymax": "plaqueboymax", "duke dennis": "dukedennis"}


def detect(text: str, source_title: str = "") -> str | None:
    """The game a clip is about, from what is said in it and the source video's title: "gta6", "gta5", or None when unclear or both are named equally often."""
    hits = {k: 3 * len(f["pat"].findall(text or "")) + len(f["pat"].findall(source_title or "")) for k, f in FRANCHISES.items()}   # what is said beats what the uploader titled it
    ranked = sorted(hits.items(), key=lambda kv: -kv[1])
    if ranked[0][1] == 0 or ranked[0][1] == ranked[1][1]:
        return None
    return ranked[0][0]


def franchise_prefix(preset_prefix: str, detected: str | None) -> tuple[str, str]:
    """(prefix for the title, a note for the person when it differs from the preset's). A GTA 5 clip is never titled GTA 6: viewers who click for GTA 6 leave at once."""
    known = {f["name"].lower() for f in FRANCHISES.values()}
    if detected and (preset_prefix or "").lower() in known and FRANCHISES[detected]["name"].lower() != preset_prefix.lower():
        n = FRANCHISES[detected]["name"]
        return n, f"The footage is {n}, not {preset_prefix}, so the title and tags say {n}."
    return preset_prefix, ""


def clean_ai_tags(tags: list[str], detected: str | None) -> list[str]:
    """Drop AI tags that name a game version the footage is not."""
    wrong = {t for k, f in FRANCHISES.items() if detected and k != detected for t in f["tags"]}
    return [t for t in tags if t.lower() not in wrong]


def _has(text: str, word: str) -> bool:
    return re.search(r"(?<![a-z])" + re.escape(word) + r"(?![a-z])", text) is not None


def tags_in(description: str) -> list[str]:
    return [t.lower() for t in re.findall(r"#(\w+)", description or "")]


def learn(rows: list[dict]) -> dict[str, float]:
    """tag -> how many times the channel's usual views that tag's clips got. rows = [{tags, views}]. Only tags used on 3+ clips count, so one lucky clip does not decide."""
    if len(rows) < 6:
        return {}
    avg = sum(r["views"] for r in rows) / len(rows) or 1.0
    per: dict[str, list[int]] = {}
    for r in rows:
        for t in set(r.get("tags") or []):
            per.setdefault(t, []).append(int(r["views"]))
    return {t: round((sum(v) / len(v)) / avg, 2) for t, v in per.items() if len(v) >= 3}


_LIFT: dict = {"at": 0.0, "v": {}}


def lift() -> dict[str, float]:
    """Which of this channel's hashtags brought more views than usual, from clips posted 2+ days ago. Cached for ten minutes. {} until there is enough data."""
    import time
    if time.time() - _LIFT["at"] < 600:
        return _LIFT["v"]
    rows: list[dict] = []
    try:
        from . import store
        from datetime import datetime, timezone
        for j in store.listing():
            for c in (store.load(j["id"]).get("clips") or []):
                st, at = c.get("stats"), c.get("posted_at")
                if c.get("youtube_id") and st and at and not st.get("removed"):
                    try:
                        age = (datetime.now(timezone.utc) - datetime.fromisoformat(at)).total_seconds() / 86400
                    except (TypeError, ValueError):
                        continue
                    if age >= 2:
                        rows.append({"tags": tags_in(c.get("description") or ""), "views": int(st.get("views") or 0)})
    except Exception:  # noqa: BLE001 - tags are never worth failing a post for
        rows = []
    _LIFT.update(at=time.time(), v=learn(rows))
    return _LIFT["v"]



def tag(w: str) -> str:
    """One hashtag word: letters and digits only, CamelCase kept, never longer than 30."""
    w = re.sub(r"[^\w]", "", str(w), flags=re.U).strip("_")
    return w[:30]


def keywords(text: str, n: int = 4) -> list[str]:
    ws = re.findall(r"[A-Za-z][A-Za-z']{3,}", (text or "").lower()) + re.findall(r"[\u0900-\u097F\u0600-\u06FF\u0400-\u04FF]{3,}", text or "")     # English, plus Hindi, Arabic and Russian words
    c = Counter(w for w in ws if w not in STOP)
    return [w.replace("'", "") for w, _ in c.most_common(n)]


def hashtags(clip: dict, extra: list[str] | None = None, limit: int = 5, source_title: str = "", lift_map: dict[str, float] | None = None) -> list[str]:
    """At most `limit` tags (3 to 5 is the sweet spot: YouTube shows the first three above the title and ignores all of them past 15). In order: the game exactly as the footage
    (never a version it is not), the moment, the AI's tags, who or what is in the clip, tags that worked on this channel, #Shorts, then keywords from what is said.
    Among the optional tags, ones with proven results on this channel come first."""
    text = clip.get("text") or ""
    fr = clip.get("franchise") or detect(text, source_title) or None
    seen: list[str] = []

    def add(w: str) -> None:
        t = tag(w)
        if t and t.lower() not in {x.lower() for x in seen} and len(seen) < limit:
            seen.append(t)

    room = max(1, limit - 1)                                     # one slot is kept for #Shorts

    def add_opt(w: str) -> None:
        if len(seen) < room:
            add(w)

    if fr in FRANCHISES:
        for t in FRANCHISES[fr]["tags"]:
            add_opt(t)
    if clip.get("moment") in MOMENT_TAGS:
        add_opt(MOMENT_TAGS[clip["moment"]])
    low = f" {text} {clip.get('title') or ''} {source_title} ".lower()
    opt = [t for p, t in PEOPLE.items() if _has(low, p)] + [t for w, t in TOPICS.items() if _has(low, w)] + list(extra or [])
    opt += list(clean_ai_tags(re.findall(r"#(\w+)", clip.get("description") or ""), fr))
    uniq: list[str] = []
    for t in opt:
        if t.lower() not in {x.lower() for x in uniq}:
            uniq.append(t)
    lm = lift_map or {}
    if lm:
        uniq.sort(key=lambda t: -lm.get(t.lower(), 1.0))
    for t in uniq:
        add_opt(t)
    for b in BASE:
        add(b)
    if fr in FRANCHISES:
        for g in GAME_TAGS:
            add(g)
    for w in (clip.get("moment") or "").replace("-", " ").split():
        if w.lower() not in GENERIC:
            add(w)
    for w in keywords(text or clip.get("title") or ""):
        if w.lower() not in GENERIC:
            add(w)
    return seen


def channel_tag(job: dict | None) -> str:
    """The source channel as a hashtag (CamelCase letters and digits), so the clip is found next to the original."""
    who = str(((job or {}).get("source") or {}).get("channel") or "")
    return tag("".join(w[:1].upper() + w[1:] for w in re.split(r"\s+", who) if w))[:24] if len(who) >= 3 else ""


def handle(job: dict | None) -> str:
    """The source channel's @handle when its URL has one (youtube.com/@name), else ''."""
    m = re.search(r"/(@[\w.-]+)", str(((job or {}).get("source") or {}).get("channel_url") or ""))
    return m.group(1) if m else ""


def mention_title(title: str, job: dict | None, clip: dict | None = None) -> str:
    """'Title @channel' when it fits in 95 characters: a mention in the title notifies the channel and shows the clip next to theirs.
    The person in the clip (from the packaging team) comes before the channel that uploaded it."""
    sm = ((clip or {}).get("seo") or {}).get("mentions") or []
    h = sm[0] if sm else handle(job)
    t = (title or "").strip()
    return f"{t} {h}" if h and h.lower() not in t.lower() and len(t) + len(h) + 1 <= 95 else t


def source_tags(job: dict | None, n: int = 3) -> list[str]:
    """Hashtags the source channel itself uses on this video (its tag field and the #tags in its description), the most specific first."""
    out: list[str] = []
    for w in ((job or {}).get("source") or {}).get("tags") or []:
        t = tag(re.sub(r"\s+", "", str(w)))
        if len(t) >= 4 and t.lower() not in GENERIC and t.lower() not in {x.lower() for x in out} and t.lower() not in ("shorts", "youtube", "viral", "trending"):
            out.append(t)
    return out[:n]


def credit(job: dict | None) -> str:
    """Names the channel the footage came from, always: 'Source: <channel> (@handle) <url>', plus the licence when there is a non-standard one."""
    if not job:
        return ""
    src = job.get("source") or {}
    who = str(src.get("channel") or src.get("uploader") or "").strip()
    url = src.get("url") or ""
    lic = str(src.get("license") or "")
    if lic.lower().startswith("standard"):
        lic = ""
    if not who and not url:
        return ""
    h = handle(job)
    head = "Source: " + (who or "original video") + (f" ({h})" if h and h.lower() not in who.lower() else "")
    return " ".join(x for x in (head, url, f"({lic})" if lic else "") if x)


def caption_line(clip: dict) -> str:
    """The one line under the video: the clip's description (or its title), without hashtags, list markers or "Highlight N", one sentence."""
    raw = re.sub(r"\s*#\w+", "", clip.get("description") or "").strip()
    raw = re.sub(r"(?im)^\s*(source:.*|🎬.*|highlight\s*\d+.*|\d+[.)]\s*)$", "", raw).strip()
    line = next((x.strip(" -•") for x in raw.splitlines() if x.strip(" -•")), "") or (clip.get("title") or "")
    line = re.sub(r"(?i)^highlight\s*\d+\s*[:\-]?\s*", "", line).strip()
    if len(line) > 150:
        line = line[:150].rsplit(" ", 1)[0] + "…"
    return line


def build(clip: dict, job: dict | None = None, extra: list[str] | None = None, limit: int = 5) -> tuple[str, list[str]]:
    """(description with hashtags at the end, tags list for the video's tag field)."""
    src_title = ((job or {}).get("title") or "") if job else ""
    try:
        lm = lift()
    except Exception:  # noqa: BLE001
        lm = {}
    ct = channel_tag(job)
    seo = [tag(t) for t in ((clip.get("seo") or {}).get("hashtags") or []) if tag(t)]
    if seo:                                   # the packaging team's tags (what the top Shorts on this topic use) come first, then the source channel, then #Shorts
        keep: list[str] = []
        for t in seo[:3] + ([ct] if ct else []) + seo[3:]:
            if t and t.lower() not in {k.lower() for k in keep} and t.lower() != "shorts":
                keep.append(t)
        tags = keep[: max(1, limit - 1)] + ["Shorts"]
    else:
        tags = hashtags(clip, ([ct] if ct else []) + source_tags(job) + list(extra or []), limit, src_title, lm)
    body = caption_line(clip)
    desc = "\n\n".join(x for x in (body, " ".join("#" + t for t in tags)) if x)          # one caption line, then the hashtags: no "Source:" line, no list
    return desc, [t for t in tags if t.lower() != "shorts"][:10]
