"""Pre-production: style breakdown → plan core → characters + assets in parallel → style frames; replanning."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from .. import config, styles
from ..render import actions, engines, rig, scene
from ..render.backgrounds import SETTINGS, guess_setting
from ..render.color import norm
from ..render.fx import FX
from ..render.props import KINDS as PROP_KINDS, guess_props, place_props
from ..render.shot import cast_sheet
from .build import ctx_for, render_still
from .common import (P, compact_plan, default_palette, engine_of, inputs, load_cast, report_summary, ref_camera, retime, secs, short,
                     storyboard_md)

ROLE = "You are the director of a small animation studio that remakes the STYLE (pacing, framing, transitions, camera, colour) of a reference video with original characters and content."
RULES = ("Rules: learn technique only, never copy the reference's footage, characters, logos or assets. Characters are original unless the user "
         "uploaded their own designs. Never write or quote song lyrics; lyrics only come from the user's text.")


# =====================================================================================================
# style
# =====================================================================================================
async def style(p: P) -> dict:
    report = p.read("analysis/report.json") or {}
    summ = report_summary(report)
    sheet = p.path("analysis/sheet_scenes.jpg") if p.path("analysis/sheet_scenes.jpg").exists() else p.path("analysis/sheet_1fps.jpg")
    p.look_at("analysis/sheet_1fps.jpg")
    if p.path("analysis/sheet_scenes.jpg").exists():
        p.look_at("analysis/sheet_scenes.jpg")
    metrics = await p.run(styles.measure_look, p.path("analysis/sheet_1fps.jpg"))
    p.tool("measure", f"look: {json.dumps(metrics)}")
    best, conf, why, alts = styles.pick(p.brief, report, metrics)
    reg = [s for s in styles.registry() if s["installed"] and s["medium"].startswith("2d")]
    ai = await p.crew.ask_json(
        f"{ROLE}\n{RULES}\n{p.lang_rule()}",
        f"""Break down this reference video and choose the production style.

User's brief:
{p.brief}

Measured from the reference (analyze.py): {json.dumps(summ, ensure_ascii=False)[:5000]}
Image measurements of its frames: {json.dumps(metrics)}
{'The attached images are contact sheets of the reference (one frame per second / one per shot).' if p.crew.vision() else ''}

Installed styles (pick ONE by its recognition features; 2D only; if the reference is 3D or live action pick the closest 2D style and say so):
{json.dumps([{k: s[k] for k in ('name', 'engine', 'medium', 'title', 'features')} for s in reg], ensure_ascii=False)[:6000]}
The rule-based pick is "{best['name']}" (confidence {conf}). Keep it unless the features clearly fit another style better, or the user asked for a style.

