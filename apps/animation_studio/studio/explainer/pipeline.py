"""The production line: plan → (you approve) → pictures → storyboard (you approve) → voice → shots → captions → final.mp4.

Runs on one background thread per project. Every step writes its files and records them, so Continue after a stop,
a crash or a restart skips what is already done. With auto=True the two approvals are skipped (idea in, video out)."""
from __future__ import annotations

import subprocess
import threading
from pathlib import Path
from typing import Any, Callable

from .. import config, models
from ..series import assemble, languages, media
from . import agents, captions, engines, memory, planner, prompts, quality, research, router, skills, spec, store

_threads: dict[str, threading.Thread] = {}
_cancel: dict[str, threading.Event] = {}
STAGES = ("plan", "design", "board", "shoot", "finish")
LABELS = {"plan": "Script and shot list", "design": "Characters and backgrounds", "board": "Storyboard", "shoot": "Voice and shots", "finish": "Captions and final video"}


class Stopped(Exception):
    pass


# ---------- helpers ----------
def sdict(p: dict) -> dict:
    """The project in the shape the shared media/crew code expects."""
    w, h = spec.ASPECTS.get(p.get("aspect") or "9:16", spec.ASPECTS["9:16"])
    return {"id": p["id"], "crew": p.get("crew") or "builtin", "language": p.get("language") or "en", "format": {"width": w, "height": h},
            "settings": {"models": p.get("models") or {}, "local_only": bool(p.get("local_only"))}, "source": p.get("source"), "research": p.get("research"), "mode": p.get("mode") or "summarize", "brief": p["brief"], "seconds": p["seconds"], "aspect": p.get("aspect") or "9:16"}


def _check(pid: str) -> None:
    ev = _cancel.get(pid)
    if ev is not None and ev.is_set():
        raise Stopped()


def _set(pid: str, **kw: Any) -> None:
    def f(p: dict) -> None:
        p.update(kw)
    store.update(pid, f)


def _save_bytes(pid: str, rel: str, data: bytes) -> str:
    path = store.pdir(pid) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return rel


def _have(pid: str, rel: str | None) -> bool:
    return bool(rel) and (store.pdir(pid) / rel).is_file()


def _read(pid: str, rel: str | None) -> bytes | None:
    return (store.pdir(pid) / rel).read_bytes() if _have(pid, rel) else None


def _shot_update(pid: str, sid: str, **kw: Any) -> None:
    def f(p: dict) -> None:
        for s in p["plan"]["shots"]:
            if s["id"] == sid:
                s.update(kw)
    store.update(pid, f)


def _log(pid: str) -> Callable[[dict], None]:
    return lambda ev: store.say(pid, ev.get("text") or ev.get("type") or "", ev.get("type") or "info") if ev.get("text") else None


# ---------- stages ----------
def do_plan(pid: str, note: str = "") -> None:
    p = store.load(pid)
    s = sdict(p)
    if p.get("research_on") and skills.on("research") and not p.get("source") and (p.get("research") or {}).get("status") != "ok":
        store.say(pid, "Checking the facts (Wikipedia)…")
        r = research.run(s, p["brief"], _log(pid))
        _set(pid, research=r)
        store.say(pid, f"Research: {len(r['facts'])} facts from {len(r['sources'])} sources." if r["status"] == "ok" else f"Research skipped: {r['reason']}")
        s = sdict(store.load(pid))
    store.say(pid, "Writing the script and shot list…")
    if note:                                                 # you asked for a change: the script prompt did not satisfy you
        prompts.record_all((p.get("plan") or {}).get("pk"), "redo", note=note)
    try:
        plan = planner.plan(s, _log(pid), note)
    except Exception as e:  # noqa: BLE001
        if type(e).__name__ == "WriterError" and "usable" in str(e):
            prompts.record("director.rules", prompts.pick("director.rules", pid)[1], "failed", ["unusable_plan"], note=str(e)[:150])
        raise
    if plan.get("pk"):                                       # judge the script by how complete its film fields are
        full = sum(1 for sh in plan["shots"] if sh.get("cam_note") and sh.get("lighting") and sh.get("audio"))
        thin = full < 0.7 * len(plan["shots"])
        prompts.record_all(plan["pk"], "flag" if thin else "ok", ["thin_plan"] if thin else [], prompt=p["brief"][:200])
    known = memory.apply(plan)                               # characters the studio built before keep their exact look and seed
    if known:
        store.say(pid, f"Cast memory: recognised {', '.join(known)}; their look is locked from earlier videos.")
    caps = engines.capabilities(s)
    router.route_all(plan["shots"], caps)
    _set(pid, plan=plan, title=plan["title"], caps=caps)
    store.say(pid, f"Plan ready: {len(plan['shots'])} shots, {spec.total_seconds(plan)} s.")


def _sheet_prompt(c: dict, style: str, pid: str = "") -> tuple[str, list]:
    text, v = prompts.pick("sheet.character", pid)
    return text.replace("{name}", c["name"]).replace("{look}", c["look"]).replace("{style}", style), [["sheet.character", v]]


