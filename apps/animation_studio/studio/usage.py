"""What each run actually spent: which model, how much of it, and roughly what that cost.

Nothing in AVOS recorded this before, so "is this run about to cost me nine dollars?" had no answer anywhere. This is
an append-only ledger -- one JSON line per model call -- plus a price table and the rollups the Analytics tab reads.

Two honesty rules, because a wrong number here is worse than no number:
  * Every cost is an ESTIMATE from a published list price, and every row says which price it used. Prices change,
    and a provider's actual bill is the only truth.
  * A call whose price is unknown is recorded with `priced: false` and a cost of zero, never guessed. The rollup
    reports how many of those there were, so a small total that is missing half its calls cannot look like a small bill.

Writing never raises. A ledger that breaks a render is worse than no ledger.
"""
from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_lock = threading.Lock()
MAX_LINES = 40000                 # about a year of heavy use; older lines are dropped from the front


def _path() -> Path | None:
    try:
        from .config import PROJECTS
        for cand in (Path(PROJECTS).parent / "usage.jsonl", Path(PROJECTS) / "_usage.jsonl"):
            try:
                cand.parent.mkdir(parents=True, exist_ok=True)
                return cand
            except OSError:
                continue
    except Exception:  # noqa: BLE001 - metering must never take the server down
        pass
    return None


# ---------------------------------------------------------------- prices
# Published list prices, checked 7 November 2026. Per image, or per second of finished video.
# "free" means a free tier covers ordinary use (Cloudflare Workers AI gives 10,000 neurons a day, about 150 images),
# not that the call is unlimited.
PRICES: tuple[tuple[str, str, str, float], ...] = (
    # pattern (lower-cased, searched)        kind       unit      price
    (r"drawn in code|macro move|camera move|paper (set|scene|puppet)|still|synth", "free", "call", 0.0),
    (r"pollinations",                         "image",  "image",  0.0),
    (r"cloudflare|workers ai|flux\.?2 klein|flux\.1 schnell.*cloudflare", "image", "image", 0.0),
    (r"seedance.*(mini|lite)",                "video",  "second", 0.155),
    (r"seedance",                             "video",  "second", 0.303),
    (r"wan.*2\.6",                            "video",  "second", 0.10),
    (r"wan",                                  "video",  "second", 0.08),
    (r"kling.*pro",                           "video",  "second", 0.070),
    (r"ltx",                                  "video",  "second", 0.12),
    (r"qwen-image-edit",                      "image",  "image",  0.0),
    (r"flux.*(schnell|dev)",                  "image",  "image",  0.003),
    (r"nano.?banana|gemini.*image",           "image",  "image",  0.034),
    (r"\bsdxl\b|stable.?diffusion",           "image",  "image",  0.003),
    (r"edge|kokoro|piper",                    "voice",  "call",   0.0),
    (r"elevenlabs",                           "voice",  "call",   0.0),
)
FREE_WORDS = re.compile(r"drawn in code|macro move|camera move|paper (set|scene|puppet)|synth|your recording")


def price_of(model: str, kind: str) -> tuple[float, str, bool]:
    """(price per unit, unit, priced?) for one model name. Unknown models are not guessed at."""
    m = (model or "").lower()
    for pattern, _k, unit, price in PRICES:
        if re.search(pattern, m):
            return price, unit, True
    return 0.0, {"video": "second", "writer": "ktoken"}.get(kind, "call"), False


def record(kind: str, model: str, units: float = 1.0, *, run: str = "", skill: str = "",
           ok: bool = True, note: str = "") -> dict:
    """One model call. `units` is images, seconds of video, or thousands of tokens, by kind.

    Returns the row it wrote so a caller can show it; never raises.
    """
    per, unit, priced = price_of(model, kind)
    row = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "kind": kind,
           "model": (model or "unknown")[:80], "units": round(float(units or 0), 3), "unit": unit,
           "cost": round(per * float(units or 0), 6), "priced": priced, "ok": bool(ok),
           "run": run[:40], "skill": skill[:60], "note": note[:160]}
    p = _path()
    if not p:
        return row
    try:
        with _lock, p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    except Exception:  # noqa: BLE001 - never break a render over metering
        pass
    return row


