"""Films: prompt → animation, in the seven stages of the storyboard workflow ("lock the look, storyboard, animate
each frame separately, design the sound, assemble"). A film is a series of kind "film" with one episode of one part,
so it runs on the Series engine (approvals, scene graph, compiler, shot QA, sound, shot tools).

    1 breakdown    your prompt (text with time codes like "0–3 sec" / "SHOT 1 (0.00–1.00s)", or JSON) → timed shots,
                   characters, world, camera, audio map, continuity rules                         → script.json
    2 lock         characters (sheet + voice, or from your library) + world reference pictures    → consistency_manifest.json
    3 storyboard   one frame per shot + a numbered collage, approved before anything moves        → storyboard/
    4 motion       per-shot blueprint (camera, timed actions, effects) on the timeline            → motion_blueprint.json
    5 prompts      compiled per model from the frame + sheets + world + blueprint                 → prompts/shot_NN.txt
    6 render       one clip per shot; any one redone                                              → renders/clip_NN.mp4
    7 edit bay     timed sound effects, ambience, music, the master                               → final/

`analyze()` reads the prompt with rules first (time codes, headings, camera words, sounds), then — with an AI crew —
asks the prompt analyst (skill avos-prompt-analyst) for the full breakdown, given that skeleton. Everything is
repaired by `normalize()`, so an AI answer, a JSON prompt or your edits all end up in the same shape.
"""
from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Any, Callable

from ..creative import dna as DNA, scene as SG
from . import store, writers

FRAMINGS = writers.FRAMINGS
EMOTIONS = writers.EMOTIONS
MAX_SHOT = 15.0
MIN_SHOT = 0.5

# ---------- reading a prompt with rules ----------
NUM = r"\d{1,3}(?::\d{2})?(?:\.\d+)?"
RANGE_RX = re.compile(rf"(?<![\w.:])({NUM})\s*(?:s|sec|secs|seconds)?\s*(?:–|—|-|to)\s*({NUM})\s*(s|sec|secs|seconds)?\b", re.I)
SHOT_RX = re.compile(r"^\W*(?:shot|scene|frame|beat)\s*#?\s*(\d{1,3})\b", re.I)
HEAD_RX = re.compile(r"^\W*(setting|environment|world|locations?|characters?|cast|audio|sound(?:s| design)?|music|style|look|"
                     r"rules|continuity|notes?|ending)\W*\s*(?::|$)\s*(.*)$", re.I)
DURATION_RX = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*-?\s*(?:second|sec)s?\b(?![^(]*\))", re.I)
QUOTE_RX = re.compile(r"(?:^|[\s(,;])([A-Z][\w'’ -]{0,24}?)\s*(?:says|said|shouts|yells|sings|whispers|asks|mutters|cries|replies|:)\s*[,:]?\s*[“\"]([^”\"]{1,240})[”\"]")
CAMERA_WORDS = [
    (r"whip[- ]?pan", "pan_right"), (r"pan(?:s|ning)? (?:to the )?left", "pan_left"), (r"pan(?:s|ning)? (?:to the )?right|camera pans|pans? across|panning", "pan_right"),
    (r"tilt(?:s|ing)? down|tilt down", "tilt_down"), (r"tilt(?:s|ing)? up|tilt up|\btilts?\b", "tilt_up"),
    (r"push(?:es|ing)?[- ]in|dolly(?:ies|ing)?[- ]in|dollies in|move(?:s)? in|creep(?:s)? in", "push_in"),
    (r"pull(?:s|ing)?[- ](?:back|out)|dolly(?:ies|ing)?[- ]out|dollies out", "pull_out"),
    (r"track(?:s|ing)? (?:shot )?(?:to the )?left|truck(?:s)? left", "truck_left"), (r"tracking|camera follows|follows (?:him|her|them|the)|truck(?:s)? right", "truck_right"),
    (r"orbit(?:s|ing)? left|arc(?:s)? left", "orbit_left"), (r"orbit|arc(?:s|ing)? around|circles around", "orbit_right"),
    (r"crane(?:s)? up|rises above|boom up|camera rises", "crane_up"), (r"crane(?:s)? down|boom down|camera lowers", "crane_down"),
    (r"zoom(?:s|ing)? in|crash zoom|\bzooms?\b", "zoom_in"), (r"handheld|shaky|shake", "handheld"), (r"static|locked[- ]off|still camera|holds still", "static"),
]
FRAMING_WORDS = [
    (r"over[- ]the[- ]shoulder|\bots\b", "over-the-shoulder"), (r"two[- ]shot", "two-shot"),
    (r"insert|detail shot|macro|extreme close[- ]up on (?:the |a |his |her )?(?:hand|plate|dish|food|object)", "insert"),
    (r"close[- ]up|closeup|\bcu\b|\becu\b", "close-up"), (r"medium|mid[- ]shot|waist", "medium"),
    (r"wide|establishing|long shot|full shot", "wide"),
]
SOUND_WORDS = ("splash", "engine", "rumble", "roar", "whoosh", "sizzl", "chop", "drip", "plop", "footstep", "knock", "crash", "bang", "thud",
               "honk", "horn", "laugh", "giggle", "bird", "wind", "rain", "thunder", "sparkle", "ding", "pop", "creak", "clink", "slurp",
               "munch", "gasp", "sigh", "applause", "splat", "swoosh", "screech", "beep", "buzz", "ring", "whistle", "boom", "clang", "snap")
PEOPLE = ("grandma", "grandmother", "grandpa", "old lady", "lady", "chef", "wolf", "rabbit", "bunny", "fox", "bear", "cat", "dog", "puppy",
          "kitten", "mouse", "lion", "tiger", "monkey", "panda", "owl", "duck", "frog", "dragon", "robot", "boy", "girl", "man", "woman",
          "king", "queen", "princess", "prince", "witch", "wizard", "farmer", "teacher", "police officer", "doctor", "pig", "cow",
          "horse", "elephant", "penguin", "squirrel", "turtle", "alien", "ghost", "mother", "father", "mom", "dad")


def _secs(v: str) -> float:
    if ":" in v:
        m, s = v.split(":", 1)
        return int(m) * 60 + float(s)
    return float(v)