def do_design(pid: str) -> None:
    p = store.load(pid)
    s = sdict(p)
    style = engines.look(p)
    W, H = s["format"]["width"], s["format"]["height"]
    a = p.setdefault("assets", {})
    todo: list[tuple[str, str, str, int, int, list]] = []
    for c in p["plan"]["characters"]:
        if _from_memory(pid, c):
            continue
        rp, rv = prompts.pick("portrait.identity", pid)
        todo.append((f"ref:{c['id']}", f"assets/ref_{c['id']}.png", rp.replace("{name}", c["name"]).replace("{look}", c["look"]).replace("{style}", style),
                     768, 1152, [["portrait.identity", rv]]))
        sp, su = _sheet_prompt(c, style, pid)
        todo.append((f"char:{c['id']}", f"assets/char_{c['id']}.png", sp, 1280, 720, su))
    for x in p["plan"]["props"]:
        todo.append((f"prop:{x['id']}", f"assets/prop_{x['id']}.png",
                     f"{x['name']}: {x['look']}. Product-style render on a plain light background, three-quarter view, soft shadow. {style}. No text.", 768, 768, []))
    w = p["plan"]["world"]
    todo.append(("world", "assets/world.png", f"Empty set, no people: {w['look']}. Wide establishing view with a clear table or floor in the foreground. {style}. No text.", W, H, []))
    todo.append(("poster", "assets/poster.png", engines.poster_prompt(p), W, H, [["poster.tail", prompts.pick("poster.tail", pid)[1]]]))
    for key, rel, prompt, pw, ph, used in todo:
        _check(pid)
        if _have(pid, (store.load(pid).get("assets") or {}).get(key)):
            continue
        store.say(pid, f"Drawing {key.split(':')[-1]}…")
        cur = store.load(pid)
        ver, note = int((cur.get("asset_ver") or {}).get(key, 0)), (cur.get("asset_note") or {}).get(key) or ""
        if note:
            prompt = f"{prompt} {note}"
        try:
            cid = key.split(":", 1)[1] if key.startswith(("char:", "ref:")) else None
            cc = next((c for c in p["plan"]["characters"] if c["id"] == cid), None)
            base = media.seed_of(pid, "char:" + cid) if cc else media.seed_of(pid, key)
            sd = media.seed_of(pid, key, ver) if ver else (memory.seed(cc, base) if cc else base)   # one face seed per character
            refs_for = []                                      # the sheet and the key visual are drawn FROM the identity portrait
            if key.startswith("char:") and cc:
                refs_for = [b for b in [_read(pid, (store.load(pid).get("assets") or {}).get(f"ref:{cid}"))] if b]
            elif key == "poster":
                cur_a = store.load(pid).get("assets") or {}
                refs_for = [b for b in [_read(pid, cur_a.get(f"ref:{c['id']}")) for c in p["plan"]["characters"][:2]] + [_read(pid, cur_a.get("world"))] if b]
            if refs_for:
                data, info0 = media.picture(prompt, refs_for, pw, ph, sd, f"{pid}:{key}", s=s)
                mid = info0.get("model")
            else:
                data, mid = media._t2i(prompt, pw, ph, sd, s=s)
        except Exception as e:  # noqa: BLE001
            if prompts.is_prompt_fault(str(e)):
                prompts.record_all(used, "failed", ["refused"], prompt, str(e)[:150])
            raise
        flags = [f for f in quality.check(data)["flags"] if f != "duplicate"]
        prompts.record_all(used, "flag" if flags else "ok", flags, prompt)
        skills.tick("characters" if key.startswith("char:") else "backgrounds", not flags, ",".join(flags))
        _save_bytes(pid, rel, data)
        def f(q: dict, key=key, rel=rel, mid=mid, used=used, flags=flags) -> None:
            q.setdefault("assets", {})[key] = rel
            q.setdefault("models_used", {})[key] = mid
            q.setdefault("asset_pk", {})[key] = used
            q.setdefault("asset_flags", {})[key] = flags
        store.update(pid, f)
    if store.load(pid).get("auto"):                          # nobody approves in automatic mode: remember what was made
        _remember_cast(pid, approved=False)


def _from_memory(pid: str, c: dict) -> bool:
    """A remembered character is copied in, not redrawn: same face, video after video."""
    m = memory.get(c.get("memory") or "") if c.get("memory") else None
    if not m or m.get("look") != c["look"]:
        return False
    cur = store.load(pid).get("assets") or {}
    if _have(pid, cur.get(f"char:{c['id']}")) and _have(pid, cur.get(f"ref:{c['id']}")):
        return True
    portrait, sheet = memory.read(m["id"], m.get("portrait")), memory.read(m["id"], m.get("sheet"))
    if not (portrait and sheet):
        return False
    r1 = _save_bytes(pid, f"assets/ref_{c['id']}.png", portrait)
    r2 = _save_bytes(pid, f"assets/char_{c['id']}.png", sheet)
    def f(q: dict) -> None:
        q.setdefault("assets", {}).update({f"ref:{c['id']}": r1, f"char:{c['id']}": r2})
        q.setdefault("models_used", {})[f"char:{c['id']}"] = "cast memory"
    store.update(pid, f)
    store.say(pid, f"{c['name']} comes from cast memory (not redrawn).")
    return True


