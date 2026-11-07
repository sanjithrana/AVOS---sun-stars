"""Production line: setup, the cast gate (review ⇄ fix per character), shots (build → fresh review ⇄ fix), shared fixes.

Reviewers measure what the renderer drew (actor/text boxes, motion, blank area, flicker, connected silhouette…) and,
when the AI crew can see images, also look at the sheets. Every fix carries before/after crops of the same moment."""
from __future__ import annotations

import json
import math
import re
import shutil
from pathlib import Path

from ..render import actions, engines, rig, scene
from ..render.color import hue_dist, luma, mix, norm, palette_roles, shade
from ..render.shot import cast_sheet, lineup_sheet, silhouette_parts
from .build import HANDLE, ctx_for, load_spec, metrics, render_shot_files, save_spec, spec_json_for_prompt
from .common import P, engine_of, load_cast, short
from .pre import ENUMS, RULES

EMO_ACTIONS = {"talk", "cry", "laugh", "shock", "love", "shy", "angry", "think"}


# =====================================================================================================
# setup
# =====================================================================================================
def _chunks(shots: list[str], builders: int) -> list[dict]:
    n = len(shots)
    size = 2 if n <= 6 else 3 if n <= 15 else 4
    out = []
    for i in range(0, n, size):
        out.append({"id": f"C{len(out) + 1}", "shots": shots[i:i + size]})
    if len(out) > 1 and len(out[-1]["shots"]) == 1:
        out[-2]["shots"] += out.pop()["shots"]
    return out


async def setup(p: P) -> dict:
    from ..config import CONFIG
    plan = p.plan()
    lk = engines.look(engine_of(p))
    roles = palette_roles((plan.get("look") or {}).get("palette"))
    cast = load_cast(p, plan)
    for c in plan.get("characters") or []:
        if not p.path(c["file"]).exists():
            p.write(c["file"], cast[c["id"]])
    shared = p.read("build/shared.json") or {}
    shared.setdefault("captions", {"narration_captions": True, "font": lk["font"], "min_height": 0.05})
    shared.setdefault("line_weight", 1.0)
    shared.update({"engine": engine_of(p), "palette": roles["all"], "fps": (plan.get("format") or {}).get("fps") or 24})
    p.write("build/shared.json", shared)
    chars = []
    for c in plan.get("characters") or []:
        cd = cast[c["id"]]
        used = sorted({actions.canon(a.get("action")) for s in plan.get("shots") or [] for a in (s.get("scene") or {}).get("actors") or [] if a.get("cast") == c["id"]})
        rel = f"out/check/cast/sheet_{c['id']}.jpg"
        await p.run(cast_sheet, cd, lk, roles, p.path(rel), used[:6], None)
        p.look_at(rel)
        chars.append({"id": c["id"], "name": c.get("name") or c["id"], "file": c["file"], "sheet": rel})
    await p.run(lineup_sheet, list(cast.values()), lk, p.path("out/check/cast/sheet.jpg"))
    p.look_at("out/check/cast/sheet.jpg")
    shot_ids = [s["id"] for s in plan.get("shots") or []]
    prod = {"cast_sheet": "out/check/cast/sheet.jpg", "characters": chars, "chunks": _chunks(shot_ids, CONFIG["builders"]),
            "rig_files": ["build/shared.json"], "shot_files": "build/shots/<id>.json", "engine": engine_of(p),
            "how_to_preview": "build/shots/<id>.mp4 + out/check/shots/<id>_sheet.jpg", "how_to_render": "studio.render.shot.render_shot",
            "shared_readonly": ["build/assets/cast/*.json", "build/shared.json"]}
    p.write("build/production.json", prod)
    return {"ok": True, "text": p.t(
        f"Set up: {len(chars)} character sheet(s), {len(shot_ids)} shots in {len(prod['chunks'])} parts, engine {lk['label']}.",
        f"建置完成：{len(chars)} 張角色設定圖，{len(shot_ids)} 鏡分成 {len(prod['chunks'])} 段，引擎 {lk['label']}。")}


# =====================================================================================================
# cast gate
# =====================================================================================================
def _desc_colors(desc: str) -> dict:
    from ..render.color import colors_near
    t = (desc or "").lower()
    return {k: v for k, v in {
        "top": colors_near(t, ["hoodie", "shirt", "連帽", "帽t", "dress", "洋裝", "sweater", "毛衣", "suit", "西裝", "jacket", "外套"]),
        "hair": colors_near(t, ["hair", "髮", "发"]), "skin": colors_near(t, ["skin", "膚", "fur", "毛色"])}.items() if v}


