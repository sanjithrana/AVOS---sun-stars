"""Series REST API (mounted at /api/series by studio/server.py; the Animations tab reaches it through /studio-api).

    GET    /api/series                                   your series
    GET    /api/series/languages                         languages and which voice models speak them
    POST   /api/series                                   create (multipart: title, premise, language, aspect, style,
                                                         cast, crew, minutes plan, style pictures, theme music)
    GET    /api/series/{sid}                             everything the page shows (series, episodes, readiness)
    PATCH  /api/series/{sid}                             edit title / premise / style / settings
    POST   /api/series/{sid}/refs                        add style pictures · POST /music: theme music
    POST   /api/series/{sid}/characters                  add a character (AI drafts sheet + voice)
    PATCH  /api/series/{sid}/characters/{cid}            edit its description
    POST   /api/series/{sid}/characters/{cid}/approve    ✔ approve (look + voice)
    POST   /api/series/{sid}/characters/{cid}/redo       {what: look|voice|both, note}
    POST   /api/series/{sid}/characters/{cid}/upload     your own picture / voice recording for it
    DELETE /api/series/{sid}/characters/{cid}
    POST   /api/series/{sid}/locations/{lid}/redo        {note}
    POST   /api/series/{sid}/episodes                    {brief, minutes, script?, title?}
    POST   /api/series/{sid}/episodes/{eid}/outline/approve | /outline/redo {note}
    PUT    /api/series/{sid}/episodes/{eid}/parts/{n}/script            your edits to a part's script
    POST   /api/series/{sid}/episodes/{eid}/parts/{n}/script/approve    ✔ → renders the part
    POST   /api/series/{sid}/episodes/{eid}/parts/{n}/script/redo       {note}
    POST   /api/series/{sid}/episodes/{eid}/parts/{n}/approve           ✔ → next part
    POST   /api/series/{sid}/episodes/{eid}/parts/{n}/redo              {shots: [...], what: [...], note}
    POST   /api/series/{sid}/episodes/{eid}/resume                      carry on after a stop / restart / error
    POST   /api/series/{sid}/cancel                      stop what's running
    GET    /api/series/{sid}/files/{path}                pictures, voices, clips, parts, the episode

  Storyboard gate (films and series)
    POST   /api/series/{sid}/episodes/{eid}/parts/{n}/board/approve     ✔ the storyboard → animate the part
    POST   /api/series/{sid}/episodes/{eid}/parts/{n}/camera            {shots?, move?, ease?, lens?, angle?} on many shots
    GET    /api/series/{sid}/episodes/{eid}/export                      every stage's files as one zip

  Films (prompt → animation; a series of kind "film" with one episode of one part)
    POST   /api/series/films                             multipart: prompt (text or JSON), title?, language, aspect, crew,
                                                         style?, refs, library (character ids), musicStyle?, theme?
    PUT    /api/series/{sid}/breakdown                   your edits to the breakdown
    POST   /api/series/{sid}/breakdown/redo              {note} · /breakdown/approve → characters + world drawn
    POST   /api/series/{sid}/film/storyboard             (all characters approved) → the storyboard

  Character library
    GET    /api/series/library/characters · DELETE /api/series/library/characters/{lid} · GET /api/series/library/files/{lid}/{name}
    POST   /api/series/{sid}/characters/{cid}/library    save an approved character · POST /{sid}/characters/from-library {id}
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse, Response

from ..creative import dna as DNA, scene as SG, skills as SK
from ..llm import agent_kinds, default_agent
from . import film, languages, library, media, pipeline, store, writers

router = APIRouter(prefix="/api/series")
ASPECTS = {"16:9": (1280, 720), "9:16": (720, 1280), "1:1": (960, 960), "4:3": (1024, 768)}
PIC = {".png", ".jpg", ".jpeg", ".webp"}
AUD = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac", ".opus", ".webm"}


def err(status: int, msg: str) -> JSONResponse:
    return JSONResponse({"error": msg}, status_code=status)


def _need(sid: str) -> JSONResponse | None:
    return None if store.exists(sid) else err(404, "no such series")


async def _body(req: Request) -> dict:
    try:
        return (await req.json()) or {} if await req.body() else {}
    except ValueError:
        return {}


async def _save(f: Any, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "wb") as out:
        while chunk := await f.read(1 << 20):
            out.write(chunk)


def _ext(f: Any, allowed: set[str]) -> str | None:
    ext = Path(getattr(f, "filename", "") or "").suffix.lower()
    return ext if ext in allowed else None


# ---------- the character library (registered before /{sid}/… so "library" isn't read as a series id) ----------
@router.get("/library/characters")
async def library_list() -> list:
    return [library.public(c) for c in library.list_all()]


@router.delete("/library/characters/{lid}")
async def library_delete(lid: str) -> Any:
    if not library.exists(lid):
        return err(404, "no such library character")
    library.delete(lid)
    return [library.public(c) for c in library.list_all()]


@router.get("/library/files/{lid}/{name}")
async def library_file(lid: str, name: str) -> Any:
    p = library.file_path(lid, name)
    return FileResponse(p, headers={"Cache-Control": "no-cache"}) if p else Response(status_code=404)


@router.get("")
async def list_series() -> list:
    return store.list_series()


@router.get("/languages")
async def langs() -> list:
    return languages.public()


@router.get("/skills")
async def skills_list() -> dict:
    """The SKILL.md files the agents read (apps/skills): edit them to change how AVOS writes, directs and checks."""
    d = SK.skills_dir()
    return {"dir": str(d) if d else None, "skills": SK.catalog()}


@router.post("")
async def create(req: Request) -> Any:
    form = await req.form()
    title = str(form.get("title") or "").strip()
    if not title:
        return err(400, "Give the series a title.")
    lang = str(form.get("language") or "en").strip() or "en"
    aspect = str(form.get("aspect") or "16:9")
    if aspect not in ASPECTS:
        return err(400, f"aspect must be one of {', '.join(ASPECTS)}")
    crew = str(form.get("crew") or "") or default_agent()
    if crew not in agent_kinds():
        return err(400, f"crew must be one of {', '.join(agent_kinds())}")
    try:
        plan = [float(x) for x in str(form.get("partPlan") or "1,3").replace(" ", "").split(",") if x]
        assert plan and all(0.25 <= x <= 10 for x in plan)
    except (ValueError, AssertionError):
        return err(400, "Part plan: minutes per part, e.g. 1,3 (each between 0.25 and 10).")
    sid = store.new_id()
    W, H = ASPECTS[aspect]
    lg = languages.get(lang)
    s = {"id": sid, "title": title[:80], "premise": str(form.get("premise") or "")[:3000], "language": lg.code if lg.code in languages.LANGS else lang,
         "languageName": lg.name, "tone": str(form.get("tone") or "comedy")[:80], "audience": str(form.get("audience") or "family")[:80],
         "castText": str(form.get("cast") or "")[:3000], "suggestCast": str(form.get("suggestCast") or "1") not in ("0", "false"),
         "crew": crew, "partPlan": plan, "format": {"aspect": aspect, "width": W, "height": H, "fps": 24},
         "style": {"description": str(form.get("style") or "")[:1000], "refs": []}, "music": {"style": str(form.get("musicStyle") or "")[:200]},
         "characters": [], "locations": [], "episodes": [], "story": {"episodes": [], "facts": []},
         "settings": {"autoApproveScripts": str(form.get("autoApproveScripts") or "") in ("1", "true")},
         "work": {"state": "idle"}, "createdAt": store.now()}
    d = store.sdir(sid)
    d.mkdir(parents=True, exist_ok=True)
    store.save(s)
    for i, f in enumerate(form.getlist("refs")):
        ext = _ext(f, PIC)
        if ext:
            await _save(f, d / "refs" / f"ref{i + 1}{ext}")
            s["style"]["refs"].append(f"refs/ref{i + 1}{ext}")
    theme = form.get("theme")
    if theme is not None and _ext(theme, AUD):
        await _save(theme, d / "music" / f"theme{_ext(theme, AUD)}")
        s["music"]["theme"] = f"music/theme{_ext(theme, AUD)}"
    store.save(s)
    pipeline.enqueue(sid, "Series bible: characters and places", pipeline.op_bible)
    return {"id": sid}


# ---------- films ----------
@router.post("/films")
async def create_film(req: Request) -> Any:
    form = await req.form()
    prompt = str(form.get("prompt") or "").strip()
    if len(prompt) < 10:
        return err(400, "Write the animation prompt: what happens, who is in it, where (time codes like '0–3 sec:' are read exactly).")
    lang = str(form.get("language") or "en").strip() or "en"
    aspect = str(form.get("aspect") or "16:9")
    if aspect not in ASPECTS:
        return err(400, f"aspect must be one of {', '.join(ASPECTS)}")
    crew = str(form.get("crew") or "") or default_agent()
    if crew not in agent_kinds():
        return err(400, f"crew must be one of {', '.join(agent_kinds())}")
    picks = [x for x in str(form.get("library") or "").replace(" ", "").split(",") if x and library.exists(x)]
    sid = store.new_id("f")
    W, H = ASPECTS[aspect]
    lg = languages.get(lang)
    title = str(form.get("title") or "").strip()
    style = str(form.get("style") or "").strip()
    s = {"id": sid, "kind": "film", "title": (title or "New film")[:80], "titleGiven": bool(title), "prompt": prompt[:30000],
         "premise": "", "language": lg.code if lg.code in languages.LANGS else lang, "languageName": lg.name, "tone": "", "audience": "family",
         "castText": "", "suggestCast": False, "crew": crew, "partPlan": [3], "format": {"aspect": aspect, "width": W, "height": H, "fps": 24},
         "style": {"description": style[:1000], "given": bool(style), "refs": []}, "music": {"style": str(form.get("musicStyle") or "")[:200]},
         "characters": [], "locations": [], "episodes": [], "story": {"episodes": [], "facts": []}, "libraryPicks": picks,
         "breakdown": {"status": "analyzing"}, "settings": {"storyboardGate": True, "shotQA": True}, "work": {"state": "idle"}, "createdAt": store.now()}
    d = store.sdir(sid)
    d.mkdir(parents=True, exist_ok=True)
    store.save(s)
    for i, f in enumerate(form.getlist("refs")):
        ext = _ext(f, PIC)
        if ext:
            await _save(f, d / "refs" / f"ref{i + 1}{ext}")
            s["style"]["refs"].append(f"refs/ref{i + 1}{ext}")
    theme = form.get("theme")
    if theme is not None and _ext(theme, AUD):
        await _save(theme, d / "music" / f"theme{_ext(theme, AUD)}")
        s["music"]["theme"] = f"music/theme{_ext(theme, AUD)}"
    store.save(s)
    pipeline.enqueue(sid, "Breakdown: reading your prompt", pipeline.op_analyze, "")
    return {"id": sid}


def _film(sid: str) -> JSONResponse | None:
    if not store.exists(sid):
        return err(404, "no such film")
    return None if store.load(sid).get("kind") == "film" else err(409, "This is a series, not a film.")


@router.put("/{sid}/breakdown")
async def edit_breakdown(sid: str, req: Request) -> Any:
    if (bad := _film(sid)):
        return bad
    b = await _body(req)
    if not isinstance(b.get("breakdown"), dict):
        return err(400, "Send {breakdown: {...}}.")
    bd = film.normalize(b["breakdown"], store.load(sid))
    if not bd["shots"]:
        return err(400, "The breakdown needs at least one shot.")
    if pipeline.busy(sid) and (store.load(sid).get("breakdown") or {}).get("status") == "analyzing":
        return err(409, "It's still reading the prompt.")

    def put(s: dict) -> None:
        old = s.get("breakdown") or {}
        s["breakdown"] = {**bd, "status": "approved" if old.get("status") == "approved" else "review", "edited": store.now(),
                          **{k: old[k] for k in ("approvedAt", "storyboardFor", "notes") if k in old}}
    store.update(sid, put)
    return pipeline.snapshot(sid)


@router.post("/{sid}/breakdown/redo")
async def redo_breakdown(sid: str, req: Request) -> Any:
    if (bad := _film(sid)):
        return bad
    b = await _body(req)
    if isinstance(b.get("prompt"), str) and len(b["prompt"].strip()) >= 10:
        store.update(sid, lambda s: s.update(prompt=b["prompt"].strip()[:30000]))
    pipeline.enqueue(sid, "Breakdown: reading your prompt again", pipeline.op_analyze, str(b.get("note") or "")[:800])
    return pipeline.snapshot(sid)


@router.post("/{sid}/breakdown/approve")
async def approve_breakdown(sid: str) -> Any:
    if (bad := _film(sid)):
        return bad
    bd = store.load(sid).get("breakdown") or {}
    if bd.get("status") not in ("review", "approved") or not bd.get("shots"):
        return err(409, "The breakdown isn't ready yet.")
    pipeline.enqueue(sid, "Characters and world", pipeline.op_film_cast)
    return pipeline.snapshot(sid)


@router.post("/{sid}/film/storyboard")
async def film_storyboard(sid: str) -> Any:
    if (bad := _film(sid)):
        return bad
    s = store.load(sid)
    if (s.get("breakdown") or {}).get("status") != "approved":
        return err(409, "Approve the breakdown first.")
    cast = s.get("characters") or []
    waiting = [c["name"] for c in cast if c.get("status") != "approved"]
    if waiting:
        return err(409, "Approve every character first: " + ", ".join(waiting))
    if pipeline.busy(sid):
        return err(409, "It's busy; try again when it's done.")
    if s.get("episodes"):
        p = store.load_ep(sid, "ep1")["parts"][0]
        if p.get("status") in ("rendering", "queued"):
            return err(409, "It's already drawing.")
    pipeline.start_storyboard(sid)
    return pipeline.snapshot(sid)


@router.get("/{sid}")
async def get(sid: str) -> Any:
    return _need(sid) or pipeline.snapshot(sid)


@router.patch("/{sid}")
async def edit(sid: str, req: Request) -> Any:
    if (bad := _need(sid)):
        return bad
    b = await _body(req)

    def put(s: dict) -> None:
        for k in ("title", "premise", "tone", "audience"):
            if isinstance(b.get(k), str):
                s[k] = b[k][:3000]
        if isinstance(b.get("style"), str):
            s.setdefault("style", {})["description"] = b["style"][:1000]
        if isinstance(b.get("stylePrompt"), str):
            s.setdefault("style", {})["prompt"] = b["stylePrompt"][:400]
        if isinstance(b.get("settings"), dict):
            s.setdefault("settings", {}).update({k: bool(v) for k, v in b["settings"].items() if k in ("autoApproveScripts", "shotQA", "storyboardGate")})
        if isinstance(b.get("models"), dict):           # your model choices per step: {step: {model, backend}}
            cur = s.setdefault("settings", {}).setdefault("models", {})
            for step, c in b["models"].items():
                if step in media.STEP_LABELS and isinstance(c, dict):
                    cur[step] = {"model": str(c.get("model") or "auto")[:40], "backend": str(c.get("backend") or "auto")[:20]}
        if isinstance(b.get("dna"), dict):
            s["dna"] = DNA.normalize(b["dna"])
            s["dnaAt"] = store.now()
        if isinstance(b.get("subtitleNames"), bool):
            s["subtitleNames"] = b["subtitleNames"]
        if isinstance(b.get("music"), dict):
            s.setdefault("music", {}).update({k: v for k, v in b["music"].items() if k in ("off", "style")})
        if b.get("crew") in agent_kinds():
            s["crew"] = b["crew"]
    store.update(sid, put)
    return pipeline.snapshot(sid)


@router.post("/{sid}/refs")
async def add_refs(sid: str, req: Request) -> Any:
    if (bad := _need(sid)):
        return bad
    form = await req.form()
    s = store.load(sid)
    refs = s["style"].setdefault("refs", [])
    for f in form.getlist("refs"):
        ext = _ext(f, PIC)
        if ext:
            name = f"refs/ref{len(refs) + 1}{ext}"
            await _save(f, store.sdir(sid) / name)
            refs.append(name)
    store.update(sid, lambda x: x["style"].update(refs=refs[-6:]))
    return pipeline.snapshot(sid)


@router.post("/{sid}/music")
async def theme(sid: str, req: Request) -> Any:
    if (bad := _need(sid)):
        return bad
    form = await req.form()
    f = form.get("theme")
    if f is None or not _ext(f, AUD):
        return err(400, "Upload an audio file (wav, mp3, m4a, flac, ogg).")
    name = f"music/theme{_ext(f, AUD)}"
    await _save(f, store.sdir(sid) / name)
    store.update(sid, lambda s: s.setdefault("music", {}).update(theme=name, off=False))
    return pipeline.snapshot(sid)


# ---------- characters ----------
def _find(s: dict, cid: str) -> dict | None:
    return next((c for c in s.get("characters") or [] if c["id"] == cid), None)


@router.post("/{sid}/characters")
async def add_character(sid: str, req: Request) -> Any:
    if (bad := _need(sid)):
        return bad
    b = await _body(req)
    name = str(b.get("name") or "").strip()
    if not name:
        return err(400, "Name the character.")
    s = store.load(sid)
    cid = store.slug(name, {c["id"] for c in s.get("characters") or []})
    g = str(b.get("gender") or "other").lower()
    c = {"id": cid, "name": name[:40], "role": str(b.get("role") or "supporting")[:20], "age": str(b.get("age") or "")[:20],
         "gender": g if g in ("male", "female") else "other", "personality": str(b.get("personality") or "")[:400],
         "look": str(b.get("look") or "")[:600], "outfit": str(b.get("outfit") or "")[:300], "catchphrase": str(b.get("catchphrase") or "")[:120],
         "voice": {"description": str(b.get("voice") or "")[:300]}, "status": "drafting", "version": 0, "history": [], "notes": []}
    store.update(sid, lambda s: s.setdefault("characters", []).append(c))
    pipeline.enqueue(sid, f"Character: {name}", pipeline.op_character, cid, "both", "")
    return pipeline.snapshot(sid)


@router.post("/{sid}/characters/from-library")
async def character_from_library(sid: str, req: Request) -> Any:
    if (bad := _need(sid)):
        return bad
    b = await _body(req)
    lid = str(b.get("id") or "")
    if not library.exists(lid):
        return err(404, "no such library character")
    library.add_to(sid, lid)
    return pipeline.snapshot(sid)


@router.post("/{sid}/characters/{cid}/library")
async def character_to_library(sid: str, cid: str) -> Any:
    if (bad := _need(sid)):
        return bad
    try:
        library.save_from(sid, cid)
    except KeyError:
        return err(404, "no such character")
    except ValueError as e:
        return err(409, str(e))
    return pipeline.snapshot(sid)


@router.patch("/{sid}/characters/{cid}")
async def edit_character(sid: str, cid: str, req: Request) -> Any:
    if (bad := _need(sid)):
        return bad
    b = await _body(req)
    if not _find(store.load(sid), cid):
        return err(404, "no such character")

    def put(s: dict) -> None:
        c = _find(s, cid)
        for k in ("name", "role", "age", "gender", "personality", "look", "outfit", "catchphrase"):
            if isinstance(b.get(k), str):
                c[k] = b[k][:600]
        if isinstance(b.get("voice"), str):
            c.setdefault("voice", {})["description"] = b["voice"][:300]
        if isinstance(b.get("sampleText"), str) and b["sampleText"].strip():
            c.setdefault("voice", {})["sampleText"] = b["sampleText"][:300]
    store.update(sid, put)
    return pipeline.snapshot(sid)


@router.post("/{sid}/characters/{cid}/approve")
async def approve_character(sid: str, cid: str) -> Any:
    if (bad := _need(sid)):
        return bad
    c = _find(store.load(sid), cid)
    if not c:
        return err(404, "no such character")
    if c.get("status") != "review" or not c.get("sheet") or not (c.get("voice") or {}).get("sample"):
        return err(409, f"{c['name']} isn't ready for approval yet (needs a sheet and a voice sample).")
    store.update(sid, lambda s: _find(s, cid).update(status="approved", approvedAt=store.now(), approvedVersion=c.get("version")))
    return pipeline.snapshot(sid)


@router.post("/{sid}/characters/{cid}/redo")
async def redo_character(sid: str, cid: str, req: Request) -> Any:
    if (bad := _need(sid)):
        return bad
    b = await _body(req)
    c = _find(store.load(sid), cid)
    if not c:
        return err(404, "no such character")
    what = b.get("what") if b.get("what") in ("look", "voice", "both") else "both"
    if c.get("status") in ("drafting", "redo"):
        return err(409, f"{c['name']} is being made right now.")
    store.update(sid, lambda s: _find(s, cid).update(status="redo"))
    pipeline.enqueue(sid, f"Redo {c['name']} ({what})", pipeline.op_character, cid, what, str(b.get("note") or "")[:500])
    return pipeline.snapshot(sid)


@router.post("/{sid}/characters/{cid}/upload")
async def upload_character(sid: str, cid: str, req: Request) -> Any:
    """Your own drawing (it becomes the reference the sheet is drawn from) or voice recording (it becomes the sample)."""
    if (bad := _need(sid)):
        return bad
    form = await req.form()
    c = _find(store.load(sid), cid)
    if not c:
        return err(404, "no such character")
    pic, voice = form.get("picture"), form.get("voice")
    what = None
    if pic is not None and _ext(pic, PIC):
        name = f"characters/{cid}/upload{_ext(pic, PIC)}"
        await _save(pic, store.sdir(sid) / name)
        store.update(sid, lambda s: _find(s, cid).update(upload=name))
        what = "look"
    if voice is not None and _ext(voice, AUD):
        name = f"characters/{cid}/voice_upload{_ext(voice, AUD)}"
        await _save(voice, store.sdir(sid) / name)
        text = str(form.get("sampleText") or "").strip()
        store.update(sid, lambda s: _find(s, cid).setdefault("voice", {}).update(upload=name, **({"sampleText": text} if text else {})))
        what = "both" if what else "voice"
    if not what:
        return err(400, "Upload a picture (png, jpg, webp) or a voice recording (wav, mp3, m4a).")
    pipeline.enqueue(sid, f"{c['name']}: from your upload", pipeline.op_character, cid, what, "")
    return pipeline.snapshot(sid)


@router.delete("/{sid}/characters/{cid}")
async def delete_character(sid: str, cid: str) -> Any:
    if (bad := _need(sid)):
        return bad
    store.update(sid, lambda s: s.__setitem__("characters", [c for c in s.get("characters") or [] if c["id"] != cid]))
    return pipeline.snapshot(sid)


@router.post("/{sid}/locations/{lid}/redo")
async def redo_location(sid: str, lid: str, req: Request) -> Any:
    if (bad := _need(sid)):
        return bad
    b = await _body(req)
    if not any(x["id"] == lid for x in store.load(sid).get("locations") or []):
        return err(404, "no such location")
    pipeline.enqueue(sid, f"Location: {lid}", pipeline.op_location, lid, str(b.get("note") or "")[:400])
    return pipeline.snapshot(sid)


# ---------- episodes ----------
@router.post("/{sid}/episodes")
async def new_episode(sid: str, req: Request) -> Any:
    if (bad := _need(sid)):
        return bad
    b = await _body(req)
    s = store.load(sid)
    if not any(c.get("status") == "approved" for c in s.get("characters") or []):
        return err(409, "Approve at least one character first.")
    open_ = [e for e in s.get("episodes") or [] if e.get("status") not in ("done",)]
    if open_:
        return err(409, f"Finish {open_[-1].get('title') or open_[-1]['id']} first (one episode at a time keeps the story straight).")
    script = str(b.get("script") or "").strip() or None
    try:
        minutes = float(b.get("minutes") or 10)
    except (TypeError, ValueError):
        return err(400, "minutes must be a number")
    if not 0.25 <= minutes <= 60:
        return err(400, "An episode is between 0.25 and 60 minutes.")
    ep = pipeline.new_episode(sid, str(b.get("brief") or "")[:3000], minutes, script, (str(b.get("title") or "").strip() or None))
    return {**pipeline.snapshot(sid), "episode": ep["id"]}


def _ep(sid: str, eid: str) -> dict | None:
    try:
        return store.load_ep(sid, eid)
    except (FileNotFoundError, KeyError):
        return None


@router.post("/{sid}/episodes/{eid}/outline/approve")
async def approve_outline(sid: str, eid: str) -> Any:
    ep = _ep(sid, eid) if store.exists(sid) else None
    if not ep:
        return err(404, "no such episode")
    if ep.get("status") != "outline_review":
        return err(409, "The outline isn't waiting for approval.")
    pipeline.approve_outline(sid, eid)
    return pipeline.snapshot(sid)


@router.post("/{sid}/episodes/{eid}/outline/redo")
async def redo_outline(sid: str, eid: str, req: Request) -> Any:
    ep = _ep(sid, eid) if store.exists(sid) else None
    if not ep:
        return err(404, "no such episode")
    b = await _body(req)
    pipeline.enqueue(sid, f"{eid}: outline again", pipeline.op_outline, eid, str(b.get("note") or "")[:800])
    return pipeline.snapshot(sid)


def _part(ep: dict, n: int) -> dict | None:
    return ep["parts"][n - 1] if 1 <= n <= len(ep.get("parts") or []) else None


@router.put("/{sid}/episodes/{eid}/parts/{n}/script")
async def edit_script(sid: str, eid: str, n: int, req: Request) -> Any:
    ep = _ep(sid, eid) if store.exists(sid) else None
    if not ep or not _part(ep, n):
        return err(404, "no such part")
    if _part(ep, n).get("status") not in ("script_review", "board_review", "review", "error", "stopped"):
        return err(409, "This part's script can't be edited right now.")
    b = await _body(req)
    script = writers.norm_script(store.load(sid), b.get("script") if isinstance(b.get("script"), dict) else {})
    if not script["scenes"]:
        return err(400, "The script has no usable lines or actions (speakers must be approved characters).")
    store.update_ep(sid, eid, lambda e: e["parts"][n - 1].update(script=script, status="script_review",
                                                                 scriptSeconds=writers.script_seconds(script), edited=True))
    return pipeline.snapshot(sid)


@router.post("/{sid}/episodes/{eid}/parts/{n}/script/approve")
async def approve_script(sid: str, eid: str, n: int) -> Any:
    ep = _ep(sid, eid) if store.exists(sid) else None
    if not ep or not _part(ep, n):
        return err(404, "no such part")
    if _part(ep, n).get("status") != "script_review":
        return err(409, "This part's script isn't waiting for approval.")
    if n > 1 and _part(ep, n - 1).get("status") != "approved":
        return err(409, f"Approve part {n - 1} first.")
    pipeline.approve_script(sid, eid, n)
    return pipeline.snapshot(sid)


@router.post("/{sid}/episodes/{eid}/parts/{n}/script/redo")
async def redo_script(sid: str, eid: str, n: int, req: Request) -> Any:
    ep = _ep(sid, eid) if store.exists(sid) else None
    if not ep or not _part(ep, n):
        return err(404, "no such part")
    b = await _body(req)
    pipeline.enqueue(sid, f"{eid}: rewrite part {n}", pipeline.op_write_part, eid, n, str(b.get("note") or "")[:800])
    return pipeline.snapshot(sid)


@router.post("/{sid}/episodes/{eid}/parts/{n}/approve")
async def approve_part(sid: str, eid: str, n: int) -> Any:
    ep = _ep(sid, eid) if store.exists(sid) else None
    if not ep or not _part(ep, n):
        return err(404, "no such part")
    if _part(ep, n).get("status") != "review":
        return err(409, "This part isn't waiting for your review.")
    pipeline.approve_part(sid, eid, n)
    return pipeline.snapshot(sid)


@router.post("/{sid}/episodes/{eid}/parts/{n}/redo")
async def redo_part(sid: str, eid: str, n: int, req: Request) -> Any:
    ep = _ep(sid, eid) if store.exists(sid) else None
    if not ep or not _part(ep, n):
        return err(404, "no such part")
    p = _part(ep, n)
    if p.get("status") not in ("review", "board_review", "error", "stopped"):
        return err(409, "This part can be redone after it has rendered.")
    b = await _body(req)
    ids = {x["id"] for x in p.get("shots") or []}
    shots = [x for x in (b.get("shots") or []) if x in ids] or sorted(ids)
    what = [w for w in (b.get("what") or ["picture", "motion"]) if w in ("voice", "picture", "motion")] or ["picture", "motion"]
    store.update_ep(sid, eid, lambda e: e["parts"][n - 1].update(status="queued"))
    pipeline.enqueue(sid, f"{eid}: redo part {n}", pipeline.op_render_part, eid, n, shots, str(b.get("note") or "")[:500], what)
    return pipeline.snapshot(sid)


@router.post("/{sid}/episodes/{eid}/parts/{n}/board/approve")
async def approve_board(sid: str, eid: str, n: int) -> Any:
    ep = _ep(sid, eid) if store.exists(sid) else None
    if not ep or not _part(ep, n):
        return err(404, "no such part")
    if _part(ep, n).get("status") != "board_review":
        return err(409, "The storyboard isn't waiting for approval.")
    pipeline.approve_board(sid, eid, n)
    return pipeline.snapshot(sid)


@router.post("/{sid}/episodes/{eid}/parts/{n}/camera")
async def batch_camera(sid: str, eid: str, n: int, req: Request) -> Any:
    """One camera change on many shots (Global camera panel): move, ease, lens (mm), angle."""
    ep = _ep(sid, eid) if store.exists(sid) else None
    p = _part(ep, n) if ep else None
    if not p:
        return err(404, "no such part")
    if p.get("status") not in ("board_review", "review", "error", "stopped"):
        return err(409, "Change the camera once the storyboard is drawn.")
    b = await _body(req)
    move = b.get("move") if b.get("move") in SG.MOVES else None
    ease = b.get("ease") if b.get("ease") in SG.EASES else None
    try:
        lens = int(b["lens"]) if b.get("lens") else None
    except (TypeError, ValueError):
        return err(400, "lens is a number of millimetres")
    angle = SG.angle_of(b["angle"]) if b.get("angle") else None
    if not (move or ease or lens or angle):
        return err(400, "Say what to change: move, ease, lens or angle.")
    ids = [x for x in (b.get("shots") or []) if isinstance(x, str)]
    changed = pipeline.batch_camera(sid, eid, n, ids, move, ease, lens and max(12, min(200, lens)), angle)
    if changed:
        store.update_ep(sid, eid, lambda e: e["parts"][n - 1].update(status="queued"))
        pipeline.enqueue(sid, f"{eid}: part {n} · camera on {len(changed)} shot(s)", pipeline.op_render_part, eid, n, changed, "", ["none"])
    return {**pipeline.snapshot(sid), "changed": changed}


@router.get("/{sid}/episodes/{eid}/export")
async def export(sid: str, eid: str) -> Any:
    ep = _ep(sid, eid) if store.exists(sid) else None
    if not ep:
        return err(404, "no such episode")
    import asyncio
    path = await asyncio.to_thread(film.export, sid, eid)
    name = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in (store.load(sid).get("title") or sid))[:40].strip("-") or sid
    return FileResponse(path, media_type="application/zip", filename=f"{name}-{eid}-project.zip")


@router.post("/{sid}/episodes/{eid}/resume")
async def resume(sid: str, eid: str) -> Any:
    ep = _ep(sid, eid) if store.exists(sid) else None
    if not ep:
        return err(404, "no such episode")
    if pipeline.busy(sid):
        return err(409, "It's already working.")
    parts = ep.get("parts") or []
    if not ep.get("outline"):
        pipeline.enqueue(sid, f"{eid}: outline", pipeline.op_outline, eid, "")
    elif parts and all(p.get("status") == "approved" for p in parts):
        pipeline.enqueue(sid, f"{eid}: join", pipeline.op_join, eid)
    else:
        p = next((p for p in parts if p.get("status") in ("rendering", "writing", "queued", "stopped", "error")), None)
        if p is None:
            return err(409, "Nothing to resume: it's waiting for your review.")
        if p.get("script") and p.get("status") != "writing":
            pipeline.enqueue(sid, f"{eid}: render part {p['index']}", pipeline.op_render_part, eid, p["index"])
        else:
            pipeline.enqueue(sid, f"{eid}: write part {p['index']}", pipeline.op_write_part, eid, p["index"], "")
    if ep.get("status") in ("stopped", "error"):
        store.update_ep(sid, eid, lambda e: e.update(status="in_production" if e.get("outline") else "outlining", error=None))
    return pipeline.snapshot(sid)


@router.get("/{sid}/models")
async def model_options(sid: str) -> Any:
    """Per step: your choice, every model that can do it, where each can run (your GPU, ComfyUI, fal.ai, Cloudflare)
    and why not; change it with PATCH /{sid} {"models": {step: {"model", "backend"}}}."""
    if (bad := _need(sid)):
        return bad
    import asyncio
    from .. import provider_health
    steps = await asyncio.to_thread(media.model_options, store.load(sid))
    return {"steps": steps, "providers": provider_health.snapshot()}


@router.post("/{sid}/dna/rebuild")
async def rebuild_dna(sid: str) -> Any:
    if (bad := _need(sid)):
        return bad
    pipeline.enqueue(sid, "Design DNA", pipeline.op_dna)
    return pipeline.snapshot(sid)


# ---------- shot tools (Director mode, Modify shot, Animate image, Motion transfer) ----------
def _shot_ctx(sid: str, eid: str, n: int, shot_id: str) -> tuple[dict | None, dict | None, JSONResponse | None]:
    ep = _ep(sid, eid) if store.exists(sid) else None
    p = _part(ep, n) if ep else None
    if not p:
        return None, None, err(404, "no such part")
    sh = next((x for x in p.get("shots") or [] if x["id"] == shot_id), None)
    if sh is None:
        return None, None, err(404, "no such shot")
    if p.get("status") not in ("review", "board_review", "error", "stopped"):
        return None, None, err(409, "Shots can be changed once the storyboard is drawn (and while nothing else runs on it).")
    return p, sh, None


def _rerender(sid: str, eid: str, n: int, shot_id: str, label: str) -> Any:
    store.update_ep(sid, eid, lambda e: e["parts"][n - 1].update(status="queued"))
    pipeline.enqueue(sid, f"{eid}: part {n} · {label} {shot_id}", pipeline.op_render_part, eid, n, [shot_id], "", ["none"])
    return pipeline.snapshot(sid)


def _put(sid: str, eid: str, n: int, shot_id: str, fn: Any) -> None:
    def upd(e: dict) -> None:
        for sh in e["parts"][n - 1].get("shots") or []:
            if sh["id"] == shot_id:
                fn(sh)
    store.update_ep(sid, eid, upd)


@router.put("/{sid}/episodes/{eid}/parts/{n}/shots/{shot_id}/stage")
async def save_stage(sid: str, eid: str, n: int, shot_id: str, req: Request) -> Any:
    """Director mode: the edited scene graph (positions, camera, light) and motion blueprint (timeline) of one shot."""
    p, sh, bad = _shot_ctx(sid, eid, n, shot_id)
    if bad:
        return bad
    b = await _body(req)
    s = store.load(sid)
    cast = {c["id"] for c in s.get("characters") or []}
    st_in = b.get("stage") if isinstance(b.get("stage"), dict) else sh.get("stage") or {}
    subjects = [a.get("id") for a in st_in.get("actors") or [] if isinstance(a, dict) and a.get("id") in cast] or sh.get("subjects") or []
    stage = SG.normalize_scene(st_in, subjects=subjects, framing=st_in.get("framing") or sh.get("framing"),
                               location=sh.get("location", ""), time=st_in.get("time") or sh.get("time", "day"))
    bp = SG.normalize_motion(b.get("blueprint") if isinstance(b.get("blueprint"), dict) else sh.get("blueprint") or {}, stage,
                             duration=float(sh.get("seconds") or 3), speaker=sh.get("speaker"))
    bp = SG.retime(bp, float(sh.get("seconds") or bp["duration"]))
    changed = SG.changed_parts(sh.get("stage"), stage, sh.get("blueprint"), bp)
    if not changed:
        return pipeline.snapshot(sid)
    names = {c["id"]: c["name"] for c in s.get("characters") or []}

    def fn(x: dict) -> None:
        x.update(stage=stage, blueprint=bp, framing=stage["framing"], subjects=[a["id"] for a in stage["actors"]],
                 camera=bp["camera"]["move"], directed=store.now(),
                 motion="; ".join(f"{names.get(t['target'], t['target'])} {k['action']}" for t in bp["tracks"] for k in t["keys"]) or x.get("motion"))
        if "picture" in changed:
            x.pop("keyOverride", None)          # a new layout means a new first frame
    _put(sid, eid, n, shot_id, fn)
    return _rerender(sid, eid, n, shot_id, "director")


@router.post("/{sid}/episodes/{eid}/parts/{n}/shots/{shot_id}/modify")
async def modify_shot(sid: str, eid: str, n: int, shot_id: str, req: Request) -> Any:
    """Change one thing in the shot (an object, an outfit, the light) and keep everything else; optionally keep the
    exact motion of the current take (Wan VACE)."""
    p, sh, bad = _shot_ctx(sid, eid, n, shot_id)
    if bad:
        return bad
    b = await _body(req)
    ins = str(b.get("instruction") or "").strip()
    if not ins:
        return err(400, "Say what to change, e.g. 'make the TV remote red' or 'turn the lights off'.")
    if not (store.part_dir(sid, eid, n) / "shots" / shot_id / "key.png").is_file():
        return err(409, "This shot has no picture yet.")
    count = int((sh.get("keyOverride") or {}).get("n") or 0) + 1
    _put(sid, eid, n, shot_id, lambda x: x.update(keyOverride={"pending": "modify", "instruction": ins[:300], "n": count,
                                                              "keepMotion": bool(b.get("keepMotion", True)),
                                                              "history": ((x.get("keyOverride") or {}).get("history") or []) + [ins[:300]]}))
    return _rerender(sid, eid, n, shot_id, "modify")


@router.post("/{sid}/episodes/{eid}/parts/{n}/shots/{shot_id}/image")
async def animate_image(sid: str, eid: str, n: int, shot_id: str, req: Request) -> Any:
    """Animate image: your own picture becomes the shot's first frame, animated with the shot's motion (+ your note)."""
    p, sh, bad = _shot_ctx(sid, eid, n, shot_id)
    if bad:
        return bad
    form = await req.form()
    f = form.get("picture")
    if f is None or not _ext(f, PIC):
        return err(400, "Upload a picture (png, jpg, webp).")
    d = store.part_dir(sid, eid, n) / "shots" / shot_id
    await _save(f, d / "key.png")
    data = (d / "key.png").read_bytes()
    import hashlib
    motion_note = str(form.get("motion") or "").strip()[:300]
    _put(sid, eid, n, shot_id, lambda x: x.update(keyOverride={"source": "upload", "fp": hashlib.sha1(data).hexdigest()[:16]},
                                                **({"note": motion_note} if motion_note else {})))
    return _rerender(sid, eid, n, shot_id, "animate image")


@router.post("/{sid}/episodes/{eid}/parts/{n}/shots/{shot_id}/driver")
async def motion_driver(sid: str, eid: str, n: int, shot_id: str, req: Request) -> Any:
    """Motion transfer: a reference video (you acting it out, any clip) drives the character in this shot."""
    p, sh, bad = _shot_ctx(sid, eid, n, shot_id)
    if bad:
        return bad
    form = await req.form()
    f = form.get("video")
    if f is None or Path(getattr(f, "filename", "") or "").suffix.lower() not in (".mp4", ".mov", ".webm", ".mkv"):
        return err(400, "Upload a video (mp4, mov, webm).")
    await _save(f, store.part_dir(sid, eid, n) / "shots" / shot_id / "driver.mp4")
    _put(sid, eid, n, shot_id, lambda x: x.update(driver=True))
    return _rerender(sid, eid, n, shot_id, "motion transfer")


@router.delete("/{sid}/episodes/{eid}/parts/{n}/shots/{shot_id}/override")
async def reset_shot(sid: str, eid: str, n: int, shot_id: str) -> Any:
    """Back to the generated shot: drop your picture, the edits and the driving video."""
    p, sh, bad = _shot_ctx(sid, eid, n, shot_id)
    if bad:
        return bad
    d = store.part_dir(sid, eid, n) / "shots" / shot_id
    (d / "driver.mp4").unlink(missing_ok=True)

    def fn(x: dict) -> None:
        x.pop("keyOverride", None)
        x.pop("driver", None)
        x.pop("note", None)
        x["takes"]["picture"] = int(x["takes"].get("picture") or 1) + 1
    _put(sid, eid, n, shot_id, fn)
    return _rerender(sid, eid, n, shot_id, "reset")


@router.post("/{sid}/cancel")
async def cancel(sid: str) -> Any:
    if (bad := _need(sid)):
        return bad
    pipeline.cancel(sid)
    return {"ok": True}


@router.get("/{sid}/files/{path:path}")
async def files(sid: str, path: str) -> Any:
    if not store.exists(sid):
        return Response(status_code=404)
    p = store.file_path(sid, path)
    if p is None:
        return Response(status_code=404)
    return FileResponse(p, headers={"Cache-Control": "no-cache"})
