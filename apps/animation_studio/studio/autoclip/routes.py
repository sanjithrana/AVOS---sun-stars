"""Auto Clip's HTTP API, mounted at /api/autoclip (the Next app reaches it as /studio-api/autoclip)."""
from __future__ import annotations

import shutil
import re
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from starlette.datastructures import UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from . import autopilot, captions, coach, comments, cut, experiments, hype, intake, music, pipeline, polish, postqueue, retention, presets, reframe, rights, smart, social, store, templates, cards, transcript, youtube

router = APIRouter(prefix="/api/autoclip")
MAX_UPLOAD = 6 * 1024 ** 3


def err(status: int, msg: str, **kw: Any) -> JSONResponse:
    return JSONResponse({"error": msg, **kw}, status_code=status)


def capabilities() -> dict:
    import importlib.util as iu
    return {"ffmpeg": bool(shutil.which("ffmpeg")), "yt_dlp": intake.have_ytdlp(), "whisper": iu.find_spec("faster_whisper") is not None,
            "layouts": cut.LAYOUTS, "captions": cut.CAPTIONS, "caption_styles": caption_styles(), "anims": captions.ANIMS, "fonts": captions.font_list(),
            "whisper_models": pipeline.WHISPER_MODELS, "whisper_pick": whisper_pick(), "edit_styles": {k: v["label"] for k, v in polish.STYLES.items()}, "looks": {k: v[0] for k, v in polish.LOOKS.items()}, "moods": music.MOODS, "reframe": reframe.status(),
            "templates": {k: v["label"] for k, v in templates.TEMPLATES.items()},
            "template_info": {k: {"label": v["label"], "cat": v.get("cat", "all"), "desc": v.get("desc", ""), "card": bool(v.get("card"))} for k, v in templates.TEMPLATES.items()},
            "template_cats": templates.CATEGORIES, "card_fonts": list(cards.FONT_FILES), "backgrounds": templates.BACKGROUNDS, "caption_modes": captions.MODES}


def caption_styles() -> dict:
    """What the page needs to draw a small sample of each style (colours as #RRGGBB)."""
    keep = ("label", "font", "upper", "text", "hi", "outline", "anim", "words", "italic", "layout", "kw", "rest", "kw_font", "kw_italic", "kw_upper", "kw_scale",
            "rest_scale", "box", "tiles", "tile_text", "hi_box", "underline", "dim", "blur", "glow", "out", "spacing", "hi_font", "hi_italic", "size")
    return {k: {f: v.get(f) for f in keep if v.get(f) not in (None, False)} for k, v in captions.STYLES.items()}


def ram_gb() -> float:
    try:
        for ln in Path("/proc/meminfo").read_text().splitlines():
            if ln.startswith("MemTotal:"):
                return round(int(ln.split()[1]) / 1024 / 1024, 1)
    except OSError:
        pass
    return 0.0


def whisper_pick() -> str:
    """The best speech model this machine can hold comfortably (leaving room for the video work)."""
    free = ram_gb() or 8
    best = "base"
    for k, v in pipeline.WHISPER_MODELS.items():
        if v["ram_gb"] * 1.6 <= free:
            best = k
    return "medium" if best == "large-v3-turbo" and (os.cpu_count() or 4) < 8 else best


def view(job: dict) -> dict:
    return {**job, "busy": pipeline.busy(job["id"]), "stages": [{"id": s, "label": pipeline.LABELS[s]} for s in pipeline.STAGES]}


def public_settings() -> dict:
    st = store.settings()
    return {k: v for k, v in st.items() if k != "posted_log"}


@router.get("")
def overview() -> dict:
    return {"settings": public_settings(), "autopilot": autopilot.status(), "channels": youtube.channels(), "jobs": store.listing(),
            "google": {"has_client": youtube.has_client()}, "capabilities": capabilities(), "presets": presets.public()}


@router.get("/readiness")
async def readiness_check() -> Any:
    """Is everything ready (ffmpeg filters, disk, AI helper, Ollama, YouTube logins)? A second or two."""
    from starlette.concurrency import run_in_threadpool
    from . import readiness
    return await run_in_threadpool(readiness.run)


@router.post("/check")
async def check_source(req: Request) -> Any:
    """Is this link OK to clip, and is it live? Reads the video's licence, channel and live state: see rights.py. Runs off the event loop (yt-dlp can take several seconds)."""
    from starlette.concurrency import run_in_threadpool
    b = await req.json()
    try:
        return await run_in_threadpool(rights.check, str(b.get("url") or "").strip())
    except RuntimeError as e:
        return err(400, str(e))


# ---------- the YouTube tab: queue, plan, uploads, numbers ----------
@router.get("/youtube/tab")
def yt_tab(refresh: bool = False) -> Any:
    if refresh:
        try:
            postqueue.refresh(force=True)
        except Exception:  # noqa: BLE001
            pass
    return postqueue.overview() | {"library": postqueue.library(), "uploads": postqueue.uploads(), "google": {"has_client": youtube.has_client()},
                                   "rights_ack": store.settings().get("rights_ack"), "tz_offset_minutes": store.settings().get("tz_offset_minutes")}


@router.put("/youtube/plan")
async def yt_plan(req: Request) -> Any:
    try:
        b = await req.json()
        postqueue.set_plan(b, str(b["channel"]) if b.get("channel") else None)
    except ValueError as e:
        return err(400, str(e))
    return yt_tab()


@router.post("/youtube/uploads")
async def yt_upload(req: Request) -> Any:
    form = await req.form()
    up = form.get("file")
    if not isinstance(up, UploadFile) or not up.filename:
        return err(400, "Choose a video file.")
    if Path(up.filename).suffix.lower() not in (".mp4", ".mov", ".mkv", ".webm", ".m4v"):
        return err(400, "Upload a video file (mp4, mov, mkv, webm).")
    ack = str(form.get("ack")).lower() in ("1", "true", "yes")
    tmp = store.ROOT / "uploads" / f"tmp-{store.new_id()}"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    with tmp.open("wb") as out:
        while chunk := await up.read(1 << 20):
            size += len(chunk)
            if size > 2 * 1024 ** 3:
                out.close()
                tmp.unlink(missing_ok=True)
                return err(413, "That file is larger than 2 GB.")
            out.write(chunk)
    return postqueue.add_upload(up.filename, tmp, ack)