def _remember_cast(pid: str, approved: bool) -> None:
    """Save every character's look, seed, portrait and sheet in cast memory (never stops the video)."""
    try:
        p = store.load(pid)
        a = p.get("assets") or {}
        for c in p["plan"]["characters"]:
            m = memory.remember(pid, c, _read(pid, a.get(f"ref:{c['id']}")), _read(pid, a.get(f"char:{c['id']}")),
                                memory.seed(c, media.seed_of(pid, "char:" + c["id"])), approved)
            def f(q: dict, cid=c["id"], mid=m["id"]) -> None:
                for cc in q["plan"]["characters"]:
                    if cc["id"] == cid:
                        cc["memory"] = mid
            store.update(pid, f)
    except Exception as e:  # noqa: BLE001
        store.say(pid, f"Cast memory skipped: {str(e)[:120]}", "warn")


def _refs(pid: str, shot: dict, assets: dict) -> list[bytes]:
    """References a picture model looks at, one clear thing each (the cleanest first): each character's identity portrait
    (its design sheet only when there is no portrait), the main prop, then the empty set."""
    out = []
    for c in shot["characters"][:2]:
        d = _read(pid, assets.get(f"ref:{c}")) or _read(pid, assets.get(f"char:{c}"))
        if d:
            out.append(d)
    for x in shot["props"][:1]:
        d = _read(pid, assets.get(f"prop:{x}"))
        if d:
            out.append(d)
    w = _read(pid, assets.get("world"))
    if w and len(out) < 4:
        out.append(w)
    return out


def do_board(pid: str, only: str | None = None, note: str = "") -> None:
    p = store.load(pid)
    s = sdict(p)
    W, H = s["format"]["width"], s["format"]["height"]
    ref_ok = media.refs_supported(s)
    if not ref_ok and not only:
        store.say(pid, "No picture model here can look at the character portrait, so each shot is drawn from words alone and faces may drift. "
                       "Free fix: add your Cloudflare account ID and API token in Settings (FLUX.2 klein then draws every shot FROM the portrait). "
                       "Or use Qwen-Image-Edit on a GPU worker.")
    for shot in p["plan"]["shots"]:
        if only and shot["id"] != only:
            continue
        _check(pid)
        if not only and _have(pid, shot.get("frame")):
            continue
        store.say(pid, f"Storyboard {shot['id']}…")
        built, used = engines.shot_prompt_used(p, shot)
        custom = bool(shot.get("prompt_custom"))             # your own wording is yours: the library does not learn from it
        used = [] if custom else used
        prompt = (shot.get("prompt_custom") or built) + (f". Change: {note}" if note else "")
        refs = _refs(pid, shot, p.get("assets") or {})
        lead = next((c for c in p["plan"]["characters"] if shot["characters"] and c["id"] == shot["characters"][0]), None)
        seed = (memory.seed(lead, media.seed_of(pid, "char:" + lead["id"])) + (shot.get("version", 1) - 1 if only else 0)) if lead and not ref_ok \
            else media.seed_of(pid, shot["id"], shot.get("version", 1))
        try:
            data, info = media.picture(prompt, refs, W, H, seed, f"{pid}:{shot['id']}", s=s, negative=engines.negative(p))
        except Exception as e:  # noqa: BLE001
            if prompts.is_prompt_fault(str(e)):
                prompts.record_all(used, "failed", ["refused"], prompt, str(e)[:150])
            raise
        portrait = _read(pid, (p.get("assets") or {}).get(f"ref:{lead['id']}")) if lead else None
        chk = memory.check(s, portrait, data, lead["name"], _log(pid)) if lead and portrait else None
        if chk is not None:
            _set(pid, vision_check=True)
        extra: list[str] = []
        if chk and not chk.get("same"):                       # drifted: one more try, told exactly what to fix
            store.say(pid, f"{shot['id']}: {lead['name']} did not match the portrait ({chk.get('differences') or 'different look'}); drawing again.", "warn")
            data, info = media.picture(f"{prompt}. Fix: {chk.get('fix') or lead['look']}", refs, W, H, seed + 7, f"{pid}:{shot['id']}:fix", s=s, negative=engines.negative(p))
            chk2 = memory.check(s, portrait, data, lead["name"], _log(pid))
            if chk2 and not chk2.get("same"):
                extra.append("off_model")
            chk = {**(chk2 or chk), "redrawn": True}
        others = [q["qhash"] for q in store.load(pid)["plan"]["shots"] if q["id"] != shot["id"] and q.get("qhash") is not None]
        qc = quality.check(data, others)
        qc["flags"] = [*qc["flags"], *extra]
        prompts.record_all(used, "flag" if qc["flags"] else "ok", qc["flags"], prompt)
        skills.tick("storyboard", not qc["flags"], ",".join(qc["flags"]))
        rel = _save_bytes(pid, f"shots/{shot['id']}/frame_v{shot.get('version', 1)}.png", data)
        _shot_update(pid, shot["id"], frame=rel, frame_model=info.get("model"), prompt=prompt, pk=used, qc=qc["flags"], qhash=qc["hash"], rating=None,
                     continuity_check=chk, end_frame=None)
        if skills.on("keyframes") and not custom and shot["shot_type"] != "establishing":
            _check(pid)
            store.say(pid, f"Last frame {shot['id']}…")
            ep, eu = engines.end_prompt(p, shot)
            try:
                end_refs = [*refs[:3], data]                    # the portraits / prop first, then this shot's first frame
                end, _ = media.picture(f"The last image is this shot's first frame: keep its camera, framing, set and light; change only the pose and the result of the action. {ep}"
                                       + (f". Change: {note}" if note else ""), end_refs, W, H, seed, f"{pid}:{shot['id']}:end", s=s, negative=engines.negative(p))
                erel = _save_bytes(pid, f"shots/{shot['id']}/end_v{shot.get('version', 1)}.png", end)
                eq = quality.check(end, [qc["hash"]])
                prompts.record_all(eu, "flag" if [x for x in eq["flags"] if x != "duplicate"] else "ok", [x for x in eq["flags"] if x != "duplicate"], ep)
                skills.tick("keyframes", True)
                _shot_update(pid, shot["id"], end_frame=erel)
            except Exception as e:  # noqa: BLE001 - the last frame is a bonus; the shot keeps its first frame
                skills.tick("keyframes", False, str(e))
                store.say(pid, f"Last frame {shot['id']} skipped: {str(e)[:120]}", "warn")
    _contact(pid)
    q = store.load(pid)
    if q["plan"]["shots"] and not q.get("thumb"):
        _set(pid, thumb=q["plan"]["shots"][0].get("frame"))


