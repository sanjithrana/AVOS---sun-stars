"""The prompt library: every strong prompt the Explainer uses, versioned, measured, and improved from real results.

How it learns (nothing is replaced on a hunch):
  1. Every picture / clip / plan remembers which prompt VERSION made it.
  2. Outcomes are recorded: ok, flagged by the picture check (dark, blank, duplicate), failed because of the prompt itself,
     redone by you, or 👍 / 👎 from you. Network, key and billing errors are NOT blamed on a prompt.
  3. When a prompt version has enough uses and a high bad rate, an improved version is written (by your script writer, or by
     simple rules when there is none) and becomes a CANDIDATE used on about half of the next videos.
  4. After enough uses the candidate replaces the old prompt only if it is clearly better; otherwise it is dropped.
     Every version stays in the history and can be restored; you can also edit any prompt yourself.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from . import store

MIN_USES = 6            # uses before a prompt can be judged
BAD_RATE = 0.30         # judged weak at or above this share of bad results
MARGIN = 0.05           # a candidate must beat the old prompt by this much to replace it
MAX_TEXT = 2400
BAD, GOOD_GEN = ("flag", "failed"), ("ok",)

DIRECTOR = ("Write a production storyboard like a film director. Add at the top level: \"logline\" (one sentence), \"palette\" (5-6 objects "
            "{\"name\",\"hex\"} with real hex colours that fit the story, e.g. polished copper #B87333), \"camera_language\", \"lighting_note\", "
            "\"sound_design\" and \"narrative_note\" (one sentence each). For every shot ALSO fill these film fields, each a real sentence and "
            "different from shot to shot: \"camera_note\" (shot size, lens feel, movement, e.g. medium close-up, slow push-in, 50mm, shallow depth "
            "of field), \"lighting\" (light source, direction, warmth, e.g. warm afternoon sun from a side window, soft highlights on the copper), "
            "\"audio\" (ambient sound plus the exact sound effects, in order). For every shot add: \"scene\" (1,2,3… grouping shots into scenes, "
            "shots of one scene are consecutive), \"scene_title\" (a few words, same on every shot of the scene), \"mood\" (the light and colour of "
            "the moment, e.g. warm golden afternoon light, or cold blue after the ice cracks), and \"emotion\" (what the main character feels). "
            "\"action\" must be a full, concrete picture description: who is where, what they do with their hands, what the camera sees, what has "
            "changed since the last shot. List in \"characters\" ONLY the characters actually visible. Never add characters or animals the brief does "
            "not name. Keep each character's \"look\" exact and complete (face, colours, size, signature item) because it is pasted into every "
            "picture prompt. When a character on screen says the shot's line, set \"speaker\" to that character's id (the line is then spoken in their own "
            "voice and their lips are synced); leave \"speaker\" empty when a narrator speaks over the picture. ")

CINEMA = ("Make every shot COMPLETE: fill all 14 fields so the picture and video models have nothing to guess. For every shot add: \"objective\" (what the "
          "character is trying to do right now), \"angle\" (one of: eye_level, low_angle, high_angle, ground_level, shoulder_height, overhead, profile, "
          "three_quarter), \"composition\" (one of: rule_of_thirds, center, negative_space, symmetry, leading_lines, frame_within_frame, layers, "
          "asymmetrical_balance, blocking, movement_space), \"performance\" (eyes, gestures and reaction timing, e.g. eyes on the door, relief after one beat), "
          "\"end_state\" (the exact final pose or frame, e.g. door open, parcel in her hands) and \"continuity\" (what must stay unchanged, e.g. same "
          "raincoat, same rain, same parcel). \"camera_note\" is ONE camera move with distance and timing (e.g. slow 1 m push-in over 4 seconds), never several. "
          "Choose each angle for the feeling it should create: low angle = power, high angle = vulnerability, eye level = intimacy, ground level = scale. "
          "Avoid the common mistakes: no vague adjectives like 'epic' without a visible detail, no stacked camera moves in one shot, no missing end state, "
          "no characters or props that change between shots. "
          "Every shot must SHOW a change between its first and its last frame: write \"action\" as the movement with strong verbs (drops, slides, "
          "lifts, spins, lights up, turns to camera) and \"end_state\" as the frame after it, visibly different from the start. A shot where nobody and "
          "nothing moves is allowed only as the held final image. ")

STORY = ("If the idea is a story, a cartoon or a comedy, build it like a short film: ONE strong visual hook in the first three seconds that makes the "
         "viewer ask a question; every action follows from the one before (set up what a later beat needs, e.g. he must leave the throne before the "
         "monkey can take it); each beat says what happens, how each character reacts and how it leads to the next; escalation where each scene raises "
         "the stakes or the chaos; one misunderstanding or false hope, then a reveal or twist that changes what the viewer thought; a payoff in the last "
         "shot held on a clear final image. Physical comedy must read at a glance: exaggerated, readable poses, the setup shown before the joke lands. "
         "In a story there is NO narrator unless the brief asks for one: set \"narration_mode\" to \"dialogue\" (or \"none\"), put only lines an on-screen "
         "character says in \"narration\" with \"speaker\" set, at most two or three short lines in the whole film, and leave \"narration\" empty in the "
         "other shots. Write each shot's sounds in \"audio\" (whooshes, squeaks, footsteps, ambience). ")

EXPLAIN = ("For an explainer, show the hidden mechanism as a world: travel inside the object, or give the invisible force a tiny character doing "
           "the work (e.g. a beaver inside a pencil sharpener carving the point). Open on the everyday problem, go inside, show the mechanism "
           "step by step, come back out to the satisfying result. Never letters, numbers or charts in the picture. ")

DEFAULTS: dict[str, dict[str, str]] = {
    "director.cinema": {"title": "Director: complete shot fields", "group": "Script", "text": CINEMA,
                        "help": "Makes the writer fill all 14 fields of a shot (angle, lens, composition, performance, end state, continuity…), so nothing is left for the model to guess."},
    "director.story": {"title": "Director: story and comedy structure", "group": "Script", "text": STORY,
                       "help": "Hook, escalation, false hope, reveal and punchline. Used for stories, comedies and anything with characters."},
    "director.explain": {"title": "Director: explainer as a hidden world", "group": "Script", "text": EXPLAIN,
                         "help": "Shows how something works by going inside it or giving the invisible force a tiny character. Used for explainers."},
    "director.rules": {"title": "Director rules", "group": "Script", "text": DIRECTOR,
                       "help": "How the script writer must plan scenes, camera, lighting, mood and sound for every shot."},
    "picture.base": {"title": "Picture quality tail", "group": "Pictures", "text": "cinematic composition, shallow depth of field, rich detail, clean readable subject, consistent character design",
                     "help": "Added to the end of every shot's picture prompt."},
    "picture.recipe.presenter": {"title": "Recipe: presenter shot", "group": "Pictures", "text": "medium shot of the presenter, eyes toward the lens, expressive face, clear readable pose, soft key light from the front-left",
                                 "help": "Added to presenter shots."},
    "picture.recipe.demonstration": {"title": "Recipe: demonstration shot", "group": "Pictures", "text": "hands and prop clearly visible, the key action caught at its most readable moment, uncluttered foreground, subject well lit",
                                     "help": "Added to demonstration shots."},
    "picture.recipe.macro_close_up": {"title": "Recipe: macro close-up", "group": "Pictures", "text": "extreme close-up, macro lens, razor-sharp detail on the material, shallow depth of field, bright specular highlights, well exposed",
                                      "help": "Added to macro close-ups."},
    "picture.recipe.scientific_cutaway": {"title": "Recipe: science cutaway", "group": "Pictures", "text": "clean 3D cross-section cutaway, translucent walls, glowing arrows showing the hidden force, dark neutral background so the glow reads",
                                          "help": "Added to cutaway shots."},
    "picture.recipe.result": {"title": "Recipe: result shot", "group": "Pictures", "text": "clear payoff frame, the outcome obvious at a glance, satisfying centred composition, bright and well exposed",
                              "help": "Added to result shots."},
    "picture.recipe.reaction": {"title": "Recipe: reaction shot", "group": "Pictures", "text": "close-up on the face, one clear emotion, expressive eyes and eyebrows, soft flattering light",
                                "help": "Added to reaction shots."},
    "picture.recipe.establishing": {"title": "Recipe: establishing shot", "group": "Pictures", "text": "wide establishing shot, the whole set visible, characters small but readable, strong depth and leading lines",
                                    "help": "Added to establishing shots."},
    "motion.keep": {"title": "Motion: keep-the-look rules", "group": "Clips", "text": "Maintain the exact character design, outfit and props from the picture. Smooth natural motion, real weight, no morphing, no flickering, no extra limbs, no sudden cuts.",
                    "help": "Added to every video-model prompt so the clip keeps the picture's look."},
    "sheet.character": {"title": "Character design sheet", "group": "Design", "text": "Professional character design sheet of {name}: {look}. Layout on a clean cream paper background: on the left three full-body turnaround views (front, side, back) of the same character in a neutral standing pose; top right a row of five head close-ups showing expressions (neutral, faint smile, stern, surprised, weary); below it an equipment and costume breakdown showing each garment and accessory laid out separately; at the bottom a strip of colour swatches taken from the character's own colours. Even studio light. {style}. The identical face, hair, outfit and colours in every view. No text, no labels, no numbers.",
                        "help": "Drawn once per character. {name}, {look} and {style} are filled in."},
    "picture.endframe": {"title": "Last frame of a shot", "group": "Pictures", "text": "same camera position, same framing, same character, outfit, set and light as the first frame; only the pose and the action's result have changed",
                         "help": "Added when the key-pose artist draws a shot's last frame, so first and last frame match except for the action."},
    "portrait.identity": {"title": "Character identity portrait", "group": "Design", "text": "Identity reference portrait of {name}: {look}. One character only, full body, standing straight, facing the camera, arms relaxed, neutral friendly expression, on a plain light grey background with even soft studio light and a faint floor shadow. Sharp face, clear outfit and colours. {style}. No other people, no props unless they are part of the outfit. No text.",
                          "help": "Drawn once per character: the clean front view every shot is matched against. {name}, {look} and {style} are filled in."},
    "poster.tail": {"title": "Key visual poster", "group": "Design", "text": "dramatic composition, depth of field, volumetric light, cinematic key art, well exposed",
                    "help": "Added to the key visual prompt."},
}
_LOCK = threading.RLock()


def _file() -> Path:
    return Path(os.environ.get("AVOS_EXPLAINER_PROMPTS") or (store.ROOT.parent / "explainer_prompts.json"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _hash(t: str) -> str:
    return hashlib.sha1(t.encode()).hexdigest()[:10]


def _version(v: int, text: str, source: str, note: str = "") -> dict:
    return {"v": v, "text": text, "source": source, "note": note, "created": _now(), "uses": 0, "bad": 0, "up": 0, "down": 0, "flags": {}, "examples": []}


def _load() -> dict:
    try:
        d = json.loads(_file().read_text("utf-8"))
    except (OSError, ValueError):
        d = {}
    d.setdefault("keys", {})
    d.setdefault("events", [])
    for k, meta in DEFAULTS.items():
        e = d["keys"].get(k)
        if not e:
            d["keys"][k] = {"versions": [_version(1, meta["text"], "default")], "active": 1, "candidate": None, "base": _hash(meta["text"]), "tried_at": 0}
        elif e.get("base") != _hash(meta["text"]):                 # a new release changed the built-in text
            cur = next((x for x in e["versions"] if x["v"] == e["active"]), None)
            if cur and cur["source"] == "default":
                cur["text"] = meta["text"]
            e["base"] = _hash(meta["text"])
    return d


def _save(d: dict) -> None:
    f = _file()
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), "utf-8")
        os.replace(tmp, f)
    except OSError:
        pass


def _ver(e: dict, v: int | None) -> dict | None:
    return next((x for x in e["versions"] if x["v"] == v), None)


def default(key: str) -> str:
    return DEFAULTS[key]["text"]


def pick(key: str, pid: str = "") -> tuple[str, int]:
    """(text, version) to use for this project. A candidate is tried on about half of the projects (the same project always gets the same one)."""
    with _LOCK:
        e = _load()["keys"].get(key)
        if not e:
            return DEFAULTS[key]["text"], 1
        use = e["active"]
        if e.get("candidate") and pid and int(hashlib.sha1(f"{key}|{pid}".encode()).hexdigest()[:6], 16) % 2 == 0:
            use = e["candidate"]
        return _ver(e, use)["text"], use


def is_prompt_fault(msg: str) -> bool:
    """True only for errors a better prompt could fix (refused/too long/invalid prompt). Network, key, credit and quota errors are not the prompt's fault."""
    m = (msg or "").lower()
    if re.search(r"errno|unreachable|timed? ?out|connect|network|dns|credit|billing|balance|quota|api key|token|unauthori[sz]ed|forbidden|401|403|429|5\d\d|not set up|isn't set up|no .* model", m):
        return False
    return bool(re.search(r"safety|blocked|nsfw|moderat|policy|too long|exceeds|invalid (?:prompt|input)|prompt .* (?:invalid|rejected)|unprocessable|422|400", m))


