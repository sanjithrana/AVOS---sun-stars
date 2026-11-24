"""Comments on the clips you posted: read them, set spam aside, draft replies (you approve every one; nothing is ever posted by itself), and collect what the audience keeps asking for.

Spam is caught by plain rules (links, "sub4sub", phone numbers, crypto and betting pitches, copy-pasted text, shouting). It is only *flagged*: you can release a comment, or ask YouTube
to hold it for review. A reply is a draft until you press Post."""
from __future__ import annotations

import re
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from . import store, youtube

_last = 0.0
SPAM_RX = [(re.compile(r"https?://|www\.|\b\w+\.(com|net|org|io|xyz|ru|top)/", re.I), "has a link"),
           (re.compile(r"sub\s*4\s*sub|sub for sub|check (out )?my (channel|video|profile)|visit my|follow me|first view", re.I), "asks for subs or views"),
           (re.compile(r"whats?app|telegram|\+?\d[\d\s-]{8,}\d|dm me|text me|contact me", re.I), "contact details"),
           (re.compile(r"crypto|bitcoin|forex|invest(ment)? (with|plan)|giveaway|you('ve| have) won|claim (your )?(prize|reward)|betting|casino|promo ?code", re.I), "a money or prize pitch"),
           (re.compile(r"(.)\1{9,}"), "repeated characters")]
REQUEST_RX = re.compile(r"(?:make|do|create|show|cover|try|review|explain|teach)\s+(?:a |an |one |another |the |us |me )?(?:video |one |part \d+ )?(?:on|about|of|for|with)\s+([^.!?\n]{3,60})|"
                        r"(?:please|pls|plz)\s+(?:make|do|cover|show|explain)\s+([^.!?\n]{3,60})|"
                        r"(?:can|could|would) you (?:please )?(?:make|do|cover|show|explain|review|try)\s+([^.!?\n]{3,60})|"
                        r"\b(part\s*(?:2|two|3|three)|next part|full video|long version|tutorial)\b|"
                        r"how (?:do|to|can) (?:i |you |we )?([^.!?\n]{4,60})", re.I)
CLEAN_WORDS = re.compile(r"[^a-z0-9' ]")


def _file():
    return store.ROOT / "comments.json"


def load() -> dict:
    d = store._read(_file(), None) or {}
    d.setdefault("items", {})
    d.setdefault("last_sync", None)
    return d


def _save(d: dict) -> None:
    store._write(_file(), d)


def classify(text: str, author_channel: str = "", own: set[str] | None = None, dup: int = 1) -> dict:
    """{"spam": bool, "why": str, "request": phrase | None}. Your own comments are never spam."""
    if own and author_channel in own:
        return {"spam": False, "why": "", "request": None, "own": True}
    why = next((w for rx, w in SPAM_RX if rx.search(text)), "")
    letters = [c for c in text if c.isalpha()]
    if not why and len(letters) >= 25 and sum(c.isupper() for c in letters) / len(letters) > 0.8:
        why = "shouting"
    if not why and dup >= 3:
        why = "the same text posted several times"
    if not why and text.count("@") >= 3:
        why = "tags many people"
    req = None
    if not why:
        m = REQUEST_RX.search(text)
        if m:
            req = next((g for g in m.groups() if g), m.group(0)).strip().lower()
    return {"spam": bool(why), "why": why, "request": req}


TEMPLATES = {"request": "Thanks for the idea! I'm adding it to the list for a future video.", "question": "Good question! I'll go into this in more detail soon, so stay tuned.",
             "praise": "Thank you, that means a lot! More coming soon."}


def _kind(text: str) -> str:
    t = text.lower()
    if "?" in t:
        return "question"
    if REQUEST_RX.search(t):
        return "request"
    return "praise"


def draft_reply(item: dict, s: dict | None = None, log: Any = None) -> dict:
    """A short, friendly reply. With an AI helper it is written for this comment; otherwise a template. Always a draft."""
    if s:
        try:
            from ..series import writers
            if writers.uses_ai(s):
                data = writers.ask(s, "story", writers.system("avos-comment-reply", "You reply to YouTube comments for a small creator. Write ONE short, warm, honest reply (at most 25 words), no emojis, "
                                                                  'no promises you cannot keep, never ask for subs. Answer ONE JSON object: {"reply":"..."}.'),
                                   f"Video: {item.get('video_title', '')}\nComment by {item.get('author', '')}: {item['text'][:400]}", log, max_tokens=120, temperature=0.6)
                r = " ".join(str((data or {}).get("reply") or "").split())[:300] if isinstance(data, dict) else ""
                if r:
                    return {"text": r, "by": "ai"}
        except Exception:  # noqa: BLE001 - falls back to a template
            pass
    return {"text": TEMPLATES[_kind(item["text"])], "by": "template"}


