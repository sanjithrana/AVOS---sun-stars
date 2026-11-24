"""One feed for the top bar: what is running, what waits for you, and what finished lately, across every studio.

    GET /api/activity   {"jobs": [...running or waiting for you], "recent": [...the last finished or failed], "counts": {"running", "waiting", "error"}}

Each studio keeps its own runs in its own store; this module only READS their listings (it never writes), so a studio that is missing or
broken is skipped and never takes the bar down. Each item: studio, kind, id, title, state (running|waiting|error|done|stopped), stage label,
updatedAt, href (the desktop page), thumb (a same-origin URL or null) and needs (how many things wait for the person)."""
from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter

router = APIRouter(prefix="/api/activity")

STATES = {"working": "running", "waiting": "waiting", "error": "error", "done": "done", "stopped": "stopped"}


def _item(studio: str, kind: str, rid: str, title: str, state: str, stage: str, updated: str | None, href: str, thumb: str | None = None, needs: int = 0,
          error: str | None = None, style: str = "", video: str | None = None) -> dict:
    return {"style": style, "studio": studio, "kind": kind, "id": rid, "title": (title or rid)[:90], "state": state, "stage": stage, "updatedAt": updated or "",
            "href": href, "thumb": thumb, "needs": needs, "error": (error or "")[:200], "video": video}


def _explainer() -> list[dict]:
    from .explainer import pipeline, store
    out = []
    for r in store.listing():
        st = STATES.get(r.get("status") or "", "done")
        label = pipeline.LABELS.get(r.get("stage") or "", r.get("stage") or "")
        out.append(_item("Explainer", "video", r["id"], r.get("title") or r.get("brief"), st, label, r.get("updatedAt"), f"/explainer/{r['id']}",
                         f"/studio-api/explainer/{r['id']}/files/{r['thumb']}" if r.get("thumb") else None, 1 if st == "waiting" else 0, r.get("error"),
                         video=f"/studio-api/explainer/{r['id']}/files/{r['final']}" if st == "done" and r.get("final") else None))
    return out


def _stickman() -> list[dict]:
    from .stickman import pipeline, store
    out = []
    labels = getattr(pipeline, "LABELS", {})
    for r in store.listing():
        st = STATES.get(r.get("status") or "", "done")
        out.append(_item("Stickman", "video", r["id"], r.get("title") or r.get("event"), st, labels.get(r.get("stage") or "", r.get("stage") or ""), r.get("updatedAt"),
                         f"/stickman/{r['id']}", f"/studio-api/stickman/{r['id']}/files/{r['thumb']}" if r.get("thumb") else None, 1 if st == "waiting" else 0, r.get("error"),
                         video=f"/studio-api/stickman/{r['id']}/files/{r['final']}" if st == "done" and r.get("final") else None))
    return out


def _skills() -> list[dict]:
    from .skilllab import pipeline, store
    out = []
    for r in store.listing():
        st = STATES.get(r.get("status") or "", "done")
        sp = pipeline.SPEC.get(r.get("skill") or "", {})
        info = getattr(pipeline.SKILLS.get(r.get("skill") or ""), "INFO", None) or {}
        label = (sp.get("labels") or {}).get(r.get("stage") or "", r.get("stage") or "")
        style = info.get("name") if str(info.get("group") or "").startswith(("Kits", "Film")) else ""
        if st == "done" and str(r.get("skill") or "").startswith("kit-"):
            label = "Your video is ready"
        out.append(_item("Skills", r.get("skill") or "skill", r["id"], r.get("title") or r.get("subject"), st, label,
                         r.get("updatedAt"), f"/skills/{r['id']}", f"/studio-api/skills/{r['id']}/files/{r['thumb']}" if r.get("thumb") else None,
                         1 if st == "waiting" else 0, r.get("error"), style or "",
                         video=f"/studio-api/skills/{r['id']}/files/{r['video']}" if st == "done" and r.get("video") else None))
    return out