def _range(line: str) -> tuple[float, float, int, int] | None:
    """A time range near the start of a line ("0–3 SECONDS", "SHOT 2 (1.00–2.00s)", "[0:03-0:05]")."""
    m = RANGE_RX.search(line[:60])
    if not m:
        return None
    a, b = m.group(1), m.group(2)
    if not m.group(3) and ":" not in a + b and not re.search(r"\b(?:sec|shot|scene|frame)", line[:m.start()] + line[m.end():m.end() + 10], re.I):
        return None
    try:
        start, end = _secs(a), _secs(b)
    except ValueError:
        return None
    return (start, end, m.start(), m.end()) if end > start else None


def detect_move(text: str) -> str | None:
    t = text.lower()
    for rx, mv in CAMERA_WORDS:
        if re.search(rx, t):
            return mv
    return None


def detect_framing(text: str) -> str | None:
    t = text.lower()
    for rx, fr in FRAMING_WORDS:
        if re.search(rx, t):
            return fr
    return None


def detect_angle(text: str) -> str | None:
    t = text.lower()
    if re.search(r"low[- ]angle|worm|from below|looking up at", t):
        return "low angle"
    if re.search(r"high[- ]angle|from above|looking down", t):
        return "high angle"
    if re.search(r"overhead|bird'?s?[- ]eye|top[- ]down|aerial", t):
        return "overhead"
    if re.search(r"eye[- ]level", t):
        return "eye level"
    return None


def detect_lens(text: str) -> int | None:
    t = text.lower()
    if re.search(r"fish[- ]?eye|ultra[- ]wide", t):
        return 14
    if re.search(r"wide[- ](?:angle )?lens|wide[- ]angle", t):
        return 20
    if re.search(r"telephoto|long lens|zoom lens", t):
        return 100
    m = re.search(r"\b(\d{2,3})\s?mm\b", t)
    return int(m.group(1)) if m else None


def detect_sounds(text: str) -> list[str]:
    out = []
    for m in re.finditer(r"\b((?:" + "|".join(SOUND_WORDS) + r")[\w-]*)\b", text.lower()):
        w = m.group(1)
        if w not in out and not w.startswith(("popular", "ringlet", "drippy")):
            out.append(w)
    return out[:4]


def skeleton(prompt: str) -> dict[str, Any]:
    """The prompt's structure by rules: intro, named sections, timed sections (shots), the stated length."""
    lines = (prompt or "").replace("\r", "").split("\n")
    intro: list[str] = []
    heads: dict[str, list[str]] = {}
    shots: list[dict] = []
    cur: list[str] | None = None
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        rg = _range(line)
        sm = SHOT_RX.match(line)
        hm = HEAD_RX.match(line) if not rg else None
        if not rg and sm and (op := re.search(rf"({NUM})\s*s?\s*(?:–|—|-|to)\s*(?:end|the end)\b", line[:60], re.I)):
            rg = (_secs(op.group(1)), None, op.start(), op.end())         # "SHOT 15 (14.00s – end)"
        if rg or (sm and not hm):
            body = (line[rg[3]:] if rg else line[sm.end():]).strip(" )]:–—-*#.")
            label = line[:rg[2]].strip(" ([*#-") if rg else line[:sm.end()].strip(" *#")
            shots.append({"start": rg[0] if rg else None, "end": rg[1] if rg else None, "label": label[:40], "text": body})
            cur = None
            continue
        if hm:
            key = hm.group(1).lower()
            key = {"environment": "setting", "world": "setting", "location": "setting", "locations": "setting", "character": "characters",
                   "cast": "characters", "sound": "audio", "sounds": "audio", "sound design": "audio", "music": "audio", "look": "style",
                   "continuity": "rules", "note": "rules", "notes": "rules"}.get(key, key)
            cur = heads.setdefault(key, [])
            if hm.group(2).strip():
                cur.append(hm.group(2).strip())
            continue
        if cur is not None:
            cur.append(line)
        elif shots:
            shots[-1]["text"] = (shots[-1]["text"] + " " + line).strip()
        else:
            intro.append(line)
    whole = " ".join(intro)
    dur = None
    m = DURATION_RX.search(whole) or DURATION_RX.search(prompt[:400])
    if m:
        dur = float(m.group(1))
    ends = [x["end"] for x in shots if x.get("end")] + [x["start"] for x in shots if x.get("start") is not None]
    if ends:
        dur = max(ends) if not dur or abs(max(ends) - dur) > 1.5 else dur
    return {"intro": whole, "sections": {k: "\n".join(v) for k, v in heads.items()}, "shots": shots, "duration": dur}


def _who_in(text: str) -> list[str]:
    t = " " + text.lower() + " "
    return [p for p in PEOPLE if re.search(rf"\b{re.escape(p)}s?\b", t)]


