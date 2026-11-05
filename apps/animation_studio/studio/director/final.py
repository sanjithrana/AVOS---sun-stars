"""Assembly (transitions, music, narration, sfx), the final critic (cross-shot only) and revisions with before/after proof."""
from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from .. import config
from ..render import scene
from ..render.shot import crop
from .build import HANDLE, ctx_for, load_spec, metrics, render_shot_files, save_spec, spec_json_for_prompt
from .common import P, load_cast, shot_at, shot_times, short
from .pre import ENUMS
from .prod import apply_shot_fix, measure_shot

XFADE = {"fade": "fade", "dissolve": "fade", "wipe": "wipeleft", "wipeleft": "wipeleft", "wiperight": "wiperight", "slide": "slideleft",
         "circle": "circleopen", "zoom": "zoomin", "whip": "smoothleft", "pixelize": "pixelize", "flash": "fadewhite", "smash": "fade"}
VOICES = {"en": "en-US-AnaNeural", "zh-TW": "zh-TW-HsiaoChenNeural", "zh-CN": "zh-CN-XiaoxiaoNeural"}


def _probe_dur(f: Path) -> float:
    try:
        r = subprocess.run([config.ffprobe(), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)], capture_output=True, text=True, timeout=60)
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def _run(cmd: list[str]) -> tuple[int, str]:
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, r.stderr[-800:]


async def _tts(text: str, lang: str, out: Path) -> bool:
    try:
        import edge_tts  # type: ignore
    except Exception:
        return False
    voice = os.environ.get("STUDIO_TTS_VOICE") or VOICES.get(lang, VOICES["en"])
    if re.search(r"[一-鿿]", text) and lang == "en":
        voice = VOICES["zh-TW"]
    try:
        await edge_tts.Communicate(text, voice).save(str(out))
        return out.exists() and out.stat().st_size > 1000
    except Exception:
        return False


def _concat(p: P, plan: dict, out: Path) -> tuple[bool, str]:
    shots = plan.get("shots") or []
    files, durs, trans = [], [], []
    for s in shots:
        f = p.dir / "build" / "shots" / f"{s['id']}.mp4"
        if not f.exists():
            return False, f"missing build/shots/{s['id']}.mp4"
        spec = p.read(f"build/shots/{s['id']}.json") or {}
        files.append(f)
        durs.append(max(0.4, float(s["end_s"]) - float(s["start_s"])))
        trans.append(str(spec.get("transition_in") or s.get("transition_in") or "cut"))
    if len(files) == 1:
        shutil.copyfile(files[0], out)
        return True, ""
    inputs: list[str] = []
    for f in files:
        inputs += ["-i", str(f)]
    chain, last, t = [], "[0:v]", 0.0
    for i in range(1, len(files)):
        t += durs[i - 1]
        tr = trans[i]
        name = XFADE.get(tr)
        d = HANDLE * 0.9 if name and tr != "smash" else 0.04
        name = name or "fade"
        lab = f"[v{i}]"
        chain.append(f"{last}[{i}:v]xfade=transition={name}:duration={d:.3f}:offset={t:.3f}{lab}")
        last = lab
    total = sum(durs)
    chain.append(f"{last}trim=duration={total:.3f},setpts=PTS-STARTPTS,format=yuv420p[vout]")
    code, err = _run([config.ffmpeg(), "-y", "-loglevel", "error"] + inputs + ["-filter_complex", ";".join(chain), "-map", "[vout]",
                      "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-r", str(int((plan.get("format") or {}).get("fps") or 24)), str(out)])
    return code == 0, err