@router.get("/youtube/uploads/{uid}/cover")
def yt_cover(uid: str) -> Any:
    p = postqueue.UPLOADS() / f"{Path(uid).name}.jpg"
    return FileResponse(p) if p.is_file() else err(404, "no cover")


@router.delete("/youtube/uploads/{uid}")
def yt_upload_delete(uid: str) -> Any:
    uid = Path(uid).name
    if any(p["src"].get("upload") == uid and p["status"] in ("queued", "posting") for p in postqueue.overview()["posts"]):
        return err(409, "It is still waiting in the queue. Cancel those posts first.")
    for ext in (".mp4", ".jpg", ".json"):
        (postqueue.UPLOADS() / f"{uid}{ext}").unlink(missing_ok=True)
    return {"ok": True}


@router.post("/youtube/posts")
async def yt_add(req: Request) -> Any:
    b = await req.json()
    try:
        made = postqueue.add(b.get("items") or [], [str(c) for c in b.get("channels") or []], str(b.get("mode") or "auto"), b.get("at"), b.get("privacy"), bool(b.get("spread", True)),
                            float(b.get("gap_min") or 3), float(b.get("gap_max") or 5), float(b.get("gap_hours") or 0))
    except ValueError as e:
        return err(400, str(e))
    return {"made": len(made), **yt_tab()}


@router.patch("/youtube/posts/{pid}")
async def yt_edit(pid: str, req: Request) -> Any:
    try:
        postqueue.edit(pid, await req.json())
    except KeyError:
        return err(404, "no such post")
    except ValueError as e:
        return err(409, str(e))
    return yt_tab()


@router.delete("/youtube/posts/{pid}")
def yt_cancel(pid: str) -> Any:
    return yt_tab() if postqueue.cancel(pid) else err(409, "That post can't be cancelled now.")


@router.post("/youtube/posts/{pid}/retry")
def yt_retry(pid: str) -> Any:
    return yt_tab() if postqueue.retry(pid) else err(409, "Nothing to retry.")


@router.post("/youtube/posts/clear")
def yt_clear() -> Any:
    postqueue.clear_done()
    return yt_tab()


@router.post("/youtube/posts/privacy")
async def yt_privacy(req: Request) -> Any:
    b = await req.json()
    try:
        n = postqueue.set_privacy(str(b.get("privacy") or ""), b.get("channel") or None)
    except ValueError as e:
        return err(400, str(e))
    return {"set": n, **yt_tab()}


@router.post("/youtube/posts/drip")
async def yt_drip(req: Request) -> Any:
    """Post everything that is waiting one by one starting now, 3 to 5 minutes apart (the minute loop does the posting)."""
    try:
        b = await req.json()
    except Exception:  # noqa: BLE001
        b = {}
    n = postqueue.drip(b.get("channel") or None, float(b.get("gap_min") or 3), float(b.get("gap_max") or 5))
    if not n:
        return err(409, "Nothing is waiting to post.")
    import threading
    threading.Thread(target=postqueue.tick, daemon=True, name="post-drip").start()
    return {"set": n, **yt_tab()}


@router.post("/youtube/posts/{pid}/now")
def yt_now(pid: str) -> Any:
    """Move a waiting post to 'as soon as possible'."""
    try:
        postqueue.edit(pid, {"at": ""})
    except (KeyError, ValueError) as e:
        return err(409, str(e))
    import threading
    threading.Thread(target=lambda: postqueue.tick(only=pid), daemon=True, name="post-now").start()      # start this one right away; the minute loop would take its turn
    return yt_tab()


# ---------- jobs ----------
@router.get("/live")
def live_state() -> Any:
    from . import live
    return live.state()


@router.put("/live/streamers")
async def live_streamers(req: Request) -> Any:
    from . import live
    b = await req.json()
    live.save_streamers(b.get("streamers") or [])
    return live.state()


@router.post("/live/start")
def live_start() -> Any:
    from . import live
    t = live.tools()
    if not (t["streamlink"] and t["ffmpeg"]):
        return err(400, "streamlink is not installed in the Auto Clip container yet. Run: docker exec avos-animation-studio pip install streamlink")
    if not live.load()["streamers"]:
        return err(400, "Add at least one streamer first.")
    return live.start()


@router.post("/live/stop")
def live_stop() -> Any:
    from . import live
    live.stop()
    return live.state()