def record(key: str, v: int, outcome: str, flags: list[str] | tuple[str, ...] = (), prompt: str = "", note: str = "") -> None:
    """outcome: ok | flag | failed (a generation), redo | down (you rejected an earlier result), up (you liked it)."""
    with _LOCK:
        d = _load()
        e = d["keys"].get(key)
        x = _ver(e, v) if e else None
        if not x:
            return
        if outcome in ("ok", "flag", "failed"):
            x["uses"] += 1
            if outcome != "ok":
                x["bad"] += 1
        elif outcome in ("redo", "down"):
            x["bad"] = min(x["uses"], x["bad"] + 1)
            x["down"] += outcome == "down"
        elif outcome == "up":
            x["up"] += 1
        else:
            return
        for f in flags:
            x["flags"][f] = x["flags"].get(f, 0) + 1
        if outcome in ("flag", "failed", "redo", "down"):
            x["examples"] = (x["examples"] + [{"outcome": outcome, "flags": list(flags), "note": note[:200], "prompt": prompt[:300]}])[-8:]
        _save(d)


def record_all(used: list | None, outcome: str | None, flags: list[str] | tuple[str, ...] = (), prompt: str = "", note: str = "") -> None:
    if not outcome:
        return
    for k, v in used or []:
        record(k, int(v), outcome, flags, prompt, note)