def builtin_breakdown(prompt: str, sk: dict | None = None) -> dict:
    """No AI: the skeleton fleshed out with the rule detectors (enough to run the whole film offline)."""
    sk = sk or skeleton(prompt)
    secs = sk["sections"]
    chars: list[dict] = []
    for para in re.split(r"\n+|(?<=[.!?])\s+(?=(?:A|An|The)\s)", secs.get("characters", "")):
        para = para.strip(" -*•\t")
        if len(para) < 3:
            continue
        m = re.match(r"^([A-Z][\w'’ ]{0,24}?)\s*[:\-–—(]\s*(.*)$", para)
        if m and not re.match(r"^(A|An|The)\b", m.group(1)):
            name, look = m.group(1).strip(), m.group(2).strip(" )")
        else:
            nouns = _who_in(para)
            name, look = (nouns[0].title() if nouns else f"Character {len(chars) + 1}"), para
        if name.lower() not in {c["name"].lower() for c in chars}:
            chars.append({"name": name, "look": look[:600]})
    if not chars:
        for n in _who_in(sk["intro"] + " " + " ".join(x["text"] for x in sk["shots"]))[:3]:
            chars.append({"name": n.title(), "look": f"a {n}"})
    setting = secs.get("setting") or ""
    locs = [{"name": (re.split(r"[,.;:]", setting)[0][:40].strip() or "The place"), "description": setting[:400] or sk["intro"][:300]}]
    raw = sk["shots"]
    if not raw:
        paras = [p for p in re.split(r"(?<=[.!?])\s+", sk["intro"]) if len(p) > 12][1:] or [sk["intro"] or prompt[:300]]
        raw = [{"start": None, "end": None, "text": p} for p in paras[:12]]
    shots = []
    names = {c["name"].lower(): c["name"] for c in chars}
    for i, x in enumerate(raw):
        text = x["text"]
        who = [names[n] for n in names if re.search(rf"\b{re.escape(n)}\b", text.lower())] or \
              [c["name"] for c in chars if any(w in c["look"].lower() for w in _who_in(text))]
        dialogue = []
        for m in QUOTE_RX.finditer(text):
            sp = next((names[n] for n in names if re.search(rf"\b{re.escape(n)}\b", m.group(1).lower())), None)
            if sp is None:
                sp = next((c["name"] for c in chars if any(w in c["look"].lower() for w in _who_in(m.group(1)))), None)
            if sp:
                dialogue.append({"character": sp, "text": m.group(2).strip(), "emotion": "neutral"})
        head, _, rest = text.partition(":")
        direction = bool(rest.strip()) and len(head) <= 90 and bool(detect_framing(head) or detect_move(head) or detect_angle(head) or re.search(r"\bshot\b", head, re.I))
        action = rest.strip() if direction else text
        title = (head.strip(" –—-") if direction else " ".join(text.split()[:6]).rstrip(",.;:"))[:60]
        shots.append({"start": x.get("start"), "end": x.get("end"), "title": title or f"Shot {i + 1}", "action": action[:600],
                      "framing": detect_framing(text), "angle": detect_angle(text), "camera": detect_move(text), "lens": detect_lens(text), "characters": who,
                      "dialogue": dialogue, "sfx": [{"t": None, "sound": w} for w in detect_sounds(text)]})
    audio = secs.get("audio") or ""
    items = [a.strip() for a in re.split(r"[,;\n]", audio) if a.strip()]
    return {"title": "", "logline": sk["intro"][:300], "duration": sk["duration"], "style": _style_from(sk["intro"] + " " + secs.get("style", "")),
            "tone": "", "characters": chars, "locations": locs, "shots": shots,
            "audio": {"music": next((a for a in items if re.search(r"music|orchestra|score|theme|song", a, re.I)), ""),
                      "ambience": next((a for a in items if re.search(r"ambien|forest|birds|room tone|restaurant|city|crowd", a, re.I)), ""),
                      "events": []},
            "rules": [r.strip(" -•*") for r in re.split(r"\n+", secs.get("rules", "")) if r.strip()][:10]}


def _style_from(text: str) -> str:
    t = text.lower()
    bits = []
    for w, say in (("pixar", "3D Pixar-style animated film"), ("3d", "3D animated film" if "pixar" not in t else ""), ("2d", "2D animation"), ("anime", "anime style"),
                   ("claymation", "claymation"), ("stop-motion", "stop-motion"), ("cinematic", "cinematic lighting"),
                   ("watercolor", "watercolour look"), ("cartoon", "cartoon")):
        if say and w in t and say not in bits:
            bits.append(say)
    return ", ".join(bits[:3])


# ---------- JSON prompts ----------
def from_json(prompt: str) -> dict | None:
    """A JSON prompt (or one in a ```json fence): mapped straight into a breakdown when it lists shots."""
    raw = (prompt or "").strip()
    m = re.search(r"```(?:json)?\s*(.+?)```", raw, re.S)
    if m:
        raw = m.group(1).strip()
    if not raw.startswith(("{", "[")):
        return None
    try:
        d = json.loads(raw)
    except ValueError:
        return None
    if isinstance(d, list):
        d = {"shots": d}
    if not isinstance(d, dict):
        return None
    shots = d.get("shots") or d.get("timeline") or d.get("scenes") or d.get("frames")
    if not isinstance(shots, list) or not shots:
        if any(k in d for k in ("shot_id", "start", "duration")):
            shots = [d]
        else:
            return None
    known = {"shot_id", "id", "start", "end", "duration", "time", "camera", "framing", "shot", "angle", "lens", "action", "description",
             "text", "title", "location", "characters", "dialogue", "lines", "sfx", "sounds", "audio", "picture", "transition", "events"}
    out_shots = []
    for x in shots:
        if not isinstance(x, dict):
            continue
        cam = x.get("camera")
        cam_text = " ".join(str(v) for v in cam.values()) if isinstance(cam, dict) else str(cam or "")
        events = list(x.get("events") or [])
        for k, v in x.items():
            if k in known:
                continue
            if isinstance(v, dict):
                desc = ", ".join(f"{kk.replace('_', ' ')} {vv}" if not isinstance(vv, bool) else kk.replace("_", " ")
                                 for kk, vv in v.items() if vv not in (False, None, ""))
                events.append({"who": k, "action": desc})
            elif isinstance(v, str):
                events.append({"who": k, "action": v})
        start = x.get("start")
        end = x.get("end")
        if end is None and start is not None and x.get("duration") is not None:
            try:
                end = float(start) + float(x["duration"])
            except (TypeError, ValueError):
                end = None
        if isinstance(x.get("time"), str) and (rg := _range(x["time"] + " s")):
            start, end = rg[0], rg[1]
        action = str(x.get("action") or x.get("description") or x.get("text") or "") or "; ".join(f"{e['who']}: {e['action']}" for e in events)
        out_shots.append({"start": start, "end": end, "duration": x.get("duration"), "title": x.get("title") or x.get("shot_id") or x.get("id"),
                          "action": action, "framing": x.get("framing") or x.get("shot") or detect_framing(cam_text + " " + action),
                          "angle": x.get("angle") or detect_angle(cam_text) or (cam.get("angle") if isinstance(cam, dict) else None),
                          "camera": detect_move(cam_text) or (detect_move(action) if not cam_text else "static"),
                          "lens": x.get("lens") or (cam.get("lens") if isinstance(cam, dict) else None), "location": x.get("location"),
                          "characters": x.get("characters"), "dialogue": x.get("dialogue") or x.get("lines"), "picture": x.get("picture"),
                          "events": events, "sfx": x.get("sfx") or x.get("sounds"), "transition": x.get("transition")})
    chars = d.get("characters") or []
    if isinstance(chars, dict):
        chars = [{"name": k, **(v if isinstance(v, dict) else {"look": str(v)})} for k, v in chars.items()]
    who_ids = {str(e.get("who")) for s_ in out_shots for e in s_["events"] if e.get("who")}
    if not chars:
        chars = [{"name": w.replace("_", " ").title(), "look": w.replace("_", " ")} for w in sorted(who_ids)
                 if any(p in w.lower() for p in PEOPLE)]
    setting = d.get("setting") or d.get("world") or d.get("environment") or d.get("location")
    locs = d.get("locations") or ([{"name": (setting.get("name") if isinstance(setting, dict) else str(setting).split(",")[0])[:40],
                                    "description": json.dumps(setting) if isinstance(setting, dict) else str(setting)}] if setting else [])
    return {"title": d.get("title") or "", "logline": d.get("logline") or d.get("story") or "", "duration": d.get("duration"),
            "style": d.get("style") or "", "tone": d.get("tone") or "", "characters": chars, "locations": locs, "shots": out_shots,
            "audio": d.get("audio") if isinstance(d.get("audio"), dict) else {"music": str(d.get("music") or ""), "ambience": "", "events": []},
            "rules": d.get("rules") or []}


