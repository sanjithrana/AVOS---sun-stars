"""Explainer REST API (mounted at /api/explainer; the desktop reaches it through /studio-api).

    GET    /api/explainer                         your projects
    POST   /api/explainer                         {brief, seconds?, aspect?, language?, crew?, auto?, style?, voice?, models?}
    GET    /api/explainer/{id}                    everything the page shows
    PATCH  /api/explainer/{id}                    {title?, auto?, style?, voice?, models?, music?, plan?: edited script/shots}
    POST   /api/explainer/{id}/approve            ✔ the current gate (script, then storyboard)
    POST   /api/explainer/{id}/redo-plan          {note}  write the plan again
    POST   /api/explainer/{id}/continue           carry on after a stop / error
    POST   /api/explainer/{id}/cancel             stop
    POST   /api/explainer/{id}/shots/{sid}        {what: picture|clip, note?, engine?}  one shot again (engine forces ai_video|blender|still)
    GET    /api/explainer/{id}/files/{path}       pictures, clips, the final video
    GET    /api/explainer/capabilities            what can be made right now (AI video, Blender, voice, music)
    DELETE /api/explainer/{id}
"""
from __future__ import annotations

import asyncio
import re
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse, Response

from .. import models
from ..series import languages, media
from . import agents, engines, master, memory, pipeline, prompts, skills, spec, store
from . import styles as style_presets
from . import voices as voice_ids

router = APIRouter(prefix="/api/explainer")


def err(status: int, msg: str) -> JSONResponse:
    return JSONResponse({"error": msg}, status_code=status)


async def _body(req: Request) -> dict:
    try:
        return (await req.json()) or {} if await req.body() else {}
    except ValueError:
        return {}


def _view(p: dict) -> dict:
    src = p.get("source")
    p = {**p, "source": ({"title": src["title"], "url": src["url"], "words": src["words"]} if src else None)}
    if p.get("plan"):
        shots = []
        for s in p["plan"]["shots"]:
            mv = s["camera"]["movement"].replace("_", " ")
            shots.append({**s, "pic_prompt": s.get("prompt_custom") or engines.shot_prompt(p, s),
                          "anim_prompt": s.get("anim_custom") or engines.motion_prompt(engines.animation_prompt(p, s), mv)})
        p = {**p, "plan": {**p["plan"], "shots": shots}}
    pid = p["id"]
    return {**p, "agents": agents.status(p, lambda rel: pipeline._have(pid, rel)), "busy": pipeline.busy(p["id"]), "stages": [{"id": s, "label": pipeline.LABELS[s]} for s in pipeline.STAGES],
            "totalSeconds": spec.total_seconds(p["plan"]) if p.get("plan") else 0}


@router.get("/prompts")
def prompt_library() -> Any:
    return prompts.library()


@router.put("/prompts/{key}")
async def prompt_save(key: str, req: Request) -> Any:
    b = await _body(req)
    try:
        prompts.set_text(key, str(b.get("text") or ""))
    except KeyError:
        return err(404, "no such prompt")
    except ValueError as e:
        return err(400, str(e))
    return prompts.library()


@router.post("/prompts/{key}/restore")
async def prompt_restore(key: str, req: Request) -> Any:
    b = await _body(req)
    try:
        prompts.restore(key, int(b.get("v")))
    except (KeyError, TypeError, ValueError):
        return err(404, "no such prompt version")
    return prompts.library()


@router.post("/prompts/{key}/reset")
def prompt_reset(key: str) -> Any:
    try:
        prompts.reset(key)
    except KeyError:
        return err(404, "no such prompt")
    return prompts.library()


@router.post("/prompts/{key}/improve")
async def prompt_improve(key: str, req: Request) -> Any:
    b = await _body(req)
    pid = str(b.get("project") or "")
    s = pipeline.sdict(store.load(pid)) if pid and store.exists(pid) else None
    try:
        msg = await asyncio.to_thread(prompts.improve_now, key, s)
    except KeyError:
        return err(404, "no such prompt")
    return {**prompts.library(), "message": msg}


@router.post("/prompts/learn")
async def prompt_learn() -> Any:
    msgs = await asyncio.to_thread(pipeline.learn, None)
    return {**prompts.library(), "message": " ".join(msgs) or "Nothing to learn yet: prompts need about six results before they are judged."}


@router.get("/skills")
def skills_list() -> Any:
    s = {"id": "x", "settings": {"models": {}}}
    caps = {**engines.capabilities(s), "voice": media._edge_installed(), "music": media._ready("ace-step")}
    return {"skills": skills.listing(caps)}


@router.put("/skills/{sid}")
async def skills_set(sid: str, req: Request) -> Any:
    b = await _body(req)
    try:
        skills.set_on(sid, bool(b.get("on")))
    except KeyError:
        return err(404, "no such skill")
    except ValueError as e:
        return err(400, str(e))
    return skills_list()