def bad_rate(x: dict) -> float:
    return round(min(1.0, x["bad"] / x["uses"]), 3) if x["uses"] else 0.0


# ---- improving ---------------------------------------------------------------------------------------------------------------------
FIX = {"too_dark": "brightly and evenly lit, clear exposure, visible details in the shadows",
       "too_bright": "balanced exposure, no blown-out highlights, soft contrast",
       "flat": "rich detail, strong tonal contrast, the subject clearly separated from the background",
       "duplicate": "a clearly different camera angle, framing and subject position from the previous shot",
       "thin_plan": "Never leave camera_note, lighting or audio empty: write them for EVERY shot, each different from the others. "}
NOTE_WORDS = [(r"hand|finger", "correct hands with five fingers each"), (r"blur|soft focus|out of focus", "sharp focus on the subject"),
              (r"text|letter|word|writing", "no text, no letters, no writing anywhere in the picture"), (r"face|eyes", "a clear, well-formed face"),
              (r"dark|dim", FIX["too_dark"]), (r"off.?model|different character|wrong character|not the same", "exactly the same character design as the reference"),
              (r"cluttered|busy|messy", "uncluttered, one clear subject"), (r"boring|flat|dull", FIX["flat"])]


def heuristic_fix(text: str, x: dict) -> tuple[str, str]:
    """A safe improvement without an AI writer: add a short remedy for what actually went wrong, or shorten a prompt that gets refused."""
    add: list[str] = []
    for f, n in sorted(x["flags"].items(), key=lambda kv: -kv[1]):
        if f in FIX and FIX[f] not in text:
            add.append(FIX[f])
    notes = " ".join(ex.get("note", "") for ex in x["examples"]).lower()
    for rx, phrase in NOTE_WORDS:
        if re.search(rx, notes) and phrase not in text and phrase not in add:
            add.append(phrase)
    if not add and any(ex["outcome"] == "failed" for ex in x["examples"]) and len(text) > 500:
        cut = text[:int(len(text) * 0.75)].rsplit(".", 1)[0].strip()
        if len(cut) > 120 and cut != text:
            return cut + ".", "shortened because the prompt was refused or too long"
    if not add:
        return text, ""
    add = add[:2]
    if text.rstrip().endswith((".", "!", "?")) or "\n" in text:
        return text.rstrip() + " " + " ".join(a if a.endswith(".") else a + "." for a in add), "added: " + "; ".join(add)
    return text.rstrip(" ,") + ", " + ", ".join(add), "added: " + "; ".join(add)


