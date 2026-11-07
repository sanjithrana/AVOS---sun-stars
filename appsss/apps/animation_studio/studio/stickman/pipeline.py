"""The stickman production line, on one background thread per project:

    topics (you pick) → brief → story → roster → clip plans + prompts → reference sheets (you approve) → scene images
    → animation (AI video, else picture + camera move) → voices → six ten-second clips joined with captions → final.mp4

Every step records its files, so Continue skips what is done. With auto=True the two approvals are skipped."""
from __future__ import annotations

import threading
from typing import Any

from .. import config
from ..explainer import captions, engines as xeng, pipeline as xp
from ..series import assemble, media
from . import continuity, package, planner, prompts, spec, store, styles, video

STAGES = ("topics", "brief", "story", "roster", "clips", "refs", "scenes", "animate", "voice", "finish")
LABELS = {"topics": "Topic ideas", "brief": "Fact brief", "story": "Story and narration", "roster": "Characters", "clips": "Clip prompts",
          "refs": "Reference sheets", "scenes": "Scene images", "animate": "Animation", "voice": "Voiceover", "finish": "Captions and final video"}
GATES = ("topics", "story", "refs")          # the idea, the director's treatment (story and narration), the character sheets
MOVES = {"static": "static", "slow push in": "push_in", "slow pull out": "pull_out", "pan left": "pan_left", "pan right": "pan_right", "tilt up": "tilt_up", "tilt down": "tilt_down"}
_threads: dict[str, threading.Thread] = {}
_cancel: dict[str, threading.Event] = {}


class Stopped(Exception):
    pass


def sdict(p: dict) -> dict:
    w, h = spec.ASPECTS.get(p.get("aspect") or "9:16", spec.ASPECTS["9:16"])
    return {"id": p["id"], "crew": p.get("crew") or "builtin", "language": p.get("language") or "en", "format": {"width": w, "height": h},
            "settings": {"models": p.get("models") or {}, "local_only": bool(p.get("local_only"))}, "interest": p.get("interest") or "", "aspect": p.get("aspect") or "9:16", "style": p.get("style") or styles.DEFAULT}


def _check(pid: str) -> None:
    ev = _cancel.get(pid)
    if ev is not None and ev.is_set():
        raise Stopped()


def _set(pid: str, **kw: Any) -> None:
    store.update(pid, lambda p: p.update(kw))


def _file(pid: str, name: str, data: bytes) -> str:
    (store.pdir(pid) / name).write_bytes(data)
    return name


def _have(pid: str, name: str | None) -> bool:
    return bool(name) and (store.pdir(pid) / name).is_file()


def _read(pid: str, name: str | None) -> bytes | None:
    return (store.pdir(pid) / name).read_bytes() if _have(pid, name) else None


def _log(pid: str):
    return lambda ev: store.say(pid, ev.get("text") or "", ev.get("type") or "info") if ev.get("text") else None


# ---------- stages ----------
def do_topics(pid: str) -> None:
    p = store.load(pid)
    store.say(pid, "Looking for eight specific historical events…")
    _set(pid, topics=planner.topics(sdict(p), _log(pid), p.get("note") or ""), note="")


def do_brief(pid: str) -> None:
    p = store.load(pid)
    store.say(pid, "Writing the fact brief…")
    b = planner.brief(sdict(p), p, _log(pid))
    def f(q: dict) -> None:
        q["brief"] = b
        if not q["project"].get("date_place"):
            q["project"]["date_place"] = ", ".join(x for x in (b["date"], b["location"]) if x)
    store.update(pid, f)


def do_story(pid: str) -> None:
    p = store.load(pid)
    store.say(pid, "Writing the story and narration…")
    st = planner.story(sdict(p), p, _log(pid), p.get("note") or "")
    _set(pid, story=st, title=st.get("title") or p["title"], note="")
    store.say(pid, "Writing the continuity bible (layout, props, visual rules, music)…")
    try:
        _set(pid, bible=planner.bible(sdict(p), store.load(pid), _log(pid)))
    except Exception as e:  # noqa: BLE001 - the bible sharpens the prompts; the film still works without it
        store.say(pid, f"Continuity bible skipped: {str(e)[:140]}", "warn")


