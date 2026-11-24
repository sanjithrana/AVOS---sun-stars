"""Title (and cover) tests. A posted clip starts with variant A. After the test window it is switched to variant B for the same time, then the numbers are compared
and the better one is kept; if B is not clearly better the original A is put back. Every step is written on the clip so you can see what happened.

Honest limits, shown in the screen too:
- YouTube's API gives views, not impressions or click-through rate, so this compares views per hour in two windows, not a proper split test.
- The second window is later in the video's life, and views fall off with time. That favours A. So "B won" means something; "A won" or "no clear winner" may just be timing.
- B wins only when the difference is statistically clear (one-sided 95%), the rate is at least 20% higher, and there are at least 100 views to judge by.
- Custom covers on Shorts are often ignored by YouTube's feed, so the cover test is off unless you turn it on."""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from . import coach, store, youtube

MIN_VIEWS = 100
Z95 = 1.645
RATIO = 1.2


def _t(iso: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(iso) if iso else None
    except ValueError:
        return None


def prepare(s: dict, d: Path, c: dict, video: Path, log: Any = None) -> dict | None:
    """At cutting time: make variant B for a clip (a second title from the AI, a second cover) when tests are on. None when there is nothing to test."""
    cfg = store.settings().get("experiments") or {}
    if not cfg.get("enabled"):
        return None
    from . import cut, pick
    out: dict[str, Any] = {"title_b": None, "cover_b": None}
    try:
        out["title_b"] = pick.alt_title(s, c.get("text") or "", c.get("title") or "", log)
    except Exception:  # noqa: BLE001 - a test is never worth stopping a clip for
        out["title_b"] = None
    if cfg.get("thumbnails"):
        rel = f"clips/clip-{c['n']}-cover-b.jpg"
        try:
            dur = max(2.0, float(c["end"]) - float(c["start"]))
            if cut.cover(str(video), str(d / rel), (out["title_b"] or c.get("title") or ""), at=dur * 0.5, style="b"):
                out["cover_b"] = rel
        except Exception:  # noqa: BLE001
            pass
    return out if (out["title_b"] or out["cover_b"]) else None


def begin(jid: str, n: int, now: datetime | None = None) -> bool:
    """Right after a clip is posted: arm its test."""
    job = store.load(jid)
    c = next((x for x in job["clips"] if x["n"] == n), None)
    v = (c or {}).get("variants")
    if not c or not v or c.get("exp") or not c.get("youtube_id"):
        return False
    cfg = store.settings().get("experiments") or {}
    t = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    exp = {"phase": "A", "t0": t, "window_h": int(cfg.get("window_hours") or 24), "title_a": c["title"], "title_b": v.get("title_b"), "cover_a": c.get("cover"),
           "cover_b": v.get("cover_b"), "style_a": coach.title_style(c["title"]), "style_b": coach.title_style(v.get("title_b") or c["title"]), "snaps": [{"at": t, "views": 0, "p": "A start"}],
           "result": None}
    store.update(jid, lambda j: [x.update(exp=exp) for x in j["clips"] if x["n"] == n])
    return True


def evaluate(va: int, ha: float, vb: int, hb: float) -> dict:
    """Two windows of views: is B's rate clearly higher? Under 'no difference', B's share of all views is hb/(ha+hb); a normal approximation to that binomial gives z."""
    n = va + vb
    ra, rb = va / max(ha, 1e-9), vb / max(hb, 1e-9)
    p = hb / (ha + hb)
    z = (vb - n * p) / math.sqrt(n * p * (1 - p)) if n > 0 else 0.0
    ratio = rb / ra if ra > 0 else (math.inf if rb > 0 else 1.0)
    winner = None
    note = f"Not enough views to judge ({n}; need {MIN_VIEWS})."
    if n >= MIN_VIEWS:
        if z >= Z95 and ratio >= RATIO:
            winner, note = "B", f"B got {ratio:.2f}x the views per hour (z={z:.1f})."
        elif z <= -Z95:
            winner, note = "A", f"A got {1 / ratio if ratio else 99:.2f}x the views per hour (z={z:.1f}); partly because B ran later."
        else:
            note = f"No clear difference (B/A = {ratio:.2f}x, z={z:.1f})."
    return {"winner": winner, "z": round(z, 2), "rate_a": round(ra, 2), "rate_b": round(rb, 2), "views_a": va, "views_b": vb, "note": note}


def _apply(cid: str, vid: str, d: Path, title: str | None, cover: str | None, setter: dict) -> list[str]:
    notes = []
    if title:
        try:
            setter["title"](cid, vid, title)
        except Exception as e:  # noqa: BLE001
            notes.append("title: " + str(e)[:100])
    if cover and (d / cover).is_file():
        try:
            setter["thumb"](cid, vid, str(d / cover))
        except Exception as e:  # noqa: BLE001
            notes.append("cover: " + str(e)[:100])
    return notes


def tick(now: datetime | None = None, viewer: Callable[[str, str], int | None] | None = None, setter: dict | None = None) -> int:
    """Move tests forward: switch A -> B when A's window is over, judge and settle when B's is over. Returns how many clips changed."""
    now = now or datetime.now(timezone.utc)
    viewer = viewer or (lambda ch, vid: (youtube.stats(ch, [vid]).get(vid) or {}).get("views"))
    setter = setter or {"title": youtube.set_title, "thumb": youtube.set_thumbnail}
    moved = 0
    for j in store.listing():
        job = store.load(j["id"])
        d = store.jdir(j["id"])
        for c in job.get("clips") or []:
            e = c.get("exp")
            if not e or e.get("phase") not in ("A", "B") or not c.get("youtube_id") or not c.get("channel"):
                continue
            t0 = _t(e["t0"])
            if e["phase"] == "A" and t0 and now >= t0 + timedelta(hours=e["window_h"]):
                due = True
            elif e["phase"] == "B" and _t(e.get("switched_at")) and now >= _t(e["switched_at"]) + timedelta(hours=e["window_h"]):
                due = True
            else:
                due = False
            if not due:
                continue
            try:
                views = viewer(c["channel"], c["youtube_id"])
            except Exception:  # noqa: BLE001
                views = None
            if views is None:
                continue
            ch, vid, n = c["channel"], c["youtube_id"], c["n"]
            snaps = list(e["snaps"]) + [{"at": now.isoformat(timespec="seconds"), "views": int(views), "p": e["phase"] + " end"}]
            ne = dict(e, snaps=snaps)
            if e["phase"] == "A":
                notes = _apply(ch, vid, d, e.get("title_b"), e.get("cover_b"), setter)
                ne.update(phase="B", switched_at=now.isoformat(timespec="seconds"), notes=notes)
                if not e.get("title_b") and not e.get("cover_b"):
                    ne.update(phase="done", result={"winner": None, "note": "Nothing to test."})
            else:
                va = snaps[1]["views"] - snaps[0]["views"]
                vb = snaps[2]["views"] - snaps[1]["views"]
                res = evaluate(va, e["window_h"], vb, e["window_h"])
                if res["winner"] != "B":                                 # keep the original unless B is clearly better
                    res["notes"] = _apply(ch, vid, d, e["title_a"] if e.get("title_b") else None, e.get("cover_a") if e.get("cover_b") else None, setter)
                res["kept"] = "B" if res["winner"] == "B" else "A"
                ne.update(phase="done", result=res)
            store.update(j["id"], lambda x, nn=n, v=ne: [y.update(exp=v) for y in x["clips"] if y["n"] == nn])
            moved += 1
    return moved


def summary() -> dict:
    """What the finished tests say, for the coach: how often each title style won."""
    tests = []
    for j in store.listing():
        for c in store.load(j["id"]).get("clips") or []:
            e = c.get("exp")
            if e and e.get("phase") == "done" and e.get("result") and e["result"].get("note") != "Nothing to test.":
                tests.append({"jid": j["id"], "n": c["n"], "a": e["title_a"], "b": e.get("title_b"), "style_a": e["style_a"], "style_b": e["style_b"], "kept": e["result"].get("kept"),
                              "winner": e["result"].get("winner"), "note": e["result"].get("note")})
    wins_b = sum(1 for t in tests if t["kept"] == "B")
    tips = []
    by: dict[str, int] = {}
    for t in tests:
        if t["kept"] == "B" and t["style_b"] != t["style_a"]:
            by[t["style_b"]] = by.get(t["style_b"], 0) + 1
    for style, k in sorted(by.items(), key=lambda x: -x[1]):
        tips.append(f"A “{style}” title beat the original in {k} of {len(tests)} tests.")
    return {"n": len(tests), "wins_b": wins_b, "tests": tests[-10:], "tips": tips[:2]}