@router.post("/jobs")
async def create(req: Request) -> Any:
    ctype = req.headers.get("content-type", "")
    srt_text = None
    if ctype.startswith("multipart/"):
        form = await req.form()
        fields = {k: v for k, v in form.items() if isinstance(v, str)}
        up = form.get("file")
        srt = form.get("srt")
        if isinstance(srt, UploadFile):
            srt_text = (await srt.read(2_000_000)).decode("utf-8", "replace")
    else:
        fields, up = await req.json(), None
    opts = pipeline.build_opts({k: v for k, v in fields.items() if k not in ("url", "verdict", "ack", "live_minutes", "file", "srt")})   # every option the form sends (editing, hype, captions, brand)
    url = str(fields.get("url") or "").strip()
    if isinstance(up, UploadFile) and up.filename:
        suffix = Path(up.filename).suffix.lower()
        if suffix not in (".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi", ".ts", ".flv"):
            return err(400, "Upload a video file (mp4, mov, mkv, webm…).")
        job = pipeline.new_job(opts, {"kind": "upload", "name": Path(up.filename).stem[:100]})
        dst = store.jdir(job["id"]) / f"source{suffix}"
        size = 0
        with dst.open("wb") as out:
            while chunk := await up.read(1 << 20):
                size += len(chunk)
                if size > MAX_UPLOAD:
                    out.close()
                    shutil.rmtree(store.jdir(job["id"]), ignore_errors=True)
                    return err(413, "That file is larger than 6 GB.")
                out.write(chunk)
    elif url:
        try:
            intake.public_url(url)
        except RuntimeError as e:
            return err(400, str(e))
        from starlette.concurrency import run_in_threadpool
        try:
            chk = await run_in_threadpool(rights.check, url)       # the server decides; the form's own answer is not trusted
        except RuntimeError as e:
            return err(400, str(e))
        if chk["verdict"] == "blocked":
            return err(400, chk["tip"])
        if not chk.get("clippable", True):
            return err(400, (chk.get("notes") or ["This video can't be clipped yet."])[0])
        fields["verdict"] = chk["verdict"]
        if (chk.get("live") or {}).get("state") == "live":
            try:
                mins = max(1, min(240, int(float(fields.get("live_minutes") or 20))))
            except (TypeError, ValueError):
                mins = 20
            job = pipeline.new_job(opts, {"kind": "live", "url": url[:500], "name": (chk.get("title") or url)[:100], "minutes": mins, "channel": str(chk.get("channel") or "")[:80], "license": str(chk.get("license") or "")[:60], "channel_url": str((chk.get("links") or {}).get("channel") or "")[:200], "tags": [str(t)[:30] for t in (chk.get("tags") or [])][:40]})
        else:
            job = pipeline.new_job(opts, {"kind": "url", "url": url[:500], "name": (chk.get("title") or url)[:100], "channel": str(chk.get("channel") or "")[:80], "license": str(chk.get("license") or "")[:60], "channel_url": str((chk.get("links") or {}).get("channel") or "")[:200], "tags": [str(t)[:30] for t in (chk.get("tags") or [])][:40]})
    else:
        return err(400, "Paste a link or upload a video.")
    if "verdict" in fields or "ack" in fields:
        ack = str(fields.get("ack")).lower() in ("1", "true", "yes")
        perm = rights.permission_for(str(fields.get("verdict") or ("own" if isinstance(up, UploadFile) and up.filename and ack else "ask")), ack)
        store.update(job["id"], lambda j: j.__setitem__("permission", perm))
        job = store.load(job["id"])
    if srt_text and transcript.parse_srt(srt_text):
        (store.jdir(job["id"]) / "source.srt").write_text(srt_text, "utf-8")
    pipeline.start(job["id"])
    return view(store.load(job["id"]))


@router.get("/jobs/{jid}")
def get_job(jid: str) -> Any:
    return view(store.load(jid)) if store.exists(jid) else err(404, "no such job")


@router.post("/jobs/{jid}/run")
def run_again(jid: str, fresh: bool = False) -> Any:
    """Run (or resume) a job. A stopped or failed job carries on from the last finished step: the download, the transcript, the chosen moments and any clips
    already cut are kept. fresh=true throws those away and starts the choosing again."""
    if not store.exists(jid):
        return err(404, "no such job")
    if fresh:
        d = store.jdir(jid)
        for f in ("cues.json", "hype.json"):
            (d / f).unlink(missing_ok=True)
        store.update(jid, lambda j: j.update(pick_key=None, clips=[]))
    if not pipeline.start(jid):
        return err(409, "This job is still running.")
    store.update(jid, lambda j: j.update(status="working", error=None))
    return view(store.load(jid))


@router.post("/jobs/{jid}/stop")
def stop_job(jid: str) -> Any:
    pipeline.stop(jid)
    return {"ok": True}


@router.delete("/jobs/{jid}")
def delete_job(jid: str) -> Any:
    if not store.exists(jid):
        return err(404, "no such job")
    pipeline.stop(jid)
    shutil.rmtree(store.jdir(jid), ignore_errors=True)
    return {"ok": True}


@router.get("/jobs/{jid}/file/{name:path}")
def file(jid: str, name: str) -> Any:
    try:
        p = (store.jdir(jid) / name).resolve()
        if not p.is_file() or store.jdir(jid).resolve() not in p.parents or p.name.startswith("source") or p.suffix not in (".mp4", ".jpg"):
            return err(404, "no such file")
    except KeyError:
        return err(404, "no such file")
    return FileResponse(p)


@router.patch("/jobs/{jid}/clips/{n}")
async def patch_clip(jid: str, n: int, req: Request) -> Any:
    if not store.exists(jid):
        return err(404, "no such job")
    b = await req.json()

    def f(j: dict) -> None:
        for c in j["clips"]:
            if c["n"] == n and not c.get("youtube_id"):
                if "title" in b:
                    c["title"] = youtube.clean_text(b["title"], 95) or c["title"]
                if "description" in b:
                    c["description"] = youtube.clean_text(b["description"], 4800)
                if "approved" in b:
                    c["approved"] = bool(b["approved"])
                if b.get("privacy") in ("private", "unlisted", "public", ""):
                    c["privacy"] = b["privacy"] or None
                if "schedule_at" in b:
                    try:
                        c["schedule_at"] = datetime.fromisoformat(b["schedule_at"]).astimezone(timezone.utc).isoformat(timespec="seconds") if b["schedule_at"] else None
                    except ValueError:
                        pass
    return view(store.update(jid, f))