async def assemble(p: P) -> dict:
    plan = p.plan()
    (p.dir / "out").mkdir(exist_ok=True)
    silent = p.dir / "build" / "assembled_silent.mp4"
    p.tool("ffmpeg", f"join {len(plan.get('shots') or [])} shots with their transitions")
    ok, err = await p.run(_concat, p, plan, silent)
    if not ok:
        return {"ok": False, "stderr": err}
    total = sum(float(s["end_s"]) - float(s["start_s"]) for s in plan.get("shots") or [])
    tracks: list[tuple[str, list[str], str]] = []   # (label, input args, filter)
    music = plan.get("music") or {}
    notes = []
    mfile = p.dir / music["file"] if music.get("file") else None
    if mfile and mfile.exists():
        sec = music.get("section") or {}
        st = float(sec.get("start_s") or 0)
        tracks.append(("music", ["-ss", f"{st:.3f}", "-t", f"{total + 0.1:.3f}", "-i", str(mfile)],
                       f"afade=t=in:d=0.08,afade=t=out:st={max(0, total - 1.8):.2f}:d=1.8,volume=1.0"))
        notes.append(p.t("music", "配樂"))
    # narration (free Microsoft Edge voices; offline → captions only)
    nar = [(s, s.get("narration")) for s in plan.get("shots") or [] if str(s.get("narration") or "").strip()]
    nar_ok = 0
    for s, text in nar:
        f = p.dir / "build" / "voice" / f"{s['id']}.mp3"
        f.parent.mkdir(parents=True, exist_ok=True)
        if f.exists() or await _tts(text, p.lang, f):
            nar_ok += 1
            tracks.append((f"voice{s['id']}", ["-i", str(f)], f"adelay={int(float(s['start_s']) * 1000)}|{int(float(s['start_s']) * 1000)},volume=1.6"))
    if nar:
        notes.append(p.t(f"narration {nar_ok}/{len(nar)}", f"旁白 {nar_ok}/{len(nar)}"))
        if nar_ok < len(nar):
            p.err(p.t("Some narration couldn't be voiced (needs internet and `pip install edge-tts`); captions show the lines.",
                      "部分旁白無法配音（需要網路與 `pip install edge-tts`），字幕仍會顯示。"))
    # whooshes on designed transitions
    sfx = next((p.dir / a["file"] for a in plan.get("assets") or [] if a.get("kind") == "sfx" and a.get("file") and (p.dir / a["file"]).exists()), None)
    if sfx:
        t = 0.0
        k = 0
        for i, s in enumerate(plan.get("shots") or []):
            spec = p.read(f"build/shots/{s['id']}.json") or {}
            if i and str(spec.get("transition_in") or "cut") not in ("cut", "smash") and k < 12:
                tracks.append((f"sfx{i}", ["-i", str(sfx)], f"atrim=0:0.8,adelay={int(max(0, t - 0.2) * 1000)}|{int(max(0, t - 0.2) * 1000)},volume={0.35 if mfile else 0.6}"))
                k += 1
            t += float(s["end_s"]) - float(s["start_s"])
        if k:
            notes.append(p.t(f"{k} whoosh(es)", f"{k} 個轉場音效"))
    out = p.dir / "out" / "video.mp4"
    tmp = p.dir / "out" / "video.tmp.mp4"
    if tracks:
        args = [config.ffmpeg(), "-y", "-loglevel", "error", "-i", str(silent)]
        filt = []
        for i, (lab, inp, f) in enumerate(tracks, start=1):
            args += inp
            filt.append(f"[{i}:a]{f},aresample=48000,aformat=channel_layouts=stereo[a{i}]")
        labels = "".join(f"[a{i}]" for i in range(1, len(tracks) + 1))
        duck = ""
        if mfile and nar_ok:
            duck = ",volume=0.9"
        filt.append(f"{labels}amix=inputs={len(tracks)}:normalize=0:duration=longest{duck},alimiter=limit=0.95,apad,atrim=0:{total:.3f}[aout]")
        args += ["-filter_complex", ";".join(filt), "-map", "0:v", "-map", "[aout]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.3f}", "-movflags", "+faststart", str(tmp)]
        code, err = await p.run(_run, args)
        if code:
            p.err("audio mix failed: " + err[-300:])
            tracks = []
    if not tracks:
        code, err = await p.run(_run, [config.ffmpeg(), "-y", "-loglevel", "error", "-i", str(silent), "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                                       "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-t", f"{total:.3f}", "-movflags", "+faststart", str(tmp)])
        if code:
            return {"ok": False, "stderr": err}
    os.replace(tmp, out)
    dur = _probe_dur(out)
    p.tool("ffprobe", f"out/video.mp4 · {dur:.2f}s")
    return {"ok": True, "text": p.t(f"Assembled out/video.mp4: {dur:.1f}s, {len(plan.get('shots') or [])} shots" + (f", {', '.join(notes)}" if notes else ", silent") + ".",
                                    f"組裝完成 out/video.mp4：{dur:.1f} 秒、{len(plan.get('shots') or [])} 鏡" + (f"、{'、'.join(notes)}" if notes else "、無聲") + "。")}


# =====================================================================================================
# critique: only what spans segments
# =====================================================================================================
def _contact(p: P, video: Path, out: Path, n: int = 12) -> None:
    dur = _probe_dur(video)
    if dur <= 0:
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    _run([config.ffmpeg(), "-y", "-loglevel", "error", "-i", str(video), "-vf", f"fps={n / dur:.4f},scale=320:-2,tile=4x{(n + 3) // 4}", "-frames:v", "1", str(out)])


def _mean_volume(f: Path) -> float | None:
    r = subprocess.run([config.ffmpeg(), "-hide_banner", "-i", str(f), "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    m = re.search(r"mean_volume:\s*(-?[\d.]+)", r.stderr)
    return float(m.group(1)) if m else None


async def critique(p: P) -> dict:
    plan = p.plan()
    report = p.read("analysis/report.json") or {}
    video = p.dir / "out" / "video.mp4"
    T = p.t
    must, nice, verified = [], [], []
    scores = {"pacing": 5, "continuity": 5, "readability": 5, "motion": 5, "style": 5, "sound": 5}
    dur = _probe_dur(video)
    planned = sum(float(s["end_s"]) - float(s["start_s"]) for s in plan.get("shots") or [])
    if abs(dur - planned) > 0.4:
        must.append({"shot": None, "time": None, "issue": T(f"Film is {dur:.1f}s but the plan is {planned:.1f}s.", f"成片 {dur:.1f} 秒，企劃是 {planned:.1f} 秒。"),
                     "fix": T("re-assemble", "重新組裝"), "code": "length"})
        scores["pacing"] -= 2
    ref_mean = (report.get("pacing") or {}).get("mean_shot_s")
    n = len(plan.get("shots") or [])
    if ref_mean and n:
        ours = planned / n
        if abs(ours - ref_mean) / ref_mean > 0.3 and (report.get("pacing") or {}).get("count", 0) >= 3:
            nice.append({"issue": T(f"Mean shot {ours:.1f}s vs reference {ref_mean:.1f}s (more than ±30%).", f"平均鏡頭 {ours:.1f} 秒，參考片 {ref_mean:.1f} 秒（差超過 ±30%）。")})
            scores["pacing"] -= 1
    # continuity: 180° rule across same-setting seams
    prev = None
    for sid, a, b in shot_times(plan):
        sp = p.read(f"build/shots/{sid}.json") or {}
        acts = {x["cast"]: x["x"] for x in sp.get("actors") or []}
        if prev and prev[1] == sp.get("setting") and len(acts) >= 2:
            common = [c for c in acts if c in prev[2]]
            if len(common) >= 2:
                c1, c2 = common[:2]
                if (acts[c1] - acts[c2]) * (prev[2][c1] - prev[2][c2]) < 0:
                    must.append({"shot": sid, "time": round(a, 2), "issue": T(f"{c1} and {c2} swap sides between {prev[0]} and {sid} (breaks the 180° rule).",
                                                                               f"{prev[0]} 接 {sid} 時 {c1} 和 {c2} 左右互換（違反 180 度原則）。"),
                                 "fix": T("keep them on the same sides", "保持左右位置一致"), "code": "swap", "cast": [c1, c2]})
                    scores["continuity"] -= 2
        prev = (sid, sp.get("setting"), acts)
    # every shot re-measured (fixes made since the shot review still hold?)
    for sid, a, b in shot_times(plan):
        for it in measure_shot(p, sid, plan):
            if it["severity"] == "blocker":
                must.append({"shot": sid, "time": round(a + (it.get("time") or 0), 2), "issue": it["issue"], "fix": it.get("fix"), "code": it["code"]})
                key = {"subject_small": "readability", "text_face": "readability", "text_small": "readability", "static": "motion", "flicker": "motion"}.get(it["code"], "style")
                scores[key] -= 1
            else:
                nice.append({"shot": sid, "issue": it["issue"]})
    # captions consistent across the film
    sizes = set()
    for sid, _, _ in shot_times(plan):
        for s in (metrics(p, sid).get("samples") or [])[:6]:
            for tx in s["texts"]:
                if tx.get("style") == "caption":
                    sizes.add(round(tx["size_px"]))
    if len(sizes) > 2 and max(sizes) / max(1, min(sizes)) > 1.35:
        nice.append({"issue": T("Caption sizes vary between shots.", "各鏡字幕大小不一致。")})
        scores["readability"] -= 1
    # sound
    music = plan.get("music") or {}
    if music.get("file") or any(s.get("narration") for s in plan.get("shots") or []):
        mv = _mean_volume(video)
        if mv is None or mv < -45:
            must.append({"shot": None, "time": None, "issue": T("The film is silent but music/narration was planned.", "企劃有配樂或旁白，但成片是無聲的。"),
                         "fix": T("re-mix the audio", "重新混音"), "code": "silent"})
            scores["sound"] -= 3
    else:
        scores["sound"] = 3
    # verify earlier director fixes
    for x in p.read("out/check/fixes.json") or []:
        if isinstance(x, dict) and x.get("status") == "fixed":
            still = any(m.get("code") == x.get("code") and m.get("shot") == x.get("shot") for m in must if x.get("code"))
            verified.append({"issue": x.get("issue"), "shot": x.get("shot"), "verified": not still, "before": x.get("before"), "after": x.get("after")})
    sheet = p.dir / "out" / "check" / "final_contact.jpg"
    await p.run(_contact, p, video, sheet)
    if sheet.exists():
        p.look_at("out/check/final_contact.jpg")
    summary = ""
    if p.crew.enabled:
        ai = await p.crew.ask_json(
            f"You are the final critic of a short 2D animation. You check only what spans shots: seams, continuity, pacing, consistent captions.\n{p.lang_rule()}",
            f"""Plan: {short(plan.get('logline'), 200)}; {n} shots, {planned:.1f}s.
Measured problems: {json.dumps([m['issue'] for m in must], ensure_ascii=False)}; minor: {json.dumps([x['issue'] for x in nice][:8], ensure_ascii=False)}
{'The image is a contact sheet of the finished film (12 moments).' if p.crew.vision() else ''}
Reply JSON: {{"thinking": "...", "summary": "2-3 sentences for the user", "nice_to_have": ["..."]}}""",
            images=[sheet] if sheet.exists() else None, keep=False)
        if isinstance(ai, dict):
            summary = short(ai.get("summary"), 400)
            nice += [{"issue": short(x, 160)} for x in ai.get("nice_to_have") or [] if isinstance(x, str)][:4]
    if not summary:
        summary = T(f"{n} shots, {dur:.1f}s. " + ("No blocking problems found." if not must else f"{len(must)} must-fix item(s)."),
                    f"{n} 鏡、{dur:.1f} 秒。" + ("沒有必修問題。" if not must else f"{len(must)} 項必修。"))
    scores = {k: max(1, min(5, v)) for k, v in scores.items()}
    crit = {"pass": not must, "scores": scores, "must_fix": must, "needs_user": [], "verified_fixes": verified, "nice_to_have": nice[:10], "summary": summary}
    p.write("out/check/critique.json", crit)
    return {"ok": True, "text": summary + ("" if not must else "\n" + "\n".join(f"- [{m.get('shot') or T('film', '全片')}] {short(m['issue'], 100)}" for m in must[:5]))}


# =====================================================================================================
# revise: the director changes only the affected shots, re-renders, re-assembles, proves every fix
# =====================================================================================================
KEYWORD_FIX = [
    (r"bigger|larger|too small|closer|放大|太小|靠近|特寫", "subject_small"), (r"text|caption|字|字幕", "text_small"),
    (r"static|boring|nothing moves|move more|不動|太死|沒動", "static"), (r"face|擋|蓋住", "text_face"),
    (r"overlap|穿|重疊", "overlap"), (r"empty|blank|空", "blank"), (r"flash|flicker|閃", "flicker"),
]


async def revise(p: P) -> dict:
    plan = p.plan()
    cast = load_cast(p, plan)
    ids = list(cast)
    v = p.vars
    items: list[dict] = []
    for m in v.get("must") or []:
        items.append({"shot": m.get("shot") or (shot_at(plan, m["time"]) if isinstance(m.get("time"), (int, float)) else None), "time": m.get("time"),
                      "issue": m.get("issue"), "code": m.get("code"), "cast": m.get("cast")})
    for n in v.get("notes") or []:
        if isinstance(n, dict) and n.get("text"):
            items.append({"shot": shot_at(plan, float(n.get("t") or 0)), "time": float(n.get("t") or 0), "issue": n["text"], "code": None})
    if not items:
        msg = v.get("message") or ""
        for ln in [x for x in msg.splitlines() if x.strip()] or [msg]:
            sid = (re.search(r"\b(S\d+)\b", ln) or [None, None])[1]
            tm = re.search(r"［?\[?(\d+(?:\.\d+)?)\s*(?:s|秒)", ln)
            t = float(tm.group(1)) if tm else None
            if not sid and t is not None:
                sid = shot_at(plan, t)
            items.append({"shot": sid, "time": t, "issue": re.sub(r"^\d+\.\s*", "", ln).strip(), "code": None})
    fixes, film_level = [], []
    by_shot: dict[str, list[dict]] = {}
    for it in items:
        if it.get("code") in ("length", "silent"):
            film_level.append(it)
        elif it.get("shot"):
            by_shot.setdefault(it["shot"], []).append(it)
        else:
            film_level.append(it)
    # film-level notes without a shot: ask the AI which shots they concern
    if film_level and p.crew.enabled:
        ai = await p.crew.ask_json(
            "You are the director. Map each note on the finished film to the shots it concerns.",
            f"""Shots: {json.dumps([{'id': s['id'], 'start_s': s['start_s'], 'end_s': s['end_s'], 'summary': s.get('summary')} for s in plan.get('shots') or []], ensure_ascii=False)}
Notes: {json.dumps([i['issue'] for i in film_level if i.get('code') not in ('length', 'silent')], ensure_ascii=False)}
Reply JSON: {{"map": [{{"note": 0, "shots": ["S2"]}}]}}""", keep=False)
        for mp in (ai or {}).get("map") or [] if isinstance(ai, dict) else []:
            try:
                it = [i for i in film_level if i.get("code") not in ("length", "silent")][int(mp.get("note"))]
            except Exception:
                continue
            for sid in mp.get("shots") or []:
                if sid in [s["id"] for s in plan.get("shots") or []]:
                    by_shot.setdefault(sid, []).append(it)
    last_id = (plan.get("shots") or [{}])[-1].get("id")
    for sid, its in by_shot.items():
        if p.aborted():
            return {"ok": False, "stderr": "cancelled"}
        old = load_spec(p, sid, plan, ids)
        spec = json.loads(json.dumps(old))
        changes, free = [], []
        for it in its:
            code = it.get("code")
            if not code:
                for rx, c in KEYWORD_FIX:
                    if re.search(rx, str(it.get("issue")), re.I):
                        code = c if not p.crew.enabled else None
                        break
            ch = apply_shot_fix(spec, {**it, "code": code}) if code else None
            if code == "swap":
                prev_id = next((s["id"] for i, s in enumerate(plan["shots"]) if i + 1 < len(plan["shots"]) and plan["shots"][i + 1]["id"] == sid), None)
                prev = p.read(f"build/shots/{prev_id}.json") or {} if prev_id else {}
                pos = {a["cast"]: a["x"] for a in prev.get("actors") or []}
                for a in spec.get("actors") or []:
                    if a["cast"] in pos:
                        a["x"] = pos[a["cast"]]
                ch = "kept characters on the same sides as the previous shot"
            if ch:
                changes.append((it, ch))
            else:
                free.append(it)
        if free and p.crew.enabled:
            ai = await p.crew.ask_json(
                "You are the director revising one shot of a finished 2D animation. Change only what the notes ask.",
                f"""Shot {sid} spec: {spec_json_for_prompt(spec)}
Notes (times are seconds in the film; this shot spans {old['start']:.1f}-{old['start'] + old['duration']:.1f}s): {json.dumps([{'time': i.get('time'), 'note': i.get('issue')} for i in free], ensure_ascii=False)}
Allowed values — {ENUMS}
Reply JSON: {{"thinking": "...", "spec": {{...full corrected spec...}}, "changes": ["what changed"], "cannot": ["what can't be done + alternative"]}}""")
            if isinstance(ai, dict) and isinstance(ai.get("spec"), dict):
                new = scene.normalize_spec(ai["spec"], spec, ids)
                new["id"], new["start"], new["duration"] = spec["id"], spec["start"], spec["duration"]
                spec = new
                for it in free:
                    changes.append((it, "; ".join(short(c, 60) for c in ai.get("changes") or []) or "spec edited"))
                for c in ai.get("cannot") or []:
                    fixes.append({"issue": short(c, 160), "shot": sid, "status": "cannot", "change": ""})
            else:
                for it in free:
                    fixes.append({"issue": it.get("issue"), "shot": sid, "status": "cannot", "change": ""})
        elif free:
            for it in free:
                fixes.append({"issue": it.get("issue"), "shot": sid, "status": "cannot", "change": "",
                              "note": p.t("The built-in rules couldn't map this note to a change; pick an AI crew.", "內建規則無法把這則意見變成修改，請選一個 AI 導演。")})
        if not changes:
            continue
        t_local = next((float(i["time"]) - old["start"] for i in its if isinstance(i.get("time"), (int, float))), old["duration"] / 2)
        t_local = min(max(0.0, t_local), old["duration"] - 0.01)
        ctx_old = ctx_for(p, plan, cast, old["setting"], old["time"])
        m_old = metrics(p, sid)
        smp = min(m_old.get("samples") or [{"t": t_local, "actors": []}], key=lambda s: abs(s["t"] - t_local))
        box = smp["actors"][0]["box"] if smp.get("actors") else [0, 0, ctx_old.W, ctx_old.H]
        before = f"out/check/revise_{sid}_before.png"
        await p.run(crop, old, ctx_old, t_local, box, p.path(before))
        save_spec(p, spec)
        await p.run(render_shot_files, p, spec, sid == last_id, plan, cast)
        ctx_new = ctx_for(p, plan, cast, spec["setting"], spec["time"])
        after = f"out/check/revise_{sid}_after.png"
        await p.run(crop, spec, ctx_new, t_local, box, p.path(after))
        p.look_at(after)
        for it, ch in changes:
            fixes.append({"issue": short(it.get("issue"), 200), "shot": sid, "time": it.get("time"), "code": it.get("code"), "change": ch,
                          "before": before, "after": after, "status": "fixed"})
    r = await assemble(p)
    if not r.get("ok"):
        return r
    for it in film_level:
        if it.get("code") in ("length", "silent"):
            fixes.append({"issue": it.get("issue"), "shot": None, "change": p.t("re-assembled", "重新組裝"), "status": "fixed", "code": it.get("code")})
    p.write("out/check/fixes.json", fixes)
    ok = [f for f in fixes if f["status"] == "fixed"]
    bad = [f for f in fixes if f["status"] != "fixed"]
    return {"ok": True, "text": p.t(
        f"Revised {len({f['shot'] for f in ok if f.get('shot')})} shot(s), {len(ok)} change(s) with before/after crops." + (f"\nCouldn't do: " + "; ".join(short(f['issue'], 80) for f in bad[:3]) if bad else ""),
        f"改了 {len({f['shot'] for f in ok if f.get('shot')})} 鏡、{len(ok)} 處，每處附修改前後對照。" + (f"\n做不到：" + "；".join(short(f['issue'], 50) for f in bad[:3]) if bad else ""))}


__all__ = ["assemble", "critique", "revise", "asyncio"]
