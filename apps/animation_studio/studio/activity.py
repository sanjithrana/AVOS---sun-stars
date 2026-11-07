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
          error: str | None = None) -> dict:
    return {"studio": studio, "kind": kind, "id": rid, "title": (title or rid)[:90], "state": state, "stage": stage, "updatedAt": updated or "",
            "href": href, "thumb": thumb, "needs": needs, "error": (error or "")[:200]}


def _explainer() -> list[dict]:
    from .explainer import pipeline, store
    out = []
    for r in store.listing():
        st = STATES.get(r.get("status") or "", "done")
        label = pipeline.LABELS.get(r.get("stage") or "", r.get("stage") or "")
        out.append(_item("Explainer", "video", r["id"], r.get("title") or r.get("brief"), st, label, r.get("updatedAt"), f"/explainer/{r['id']}",
                         f"/studio-api/explainer/{r['id']}/files/{r['thumb']}" if r.get("thumb") else None, 1 if st == "waiting" else 0, r.get("error")))
    return out


def _stickman() -> list[dict]:
    from .stickman import pipeline, store
    out = []
    labels = getattr(pipeline, "LABELS", {})
    for r in store.listing():
        st = STATES.get(r.get("status") or "", "done")
        out.append(_item("Stickman", "video", r["id"], r.get("title") or r.get("event"), st, labels.get(r.get("stage") or "", r.get("stage") or ""), r.get("updatedAt"),
                         f"/stickman/{r['id']}", f"/studio-api/stickman/{r['id']}/files/{r['thumb']}" if r.get("thumb") else None, 1 if st == "waiting" else 0, r.get("error")))
    return out


def _skills() -> list[dict]:
    from .skilllab import pipeline, store
    out = []
    for r in store.listing():
        st = STATES.get(r.get("status") or "", "done")
        sp = pipeline.SPEC.get(r.get("skill") or "", {})
        out.append(_item("Skills", r.get("skill") or "skill", r["id"], r.get("title") or r.get("subject"), st, (sp.get("labels") or {}).get(r.get("stage") or "", r.get("stage") or ""),
                         r.get("updatedAt"), f"/skills/{r['id']}", f"/studio-api/skills/{r['id']}/files/{r['thumb']}" if r.get("thumb") else None,
                         1 if st == "waiting" else 0, r.get("error")))
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


SOURCES: list[Callable[[], list[dict]]] = [_explainer, _stickman, _skills, _series, _films]


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


@router.get("")
def activity() -> Any:
    return collect()