def _review_char(p: P, cd: dict, plan: dict, lk: dict, others: list[dict]) -> list[dict]:
    issues = []
    T = p.t
    nm = cd["name"]
    for pose in list(dict.fromkeys(["idle", "wave", "walk"] + cd.get("poses", [])[:4])):
        parts = silhouette_parts(cd, lk, pose)
        if parts > 1:
            issues.append({"character": cd["id"], "what": pose, "code": "detached", "severity": "blocker",
                           "issue": T(f"{nm}'s silhouette breaks into {parts} pieces in the '{pose}' pose (a floating part).", f"{nm} 的「{pose}」姿勢輪廓斷成 {parts} 塊（有浮空的部位）。"),
                           "fix": T("reconnect the limb to the body (shorter reach / smaller arm angle)", "把肢體接回身體（縮短或減小角度）")})
            break
    want = _desc_colors(cd.get("design") or "")
    for k, col in want.items():
        if hue_dist(col, cd["colors"][k]) > 0.22 or abs(luma(col) - luma(cd["colors"][k])) > 0.3:
            issues.append({"character": cd["id"], "what": k, "code": f"color_{k}", "severity": "blocker", "want": col,
                           "issue": T(f"{nm}'s {k} is {cd['colors'][k]} but the plan describes {col}.", f"{nm} 的 {k} 顏色是 {cd['colors'][k]}，企劃寫的是 {col}。"),
                           "fix": T(f"set {k} to {col}", f"把 {k} 改成 {col}")})
    roles = palette_roles((plan.get("look") or {}).get("palette"))
    bgs = [roles["wall"], roles["sky_bot"], mix(roles["ground"], "#FFFFFF", 0.35)]
    main = cd["colors"]["top"] if cd["top"] != "none" else cd["colors"]["skin"]
    if lk["look"] != "whiteboard" and min(abs(luma(main) - luma(b)) + hue_dist(main, b) for b in bgs) < 0.06:
        issues.append({"character": cd["id"], "what": "contrast", "code": "contrast", "severity": "blocker",
                       "issue": T(f"{nm}'s main colour {main} melts into the backgrounds.", f"{nm} 的主色 {main} 跟背景太接近，會糊在一起。"),
                       "fix": T("darken or saturate the outfit", "衣服加深或提高彩度")})
    for o in others:
        if o["id"] == cd["id"]:
            continue
        a = cd["colors"]["top"] if cd["top"] != "none" else cd["colors"]["skin"]
        b = o["colors"]["top"] if o["top"] != "none" else o["colors"]["skin"]
        if hue_dist(a, b) < 0.05 and abs(luma(a) - luma(b)) < 0.08 and cd["body"] == o["body"] and cd["hair"] == o["hair"]:
            issues.append({"character": cd["id"], "what": "lineup", "code": "twin", "severity": "blocker",
                           "issue": T(f"{nm} and {o['name']} look almost the same (body, hair and colours).", f"{nm} 和 {o['name']} 幾乎一樣（身形、髮型、顏色）。"),
                           "fix": T("give one of them a different main colour", "其中一個換主色")})
    d = (cd.get("design") or "").lower()
    if re.search(r"\btall|高大|高個", d) and cd["height"] < 1.0:
        issues.append({"character": cd["id"], "what": "height", "code": "height_up", "severity": "polish",
                       "issue": T(f"The plan says {nm} is tall but the rig is {cd['height']:.2f}.", f"企劃寫 {nm} 很高，但目前高度 {cd['height']:.2f}。"), "fix": "height 1.15"})
    if re.search(r"small|tiny|little|小小|矮", d) and cd["height"] > 0.95 and cd["body"] != "blob":
        issues.append({"character": cd["id"], "what": "height", "code": "height_down", "severity": "polish",
                       "issue": T(f"The plan says {nm} is small but the rig is {cd['height']:.2f}.", f"企劃寫 {nm} 很小，但目前高度 {cd['height']:.2f}。"), "fix": "height 0.8"})
    return issues


async def _vision_issues(p: P, image: Path, who: str, what: str) -> list[dict]:
    if not p.crew.enabled or not p.crew.vision() or not image.exists():
        return []
    ai = await p.crew.ask_json(
        f"You are an independent reviewer of 2D animation. You did not make this. Be strict about real defects only.\n{p.lang_rule()}",
        f"""Look at {what}. Check: every body part attached (head-neck-body, shoulder-arm-hand, hip-leg-foot), no floating parts,
no seams or double outlines at joints, consistent line width, readable expression, matches the description.
Reply JSON: {{"thinking": "...", "issues": [{{"what": "where", "issue": "what you see", "fix": "how", "severity": "blocker|polish"}}]}}
blocker = visible at normal size; polish = only when zoomed. Return an empty list if it is fine.""", images=[image], keep=False)
    out = []
    for x in (ai or {}).get("issues") or [] if isinstance(ai, dict) else []:
        if isinstance(x, dict) and x.get("issue"):
            out.append({"character": who, "what": short(x.get("what"), 40), "issue": short(x["issue"], 200), "fix": short(x.get("fix"), 160),
                        "severity": "blocker" if x.get("severity") == "blocker" else "polish", "code": "vision"})
    return out


def _verify(p: P, prev_fix_files: list[str], current_codes: set[str]) -> list[dict]:
    out = []
    for f in prev_fix_files:
        fx = p.read(f) or []
        for x in fx if isinstance(fx, list) else fx.get("fixes") or []:
            if isinstance(x, dict) and x.get("status") == "fixed":
                ok = x.get("code") not in current_codes
                out.append({"issue": x.get("issue"), "verified": ok, "before": x.get("before"), "after": x.get("after"),
                            "note": "" if ok else "said fixed, still there"})
    return out