IMPROVER = """You improve prompts for an AI video studio. Answer with ONE JSON object only: {"text":"<the improved prompt>","why":"<one short sentence>"}.
Keep the same job, the same placeholders in {curly braces}, and a similar length (at most 30% longer). Fix what went wrong in the failure examples
by adding concrete, positive visual wording (not long lists of "don't"). Never add words that make images contain text or logos."""


def _ai_improve(s: dict, key: str, cur: str, x: dict, log: Callable[[dict], None] | None) -> tuple[str, str] | None:
    from ..series import writers
    if not writers.uses_ai(s):
        return None
    ex = "\n".join(f"- {e['outcome']} {','.join(e['flags'])} {e['note']} | prompt: {e['prompt']}" for e in x["examples"][-5:])
    prompt = (f"Prompt slot: {key} ({DEFAULTS[key]['help']})\nCurrent prompt:\n{cur}\n\n"
              f"Results with it: {x['uses']} uses, {round(bad_rate(x) * 100)}% bad. Problems seen: {json.dumps(x['flags'])}.\nRecent bad results:\n{ex or '(none recorded)'}\n\nWrite the improved prompt.")
    try:
        r = writers.ask(s, "story", IMPROVER, prompt, log, max_tokens=1200, temperature=0.4)
    except Exception:  # noqa: BLE001 - never let learning break a video
        return None
    if not isinstance(r, dict) or not isinstance(r.get("text"), str):
        return None
    new = r["text"].strip()
    need = set(re.findall(r"\{\w+\}", cur))
    if not (20 <= len(new) <= min(MAX_TEXT, int(len(cur) * 1.4) + 80)) or new == cur or not need <= set(re.findall(r"\{\w+\}", new)):
        return None
    return new, "AI writer: " + " ".join(str(r.get("why") or "improved wording").split())[:160]