# ---------- the AI prompt analyst ----------
ANALYST_SYS = """You are the prompt analyst of an animation studio. Turn the creator's animation prompt into a production
breakdown: the story, every character (a precise visual identity: species, face, body, outfit with colours,
accessories, vehicles or props they always have), the world (place, materials, atmosphere, light), and a list of
SHOTS with exact start/end seconds. Keep the creator's time sections exactly; split a section only when it has
clearly separate camera set-ups. For each shot give framing, camera angle, camera move, what is seen in the first
frame, the timed actions inside it (seconds from the shot's start), any dialogue (kept word for word) and timed
sound effects. Collect the audio direction (music, ambience) and the continuity rules. Never invent a different
story; only fill in what the prompt implies."""

BD_SCHEMA = ('{"title": "", "logline": "", "duration": 15, "style": "one line: medium, look, lighting", "tone": "", '
             '"characters": [{"name": "", "species": "", "look": "face, body, colours", "outfit": "", "props": "vehicle / accessories", '
             '"personality": "", "voice": "age, pitch, attitude", "gender": "male|female|other", "actions": ["drive", "sing"]}], '
             '"locations": [{"name": "", "description": "environment, materials, atmosphere, light"}], '
             '"shots": [{"start": 0, "end": 3, "title": "", "location": "", "framing": "' + "|".join(FRAMINGS) + '", '
             '"angle": "eye level|low angle|high angle|overhead", "camera": "' + "|".join(SG.MOVES) + '", "lens": 35, '
             '"characters": ["names"], "picture": "the first frame", "action": "what happens", '
             '"events": [{"t": 0.0, "who": "name or null", "action": ""}], '
             '"dialogue": [{"character": "", "text": "", "emotion": "' + "|".join(EMOTIONS) + '"}], '
             '"sfx": [{"t": 1.2, "sound": ""}], "transition": "cut|time jump|match cut|fade"}], '
             '"audio": {"music": "", "ambience": "", "events": [{"t": 0, "sound": ""}]}, "rules": [""]}')


def analyze(s: dict, prompt: str, note: str = "", log: Callable[[dict], None] | None = None) -> dict:
    """The breakdown of a film prompt: JSON prompts map directly; otherwise the AI analyst (or the rules)."""
    j = from_json(prompt)
    if j is not None:
        return normalize(j, s)
    sk = skeleton(prompt)
    if writers.uses_ai(s):
        lg = writers.languages.get(s.get("language") or "en")
        ask_prompt = (f"The creator's prompt:\n<<<\n{prompt[:16000]}\n>>>\n\n"
                      f"What the rules found (keep these times): {json.dumps({'duration': sk['duration'], 'shots': [{k: x[k] for k in ('start', 'end', 'label')} for x in sk['shots']], 'sections': list(sk['sections'])}, ensure_ascii=False)}\n"
                      f"Dialogue stays word for word; new dialogue (only if asked) is in {lg.name}. Everything else in English.\n"
                      + (f"Characters from the creator's library (use these exact names when the prompt means them): "
                         f"{', '.join(n for n in lib_names)}\n" if (lib_names := _library_names(s)) else "")
                      + (f"The creator's note on your last breakdown: {note}\n" if note else "")
                      + f"\nAnswer as JSON: {BD_SCHEMA}")
        data = writers.ask(s, "prompt analyst", writers.system("avos-prompt-analyst", ANALYST_SYS), ask_prompt, log, max_tokens=9000, temperature=0.3)
        ok = isinstance(data, dict) and bool(data.get("shots"))
        writers.need(s, ok, "breakdown of your prompt")
        if ok:
            bd = normalize(data, s)
            if sk["shots"] and all(x.get("start") is not None for x in sk["shots"]) and len(bd["shots"]) < len(sk["shots"]):
                pass        # the analyst merged sections: still usable, the creator can split them on the breakdown
            return bd
    return normalize(builtin_breakdown(prompt, sk), s)


def _library_names(s: dict) -> list[str]:
    from . import library
    return [library.load(x)["name"] for x in s.get("libraryPicks") or [] if library.exists(x)]


# ---------- the one shape everything ends up in ----------
def _f(v: Any, default: float | None = None) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _s(v: Any, n: int = 400) -> str:
    return str(v).strip()[:n] if v is not None and not isinstance(v, (dict, list)) else ""


