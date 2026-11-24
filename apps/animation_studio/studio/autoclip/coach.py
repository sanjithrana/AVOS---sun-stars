"""The coach: looks at every clip you posted, works out what made some do better, and changes how the next ones are made.

How it learns (honestly): this is a multi-armed bandit, the small-data form of reinforcement learning. Every clip is made from a "recipe"
(caption style, edit style, zoom, stickers, music mood). When its views and likes come back, the recipe gets a reward. Each choice keeps a score for how
well it has done; the coach mostly picks the choice with the best score, but keeps trying others a bit (so it can discover something better).
With a handful of clips a day a bandit is what works; a deep network would only memorise noise.

What it can't see: the YouTube Data API only gives views, likes and comments. It does not give watch time or retention, so the reward is views per day (capped
at the first week) plus how many viewers liked or commented. Nothing here decides about the *content*: titles and length are only observed and reported."""
from __future__ import annotations

import json
import math
import random
import re
from datetime import datetime, timezone
from typing import Any

from . import store

OPTIONS: dict[str, list[Any]] = {
    "caption": ["bounce", "hype", "clean"],
    "edit": ["classic", "punchy", "clean"],
    "look": ["clean", "cinematic", "vivid", "warm", "cool", "film"],
    "zoom": [True, False],
    "stickers": [True, False],
    "music": ["none", "chill", "upbeat", "epic", "happy"],
}
LABELS = {"caption": "Caption style", "edit": "Edit style", "look": "Colour look", "zoom": "Zoom effects", "stickers": "Callouts", "music": "Music"}
DEFAULT = {"mode": "off", "dims": {"caption": True, "edit": True, "look": True, "zoom": True, "stickers": True, "music": False}, "explore": 0.1, "last_run": None, "insights": None}
MIN_AGE_H = 36


def _file():
    return store.ROOT / "coach.json"


def config() -> dict:
    c = store._read(_file(), None) or {}
    out = json.loads(json.dumps(DEFAULT))
    out.update({k: c[k] for k in ("mode", "explore", "last_run", "insights") if k in c})
    out["dims"].update({k: bool(v) for k, v in (c.get("dims") or {}).items() if k in OPTIONS})
    if out["mode"] not in ("off", "suggest", "auto"):
        out["mode"] = "off"
    return out


def save(cfg: dict) -> dict:
    full = dict(store._read(_file(), None) or {})
    full.update(cfg)                                    # keep the change log that lives in the same file
    store._write(_file(), full)
    return cfg


def set_config(b: dict) -> dict:
    c = config()
    if b.get("mode") in ("off", "suggest", "auto"):
        c["mode"] = b["mode"]
    if isinstance(b.get("dims"), dict):
        c["dims"].update({k: bool(v) for k, v in b["dims"].items() if k in OPTIONS})
    if "explore" in b:
        try:
            c["explore"] = max(0.0, min(0.4, float(b["explore"])))
        except (TypeError, ValueError):
            pass
    return save(c)


# ---------- recipes ----------
def len_bucket(sec: float) -> str:
    return "under 20s" if sec < 20 else "20-35s" if sec < 35 else "35-50s" if sec < 50 else "50s+"


def title_style(t: str) -> str:
    t = t or ""
    if "?" in t:
        return "question"
    if re.search(r"\d", t):
        return "has a number"
    if t.isupper() and len(t) > 6:
        return "ALL CAPS"
    return "statement"


def hour_bucket(h: int) -> str:
    return "night (0-6)" if h < 6 else "morning (6-12)" if h < 12 else "afternoon (12-17)" if h < 17 else "evening (17-24)"


def recipe_of(o: dict, ed: dict | None, c: dict) -> dict:
    mus = (ed or {}).get("music")
    return {"caption": o.get("caption"), "edit": (ed or {}).get("style") or "off", "look": (ed or {}).get("look") or "none", "zoom": bool((ed or {}).get("zooms")), "stickers": bool((ed or {}).get("stickers")),
            "music": (mus or {}).get("mood") or "none", "length": len_bucket(c["end"] - c["start"]), "title": title_style(c.get("title") or ""), "layout": o.get("layout")}