def _event(d: dict, msg: str) -> None:
    d["events"] = (d["events"] + [{"t": _now(), "text": msg}])[-40:]


def learn(s: dict | None = None, log: Callable[[dict], None] | None = None) -> list[str]:
    """One learning pass over every prompt: judge running candidates, and start a candidate for prompts that keep giving bad results."""
    out: list[str] = []
    with _LOCK:
        d = _load()
        for key, e in d["keys"].items():
            act, cand = _ver(e, e["active"]), _ver(e, e.get("candidate"))
            if cand:
                if cand["uses"] < MIN_USES:
                    continue
                a, c = bad_rate(act), bad_rate(cand)
                if c + MARGIN <= a:
                    e["active"], e["candidate"] = cand["v"], None
                    out.append(f"{DEFAULTS[key]['title']}: new version v{cand['v']} won ({round(c * 100)}% bad vs {round(a * 100)}%), it is now the main prompt.")
                else:
                    e["candidate"], e["tried_at"] = None, act["uses"]
                    out.append(f"{DEFAULTS[key]['title']}: v{cand['v']} was not better ({round(c * 100)}% bad vs {round(a * 100)}%), kept v{act['v']}.")
                continue
            if act["uses"] < MIN_USES or bad_rate(act) < BAD_RATE or act["uses"] < e.get("tried_at", 0) + MIN_USES:
                continue
            res = (_ai_improve(s, key, act["text"], act, log) if s else None) or (lambda r: (r if r[1] else None))(heuristic_fix(act["text"], act))
            e["tried_at"] = act["uses"]
            if not res:
                continue
            nv = max(x["v"] for x in e["versions"]) + 1
            e["versions"].append(_version(nv, res[0], "learned", res[1]))
            e["candidate"] = nv
            out.append(f"{DEFAULTS[key]['title']}: {round(bad_rate(act) * 100)}% of results were bad, testing v{nv} ({res[1]}).")
        for m in out:
            _event(d, m)
        if out:
            _save(d)
    return out