def _series() -> list[dict]:
    from .series import store
    out = []
    for r in store.list_series():
        film = r.get("kind") == "film"
        st = "running" if r.get("working") else "done"
        out.append(_item("Animations", "film" if film else "series", r["id"], r.get("title"), st, "Film" if film else f"Series · {r.get('episodes', 0)} episodes", r.get("updatedAt"),
                         f"/animations/{'films' if film else 'series'}/{r['id']}", None, 0))
    return out


def _films() -> list[dict]:
    from . import jobs
    out = []
    for j in jobs.list_jobs():
        stage = j.get("stage") or ""
        st = "running" if stage in jobs.WORKING else "waiting" if stage in ("plan_review", "needs_user") or j.get("needs") else "done"
        out.append(_item("Animations", "style video", j["id"], j.get("title"), st, stage.replace("_", " "), j.get("updatedAt"), f"/animations/{j['id']}", None, int(j.get("needs") or 0)))
    return out


def _autoclip() -> list[dict]:
    from .autoclip import pipeline, store
    out = []
    for r in store.listing():
        st = STATES.get(r.get("status") or "", "done")
        n, posted = int(r.get("clips") or 0), int(r.get("posted") or 0)
        if st == "done":
            label = f"Your video is ready · {n} clip{'s' if n != 1 else ''}" + (f" · {posted} posted" if posted else "")
        else:
            label = pipeline.LABELS.get(r.get("stage") or "", r.get("stage") or "")
        thumb = None
        if st == "done":
            try:
                clip = next((c for c in (store.load(r["id"]).get("clips") or []) if c.get("thumb")), None)
                thumb = f"/studio-api/autoclip/jobs/{r['id']}/file/{clip['thumb']}" if clip else None
            except Exception:  # noqa: BLE001 - a missing picture must not hide the video
                thumb = None
        out.append(_item("Auto Clip", "clips", r["id"], r.get("title"), st, label, r.get("updatedAt"), f"/autoclip?open={r['id']}", thumb, 0, r.get("error"),
                         "GTA 6 clips" if r.get("preset") == "gta6" else ""))
    return out


SOURCES: list[Callable[[], list[dict]]] = [_explainer, _stickman, _skills, _series, _films, _autoclip]


def collect() -> dict:
    items: list[dict] = []
    for src in SOURCES:
        try:
            items += src()
        except Exception:  # noqa: BLE001 - one studio's trouble must not hide the others
            continue
    items.sort(key=lambda x: x.get("updatedAt") or "", reverse=True)
    jobs = [x for x in items if x["state"] in ("running", "waiting")]
    jobs.sort(key=lambda x: (x["state"] != "waiting", x.get("updatedAt") or ""))
    recent = [x for x in items if x["state"] not in ("running", "waiting")][:25]
    return {"jobs": jobs[:40], "recent": recent,
            "counts": {"running": sum(1 for x in items if x["state"] == "running"), "waiting": sum(1 for x in items if x["state"] == "waiting"),
                       "error": sum(1 for x in items[:60] if x["state"] == "error")}}


def everything(limit: int = 500) -> dict:
    """Every output from every studio, in one list.

    `collect` is built for the home page, so it keeps the newest 25 finished items and drops the rest. The Library
    needs all of them, grouped, which is a different question and gets its own answer rather than a bigger cap on the
    old one.
    """
    items: list[dict] = []
    for src in SOURCES:
        try:
            items += src()
        except Exception:  # noqa: BLE001 - one studio's trouble must not hide the others
            continue
    items.sort(key=lambda x: x.get("updatedAt") or "", reverse=True)
    items = items[:max(1, min(2000, int(limit or 500)))]

    def tally(key: str) -> list[dict]:
        n: dict[str, int] = {}
        for x in items:
            n[str(x.get(key) or "other")] = n.get(str(x.get(key) or "other"), 0) + 1
        return [{"name": k, "count": v} for k, v in sorted(n.items(), key=lambda kv: -kv[1])]

    return {"items": items, "total": len(items), "by_studio": tally("studio"), "by_state": tally("state"),
            "by_kind": tally("kind"), "by_style": [x for x in tally("style") if x["name"] != "other"]}


@router.get("")
def activity() -> Any:
    return collect()


@router.get("/all")
def activity_all(limit: int = 500) -> Any:
    return everything(limit)