def rebuild_sheet(pid: str) -> None:
    """Draw the production storyboard sheet again from the pictures already made."""
    _contact(pid)


def _contact(pid: str) -> None:
    """The numbered overview of the whole storyboard (never lets a failure here stop the video)."""
    try:
        from . import contactsheet
        p = store.load(pid)
        frames = [(sh["id"], _read(pid, sh.get("frame"))) for sh in p["plan"]["shots"]]
        data = contactsheet.build(frames, p.get("title") or "Storyboard")
        _set(pid, contact=_save_bytes(pid, "storyboard.png", data))
        a = p.get("assets") or {}
        board = contactsheet.board(p["plan"], frames=[_read(pid, sh.get("frame")) for sh in p["plan"]["shots"]], poster=_read(pid, a.get("poster")),
                                   sheets=[_read(pid, a.get(f"char:{c['id']}")) for c in p["plan"]["characters"]], world=_read(pid, a.get("world")),
                                   props=[_read(pid, a.get(f"prop:{x['id']}")) for x in p["plan"]["props"]], aspect=p.get("aspect") or "9:16")
        _set(pid, board=_save_bytes(pid, "board.png", board), board_error=None)
        from . import boards
        q = store.load(pid)
        lv = boards.build_all(q, lambda rel: _read(pid, rel), lambda rel, b: _save_bytes(pid, rel, b),
                              lambda sh: engines.animation_prompt(q, sh), {c["id"] for c in q["plan"]["characters"] if c.get("memory")})
        _set(pid, boards=lv)
    except Exception as e:  # noqa: BLE001
        store.say(pid, f"Storyboard overview skipped: {str(e)[:120]}")
        try:
            _set(pid, board_error=f"{type(e).__name__}: {str(e)[:160]}")
        except Exception:  # noqa: BLE001
            pass


def _voice(s: dict, text: str, p: dict) -> tuple[bytes, dict]:
    chosen = p.get("voice_id")
    if chosen:                                   # the voice you picked (kept exactly; no other voice is used)
        try:
            return media.edge_say(text, {"edge": chosen, "pitch": "+0Hz", "rate": "+0%"}, "neutral"), {"model": "edge-tts", "voice": chosen, "fallback": False}
        except Exception as e:  # noqa: BLE001
            return media.silence(max(1.5, spec.speak_seconds(text))), {"model": "silence", "voice": chosen, "fallback": True,
                                                                      "note": f"Your voice {chosen} could not speak (needs internet): {str(e)[:120]}"}
    lg = languages.get(s["language"])
    pool = (lg.edge_female if p.get("voice") == "female" else lg.edge_male) or lg.edge_male
    try:
        return media.edge_say(text, {"edge": pool[0], "pitch": "+0Hz", "rate": "+0%"}, "neutral"), {"model": "edge-tts", "fallback": False}
    except Exception as e:  # noqa: BLE001 - offline or edge-tts missing: silent shot, captions still show the words
        return media.silence(max(1.5, spec.speak_seconds(text))), {"model": "silence", "fallback": True, "note": str(e)[:160]}


def _speaker(p: dict, shot: dict) -> tuple[dict, int] | None:
    """The character who says this shot's line (None: the narrator does), with their index."""
    sid = shot.get("speaker")
    if not sid or not skills.on("dialog"):
        return None
    for i, c in enumerate(p["plan"]["characters"]):
        if c["id"] == sid:
            return c, i
    return None


def _speaker_voice(s: dict, p: dict, text: str, c: dict, i: int, emotion: str) -> tuple[bytes, dict]:
    """A character's own voice: the presenter keeps the voice you picked; the others get a distinct Edge voice."""
    if i == 0:
        return _voice(s, text, p)
    ev = media.edge_voice(s, {"gender": "female" if "female" in str(c.get("voice") or "").lower() or "she" in str(c.get("look") or "").lower().split() else "male",
                              "age": ""}, i)
    try:
        return media.edge_say(text, ev, emotion or "neutral"), {"model": "edge-tts", "voice": ev["edge"], "fallback": False, "speaker": c["id"]}
    except Exception as e:  # noqa: BLE001
        return media.silence(max(1.5, spec.speak_seconds(text))), {"model": "silence", "fallback": True, "note": str(e)[:160], "speaker": c["id"]}