Reply JSON:
{{"thinking": "2-4 sentences: what you see and why the style fits",
 "medium": "2d-painted|2d-crayon|2d-vector|2d-pixel|2d-paper|2d-lineart|2d-cel",
 "style": "<style name from the list>", "confidence": 0.0-1.0, "why": ["short reason", "..."],
 "palette": ["#hex", "... 4-6 colours you see"], "color_arc": "how colour changes over the video",
 "character_language": "shape language of the characters", "editing": "cuts, transitions, on the beat or not",
 "structure": "narrative structure, motif, how jokes land", "text_use": "how captions/text are used",
 "keys": ["3-5 things that make this video good"]}}""",
        images=[sheet, p.path("analysis/sheet_1fps.jpg")])
    chosen = best
    if isinstance(ai, dict) and ai.get("style"):
        hit = next((s for s in reg if s["name"] == ai.get("style")), None)
        if hit:
            chosen = hit
    a = ai if isinstance(ai, dict) else {}
    engine = chosen["engine"]
    medium = a.get("medium") if str(a.get("medium", "")).startswith("2d-") else chosen["medium"]
    ref3d = bool(re.search(r"3d|live|photo|real", str(a.get("thinking", "")).lower())) and not medium.startswith("2d")
    why_list = [short(w, 160) for w in (a.get("why") or why) if w][:5]
    if ref3d:
        why_list.append(p.t("The reference looks 3D/live action; this one is remade in 2D.", "參考片是 3D／實拍，這支用 2D 重現。"))
    route = {"medium": medium, "style": chosen["name"], "engine": engine, "engine_label": engines.engine_label(engine),
             "confidence": float(a.get("confidence") or conf) if isinstance(a.get("confidence"), (int, float)) else conf,
             "why": why_list, "alternatives": alts, "new_style_proposed": False, "measured": metrics}
    p.write("analysis/route.json", route)
    # STYLE.md
    shots = summ["shots"]
    pacing = report.get("pacing") or {}
    audio = report.get("audio") or {}
    pal = [norm(c) for c in (a.get("palette") or []) if isinstance(c, str)][:6] or default_palette(engine, report)
    T = p.t
    md = [f"{T('Medium', '媒材')}: {medium}", "", f"# {T('Style breakdown', '風格拆解')}", "",
          f"## {T('Shot list', '鏡頭清單')}", "", f"| # | {T('Time', '秒數')} | {T('Camera', '運鏡')} | {T('Pace', '快慢')} | {T('Brightness', '亮暗')} | {T('Colours', '主色')} |", "|---|---|---|---|---|---|"]
    for s in shots:
        md.append(f"| {s['n']} | {s['start']:.1f}–{s['end']:.1f} | {s['move']} | {s.get('pace') or ''} | {s.get('brightness')} | {' '.join(s.get('colours') or [])} |")
    md += ["", f"## {T('Colour', '配色與色彩弧線')}", f"- {T('Palette', '配色')}: {' '.join(pal)}", f"- {a.get('color_arc') or T('steady palette', '色調穩定')}",
           "", f"## {T('Character shape language', '角色造型語言')}", f"- {a.get('character_language') or T('simple, rounded, readable shapes', '簡單、圓潤、好讀的造型')}",
           "", f"## {T('Editing', '剪接')}",
           f"- {T('Shots', '鏡頭數')}: {pacing.get('count')} · {T('mean shot', '平均鏡頭')} {pacing.get('mean_shot_s')}s" + (f" · {pacing.get('mean_shot_beats')} {T('beats', '拍')}" if pacing.get("mean_shot_beats") else ""),
           f"- {T('Tempo', '節奏')}: {audio.get('bpm') or T('no music detected', '沒有偵測到音樂')} BPM",
           f"- {a.get('editing') or ''}", "", f"## {T('Structure', '敘事結構')}", f"- {a.get('structure') or ''}",
           "", f"## {T('Text use', '字幕／文字')}", f"- {a.get('text_use') or ''}", "",
           f"## {T('What makes it work', '這支好看的關鍵')}"] + [f"- {k}" for k in (a.get("keys") or [T("rhythm locked to the cut", "節奏與剪接一致"), T("bold, readable framing", "構圖大膽、好讀"), T("a clear payoff at the end", "結尾有明確的收尾")])][:5]
    md += ["", f"## {T('Chosen style', '選用風格')}", f"- {chosen['title']} (`{chosen['name']}` → {engines.engine_label(engine)})"] + [f"- {w}" for w in why_list]
    p.write_text("analysis/STYLE.md", "\n".join(md) + "\n")
    (p.dir / "analysis" / "style_palette.json").write_text(json.dumps(pal), "utf-8")
    return {"ok": True, "text": p.t(
        f"Style: **{chosen['name']}** → {engines.engine_label(engine)} (confidence {route['confidence']:.0%}).\n"
        f"Reference: {pacing.get('count')} shots, mean {pacing.get('mean_shot_s')}s, {audio.get('bpm') or 'no'} BPM.\n" + "\n".join(f"- {w}" for w in why_list[:3]),
        f"風格：**{chosen['title']}** → {engines.engine_label(engine)}（信心 {route['confidence']:.0%}）。\n"
        f"參考片：{pacing.get('count')} 個鏡頭，平均 {pacing.get('mean_shot_s')} 秒，{audio.get('bpm') or '沒有'} BPM。\n" + "\n".join(f"- {w}" for w in why_list[:3]))}


# =====================================================================================================
# plan
# =====================================================================================================
AUD = re.compile(r"\.(mp3|m4a|wav|aac|flac|ogg|opus)$", re.I)
IMG = re.compile(r"\.(png|jpe?g|webp|gif)$", re.I)


def _target_duration(brief: str, ref_dur: float, song_dur: float | None) -> float:
    m = re.search(r"(\d{1,3})\s*-?\s*(?:s\b|sec|secs|second|seconds|秒)", brief, re.I) or re.search(r"(\d{1,2})\s*-?\s*(?:min|minute|分鐘)", brief, re.I)
    if m:
        v = float(m.group(1)) * (60 if re.search(r"min|分", m.group(0)) else 1)
        return max(6.0, min(120.0, v))
    if song_dur:
        return max(10.0, min(45.0, song_dur))
    if ref_dur and ref_dur <= 60:
        return max(8.0, round(ref_dur))
    return 30.0


def _format(brief: str, report: dict) -> dict:
    vertical = bool(re.search(r"9\s*[:：x]\s*16|vertical|portrait|直式|豎|竖|shorts|reels|tiktok", brief, re.I))
    crop = report.get("crop") or {}
    v = report.get("video") or {}
    w, h = crop.get("w") or v.get("width") or 16, crop.get("h") or v.get("height") or 9
    if not re.search(r"16\s*[:：x]\s*9|horizontal|landscape|橫式", brief, re.I) and h > w * 1.2:
        vertical = True
    return {"width": 1080 if vertical else 1920, "height": 1920 if vertical else 1080, "fps": 24}


def _slots(report: dict, total: float, bpm: float | None) -> list[dict]:
    sd = report.get("shot_details") or []
    ref_dur = (report.get("video") or {}).get("duration") or total
    slots = []
    if len(sd) >= 2:
        k = total / max(1.0, sum(max(0.1, s["end"] - s["start"]) for s in sd))
        for s in sd:
            slots.append({"len": max(0.1, (s["end"] - s["start"]) * k), "ref": s})
        merged = []
        for s in slots:
            if merged and (s["len"] < 0.9 or merged[-1]["len"] < 0.9) and merged[-1]["len"] + s["len"] < 4.5:
                merged[-1]["len"] += s["len"]
            else:
                merged.append(dict(s))
        slots = merged
    else:
        mean = (report.get("pacing") or {}).get("mean_shot_s") or 3.0
        mean = max(1.6, min(4.5, mean if len(sd) >= 2 else 3.0))
        n = max(2, round(total / mean))
        ref = sd[0] if sd else {"shot": 1, "start": 0, "end": ref_dur, "camera": {"kind": ["static"], "pace": "slow"}}
        slots = [{"len": total / n, "ref": ref} for _ in range(n)]
    out = []
    for s in slots:
        while s["len"] > 6.5:
            out.append({"len": s["len"] / 2, "ref": s["ref"]})
            s = {"len": s["len"] / 2, "ref": s["ref"]}
        out.append(s)
    out = out[:24]
    scale = total / sum(s["len"] for s in out)
    beat = 60.0 / bpm if bpm and 60 <= bpm <= 200 else None
    t = 0.0
    res = []
    for i, s in enumerate(out):
        d = s["len"] * scale
        end = t + d
        if beat and i < len(out) - 1:
            end = max(t + beat * 2, round(end / beat) * beat)
        if i == len(out) - 1:
            end = total
        res.append({"start": round(t, 3), "end": round(end, 3), "ref": s["ref"]})
        t = end
    return [r for r in res if r["end"] - r["start"] >= 0.4]


def _analyze_song(p: P, song: str) -> dict:
    out = p.dir / "analysis" / "song"
    if (out / "report.json").exists():
        return json.loads((out / "report.json").read_text("utf-8"))
    p.tool("analyze.py", f"{song} → analysis/song")
    r = subprocess.run([config.PY, str(config.SCRIPTS / "analyze.py"), str(p.dir / song), "--out", str(out)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=str(config.WORK_DIR))
    if r.returncode or not (out / "report.json").exists():
        p.err(f"analyze.py (song): {r.stderr[-300:]}")
        return {}
    return json.loads((out / "report.json").read_text("utf-8"))


ARC_EN = [("Opening: establish the world and the hero", "idle", "happy", "wave"), ("The hero wants something", "talk", "happy", "think"),
          ("Trying to get it", "walk", "determined", "walk"), ("A funny setback", "shock", "surprised", "fall"),
          ("Not giving up", "think", "confused", "point"), ("The big moment", "jump", "excited", "cheer"),
          ("Payoff", "cheer", "laugh", "dance"), ("Ending that echoes the opening", "wave", "happy", "idle")]
ARC_ZH = ["開場：建立世界與主角", "主角想要某樣東西", "努力去拿", "好笑的挫折", "不放棄", "關鍵時刻", "收穫", "呼應開場的結尾"]


def title_from_brief(brief: str) -> str:
    """A readable working title from the brief ("A 20-second video about a girl who…" → "A girl who…")."""
    first = re.split(r"[\n。!！?？]|\.(?:\s|$)", (brief or "").strip())[0].strip()
    t = re.sub(r"^(please\s+)?(make|create|do|build|give me|i want|i need)\s+(me\s+)?", "", first, flags=re.I)
    t = re.sub(r"^(a|an|one)\s+([\w-]+\s+){0,4}?(video|story|animation|film|clip|cartoon|short|mv|explainer|ad|vlog)\s+(about|of|where|in which|showing|on)\s+", "", t, flags=re.I)
    t = re.sub(r"^(做|製作|制作)?(一支|一部|一個|一个)?.{0,12}?(影片|動畫|动画|故事)[，,:：]?(關於|关于|主軸是|主轴是)?", "", t)
    head = re.sub(r"[,，;；].*$", "", t).strip()
    t = head if head and (len(head.split()) >= 3 or not re.match(r"[A-Za-z]", head)) else (t.strip() or first or "Untitled")
    t = t[0].upper() + t[1:] if t and t[0].isalpha() else t
    if len(t) > 40:
        cut = t[:40].rsplit(" ", 1)[0] if " " in t[:40] else t[:38]
        t = cut.rstrip(" ,.-") + "…"
    return t


def _baseline_plan(p: P, slots: list[dict], engine: str, style_name: str, palette: list[str], fmt: dict, music: dict) -> dict:
    brief = p.brief.strip()
    title = title_from_brief(brief)
    setting = guess_setting(brief, {"whiteboard": "plain", "hyperframes": "abstract" if re.search(r"app|product|產品|logo", brief, re.I) else "room"}.get(engine, "park" if engine == "painted-animation" else "room"))
    user_imgs = [f for f in inputs(p) if IMG.search(f)]
    design = short(re.sub(r"\s+", " ", brief), 140)
    chars = [{"id": "hero", "name": p.t("Hero", "主角"), "design": design, "arc": p.t("wants something → tries → gets it", "想要 → 努力 → 得到"),
              "file": "build/assets/cast/hero.json"}]
    if re.search(r"two|friend|couple|love|情侶|愛情|朋友|兩個|兄弟|姐妹|together|we\b", brief, re.I):
        chars.append({"id": "friend", "name": p.t("Friend", "朋友"), "design": p.t("the hero's friend, contrasting colours", "主角的朋友，配色對比"),
                      "arc": p.t("helps at the end", "最後幫忙"), "file": "build/assets/cast/friend.json"})
    brief_props = [k for k in guess_props(brief, 3) if not re.search(rf"\b{k}\b", " ".join(c["design"] for c in chars).lower() if k in ("cat", "dog", "bird", "fish") else "@@")][:2]
    shots = []
    n = len(slots)
    for i, s in enumerate(slots):
        k = min(len(ARC_EN) - 1, int(i * len(ARC_EN) / max(1, n)))
        beat_en, act, expr, act2 = ARC_EN[k]
        ref = s["ref"]
        cam = ref_camera((ref.get("camera") or {}).get("kind") or [], (ref.get("camera") or {}).get("pace"))
        dark = ((ref.get("look") or {}).get("brightness") or 0.5) < 0.3
        actors = [{"id": "hero", "action": act if i % 2 == 0 else act2, "expression": expr}]
        if len(chars) > 1 and k >= 4:
            actors.append({"id": "friend", "action": "cheer" if k >= 5 else "talk", "expression": "happy"})
        txt = []
        if i == 0:
            txt = [{"text": title, "at": [0.2, max(0.6, s["end"] - s["start"] - 0.2)], "position": "top", "style": "title"}]
        shots.append({
            "id": f"S{i + 1}", "start_s": s["start"], "end_s": s["end"],
            "summary": p.t(beat_en, ARC_ZH[k]) + (f" — {short(brief, 60)}" if i == 0 else ""),
            "action": p.t(f"Hero {actors[0]['action']}s ({expr})", f"主角動作：{actors[0]['action']}（{expr}）"),
            "camera_note": f"{cam['move']} · {cam['pace']}", "camera": cam,
            "transition_in": "cut" if i == 0 or (ref.get("camera") or {}).get("pace") == "fast" else ("fade" if dark else "wipe" if i % 3 == 0 else "cut"),
            "transition_out": "", "reads": [p.t(beat_en, ARC_ZH[k])],
            "ref_shot": ref.get("shot"), "ref_what": p.t(f"ref #{ref.get('shot')}: {'+'.join((ref.get('camera') or {}).get('kind') or ['static'])}, {(ref.get('camera') or {}).get('pace') or ''}",
                                                         f"參考 #{ref.get('shot')}：{'+'.join((ref.get('camera') or {}).get('kind') or ['static'])}，{(ref.get('camera') or {}).get('pace') or ''}"),
            "text_overlay": txt, "assets": [], "sfx": [], "notes": "",
            "scene": {"setting": setting, "time": "night" if dark or "moon" in brief_props or "star" in brief_props else "day",
                      "actors": [{"cast": a["id"], "action": a["action"], "expression": a["expression"]} for a in actors],
                      "props": place_props(brief_props)},
        })
    req = []
    lyr_style = style_name in ("painted-story-mv", "music-kinetic")
    if (lyr_style or re.search(r"lyric|歌詞|歌词|karaoke|卡拉", brief, re.I)) and (music.get("file") or lyr_style):
        req.append({"id": "lyrics", "kind": "lyrics", "label": p.t("Lyrics text", "歌詞文字"),
                    "why": p.t("Karaoke captions; paste plain text, it's timed automatically", "卡拉 OK 字幕；貼上純文字即可，系統會自動對時")})
    if lyr_style and not music.get("file"):
        req.append({"id": "song", "kind": "audio", "label": p.t("Song / music file", "歌曲音檔"),
                    "why": p.t("This style is cut to a song. Upload your own track (or skip for a silent film)", "這個風格跟著歌曲剪接，請上傳你自己的音檔（或略過做無聲版）")})
    if re.search(r"my (own )?character|our (logo|mascot|product)|my product|自家|我的角色|我們的(產品|logo)|吉祥物", brief, re.I) and not user_imgs:
        req.append({"id": "design", "kind": "image", "label": p.t("Your character / product images", "你的角色或產品圖"),
                    "why": p.t("You mentioned your own design; the crew follows it exactly", "你提到自家設計，製作會照著做")})
    props_used = sorted({(k.get("kind") if isinstance(k, dict) else k) for s in shots for k in (s.get("scene") or {}).get("props") or []} - {None})
    assets = [{"id": f"A{i + 1}", "kind": "image", "purpose": k, "status": "drawn_in_code", "license": "original"} for i, k in enumerate(props_used)]
    assets.append({"id": f"A{len(assets) + 1}", "kind": "sfx", "purpose": p.t("whoosh for transitions", "轉場的咻聲"), "status": "to_fetch",
                   "query": "whoosh swoosh", "source": "openverse"})
    if music.get("file"):
        assets.append({"id": f"A{len(assets) + 1}", "kind": "music", "purpose": p.t("your music", "你的配樂"), "status": "user", "file": music["file"], "license": "user-provided"})
    sf = sorted({0, n // 2, max(0, n - 2)})
    return {
        "version": 1, "title": title, "logline": short(brief, 160), "style": style_name, "engine": engine, "format": fmt,
        "music": music, "look": {"medium": engines.engine_label(engine), "palette": palette, "typography": "", "texture": "",
                                 "color_arc": p.t("warm and bright, a little darker at the setback, brightest at the end", "溫暖明亮，挫折時稍暗，結尾最亮")},
        "borrowed_from_reference": [p.t("shot lengths follow the reference", "鏡頭長度照參考片"), p.t("same camera move per shot", "每鏡運鏡與參考一致"),
                                    p.t("ending echoes the opening", "結尾呼應開場")],
        "characters": chars, "shots": shots, "assets": assets,
        "style_frames": [f"out/check/style_{i + 1}.jpg" for i in range(len(sf))], "style_frame_shots": [shots[i]["id"] for i in sf],
        "required_inputs": req, "open_questions": [], "changelog": [p.t("v1: first draft", "v1：初版")],
    }


ENUMS = (f"settings: {', '.join(SETTINGS)}; actions: {', '.join(rig.POSES)}; expressions: {', '.join(rig.EXPRESSIONS)}; "
         f"props: {', '.join(PROP_KINDS)}; fx: {', '.join(FX)}; transitions: {', '.join(scene.TRANSITIONS)}")


def _merge_ai_plan(base: dict, ai: dict, p: P, by_index: bool = True) -> dict:
    plan = json.loads(json.dumps(base))
    if not isinstance(ai, dict):
        return plan
    for k in ("title", "logline", "motif"):
        if isinstance(ai.get(k), str) and ai[k].strip():
            plan[k] = short(ai[k], 160 if k != "title" else 40)
    look = ai.get("look") if isinstance(ai.get("look"), dict) else {}
    pal = [norm(c) for c in look.get("palette") or [] if isinstance(c, str) and re.match(r"#?[0-9a-fA-F]{6}$", c.strip())]
    if len(pal) >= 3:
        plan["look"]["palette"] = pal[:6]
    for k in ("color_arc", "typography", "texture"):
        if isinstance(look.get(k), str):
            plan["look"][k] = short(look[k], 160)
    if isinstance(ai.get("borrowed_from_reference"), list) and ai["borrowed_from_reference"]:
        plan["borrowed_from_reference"] = [short(x, 100) for x in ai["borrowed_from_reference"] if isinstance(x, str)][:6]
    chars = []
    for c in ai.get("characters") or []:
        if not isinstance(c, dict) or not c.get("name"):
            continue
        cid = re.sub(r"[^a-z0-9_]+", "", str(c.get("id") or c["name"]).lower())[:20] or f"c{len(chars) + 1}"
        if any(x["id"] == cid for x in chars):
            cid += str(len(chars) + 1)
        chars.append({"id": cid, "name": short(c["name"], 30), "design": short(c.get("design"), 300), "arc": short(c.get("arc"), 120),
                      "file": f"build/assets/cast/{cid}.json"})
    if chars:
        plan["characters"] = chars[:4]
    ids = [c["id"] for c in plan["characters"]]
    by_id = {s.get("id"): s for s in ai.get("shots") or [] if isinstance(s, dict)}
    ai_list = [s for s in ai.get("shots") or [] if isinstance(s, dict)]
    for i, s in enumerate(plan["shots"]):
        a = by_id.get(s["id"]) or (ai_list[i] if by_index and i < len(ai_list) and not any(x.get("id") for x in ai_list if isinstance(x, dict)) else None)
        if a is None and by_index and i < len(ai_list) and len(ai_list) == len(plan["shots"]):
            a = ai_list[i]   # a full list whose ids don't match ours: same order
        if not a:
            continue
        for k in ("summary", "action", "narration"):
            if isinstance(a.get(k), str) and a[k].strip():
                s[k] = short(a[k], 220)
        if isinstance(a.get("reads"), list):
            s["reads"] = [short(x, 80) for x in a["reads"] if isinstance(x, str)][:4]
        tr = str(a.get("transition_in") or "").lower()
        if tr in scene.TRANSITIONS:
            s["transition_in"] = tr
        sc = s["scene"]
        if a.get("setting") in SETTINGS:
            sc["setting"] = a["setting"]
        if a.get("time") in ("day", "sunset", "night"):
            sc["time"] = a["time"]
        acts = []
        for x in a.get("actors") or []:
            if isinstance(x, dict) and x.get("id") in ids:
                acts.append({"cast": x["id"], "action": actions.canon(x.get("action")), "expression": x.get("expression") if x.get("expression") in rig.EXPRESSIONS else None})
        if acts or a.get("actors") == []:
            sc["actors"] = acts[:3]
        props = [x for x in a.get("props") or [] if x in PROP_KINDS][:3]
        if props:
            sc["props"] = place_props(props)
        fx = [x for x in a.get("fx") or [] if x in FX][:2]
        if fx:
            sc["fx"] = fx
        txt = a.get("text")
        if isinstance(txt, str) and txt.strip():
            d = s["end_s"] - s["start_s"]
            s["text_overlay"] = [{"text": short(txt, 80), "at": [0.15, max(0.5, d - 0.15)], "position": a.get("text_position") if a.get("text_position") in ("bottom", "top", "center") else "bottom"}]
        elif txt == "" and i > 0:
            s["text_overlay"] = []
    if isinstance(ai.get("open_questions"), list):
        plan["open_questions"] = [short(q, 160) for q in ai["open_questions"] if isinstance(q, str)][:4]
    for r in ai.get("required_inputs") or []:
        if isinstance(r, dict) and r.get("kind") in ("lyrics", "audio", "image", "text", "other") and r.get("id") and not any(x["id"] == r["id"] for x in plan["required_inputs"]):
            if r["kind"] == "lyrics" and not (plan.get("music") or {}).get("file") and not any(x["kind"] == "audio" for x in plan["required_inputs"]):
                continue
            plan["required_inputs"].append({"id": re.sub(r"[^\w-]", "", r["id"])[:20], "kind": r["kind"], "label": short(r.get("label") or r["id"], 60), "why": short(r.get("why"), 160)})
    return plan


async def plan(p: P) -> dict:
    report = p.read("analysis/report.json") or {}
    route = p.read("analysis/route.json") or {}
    engine = engines.resolve(route.get("engine"))
    st = styles.by_name(route.get("style")) or {}
    try:
        palette = json.loads((p.dir / "analysis" / "style_palette.json").read_text("utf-8"))
    except Exception:
        palette = default_palette(engine, report)
    ins = inputs(p)
    song = next((f for f in ins if AUD.search(f)), None)
    music: dict = {"source": "none"}
    song_rep = {}
    if song:
        song_rep = await p.run(_analyze_song, p, song)
        a = song_rep.get("audio") or {}
        dur = (song_rep.get("video") or {}).get("duration") or 30
        target = _target_duration(p.brief, (report.get("video") or {}).get("duration") or 30, None)
        starts = a.get("best_30s_starts") or [0]
        st0 = float(starts[0]) if starts else 0.0
        music = {"source": "user", "file": song, "bpm": a.get("bpm"), "offset": 0,
                 "section": {"start_s": round(st0, 2), "end_s": round(min(dur, st0 + target), 2)}, "license": "user-provided", "note": ""}
    total = _target_duration(p.brief, (report.get("video") or {}).get("duration") or 30, None)
    if music.get("section"):
        total = max(6.0, music["section"]["end_s"] - music["section"]["start_s"])
    fmt = _format(p.brief, report)
    bpm = music.get("bpm") or None
    slots = _slots(report, total, bpm)
    p.think(p.t(f"{len(slots)} shots over {total:.0f}s, each mapped to a reference shot.", f"{total:.0f} 秒切成 {len(slots)} 鏡，逐鏡對照參考片。"))
    base = _baseline_plan(p, slots, engine, route.get("style") or "motion-graphics", palette, fmt, music)
    imgs = [p.path(f) for f in ins if IMG.search(f)][:2]
    slot_desc = [{"id": s["id"], "seconds": f"{s['start_s']:.1f}-{s['end_s']:.1f}", "ref": s["ref_what"], "camera": s["camera"]["move"]} for s in base["shots"]]
    ai = await p.crew.ask_json(
        f"{ROLE}\n{RULES}\n{p.lang_rule()}",
        f"""Write the pre-production plan.