async def cast_qa(p: P) -> dict:
    plan = p.plan()
    lk = engines.look(engine_of(p))
    cast = load_cast(p, plan)
    others = list(cast.values())
    v = p.vars
    if v.get("character"):
        c = v["character"]
        cd = cast.get(c["id"])
        p.look_at(c["sheet"])
        issues = await p.run(_review_char, p, cd, plan, lk, others) if cd else []
        issues += await _vision_issues(p, p.path(c["sheet"]), c["id"], f"the character sheet of {c.get('name')}: {cd.get('design') if cd else ''}")
        verified = _verify(p, [f"out/check/cast/fixes_{c['id']}.json"], {i.get("code") for i in issues})
        for x in verified:
            if not x["verified"]:
                issues.append({"character": c["id"], "what": "fix", "code": "unverified", "severity": "blocker",
                               "issue": p.t(f"Said fixed but still there: {x['issue']}", f"說修好了但還在：{x['issue']}")})
        rv = {"pass": not any(i["severity"] == "blocker" for i in issues), "issues": issues, "verified_fixes": verified, "needs_user": []}
        p.write(f"out/check/cast/review_{c['id']}.json", rv)
        name = c.get("name") or c["id"]
    else:
        p.look_at("out/check/cast/sheet.jpg")
        issues = []
        for cd in others:
            issues += await p.run(_review_char, p, cd, plan, lk, others)
        if v.get("lineup") or v.get("round") == "lineup":
            hs = sorted((cd["height"], cd["name"]) for cd in others)
            if len(hs) > 1 and hs[-1][0] / max(0.1, hs[0][0]) > 2.2:
                issues.append({"character": "lineup", "what": "scale", "code": "scale", "severity": "polish",
                               "issue": p.t(f"Height gap is very large ({hs[0][1]} vs {hs[-1][1]}).", f"身高差非常大（{hs[0][1]} 對 {hs[-1][1]}）。")})
        issues += await _vision_issues(p, p.path("out/check/cast/sheet.jpg"), "lineup", "the line-up of all characters side by side")
        verified = _verify(p, ["out/check/cast/fixes.json"], {i.get("code") for i in issues})
        rv = {"pass": not any(i["severity"] == "blocker" for i in issues), "issues": issues, "verified_fixes": verified, "needs_user": []}
        p.write("out/check/cast/review.json", rv)
        name = p.t("the cast", "全體角色")
    b = [i for i in issues if i["severity"] == "blocker"]
    return {"ok": True, "text": p.t(
        f"Checked {name}: " + ("passes." if not b else f"{len(b)} blocker(s): " + "; ".join(short(i['issue'], 90) for i in b[:3])) + (f" ({len(issues) - len(b)} polish)" if len(issues) > len(b) else ""),
        f"檢查 {name}：" + ("通過。" if not b else f"{len(b)} 個必修：" + "；".join(short(i['issue'], 60) for i in b[:3])) + (f"（{len(issues) - len(b)} 個小瑕疵）" if len(issues) > len(b) else ""))}


def _apply_char_fix(cd: dict, it: dict) -> str | None:
    code = it.get("code") or ""
    if code.startswith("color_") and it.get("want"):
        k = code.split("_", 1)[1]
        cd["colors"][k] = norm(it["want"])
        return f"{k} → {cd['colors'][k]}"
    if code == "contrast":
        k = "top" if cd["top"] != "none" else "skin"
        cd["colors"][k] = shade(cd["colors"][k], -0.18, 0.15)
        return f"{k} → {cd['colors'][k]}"
    if code == "twin":
        cd["colors"]["top"] = shade(mix(cd["colors"]["top"], "#E5484D", 0.6), 0.0, 0.1)
        return f"top → {cd['colors']['top']}"
    if code == "detached":
        cd["build"] = "round" if cd["build"] != "round" else "normal"
        return "build → " + cd["build"]
    if code == "height_up":
        cd["height"] = 1.15
        return "height → 1.15"
    if code == "height_down":
        cd["height"] = 0.8
        return "height → 0.8"
    return None