def rows(limit: int = MAX_LINES) -> list[dict]:
    p = _path()
    if not p or not p.is_file():
        return []
    try:
        with p.open(encoding="utf-8") as f:
            lines = f.readlines()[-limit:]
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def trim() -> None:
    """Keeps the ledger from growing without bound. Called after a run finishes."""
    p = _path()
    if not p or not p.is_file():
        return
    try:
        with _lock:
            lines = p.read_text("utf-8").splitlines()
            if len(lines) > MAX_LINES:
                p.write_text("\n".join(lines[-MAX_LINES:]) + "\n", "utf-8")
    except OSError:
        pass


def _bucket(items: list[dict], key: str) -> list[dict]:
    agg: dict[str, dict] = {}
    for r in items:
        k = str(r.get(key) or "unknown")
        a = agg.setdefault(k, {"name": k, "calls": 0, "units": 0.0, "cost": 0.0, "unpriced": 0, "failed": 0})
        a["calls"] += 1
        a["units"] += float(r.get("units") or 0)
        a["cost"] += float(r.get("cost") or 0)
        a["unpriced"] += not r.get("priced")
        a["failed"] += not r.get("ok", True)
    for a in agg.values():
        a["units"], a["cost"] = round(a["units"], 2), round(a["cost"], 4)
    return sorted(agg.values(), key=lambda a: (-a["cost"], -a["calls"]))


def summary(days: int = 30) -> dict:
    """Everything the Analytics tab shows, worked out in one pass."""
    items = rows()
    cutoff = ""
    if days:
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
    items = [r for r in items if not cutoff or str(r.get("at", "")) >= cutoff]
    by_day: dict[str, dict] = {}
    for r in items:
        d = str(r.get("at", ""))[:10]
        a = by_day.setdefault(d, {"day": d, "cost": 0.0, "calls": 0})
        a["cost"] += float(r.get("cost") or 0)
        a["calls"] += 1
    for a in by_day.values():
        a["cost"] = round(a["cost"], 4)
    unpriced = sum(1 for r in items if not r.get("priced"))
    free = sum(1 for r in items if r.get("priced") and not float(r.get("cost") or 0))
    return {
        "days": days,
        "total": {"cost": round(sum(float(r.get("cost") or 0) for r in items), 4), "calls": len(items),
                  "unpriced": unpriced, "free": free,
                  "failed": sum(1 for r in items if not r.get("ok", True))},
        "by_kind": _bucket(items, "kind"),
        "by_model": _bucket(items, "model")[:24],
        "by_skill": _bucket(items, "skill")[:24],
        "by_day": sorted(by_day.values(), key=lambda a: a["day"]),
        "recent": list(reversed(items[-40:])),
        "note": "Estimates from published list prices, checked 7 November 2026. Your provider's bill is the only "
                "truth. Calls from a model with no price in the table are counted but cost nothing here.",
    }


def for_run(run: str) -> dict:
    items = [r for r in rows() if r.get("run") == run]
    return {"run": run, "calls": len(items),
            "cost": round(sum(float(r.get("cost") or 0) for r in items), 4),
            "unpriced": sum(1 for r in items if not r.get("priced")),
            "by_kind": _bucket(items, "kind"), "rows": items}


# ---------------------------------------------------------------- route
try:
    from fastapi import APIRouter

    router = APIRouter(prefix="/api/usage", tags=["usage"])

    @router.get("")
    def usage(days: int = 30) -> Any:
        return summary(max(0, min(365, int(days or 30))))

    @router.get("/run/{run}")
    def usage_run(run: str) -> Any:
        return for_run(run)
except Exception:  # noqa: BLE001 - importable without FastAPI, for tests
    router = None  # type: ignore[assignment]