def do_roster(pid: str) -> None:
    p = store.load(pid)
    store.say(pid, "Designing the characters…")
    _set(pid, roster=planner.roster(sdict(p), p, _log(pid)))


def compile_clip(p: dict, clip: dict) -> dict:
    clip["scene_prompt"] = prompts.scene_prompt(p, clip)
    clip["animation_prompt"] = prompts.animation_prompt(p, clip)
    clip["words"] = {"scene": spec.words(clip["scene_prompt"]), "animation": spec.words(clip["animation_prompt"])}
    clip["narration_warning"] = spec.narration_warning(p["story"]["clips"][clip["n"] - 1]["narration"])
    return clip


def do_clips(pid: str) -> None:
    p = store.load(pid)
    s = sdict(p)
    done = {c["n"]: c for c in p.get("clips") or []}
    for n in range(1, p["clip_count"] + 1):
        _check(pid)
        if n in done:
            continue
        store.say(pid, f"Planning clip {n} of {p['clip_count']}…")
        q = store.load(pid)
        clip = compile_clip(q, planner.clip_plan(s, q, n, _log(pid)))
        store.update(pid, lambda x, clip=clip: x.setdefault("clips", []).append(clip))
    q = store.load(pid)
    def f(x: dict) -> None:
        for c in x["clips"]:
            compile_clip(x, c)
        x["consistency"] = prompts.consistency_prompt(x)
        x["continuity"] = {"record": continuity.record(x), "issues": continuity.check(x)}
    store.update(pid, f)


def do_refs(pid: str) -> None:
    p = store.load(pid)
    s = sdict(p)
    for c in p["roster"]:
        _check(pid)
        name = f"{c['id']}_sheet.png"
        if _have(pid, name):
            continue
        store.say(pid, f"Drawing the reference sheet for {c['name']}…")
        ref = styles.reference(p.get("style"))            # the style's sample frame: the sheet is drawn in that exact look
        if ref:
            data, info = media.picture("Image 0 is the STYLE reference only (copy its drawing style, line weight and colouring, not its scene). " + prompts.sheet_prompt(p, c),
                                       [ref], 1280, 720, media.seed_of(pid, c["id"], "sheet"), f"{pid}:{c['id']}:sheet", s=s, negative=prompts.NEGATIVE)
            mid = info.get("model")
        else:
            data, mid = media._t2i(prompts.sheet_prompt(p, c), 1280, 720, media.seed_of(pid, c["id"], "sheet"), s=s)
        _file(pid, name, data)
        def f(q: dict, c=c, name=name, mid=mid) -> None:
            q.setdefault("assets", {})[f"sheet:{c['id']}"] = name
            q["consistency"] = prompts.consistency_prompt(q)
        store.update(pid, f)
    p = store.load(pid)
    if p.get("bible") and not _have(pid, "layout.png"):         # the fixed location reference every opening is drawn from
        _check(pid)
        store.say(pid, "Drawing the location continuity reference…")
        W, H = spec.ASPECTS.get(p.get("aspect") or "9:16", spec.ASPECTS["9:16"])
        ref = styles.reference(p.get("style"))
        sheet = _read(pid, (p.get("assets") or {}).get(f"sheet:{p['roster'][0]['id']}")) if p.get("roster") else None
        refs = [x for x in (sheet, ref) if x]
        lead = ("Image 0 is the character identity sheet. " if sheet else "") + ("The last image is the style reference: copy its drawing style only. " if ref else "")
        data, info = media.picture(lead + prompts.layout_prompt(p), refs, W, H, media.seed_of(pid, "layout"), f"{pid}:layout", s=s, negative=prompts.NEGATIVE)
        _file(pid, "layout.png", data)
        chk = planner.inspect(s, p, [store.pdir(pid) / "layout.png"], "the full location layout with every prop in place")
        store.update(pid, lambda q, chk=chk: (q.setdefault("assets", {}).update(layout="layout.png"), q.update(layout_check=chk)))
        if chk and not chk.get("ok"):
            store.say(pid, "Layout check: " + "; ".join(chk.get("defects") or []), "warn")