async def cast_fix(p: P) -> dict:
    plan = p.plan()
    lk = engines.look(engine_of(p))
    roles = palette_roles((plan.get("look") or {}).get("palette"))
    v = p.vars
    issues = [i for i in v.get("issues") or [] if isinstance(i, dict)]
    targets = [v["character"]["id"]] if v.get("character") else [c["id"] for c in plan.get("characters") or []]
    cast = load_cast(p, plan)
    fixes = []
    if v.get("shared"):
        sh = p.read("build/shared.json") or {}
        sh["line_weight"] = round(float(sh.get("line_weight") or 1.0) * 1.1, 2)
        p.write("build/shared.json", sh)
        fixes.append({"issue": "; ".join(short(i.get("issue"), 60) for i in issues[:3]), "change": f"shared line weight → {sh['line_weight']}", "status": "fixed"})
    for cid in targets:
        cd = cast.get(cid)
        if not cd:
            continue
        mine = [i for i in issues if i.get("character") in (cid, None, "lineup")]
        sheet = f"out/check/cast/sheet_{cid}.jpg"
        before = f"out/check/cast/fix_{cid}_r{v.get('round')}_before.jpg"
        if p.path(sheet).exists():
            shutil.copyfile(p.path(sheet), p.path(before))
        changes = []
        for it in mine:
            ch = _apply_char_fix(cd, it)
            if ch:
                changes.append((it, ch))
        free = [i for i in mine if not _known(i)] + ([{"issue": v["message"], "code": "user"}] if v.get("message") else [])
        if free and p.crew.enabled:
            ai = await p.crew.ask_json(
                f"You fix a 2D character rig definition.\n{RULES}",
                f"""Definition: {json.dumps({k: cd[k] for k in ('body', 'height', 'build', 'colors', 'hair', 'eyes', 'glasses', 'ears', 'tail', 'top', 'bottom', 'accessories')}, ensure_ascii=False)}
Problems to fix: {json.dumps([{k: i.get(k) for k in ('what', 'issue', 'fix')} for i in free], ensure_ascii=False)}
Allowed: body {rig.BODY_TYPES}; hair {rig.HAIR}; top {rig.TOPS}; bottom {rig.BOTTOMS}; glasses {rig.GLASSES}; ears {rig.EARS}; accessories {rig.ACCESSORIES}
Reply JSON: {{"thinking": "...", "changes": {{"field": "new value", "colors": {{"top": "#hex"}}}}, "cannot": ["problem you can't fix and why"]}}""", keep=True)
            ch = (ai or {}).get("changes") if isinstance(ai, dict) else None
            if isinstance(ch, dict):
                merged = rig.normalize({**cd, **{k: v2 for k, v2 in ch.items() if k != "colors"},
                                        "colors": {**cd["colors"], **(ch.get("colors") if isinstance(ch.get("colors"), dict) else {})}}, cid, cd["name"])
                diff = [k for k in ("body", "height", "build", "hair", "top", "bottom", "glasses", "ears", "accessories") if merged[k] != cd[k]] + \
                       [f"colors.{k}" for k in merged["colors"] if merged["colors"][k] != cd["colors"][k]]
                merged["poses"], merged["expressions"], merged["design"] = cd["poses"], cd["expressions"], cd.get("design")
                cd.clear()
                cd.update(merged)
                for i in free:
                    changes.append((i, ", ".join(diff) or "no change"))
            for c in (ai or {}).get("cannot") or [] if isinstance(ai, dict) else []:
                fixes.append({"issue": short(c, 160), "change": "", "status": "cannot"})
        elif free:
            for i in free:
                fixes.append({"issue": short(i.get("issue"), 160), "change": "", "status": "cannot",
                              "note": p.t("needs an AI crew to interpret", "需要 AI 導演才能理解這項")})
        p.write(f"build/assets/cast/{cid}.json", cd)
        used = sorted({actions.canon(a.get("action")) for s in plan.get("shots") or [] for a in (s.get("scene") or {}).get("actors") or [] if a.get("cast") == cid})
        await p.run(cast_sheet, cd, lk, roles, p.path(sheet), used[:6], None)
        p.look_at(sheet)
        after = f"out/check/cast/fix_{cid}_r{v.get('round')}_after.jpg"
        shutil.copyfile(p.path(sheet), p.path(after))
        for it, ch in changes:
            fixes.append({"issue": short(it.get("issue"), 200), "code": it.get("code"), "change": ch, "before": before, "after": after, "status": "fixed"})
        if v.get("character"):
            p.write(f"out/check/cast/fixes_{cid}.json", fixes)
    await p.run(lineup_sheet, list(load_cast(p, plan).values()), lk, p.path("out/check/cast/sheet.jpg"))
    if not v.get("character"):
        p.write("out/check/cast/fixes.json", fixes)
    n = sum(1 for f in fixes if f["status"] == "fixed")
    return {"ok": True, "text": p.t(f"Fixed {n} item(s): " + "; ".join(short(f['change'], 50) for f in fixes if f['status'] == 'fixed')[:300] +
                                    ("" if all(f["status"] == "fixed" for f in fixes) else f" · {sum(1 for f in fixes if f['status'] != 'fixed')} couldn't be fixed"),
                                    f"修好 {n} 項：" + "；".join(short(f['change'], 40) for f in fixes if f['status'] == 'fixed')[:200] +
                                    ("" if all(f["status"] == "fixed" for f in fixes) else f" · {sum(1 for f in fixes if f['status'] != 'fixed')} 項無法修"))}


def _known(i: dict) -> bool:
    return str(i.get("code") or "").startswith(("color_", "contrast", "twin", "detached", "height_"))


# =====================================================================================================
# shots: build
# =====================================================================================================
async def build_chunk(p: P) -> dict:
    plan = p.plan()
    chunk = p.vars["chunk"]
    cast = load_cast(p, plan)
    ids = list(cast)
    shots = {s["id"]: s for s in plan.get("shots") or []}
    last_id = (plan.get("shots") or [{}])[-1].get("id")
    drafts = {sid: load_spec(p, sid, plan, ids) for sid in chunk["shots"] if sid in shots}
    ai = await p.crew.ask_json(
        f"You are a shot builder. You turn plan shots into exact shot specs for the renderer.\n{RULES}",
        f"""Plan: {short(plan.get('logline'), 200)} · style {plan.get('style')} · palette {(plan.get('look') or {}).get('palette')}
Characters: {json.dumps([{k: c.get(k) for k in ('id', 'name', 'design')} for c in plan.get('characters') or []], ensure_ascii=False)}
Shots to build: {json.dumps([{k: shots[s].get(k) for k in ('id', 'start_s', 'end_s', 'summary', 'action', 'camera', 'ref_what', 'text_overlay', 'narration', 'transition_in')} for s in drafts], ensure_ascii=False)}
Engine drafts (improve them): {json.dumps({sid: json.loads(spec_json_for_prompt(sp)) for sid, sp in drafts.items()}, ensure_ascii=False)[:7000]}
Allowed values — {ENUMS}
Positions: x 0..1 across the frame, y = height above the ground (0 = standing on it), scale = character height as a fraction of the frame (0.35-0.7; emotional close-ups 0.6+).
Props: x, y (0..1 screen position), scale 0.08-0.3. Text: at [start, end] seconds inside the shot, position bottom|top|center.
Camera: move, pace (match the reference), from.fill/to.fill = how much of the frame height the main character fills.
Reply JSON: {{"thinking": "...", "shots": {{"S1": {{"setting": "...", "time": "...", "actors": [...], "props": [...], "text": [...], "camera": {{...}}, "fx": [...], "transition_in": "..."}}}}}}""",
        max_tokens=5000)
    ai_specs = (ai or {}).get("shots") if isinstance(ai, dict) else None
    notes = []
    done_list = []
    for sid, draft in drafts.items():
        if p.aborted():
            return {"ok": False, "stderr": "cancelled"}
        raw = ai_specs.get(sid) if isinstance(ai_specs, dict) else None
        spec = scene.normalize_spec(raw, draft, ids) if raw else draft
        spec["id"], spec["start"], spec["duration"] = sid, draft["start"], draft["duration"]
        save_spec(p, spec)
        m = await p.run(render_shot_files, p, spec, sid == last_id, plan, cast)
        entry = {"id": sid, "sheet": m["sheet"], "crops": m["crops"], "notes": short(shots[sid].get("summary"), 120)}
        p.write(f"out/check/shots/{sid}.done.json", {"shots": [entry]})
        done_list.append(entry)
        notes.append(f"{sid} {spec['duration']:.1f}s {spec['setting']} {spec['camera']['move']}")
    p.write(f"out/check/shots/{chunk['id']}.done.json", {"shots": done_list})
    return {"ok": True, "text": p.t(f"Built {chunk['id']}: " + "; ".join(notes), f"{chunk['id']} 做好了：" + "；".join(notes))}


