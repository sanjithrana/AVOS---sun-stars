"""Skill Lab REST API (/api/skills; the desktop reaches it through /studio-api/skills).

    GET    /api/skills                  the skills you can run, and your runs
    POST   /api/skills                  {skill, subject, media: "media"|"prompts", aspect?, seconds?}  → a run (starts at once)
    GET    /api/skills/{id}             the run: design lock, three prompts, pictures, clip, steps, log
    PATCH  /api/skills/{id}             {prompts: {compact|transformed|video: "..."}} · {narration: {"1": "..."}}
    POST   /api/skills/{id}/redo        {step, n?}  that step (only scene n) and everything after it
    GET    /api/skills/{id}/takes/{n}               every take of shot n, newest first
    POST   /api/skills/{id}/takes/{n}   {kind, take} use that take instead of the current one
    GET    /api/skills/{id}/plan        Company Story: the plan to review (characters, storyboard, motion, audio)
    POST   /api/skills/{id}/continue | /cancel ;  GET /files/{name} ;  DELETE
    GET    /api/skills/characters/{file}  the ready-made characters a skill offers (Company Story: sheets and thumbnails)
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse

import threading

from . import pipeline, store, takes

router = APIRouter(prefix="/api/skills")


def err(status: int, msg: str) -> JSONResponse:
    return JSONResponse({"error": msg}, status_code=status)


async def _body(req: Request) -> dict:
    try:
        return (await req.json()) or {} if await req.body() else {}
    except ValueError:
        return {}


# Mechanical Toy's three outputs, which the run page used to assume every skill had. Kept as the fallback for any
# skill whose module does not describe its own, which is exactly Mechanical Toy.
TOY_OUTPUTS = (
    {"key": "compact", "step": "compact", "title": "Compact device", "kind": "image", "prompt": "compact"},
    {"key": "transformed", "step": "transformed", "title": "Fully transformed", "kind": "image", "prompt": "transformed"},
    {"key": "video", "step": "video", "title": "Transformation video", "kind": "video", "prompt": "video"},
)


def outputs_of(p: dict) -> list[dict]:
    """What this run has to show, named by the skill rather than guessed at by the page.

    The run page used to hold one hard-coded list -- compact / transformed / video -- so a Film Style or ASMR Cooking
    run was asked for files it has never had. The cards said "Waiting" forever and the prompt boxes were empty, while
    the run itself was fine: only the labels were wrong. A skill now describes its own outputs, and each entry
    carries the file, so the page has nothing left to work out.
    """
    mod = pipeline.SKILLS.get(p.get("skill") or "")
    fn = getattr(mod, "outputs_of", None)
    if callable(fn):
        try:
            return list(fn(p))
        except Exception:  # noqa: BLE001 - a broken describer must not take the page down
            pass
    return [{**o, "file": p.get(o["key"] if o["key"] != "video" else "video")} for o in TOY_OUTPUTS]


def _view(p: dict) -> dict:
    sp = pipeline.spec_of(p)
    mod = pipeline.SKILLS.get(p.get("skill") or "")
    return {**{k: v for k, v in p.items() if k != "research" or not isinstance(v, dict)},
            **({"research": {k: v for k, v in p["research"].items() if k != "allowed"}} if isinstance(p.get("research"), dict) else {}),
            "busy": pipeline.busy(p["id"]), "stages": [{"id": s, "label": sp["labels"][s]} for s in sp["stages"]],
            "skillName": (getattr(mod, "INFO", {}) or {}).get("name") or "Skill",
            "outputs": outputs_of(p)}


@router.get("/kits/engine")
def kits_engine() -> Any:
    """Is the kit render engine (Playwright + Chromium + edge-tts) installed? The 29 kit skills need it."""
    from ..kits import engine
    return {**engine.status(), "installing": _installing.is_set()}


_installing = threading.Event()


@router.post("/kits/engine/install")
def kits_engine_install() -> Any:
    """Install what is missing, in the background (the first kit run does the same by itself)."""
    from ..kits import engine
    if _installing.is_set():
        return {"started": False, "installing": True}

    def work() -> None:
        _installing.set()
        try:
            engine.ensure()
        except Exception:  # noqa: BLE001 - status() shows what is still missing
            pass
        finally:
            _installing.clear()
    threading.Thread(target=work, daemon=True).start()
    return {"started": True, "installing": True}


@router.get("")
def listing() -> dict:
    return {"skills": [m.INFO for m in pipeline.SKILLS.values()], "runs": store.listing()}


@router.post("")
async def create(req: Request) -> Any:
    from ..llm import agent_kinds, default_agent
    b = await _body(req)
    sk = pipeline.SKILLS.get(str(b.get("skill") or ""))
    if not sk:
        return err(400, "no such skill")
    subject = sk.subject_of(b.get("subject") or "") if hasattr(sk, "subject_of") else " ".join(str(b.get("subject") or "").split())[:120]
    if len(subject) < 2:
        return err(400, "Name a subject first.")
    shapes = sk.INFO.get("aspects") or list(pipeline.SIZES)
    aspect = b.get("aspect") if b.get("aspect") in pipeline.SIZES and b.get("aspect") in shapes else sk.INFO["aspect"]
    secs = int(b.get("seconds") or sk.INFO["default_seconds"])
    secs = secs if secs in sk.INFO["seconds"] else sk.INFO["default_seconds"]
    crew = b.get("crew") if b.get("crew") in agent_kinds() else default_agent()
    pid = store.new_id()
    p = {"id": pid, "skill": sk.ID, "subject": subject, "request": str(b.get("subject") or "")[:2000], "title": subject, "aspect": aspect, "seconds": secs,
         "media": "prompts" if b.get("media") == "prompts" else "media", "crew": crew, "models": b.get("models") or {}, "local_only": bool(b.get("local_only")),
         "voice": "female" if b.get("voice") == "female" else "male", "review": bool(b.get("review", True)) and bool(sk.INFO.get("styles")), **_story_options(sk, b), "status": "working", "stage": pipeline.spec_of({"skill": sk.ID})["stages"][0], "steps": {}, "log": [], "createdAt": store.now(), "updatedAt": store.now()}
    store.save(p)
    pipeline.start(pid)
    return _view(store.load(pid))


def _story_options(sk: Any, b: dict) -> dict:
    """The choices a skill offers on the create page. Company Story: always 2D, AI video or drawn poses, and ONE ready-made character.
    A skill with motions but no styles (ASMR Cooking) only picks its motion."""
    info = sk.INFO
    if not info.get("styles"):
        out = {}
        if info.get("hands"):                                  # ASMR Cooking: gloved or bare
            out["hands"] = b.get("hands") if b.get("hands") in {x[0] for x in info["hands"]} else info["hands"][0][0]
        if not info.get("motions"):
            return out
        out["motion"] = b.get("motion") if b.get("motion") in {x[0] for x in info["motions"]} else info["motions"][0][0]
        return out
    chars = {c["id"] for c in info.get("characters") or []}
    dflt = (info.get("default_cast") or {}).get("founder")
    want = (b.get("characters") or {}).get("founder") if isinstance(b.get("characters"), dict) else None
    return {"style": "2d", "motion": b.get("motion") if b.get("motion") in {x[0] for x in info.get("motions") or []} else "video",
            "characters": {"founder": want if want in chars else dflt}}


@router.get("/characters/{name}")
def character(name: str) -> Any:
    from .company_story import CHAR_DIR
    f = CHAR_DIR / name
    ok = f.suffix == ".jpg" and f.parent == CHAR_DIR and f.is_file()
    return FileResponse(f, headers={"Cache-Control": "public, max-age=86400"}) if ok else err(404, "no such character")


@router.get("/{pid}/plan")
def plan(pid: str) -> Any:
    """The plan the person reviews after the script: characters, storyboard, motion and audio (Company Story)."""
    if not store.exists(pid):
        return err(404, "no such run")
    p = store.load(pid)
    if p.get("skill") != "company-story" or not (p.get("script") or {}).get("scenes"):
        return err(409, "There is no script yet.")
    from .company_story import plan_of
    return plan_of(p)


@router.get("/{pid}")
def get(pid: str) -> Any:
    return _view(store.load(pid)) if store.exists(pid) else err(404, "no such run")


def pid_skill(pid: str) -> str:
    try:
        return store.load(pid).get("skill") or ""
    except Exception:  # noqa: BLE001
        return ""


@router.patch("/{pid}")
async def patch(pid: str, req: Request) -> Any:
    if not store.exists(pid):
        return err(404, "no such run")
    b = await _body(req)
    edits = {k: " ".join(str(v).split())[:6000] for k, v in (b.get("prompts") or {}).items() if (k in ("compact", "transformed", "video") or (k == "script" and str(pid_skill(pid)).startswith("kit-"))) and str(v).strip()}
    narr = {int(k): " ".join(str(v).split())[:400] for k, v in (b.get("narration") or {}).items() if str(k).isdigit() and str(v).strip()}
    motion = b.get("motion") if b.get("motion") in ("video", "poses") else None
    def f(p: dict) -> None:
        if p.get("skill") == "company-story" and (b.get("character") or b.get("voice")):
            from .company_story import change_plan
            change_plan(p, b)
        if motion and p.get("skill") == "company-story" and motion != p.get("motion"):
            p["motion"] = motion
            for sc in (p.get("script") or {}).get("scenes") or []:
                sc["video"] = None
            for st in ("scenes", "animate", "voice", "finish"):    # poses are drawn by the scenes step; Continue picks it up from there
                p.get("steps", {}).pop(st, None)
            p.pop("video", None)
        if edits:
            p.setdefault("prompts", {}).update(edits)
            if "script" in edits and isinstance(p.get("kitScript"), dict):
                p["kitScript"]["script"] = str(b["prompts"]["script"]).strip()[:6000]     # the kit skills keep line breaks: one sentence a line
        for sc in (p.get("script") or {}).get("scenes") or []:
            if sc["n"] in narr and narr[sc["n"]] != sc["narration"]:
                sc["narration"], sc["voice"] = narr[sc["n"]], None
    store.update(pid, f)
    return _view(store.load(pid))


@router.post("/{pid}/redo")
async def redo(pid: str, req: Request) -> Any:
    if not store.exists(pid):
        return err(404, "no such run")
    b = await _body(req)
    stages = pipeline.spec_of(store.load(pid))["stages"]
    step = b.get("step") if b.get("step") in stages else stages[1]
    n = int(b["n"]) if str(b.get("n") or "").isdigit() else None
    if not pipeline.redo(pid, step, n):
        return err(409, "This run is still working.")
    return _view(store.load(pid))


def _shot(p: dict, n: int) -> dict | None:
    shots = (p.get("recipe") or p.get("script") or {}).get("shots") or p.get("shots") or []
    return next((sh for sh in shots if int(sh.get("n") or 0) == n), None)


@router.get("/{pid}/takes/{n}")
def take_list(pid: str, n: int) -> Any:
    """Every version of one shot, so a person can compare them instead of trusting the newest."""
    if not store.exists(pid):
        return err(404, "no such run")
    sh = _shot(store.load(pid), n)
    if not sh:
        return err(404, "no such shot")
    return {"n": n, "title": sh.get("title") or "", "picture": sh.get("picture"), "video": sh.get("video"),
            "takes": {k: takes.listing(sh, k) for k in takes.KINDS}}


@router.post("/{pid}/takes/{n}")
async def take_pick(pid: str, n: int, req: Request) -> Any:
    """Use an earlier take of this shot. Nothing is regenerated and nothing is thrown away."""
    if not store.exists(pid):
        return err(404, "no such run")
    if pipeline.busy(pid):
        return err(409, "This run is still working.")
    b = await _body(req)
    kind = b.get("kind") if b.get("kind") in takes.KINDS else "picture"
    tid = str(b.get("take") or "")
    ok = False

    def f(p: dict) -> None:
        nonlocal ok
        sh = _shot(p, n)
        if sh:
            ok = takes.pick(sh, kind, tid)
    store.update(pid, f)
    if not ok:
        return err(404, "no such take")
    return _view(store.load(pid))


@router.post("/{pid}/continue")
def resume(pid: str) -> Any:
    if not store.exists(pid):
        return err(404, "no such run")
    p = store.load(pid)
    if p.get("status") == "waiting" and not p.get("plan_ok"):          # Approve: the person reviewed the plan
        store.update(pid, lambda q: q.update(plan_ok=True))
    if not pipeline.start(pid, pipeline.resume_stage(p)):
        return err(409, "This run is still working.")
    return _view(store.load(pid))


@router.post("/{pid}/cancel")
def cancel(pid: str) -> Any:
    pipeline.cancel(pid)
    return {"ok": True}


@router.get("/{pid}/files/{name}")
def file(pid: str, name: str) -> Any:
    f = store.file_path(pid, name)
    return FileResponse(f) if f else err(404, "no such file")


@router.delete("/{pid}")
def delete(pid: str) -> Any:
    if pipeline.busy(pid):
        return err(409, "Stop it first.")
    store.delete(pid)
    return {"ok": True}