@router.post("/skills/{sid}/improve")
async def skills_improve(sid: str) -> Any:
    try:
        msg = await asyncio.to_thread(skills.improve, sid, None)
    except KeyError:
        return err(404, "no such skill")
    return {**skills_list(), "message": msg}


@router.get("/capabilities")
def capabilities() -> dict:
    s = {"id": "x", "settings": {"models": {}}}
    caps = engines.capabilities(s)
    return {**caps, "voice": media._edge_installed(), "music": media._ready("ace-step"), "languages": languages.public(),
            "aspects": list(spec.ASPECTS), "hint": None if caps["ai_video"] else
            "No AI video model is ready. Add a fal.ai key and credit (Settings), or connect a GPU worker. Shots become pictures with camera moves until then."}


@router.get("/memory")
def memory_list() -> Any:
    """The characters the studio remembers across videos."""
    return {"cast": memory.listing()}


@router.get("/memory/{mid}/{name}")
def memory_file(mid: str, name: str) -> Any:
    f = memory.path(mid, name)
    return FileResponse(f) if f else err(404, "no such file")


@router.delete("/memory/{mid}")
def memory_forget(mid: str) -> Any:
    if not memory.forget(mid):
        return err(404, "no such character")
    return {"cast": memory.listing()}


@router.get("")
def list_projects() -> list[dict]:
    return store.listing()


@router.get("/voices")
async def voice_list(language: str = "", gender: str = "") -> Any:
    from . import voices as vc
    return await asyncio.to_thread(vc.search, language, gender)


@router.get("/voices/preview")
async def voice_preview(voice: str, text: str = "") -> Any:
    from fastapi.responses import Response
    from . import voices as vc
    if not vc.valid_id(voice):
        return err(400, "That voice name isn't valid.")
    try:
        data = await asyncio.to_thread(vc.preview, voice, text or None)
    except Exception as e:  # noqa: BLE001
        return err(502, f"Couldn't make a sample (voices need internet): {str(e)[:120]}")
    return Response(content=data, media_type="audio/wav", headers={"Cache-Control": "max-age=86400"})


@router.get("/styles")
def styles() -> list[dict]:
    return [{"id": x["id"], "name": x["name"]} for x in style_presets.STYLES]


@router.post("/article/preview")
async def article_preview(req: Request) -> Any:
    from . import article
    b = await _body(req)
    try:
        a = await asyncio.to_thread(article.fetch, str(b.get("url") or ""))
    except article.ArticleError as e:
        return err(400, str(e))
    return {"title": a["title"], "words": a["words"], "readMinutes": round(a["words"] / 200, 1), "excerpt": a["text"][:500]}


@router.post("/estimate")
async def estimate(req: Request) -> Any:
    from . import cost
    b = await _body(req)
    s = {"id": "x", "settings": {"models": b.get("models") if isinstance(b.get("models"), dict) else {}, "local_only": bool(b.get("local_only"))}}
    try:
        secs = int(max(10, min(90, float(b.get("seconds") or 30))))
    except (TypeError, ValueError):
        secs = 30
    return cost.estimate(secs, s)


@router.post("")
async def create(req: Request) -> Any:
    b = await _body(req)
    source, mode = None, str(b.get("mode") or "summarize")
    if b.get("url"):
        from . import article
        try:
            source = await asyncio.to_thread(article.fetch, str(b["url"]))
        except article.ArticleError as e:
            return err(400, str(e))
        b["brief"] = f"Video from the article: {source['title']}"
    brief = "\n".join(" ".join(ln.split()) for ln in str(b.get("brief") or "").splitlines()).strip()
    if len(brief) < 3:
        return err(400, "Tell me what the video is about (a sentence is enough).")
    aspect = b.get("aspect") if b.get("aspect") in spec.ASPECTS else "9:16"
    try:
        seconds = int(max(10, min(90, float(b.get("seconds") or 30))))
    except (TypeError, ValueError):
        seconds = 30
    fmt = __import__("re").search(r"format[:\s]+(16:9|9:16|1:1)", brief, __import__("re").I)
    if fmt and len(brief) > 200:
        aspect = fmt.group(1)
    named = __import__("re").search(r"duration[:\s]+(\d{2,3})\s*(?:seconds|secs?|s)\b", brief, __import__("re").I)
    if named and len(brief) > 200:                    # a full brief names its own length
        seconds = int(max(10, min(90, int(named.group(1)))))
    from ..llm import agent_kinds, default_agent
    crew = b.get("crew") if b.get("crew") in agent_kinds() else default_agent()
    pid = store.new_id()
    p = {"id": pid, "brief": brief[:4000], "title": (brief.split(".")[0].split("\n")[0] or brief)[:60], "seconds": seconds, "aspect": aspect, "language": str(b.get("language") or "en"),
         "crew": crew, "auto": bool(b.get("auto")), "style": (style_presets.prompt_for(b.get("style_id")) if b.get("style_id") else str(b.get("style") or ""))[:600], "source": source, "mode": mode if mode in ("summarize", "explain", "story", "highlights") else "summarize", "voice": "female" if b.get("voice") == "female" else "male",
         "voice_id": (b.get("voice_id") if voice_ids.valid_id(b.get("voice_id")) else None),
         "models": b.get("models") if isinstance(b.get("models"), dict) else {}, "local_only": bool(b.get("local_only")), "research_on": bool(b.get("research", True)) and not source and len(brief) <= 300, "status": "working", "stage": "plan", "plan": None,
         "assets": {}, "log": [], "createdAt": store.now(), "updatedAt": store.now()}
    store.save(p)
    pipeline.start(pid, "plan")
    return _view(p)