@router.post("/jobs/{jid}/clips/{n}/reframe")
async def reframe_clip(jid: str, n: int, req: Request) -> Any:
    """Change the layout of single scenes and re-cut this clip (the faces are not searched for again). Body: {"scenes": {"2": "split", "3": "auto"}}."""
    if not store.exists(jid):
        return err(404, "no such job")
    if pipeline.busy(jid):
        return err(409, "Wait until the job has finished.")
    job = store.load(jid)
    c = next((x for x in job["clips"] if x["n"] == n), None)
    d = store.jdir(jid)
    pf = d / "clips" / f"clip-{n}.plan.json"
    if not c or c.get("youtube_id") or not pf.is_file():
        return err(409, "This clip has no scene plan to change (it was cut without AI Reframe) or it is already posted.")
    src, shift = smart.clip_source(d, c)
    cs, ce = c["start"] - shift, c["end"] - shift
    if c.get("tight") and (d / c["tight"]).is_file():          # a tightened clip is re-cut from its own tightened source
        src, shift, cs, ce = d / c["tight"], 0.0, 0.0, float(c.get("tight_dur") or 0)
    if src is None:
        return err(409, "The source video is gone, so the clip can't be re-cut.")
    import json
    b = await req.json()
    plan = reframe.apply_overrides(json.loads(pf.read_text("utf-8")), {str(k): str(v) for k, v in (b.get("scenes") or {}).items()})
    ass = d / "clips" / f"clip-{n}.ass"
    try:
        cut.cut(str(src), str(d / "clips" / f"clip-{n}.mp4"), cs, ce, "blur", job["opts"]["quality"], ass.read_text("utf-8") if ass.is_file() else None, plan, None, pipeline.logo_of(job["opts"]))
    except Exception as e:  # noqa: BLE001
        return err(502, str(e)[:300])
    pf.write_text(json.dumps(plan), "utf-8")
    try:
        cut.cover(str(d / "clips" / f"clip-{n}.mp4"), str(d / "clips" / f"clip-{n}-cover.jpg"), c.get("title") or "")
    except Exception:  # noqa: BLE001
        pass

    def f(j: dict) -> None:
        for x in j["clips"]:
            if x["n"] == n:
                x["reframe"] = reframe.summary(plan)
                x["rev"] = int(x.get("rev", 0)) + 1
    return view(store.update(jid, f))


# ---------- editing: music shelf, re-edit, coach ----------
@router.get("/music")
def music_list() -> Any:
    return {"tracks": music.tracks(), "moods": music.MOODS}


@router.post("/music")
async def music_add(req: Request) -> Any:
    form = await req.form()
    up = form.get("file")
    if not isinstance(up, UploadFile) or not up.filename:
        return err(400, "Choose an audio file.")
    tmp = store.ROOT / "music" / f"tmp-{store.new_id()}"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    with tmp.open("wb") as out:
        while chunk := await up.read(1 << 20):
            size += len(chunk)
            if size > 30 * 1024 ** 2:
                out.close()
                tmp.unlink(missing_ok=True)
                return err(413, "That file is larger than 30 MB.")
            out.write(chunk)
    try:
        return music.add(str(form.get("name") or Path(up.filename).stem), tmp, Path(up.filename).suffix, str(form.get("mood") or "upbeat"), str(form.get("ack")).lower() in ("1", "true", "yes"))
    except ValueError as e:
        tmp.unlink(missing_ok=True)
        return err(400, str(e))


@router.delete("/music/{tid}")
def music_del(tid: str) -> Any:
    return {"ok": music.remove(tid)}


@router.get("/music/{tid}/preview")
def music_preview(tid: str) -> Any:
    f = music.file_for(tid)
    return FileResponse(f) if f else err(404, "no such track")


def _reedit(jid: str, n: int, b: dict) -> Any:
    """Re-render one clip with different polish. The clip's words are kept, so nothing is transcribed again. Returns the job view or an error response."""
    import json
    if not store.exists(jid):
        return err(404, "no such job")
    if pipeline.busy(jid):
        return err(409, "Wait until the job has finished.")
    job = store.load(jid)
    c = next((x for x in job["clips"] if x["n"] == n), None)
    d = store.jdir(jid)
    if not c or c.get("youtube_id") or c.get("status") not in ("ready", None):
        return err(409, "This clip is posted or not finished.")
    src, shift = smart.clip_source(d, c)
    tight = bool(c.get("tight")) and (d / c["tight"]).is_file()
    if tight:                                                  # a tightened clip is re-edited from its own tightened source; its words already match it
        src, shift = d / c["tight"], 0.0
    if src is None:
        return err(409, "The source video is gone, so the clip can't be re-edited.")
    wf = d / "clips" / f"clip-{n}.words.json"
    words = json.loads(wf.read_text("utf-8")) if wf.is_file() else []
    cs, ce = (0.0, float(c.get("tight_dur") or 0)) if tight else (c["start"] - shift, c["end"] - shift)
    if shift and not tight:
        words = smart.shifted(words, shift, c["start"], c["end"])
    o = dict(job["opts"]) | {k: v for k, v in b.items() if k in ("edit", "zoom", "stickers", "look", "fx", "sfx", "progress", "loudness", "music", "music_volume", "caption", "cap", "brand", "cap_lang")}
    for k in ("cap", "brand"):
        if not isinstance(o.get(k), dict):
            o[k] = {}
    o["brand"] = pipeline.clean_brand(o["brand"])
    peaks = None
    hf = d / "hype.json"
    if hf.is_file() and not tight:
        try:
            hj = json.loads(hf.read_text("utf-8"))
            peaks = hype.peaks_in(hj["curve"], hj["offset"], c["start"], c["end"], job["opts"].get("hype_level") or "balanced")
        except Exception:  # noqa: BLE001
            peaks = None
    ed = polish.plan_edit(words, cs, ce, o, c.get("moment") or c.get("title") or "", rng_seed=int(b.get("seed") or (n + int(datetime.now().timestamp()) % 1000)), peaks=peaks)
    w, h = cut.SIZES.get(o.get("quality"), cut.SIZES["720p"])
    pf = d / "clips" / f"clip-{n}.plan.json"
    plan = json.loads(pf.read_text("utf-8")) if pf.is_file() else None
    ass = cut.ass_for(words, cs, ce, o.get("caption") or "bounce", w, h, hook=c.get("hook"), cam_top=(plan.get("cam_h") or reframe.CAM_TOP) if plan and plan.get("cam") else None,
                      cap=o.get("cap"), brand=o.get("brand"), roman=o.get("cap_lang") == "roman")
    try:
        cut.cut(str(src), str(d / "clips" / f"clip-{n}.mp4"), cs, ce, job["opts"]["layout"] if job["opts"]["layout"] != "auto" else "blur", job["opts"]["quality"], ass, plan, ed, pipeline.logo_of(o), pipeline.game_ar(job["opts"]))
        cut.cover(str(d / "clips" / f"clip-{n}.mp4"), str(d / "clips" / f"clip-{n}-cover.jpg"), c.get("title") or "")
    except Exception as e:  # noqa: BLE001
        return err(502, str(e)[:300])

    def f(j: dict) -> None:
        for x in j["clips"]:
            if x["n"] == n:
                x["edit"] = ed
                x["recipe"] = coach.recipe_of(o, ed, c)
                x["rev"] = int(x.get("rev", 0)) + 1
    return view(store.update(jid, f))