def do_shoot(pid: str, only: str | None = None) -> None:
    p = store.load(pid)
    s = sdict(p)
    caps = engines.capabilities(s)
    for shot in p["plan"]["shots"]:
        if only and shot["id"] != only:
            continue
        _check(pid)
        sid, d = shot["id"], store.pdir(pid) / "shots" / shot["id"]
        d.mkdir(parents=True, exist_ok=True)
        line = d / "line.wav"
        if shot["narration"] and (only or not line.is_file()):
            store.say(pid, f"Voice {sid}…")
            who = _speaker(p, shot)
            wav, vinfo = _speaker_voice(s, p, shot["narration"], who[0], who[1], shot.get("emotion") or "") if who else _voice(s, shot["narration"], p)
            skills.tick("dialog" if who else "voice", not vinfo.get("fallback"), vinfo.get("note", ""))
            line.write_bytes(wav)
            secs = round(min(10.0, max(shot["seconds"], media.wav_seconds(wav) + 0.35)), 2)
            _shot_update(pid, sid, seconds=secs, voice=vinfo)
            shot["seconds"] = secs
        clip = d / f"clip_v{shot.get('version', 1)}.mp4"
        if clip.is_file() and not only:
            continue
        shot["engine"], shot["engine_why"] = router.route(shot, caps)
        key = _read(pid, shot.get("frame"))
        if key is None:
            raise RuntimeError(f"{sid} has no storyboard picture yet")
        shot["_end"] = _read(pid, shot.get("end_frame"))      # the last frame: a key-pose animatic when no video model is ready
        store.say(pid, f"Shot {sid} with {shot['engine'].replace('_', ' ')}…")
        seed = media.seed_of(pid, sid, shot.get("version", 1), "clip")
        mk: list = []
        data = info = None
        if shot["engine"] == "lipsync":
            if not (skills.on("lipsync") and shot.get("speaker") and line.is_file()):
                shot["engine"] = "ai_video" if caps["ai_video"] else "still"
            else:
                try:
                    data, info = engines.lipsync(s, shot, key, line.read_bytes(), shot["seconds"], seed, f"{pid}:{sid}", shot.get("anim_custom") or engines.animation_prompt(p, shot))
                    skills.tick("lipsync", True)
                except Exception as e:  # noqa: BLE001 - the shot is still made, with normal video
                    skills.tick("lipsync", False, str(e))
                    store.say(pid, f"Lip-sync for {sid} did not work ({str(e)[:140]}); using normal video.", "warn")
                    shot["engine"] = "ai_video" if caps["ai_video"] else "still"
        if data is not None:
            pass
        elif shot["engine"] == "ai_video":
            mk = [] if shot.get("anim_custom") else [["motion.keep", prompts.pick("motion.keep", pid)[1]]]
            try:
                data, info = engines.ai_video(s, shot, key, shot["seconds"], seed, shot.get("anim_custom") or engines.animation_prompt(p, shot), f"{pid}:{sid}")
            except Exception as e:  # noqa: BLE001
                if prompts.is_prompt_fault(str(e)):
                    prompts.record_all(mk, "failed", ["refused"], note=str(e)[:150])
                raise
            if not info.get("fallback"):
                prompts.record_all(mk, "ok")
            skills.tick("motion", not info.get("fallback"), str(info.get("note") or ""))
        elif shot["engine"] == "blender":
            data, info = engines.blender(s, p, shot, key, shot["seconds"])
        else:
            data, info = engines.still(s, shot, key, shot["seconds"], "", shot.get("_end"))
        shot.pop("_end", None)
        clip.write_bytes(data)
        _shot_update(pid, sid, clip=store.rel(pid, clip), mk=mk, engine=info.get("engine", shot["engine"]), engine_why=shot["engine_why"],
                     info={k: v for k, v in info.items() if k != "scene"}, status="fallback" if info.get("fallback") else "done")


def _ff(args: list[str], cwd: Path | None = None) -> None:
    r = subprocess.run([config.ffmpeg(), "-y", "-v", "error", *args], capture_output=True, text=True, cwd=cwd)
    if r.returncode:
        raise RuntimeError("ffmpeg: " + (r.stderr or "")[-400:])