# ---------- what happened ----------
def _age_days(iso: str | None) -> float | None:
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(iso)).total_seconds() / 86400
    except (TypeError, ValueError):
        return None


def reward(st: dict, age_days: float) -> float:
    v = int(st.get("views") or 0)
    eng = (int(st.get("likes") or 0) + 3 * int(st.get("comments") or 0)) / max(v, 20)
    return math.log1p(v / min(max(age_days, 1.0), 7.0)) + 8.0 * min(eng, 0.25)


def observations() -> list[dict]:
    """[{recipe, reward (raw), channel, views, likes, comments, jid, n, title, vid, hour}] for posted clips old enough to judge."""
    from . import postqueue
    rows: dict[str, dict] = {}
    for j in store.listing():
        job = store.load(j["id"])
        for c in job.get("clips") or []:
            if c.get("youtube_id") and c.get("recipe"):
                rows[c["youtube_id"]] = {"recipe": c["recipe"], "stats": c.get("stats"), "at": c.get("posted_at"), "channel": c.get("channel") or "", "jid": j["id"], "n": c["n"],
                                         "title": c.get("title") or "", "retention": c.get("retention"), "exp": c.get("exp")}
    try:
        for p in postqueue._load().get("posts") or []:
            s = p.get("src") or {}
            if p.get("status") == "posted" and p.get("youtube_id") and s.get("jid"):
                job = store.load(s["jid"])
                c = next((x for x in job["clips"] if x["n"] == s["n"]), None)
                if c and c.get("recipe"):
                    rows.setdefault(p["youtube_id"], {"recipe": c["recipe"], "title": c.get("title") or "", "jid": s["jid"], "n": s["n"], "channel": p["channel"], "at": None, "stats": None,
                                                      "retention": c.get("retention"), "exp": c.get("exp")})
                    rows[p["youtube_id"]].update(stats=p.get("stats") or rows[p["youtube_id"]]["stats"], at=p.get("posted_at") or p.get("started") or rows[p["youtube_id"]]["at"])
    except Exception:  # noqa: BLE001 - the queue may not exist yet
        pass
    out = []
    for vid, r in rows.items():
        st, age = r.get("stats"), _age_days(r.get("at"))
        if not st or st.get("removed") or age is None or age * 24 < MIN_AGE_H:
            continue
        out.append({**r, "vid": vid, "views": st.get("views", 0), "likes": st.get("likes", 0), "comments": st.get("comments", 0), "raw": reward(st, age),
                    "hour": datetime.fromisoformat(r["at"]).astimezone(timezone.utc).hour if r.get("at") else None})
    _add_watch_time(out)
    _normalise(out)
    return out


WATCH_WEIGHT = 2.5


