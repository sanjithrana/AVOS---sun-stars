"""Watch time, not just views: where in a clip viewers leave. Read from the YouTube Analytics API for posted clips that are old enough (Google's numbers lag
2-3 days), saved on the clip, and used by the coach as part of the reward and to tune how far before the peak a clip starts."""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from . import store, youtube

_last = 0.0
MIN_AGE_DAYS = 3
REFRESH_DAYS = 4


def _age_days(iso: str | None) -> float | None:
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(iso)).total_seconds() / 86400
    except (TypeError, ValueError):
        return None


def refresh(force: bool = False, reader: Callable[..., dict | None] | None = None) -> dict:
    """Fetch retention for posted clips that have none (or an old copy). Returns {"updated": n, "needs_reconnect": [channel ids]}."""
    global _last
    if not force and time.time() - _last < 3600:
        return {"updated": 0, "needs_reconnect": []}
    _last = time.time()
    rd = reader or youtube.retention
    n, bad = 0, set()
    today = datetime.now(timezone.utc).date().isoformat()
    for j in store.listing():
        job = store.load(j["id"])
        for c in job.get("clips") or []:
            vid, ch = c.get("youtube_id"), c.get("channel")
            if not vid or not ch or ch in bad:
                continue
            age = _age_days(c.get("posted_at"))
            have = c.get("retention") or {}
            if age is None or age < MIN_AGE_DAYS or (have and (_age_days(have.get("at")) or 99) < REFRESH_DAYS):
                continue
            since = (datetime.fromisoformat(c["posted_at"]).date() - timedelta(days=1)).isoformat()
            try:
                data = rd(ch, vid, since, today)
            except youtube.NeedsScope:
                bad.add(ch)
                continue
            except Exception:  # noqa: BLE001 - the next pass tries again
                continue
            if data:
                store.update(j["id"], lambda x, nn=c["n"], d=data: [y.update(retention=d | {"at": store.now()}) for y in x["clips"] if y["n"] == nn])
                n += 1
    return {"updated": n, "needs_reconnect": sorted(bad)}


def summary(obs: list[dict]) -> dict | None:
    """Across the clips that have retention: the average curve and the plain-language reading of it."""
    rs = [o["retention"] for o in obs if o.get("retention") and o["retention"].get("curve")]
    if not rs:
        return None
    n = len(rs)
    curve = [round(sum(r["curve"][i] for r in rs) / n, 3) for i in range(20)]
    avg_pct = round(sum(r["avg_view_pct"] for r in rs) / n, 1)
    early, mid, end = curve[3], curve[10], curve[18]                     # 15%, 50% and 90% of the way through
    tips: list[str] = []
    if early < 0.6:
        tips.append(f"Only {early * 100:.0f}% are still watching 15% into a clip: start closer to the peak and say the hook first.")
    if mid > 0 and end / mid < 0.55:
        tips.append("Viewers leave in the last third: end right after the payoff, no tail.")
    if avg_pct >= 80:
        tips.append("People watch most of each clip: try slightly longer clips.")
    biggest = max(range(1, 20), key=lambda i: curve[i - 1] - curve[i])
    return {"n": n, "avg_view_pct": avg_pct, "curve": curve, "early_hold": early, "end_hold": end, "worst_bucket": biggest, "tips": tips}


def lead_in(summ: dict | None) -> int:
    """Seconds of lead-in before a hype peak: 2 normally, 1 when viewers leave early (needs at least 4 clips of evidence)."""
    return 1 if summ and summ["n"] >= 4 and summ["early_hold"] < 0.6 else 2