# =====================================================================================================
# shots: review
# =====================================================================================================
def _iou(a: list[float], b: list[float]) -> float:
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x1 - x0) * max(0, y1 - y0)
    if not inter:
        return 0.0
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / max(1e-6, ua)


def _cover(inner: list[float], outer: list[float]) -> float:
    x0, y0, x1, y1 = max(inner[0], outer[0]), max(inner[1], outer[1]), min(inner[2], outer[2]), min(inner[3], outer[3])
    inter = max(0, x1 - x0) * max(0, y1 - y0)
    return inter / max(1e-6, (inner[2] - inner[0]) * (inner[3] - inner[1]))


def measure_shot(p: P, sid: str, plan: dict) -> list[dict]:
    """Defects found from what the renderer reports (boxes, motion, blank area, flicker)."""
    m = metrics(p, sid)
    shot = next((s for s in plan.get("shots") or [] if s["id"] == sid), {})
    spec = p.read(f"build/shots/{sid}.json") or {}
    T = p.t
    if not m:
        return [{"code": "missing", "severity": "blocker", "issue": T("The shot wasn't rendered.", "這一鏡沒有渲染出來。"), "time": 0, "where": "all"}]
    W, H = m["W"], m["H"]
    S = m.get("samples") or []
    dur = m.get("duration", 0)
    issues: list[dict] = []
    frame = [0, 0, W, H]

    def add(code: str, sev: str, en: str, zh: str, t: float, where: str, fix_en: str, fix_zh: str, **extra) -> None:
        issues.append({"code": code, "severity": sev, "issue": T(en, zh), "time": round(t, 2), "where": where, "fix": T(fix_en, fix_zh), **extra})
    # duration
    if abs(m["frames"] / m["fps"] - (dur + m.get("handle", 0))) > 0.12:
        add("duration", "blocker", f"Length is {m['frames'] / m['fps']:.2f}s, the plan says {dur:.2f}s.", f"長度 {m['frames'] / m['fps']:.2f} 秒，企劃是 {dur:.2f} 秒。", 0, "all", "re-render at the planned length", "照企劃長度重渲染")
    cam = spec.get("camera") or {}
    planned_fill = max((cam.get("from") or {}).get("fill", 0.5), (cam.get("to") or {}).get("fill", 0.5))
    inner = [s for s in S if s["t"] <= dur]
    acts = spec.get("actors") or []
    # subject size on emotional beats
    if acts and inner:
        main = acts[0]
        emo = main.get("action") in EMO_ACTIONS or (main.get("expression") or "") not in ("", "neutral", "happy")
        hs = [next((a for a in s["actors"] if a["cast"] == main["cast"]), None) for s in inner]
        hs = [(a["box"][3] - a["box"][1]) / H for a in hs if a]
        if emo and hs and max(hs) < 0.35 and planned_fill >= 0.35:
            add("subject_small", "blocker", f"The main character fills only {max(hs):.0%} of the frame height in an emotional moment (needs ≥35%).",
                f"情緒鏡頭主角只佔畫面高度 {max(hs):.0%}（至少要 35%）。", dur / 2, main["cast"], "bigger scale or push in", "放大角色或推近")
    # off screen / overlap / text over faces
    off: dict[str, int] = {}
    overlap = 0
    face_hits: list[tuple[float, str]] = []
    for s in inner:
        in_entry = any((a.get("enter") and s["t"] < min(dur * 0.45, 1.8)) or (a.get("exit") and s["t"] > dur - min(dur * 0.4, 1.6)) for a in acts)
        for a in s["actors"]:
            if not in_entry and _cover(a["box"], frame) < 0.55:
                off[a["cast"]] = off.get(a["cast"], 0) + 1
        for i in range(len(s["actors"])):
            for j in range(i + 1, len(s["actors"])):
                if _iou(s["actors"][i]["box"], s["actors"][j]["box"]) > 0.45 and s["actors"][i]["action"] != "hug":
                    overlap += 1
        for tx in s["texts"]:
            if tx.get("style") == "lyrics":
                continue
            for a in s["actors"]:
                if _cover(a["head"], tx["box"]) > 0.3:
                    face_hits.append((s["t"], a["cast"], (a["head"][1] + a["head"][3]) / 2 / H, tx["box"][1] / H))
            if _cover(tx["box"], frame) < 0.95:
                add("text_offscreen", "blocker", f"Text '{short(tx['text'], 30)}' runs off the frame.", f"字「{short(tx['text'], 20)}」超出畫面。", s["t"], "text",
                    "shorter text or smaller size", "縮短文字或縮小")
            if tx["size_px"] < 0.045 * min(W, H) * 0.98:
                add("text_small", "blocker", f"Text '{short(tx['text'], 30)}' is {tx['size_px'] / min(W, H):.1%} of the frame (needs ≥4.5% to read on a phone).",
                    f"字「{short(tx['text'], 20)}」只有畫面的 {tx['size_px'] / min(W, H):.1%}（手機上要 ≥4.5%）。", s["t"], "text", "bigger text", "字放大")
    for cid, n in off.items():
        if n > 0.4 * max(1, len(inner)):
            add("offscreen", "blocker", f"{cid} is mostly outside the frame.", f"{cid} 大部分在畫面外。", dur / 2, cid, "move them into frame", "把角色移回畫面內", cast=cid)
    if overlap > 0.3 * max(1, len(inner)):
        add("overlap", "blocker", "Two characters overlap / pass through each other.", "兩個角色重疊、互相穿過。", dur / 2, "actors", "spread them apart", "把角色分開")
    if face_hits:
        t0, cid, head_y, _ = face_hits[0]
        add("text_face", "blocker", f"On-screen text covers {cid}'s face.", f"字幕蓋住 {cid} 的臉。", t0, "text", "move the text away from the face", "把字移開",
            head_y=round(head_y, 3))
    # motion
    zooms = [s.get("zoom", 1) for s in inner]
    centers = []
    for s in inner:
        if s["actors"]:
            b = s["actors"][0]["box"]
            centers.append(((b[0] + b[2]) / 2 / W, (b[1] + b[3]) / 2 / H))
    moved = (max(zooms) - min(zooms) > 0.03 if zooms else False) or (len(centers) > 1 and max(abs(c[0] - centers[0][0]) + abs(c[1] - centers[0][1]) for c in centers) > 0.02)
    ref_moves = str((shot.get("camera") or {}).get("move") or "static") != "static"
    if not moved and (ref_moves or dur > 2.5):
        add("static", "blocker" if ref_moves else "polish", "A dead static shot: nothing moves, but the reference moves here.",
            "畫面完全沒動，但參考片這裡有動。", dur / 2, "camera", "add the reference's camera move", "加上參考片的運鏡")
    # flicker / jumps inside the shot
    diff = m.get("diff") or []
    fps = m["fps"]
    for i, d in enumerate(diff[1:int(dur * fps)], start=1):
        if d > 45:
            add("flicker", "blocker", f"A jump/flash at {i / fps:.2f}s (frame change {d:.0f}).", f"{i / fps:.2f} 秒有跳格／閃爍（變化 {d:.0f}）。", i / fps, "all",
                "remove the shake/flash or smooth it", "拿掉晃動或閃光，讓它平順")
            break
    # blank frame
    if m.get("blank", 0) > 0.72:
        add("blank", "blocker" if m["blank"] > 0.85 else "polish", f"{m['blank']:.0%} of the frame is empty.", f"畫面有 {m['blank']:.0%} 是空白。", dur / 2, "all",
            "fill the frame: bigger subject, props or a richer setting", "填滿畫面：主體放大、加道具或背景")
    if not acts and not spec.get("text") and not spec.get("props"):
        add("empty", "blocker", "Nothing happens in this shot (no character, text or prop).", "這一鏡什麼都沒有（沒有角色、字或道具）。", dur / 2, "all",
            "add the planned subject", "加上企劃的主體")
    return issues