def _add_watch_time(obs: list[dict]) -> None:
    """Watch time counts too, when YouTube Analytics has it: average % watched adds up to WATCH_WEIGHT to a clip's reward. Clips without it get their channel's typical value,
    so having numbers or not doesn't tilt the comparison."""
    have = [o["retention"]["avg_view_pct"] for o in obs if o.get("retention")]
    if not have:
        return
    sh = sorted(have)
    med = (sh[len(sh) // 2] + sh[(len(sh) - 1) // 2]) / 2
    for o in obs:
        pct = o["retention"]["avg_view_pct"] if o.get("retention") else med
        o["raw"] += WATCH_WEIGHT * min(pct, 100.0) / 100.0
        o["watch_pct"] = pct


def _normalise(obs: list[dict]) -> None:
    """Rewards relative to the same channel (a 200-view channel and a 20k-view channel aren't comparable), as z-scores."""
    by: dict[str, list[dict]] = {}
    for o in obs:
        by.setdefault(o["channel"], []).append(o)
    for rows in by.values():
        m = sum(r["raw"] for r in rows) / len(rows)
        sd = max(0.5, math.sqrt(sum((r["raw"] - m) ** 2 for r in rows) / len(rows)))
        for r in rows:
            r["reward"] = (r["raw"] - m) / sd


def arms(obs: list[dict], dim: str) -> list[dict]:
    """per choice: n, mean reward, posterior mean (shrunk to 0 with one pseudo-observation), and the uncertainty."""
    out = []
    for opt in OPTIONS.get(dim, []):
        r = [o["reward"] for o in obs if o["recipe"].get(dim) == opt]
        n = len(r)
        post = sum(r) / (n + 1)
        out.append({"option": opt, "n": n, "mean": round(sum(r) / n, 3) if n else None, "score": round(post, 3), "sd": round(1 / math.sqrt(n + 1), 3),
                    "avg_views": round(sum(o["views"] for o in obs if o["recipe"].get(dim) == opt) / n) if n else None})
    return out


def draw(o: dict, rng: random.Random | None = None) -> dict:
    """Thompson sampling: one random draw from each choice's belief, take the highest. Returns option overrides for one clip."""
    cfg = config()
    rng = rng or random.Random()
    obs = observations()
    over: dict[str, Any] = {}
    for dim, on in cfg["dims"].items():
        if not on:
            continue
        if rng.random() < cfg["explore"]:
            over[dim] = rng.choice(OPTIONS[dim])
            continue
        best = max(arms(obs, dim), key=lambda a: rng.gauss(a["score"], a["sd"]))
        over[dim] = best["option"]
    if "music" in over:
        over["music"] = over["music"] if over["music"] == "none" else over["music"]
    if "edit" in over and over["edit"] not in ("classic", "punchy", "clean"):
        over["edit"] = "classic"
    return over


def best_choices(min_n: int = 3) -> dict[str, Any]:
    """The choices that are clearly ahead (at least `min_n` clips each and the best posterior): what 'Apply best to defaults' sets."""
    obs = observations()
    out = {}
    for dim in OPTIONS:
        a = [x for x in arms(obs, dim) if x["n"] >= min_n]
        if len(a) >= 2:
            top = max(a, key=lambda x: x["score"])
            if top["score"] > 0:
                out[dim] = top["option"]
    return out


# ---------- what the coach changed, and undoing it ----------
def _log(kind: str, **kw: Any) -> dict:
    cfg = config()
    full = dict(store._read(_file(), None) or {})
    rows = list(full.get("changes") or [])
    row = {"id": store.new_id(), "at": store.now(), "kind": kind, "undone": False, **kw}
    rows.append(row)
    full.update(cfg)
    full["changes"] = rows[-120:]
    store._write(_file(), full)
    return row


def changes(limit: int = 40) -> list[dict]:
    return list(reversed((store._read(_file(), None) or {}).get("changes") or []))[:limit]


def log_draw(jid: str, n: int, baseline: dict, drawn: dict) -> None:
    """Auto mode: remember what this clip would have been without the coach (baseline) and what the coach made it. Only differences are logged."""
    diff = {k: {"from": baseline.get(k), "to": v} for k, v in drawn.items() if baseline.get(k) != v}
    if diff:
        _log("clip", jid=jid, n=n, diff=diff)


def apply_best() -> dict:
    """Write the best choices into the Auto Clip defaults so every future clip starts there. The previous values are kept so it can be undone."""
    b = best_choices()
    st = store.settings()
    d = st["defaults"]
    before = {k: d.get(k) for k in b}
    for k, v in b.items():
        d[k] = v
    store.save_settings(st)
    if b:
        _log("defaults", diff={k: {"from": before[k], "to": v} for k, v in b.items() if before[k] != v})
    return b


def undo(cid: str) -> dict:
    """Undo one change. defaults: put the old default values back (only the ones still at the coach's value). clip: returns what to re-render the clip with."""
    full = dict(store._read(_file(), None) or {})
    rows = full.get("changes") or []
    row = next((r for r in rows if r["id"] == cid), None)
    if not row:
        raise KeyError("No such change.")
    if row.get("undone"):
        raise ValueError("Already undone.")
    out: dict = {"kind": row["kind"]}
    if row["kind"] == "defaults":
        st = store.settings()
        back = {}
        for k, d in row["diff"].items():
            if st["defaults"].get(k) == d["to"]:
                st["defaults"][k] = d["from"]
                back[k] = d["from"]
        store.save_settings(st)
        out["restored"] = back
    else:
        out.update(jid=row["jid"], n=row["n"], body={k: d["from"] for k, d in row["diff"].items()})
    row["undone"] = True
    full["changes"] = rows
    store._write(_file(), full)
    return out


# ---------- reporting ----------
def tables(obs: list[dict]) -> dict:
    t = {dim: arms(obs, dim) for dim in OPTIONS}
    for key in ("length", "title"):
        vals = sorted({o["recipe"].get(key) for o in obs if o["recipe"].get(key)})
        t[key] = [{"option": v, "n": sum(1 for o in obs if o["recipe"].get(key) == v), "mean": round(sum(o["reward"] for o in obs if o["recipe"].get(key) == v) / max(1, sum(1 for o in obs if o["recipe"].get(key) == v)), 3),
                   "avg_views": round(sum(o["views"] for o in obs if o["recipe"].get(key) == v) / max(1, sum(1 for o in obs if o["recipe"].get(key) == v)))} for v in vals]
    hrs = sorted({hour_bucket(o["hour"]) for o in obs if o["hour"] is not None})
    t["hour"] = [{"option": h, "n": sum(1 for o in obs if o["hour"] is not None and hour_bucket(o["hour"]) == h),
                  "mean": round(sum(o["reward"] for o in obs if o["hour"] is not None and hour_bucket(o["hour"]) == h) / max(1, sum(1 for o in obs if o["hour"] is not None and hour_bucket(o["hour"]) == h)), 3)} for h in hrs]
    return t


def rule_insights(obs: list[dict], tabs: dict) -> dict:
    """Plain findings without any AI: the best and worst choice in each row that has enough clips."""
    do_more, avoid = [], []
    for dim, rows in tabs.items():
        ok = [r for r in rows if r["n"] >= 2 and r.get("mean") is not None]
        if len(ok) < 2:
            continue
        top, low = max(ok, key=lambda r: r["mean"]), min(ok, key=lambda r: r["mean"])
        if top["mean"] - low["mean"] < 0.3:
            continue
        name = LABELS.get(dim, {"length": "Length", "title": "Title style", "hour": "Posting time"}.get(dim, dim))
        do_more.append(f"{name}: “{_nice(top['option'])}” did best ({top['n']} clips)")
        avoid.append(f"{name}: “{_nice(low['option'])}” did worst ({low['n']} clips)")
    n = len(obs)
    summary = (f"{n} posted clips have been measured." if n else "No clips are old enough to judge yet (they need about a day and a half and some views).")
    if n and n < 12:
        summary += " That is still few, so treat these as hints, not facts."
    return {"summary": summary, "do_more": do_more[:6], "avoid": avoid[:6], "title_tips": [], "hashtag_tips": [], "experiments": [], "by": "rules"}


def _nice(v: Any) -> str:
    return {True: "on", False: "off"}.get(v, str(v)) if isinstance(v, bool) else str(v)


def ai_insights(obs: list[dict], tabs: dict, base: dict, log=None) -> dict:
    """The words: ask the AI (local or paid helper from Auto Clip's crew setting) to explain the tables and suggest what to test next. Falls back to the rules."""
    from ..series import writers
    s = {"id": "coach", "crew": store.settings()["defaults"].get("crew") or "builtin", "language": "en", "format": {"width": 720, "height": 1280}, "settings": {"models": {}, "local_only": False}}
    if not writers.uses_ai(s) or len(obs) < 4:
        return base
    top = sorted(obs, key=lambda o: -o["views"])[:5]
    low = sorted(obs, key=lambda o: o["views"])[:3]
    prompt = ("Tables (reward is a z-score within the channel; higher is better):\n" + json.dumps(tabs)[:3500] + "\nBest clips:\n"
              + "\n".join(f"- {o['title']} | {o['views']} views, {o['likes']} likes | {json.dumps(o['recipe'])}" for o in top)
              + "\nWorst clips:\n" + "\n".join(f"- {o['title']} | {o['views']} views | {json.dumps(o['recipe'])}" for o in low))
    system = ("You are a YouTube Shorts growth analyst. Use ONLY the numbers given; if a difference rests on fewer than 3 clips, say it is a guess. "
              'Answer ONE JSON object: {"summary":"two sentences","do_more":["..."],"avoid":["..."],"title_tips":["..."],"hashtag_tips":["..."],"experiments":["one change to test next"]} '
              "with at most 4 short items per list and no invented numbers.")
    try:
        data = writers.ask(s, "story", writers.system("avos-coach", system), prompt, log, max_tokens=700, temperature=0.3)
    except Exception:  # noqa: BLE001
        return base
    if not isinstance(data, dict):
        return base
    out = dict(base)
    out["by"] = "ai"
    for k in ("summary",):
        if isinstance(data.get(k), str) and data[k].strip():
            out[k] = " ".join(data[k].split())[:500]
    for k in ("do_more", "avoid", "title_tips", "hashtag_tips", "experiments"):
        if isinstance(data.get(k), list):
            out[k] = [" ".join(str(x).split())[:200] for x in data[k] if str(x).strip()][:4]
    return out


def learned_tags(obs: list[dict], limit: int = 3) -> list[str]:
    """Hashtags from the best third of clips: words that appear in the titles of top performers and not in the bottom."""
    from . import meta
    if len(obs) < 6:
        return []
    srt = sorted(obs, key=lambda o: -o["reward"])
    k = max(2, len(srt) // 3)
    top = meta.keywords(" ".join(o["title"] for o in srt[:k]), 12)
    bot = set(meta.keywords(" ".join(o["title"] for o in srt[-k:]), 12))
    return [w for w in top if w not in bot][:limit]


def analyse(log=None, force: bool = False) -> dict:
    cfg = config()
    obs = observations()
    tabs = tables(obs)
    from . import experiments, retention
    base = rule_insights(obs, tabs)
    rs = retention.summary(obs)
    if rs:
        base["avoid"] = (base["avoid"] + rs["tips"])[:6]
    ex = experiments.summary()
    if ex["tips"]:
        base["title_tips"] = (base["title_tips"] + ex["tips"])[:4]
    ins = ai_insights(obs, tabs, base, log)
    cfg["insights"] = {**ins, "n": len(obs), "tables": tabs, "best": best_choices(), "tags": learned_tags(obs), "at": store.now(), "retention": rs, "experiments": ex}
    cfg["last_run"] = store.now()
    save(cfg)
    return cfg


def maybe_analyse() -> bool:
    """Once a day, called from the autopilot tick."""
    cfg = config()
    if cfg["mode"] == "off":
        return False
    age = _age_days(cfg.get("last_run"))
    if age is not None and age < 1:
        return False
    analyse()
    return True


def tags_for_posting() -> list[str]:
    cfg = config()
    return list(((cfg.get("insights") or {}).get("tags")) or []) if cfg["mode"] != "off" else []


def view() -> dict:
    cfg = config()
    return {**cfg, "changes": changes(), "options": {k: [_nice(x) if isinstance(x, bool) else x for x in v] for k, v in OPTIONS.items()}, "labels": LABELS}


def lead_in() -> int:
    """Seconds before a hype peak that a clip starts: shortened when watch-time data shows viewers leave early. Only in Auto mode, with enough clips."""
    from . import retention
    if config()["mode"] != "auto":
        return 2
    return retention.lead_in(retention.summary(observations()))