def sync(reader: Callable[..., list[dict]] | None = None, limit_videos: int = 12, s: dict | None = None) -> dict:
    """Read the comments on your most recent posted clips and add the new ones. Returns counts and which channels need to be connected again."""
    rd = reader or youtube.comments
    d = load()
    items = d["items"]
    own = {c["id"] for c in (store.accounts().get("channels") or {}).values()}
    posted = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    for j in store.listing():
        job = store.load(j["id"])
        for c in job.get("clips") or []:
            at = None
            try:
                at = datetime.fromisoformat(c.get("posted_at") or "")
            except ValueError:
                pass
            if c.get("youtube_id") and c.get("channel") and at and at > cutoff:
                posted.append((at, j["id"], c))
    posted.sort(key=lambda x: x[0], reverse=True)
    new, bad = 0, set()
    for _at, jid, c in posted[:limit_videos]:
        if c["channel"] in bad:
            continue
        try:
            rows = rd(c["channel"], c["youtube_id"])
        except youtube.NeedsScope:
            bad.add(c["channel"])
            continue
        except Exception:  # noqa: BLE001
            continue
        texts = Counter(" ".join(r["text"].lower().split()) for r in rows)
        for r in rows:
            if r["id"] in items:
                items[r["id"]]["likes"], items[r["id"]]["replies"] = r["likes"], r["replies"]
                continue
            k = classify(r["text"], r.get("author_channel") or "", own, texts[" ".join(r["text"].lower().split())])
            if k.get("own"):
                continue
            it = {"id": r["id"], "vid": c["youtube_id"], "channel": c["channel"], "jid": jid, "n": c["n"], "video_title": c.get("title") or "", "author": r["author"], "text": r["text"],
                  "likes": r["likes"], "replies": r["replies"], "at": r["at"], "status": "spam" if k["spam"] else ("answered" if r["replies"] else "new"), "why": k["why"], "request": k["request"],
                  "draft": None, "seen": store.now()}
            items[r["id"]] = it
            new += 1
    # drafts for the comments worth answering: new, not spam, most liked first
    todo = sorted((i for i in items.values() if i["status"] == "new" and not i.get("draft")), key=lambda i: (-i["likes"], i["at"]))[:15]
    for it in todo:
        it["draft"] = draft_reply(it, s)
    d["items"] = items
    d["last_sync"] = store.now()
    _save(d)
    return {"new": new, "needs_reconnect": sorted(bad), "drafted": len(todo)}


def maybe_sync() -> bool:
    """Every 3 hours, from the autopilot loop, but only once the comment feature has been used (there is a comments file)."""
    global _last
    if time.time() - _last < 3 * 3600 or not _file().is_file():
        return False
    _last = time.time()
    sync()
    return True


FILLER = {"a", "an", "the", "to", "me", "us", "please", "pls", "plz", "your", "video", "videos", "on", "about", "of", "for", "with", "make", "do", "one", "another", "part", "it", "this", "that", "you", "i", "can", "how"}


def ideas(items: dict | None = None, top: int = 10) -> list[dict]:
    """What viewers keep asking for: the requests found in comments. Requests that share their key words ("the new map", "new map pls") are one idea; most repeated first, likes added up."""
    items = items if items is not None else load()["items"]
    groups: list[dict] = []
    for it in sorted(items.values(), key=lambda i: i["at"]):
        if it["status"] == "spam" or not it.get("request"):
            continue
        words = frozenset(w for w in CLEAN_WORDS.sub("", it["request"].lower()).split() if w not in FILLER)
        if not words:
            words = frozenset(CLEAN_WORDS.sub("", it["request"].lower()).split()[:3])
        if not words:
            continue
        g = next((g for g in groups if g["words"] <= words or words <= g["words"] or len(g["words"] & words) / len(g["words"] | words) >= 0.5), None)
        if g is None:
            g = {"words": set(words), "idea": " ".join(sorted(words, key=lambda w: it["request"].lower().find(w)))[:50], "count": 0, "likes": 0, "examples": []}
            groups.append(g)
        g["count"] += 1
        g["likes"] += it["likes"]
        if len(g["examples"]) < 2:
            g["examples"].append(it["text"][:140])
    return [{k: v for k, v in g.items() if k != "words"} for g in sorted(groups, key=lambda g: (-g["count"], -g["likes"]))[:top]]


def view(status: str | None = None) -> dict:
    d = load()
    rows = sorted(d["items"].values(), key=lambda i: (i["status"] != "new", -i["likes"], i["at"]), reverse=False)
    counts = Counter(i["status"] for i in d["items"].values())
    if status:
        rows = [r for r in rows if r["status"] == status]
    return {"items": rows[:80], "counts": dict(counts), "ideas": ideas(d["items"]), "last_sync": d["last_sync"]}


def set_status(cid: str, status: str, **kw: Any) -> dict:
    d = load()
    it = d["items"].get(cid)
    if not it:
        raise KeyError("No such comment.")
    it["status"] = status
    it.update(kw)
    _save(d)
    return it


def post_reply(cid: str, text: str, poster: Callable[[str, str, str], str] | None = None) -> dict:
    d = load()
    it = d["items"].get(cid)
    if not it:
        raise KeyError("No such comment.")
    text = " ".join(str(text or "").split())
    if not text:
        raise ValueError("Write a reply first.")
    (poster or youtube.reply)(it["channel"], it["id"], text)
    return set_status(cid, "answered", replied=text, replied_at=store.now())