@router.post("/jobs/{jid}/clips/{n}/edit")
async def edit_clip(jid: str, n: int, req: Request) -> Any:
    from starlette.concurrency import run_in_threadpool
    return await run_in_threadpool(_reedit, jid, n, await req.json())


@router.get("/coach")
def coach_get() -> Any:
    return coach.view()


@router.put("/coach")
async def coach_put(req: Request) -> Any:
    coach.set_config(await req.json())
    return coach.view()


@router.post("/coach/analyse")
def coach_analyse() -> Any:
    rt = {"updated": 0, "needs_reconnect": []}
    try:
        postqueue.refresh(force=True)
        autopilot.refresh_stats(force=True)
        rt = retention.refresh(force=True)
    except Exception:  # noqa: BLE001
        pass
    coach.analyse()
    return coach.view() | {"retention_fetch": rt}


@router.post("/coach/changes/{cid}/undo")
async def coach_undo(cid: str) -> Any:
    """Undo something the coach changed: put the old defaults back, or re-render a clip the way your own settings would have made it."""
    from starlette.concurrency import run_in_threadpool
    row = next((x for x in coach.changes(200) if x["id"] == cid), None)
    if not row:
        return err(404, "No such change.")
    if row.get("undone"):
        return err(409, "Already undone.")
    if row["kind"] == "clip":
        res = await run_in_threadpool(_reedit, row["jid"], row["n"], {k: d["from"] for k, d in row["diff"].items()})
        if isinstance(res, JSONResponse):
            return res                                  # the clip couldn't be re-rendered: leave the change as it was
    coach.undo(cid)
    return coach.view()


@router.post("/coach/apply")
def coach_apply() -> Any:
    return {"applied": coach.apply_best(), "settings": public_settings()}


@router.post("/jobs/{jid}/permission")
async def confirm_permission(jid: str, request: Request) -> Any:
    """'I have permission to use this video.' Lifts an unconfirmed job; a blocked one (site or owner says no) stays blocked."""
    if not store.exists(jid):
        return err(404, "no such job")
    try:
        body = await request.json()
    except Exception:
        body = {}
    if str(body.get("ack")).lower() not in ("true", "1", "yes"):
        return err(400, "Tick the box to confirm you have permission.")
    cur = store.load(jid).get("permission")
    if cur == "blocked":
        return err(409, "This video is marked as not allowed to reuse, so it can't be unlocked here. Upload your own video or use one you own.")
    if cur not in ("own", "cc"):
        store.update(jid, lambda j: j.__setitem__("permission", "granted"))
    return {"id": jid, "permission": store.load(jid).get("permission")}


@router.post("/jobs/{jid}/clips/{n}/post")
def post_now(jid: str, n: int) -> Any:
    """The manual button. Needs the same 'I have the rights' tick as autopilot, and posts as the privacy set on the clip or in settings."""
    if not store.exists(jid):
        return err(404, "no such job")
    st = store.settings()
    if not rights.can_post(store.load(jid)):
        return err(409, "This video's permission isn't confirmed. Check it in Auto Clip (\"Is it safe to clip?\") first.")
    if not st["rights_ack"]:
        return err(409, "Confirm that you own this content or have permission to clip it (Autopilot settings) before posting.")
    chan = autopilot.pick_channel(st)
    if not chan:
        return err(409, "Connect a YouTube channel first.")
    try:
        vid = autopilot.post_clip(jid, n, chan, st["autopilot"]["privacy"])
    except youtube.NeedsLogin as e:
        return err(401, str(e))
    except Exception as e:  # noqa: BLE001
        return err(502, str(e)[:300])
    return {"youtube_id": vid, "url": f"https://youtube.com/shorts/{vid}", "job": view(store.load(jid))}


# ---------- settings / autopilot ----------
@router.put("/settings")
async def put_settings(req: Request) -> Any:
    try:
        store.clean_settings(await req.json())
    except (TypeError, ValueError):
        return err(400, "Those settings are not valid.")
    return overview()


@router.post("/pause")
async def pause(req: Request) -> Any:
    b = await req.json()
    st = store.settings()
    st["autopilot"]["paused"] = bool(b.get("paused"))
    if not st["autopilot"]["paused"]:
        st["notice"] = None
    store.save_settings(st)
    return overview()


# ---------- YouTube ----------
@router.post("/youtube/client")
async def set_client(req: Request) -> Any:
    b = await req.json()
    cid, sec = str(b.get("client_id") or "").strip(), str(b.get("client_secret") or "").strip()
    if not cid.endswith(".apps.googleusercontent.com") or len(sec) < 10:
        return err(400, "That does not look like a Google OAuth client ID (it ends in .apps.googleusercontent.com) and secret.")
    youtube.set_client(cid, sec)
    return overview()


@router.get("/youtube/connect")
def connect(origin: str) -> Any:
    if not origin.startswith(("http://localhost", "http://127.0.0.1", "https://")):
        return err(400, "Unexpected origin.")
    try:
        return {"url": youtube.auth_url(origin), "redirect": youtube.redirect_uri(origin)}
    except RuntimeError as e:
        return err(400, str(e))


@router.get("/youtube/redirect")
def redirect_hint(origin: str) -> dict:
    return {"redirect": youtube.redirect_uri(origin)}