async def shot_qa(p: P) -> dict:
    plan = p.plan()
    sid = p.vars["shots"][0]
    rnd = p.vars.get("round", 1)
    p.look_at(f"out/check/shots/{sid}_sheet.jpg")
    issues = await p.run(measure_shot, p, sid, plan)
    if p.crew.enabled and p.crew.vision():
        shot = next((s for s in plan.get("shots") or [] if s["id"] == sid), {})
        ai = await p.crew.ask_json(
            f"You are an independent shot reviewer for a 2D animation. You didn't make it. Real defects only.\n{p.lang_rule()}",
            f"""Shot {sid} ({shot.get('summary')}). The image is a strip of 6 moments with timestamps.
Check: limbs attached, no floating parts, characters consistent, nothing passes through anything, subject big enough, text readable and not over faces, no broken frames.
Reply JSON: {{"thinking": "...", "issues": [{{"time": seconds, "where": "...", "issue": "...", "fix": "...", "severity": "blocker|polish"}}]}}""",
            images=[p.path(f"out/check/shots/{sid}_sheet.jpg")], keep=False)
        for x in (ai or {}).get("issues") or [] if isinstance(ai, dict) else []:
            if isinstance(x, dict) and x.get("issue"):
                issues.append({"code": "vision", "severity": "blocker" if x.get("severity") == "blocker" and rnd == 1 else "polish", "issue": short(x["issue"], 200),
                               "fix": short(x.get("fix"), 160), "time": x.get("time") if isinstance(x.get("time"), (int, float)) else None, "where": short(x.get("where"), 40)})
    # verify the builder's earlier fixes first
    chunk = p.vars["chunk"]["id"]
    verified = []
    fx = p.read(f"out/check/shots/{chunk}.fixes.json") or []
    codes = {i["code"] for i in issues}
    for x in fx if isinstance(fx, list) else []:
        if isinstance(x, dict) and x.get("shot") == sid and x.get("status") == "fixed":
            ok = x.get("code") not in codes or x.get("code") == "vision"
            verified.append({"shot": sid, "issue": x.get("issue"), "verified": ok, "before": x.get("before"), "after": x.get("after")})
            if not ok:
                base_issue = re.sub(r"^(Said fixed but still there: |說修好了但還在：)+", "", str(x.get("issue") or ""))
                same = next((i for i in issues if i.get("code") == x.get("code")), None)
                if same:
                    same["issue"] = p.t(f"Said fixed but still there: {base_issue}", f"說修好了但還在：{base_issue}")
                    same["unverified"] = True
    # round 2+: only blockers can fail the shot; new polish isn't hunted for
    entry = {"id": sid, "pass": not any(i["severity"] == "blocker" for i in issues), "issues": issues}
    p.write(p.vars.get("out") or f"out/check/shots/{sid}.review.json", {"shots": [entry], "verified_fixes": verified, "needs_user": []})
    b = [i for i in issues if i["severity"] == "blocker"]
    return {"ok": True, "text": p.t(f"{sid}: " + ("passes" if not b else "; ".join(short(i['issue'], 80) for i in b[:3])) + (f" · {len(verified)} fix(es) checked" if verified else ""),
                                    f"{sid}：" + ("通過" if not b else "；".join(short(i['issue'], 50) for i in b[:3])) + (f" · 核對了 {len(verified)} 個修正" if verified else ""))}