# ---- editing by hand and the library view -------------------------------------------------------------------------------------------
def set_text(key: str, text: str, note: str = "edited by you") -> None:
    if key not in DEFAULTS:
        raise KeyError(key)
    text = text.strip()
    if not 10 <= len(text) <= MAX_TEXT:
        raise ValueError(f"A prompt must be 10 to {MAX_TEXT} characters.")
    need = set(re.findall(r"\{\w+\}", default(key)))
    if not need <= set(re.findall(r"\{\w+\}", text)):
        raise ValueError("Keep these placeholders in the text: " + ", ".join(sorted(need)))
    with _LOCK:
        d = _load()
        e = d["keys"][key]
        nv = max(x["v"] for x in e["versions"]) + 1
        e["versions"].append(_version(nv, text, "manual", note))
        e["active"], e["candidate"] = nv, None
        _event(d, f"{DEFAULTS[key]['title']}: you saved v{nv}.")
        _save(d)


def restore(key: str, v: int) -> None:
    with _LOCK:
        d = _load()
        e = d["keys"].get(key)
        if not e or not _ver(e, v):
            raise KeyError(key)
        e["active"], e["candidate"] = v, None
        _event(d, f"{DEFAULTS[key]['title']}: back to v{v}.")
        _save(d)


def reset(key: str) -> None:
    with _LOCK:
        d = _load()
        e = d["keys"].get(key)
        if not e:
            raise KeyError(key)
        nv = max(x["v"] for x in e["versions"]) + 1
        e["versions"].append(_version(nv, default(key), "default", "reset to the built-in prompt"))
        e["active"], e["candidate"] = nv, None
        _save(d)


def improve_now(key: str, s: dict | None = None) -> str:
    """Start a candidate for one prompt right now (even before it has many uses), from whatever has gone wrong so far."""
    with _LOCK:
        d = _load()
        e = d["keys"].get(key)
        if not e:
            raise KeyError(key)
        if e.get("candidate"):
            return "A new version is already being tested."
        act = _ver(e, e["active"])
        res = (_ai_improve(s, key, act["text"], act, None) if s else None) or heuristic_fix(act["text"], act)
        if not res[1] or res[0] == act["text"]:
            return "Nothing to improve yet: no problems have been recorded for this prompt."
        nv = max(x["v"] for x in e["versions"]) + 1
        e["versions"].append(_version(nv, res[0], "learned", res[1]))
        e["candidate"], e["tried_at"] = nv, act["uses"]
        _event(d, f"{DEFAULTS[key]['title']}: testing v{nv} ({res[1]}).")
        _save(d)
        return f"Testing v{nv}: {res[1]}"


def _brief(x: dict | None) -> dict | None:
    return None if not x else {k: x[k] for k in ("v", "text", "source", "note", "created", "uses", "bad", "up", "down", "flags")} | {"bad_rate": bad_rate(x), "examples": x["examples"][-3:]}


def library() -> dict:
    with _LOCK:
        d = _load()
        items = []
        for k, meta in DEFAULTS.items():
            e = d["keys"][k]
            items.append({"key": k, "title": meta["title"], "group": meta["group"], "help": meta["help"], "placeholders": re.findall(r"\{\w+\}", meta["text"]),
                          "active": _brief(_ver(e, e["active"])), "candidate": _brief(_ver(e, e.get("candidate"))), "min_uses": MIN_USES,
                          "versions": [{"v": x["v"], "source": x["source"], "note": x["note"], "created": x["created"], "uses": x["uses"], "bad_rate": bad_rate(x), "up": x["up"], "down": x["down"]} for x in e["versions"]]})
        return {"items": items, "events": d["events"][-15:]}