@router.get("/youtube/callback")
def callback(code: str = "", state: str = "", error: str = "") -> Any:
    back = "/autoclip"
    try:
        if error or not code:
            raise RuntimeError("Google did not give permission" + (f" ({error})" if error else "") + ".")
        info = youtube.finish(code, state)
        postqueue.release(info["id"])
        return RedirectResponse(f"{back}?connected={info['id']}")
    except Exception as e:  # noqa: BLE001
        from urllib.parse import quote
        return RedirectResponse(f"{back}?error={quote(str(e)[:200])}")


@router.delete("/youtube/channels/{cid}")
def disconnect(cid: str) -> Any:
    return {"ok": youtube.disconnect(cid)}


# ---------- other platforms: Instagram, Facebook, TikTok ----------
def _plat(platform: str) -> bool:
    return platform in {x["id"] for x in social.PLATFORMS if x["status"] == "ready"}


@router.get("/social")
def social_list(origin: str = "") -> Any:
    return {"platforms": social.platforms(origin), "youtube": {"has_client": youtube.has_client(), "channels": youtube.channels()}}


@router.post("/social/{platform}/client")
async def social_client(platform: str, req: Request) -> Any:
    if not _plat(platform):
        return err(404, "Unknown platform.")
    b = await req.json()
    try:
        social.set_client(platform, str(b.get("key") or ""), str(b.get("secret") or ""))
    except ValueError as e:
        return err(400, str(e))
    return {"ok": True}


@router.get("/social/{platform}/connect")
def social_connect(platform: str, origin: str) -> Any:
    if not _plat(platform):
        return err(404, "Unknown platform.")
    if not origin.startswith(("http://localhost", "http://127.0.0.1", "https://")):
        return err(400, "Unexpected origin.")
    try:
        return {"url": social.auth_url(platform, origin), "redirect": social.redirect_uri(platform, origin)}
    except RuntimeError as e:
        return err(400, str(e))


@router.get("/social/{platform}/callback")
def social_callback(platform: str, code: str = "", state: str = "", error: str = "", error_description: str = "") -> Any:
    from urllib.parse import quote
    back = "/connections"
    try:
        if not _plat(platform):
            raise RuntimeError("Unknown platform.")
        if error or not code:
            raise RuntimeError("The sign-in was cancelled or refused" + (f" ({error_description or error})" if (error_description or error) else "") + ".")
        info = social.finish(platform, code, state)
        for aid in info["added"]:
            postqueue.release(aid)
        return RedirectResponse(f"{back}?connected={quote(', '.join(info['titles'])[:200])}")
    except Exception as e:  # noqa: BLE001
        return RedirectResponse(f"{back}?error={quote(str(e)[:240])}")


@router.delete("/social/accounts/{aid:path}")
def social_disconnect(aid: str) -> Any:
    return {"ok": social.disconnect(aid)}


# ---------- numbers ----------
@router.get("/stats")
def stats(refresh: bool = False) -> Any:
    try:
        n = autopilot.refresh_stats(force=refresh)
    except Exception:  # noqa: BLE001
        n = 0
    posted, views = [], 0
    for j in store.listing():
        job = store.load(j["id"])
        for c in job.get("clips") or []:
            if c.get("youtube_id"):
                s = c.get("stats") or {}
                views += int(s.get("views") or 0)
                posted.append({"job": job["id"], "n": c["n"], "title": c["title"], "youtube_id": c["youtube_id"], "posted_at": c.get("posted_at"),
                               "views": s.get("views"), "likes": s.get("likes"), "privacy": s.get("privacy") or c.get("privacy")})
    rev = None
    end = datetime.now(timezone.utc).date()
    for ch in youtube.channels():
        if ch.get("revenue_scope") and not ch.get("needs_login"):
            try:
                rev = youtube.revenue(ch["id"], str(end - timedelta(days=28)), str(end))
            except Exception:  # noqa: BLE001
                rev = None
    posted.sort(key=lambda x: x["posted_at"] or "", reverse=True)
    return {"posted": posted[:100], "views": views, "refreshed": n, "revenue_28d": rev,
            "note": "Earnings exist only for channels in the YouTube Partner Programme; otherwise this stays empty."}


# ---------- comments, experiments, readiness ----------
@router.get("/comments")
def comments_get(status: str | None = None) -> Any:
    return comments.view(status)


@router.post("/comments/sync")
async def comments_sync() -> Any:
    from starlette.concurrency import run_in_threadpool
    s = {"id": "comments", "crew": store.settings()["defaults"].get("crew") or "builtin", "language": "en", "format": {"width": 720, "height": 1280}, "settings": {"models": {}, "local_only": False}}
    res = await run_in_threadpool(comments.sync, None, 12, s)
    return comments.view() | {"sync": res}


@router.post("/comments/{cid}/draft")
async def comments_draft(cid: str) -> Any:
    from starlette.concurrency import run_in_threadpool
    it = comments.load()["items"].get(cid)
    if not it:
        return err(404, "No such comment.")
    s = {"id": "comments", "crew": store.settings()["defaults"].get("crew") or "builtin", "language": "en", "format": {"width": 720, "height": 1280}, "settings": {"models": {}, "local_only": False}}
    dr = await run_in_threadpool(comments.draft_reply, it, s)
    comments.set_status(cid, it["status"] if it["status"] != "spam" else "new", draft=dr)
    return comments.view()


@router.post("/comments/{cid}/reply")
async def comments_reply(cid: str, req: Request) -> Any:
    """Post a reply. This is the only way a reply is ever sent: it needs your press."""
    from starlette.concurrency import run_in_threadpool
    b = await req.json()
    try:
        await run_in_threadpool(comments.post_reply, cid, str(b.get("text") or ""))
    except KeyError:
        return err(404, "No such comment.")
    except ValueError as e:
        return err(400, str(e))
    except youtube.NeedsScope:
        return err(403, "This channel was connected before comments were allowed. Disconnect it and connect it again.")
    except Exception as e:  # noqa: BLE001
        return err(502, str(e)[:240])
    return comments.view()