User's brief:
{p.brief}
Files the user gave: {', '.join(ins) or 'none'}{' (the attached images are their own designs: follow them exactly)' if imgs else ''}
Style: {route.get('style')} drawn as {engines.engine_label(engine)}.
Style defaults: {short(st.get('defaults'), 900)}
STYLE.md (reference breakdown):
{short(p.text('analysis/STYLE.md'), 2500)}

Shot slots (timing and camera already copied from the reference — keep the count and order, invent the content):
{json.dumps(slot_desc, ensure_ascii=False)}

Allowed values — {ENUMS}

Reply JSON:
{{"thinking": "how the story uses the reference's structure",
 "title": "short title", "logline": "one-sentence story", "motif": "a recurring visual symbol",
 "look": {{"palette": ["#hex x5: dark, light, 3 accents"], "color_arc": "...", "typography": "..."}},
 "borrowed_from_reference": ["3-5 techniques you copy"],
 "characters": [{{"id": "short_id", "name": "...", "design": "silhouette, proportions, colours, hair, outfit, signature traits", "arc": "..."}}],
 "shots": [{{"id": "S1", "summary": "what happens", "action": "concrete action in time order", "setting": "<setting>", "time": "day|sunset|night",
            "actors": [{{"id": "character id", "action": "<action>", "expression": "<expression>"}}], "props": ["<prop>"], "fx": ["<fx>"],
            "text": "on-screen text or empty", "narration": "voice-over line or empty", "transition_in": "<transition>", "reads": ["what the viewer understands"]}}],
 "required_inputs": [{{"id": "lyrics", "kind": "lyrics|audio|image|text|other", "label": "...", "why": "..."}}],
 "open_questions": ["at most 4 real decisions for the user"]}}