def do_finish(pid: str) -> None:
    p = store.load(pid)
    s = sdict(p)
    W, H = s["format"]["width"], s["format"]["height"]
    d = store.pdir(pid)
    work = d / "work"
    work.mkdir(exist_ok=True)
    rows: list[tuple[float, float, str]] = []
    parts, at = [], 0.0
    for shot in p["plan"]["shots"]:
        _check(pid)
        clip = d / (shot.get("clip") or "")
        if not clip.is_file():
            raise RuntimeError(f"{shot['id']} has no clip yet")
        sec = float(shot["seconds"])
        fit = assemble.fit_shot(clip, work / f"{shot['id']}_fit.mp4", sec, W, H)
        line = d / "shots" / shot["id"] / "line.wav"
        aud = assemble.shot_audio(work / f"{shot['id']}_a.wav", sec, line if line.is_file() else None, None)
        parts.append({"video": fit, "audio": aud, "seconds": sec})
        rows += captions.chunks(shot["narration"], at + 0.12, at + max(0.6, sec - 0.1))
        at += sec
    store.say(pid, "Mixing music and joining the shots…")
    music, mpath = None, None
    keep = d / "music_keep.wav"
    try:
        if not skills.on("music"):
            music = None
        elif keep.is_file() and media.probe_seconds(keep) >= at - 0.3:       # the music you already heard is reused, never regenerated
            music = keep.read_bytes()
            store.say(pid, "Reusing the music from before.")
        else:
            music, _ = media.music(s, p["plan"].get("music") or "", at, f"{pid}:music")
            if music:
                keep.write_bytes(media.to_wav(music))
            skills.tick("music", bool(music), "no music came back")
    except Exception as e:  # noqa: BLE001 - music is optional
        skills.tick("music", False, str(e))
        store.say(pid, f"No music this time ({str(e)[:120]})", "warn")
    if music:
        mpath = work / "music.wav"
        mpath.write_bytes(media.to_wav(music))
    joined = assemble.part(parts, work, work / "joined.mp4", W, H, mpath, [(a, b, t) for a, b, t in rows])
    (work / "captions.ass").write_text(captions.ass(rows, W, H), "utf-8")
    store.say(pid, "Burning in the captions…")
    out = d / "final.mp4"
    _ff(["-i", str(joined.resolve()), "-vf", "ass=captions.ass", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
         "-c:a", "copy", "-movflags", "+faststart", str(out.resolve())], cwd=work)
    (d / "final.srt").write_text(assemble.srt(rows), "utf-8")
    skills.tick("finish", True)
    _set(pid, final=store.rel(pid, out), finalSeconds=round(at, 1))


RUN = {"plan": do_plan, "design": do_design, "board": do_board, "shoot": do_shoot, "finish": do_finish}


# ---------- the runner ----------
def busy(pid: str) -> bool:
    t = _threads.get(pid)
    return bool(t and t.is_alive())


def _gate(p: dict, stage: str) -> bool:
    """Does the line stop after this stage for your approval?"""
    return not p.get("auto") and stage in ("plan", "design", "board")


def _run(pid: str, start: str, note: str = "") -> None:
    try:
        i = STAGES.index(start)
        while i < len(STAGES):
            st = STAGES[i]
            _set(pid, status="working", stage=st, error=None)
            _check(pid)
            RUN[st](pid, note) if st == "plan" else RUN[st](pid)
            note = ""
            if _gate(store.load(pid), st):
                _set(pid, status="waiting", stage=st)
                store.say(pid, f"{LABELS[st]} is ready for your approval.")
                return
            i += 1
        _set(pid, status="done", stage="finish")
        store.say(pid, "Your video is ready.")
        learn(pid)
    except Stopped:
        _set(pid, status="stopped")
        store.say(pid, "Stopped.", "warn")
    except Exception as e:  # noqa: BLE001 - say it, keep the work; Continue picks up where it stopped
        _set(pid, status="error", error=str(e)[:600])
        store.say(pid, f"Stopped at {LABELS.get(store.load(pid).get('stage'), '')}: {str(e)[:300]}", "error")


def start(pid: str, stage: str = "plan", note: str = "") -> bool:
    if busy(pid):
        return False
    _cancel[pid] = threading.Event()
    t = threading.Thread(target=_run, args=(pid, stage, note), daemon=True, name=f"explainer-{pid}")
    _threads[pid] = t
    t.start()
    return True


def cancel(pid: str) -> None:
    if pid in _cancel:
        _cancel[pid].set()


def next_stage(p: dict) -> str:
    """Where Continue / Approve goes next."""
    st = p.get("stage") or "plan"
    if p.get("status") == "waiting":
        return STAGES[min(len(STAGES) - 1, STAGES.index(st) + 1)]
    return st


def on_approve(pid: str) -> None:
    """Your OK is the strongest signal short of a rating: what you let through counts as good for the prompts that made it."""
    p = store.load(pid)
    if p.get("status") != "waiting":
        return
    if p.get("stage") == "design":
        for key, used in (p.get("asset_pk") or {}).items():
            if key in (p.get("asset_ok") or []) or key in (p.get("asset_flags") or {}) and (p.get("asset_flags") or {}).get(key):
                continue
            prompts.record_all(used, "up")
        _set(pid, asset_ok=sorted((p.get("asset_pk") or {}).keys()))
        _remember_cast(pid, approved=True)
    elif p.get("stage") == "board":
        done = set(p.get("approved_shots") or [])
        for sh in p["plan"]["shots"]:
            if sh["id"] not in done and not sh.get("rating") and not sh.get("qc") and sh.get("pk"):
                prompts.record_all(sh["pk"], "up")
                done.add(sh["id"])
        _set(pid, approved_shots=sorted(done))
        try:                                                   # approved frames with one character become more references for it
            q = store.load(pid)
            for sh in q["plan"]["shots"]:
                cs = [c for c in q["plan"]["characters"] if c["id"] in sh["characters"]]
                if len(cs) == 1 and cs[0].get("memory") and sh.get("frame") and "off_model" not in (sh.get("qc") or []):
                    memory.add_frame(cs[0]["memory"], _read(pid, sh["frame"]) or b"", f"{pid}-{sh['id']}")
        except Exception:  # noqa: BLE001
            pass