def do_scenes(pid: str, only: int | None = None, note: str = "") -> None:
    p = store.load(pid)
    s = sdict(p)
    W, H = s["format"]["width"], s["format"]["height"]
    for c in p["clips"]:
        if only and c["n"] != only:
            continue
        _check(pid)
        name = f"C{c['n']:02d}_scene.png"
        if _have(pid, name) and not only:
            continue
        store.say(pid, f"Scene image for clip {c['n']}…")
        sheets = [r for r in (_read(pid, (p.get("assets") or {}).get(f"sheet:{x['id']}")) for x in c["chars"]) if r][:2]
        layout = _read(pid, (p.get("assets") or {}).get("layout"))
        prev = _read(pid, f"C{c['n'] - 1:02d}_scene.png") if c["n"] > 1 and c.get("transition") != "cut" and not layout else None
        ref = styles.reference(p.get("style"))
        refs = [*sheets, *([layout] if layout else []), *([prev] if prev else []), *([ref] if ref else [])][:4]
        lead = (f"The first {len(sheets)} image(s) are the character identity sheets: draw exactly these characters. " if sheets else "") \
            + ("The next image is the fixed location layout: keep its arrangement, props, lights and palette. " if layout else "") \
            + ("The next image is the previous clip's first frame: keep the same place, light and characters. " if prev else "") \
            + ("The last image is the style reference: copy its drawing style only, not its scene. " if ref and len(refs) < 5 and refs[-1] is ref else "")
        prompt = lead + c["scene_prompt"] + (f" Change: {note}." if note else "")
        data, info = media.picture(prompt, refs, W, H, media.seed_of(pid, c["n"], c.get("version", 1), "scene"), f"{pid}:C{c['n']}", s=s, negative=prompts.NEGATIVE)
        _file(pid, name, data)
        chk = planner.inspect(s, p, [store.pdir(pid) / name], f"the first frame of clip {c['n']}: {c['opening_setup']}")
        if chk and not chk.get("ok") and chk.get("fix"):            # one targeted correction, keeping the accepted framing
            store.say(pid, f"Clip {c['n']} opening: {'; '.join(chk.get('defects') or [])}. Correcting it.", "warn")
            data, info = media.picture(prompt + f" Correction: {chk['fix']}", [data, *refs][:4], W, H, media.seed_of(pid, c["n"], c.get("version", 1), "scene", "fix"),
                                       f"{pid}:C{c['n']}:fix", s=s, negative=prompts.NEGATIVE)
            _file(pid, name, data)
            chk = {**(planner.inspect(s, p, [store.pdir(pid) / name], f"the corrected first frame of clip {c['n']}") or chk), "corrected": True}
        def f(q: dict, n=c["n"], name=name, info=info, chk=chk) -> None:
            q["clips"][n - 1].update(scene=name, scene_model=info.get("model"), scene_check=chk)
            if n == 1:
                q["thumb"] = name
        store.update(pid, f)