1-3 original characters. Give every slot a shot. Captions short. The ending echoes the opening.""",
        images=imgs, max_tokens=6000)
    plan_ = _merge_ai_plan(base, ai, p) if ai else base
    retime(plan_)
    plan_["format"]["duration_s"] = round(total, 2)
    p.write("plan.json", plan_)
    p.write_text("STORYBOARD.md", storyboard_md(plan_, p.lang))
    p.look_at("analysis/sheet_scenes.jpg")
    req = plan_.get("required_inputs") or []
    return {"ok": True, "text": p.t(
        f"Plan v1: **{plan_['title']}** — {len(plan_['shots'])} shots, {total:.0f}s, {len(plan_['characters'])} character(s)." +
        (f"\nNeeds from you: {', '.join(r['label'] for r in req)}." if req else "") + ("" if ai else "\n(The plan text comes from the engine's own rules; pick an AI crew for a real story.)" if not p.crew.enabled else ""),
        f"企劃 v1：**{plan_['title']}** — {len(plan_['shots'])} 鏡、{total:.0f} 秒、{len(plan_['characters'])} 個角色。" +
        (f"\n需要你提供：{'、'.join(r['label'] for r in req)}。" if req else "") + ("" if ai else "\n（企劃文字是引擎規則產生的；選一個 AI 導演會有真正的故事。）" if not p.crew.enabled else ""))}


# =====================================================================================================
# pre_cast: one character
# =====================================================================================================
async def pre_cast(p: P) -> dict:
    c = p.vars["character"]
    plan_ = p.plan()
    base = rig.from_description(c["id"], c.get("name") or c["id"], c.get("design") or "")
    user_imgs = [p.path(f) for f in inputs(p) if IMG.search(f)][:2]
    uses = [s["id"] for s in plan_.get("shots") or [] if any(a.get("cast") == c["id"] for a in (s.get("scene") or {}).get("actors") or [])]
    acts = sorted({actions.canon(a.get("action")) for s in plan_.get("shots") or [] for a in (s.get("scene") or {}).get("actors") or [] if a.get("cast") == c["id"]})
    exprs = sorted({a.get("expression") for s in plan_.get("shots") or [] for a in (s.get("scene") or {}).get("actors") or [] if a.get("cast") == c["id"] and a.get("expression")})
    ai = await p.crew.ask_json(
        f"You design one character for a 2D animation rig.\n{RULES}",
        f"""Character from the plan: {json.dumps(c, ensure_ascii=False)}