def normalize(d: dict, s: dict | None = None) -> dict:
    """Repair any breakdown (AI answer, JSON prompt, the creator's edits): names unique, times contiguous and positive,
    every shot's framing / angle / move valid, events and sounds inside the shot, characters and places that exist."""
    d = d if isinstance(d, dict) else {}
    chars: list[dict] = []
    for c in d.get("characters") or []:
        if isinstance(c, str):
            c = {"name": c}
        if not isinstance(c, dict) or not _s(c.get("name"), 40):
            continue
        name = _s(c["name"], 40)
        if name.lower() in {x["name"].lower() for x in chars}:
            continue
        g = _s(c.get("gender"), 10).lower()
        acts = c.get("actions") if isinstance(c.get("actions"), list) else []
        look = _s(c.get("look") or c.get("description") or c.get("appearance"), 600)
        if c.get("species") and _s(c["species"], 60).lower() not in look.lower():
            look = (_s(c["species"], 60) + (", " + look if look else "")).strip(", ")
        chars.append({"name": name, "look": look, "outfit": _s(c.get("outfit") or c.get("clothing"), 300), "props": _s(c.get("props") or c.get("vehicle"), 300),
                      "personality": _s(c.get("personality"), 300), "voice": _s(c.get("voice"), 300), "gender": g if g in ("male", "female") else "other",
                      "age": _s(c.get("age"), 20), "actions": [_s(a, 60) for a in acts if _s(a, 60)][:12],
                      **({"library": _s(c["library"], 60)} if c.get("library") else {})})
    locs: list[dict] = []
    for x in d.get("locations") or []:
        if isinstance(x, str):
            x = {"name": x[:40], "description": x}
        if isinstance(x, dict) and _s(x.get("name"), 40) and _s(x["name"], 40).lower() not in {y["name"].lower() for y in locs}:
            locs.append({"name": _s(x["name"], 40), "description": _s(x.get("description"), 600)})
    if not locs:
        locs = [{"name": "The place", "description": _s(d.get("setting"), 600) or "where the story happens"}]
    names = {c["name"].lower(): c["name"] for c in chars}
    lnames = {x["name"].lower(): x["name"] for x in locs}

    def who(v: Any) -> str | None:
        v = _s(v, 40).lower()
        if not v:
            return None
        if v in names:
            return names[v]
        return next((names[n] for n in names if n in v or v in n), None)
    raw = [x for x in d.get("shots") or [] if isinstance(x, dict)]
    shots: list[dict] = []
    t = 0.0
    want_total = _f(d.get("duration"))
    for i, x in enumerate(raw):
        s0, e0, d0 = _f(x.get("start")), _f(x.get("end")), _f(x.get("duration"))
        if s0 is not None and e0 is not None and e0 > s0:
            dur = e0 - s0
        elif d0:
            dur = d0
        elif want_total and want_total > t + 0.5:
            dur = max(1.0, (want_total - t) / max(1, len(raw) - i))
        else:
            dur = 2.0 if want_total and t >= want_total - 0.5 else 3.0
        dur = round(max(MIN_SHOT, min(MAX_SHOT, dur)), 2)
        start = round(t, 2)                         # contiguous: a gap or an overlap is closed, the shot keeps its length
        end = round(start + dur, 2)
        orig = s0 if s0 is not None else start      # events / sounds written in film time are moved inside the shot

        def inside(v: Any) -> float | None:
            v = _f(v)
            if v is None:
                return None
            if v > dur + 0.01 and orig <= v <= orig + dur + 0.01:
                v -= orig
            return round(max(0.0, min(dur, v)), 2)
        text = _s(x.get("action") or x.get("text") or x.get("description"), 800)
        framing = _s(x.get("framing"), 30).lower()
        framing = framing if framing in FRAMINGS else (detect_framing(framing + " " + text) or ("wide" if i == 0 else "medium"))
        cam = x.get("camera")
        mv = _s(cam.get("move") if isinstance(cam, dict) else cam, 40).lower().replace(" ", "_").replace("-", "_")
        mv = {"dolly_in": "push_in", "dolly_out": "pull_out", "tracking": "truck_right", "track": "truck_right", "slow_push_in": "push_in",
              "pan": "pan_right", "tilt": "tilt_up", "zoom": "zoom_in", "orbit": "orbit_right", "whip_pan": "pan_right"}.get(mv, mv)
        if mv not in SG.MOVES:
            mv = detect_move(mv.replace("_", " ") + " " + text) or "static"
        ease = _s(cam.get("ease") if isinstance(cam, dict) else x.get("ease"), 20)
        lens = _f(x.get("lens") or (cam.get("lens") if isinstance(cam, dict) else None))
        loc = lnames.get(_s(x.get("location"), 40).lower()) or next((lnames[n] for n in lnames if n in _s(x.get("location"), 200).lower()), None) \
            or (shots[-1]["location"] if shots else locs[0]["name"])
        cs = [n for n in (who(c) for c in (x.get("characters") or [])) if n]
        dialogue = []
        for ln in x.get("dialogue") or []:
            if isinstance(ln, str):
                m = re.match(r"^\s*([^:]{1,30}):\s*(.+)$", ln)
                ln = {"character": m.group(1), "text": m.group(2)} if m else {"character": cs[0] if cs else "", "text": ln}
            if not isinstance(ln, dict) or not _s(ln.get("text"), 400):
                continue
            sp = who(ln.get("character") or ln.get("speaker"))
            if not sp:
                continue
            emo = _s(ln.get("emotion"), 20).lower()
            dialogue.append({"character": sp, "text": _s(ln["text"], 400).strip("“”\""), "emotion": emo if emo in EMOTIONS else "neutral"})
        for ln in dialogue:
            if ln["character"] not in cs:
                cs.append(ln["character"])
        if not cs:
            cs = [names[n] for n in names if re.search(rf"\b{re.escape(n)}\b", text.lower())]
        events = []
        for e in x.get("events") or []:
            if not isinstance(e, dict) or not _s(e.get("action") or e.get("text"), 200):
                continue
            events.append({"t": inside(e.get("t")) or 0.0, "who": who(e.get("who") or e.get("target")), "action": _s(e.get("action") or e.get("text"), 200)})
        sfx = []
        for e in (x.get("sfx") or []) if isinstance(x.get("sfx"), list) else ([{"sound": x["sfx"]}] if _s(x.get("sfx")) else []):
            if isinstance(e, str):
                e = {"sound": e}
            if isinstance(e, dict) and _s(e.get("sound") or e.get("text"), 120):
                sfx.append({"t": inside(e.get("t")), "sound": _s(e.get("sound") or e.get("text"), 120)})
        tr = _s(x.get("transition"), 20).lower()
        shots.append({"id": f"sh{len(shots) + 1:02d}", "start": round(start, 2), "end": end, "title": _s(x.get("title"), 60) or f"Shot {len(shots) + 1}",
                      "location": loc, "framing": framing, "angle": SG.angle_of(x.get("angle") or detect_angle(text) or ""),
                      "camera": mv, **({"ease": ease} if ease in SG.EASES else {}), **({"lens": int(max(12, min(200, lens)))} if lens else {}),
                      "characters": cs[:4], "picture": _s(x.get("picture"), 600), "action": text, "events": events[:8], "dialogue": dialogue[:4],
                      "sfx": sfx[:6], "transition": tr if tr in ("cut", "time jump", "match cut", "fade") else "cut"})
        t = end
        if len(shots) >= 40:
            break
    audio = d.get("audio") if isinstance(d.get("audio"), dict) else {}
    aev = []
    for e in audio.get("events") or []:
        if isinstance(e, dict) and _s(e.get("sound"), 120):
            aev.append({"t": round(max(0.0, _f(e.get("t"), 0.0) or 0.0), 2), "sound": _s(e["sound"], 120)})
    total = round(shots[-1]["end"], 2) if shots else 0.0
    rules = d.get("rules") if isinstance(d.get("rules"), list) else ([d["rules"]] if _s(d.get("rules")) else [])
    out = {"title": _s(d.get("title"), 80), "logline": _s(d.get("logline"), 400), "duration": total, "style": _s(d.get("style"), 300),
           "tone": _s(d.get("tone"), 80), "characters": chars[:8], "locations": locs[:6], "shots": shots,
           "audio": {"music": _s(audio.get("music"), 300), "ambience": _s(audio.get("ambience"), 300), "events": aev[:20]},
           "rules": [_s(r, 200) for r in rules if _s(r, 200)][:12]}
    out["detected"] = detected(out)
    return out