def do_animate(pid: str, only: int | None = None) -> None:
    p = store.load(pid)
    s = sdict(p)
    caps = xeng.capabilities(s)
    for c in p["clips"]:
        if only and c["n"] != only:
            continue
        _check(pid)
        name = f"C{c['n']:02d}_video.mp4"
        if _have(pid, name) and not only:
            continue
        key = _read(pid, c.get("scene"))
        if key is None:
            raise RuntimeError(f"clip {c['n']} has no scene image yet")
        shot = {"camera": {"movement": MOVES.get(c["camera_move"], "static")}, "sfx": ""}
        store.say(pid, f"Animating clip {c['n']}…")
        seed = media.seed_of(pid, c["n"], c.get("version", 1), "video")
        st = styles.get(p.get("style"))
        if not st.get("autopilot") and video.ready(s):           # Seedance 2.0 from the opening, the identity sheet, the layout and the previous clip
            imgs = [key, *[r for r in (_read(pid, (p.get("assets") or {}).get(f"sheet:{x['id']}")) for x in c["chars"][:1]) if r],
                    *([_read(pid, (p.get("assets") or {}).get("layout"))] if (p.get("assets") or {}).get("layout") else [])]
            prev = _read(pid, f"C{c['n'] - 1:02d}_video.mp4") if c["n"] > 1 else None
            prm = prompts.reference_video_prompt(p, c, len(imgs), bool(prev and len(prev) <= video.MAX_VIDEO_REF))
            try:
                data = video.clip(prm, imgs, prev, spec.CLIP_SECONDS, p.get("aspect") or "9:16", bool(st.get("native_audio")))
                info = {"engine": "ai_video", "model": "Seedance 2.0 mini (references)", "fallback": False, "native_audio": bool(st.get("native_audio"))}
                store.update(pid, lambda q, n=c["n"], prm=prm: q["clips"][n - 1].update(reference_prompt=prm))
            except Exception as e:  # noqa: BLE001 - no credit or offline: the usual path below
                store.say(pid, f"Seedance could not make clip {c['n']} ({str(e)[:160]}); using the standard video path.", "warn")
                data = None
            if data is not None:
                _file(pid, name, data)
                store.update(pid, lambda q, n=c["n"], name=name, info=info: q["clips"][n - 1].update(
                    video=name, engine=info["engine"], video_model=info["model"], native_audio=info["native_audio"], video_note="", status="done"))
                continue
        if st.get("autopilot"):    # Autopilot looks: the illustration with subtle motion, by design
            data, info = xeng.still(s, shot, key, float(spec.CLIP_SECONDS))
            info["note"] = "Autopilot style: illustration with subtle motion"
        elif caps["ai_video"] or media.strict(s, "motion"):
            data, info = xeng.ai_video(s, shot, key, float(spec.CLIP_SECONDS), seed, c["animation_prompt"], f"{pid}:C{c['n']}")
        else:
            data, info = xeng.still(s, shot, key, float(spec.CLIP_SECONDS), "no AI video model is ready (add fal.ai credit or a GPU worker); the scene image gets a camera move")
        _file(pid, name, data)
        got = 0.0
        try:
            got = media.probe_seconds(store.pdir(pid) / name)
        except Exception:  # noqa: BLE001
            pass
        note = (info.get("note") or "") + (f" The model returned {got:.1f} s; the editor will hold the last frame or trim it to {spec.CLIP_SECONDS} s." if got and abs(got - spec.CLIP_SECONDS) > 0.5 else "")
        store.update(pid, lambda q, n=c["n"], name=name, info=info, note=note: q["clips"][n - 1].update(
            video=name, engine=info.get("engine"), video_model=info.get("model"), video_note=note.strip(), status="fallback" if info.get("fallback") else "done"))


def do_voice(pid: str) -> None:
    p = store.load(pid)
    s = sdict(p)
    for sc in p["story"]["clips"]:
        _check(pid)
        name = f"C{sc['n']:02d}_voice.wav"
        if _have(pid, name) or p["clips"][sc["n"] - 1].get("native_audio"):     # the clip already speaks its narration
            continue
        store.say(pid, f"Voiceover for clip {sc['n']}…")
        wav, info = xp._voice(s, sc["narration"], p)
        _file(pid, name, wav)
        secs = media.wav_seconds(wav)
        warn = f"The narration runs {secs:.1f} s, longer than the {spec.CLIP_SECONDS}-second clip: shorten the narration." if secs > spec.CLIP_SECONDS - 0.4 else ""
        store.update(pid, lambda q, n=sc["n"], secs=secs, warn=warn, info=info: q["clips"][n - 1].update(voice=f"C{n:02d}_voice.wav", voice_seconds=round(secs, 2), voice_warning=warn, voice_model=info.get("model")))