Palette of the film: {', '.join((plan_.get('look') or {}).get('palette') or [])}
{'The attached images are the user own design: match colours and features.' if user_imgs and p.crew.vision() else ''}
Fill this definition (choose only from the listed options):
{{"body": "{'|'.join(rig.BODY_TYPES)}", "height": 0.6-1.4, "build": "slim|normal|round",
 "colors": {{"skin": "#hex", "hair": "#hex", "top": "#hex", "bottom": "#hex", "shoes": "#hex", "accent": "#hex"}},
 "hair": "{'|'.join(rig.HAIR)}", "eyes": "{'|'.join(rig.EYES)}", "glasses": "{'|'.join(rig.GLASSES)}",
 "ears": "{'|'.join(rig.EARS)}", "tail": "{'|'.join(rig.TAILS)}", "top": "{'|'.join(rig.TOPS)}", "bottom": "{'|'.join(rig.BOTTOMS)}",
 "accessories": ["{'|'.join(rig.ACCESSORIES)}"], "blush": true, "freckles": false}}
Engine's first reading of the description: {json.dumps({k: base[k] for k in ('body', 'hair', 'top', 'bottom', 'glasses', 'ears', 'colors', 'accessories')}, ensure_ascii=False)}""",
        images=user_imgs)
    cd = rig.normalize({**base, **(ai if isinstance(ai, dict) else {}), "id": c["id"], "name": c.get("name"), "design": c.get("design"),
                        "poses": list(dict.fromkeys(acts + base["poses"])), "expressions": list(dict.fromkeys(exprs + base["expressions"]))}, c["id"], c.get("name"))
    if isinstance(ai, dict) and isinstance(ai.get("colors"), dict):
        for k in ("skin", "hair", "top", "bottom", "shoes", "accent"):
            if ai["colors"].get(k):
                cd["colors"][k] = norm(ai["colors"][k], cd["colors"][k])
    p.write(c["file"], cd)
    lk = engines.look(engine_of(p))
    from ..render.color import palette_roles
    rel = f"out/check/cast/pre_{c['id']}.jpg"
    p.tool("render", f"character sheet {c['id']}")
    await p.run(cast_sheet, cd, lk, palette_roles((plan_.get("look") or {}).get("palette")), p.path(rel), acts[:6], exprs[:8])
    p.look_at(rel)
    return {"ok": True, "text": p.t(
        f"{cd['name']}: {cd['body']} body, {cd['hair']} hair, {cd['top']}; poses {', '.join(cd['poses'][:6])}; in {len(uses)} shot(s).",
        f"{cd['name']}：{cd['body']} 身形、{cd['hair']} 髮型、{cd['top']}；姿勢 {'、'.join(cd['poses'][:6])}；出現在 {len(uses)} 鏡。")}