def redo_asset(pid: str, key: str, note: str = "") -> bool:
    """Draw one character, prop, the set or the poster again. The prompts that made the old picture are told you did not accept it."""
    if busy(pid):
        return False
    p = store.load(pid)
    if key not in (p.get("assets") or {}):
        return False
    prompts.record_all((p.get("asset_pk") or {}).get(key), "redo", note=note)
    def f(q: dict) -> None:
        q["assets"].pop(key, None)
        if key.startswith("char:"):
            q["assets"].pop("ref:" + key[5:], None)
            for c in q["plan"]["characters"]:
                if c["id"] == key[5:]:
                    c.pop("memory", None)            # a redraw is a new design; approving it updates the memory
        q.setdefault("asset_ver", {})[key] = int((q.get("asset_ver") or {}).get(key, 0)) + 1
        q.setdefault("asset_note", {})[key] = " ".join(str(note).split())[:300] if note else ""
        q["asset_ok"] = [k for k in (q.get("asset_ok") or []) if k != key]
        if key.startswith("char:") or key == "world" or key == "poster":
            q["board"] = None
    store.update(pid, f)
    return start(pid, "design")


def reset_look(pid: str, note: str) -> None:
    """A new visual direction for the whole video: pictures and clips are drawn again; the script, voice lines and music are kept."""
    def f(p: dict) -> None:
        p["style"] = f"{note.strip()}"[:300]
        p["assets"] = {}
        p["final"] = None
        p["thumb"] = None
        p["contact"] = None
        p["board"] = None
        for s in (p.get("plan") or {}).get("shots", []):
            s["version"] = int(s.get("version", 1)) + 1
            s["frame"] = None
            s["end_frame"] = None
            s["clip"] = None
            s["status"] = "pending"
    store.update(pid, f)


def restyle(pid: str, note: str) -> bool:
    if busy(pid):
        return False
    reset_look(pid, note)
    return start(pid, "design")


def redo_shot(pid: str, sid: str, what: str, note: str = "", prompt: str | None = None, anim: str | None = None) -> bool:
    """One shot again: its picture (then its clip) or just its clip."""
    if busy(pid):
        return False
    before = next((x for x in store.load(pid)["plan"]["shots"] if x["id"] == sid), {})
    if what == "picture" and prompt is None:                  # you asked for a new picture: the prompts behind the old one did not satisfy you
        prompts.record_all(before.get("pk"), "redo", note=note)
    elif what == "clip" and anim is None:
        prompts.record_all(before.get("mk"), "redo", note=note)
    def f(p: dict) -> None:
        for s in p["plan"]["shots"]:
            if s["id"] == sid:
                s["version"] = int(s.get("version", 1)) + 1
                s["status"] = "pending"
                if prompt is not None:
                    s["prompt_custom"] = prompt.strip()[:1800] or None
                if anim is not None:
                    s["anim_custom"] = anim.strip()[:1500] or None
                if what == "picture":
                    s["frame"] = None
                    s["end_frame"] = None
    store.update(pid, f)
    def run() -> None:
        try:
            _set(pid, status="working", stage="shoot", error=None)
            if what == "picture":
                do_board(pid, only=sid, note=note)
            do_shoot(pid, only=sid)
            do_finish(pid)
            _set(pid, status="done", stage="finish")
        except Exception as e:  # noqa: BLE001
            _set(pid, status="error", error=str(e)[:600])
    _cancel[pid] = threading.Event()
    _threads[pid] = threading.Thread(target=run, daemon=True, name=f"explainer-redo-{pid}")
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


def learn(pid: str | None = None) -> list[str]:
    """One pass of the prompt library's learning (never breaks a project)."""
    try:
        s = sdict(store.load(pid)) if pid else None
        msgs = prompts.learn(s, _log(pid) if pid else None)
        for m in msgs:
            if pid:
                store.say(pid, "Prompt library: " + m)
        return msgs
    except Exception as e:  # noqa: BLE001
        if pid:
            store.say(pid, f"Prompt library skipped: {str(e)[:120]}", "warn")
        return []


def rate_shot(pid: str, sid: str, up: bool, note: str = "") -> bool:
    """Your 👍 / 👎 on a shot's picture: the strongest signal the library gets. One rating per picture."""
    done: dict = {}
    def f(p: dict) -> None:
        for s in p["plan"]["shots"]:
            if s["id"] == sid and not s.get("rating"):
                s["rating"] = "up" if up else "down"
                done["pk"] = s.get("pk")
                done["prompt"] = s.get("prompt", "")
    store.update(pid, f)
    if "pk" not in done:
        return False
    prompts.record_all(done["pk"], "up" if up else "down", prompt=done["prompt"], note=note)
    learn(pid)
    return True


# ---------- real motion from any video website: the shot pack out, your clips back in ----------
PACK_README = """AVOS shot pack: {title}

Make each shot move with any image-to-video tool (Kling, Runway, OpenArt, Luma, Pika, Hailuo, Veo...):

  1. Open the tool's image-to-video mode.
  2. Upload  first.png  as the start frame. If the tool has an end frame (Kling "Start & End frame", Runway, Luma),
     upload  last.png  as the end frame so the action finishes where the storyboard says.
  3. Paste  motion.txt  as the prompt. Set the length to the seconds in  shot.txt  and the shape to {aspect}.
  4. Download the clip and, on the shot in AVOS, press "Use my clip" and pick the file.

Or make the whole film at once: paste  master_prompt*.txt  into a multi-shot model (Seedance on Higgsfield or Lovart,
Kling, Picsart Cartoon Director), one part per generation, with the character portraits as references.

When every shot has a clip, AVOS joins them with the voice, music and captions into the final video.
The character portraits in characters/ help tools that accept a character or subject reference.
"""