def do_finish(pid: str) -> None:
    p = store.load(pid)
    s = sdict(p)
    W, H = s["format"]["width"], s["format"]["height"]
    d = store.pdir(pid)
    work = d / "work"
    work.mkdir(exist_ok=True)
    rows, parts, at = [], [], 0.0
    sec = float(spec.CLIP_SECONDS)
    native, show_caps = 0, styles.get(p.get("style")).get("captions", True)
    for c in p["clips"]:
        _check(pid)
        clip, line = d / (c.get("video") or ""), d / (c.get("voice") or "")
        if not clip.is_file():
            raise RuntimeError(f"clip {c['n']} has no video yet")
        fit = assemble.fit_shot(clip, work / f"C{c['n']:02d}_fit.mp4", sec, W, H)
        if c.get("native_audio") and video.has_audio(clip):          # keep the model's own narration, music, ambience and effects
            aud = work / f"C{c['n']:02d}_a.wav"
            xp._ff(["-i", str(clip), "-vn", "-af", f"apad,atrim=0:{sec}", "-ar", "48000", "-ac", "2", str(aud)])
            native += 1
        else:
            aud = assemble.shot_audio(work / f"C{c['n']:02d}_a.wav", sec, line if line.is_file() else None, None, line_at=0.3)
        parts.append({"video": fit, "audio": aud, "seconds": sec})
        if show_caps:
            rows += captions.chunks(p["story"]["clips"][c["n"] - 1]["narration"], at + 0.3, at + sec - 0.2)
        at += sec
    store.say(pid, "Joining the clips…")
    music, mpath = None, None
    try:
        music = None
        if native < len(p["clips"]):                                   # native clips bring their own score
            music, _ = media.music(s, (p.get("bible") or {}).get("music") or p["clips"][0]["music"], at, f"{pid}:music")
    except Exception as e:  # noqa: BLE001 - optional
        store.say(pid, f"No music this time ({str(e)[:120]})", "warn")
    if music:
        mpath = work / "music.wav"
        mpath.write_bytes(media.to_wav(music))
    joined = assemble.part(parts, work, work / "joined.mp4", W, H, mpath, rows)
    (work / "captions.ass").write_text(captions.ass(rows, W, H), "utf-8")
    out = d / "final.mp4"
    if not rows:                                                       # no on-screen text for this style
        import shutil
        shutil.copyfile(joined, out)
        (d / "final.srt").write_text("", "utf-8")
        (d / "package.md").write_text(package.build(store.load(pid)), "utf-8")
        _set(pid, final="final.mp4", finalSeconds=round(at, 1))
        return
    xp._ff(["-i", str(joined.resolve()), "-vf", "ass=captions.ass", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "copy", "-movflags", "+faststart", str(out.resolve())], cwd=work)
    (d / "final.srt").write_text(assemble.srt(rows), "utf-8")
    (d / "package.md").write_text(package.build(store.load(pid)), "utf-8")
    _set(pid, final="final.mp4", finalSeconds=round(at, 1))


RUN = {"topics": do_topics, "brief": do_brief, "story": do_story, "roster": do_roster, "clips": do_clips, "refs": do_refs, "scenes": do_scenes,
       "animate": do_animate, "voice": do_voice, "finish": do_finish}


def write_package(pid: str) -> str:
    p = store.load(pid)
    text = package.build(p)
    (store.pdir(pid) / "package.md").write_text(text, "utf-8")
    return text


# ---------- runner ----------
def busy(pid: str) -> bool:
    t = _threads.get(pid)
    return bool(t and t.is_alive())


def _gated(p: dict, stage: str) -> bool:
    return stage in GATES and not p.get("auto")