# =====================================================================================================
# shots: fix
# =====================================================================================================
def apply_shot_fix(spec: dict, it: dict) -> str | None:
    code = it.get("code") or ""
    acts = spec.get("actors") or []
    cam = spec.setdefault("camera", {"move": "static", "pace": "medium", "from": {"fill": 0.5}, "to": {"fill": 0.5}})
    if code == "subject_small" and acts:
        acts[0]["scale"] = max(acts[0].get("scale", 0.5), 0.6)
        cam["to"] = {"fill": max(0.62, cam.get("to", {}).get("fill", 0.5))}
        cam["from"] = {"fill": max(0.5, cam.get("from", {}).get("fill", 0.5))}
        return f"main character scale {acts[0]['scale']}, camera fill → {cam['to']['fill']}"
    if code == "offscreen":
        for a in acts:
            if a["cast"] == it.get("cast") or not it.get("cast"):
                a["x"] = min(0.82, max(0.18, a.get("x", 0.5)))
                a["y"] = min(0.15, a.get("y", 0))
        return "characters moved into frame"
    if code == "overlap" and len(acts) >= 2:
        n = len(acts)
        for i, a in enumerate(acts):
            a["x"] = 0.28 + 0.44 * i / max(1, n - 1)
        return "characters spread to " + ", ".join(f"{a['x']:.2f}" for a in acts)
    if code == "text_face":
        hy = it.get("head_y", 0.4)
        pos = "bottom" if hy < 0.5 else "top"
        for t in spec.get("text") or []:
            t["position"] = pos
            t["size"] = min(t.get("size", 0.07), 0.075)
        if hy >= 0.3 and pos == "bottom":
            for a in acts:
                a["y"] = max(a.get("y", 0), 0.0)
        cam["to"] = {"fill": min(cam.get("to", {}).get("fill", 0.5), 0.6)}
        cam["from"] = {"fill": min(cam.get("from", {}).get("fill", 0.5), 0.6)}
        return f"text moved to the {pos}, away from the face"
    if code in ("text_small", "text_offscreen"):
        for t in spec.get("text") or []:
            t["size"] = max(0.06, min(0.09, t.get("size", 0.07))) if code == "text_small" else 0.06
            if code == "text_offscreen":
                t["text"] = t["text"][:60]
        return "text resized"
    if code == "static":
        cam["move"] = "dolly_in"
        cam["pace"] = cam.get("pace") or "slow"
        cam["to"] = {"fill": cam.get("from", {}).get("fill", 0.5) * 1.25}
        if acts and acts[0].get("action") == "idle":
            acts[0]["action"] = "talk"
        return "added a slow push-in and movement"
    if code == "flicker":
        spec["fx"] = [f for f in spec.get("fx") or [] if f not in ("speedlines", "focuslines")]
        if cam.get("move") == "shake":
            cam["move"] = "static"
        return "removed flashing effects / shake"
    if code in ("blank", "empty"):
        if acts:
            for a in acts:
                a["scale"] = max(a.get("scale", 0.5), 0.55)
        if not spec.get("props"):
            spec["props"] = [{"kind": "star", "x": 0.82, "y": 0.3, "scale": 0.12, "anim": "float", "color": "", "front": False}]
        if spec.get("setting") == "plain":
            spec["setting"] = "abstract"
        if not spec.get("fx"):
            spec["fx"] = ["sparkles"]
        return "filled the frame (bigger subject, prop, effects)"
    if code == "duration":
        return "re-rendered at the planned length"
    return None