@router.post("/comments/{cid}/{action}")
async def comments_act(cid: str, action: str) -> Any:
    """dismiss | release (a flagged comment is fine) | hold (ask YouTube to hold it for review)."""
    from starlette.concurrency import run_in_threadpool
    try:
        if action == "dismiss":
            comments.set_status(cid, "dismissed")
        elif action == "release":
            comments.set_status(cid, "new", why="")
        elif action == "hold":
            it = comments.load()["items"].get(cid)
            if not it:
                return err(404, "No such comment.")
            await run_in_threadpool(youtube.hold_comment, it["channel"], cid)
            comments.set_status(cid, "held")
        else:
            return err(404, "unknown action")
    except KeyError:
        return err(404, "No such comment.")
    except youtube.NeedsScope:
        return err(403, "This channel was connected before comments were allowed. Disconnect it and connect it again.")
    except Exception as e:  # noqa: BLE001
        return err(502, str(e)[:240])
    return comments.view()


@router.get("/experiments")
def experiments_get() -> Any:
    return experiments.summary() | {"settings": store.settings().get("experiments")}


# ---------- captions: fonts, brand logo, saved looks, system, estimate ----------
@router.get("/fonts")
def fonts_get() -> Any:
    return {"fonts": captions.font_list()}


@router.post("/fonts")
async def fonts_add(req: Request) -> Any:
    form = await req.form()
    up = form.get("file")
    if not isinstance(up, UploadFile) or not up.filename or Path(up.filename).suffix.lower() not in (".ttf", ".otf"):
        return err(400, "Choose a .ttf or .otf font file.")
    data = await up.read(10 * 1024 ** 2 + 1)
    if len(data) > 10 * 1024 ** 2:
        return err(413, "That font is larger than 10 MB.")
    if data[:4] not in (b"\x00\x01\x00\x00", b"OTTO", b"true"):
        return err(400, "That file is not a TrueType or OpenType font.")
    name = re.sub(r"[^A-Za-z0-9._-]", "_", Path(up.filename).name)[:80]
    dst = captions.user_fonts() / name
    dst.write_bytes(data)
    (store.ROOT / "fonts_all" / name).unlink(missing_ok=True)
    return {"fonts": captions.font_list(), "added": captions.family_of(dst)}


@router.delete("/fonts/{name}")
def fonts_del(name: str) -> Any:
    p = captions.user_fonts() / Path(name).name
    if p.suffix.lower() in (".ttf", ".otf"):
        p.unlink(missing_ok=True)
        (store.ROOT / "fonts_all" / p.name).unlink(missing_ok=True)
    return {"fonts": captions.font_list()}


def _logo() -> Path:
    return store.ROOT / "brand" / "logo.png"


@router.post("/brand/logo")
async def logo_add(req: Request) -> Any:
    """Your logo for the watermark: any picture, kept as a PNG (transparency is kept)."""
    import subprocess
    import tempfile
    from .. import config
    form = await req.form()
    up = form.get("file")
    if not isinstance(up, UploadFile) or not up.filename or Path(up.filename).suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
        return err(400, "Choose a PNG, JPG or WebP picture.")
    data = await up.read(8 * 1024 ** 2 + 1)
    if len(data) > 8 * 1024 ** 2:
        return err(413, "That picture is larger than 8 MB.")
    tmp = Path(tempfile.mkdtemp()) / ("in" + Path(up.filename).suffix.lower())
    tmp.write_bytes(data)
    _logo().parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([config.ffmpeg(), "-v", "error", "-y", "-nostdin", "-i", str(tmp), "-vf", "scale='min(800,iw)':-1", "-frames:v", "1", str(_logo())], capture_output=True, text=True, timeout=60)
    shutil.rmtree(tmp.parent, ignore_errors=True)
    if r.returncode != 0 or not _logo().is_file():
        return err(400, "That picture could not be read.")
    return {"ok": True}


@router.get("/brand/logo")
def logo_get() -> Any:
    from fastapi.responses import FileResponse
    return FileResponse(str(_logo()), media_type="image/png") if _logo().is_file() else err(404, "no logo")


@router.delete("/brand/logo")
def logo_del() -> Any:
    _logo().unlink(missing_ok=True)
    return {"ok": True}


def _canvas() -> Path:
    return store.ROOT / "brand" / "canvas.png"


@router.post("/brand/canvas")
async def canvas_add(req: Request) -> Any:
    """Your own background picture for the canvas behind the clip (blurred and dimmed by the canvas settings)."""
    import subprocess
    import tempfile
    from .. import config
    form = await req.form()
    up = form.get("file")
    if not isinstance(up, UploadFile) or not up.filename or Path(up.filename).suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
        return err(400, "Choose a PNG, JPG or WebP picture.")
    data = await up.read(12 * 1024 ** 2 + 1)
    if len(data) > 12 * 1024 ** 2:
        return err(413, "That picture is larger than 12 MB.")
    tmp = Path(tempfile.mkdtemp()) / ("in" + Path(up.filename).suffix.lower())
    tmp.write_bytes(data)
    _canvas().parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([config.ffmpeg(), "-v", "error", "-y", "-nostdin", "-i", str(tmp), "-vf", "scale='min(1440,iw)':-1", "-frames:v", "1", str(_canvas())], capture_output=True, text=True, timeout=60)
    shutil.rmtree(tmp.parent, ignore_errors=True)
    if r.returncode != 0 or not _canvas().is_file():
        return err(400, "That picture could not be read.")
    return {"ok": True}


@router.delete("/brand/canvas")
def canvas_del() -> Any:
    _canvas().unlink(missing_ok=True)
    return {"ok": True}


def _avatar() -> Path:
    return store.ROOT / "brand" / "avatar.png"