def _run(pid: str, start: str) -> None:
    try:
        i = STAGES.index(start)
        while i < len(STAGES):
            st = STAGES[i]
            _set(pid, status="working", stage=st, error=None)
            _check(pid)
            RUN[st](pid)
            if st in ("clips", "refs", "scenes", "animate", "voice"):
                try:
                    write_package(pid)
                except Exception:  # noqa: BLE001 - the package is a convenience; the run goes on
                    pass
            q = store.load(pid)
            if st == "topics" and q.get("auto"):
                pick(pid, q["topics"].get("recommended", 0))
            if _gated(store.load(pid), st):
                _set(pid, status="waiting", stage=st)
                store.say(pid, f"{LABELS[st]} ready for your decision.")
                return
            i += 1
        _set(pid, status="done", stage="finish")
        store.say(pid, "Your video and the written package are ready.")
    except Stopped:
        _set(pid, status="stopped")
        store.say(pid, "Stopped.", "warn")
    except Exception as e:  # noqa: BLE001 - kept and shown; Continue picks up
        _set(pid, status="error", error=str(e)[:600])
        store.say(pid, f"Stopped at {LABELS.get(store.load(pid).get('stage'), '')}: {str(e)[:300]}", "error")


def start(pid: str, stage: str) -> bool:
    if busy(pid):
        return False
    _cancel[pid] = threading.Event()
    _threads[pid] = threading.Thread(target=_run, args=(pid, stage), daemon=True, name=f"stickman-{pid}")
    _threads[pid].start()
    return True


def cancel(pid: str) -> None:
    if pid in _cancel:
        _cancel[pid].set()


def pick(pid: str, index: int) -> None:
    """Lock the project on one of the offered events: title, scope, clip count, key characters, tone."""
    p = store.load(pid)
    t = (p.get("topics") or {}).get("topics") or []
    if not 0 <= index < len(t):
        raise ValueError("no such topic")
    ev = t[index]
    clips = int(max(3, min(12, ev.get("clips") or round((ev.get("duration_s") or 60) / spec.CLIP_SECONDS))))
    def f(q: dict) -> None:
        q["project"] = {"title": ev["title"], "date_place": ev["date_place"], "premise": ev["premise"], "tone": q.get("tone") or "engaging, respectful, clear",
                        "scope": ev["conflict"], "opening_visual": ev["opening_visual"], "ending": ev["ending"]}
        n = int(q.get("clip_count") or clips) if q.get("length_set") else clips       # the length you chose wins over the idea's suggestion
        q["title"], q["clip_count"], q["seconds"], q["event"] = ev["title"], n, n * spec.CLIP_SECONDS, ev["title"]
        q["clips"], q["story"], q["roster"], q["brief"] = [], None, None, None
    store.update(pid, f)


def next_stage(p: dict) -> str:
    st = p.get("stage") or "topics"
    return STAGES[min(len(STAGES) - 1, STAGES.index(st) + 1)] if p.get("status") == "waiting" else st


def redo_clip(pid: str, n: int, what: str, note: str = "") -> bool:
    if busy(pid):
        return False
    def f(p: dict) -> None:
        c = p["clips"][n - 1]
        c["version"] = int(c.get("version", 1)) + 1
        if what == "scene":
            c["scene"] = None
    store.update(pid, f)
    def run() -> None:
        try:
            _set(pid, status="working", stage="scenes" if what == "scene" else "animate", error=None)
            if what == "scene":
                do_scenes(pid, only=n, note=note)
            do_animate(pid, only=n)
            do_finish(pid)
            _set(pid, status="done", stage="finish")
        except Exception as e:  # noqa: BLE001
            _set(pid, status="error", error=str(e)[:600])
    _cancel[pid] = threading.Event()
    _threads[pid] = threading.Thread(target=run, daemon=True, name=f"stickman-redo-{pid}")
    _threads[pid].start()
    return True


def recover() -> None:
    for row in store.listing():
        if row.get("status") == "working":
            def f(p: dict) -> None:
                p["status"], p["error"] = "error", "The studio restarted while this was running. Press Continue; finished steps are kept."
            try:
                store.update(row["id"], f)
            except Exception:  # noqa: BLE001
                pass