def detected(bd: dict) -> dict:
    sh = bd.get("shots") or []
    return {"story": bool(bd.get("logline") or sh), "characters": len(bd.get("characters") or []), "locations": len(bd.get("locations") or []),
            "shots": len(sh), "camera": sum(1 for x in sh if x["camera"] != "static" or x["angle"] != "eye level"),
            "dialogue": sum(len(x["dialogue"]) for x in sh), "sounds": sum(len(x["sfx"]) for x in sh) + len(bd.get("audio", {}).get("events") or []),
            "music": bool((bd.get("audio") or {}).get("music")), "rules": len(bd.get("rules") or []), "seconds": bd.get("duration") or 0}


# ---------- breakdown → the film's cast, places and script ----------
def ids_by_name(s: dict) -> tuple[dict[str, str], dict[str, str]]:
    return ({c["name"].lower(): c["id"] for c in s.get("characters") or []}, {x["name"].lower(): x["id"] for x in s.get("locations") or []})


def character_from(c: dict, taken: set[str], sample: str = "") -> dict:
    cid = store.slug(c["name"], taken)
    look = c.get("look") or c["name"]
    if c.get("props"):
        look = f"{look}. Always with: {c['props']}"
    return {"id": cid, "name": c["name"], "role": "lead", "age": c.get("age") or "", "gender": c.get("gender") or "other",
            "personality": c.get("personality") or "", "look": look[:600], "outfit": c.get("outfit") or "", "catchphrase": "",
            "voice": {"description": c.get("voice") or "", **({"sampleText": sample[:200]} if sample else {})},
            "status": "drafting", "version": 0, "history": [], "notes": [], "actions": c.get("actions") or []}


def first_line(bd: dict, name: str) -> str:
    return next((ln["text"] for x in bd.get("shots") or [] for ln in x["dialogue"] if ln["character"] == name), "")


def _sfx_text(items: list[dict]) -> str:
    return "; ".join(f"{e['sound']}" + (f" at {e['t']:.1f}s" if e.get("t") is not None else "") for e in items)


def script_from(s: dict, bd: dict) -> dict:
    """Each breakdown shot → one beat (a shot with two lines → two beats sharing its time), with the shot's camera,
    angle, timed events and sounds as the director's hint; consecutive shots in one place → one scene."""
    cids, lids = ids_by_name(s)
    lip_framings = ("close-up", "medium", "two-shot", "over-the-shoulder")
    global_sfx = list((bd.get("audio") or {}).get("events") or [])
    scenes: list[dict] = []
    for x in bd.get("shots") or []:
        lid = lids.get(x["location"].lower()) or (s.get("locations") or [{"id": "home"}])[0]["id"]
        if not scenes or scenes[-1]["location"] != lid or x.get("transition") == "time jump":
            scenes.append({"location": lid, "time": _time_of(x, bd), "characters": [], "beats": []})
        sc = scenes[-1]
        dur = round(x["end"] - x["start"], 2)
        subj = [cids[n.lower()] for n in x["characters"] if n.lower() in cids]
        sfx = list(x["sfx"]) + [{"t": round(e["t"] - x["start"], 2), "sound": e["sound"]} for e in global_sfx if x["start"] <= e["t"] < x["end"]]
        hint = {"shot": x["id"], "start": x["start"], "framing": x["framing"], "angle": x["angle"], "camera": {"move": x["camera"], **({"ease": x["ease"]} if x.get("ease") else {})},
                **({"lens": x["lens"]} if x.get("lens") else {}), "picture": x.get("picture") or "", "subjects": subj,
                "events": [{"t": e["t"], "who": cids.get((e.get("who") or "").lower()), "action": e["action"]} for e in x["events"]],
                "sfx": _sfx_text(sfx), "title": x.get("title") or ""}
        lines = [ln for ln in x["dialogue"] if ln["character"].lower() in cids]
        if lines:
            share = round(dur / len(lines), 2)
            for ln in lines:
                h = {**hint, "lipsync": x["framing"] in lip_framings}
                sc["beats"].append({"type": "line", "character": cids[ln["character"].lower()], "text": ln["text"], "emotion": ln["emotion"],
                                    "action": x["action"][:200], "seconds": share, "fixed": True, "shot": x["id"], "hint": h})
        else:
            sc["beats"].append({"type": "action", "text": x["action"] or x.get("picture") or x["title"], "characters": subj,
                                "sfx": hint["sfx"][:200], "seconds": dur, "fixed": True, "shot": x["id"], "hint": hint})
        sc["characters"] = list(dict.fromkeys(sc["characters"] + subj))
    for i, sc in enumerate(scenes):
        sc["id"] = f"s{i + 1}"
        writers._ids(sc["beats"], i + 1)
    return {"scenes": scenes}