def _need(pid: str) -> JSONResponse | None:
    return None if store.exists(pid) else err(404, "no such project")


@router.get("/{pid}")
def get(pid: str) -> Any:
    return _need(pid) or _view(store.load(pid))


@router.patch("/{pid}")
async def patch(pid: str, req: Request) -> Any:
    if (e := _need(pid)):
        return e
    b = await _body(req)
    def f(p: dict) -> None:
        for k in ("title", "style"):
            if isinstance(b.get(k), str):
                p[k] = b[k][:300]
        if "auto" in b:
            p["auto"] = bool(b["auto"])
        if b.get("voice") in ("male", "female"):
            p["voice"] = b["voice"]
        if isinstance(b.get("models"), dict):
            p["models"] = b["models"]
        if "local_only" in b:
            p["local_only"] = bool(b["local_only"])
        if isinstance(b.get("plan"), dict) and p.get("plan") and not pipeline.busy(pid):
            ids = {"characters": {c["id"] for c in p["plan"]["characters"]}, "props": {x["id"] for x in p["plan"]["props"]}}
            old = {s["id"]: s for s in p["plan"]["shots"]}
            shots = []
            for i, raw in enumerate((b["plan"].get("shots") or [])[:16]):
                n = spec.norm_shot(raw, i, ids)
                prev = old.get(raw.get("id") if isinstance(raw, dict) else None) or {}
                n.update({k: prev[k] for k in ("frame", "clip", "prompt") if prev.get(k) and prev.get("action") == n["action"]})
                if isinstance(raw, dict) and raw.get("force") in ("ai_video", "blender", "still"):
                    n["force"] = raw["force"]
                shots.append(n)
            if len(shots) >= 2:
                p["plan"]["shots"] = shots
    store.update(pid, f)
    return _view(store.load(pid))


@router.post("/{pid}/approve")
def approve(pid: str) -> Any:
    if (e := _need(pid)):
        return e
    p = store.load(pid)
    if p.get("status") != "waiting":
        return err(409, "Nothing is waiting for approval.")
    pipeline.on_approve(pid)
    pipeline.start(pid, pipeline.next_stage(p))
    return _view(store.load(pid))


@router.get("/{pid}/master-prompt")
def master_prompt(pid: str, scene: int | None = None) -> Any:
    if (e := _need(pid)):
        return e
    p = store.load(pid)
    if not p.get("plan"):
        return err(409, "There is no script yet.")
    return {"text": master.build(p, scene), "parts": master.parts(p, scene), "scenes": sorted({int(x.get("scene") or 1) for x in p["plan"]["shots"]})}