# =====================================================================================================
# pre_assets
# =====================================================================================================
def _fetch(p: P, a: dict) -> dict:
    kind = "audio" if a.get("kind") in ("sfx", "music", "audio") else "image"
    q = a.get("query") or a.get("purpose") or "whoosh"
    p.tool("fetch_assets.py", f"search --kind {kind} --q \"{q}\"")
    r = subprocess.run([config.PY, str(config.SCRIPTS / "fetch_assets.py"), "search", "--kind", kind, "--q", q, "--n", "5"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(config.WORK_DIR), timeout=90)
    try:
        res = json.loads(r.stdout) if r.returncode == 0 else []
    except Exception:
        res = []
    for hit in res[:3]:
        ext = Path(hit["url"].split("?")[0]).suffix.lower() or (".mp3" if kind == "audio" else ".jpg")
        if len(ext) > 5:
            ext = ".mp3" if kind == "audio" else ".jpg"
        name = f"{a['id'].lower()}{ext}"
        g = subprocess.run([config.PY, str(config.SCRIPTS / "fetch_assets.py"), "get", "--project", str(p.dir), "--url", hit["url"], "--name", name,
                            "--source", hit.get("source") or "openverse", "--page", hit.get("page") or hit["url"], "--license", hit.get("license") or "?",
                            "--attribution", str(hit.get("attribution") or "")], capture_output=True, text=True, encoding="utf-8", errors="replace",
                           cwd=str(config.WORK_DIR), timeout=120)
        if g.returncode == 0:
            return {"id": a["id"], "file": f"assets/{name}", "source": hit.get("source"), "url": hit.get("page") or hit["url"],
                    "license": hit.get("license"), "attribution": hit.get("attribution"), "status": "fetched", "note": short(hit.get("title"), 80)}
    # nothing usable online (offline, blocked, no result): synthesise a license-free whoosh for sfx, else draw in code
    if kind == "audio":
        out = p.dir / "assets" / f"{a['id'].lower()}_synth.wav"
        out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([config.ffmpeg(), "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anoisesrc=d=0.6:c=pink:a=0.5",
                        "-af", "highpass=f=300,lowpass=f=5000,afade=t=in:d=0.25,afade=t=out:st=0.3:d=0.3,volume=0.6", str(out)], capture_output=True)
        if out.exists():
            ledger = p.dir / "assets" / "ASSETS.md"
            new = not ledger.exists()
            with open(ledger, "a", encoding="utf-8") as f:
                if new:
                    f.write("| 檔名 | 來源 | 原始頁面 | 授權 | 署名 |\n|---|---|---|---|---|\n")
                f.write(f"| {out.name} | synthesised (ffmpeg) | — | original | — |\n")
            return {"id": a["id"], "file": f"assets/{out.name}", "source": "synthesised", "url": "", "license": "original",
                    "attribution": "", "status": "fetched", "note": "made with ffmpeg (no license needed)"}
    return {"id": a["id"], "status": "failed", "note": "nothing suitable found; drawn in code instead"}


async def pre_assets(p: P) -> dict:
    plan_ = p.plan()
    todo = [a for a in plan_.get("assets") or [] if isinstance(a, dict) and a.get("status") == "to_fetch"]
    res = []
    for a in todo:
        if p.aborted():
            break
        res.append(await p.run(_fetch, p, a))
    p.write("assets/fetched.json", res)
    ok = [r for r in res if r["status"] == "fetched"]
    return {"ok": True, "text": p.t(f"Assets: {len(ok)}/{len(res)} found" + (f" ({', '.join(r['source'] for r in ok)})" if ok else "") + ". Licences are in ASSETS.md.",
                                    f"素材：{len(ok)}/{len(res)} 找到" + (f"（{'、'.join(r['source'] for r in ok)}）" if ok else "") + "。授權記在 ASSETS.md。")}


# =====================================================================================================
# plan_frames: merge, then paint the style frames with the real cast
# =====================================================================================================
async def plan_frames(p: P) -> dict:
    plan_ = p.plan()
    fetched = p.read("assets/fetched.json") or []
    for f in fetched:
        a = next((x for x in plan_.get("assets") or [] if x.get("id") == f.get("id")), None)
        if a:
            if f.get("status") == "fetched":
                a.update({k: f[k] for k in ("file", "source", "url", "license", "attribution") if f.get(k) is not None})
                a["status"] = "fetched"
            else:
                a["status"] = "drawn_in_code"
                a["note"] = f.get("note", "")
    # characters an agent didn't finish: the director makes them
    for c in plan_.get("characters") or []:
        if not p.path(c["file"]).exists():
            cd = rig.from_description(c["id"], c.get("name") or c["id"], c.get("design") or "")
            p.write(c["file"], cd)
    cast = load_cast(p, plan_)
    for c in plan_.get("characters") or []:
        if p.path(f"out/check/cast/pre_{c['id']}.jpg").exists():
            p.look_at(f"out/check/cast/pre_{c['id']}.jpg")
    ids = list(cast)
    frames = []
    shots = {s["id"]: s for s in plan_.get("shots") or []}
    pick = plan_.get("style_frame_shots") or [s["id"] for s in (plan_.get("shots") or [])[:3]]
    for i, sid in enumerate(pick[:4]):
        s = shots.get(sid)
        if not s:
            continue
        spec = scene.normalize_spec(None, scene.draft_spec(s, plan_, ids), ids)
        rel = f"out/check/style_{i + 1}.jpg"
        await p.run(render_still, p, spec, spec["duration"] * 0.6, rel, plan_, cast)
        p.look_at(rel)
        frames.append(rel)
    plan_["style_frames"] = frames
    p.write("plan.json", plan_)
    p.write_text("STORYBOARD.md", storyboard_md(plan_, p.lang))
    return {"ok": True, "text": p.t(
        f"Style frames ready ({len(frames)}), drawn with the real cast. Have a look at the plan; tell me what to change, then approve.",
        f"定調畫面完成（{len(frames)} 張），用真正的角色畫的。看一下企劃，有想改的就說，沒問題就核准。")}


# =====================================================================================================
# replan
# =====================================================================================================
def _builtin_replan(p: P, plan_: dict, msg: str) -> list[str]:
    done = []
    low = msg.lower()
    if re.search(r"9\s*[:：x]\s*16|vertical|直式|豎", low):
        plan_["format"].update(width=1080, height=1920)
        done.append(p.t("switched to vertical 9:16", "改成直式 9:16"))
    if re.search(r"16\s*[:：x]\s*9|horizontal|橫式", low):
        plan_["format"].update(width=1920, height=1080)
        done.append(p.t("switched to 16:9", "改成橫式 16:9"))
    m = re.search(r"title[:：]\s*(.+)|片名[:：]\s*(.+)", msg, re.I)
    if m:
        plan_["title"] = short(m.group(1) or m.group(2), 40)
        done.append(p.t(f"title → {plan_['title']}", f"片名 → {plan_['title']}"))
    for eng in engines.ENGINES:
        names = {"painted-animation": r"watercolor|水彩", "crayon-storybook": r"crayon|蠟筆", "pixel-art": r"pixel|像素", "paper-cutout": r"paper|剪紙",
                 "whiteboard": r"whiteboard|白板", "anime-cel": r"anime|動畫風|賽璐璐", "hyperframes": r"vector|向量|flat"}[eng]
        if re.search(rf"({names})", low) and re.search(r"style|風格|look|改成|switch|make it", low):
            plan_["engine"] = eng
            plan_["look"]["medium"] = engines.engine_label(eng)
            done.append(p.t(f"engine → {engines.engine_label(eng)}", f"引擎 → {engines.engine_label(eng)}"))
    for sid in re.findall(r"\bS\d+\b", msg):
        s = next((x for x in plan_.get("shots") or [] if x["id"] == sid), None)
        if s:
            s["notes"] = (s.get("notes", "") + " " + msg).strip()[:400]
            done.append(p.t(f"note added to {sid}", f"已把意見記到 {sid}"))
    return done


async def replan(p: P) -> dict:
    plan_ = p.plan()
    msg = p.vars.get("message") or ""
    att = [p.path(a) for a in p.vars.get("attachments") or [] if IMG.search(a)]
    before = json.dumps(plan_.get("shots"), ensure_ascii=False)
    ai = await p.crew.ask_json(
        f"{ROLE}\n{RULES}\n{p.lang_rule()}",
        f"""The user commented on the plan. Revise it.
User: {msg}

Current plan: {compact_plan(plan_, with_scene=True)[:9000]}
Allowed values — {ENUMS}; engines: {', '.join(engines.ENGINES)}

Reply JSON with ONLY what changes:
{{"thinking": "...", "reply": ["one line per request: what you changed, or why not + alternative"],
 "title": "...", "logline": "...", "engine": "...", "format": {{"width": 1920, "height": 1080}},
 "look": {{"palette": ["#hex"], "color_arc": "..."}},
 "characters": [{{"id": "...", "name": "...", "design": "...", "arc": "..."}}],
 "shots": [{{"id": "S3", "seconds": 3.5, "summary": "...", "action": "...", "setting": "...", "time": "day", "actors": [{{"id": "...", "action": "...", "expression": "..."}}],
            "props": ["..."], "fx": ["..."], "text": "...", "narration": "...", "transition_in": "...", "camera": {{"move": "...", "pace": "slow|medium|fast"}}}}],
 "add_shots_after": [{{"after": "S4", "shot": {{...same fields as a shot...}}}}], "remove_shots": ["S7"],
 "open_questions": ["..."]}}""",
        images=att)
    replies: list[str] = []
    if isinstance(ai, dict):
        replies = [short(x, 200) for x in ai.get("reply") or [] if isinstance(x, str)]
        if ai.get("engine") in engines.ENGINES:
            plan_["engine"] = ai["engine"]
            plan_["look"]["medium"] = engines.engine_label(ai["engine"])
        if isinstance(ai.get("format"), dict) and ai["format"].get("width") and ai["format"].get("height"):
            plan_["format"].update(width=int(secs(ai["format"]["width"], 1920)), height=int(secs(ai["format"]["height"], 1080)))
        merged = _merge_ai_plan(plan_, {k: v for k, v in ai.items() if k in ("title", "logline", "look", "characters", "shots", "open_questions")}, p, by_index=False)
        # keep chars that weren't mentioned (AI may send a partial list)
        if ai.get("characters"):
            old = {c["id"]: c for c in plan_.get("characters") or []}
            new = {c["id"]: c for c in merged.get("characters") or []}
            merged["characters"] = list({**old, **new}.values())[:4]
        else:
            merged["characters"] = plan_.get("characters")
        plan_ = merged
        for s in ai.get("shots") or []:
            if isinstance(s, dict) and s.get("id") and isinstance(s.get("seconds"), (int, float)):
                x = next((y for y in plan_["shots"] if y["id"] == s["id"]), None)
                if x:
                    x["end_s"] = x["start_s"] + max(0.6, min(10, float(s["seconds"])))
                    if isinstance(s.get("camera"), dict):
                        x["camera"] = {**x.get("camera", {}), **{k: v for k, v in s["camera"].items() if k in ("move", "pace")}}
        for rid in ai.get("remove_shots") or []:
            plan_["shots"] = [s for s in plan_["shots"] if s["id"] != rid]
        for add in ai.get("add_shots_after") or []:
            if not isinstance(add, dict) or not isinstance(add.get("shot"), dict):
                continue
            idx = next((i for i, s in enumerate(plan_["shots"]) if s["id"] == add.get("after")), len(plan_["shots"]) - 1)
            prev = plan_["shots"][idx] if plan_["shots"] else {"camera": {"move": "static"}, "scene": {"setting": "room"}}
            n = max([int(re.sub(r"\D", "", s["id"]) or 0) for s in plan_["shots"]] + [0]) + 1
            new = {**json.loads(json.dumps(prev)), "id": f"S{n}", "start_s": 0, "end_s": max(0.8, secs(add["shot"].get("seconds"), 2.5)), "text_overlay": []}
            tmp = _merge_ai_plan({**plan_, "shots": [new]}, {"shots": [{**add["shot"], "id": new["id"]}]}, p)
            plan_["shots"].insert(idx + 1, tmp["shots"][0])
    else:
        replies = _builtin_replan(p, plan_, msg) or [p.t("Noted. (Built-in rules can't rewrite the story text; pick an AI crew for that.)",
                                                          "收到。（內建規則無法改寫故事文字，要改內容請選一個 AI 導演。）")]
    retime(plan_)
    plan_["version"] = int(plan_.get("version") or 1) + 1
    plan_.setdefault("changelog", []).append(p.t(f"v{plan_['version']}: {short(msg, 50)}", f"v{plan_['version']}：{short(msg, 40)}"))
    p.write("plan.json", plan_)
    p.write_text("STORYBOARD.md", storyboard_md(plan_, p.lang))
    if json.dumps(plan_.get("shots"), ensure_ascii=False) != before or isinstance(ai, dict):
        cast = load_cast(p, plan_)
        for c in plan_.get("characters") or []:
            if not p.path(c["file"]).exists():
                p.write(c["file"], rig.from_description(c["id"], c.get("name") or c["id"], c.get("design") or ""))
        cast = load_cast(p, plan_)
        ids = list(cast)
        shots = {s["id"]: s for s in plan_["shots"]}
        pick = [sid for sid in plan_.get("style_frame_shots") or [] if sid in shots] or [s["id"] for s in plan_["shots"][:3]]
        frames = []
        for i, sid in enumerate(pick[:4]):
            spec = scene.normalize_spec(None, scene.draft_spec(shots[sid], plan_, ids), ids)
            rel = f"out/check/style_{i + 1}.jpg"
            await p.run(render_still, p, spec, spec["duration"] * 0.6, rel, plan_, cast)
            frames.append(rel)
        plan_["style_frames"] = frames
        p.write("plan.json", plan_)
    return {"ok": True, "text": "\n".join(f"- {r}" for r in replies) + "\n" + p.t(f"Plan is now v{plan_['version']}.", f"企劃更新為 v{plan_['version']}。")}