@router.post("/brand/avatar")
async def avatar_add(req: Request) -> Any:
    """Your profile picture for the post-card templates (cropped to a circle)."""
    import subprocess
    import tempfile
    from .. import config
    form = await req.form()
    up = form.get("file")
    if not isinstance(up, UploadFile) or not up.filename or Path(up.filename).suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
        return err(400, "Choose a PNG, JPG or WebP picture.")
    data = await up.read(8 * 1024 ** 2 + 1)
    if len(data) > 8 * 1024 ** 2:
        return err(413, "That picture is larger than 8 MB.")
    tmp = Path(tempfile.mkdtemp()) / ("in" + Path(up.filename).suffix.lower())
    tmp.write_bytes(data)
    _avatar().parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([config.ffmpeg(), "-v", "error", "-y", "-nostdin", "-i", str(tmp), "-vf", "scale='min(400,iw)':-1", "-frames:v", "1", str(_avatar())], capture_output=True, text=True, timeout=60)
    shutil.rmtree(tmp.parent, ignore_errors=True)
    if r.returncode != 0 or not _avatar().is_file():
        return err(400, "That picture could not be read.")
    return {"ok": True}


@router.get("/brand/avatar")
def avatar_get() -> Any:
    from fastapi.responses import FileResponse
    if not _avatar().is_file():
        return err(404, "No avatar uploaded.")
    return FileResponse(str(_avatar()), media_type="image/png", headers={"Cache-Control": "no-store"})


@router.get("/brands")
def brands_get() -> Any:
    return {"brands": store.brands(), "has_logo": _logo().is_file(), "has_canvas": _canvas().is_file(), "has_avatar": _avatar().is_file()}


@router.post("/brands")
async def brands_add(req: Request) -> Any:
    try:
        return {"brands": store.save_brand(await req.json())}
    except ValueError as e:
        return err(400, str(e))


@router.delete("/brands/{name}")
def brands_del(name: str) -> Any:
    return {"brands": store.delete_brand(name)}


@router.get("/system")
def system() -> Any:
    """The status bar: this machine, the speech model, face tracking and the encoder."""
    import importlib.util as iu
    d = store.settings()["defaults"]
    try:
        free = shutil.disk_usage(str(store.ROOT)).free / 1024 ** 3
    except OSError:
        free = 0.0
    return {"cpus": os.cpu_count() or 0, "ram_gb": ram_gb(), "disk_free_gb": round(free, 1),
            "whisper": iu.find_spec("faster_whisper") is not None, "whisper_model": d.get("whisper_model") or "small", "whisper_pick": whisper_pick(),
            "faces": reframe.status().get("ready", False), "encoder": "libx264 (CPU)", "busy": [j["id"] for j in store.listing() if pipeline.busy(j["id"])][:5]}


@router.post("/estimate")
async def estimate(req: Request) -> Any:
    b = await req.json()
    try:
        minutes = float(b.get("minutes") or 0)
    except (TypeError, ValueError):
        minutes = 0.0
    if minutes <= 0:
        return err(400, "The video length is not known yet.")
    return pipeline.estimate(minutes, b.get("opts") or {})


@router.get("/fonts/file/{name}")
def fonts_file(name: str) -> Any:
    """A font file, so the page can draw the style samples in the real fonts."""
    from fastapi.responses import FileResponse
    p = captions.fonts_dir() / Path(name).name
    if p.suffix.lower() not in (".ttf", ".otf") or not p.is_file():
        return err(404, "no such font")
    return FileResponse(str(p), media_type="font/ttf" if p.suffix.lower() == ".ttf" else "font/otf", headers={"Cache-Control": "max-age=86400"})


def _repack(jid: str, n: int, fresh: bool) -> Any:
    from . import research
    from ..series import writers
    if not store.exists(jid):
        return err(404, "no such job")
    if pipeline.busy(jid):
        return err(409, "Wait until the job has finished.")
    job = store.load(jid)
    c = next((x for x in job["clips"] if x["n"] == n), None)
    if not c:
        return err(404, "no such clip")
    if c.get("youtube_id"):
        return err(409, "This clip is already posted.")
    s = {"id": jid, "crew": job["opts"].get("crew") or "builtin", "language": "en", "format": {"width": 720, "height": 1280}, "settings": {"models": {}, "local_only": False}}
    ask = (lambda sysm, prompt: writers.ask(s, "story", sysm, prompt, None, max_tokens=700, temperature=0.4)) if writers.uses_ai(s) else None  # noqa: E731
    logs: list[str] = []
    c.pop("seo", None)
    summary = research.run(job, [c], ask, logs.append, fresh)
    pipeline.apply_packs([c])

    def f(j: dict) -> None:
        for x in j["clips"]:
            if x["n"] == n:
                x.update({k: c[k] for k in ("seo", "title", "description", "hook") if k in c})
        old = {r.get("query"): r for r in (j.get("research") or [])}
        old.update(summary)
        j["research"] = list(old.values())
    for t in logs:
        store.say(jid, t)
    return view(store.update(jid, f))


@router.post("/jobs/{jid}/clips/{n}/seo")
async def repack(jid: str, n: int, req: Request) -> Any:
    """Run the packaging team again for one clip: fresh research on the top Shorts, then a new title, description, hashtags and mentions."""
    from starlette.concurrency import run_in_threadpool
    try:
        b = await req.json()
    except Exception:  # noqa: BLE001
        b = {}
    return await run_in_threadpool(_repack, jid, n, bool(b.get("fresh", True)))


@router.get("/explore")
async def explore_list(cat: str = "all", region: str = "IN", fresh: int = 0, length: str = "long") -> Any:
    """Trending videos ready to clip, by category and country (see explore.py)."""
    from starlette.concurrency import run_in_threadpool
    from . import explore
    try:
        res = await run_in_threadpool(explore.trending, cat, region, bool(fresh), "any" if length == "any" else "long")
        mine = store.settings().get("explore_channels") or []
    except Exception as e:  # noqa: BLE001
        return err(502, f"Could not load what is trending ({str(e)[:160]}).")
    return res | {"mine": mine} | {"cats": {k: v["label"] for k, v in explore.CATS.items()}, "regions": explore.REGIONS}


@router.post("/explore/channels")
async def explore_add(req: Request) -> Any:
    from . import explore
    try:
        return {"mine": explore.add_channel(str((await req.json()).get("handle") or ""))}
    except ValueError as e:
        return err(400, str(e))


@router.delete("/explore/channels/{handle}")
def explore_del(handle: str) -> Any:
    from . import explore
    return {"mine": explore.remove_channel(handle)}