def _time_of(x: dict, bd: dict) -> str:
    t = " ".join([x.get("action") or "", x.get("picture") or "", next((l["description"] for l in bd["locations"] if l["name"] == x["location"]), "")]).lower()
    for w, v in (("night", "night"), ("moon", "night"), ("sunset", "evening"), ("evening", "evening"), ("dusk", "evening"),
                 ("morning", "morning"), ("sunrise", "morning"), ("afternoon", "afternoon")):
        if w in t:
            return v
    return "day"


# ---------- the seven stages, for the page ----------
STAGES = [("breakdown", "Breakdown"), ("lock", "Characters & world"), ("storyboard", "Storyboard"), ("motion", "Motion"),
          ("prompts", "Prompts"), ("render", "Render"), ("edit", "Edit bay")]


def stages(s: dict, eps: list[dict]) -> list[dict]:
    bd = s.get("breakdown") or {}
    part = ((eps[0].get("parts") or [None])[0] if eps else None) or {}
    ep = eps[0] if eps else {}
    chars = s.get("characters") or []
    st = part.get("status")
    board_ok = bool(part.get("boardApprovedAt"))
    done = {
        "breakdown": bd.get("status") == "approved",
        "lock": bool(chars) and all(c.get("status") == "approved" for c in chars) and bd.get("status") == "approved",
        "storyboard": board_ok,
        "motion": board_ok, "prompts": board_ok,
        "render": st in ("review", "approved") and board_ok,
        "edit": ep.get("status") == "done",
    }
    working = {"breakdown": bd.get("status") == "analyzing", "lock": any(c.get("status") in ("drafting", "redo") for c in chars),
               "storyboard": st in ("queued", "rendering") and not board_ok, "render": st in ("queued", "rendering") and board_ok,
               "edit": ep.get("status") == "joining"}
    out, current = [], None
    for key, label in STAGES:
        state = "done" if done[key] else "working" if working.get(key) else "waiting"
        if state != "done" and current is None:
            current = key
            if state == "waiting":
                state = "yours" if _needs_you(key, s, part, ep) else "next"
        out.append({"key": key, "label": label, "state": state})
    return out


def _needs_you(key: str, s: dict, part: dict, ep: dict) -> bool:
    bd = s.get("breakdown") or {}
    return {"breakdown": bd.get("status") == "review", "lock": any(c.get("status") == "review" for c in s.get("characters") or []) or
            (bd.get("status") == "approved" and not ep), "storyboard": part.get("status") == "board_review",
            "render": part.get("status") == "review", "edit": part.get("status") == "review"}.get(key, False)


# ---------- the collage and the project files ----------
def collage(frames: list[tuple[Path, str]], out: Path, aspect: float = 16 / 9) -> Path | None:
    """The storyboard as one 16:9 sheet: every frame numbered with its time, like the storyboard in the workflow."""
    from PIL import Image, ImageDraw, ImageFont
    frames = [(p, label) for p, label in frames if p.is_file()]
    if not frames:
        return None
    n = len(frames)
    cols = 1 if n == 1 else 2 if n <= 4 else 3 if n <= 9 else 4 if n <= 16 else 5
    rows = -(-n // cols)
    W = 1920
    pad, cap = 16, 34
    tw = (W - pad * (cols + 1)) // cols
    th = int(tw / aspect)
    H = pad + rows * (th + cap + pad)
    sheet = Image.new("RGB", (W, H), (18, 18, 22))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 20)
    except OSError:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        except OSError:
            font = ImageFont.load_default()
    for i, (p, label) in enumerate(frames):
        r, c = divmod(i, cols)
        x, y = pad + c * (tw + pad), pad + r * (th + cap + pad)
        try:
            im = Image.open(p).convert("RGB")
        except Exception:  # noqa: BLE001 - an unreadable frame stays a grey box
            im = Image.new("RGB", (tw, th), (60, 60, 60))
        im = _cover(im, tw, th)
        sheet.paste(im, (x, y))
        draw.rectangle([x, y, x + 46, y + 32], fill=(245, 158, 11))
        draw.text((x + 8, y + 4), f"{i + 1:02d}", fill=(0, 0, 0), font=font)
        draw.text((x, y + th + 6), label[:70], fill=(230, 230, 230), font=font)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, "PNG")
    return out


def _cover(im: Any, w: int, h: int) -> Any:
    from PIL import Image
    k = max(w / im.width, h / im.height)
    im = im.resize((max(1, int(im.width * k + 0.5)), max(1, int(im.height * k + 0.5))), Image.LANCZOS)
    x, y = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


def manifest(s: dict) -> dict:
    """consistency_manifest.json: what must stay the same in every shot."""
    dna = DNA.normalize(s.get("dna"))
    return {"title": s.get("title"), "design_dna": dna, "style_clause": DNA.style_clause(dna), "palette": dna["palette"],
            "characters": [{"id": c["id"], "name": c["name"], "look": c.get("look"), "outfit": c.get("outfit"), "personality": c.get("personality"),
                            "voice": (c.get("voice") or {}).get("description"), "status": c.get("status"),
                            "sheet": f"assets/characters/{c['id']}_sheet.png" if c.get("sheet") else None} for c in s.get("characters") or []],
            "world": [{"id": x["id"], "name": x["name"], "description": x.get("description"),
                       "reference": f"assets/world/{x['id']}.png" if x.get("plate") else None} for x in s.get("locations") or []],
            "rules": (s.get("breakdown") or {}).get("rules") or [], "avoid": dna["avoid"]}