async def fix_chunk(p: P) -> dict:
    plan = p.plan()
    chunk = p.vars["chunk"]
    cast = load_cast(p, plan)
    ids = list(cast)
    last_id = (plan.get("shots") or [{}])[-1].get("id")
    bad = p.vars.get("bad") or []
    user = p.vars.get("message")
    fixes = []
    for e in bad:
        sid = e.get("id")
        if sid not in chunk["shots"]:
            continue
        spec = load_spec(p, sid, plan, ids)
        issues = [i for i in e.get("issues") or [] if isinstance(i, dict) and i.get("severity", "blocker") != "polish"] or (e.get("issues") or [])
        changes = []
        caption_shared = [i for i in issues if "caption" in str(i.get("issue", "")).lower() and "all shots" in str(i.get("issue", "")).lower()]
        for i in caption_shared:
            fixes.append({"shot": sid, "issue": i.get("issue"), "code": i.get("code"), "status": "shared", "change": ""})
        free = []
        seen_codes: set[str] = set()
        for it in issues:
            if it in caption_shared:
                continue
            if it.get("code") and it.get("code") != "vision":
                if it["code"] in seen_codes:
                    continue
                seen_codes.add(it["code"])
            ch = apply_shot_fix(spec, it)
            if ch:
                changes.append((it, ch))
            else:
                free.append(it)
        if (free or user) and p.crew.enabled:
            ai = await p.crew.ask_json(
                "You are the builder of this shot. Fix the listed problems by editing the shot spec. Keep everything else.",
                f"""Spec: {spec_json_for_prompt(spec)}
Problems: {json.dumps([{k: i.get(k) for k in ('time', 'where', 'issue', 'fix')} for i in free], ensure_ascii=False)}
{('User note: ' + user) if user else ''}
Allowed values — {ENUMS}
Reply JSON: {{"thinking": "...", "spec": {{...the full corrected spec...}}, "changes": ["what you changed"], "cannot": ["what you can't fix"]}}""")
            if isinstance(ai, dict) and isinstance(ai.get("spec"), dict):
                new = scene.normalize_spec(ai["spec"], spec, ids)
                new["id"], new["start"], new["duration"] = spec["id"], spec["start"], spec["duration"]
                spec = new
                for it in free:
                    changes.append((it, "; ".join(short(c, 60) for c in ai.get("changes") or []) or "spec edited"))
                for c in ai.get("cannot") or []:
                    fixes.append({"shot": sid, "issue": short(c, 160), "status": "cannot", "change": ""})
            else:
                for it in free:
                    fixes.append({"shot": sid, "issue": it.get("issue"), "code": it.get("code"), "status": "cannot", "change": ""})
        else:
            for it in free:
                fixes.append({"shot": sid, "issue": it.get("issue"), "code": it.get("code"), "status": "cannot", "change": "",
                              "note": p.t("needs an AI crew to interpret", "需要 AI 導演才能理解這項")})
        # before/after: same moment, same region
        t = next((i.get("time") for i in issues if isinstance(i.get("time"), (int, float))), spec["duration"] / 2) or spec["duration"] / 2
        t = min(max(0.0, t), spec["duration"] - 0.01)
        old = load_spec(p, sid, plan, ids)
        ctx = ctx_for(p, plan, cast, old["setting"], old["time"])
        from ..render.shot import crop
        m_old = metrics(p, sid)
        smp = min(m_old.get("samples") or [{"t": t, "actors": []}], key=lambda s: abs(s["t"] - t))
        box = smp["actors"][0]["box"] if smp.get("actors") else [0, 0, ctx.W, ctx.H]
        before = f"out/check/shots/{sid}_fix{p.vars.get('round')}_before.png"
        save_spec(p, spec)
        m = await p.run(render_shot_files, p, spec, sid == last_id, plan, cast)
        smp2 = min(m.get("samples") or [{"t": t, "actors": []}], key=lambda s: abs(s["t"] - t))
        box2 = smp2["actors"][0]["box"] if smp2.get("actors") else box
        union = [min(box[0], box2[0]), min(box[1], box2[1]), max(box[2], box2[2]), max(box[3], box2[3])]
        ctx2 = ctx_for(p, plan, cast, spec["setting"], spec["time"])
        after = f"out/check/shots/{sid}_fix{p.vars.get('round')}_after.png"
        await p.run(crop, spec, ctx2, t, union, p.path(after))
        await p.run(crop, old, ctx, t, union, p.path(before))
        p.look_at(after)
        for it, ch in changes:
            fixes.append({"shot": sid, "issue": short(it.get("issue"), 200), "code": it.get("code"), "time": t, "change": ch,
                          "before": before, "after": after, "status": "fixed"})
    p.write(f"out/check/shots/{chunk['id']}.fixes.json", fixes)
    n = sum(1 for f in fixes if f["status"] == "fixed")
    return {"ok": True, "text": p.t(f"{chunk['id']}: fixed {n}" + (f", {len(fixes) - n} not fixable here" if len(fixes) > n else "") + " (before/after crops attached).",
                                    f"{chunk['id']}：修好 {n} 項" + (f"，{len(fixes) - n} 項這裡修不了" if len(fixes) > n else "") + "（附修改前後對照）。")}


async def shared_fix(p: P) -> dict:
    sh = p.read("build/shared.json") or {}
    items = p.vars.get("items") or []
    cap = sh.setdefault("captions", {})
    cap["min_height"] = max(0.055, float(cap.get("min_height") or 0.05))
    p.write("build/shared.json", sh)
    chunk = p.vars["chunk"]["id"]
    p.write(f"out/check/shots/{chunk}.shared.json", {"changed": ["captions.min_height"], "api": "build/shared.json → captions", "items": items})
    return {"ok": True, "text": p.t("Shared caption style updated for every part.", "已統一調整全片的字幕樣式。")}


__all__ = ["setup", "cast_qa", "cast_fix", "build_chunk", "shot_qa", "fix_chunk", "shared_fix", "measure_shot", "apply_shot_fix", "HANDLE", "math"]