def shot_pack(pid: str) -> bytes:
    """A zip with, per shot, the first and last frame, the motion prompt, the picture prompt, the timing and the voice line."""
    import io
    import zipfile
    p = store.load(pid)
    if not p.get("plan"):
        raise ValueError("There is no script yet.")
    buf = io.BytesIO()
    a = p.get("assets") or {}
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("README.txt", PACK_README.format(title=p.get("title") or "video", aspect=p.get("aspect") or "9:16"))
        from . import master
        mp = master.parts(p)
        for i, part in enumerate(mp):                       # the whole film as one prompt per generation (Seedance, Kling, Lovart, Picsart)
            z.writestr(f"master_prompt_part_{i + 1}.txt" if len(mp) > 1 else "master_prompt.txt", part)
        for c in p["plan"]["characters"]:
            for key, name in ((f"ref:{c['id']}", "portrait"), (f"char:{c['id']}", "sheet")):
                b = _read(pid, a.get(key))
                if b:
                    z.writestr(f"characters/{spec.slug(c['name'])}_{name}.png", b)
        t = 0.0
        for sh in p["plan"]["shots"]:
            d = f"{sh['id']}_{spec.slug(sh.get('scene_title') or sh['shot_type'])}"
            for rel, name in ((sh.get("frame"), "first.png"), (sh.get("end_frame"), "last.png")):
                b = _read(pid, rel)
                if b:
                    z.writestr(f"{d}/{name}", b)
            z.writestr(f"{d}/motion.txt", sh.get("anim_custom") or engines.motion_prompt(engines.animation_prompt(p, sh), sh["camera"]["movement"].replace("_", " ")))
            z.writestr(f"{d}/picture_prompt.txt", sh.get("prompt_custom") or engines.shot_prompt(p, sh))
            end = t + float(sh["seconds"])
            z.writestr(f"{d}/shot.txt", f"{sh['id']}  {t:.1f}s to {end:.1f}s  ({float(sh['seconds']):.1f} seconds)\nShape: {p.get('aspect')}\nLine: {sh.get('narration') or '-'}\n"
                                        f"Camera: {sh.get('cam_note') or sh['camera']['movement']}\nEnds on: {sh.get('end_state') or '-'}\n")
            t = end
            line = store.pdir(pid) / "shots" / sh["id"] / "line.wav"
            if line.is_file():
                z.write(line, f"{d}/line.wav")
    return buf.getvalue()


def use_clip(pid: str, sid: str, data: bytes) -> dict:
    """Your own clip for one shot (made on any video website). It replaces the shot's clip; the final is rebuilt when all shots have one."""
    if busy(pid):
        raise RuntimeError("Busy; wait for the current step to finish.")
    if len(data) < 2000:
        raise ValueError("That file is empty.")
    p = store.load(pid)
    shot = next((s for s in (p.get("plan") or {}).get("shots", []) if s["id"] == sid), None)
    if not shot:
        raise KeyError(sid)
    d = store.pdir(pid) / "shots" / sid
    d.mkdir(parents=True, exist_ok=True)
    raw = d / "upload_raw"
    raw.write_bytes(data)
    v = int(shot.get("version", 1)) + 1
    out = d / f"clip_v{v}_yours.mp4"
    W, H = spec.ASPECTS.get(p.get("aspect") or "9:16", spec.ASPECTS["9:16"])
    try:                                                  # any format in, the shot's size out (no sound: voice and music are added at the finish)
        _ff(["-i", str(raw), "-an", "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps=24,format=yuv420p",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", str(out)])
    finally:
        raw.unlink(missing_ok=True)
    secs = media.probe_seconds(out)
    _shot_update(pid, sid, clip=store.rel(pid, out), version=v, engine="upload", engine_why="your clip",
                 info={"engine": "upload", "model": "your clip", "fallback": False, "note": f"your clip ({secs:.1f} s)"}, status="done")
    store.say(pid, f"{sid}: using your clip ({secs:.1f} s).")
    q = store.load(pid)
    if all(store.file_path(pid, s.get("clip") or "") for s in q["plan"]["shots"]):
        refinish(pid)
    return q


def refinish(pid: str) -> bool:
    """Join the shots again (after clips were replaced) with the voice, music and captions."""
    if busy(pid):
        return False
    def run() -> None:
        try:
            _set(pid, status="working", stage="finish", error=None)
            store.say(pid, "Joining the shots again with your clips…")
            do_finish(pid)
            _set(pid, status="done", stage="finish")
            store.say(pid, "Your video is ready.")
        except Exception as e:  # noqa: BLE001
            _set(pid, status="error", error=str(e)[:600])
    _cancel[pid] = threading.Event()
    _threads[pid] = threading.Thread(target=run, daemon=True, name=f"explainer-finish-{pid}")
    _threads[pid].start()
    return True