@router.get("/{pid}/picture-prompts.txt")
def picture_prompts(pid: str) -> Any:
    """Every shot's picture prompt as one plain-text file, each prompt self-contained and separated by a blank line, so the
    prompts can be taken to any picture model by hand (the paper-cut workflow's prompt file)."""
    if (e := _need(pid)):
        return e
    p = store.load(pid)
    if not p.get("plan"):
        return err(409, "There is no script yet.")
    text = "\n\n".join(engines.shot_prompt(p, sh) for sh in p["plan"]["shots"])
    name = re.sub(r"[^a-z0-9]+", "-", (p.get("title") or "prompts").lower()).strip("-")[:48] or "prompts"
    return Response(text, media_type="text/plain; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{name}-picture-prompts.txt"'})


@router.post("/{pid}/assets/redo")
async def asset_redo(pid: str, req: Request) -> Any:
    if (e := _need(pid)):
        return e
    b = await _body(req)
    if not pipeline.redo_asset(pid, str(b.get("key") or ""), str(b.get("note") or "")[:300]):
        return err(409, "Busy, or there is no such picture.")
    return _view(store.load(pid))



@router.post("/{pid}/redo-plan")
async def redo_plan(pid: str, req: Request) -> Any:
    if (e := _need(pid)):
        return e
    if pipeline.busy(pid):
        return err(409, "Busy; stop it first.")
    b = await _body(req)
    pipeline.start(pid, "plan", str(b.get("note") or "")[:400])
    return _view(store.load(pid))


@router.post("/{pid}/direct")
async def direct(pid: str, req: Request) -> Any:
    """Direct this: change the story (script written again with your note) or the look (everything redrawn, voice and music kept)."""
    if (e := _need(pid)):
        return e
    if pipeline.busy(pid):
        return err(409, "Busy; stop it first.")
    b = await _body(req)
    note = " ".join(str(b.get("note") or "").split())[:400]
    if len(note) < 3:
        return err(400, "Say what should change.")
    if b.get("scope") == "look":
        if not (store.load(pid).get("plan")):
            return err(409, "There is no script yet.")
        pipeline.restyle(pid, note)
    else:
        pipeline.start(pid, "plan", note)
    return _view(store.load(pid))


@router.post("/{pid}/storyboard-sheet")
def storyboard_sheet(pid: str):
    """Rebuild the numbered overview and the production storyboard sheet from the pictures already made."""
    if not store.exists(pid):
        return err(404, "No such video")
    pipeline.rebuild_sheet(pid)
    return store.load(pid)


@router.post("/{pid}/continue")
def cont(pid: str) -> Any:
    if (e := _need(pid)):
        return e
    p = store.load(pid)
    if not pipeline.start(pid, p.get("stage") or "plan"):
        return err(409, "Already running.")
    return _view(store.load(pid))


@router.post("/{pid}/cancel")
def cancel(pid: str) -> Any:
    if (e := _need(pid)):
        return e
    pipeline.cancel(pid)
    return {"ok": True}


@router.post("/{pid}/shots/{sid}")
async def shot_again(pid: str, sid: str, req: Request) -> Any:
    if (e := _need(pid)):
        return e
    b = await _body(req)
    what = "picture" if b.get("what") == "picture" else "clip"
    if b.get("engine") in ("ai_video", "blender", "still"):
        def f(p: dict) -> None:
            for s in p["plan"]["shots"]:
                if s["id"] == sid:
                    s["force"] = b["engine"]
        store.update(pid, f)
    prompt = str(b["prompt"]) if isinstance(b.get("prompt"), str) else None
    anim = str(b["anim"]) if isinstance(b.get("anim"), str) else None
    if prompt is not None and prompt.strip():
        what = "picture"                              # a new picture prompt means a new picture
    if not pipeline.redo_shot(pid, sid, what, str(b.get("note") or "")[:300], prompt, anim):
        return err(409, "Busy; stop it first.")
    return _view(store.load(pid))


@router.post("/{pid}/shots/{sid}/rate")
async def shot_rate(pid: str, sid: str, req: Request) -> Any:
    if (e := _need(pid)):
        return e
    b = await _body(req)
    if not await asyncio.to_thread(pipeline.rate_shot, pid, sid, bool(b.get("up")), str(b.get("note") or "")[:200]):
        return err(409, "That shot has no new picture to rate (or it is already rated).")
    return _view(store.load(pid))


@router.get("/{pid}/shot-pack")
def shot_pack(pid: str) -> Any:
    """Every shot's first and last frame, motion prompt, timing and voice line, for Kling, Runway, OpenArt and other video sites."""
    if (e := _need(pid)):
        return e
    try:
        data = pipeline.shot_pack(pid)
    except ValueError as ex:
        return err(409, str(ex))
    name = spec.slug(store.load(pid).get("title") or pid, "video")
    return Response(content=data, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{name}-shot-pack.zip"'})


@router.post("/{pid}/shots/{sid}/clip")
async def shot_clip(pid: str, sid: str, req: Request) -> Any:
    """Your own clip for a shot: the request body is the video file itself."""
    if (e := _need(pid)):
        return e
    data = await req.body()
    if len(data) > 400 * 1024 * 1024:
        return err(413, "That file is larger than 400 MB.")
    try:
        await asyncio.to_thread(pipeline.use_clip, pid, sid, data)
    except KeyError:
        return err(404, "no such shot")
    except (ValueError, RuntimeError) as ex:
        return err(409, str(ex)[:300])
    return _view(store.load(pid))


@router.post("/{pid}/finish")
def finish_again(pid: str) -> Any:
    if (e := _need(pid)):
        return e
    if not pipeline.refinish(pid):
        return err(409, "Busy; stop it first.")
    return _view(store.load(pid))


@router.get("/{pid}/files/{path:path}")
def files(pid: str, path: str) -> Any:
    f = store.file_path(pid, path)
    return FileResponse(f) if f else err(404, "no such file")


@router.delete("/{pid}")
def delete(pid: str) -> Any:
    if (e := _need(pid)):
        return e
    pipeline.cancel(pid)
    store.delete(pid)
    return {"ok": True}