def export(sid: str, eid: str) -> Path:
    """Every stage's real output in one zip (the project folder of the storyboard workflow)."""
    from . import media
    s = store.load(sid)
    ep = store.load_ep(sid, eid)
    base = store.sdir(sid)
    out = base / "exports" / f"{eid}-project.zip"
    out.parent.mkdir(parents=True, exist_ok=True)
    names = media.names_of(s)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        def add(path: Path | None, arc: str) -> None:
            if path is not None and path.is_file():
                z.write(path, arc, compress_type=zipfile.ZIP_STORED if path.suffix in (".mp4", ".png", ".jpg") else zipfile.ZIP_DEFLATED)
        if s.get("prompt"):
            z.writestr("prompt.txt", s["prompt"])
        if s.get("breakdown"):
            z.writestr("breakdown.json", json.dumps(s["breakdown"], ensure_ascii=False, indent=1))
        z.writestr("script.json", json.dumps({"title": ep.get("title"), "parts": [p.get("script") for p in ep.get("parts") or []]}, ensure_ascii=False, indent=1))
        z.writestr("consistency_manifest.json", json.dumps(manifest(s), ensure_ascii=False, indent=1))
        for c in s.get("characters") or []:
            add(base / c["sheet"] if c.get("sheet") else None, f"assets/characters/{c['id']}_sheet.png")
            add(base / (c.get("voice") or {}).get("sample", "") if (c.get("voice") or {}).get("sample") else None, f"assets/characters/{c['id']}_voice.wav")
        for x in s.get("locations") or []:
            add(base / x["plate"] if x.get("plate") else None, f"assets/world/{x['id']}.png")
        blue, k, t0 = [], 0, 0.0
        for p in ep.get("parts") or []:
            pdir = store.part_dir(sid, eid, p["index"])
            add(pdir / "storyboard.png", "storyboard/collage_master.png" if len(ep["parts"]) == 1 else f"storyboard/collage_part{p['index']}.png")
            for sh in p.get("shots") or []:
                k += 1
                d = pdir / "shots" / sh["id"]
                add(d / "key.png", f"storyboard/frames/frame_{k:02d}.png")
                add(d / "clip.mp4", f"renders/clip_{k:02d}.mp4")
                add(d / "line.wav", f"audio/line_{k:02d}.wav")
                add(d / "sfx.wav", f"audio/sfx_{k:02d}.wav")
                m = sh.get("models") or {}
                z.writestr(f"prompts/shot_{k:02d}.txt",
                           f"# Shot {k:02d} ({sh['id']}) · {sh.get('framing')} · {sh.get('seconds')}s\n\n"
                           f"## Picture ({(m.get('key') or {}).get('model') or '—'})\n{(m.get('key') or {}).get('prompt') or media.keyframe_prompt(s, sh, [])}\n\n"
                           f"## Motion ({(m.get('clip') or {}).get('model') or '—'})\n{(m.get('clip') or {}).get('prompt') or media.motion_prompt(s, sh, 'wan-2.2')}\n\n"
                           f"## Negative\n{DNA.negative(s.get('dna') or {})}\n"
                           + (f"\n## Line ({names.get(sh.get('speaker') or '', '')})\n{sh.get('text')}\n" if sh.get("kind") == "dialogue" else "")
                           + (f"\n## Sound\n{sh.get('sfx')}\n" if sh.get("sfx") else ""))
                blue.append({"frame": k, "shot": sh["id"], "start": round(t0, 2), "end": round(t0 + float(sh.get("seconds") or 0), 2),
                             "duration": sh.get("seconds"), "kind": sh.get("kind"), "framing": sh.get("framing"), "camera": sh.get("camera"),
                             "speaker": names.get(sh.get("speaker") or "", None), "line": sh.get("text") if sh.get("kind") == "dialogue" else None,
                             "sfx": sh.get("sfx"), "scene_graph": sh.get("stage"), "blueprint": sh.get("blueprint")})
                t0 += float(sh.get("seconds") or 0)
            add(pdir / "music.wav", f"audio/music_part{p['index']}.wav")
        z.writestr("motion_blueprint.json", json.dumps({"fps": 24, "duration": round(t0, 2), "shots": blue}, ensure_ascii=False, indent=1))
        final = base / ep["video"] if ep.get("video") else (store.part_dir(sid, eid, 1) / "part.mp4" if (store.part_dir(sid, eid, 1) / "part.mp4").is_file() else None)
        if final is not None and final.is_file():
            add(final, "final/final_master.mp4")
            add(final.with_suffix(".srt"), "final/subtitles.srt")
            mix = out.parent / f"{eid}-audio_mix.wav"
            try:
                media._ff(["-i", str(final), "-vn", "-ac", "2", "-ar", "48000", "-c:a", "pcm_s16le", str(mix)], timeout=300)
                add(mix, "final/audio_mix.wav")
            except Exception:  # noqa: BLE001 - a master without sound: no mix file
                pass
        z.writestr("README.txt", README)
    return out


README = """AVOS film project files
=======================
prompt.txt                     your prompt (films)
breakdown.json                 stage 1: the prompt read into timed shots, characters, world, camera, audio, rules
script.json                    the script the shots were made from (beats, lines, actions)
consistency_manifest.json      stage 2: Design DNA (look, palette, camera + motion grammar), characters, world, rules
assets/characters/             the approved character sheets and voice samples
assets/world/                  the world / location reference pictures
storyboard/collage_master.png  stage 3: the numbered storyboard
storyboard/frames/             the clean first frame of every shot
motion_blueprint.json          stage 4: per shot start/end, camera move, timed actions, scene graph
prompts/shot_NN.txt            stage 5: exactly what each model was told
renders/clip_NN.mp4            stage 6: every shot's clip, as rendered
audio/                         lines, sound effects, music
final/final_master.mp4         stage 7: the master (with audio_mix.wav and subtitles.srt)
"""
