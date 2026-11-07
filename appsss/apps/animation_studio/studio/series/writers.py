"""The Series writers' room: the AI crew (the same crews as Animations: Groq, Ollama, Gemini, …) in five roles.

    bible        characters (look, outfit, personality, voice) and locations, from the premise and style
    outline      an episode split into parts (1 min, then 3 min, …), with beats per part and a hook at each end
    part script  one part at a time, in the series' language, continuing from the story so far
    import       your own script → the same structure, your dialogue kept word for word
    DoP          each beat → a shot: framing, camera, the picture to draw and the motion
    continuity   after each approved part: what happened, for the next part and the next episode

Every answer is checked and repaired (unknown characters dropped, lengths clamped) so a weak model can't break
the pipeline; with the built-in crew (no AI) simple drafts come from rules, enough to try the whole flow offline.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any, Callable

from .. import jobs as J
from ..creative import dna as DNA, scene as SG, skills as SK
from ..llm import Crew, CrewError
from . import languages, store

EMOTIONS = ("neutral", "happy", "excited", "angry", "sad", "scared", "surprised", "sarcastic", "worried", "shout", "whisper", "laugh")
FRAMINGS = ("close-up", "medium", "two-shot", "wide", "over-the-shoulder", "insert")
CHARS_PER_SECOND = 13.0


class WriterError(RuntimeError):
    pass


def line_seconds(text: str) -> float:
    return round(max(1.4, len((text or "").strip()) / CHARS_PER_SECOND + 0.4), 2)


def beat_seconds(b: dict) -> float:
    if b.get("fixed"):                       # a film's timed shot: its length comes from the prompt's time codes
        try:
            return round(max(0.5, min(15.0, float(b.get("seconds") or 2.0))), 2)
        except (TypeError, ValueError):
            return 2.0
    if b.get("type") == "line":
        return line_seconds(b.get("text", ""))
    try:
        return max(2.0, min(6.0, float(b.get("seconds") or 3.0)))
    except (TypeError, ValueError):
        return 3.0


def script_seconds(script: dict) -> float:
    return round(sum(beat_seconds(b) for sc in script.get("scenes") or [] for b in sc.get("beats") or []), 1)


# ---------- the crew ----------
def crew(s: dict, who: str, log: Callable[[dict], None] | None = None) -> Crew:
    kind = s.get("crew") or "builtin"
    return Crew(kind, s["id"], "fresh", who, log or (lambda ev: None), J.Abort(), store.sdir(s["id"]))


RATE_RX = re.compile(r"rate.?limit|429|tokens per minute|TPM|too many requests|quota", re.I)


def uses_ai(s: dict) -> bool:
    return (s.get("crew") or "builtin") != "builtin"


def system(skill: str, fallback: str) -> str:
    """An agent's instructions: its SKILL.md (apps/skills/<skill>/SKILL.md), else the built-in text. The first line
    names the skill, so logs (and tests) can tell which role answered."""
    return f"[{skill}]\n" + SK.load(skill, fallback)


def ask(s: dict, who: str, system: str, prompt: str, log: Callable[[dict], None] | None = None,
        max_tokens: int = 6000, temperature: float = 0.7, images: list | None = None) -> Any:
    """One JSON answer from the series' crew (None with the built-in crew). Waits and retries when the provider's
    per-minute limit is hit (Groq's free tier counts the prompt + max_tokens against ~8k tokens a minute)."""
    c = crew(s, who, log)
    if not c.enabled:
        return None
    if c.kind == "groq":
        max_tokens = max(1500, min(max_tokens, 7600 - (len(system) + len(prompt)) // 3))
    for attempt in range(4):
        try:
            return asyncio.run(c.ask_json(system, prompt, images=images, temperature=temperature, max_tokens=max_tokens, keep=False))
        except CrewError as e:
            if attempt < 3 and RATE_RX.search(str(e)):
                (log or (lambda ev: None))({"type": "text", "who": who, "text": f"The AI's per-minute limit was hit; waiting {15 * 2 ** attempt} s."})
                time.sleep(15 * 2 ** attempt)
                continue
            raise WriterError(str(e)) from e
    return None


def need(s: dict, ok: bool, what: str) -> None:
    """With an AI crew, an unusable answer is an error you see (never a silent placeholder)."""
    if not ok and uses_ai(s):
        raise WriterError(f"The AI writers ({s.get('crew')}) didn't return a usable {what}. Try again, or pick another AI crew.")


def _lang_rules(s: dict) -> str:
    lg = languages.get(s.get("language") or "en")
    return (f"All DIALOGUE is in {lg.name}, written in {lg.script}. Everything else (actions, looks, picture and sound "
            f"descriptions) is in English, because the picture and sound models read English.")


def _cast(s: dict, approved_only: bool = True) -> list[dict]:
    return [c for c in s.get("characters") or [] if c.get("status") == "approved" or not approved_only]


def _cast_brief(s: dict, approved_only: bool = True) -> str:
    rows = []
    for c in _cast(s, approved_only):
        rows.append({"id": c["id"], "name": c["name"], "role": c.get("role"), "age": c.get("age"),
                     "personality": c.get("personality"), "catchphrase": c.get("catchphrase") or ""})
    return json.dumps(rows, ensure_ascii=False)


def _locations_brief(s: dict) -> str:
    return json.dumps([{"id": x["id"], "name": x["name"], "description": x.get("description", "")}
                       for x in s.get("locations") or []], ensure_ascii=False)


def _story(s: dict) -> str:
    st = s.get("story") or {}
    rows = [f"Episode {r['episode']}: {r['summary']}" for r in (st.get("episodes") or [])[-6:]]
    facts = st.get("facts") or []
    return ("\n".join(rows) or "(this is the first episode)") + (("\nThings that stay true: " + "; ".join(facts[-20:])) if facts else "")


# ---------- 1. the bible: characters and locations ----------
BIBLE_SYS = """You are the series bible writer for an animated TV series. From the premise, the style notes and any
cast the creator listed, design the main cast and the recurring locations so a picture model can draw them the
same way in every episode. Be specific and visual: face shape, hair, skin tone, body type, height, signature
outfit with colours, one or two distinctive details. Give each character a distinct VOICE description (age, pitch,
pace, timbre, attitude) and a personality that drives comedy or drama. Keep the creator's characters and their
details; only add characters if asked. Locations: 3 to 6 everyday places the stories happen in."""


def bible(s: dict, log: Callable[[dict], None] | None = None) -> dict:
    want_extra = s.get("suggestCast", True)
    prompt = (f"Series: {s['title']}\nPremise: {s.get('premise') or ''}\nAudience: {s.get('audience') or 'family'}\n"
              f"Tone / genre: {s.get('tone') or 'comedy'}\nArt style notes: {(s.get('style') or {}).get('description') or 'from the reference pictures'}\n"
              f"Language of the dialogue: {languages.get(s.get('language') or 'en').name}\n"
              f"The creator's cast (keep these):\n{s.get('castText') or '(none given)'}\n"
              f"{'Add the other characters the premise needs (at most 6 in total).' if want_extra else 'Do not add characters.'}\n\n"
              'Answer as JSON: {"logline": "", "world": "", "style_prompt": "one line describing the art style for the picture model", '
              '"characters": [{"name": "", "role": "lead|supporting|recurring", "age": "", "gender": "male|female|other", '
              '"personality": "", "look": "", "outfit": "", "voice": "", "catchphrase": "", '
              f'"sample_line": "one typical line in {languages.get(s.get("language") or "en").name}, native script"}}], '
              '"locations": [{"name": "", "description": ""}]}')
    data = ask(s, "bible writer", system("avos-series-bible", BIBLE_SYS), prompt, log)
    ok = isinstance(data, dict) and bool(data.get("characters"))
    need(s, ok, "cast")
    if not ok:
        data = builtin_bible(s)
    return norm_bible(s, data)


def _cast_from_text(text: str) -> list[dict]:
    out = []
    for line in (text or "").splitlines():
        line = line.strip(" -*•\t")
        if not line:
            continue
        m = re.match(r"^(.{1,40}?)\s*[:\-–—]\s*(.*)$", line)
        name, rest = (m.group(1), m.group(2)) if m else (line, "")
        out.append({"name": name.strip()[:40], "look": rest.strip()[:400]})
    return out


def builtin_bible(s: dict) -> dict:
    cast = _cast_from_text(s.get("castText") or "") or [
        {"name": "Raju", "look": "a skinny 12-year-old boy, messy black hair, big eyes, green t-shirt with a yellow stripe"},
        {"name": "Amma", "look": "his strict, loving mother, hair in a bun, round glasses, purple saree with a red border"}]
    chars = []
    for i, c in enumerate(cast[:6]):
        female = bool(re.search(r"\b(she|her|girl|woman|mother|mom|amma|maa|aunt|sister|didi|wife|daughter|grandma)\b", c["look"] + " " + c["name"], re.I))
        chars.append({"name": c["name"], "role": "lead" if i == 0 else "supporting", "age": "", "gender": "female" if female else "male",
                      "personality": "", "look": c["look"] or f"{c['name']}, a cartoon character", "outfit": "",
                      "voice": ("a warm adult woman, clear, expressive" if female else "a lively young male voice, quick and expressive"),
                      "catchphrase": ""})
    return {"logline": s.get("premise") or s["title"], "world": "", "style_prompt": "",
            "characters": chars, "locations": [{"name": "Home", "description": "a small, cosy family home with a kitchen and a living room"},
                                               {"name": "Street", "description": "a busy neighbourhood street with small shops"}]}


def norm_bible(s: dict, data: dict) -> dict:
    taken = {c["id"] for c in s.get("characters") or []}
    chars = []
    for c in data.get("characters") or []:
        if not isinstance(c, dict) or not str(c.get("name") or "").strip():
            continue
        cid = store.slug(str(c["name"]), taken)
        taken.add(cid)
        g = str(c.get("gender") or "").lower()
        chars.append({"id": cid, "name": str(c["name"]).strip()[:40], "role": str(c.get("role") or "supporting")[:20],
                      "age": str(c.get("age") or "")[:20], "gender": g if g in ("male", "female") else "other",
                      "personality": str(c.get("personality") or "")[:400], "look": str(c.get("look") or "")[:600],
                      "outfit": str(c.get("outfit") or "")[:300], "catchphrase": str(c.get("catchphrase") or "")[:120],
                      "voice": {"description": str(c.get("voice") or "")[:300],
                                **({"sampleText": str(c["sample_line"]).strip()[:200]} if str(c.get("sample_line") or "").strip() else {})}})
    ltaken = {x["id"] for x in s.get("locations") or []}
    locs = []
    for x in data.get("locations") or []:
        if not isinstance(x, dict) or not str(x.get("name") or "").strip():
            continue
        lid = store.slug(str(x["name"]), ltaken)
        ltaken.add(lid)
        locs.append({"id": lid, "name": str(x["name"]).strip()[:40], "description": str(x.get("description") or "")[:400]})
    return {"logline": str(data.get("logline") or "")[:300], "world": str(data.get("world") or "")[:600],
            "style_prompt": str(data.get("style_prompt") or "")[:300], "characters": chars[:8], "locations": locs[:8]}


# ---------- 1b. Design DNA ----------
DNA_SYS = """You write the Design DNA of an animated series: its look (medium, line, shading, proportions, texture,
palette, lighting), camera grammar, motion grammar and sound, short and specific, from the style notes and pictures."""


def design_dna(s: dict, log: Callable[[dict], None] | None = None, images: list | None = None) -> dict:
    st = s.get("style") or {}
    prompt = (f"Series: {s['title']} — {s.get('premise') or ''}\nTone: {s.get('tone') or 'comedy'}; audience: {s.get('audience') or 'family'}\n"
              f"The creator's style notes: {st.get('description') or '(none: use the pictures, or a clean TV-cartoon look)'}\n"
              f"Music wish: {(s.get('music') or {}).get('style') or '(none)'}\n"
              + ("The attached pictures show the style (describe what you see; never name the show).\n" if images else "")
              + '\nAnswer as JSON: {"name": "", "medium": "", "line": "", "shading": "", "proportions": "", "texture": "", '
                '"palette": ["#RRGGBB"], "lighting": "", "camera": {"default_lens": 35, "angle": "eye level", "max_speed": "slow", '
                '"allowed_moves": ["static", "push_in"]}, "motion": {"pacing": "", "ease": "power2.inOut", "squash_stretch": true, '
                '"holds": true, "feel": ""}, "sound": {"ambience": "", "music": "", "sfx_style": ""}, "avoid": [""]}')
    data = ask(s, "art director", system("avos-design-dna", DNA_SYS), prompt, log, max_tokens=2000, temperature=0.4, images=images)
    if not isinstance(data, dict) or not (data.get("medium") or data.get("line")):
        data = {"medium": (st.get("description") or "")[:200] or DNA.DEFAULT["medium"],
                "sound": {"music": (s.get("music") or {}).get("style") or DNA.DEFAULT["sound"]["music"]}}
    return DNA.normalize(data)


# ---------- 2. the episode outline ----------
OUTLINE_SYS = """You are the head writer of an animated series. Outline ONE episode split into the given parts (the
first part is short: it sets up the situation fast and makes the viewer stay). Each part needs a clear mini-goal,
escalation, and ends on a hook or a laugh that leads into the next part; the last part pays everything off. Use
only the approved characters. Keep continuity with the story so far."""


def part_plan(minutes: float, plan: list[float] | None = None) -> list[float]:
    """Part lengths: e.g. 10 min with [1, 3] → 1, 3, 3, 3 (the last one takes what's left)."""
    plan = [float(x) for x in (plan or [1, 3]) if float(x) > 0] or [1.0, 3.0]
    out, left, i = [], float(minutes), 0
    while left > 0.01:
        if out and left < min(0.25, plan[-1] / 2):      # a few seconds left: they go into the last part
            out[-1] = round(out[-1] + left, 2)
            break
        size = plan[min(i, len(plan) - 1)]
        if left - size < 0.75 * plan[-1] and out:      # a sliver at the end goes into the last part
            size = left
        size = min(size, left)
        out.append(round(size, 2))
        left = round(left - size, 2)
        i += 1
        if len(out) > 40:
            break
    return out


def outline(s: dict, ep: dict, log: Callable[[dict], None] | None = None, note: str = "") -> dict:
    sizes = [p["minutes"] for p in ep["parts"]]
    prompt = (f"Series: {s['title']} — {s.get('logline') or s.get('premise') or ''}\nWorld: {s.get('world') or ''}\n"
              f"Approved characters: {_cast_brief(s)}\nLocations: {_locations_brief(s)}\nStory so far:\n{_story(s)}\n\n"
              f"Episode {ep['number']} brief: {ep.get('brief') or 'your best idea for the next episode'}\n"
              f"Parts (minutes each): {sizes} (total {sum(sizes)} min)\n"
              + (f"The creator's note on your last outline: {note}\n" if note else "")
              + '\nAnswer as JSON: {"title": "", "logline": "", "parts": [{"index": 1, "summary": "", "beats": ["", ""], '
                '"ends_with": ""}]}')
    data = ask(s, "head writer", system("avos-head-writer", OUTLINE_SYS), prompt, log)
    parts = (data or {}).get("parts") if isinstance(data, dict) else None
    need(s, bool(parts), "outline")
    if not parts:
        data = {"title": ep.get("title") or f"Episode {ep['number']}", "logline": ep.get("brief") or "",
                "parts": [{"index": i + 1, "summary": (ep.get("brief") or "The story") + f" — part {i + 1}", "beats": []}
                          for i in range(len(sizes))]}
        parts = data["parts"]
    out = []
    for i, m in enumerate(sizes):
        p = next((x for x in parts if isinstance(x, dict) and int(x.get("index") or 0) == i + 1), None) or \
            (parts[i] if i < len(parts) and isinstance(parts[i], dict) else {})
        out.append({"summary": str(p.get("summary") or "")[:800], "beats": [str(b)[:300] for b in (p.get("beats") or [])][:12],
                    "endsWith": str(p.get("ends_with") or "")[:300]})
    return {"title": str(data.get("title") or ep.get("title") or f"Episode {ep['number']}")[:80],
            "logline": str(data.get("logline") or "")[:300], "parts": out}


# ---------- 3. one part's script ----------
PART_SYS = """You are the scriptwriter of an animated series. Write ONE part of an episode as scenes of beats.
A beat is either a LINE (one character speaks: short, natural, funny or emotional, how real people talk) or an
ACTION (something visible happens, 2-6 seconds, with the sounds it makes). Show, don't narrate: no narrator.
Every line belongs to one of the approved characters; extras may appear in actions but never speak. Use the
locations given (or name a new one). Average line: 2-4 seconds. Fill the target length."""

BEAT_SCHEMA = ('{"scenes": [{"location": "location id", "time": "morning|afternoon|evening|night", "characters": ["ids"], '
               '"beats": [{"type": "line", "character": "id", "text": "dialogue", "emotion": "' + "|".join(EMOTIONS) +
               '", "action": "what they do while speaking (English)"}, {"type": "action", "text": "what happens (English)", '
               '"characters": ["ids"], "sfx": "the sounds (English)", "seconds": 3}]}]}')


CHUNK_SECONDS = 60      # the AI writes a part about a minute at a time (fits small models and free-tier limits)


def part_script(s: dict, ep: dict, n: int, log: Callable[[dict], None] | None = None, note: str = "") -> dict:
    part = ep["parts"][n - 1]
    target = int(part["minutes"] * 60)
    prev = ""
    if n > 1 and (ep["parts"][n - 2].get("script") or {}).get("scenes"):
        last = [b for sc in ep["parts"][n - 2]["script"]["scenes"] for b in sc.get("beats") or []][-6:]
        prev = json.dumps(last, ensure_ascii=False)
    o = ep.get("outline") or {}
    head = (f"Series: {s['title']} — {s.get('logline') or s.get('premise') or ''}\n{_lang_rules(s)}\n"
            f"Approved characters: {_cast_brief(s)}\nLocations: {_locations_brief(s)}\nStory so far:\n{_story(s)}\n\n"
            f"Episode {ep['number']}: {o.get('title') or ep.get('title') or ''} — {o.get('logline') or ep.get('brief') or ''}\n"
            f"Whole episode outline: {json.dumps([{'part': i + 1, 'summary': p.get('summary')} for i, p in enumerate(ep['parts'])], ensure_ascii=False)}\n"
            f"This is PART {n} of {len(ep['parts'])}: {part.get('summary') or ''}\nBeats to hit: {json.dumps(part.get('beats') or [], ensure_ascii=False)}\n"
            f"The part ends with: {part.get('endsWith') or 'a hook into the next part'}\n"
            + (f"The creator's note on the last draft: {note}\n" if note else ""))
    if not uses_ai(s):
        return builtin_script(s, target, part.get("summary") or "")
    chunks = max(1, round(target / CHUNK_SECONDS))
    per = target / chunks
    scenes: list[dict] = []
    for k in range(chunks):
        tail = [b for sc in scenes for b in sc["beats"]][-8:]
        where = ("Write the START of the part" if k == 0 else "CONTINUE exactly where the text below stops (don't repeat it)")
        prompt = (head + f"\n{where}: about {per:.0f} seconds (roughly {max(4, int(per // 3))} beats)"
                  + (f", ending the part with: {part.get('endsWith') or 'a hook'}" if k == chunks - 1 else ", don't end the part yet")
                  + f". Chunk {k + 1} of {chunks}.\n"
                  + (f"The previous part ended with: {prev}\n" if prev and k == 0 else "")
                  + (f"So far in this part (last beats): {json.dumps(tail, ensure_ascii=False)}\n" if tail else "")
                  + f"\nAnswer as JSON: {BEAT_SCHEMA}")
        data = ask(s, "scriptwriter", system("avos-scriptwriter", PART_SYS), prompt, log, max_tokens=6000)
        got = norm_script(s, data) if isinstance(data, dict) else {"scenes": []}
        need(s, bool(got["scenes"]), f"script for part {n}")
        for sc in got["scenes"]:
            if scenes and scenes[-1]["location"] == sc["location"] and k > 0 and sc is got["scenes"][0]:
                scenes[-1]["beats"].extend(sc["beats"])        # the same scene carries on across chunks
                scenes[-1]["characters"] = list(dict.fromkeys(scenes[-1]["characters"] + sc["characters"]))
            else:
                scenes.append(sc)
    for i, sc in enumerate(scenes):
        sc["id"] = f"s{i + 1}"
        _ids(sc["beats"], i + 1)
    return {"scenes": scenes}


def builtin_script(s: dict, seconds: int, summary: str) -> dict:
    cast = _cast(s) or _cast(s, approved_only=False)
    if not cast:
        raise WriterError("No approved characters yet.")
    loc = (s.get("locations") or [{"id": "home"}])[0]["id"]
    beats: list[dict] = [{"type": "action", "text": summary or "The day begins.", "characters": [cast[0]["id"]], "sfx": "room tone, birds outside", "seconds": 3}]
    lines = ["Hello!", "What happened here?", "Don't look at me like that.", "Fine, fine. I'll fix it.", "You always say that!",
             "This time I mean it.", "Then why are you smiling?", "Because I have a plan."]
    i = 0
    while sum(beat_seconds(b) for b in beats) < seconds and i < 60:
        c = cast[i % len(cast)]
        beats.append({"type": "line", "character": c["id"], "text": lines[i % len(lines)], "emotion": EMOTIONS[i % 6], "action": "gestures"})
        i += 1
        if i % 4 == 0:
            beats.append({"type": "action", "text": f"{c['name']} paces around the room", "characters": [c["id"]], "sfx": "footsteps", "seconds": 3})
    return {"scenes": [{"id": "s1", "location": loc, "time": "morning", "characters": [c["id"] for c in cast], "beats": _ids(beats, 1)}]}


def _ids(beats: list[dict], scene_no: int) -> list[dict]:
    for i, b in enumerate(beats):
        b["id"] = f"s{scene_no}b{i + 1}"
    return beats


def _film_keys(b: dict) -> dict:
    """A film beat keeps its timing and its shot's direction (camera, angle, timed events, sounds) through edits."""
    out: dict[str, Any] = {}
    if b.get("fixed"):
        out["fixed"] = True
        try:
            out["seconds"] = max(0.5, min(15.0, float(b.get("seconds") or 2)))
        except (TypeError, ValueError):
            out["seconds"] = 2.0
    if isinstance(b.get("hint"), dict):
        out["hint"] = b["hint"]
    if b.get("shot"):
        out["shot"] = str(b["shot"])[:20]
    return out


def norm_script(s: dict, data: dict) -> dict:
    """Keep what the pipeline can make: known speakers only, known emotions, sane lengths, ids on everything."""
    cast = {c["id"]: c for c in _cast(s)}
    by_name = {c["name"].lower(): c["id"] for c in cast.values()}
    locs = {x["id"] for x in s.get("locations") or []}
    loc_names = {x["name"].lower(): x["id"] for x in s.get("locations") or []}

    def who(v: Any) -> str | None:
        v = str(v or "").strip()
        return v if v in cast else by_name.get(v.lower())
    scenes = []
    for sc in data.get("scenes") or []:
        if not isinstance(sc, dict):
            continue
        loc = str(sc.get("location") or "").strip()
        loc = loc if loc in locs else loc_names.get(loc.lower(), loc or "home")
        beats = []
        for b in sc.get("beats") or []:
            if not isinstance(b, dict):
                continue
            kind = "line" if str(b.get("type")).lower() == "line" or (b.get("character") and b.get("text") and b.get("type") != "action") else "action"
            if kind == "line":
                cid, text = who(b.get("character")), str(b.get("text") or "").strip()
                if not cid or not text:
                    continue
                emo = str(b.get("emotion") or "neutral").lower()
                beats.append({"type": "line", "character": cid, "text": text[:400],
                              "emotion": emo if emo in EMOTIONS else "neutral", "action": str(b.get("action") or "")[:200], **_film_keys(b)})
            else:
                text = str(b.get("text") or "").strip()
                if not text:
                    continue
                chars = [c for c in (who(x) for x in (b.get("characters") or [])) if c]
                try:
                    secs = max(0.5, min(15.0, float(b.get("seconds") or 3))) if b.get("fixed") else max(2.0, min(6.0, float(b.get("seconds") or 3)))
                except (TypeError, ValueError):
                    secs = 3.0
                beats.append({"type": "action", "text": text[:400], "characters": chars, "sfx": str(b.get("sfx") or "")[:200], "seconds": secs,
                              **{k: v for k, v in _film_keys(b).items() if k != "seconds"}})
        if beats:
            speakers = {b["character"] for b in beats if b["type"] == "line"} | {c for b in beats for c in b.get("characters") or []}
            listed = [c for c in (who(x) for x in (sc.get("characters") or [])) if c]
            scenes.append({"location": loc, "time": str(sc.get("time") or "day")[:20],
                           "characters": list(dict.fromkeys(listed + sorted(speakers))), "beats": beats})
    for i, sc in enumerate(scenes):
        sc["id"] = f"s{i + 1}"
        _ids(sc["beats"], i + 1)
    return {"scenes": scenes}


# ---------- 4. your own script ----------
IMPORT_SYS = """You are a script editor. Convert the creator's script into scenes of beats. Keep every line of
dialogue EXACTLY as written (same words, same language, same script); do not translate, shorten or add lines.
Turn stage directions into ACTION beats (in English). Map speaker names to the approved characters' ids."""


def import_script(s: dict, text: str, log: Callable[[dict], None] | None = None) -> dict:
    prompt = (f"Approved characters: {_cast_brief(s)}\nLocations: {_locations_brief(s)}\n\nThe creator's script:\n{text[:24000]}\n\n"
              f"Answer as JSON: {BEAT_SCHEMA}")
    data = ask(s, "script editor", system("avos-script-editor", IMPORT_SYS), prompt, log, max_tokens=12000, temperature=0.2)
    script = norm_script(s, data) if isinstance(data, dict) else None
    if not script or not script["scenes"]:
        script = parse_screenplay(s, text)
    if not script["scenes"]:
        raise WriterError("Couldn't read any lines from the script. Write lines as 'NAME: what they say' and actions on their own lines.")
    return script


def parse_screenplay(s: dict, text: str) -> dict:
    """No AI: 'NAME: line' → a line, '(...)' or other lines → an action, 'INT./EXT./SCENE' headings → a new scene."""
    cast = {c["name"].lower(): c["id"] for c in _cast(s)}
    cast.update({c["id"]: c["id"] for c in _cast(s)})
    scenes: list[dict] = []
    cur: dict | None = None
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if re.match(r"^(INT\.|EXT\.|SCENE\b|#)", line, re.I) or cur is None:
            cur = {"location": (s.get("locations") or [{"id": "home"}])[0]["id"], "time": "day", "characters": [], "beats": []}
            scenes.append(cur)
            if re.match(r"^(INT\.|EXT\.|SCENE\b|#)", line, re.I):
                low = line.lower()
                for x in s.get("locations") or []:
                    if x["name"].lower() in low or x["id"] in low:
                        cur["location"] = x["id"]
                continue
        m = re.match(r"^([^:：]{1,30})\s*[:：]\s*(?:\(([^)]*)\)\s*)?(.+)$", line)
        if m and m.group(1).strip().lower() in cast:
            cid = cast[m.group(1).strip().lower()]
            emo = (m.group(2) or "").strip().lower()
            cur["beats"].append({"type": "line", "character": cid, "text": m.group(3).strip(),
                                 "emotion": emo if emo in EMOTIONS else "neutral", "action": m.group(2) or ""})
            if cid not in cur["characters"]:
                cur["characters"].append(cid)
        else:
            cur["beats"].append({"type": "action", "text": line.strip("()[] "), "characters": [], "sfx": "", "seconds": 3})
    scenes = [sc for sc in scenes if sc["beats"]]
    for i, sc in enumerate(scenes):
        sc["id"] = f"s{i + 1}"
        _ids(sc["beats"], i + 1)
    return {"scenes": scenes}


def split_script(script: dict, sizes_min: list[float]) -> list[dict]:
    """A whole-episode script → one script per part, cutting at beat boundaries near each part's length."""
    beats = [(sc, b) for sc in script.get("scenes") or [] for b in sc.get("beats") or []]
    parts, i = [], 0
    for k, m in enumerate(sizes_min):
        target, acc, chunk = m * 60, 0.0, []
        last = k == len(sizes_min) - 1
        while i < len(beats) and (last or acc < target or not chunk):
            chunk.append(beats[i])
            acc += beat_seconds(beats[i][1])
            i += 1
        scenes: list[dict] = []
        for sc, b in chunk:
            if not scenes or scenes[-1]["_src"] is not sc:
                scenes.append({"_src": sc, "location": sc["location"], "time": sc.get("time", "day"),
                               "characters": sc.get("characters", []), "beats": []})
            scenes[-1]["beats"].append(dict(b))
        for j, sc in enumerate(scenes):
            sc.pop("_src")
            sc["id"] = f"s{j + 1}"
            _ids(sc["beats"], j + 1)
        parts.append({"scenes": scenes})
    return parts


# ---------- 5. the scene director: a scene graph + a motion blueprint per beat ----------
DOP_SYS = """You are the director of photography of an animated series. For every beat, plan ONE shot as data: the
scene graph (framing, who stands where, pose, expression, facing, props) and the motion blueprint (the camera move
and ease, timed actions per character, background motion). Establish each new location with a wide shot, use
medium and close-ups for dialogue and reactions, keep screen direction."""

SHOT_SCHEMA = ('{"shots": [{"beat": "s1b1", "framing": "' + "|".join(FRAMINGS) + '", '
               '"actors": [{"id": "", "x": 0.0, "z": 0.0, "facing": "camera|<id>", "pose": "", "expression": ""}], '
               '"props": [{"name": "", "x": 0.0, "z": 0.5, "held_by": "<id or null>"}], '
               '"camera": {"move": "' + "|".join(SG.MOVES) + '", "ease": "power1.inOut"}, '
               '"tracks": [{"target": "<id>", "keys": [{"t": 0, "action": ""}, {"t": 1.5, "action": "", "x": 0.5}]}], '
               '"environment": [{"t": 0, "text": ""}], "picture": "one line: what the first frame shows", "sfx": ""}]}')
DIRECT_CHUNK = 18      # beats per AI call (keeps answers inside small models' and free tiers' limits)


def plan_shots(s: dict, script: dict, log: Callable[[dict], None] | None = None) -> list[dict]:
    """Block every beat on the stage (scene graph) and in time (motion blueprint)."""
    beats = [(sc, b) for sc in script.get("scenes") or [] for b in sc.get("beats") or []]
    dna = DNA.normalize(s.get("dna"))
    planned: dict[str, dict] = {}
    for i in range(0, len(beats), DIRECT_CHUNK):
        chunk = beats[i:i + DIRECT_CHUNK]
        prompt = (f"Characters: {json.dumps({c['id']: c['name'] + ': ' + (c.get('look') or '') for c in _cast(s)}, ensure_ascii=False)}\n"
                  f"Locations: {_locations_brief(s)}\n"
                  f"Design DNA camera grammar: {json.dumps(dna['camera'])}; motion grammar: {json.dumps(dna['motion'])}\n"
                  + (f"(Continuing a part: beats {i + 1}-{i + len(chunk)} of {len(beats)}.)\n" if len(beats) > DIRECT_CHUNK else "")
                  + "The part, beat by beat (seconds = how long the shot lasts):\n"
                  + "\n".join(json.dumps({"beat": b["id"], "scene": sc["id"], "location": sc["location"], "time": sc.get("time"),
                                          "seconds": beat_seconds(b), "in_scene": sc.get("characters"),
                                          **({"speaker": b["character"], "line": b["text"], "emotion": b["emotion"], "doing": b.get("action")}
                                             if b["type"] == "line" else {"action": b["text"], "characters": b.get("characters"), "sfx": b.get("sfx")}),
                                          **({"creator_direction": {k: v for k, v in b["hint"].items() if k in ("framing", "angle", "camera", "picture", "events") and v}}
                                             if isinstance(b.get("hint"), dict) else {})},
                                         ensure_ascii=False) for sc, b in chunk)
                  + f"\n\nAnswer as JSON: {SHOT_SCHEMA}")
        data = ask(s, "scene director", system("avos-scene-director", DOP_SYS), prompt, log, max_tokens=7000, temperature=0.5)
        if isinstance(data, dict):
            planned.update({str(x.get("beat")): x for x in (data.get("shots") or []) if isinstance(x, dict)})
    return [norm_shot(s, sc, b, planned.get(b["id"]), k, beats, dna) for k, (sc, b) in enumerate(beats)]


def norm_shot(s: dict, sc: dict, b: dict, p: dict | None, k: int, beats: list, dna: dict | None = None) -> dict:
    cast = {c["id"]: c for c in s.get("characters") or []}
    dna = dna or DNA.normalize(s.get("dna"))
    p = p or {}
    hint = b.get("hint") if isinstance(b.get("hint"), dict) else {}
    first_in_scene = k == 0 or beats[k - 1][0] is not sc
    framing = str(hint.get("framing") or p.get("framing") or "").lower()
    if framing not in FRAMINGS:
        framing = "wide" if first_in_scene else ("close-up" if b["type"] == "line" and k % 3 else "medium" if b["type"] == "line" else "wide")
    given = [a for a in (p.get("actors") or []) if isinstance(a, dict) and a.get("id") in cast]
    subjects = [x for x in (hint.get("subjects") or p.get("subjects") or [a["id"] for a in given]) if x in cast]
    if b["type"] == "line":
        subjects = list(dict.fromkeys([b["character"], *[x for x in subjects if x != b["character"]]]))[:3]
    elif not subjects:
        subjects = [c for c in b.get("characters") or [] if c in cast][:3] or [c for c in sc.get("characters") or [] if c in cast][:2]
    for a in given:
        a["speaking"] = b["type"] == "line" and a["id"] == b.get("character")
    if b["type"] == "line" and not any(a["id"] == b["character"] for a in given):
        given.append({"id": b["character"], "speaking": True, "expression": b.get("emotion") or "neutral", "pose": b.get("action") or ""})
    stage = SG.normalize_scene({"actors": [a for a in given if a["id"] in subjects], "props": p.get("props"),
                                "lighting": p.get("lighting"), "camera": p.get("camera_position"),
                                **({"angle": hint["angle"]} if hint.get("angle") else {}), **({"lens": hint["lens"]} if hint.get("lens") else {})},
                               subjects=subjects, framing=framing, location=sc["location"], time=sc.get("time", "day"),
                               default_lens=dna["camera"]["default_lens"])
    cam = p.get("camera") if isinstance(p.get("camera"), dict) else {"move": str(p.get("camera") or "")}
    if isinstance(hint.get("camera"), dict) and hint["camera"].get("move"):
        cam = {**cam, **hint["camera"]}
    tracks = p.get("tracks") or []
    env = p.get("environment")
    if hint.get("events"):                  # the prompt's timed actions win over the director's guesses
        by: dict[str, list] = {}
        env = []
        for e in hint["events"]:
            tgt = e.get("who") if e.get("who") in subjects else None
            if tgt:
                by.setdefault(tgt, []).append({"t": e.get("t") or 0, "action": e["action"]})
            else:
                env.append({"t": e.get("t") or 0, "text": e["action"]})
        tracks = [{"target": t_, "keys": ks} for t_, ks in by.items()] or tracks
    if not tracks:
        who = b.get("character") if b["type"] == "line" else (subjects[0] if subjects else None)
        if who:
            tracks = [{"target": who, "keys": [{"t": 0, "action": (b.get("action") or "talks with natural gestures") if b["type"] == "line" else b["text"]}]}]
    allowed = dna["camera"].get("allowed_moves") or []
    blueprint = SG.normalize_motion({"camera": cam, "tracks": tracks, "environment": env}, stage,
                                    duration=beat_seconds(b), speaker=b.get("character"),
                                    default_move="push_in" if framing == "close-up" else "static", default_ease=dna["motion"]["ease"])
    if allowed and blueprint["camera"]["move"] not in allowed and not (hint.get("camera") or {}).get("move"):
        blueprint = SG.normalize_motion({"camera": {"move": "static"}, "tracks": blueprint["tracks"], "environment": blueprint["environment"]},
                                        stage, duration=blueprint["duration"], speaker=b.get("character"))
    who = ", ".join(cast[c]["name"] for c in subjects if c in cast)
    picture = str(hint.get("picture") or p.get("picture") or "").strip() or (
        f"{framing} shot of {who or 'the scene'}" + (f", {cast[b['character']]['name']} speaking, {b['emotion']} expression, {b.get('action') or ''}"
                                                     if b["type"] == "line" else f": {b['text']}"))
    motion = "; ".join(f"{cast.get(t['target'], {}).get('name', t['target'])} {k2['action']}" for t in blueprint["tracks"] for k2 in t["keys"]) \
        or (b["text"] if b["type"] == "action" else "natural gestures")
    return {"id": b["id"], "beat": b["id"], "scene": sc["id"], "kind": "dialogue" if b["type"] == "line" else "action",
            "location": sc["location"], "time": sc.get("time", "day"), "framing": framing, "subjects": subjects,
            "camera": blueprint["camera"]["move"], "picture": picture[:700], "motion": motion[:500],
            "sfx": str(hint.get("sfx") or p.get("sfx") or b.get("sfx") or "")[:300] if b["type"] == "action" or hint.get("sfx") else str(p.get("sfx") or "")[:200],
            "speaker": b.get("character"), "text": b.get("text"), "emotion": b.get("emotion"),
            "seconds": beat_seconds(b), "stage": stage, "blueprint": blueprint,
            **({"fixed": True, "planned": beat_seconds(b)} if b.get("fixed") else {}),
            **({"lipsync": bool(hint["lipsync"])} if "lipsync" in hint else {}), **({"angle": hint["angle"]} if hint.get("angle") else {}),
            **({"sfxLocked": True} if hint.get("sfx") else {}), **({"filmShot": b["shot"]} if b.get("shot") else {})}


# ---------- 5b. the sound designer ----------
SOUND_SYS = """You plan what the audience hears in one part of an animated episode: an ambience per scene, a sound
effect for every action shot and one music cue for the part."""


def plan_sound(s: dict, script: dict, shots: list[dict], log: Callable[[dict], None] | None = None, summary: str = "") -> dict:
    dna = DNA.normalize(s.get("dna"))
    locs = {x["id"]: x for x in s.get("locations") or []}
    scenes = script.get("scenes") or []
    prompt = (f"Design DNA sound: {json.dumps(dna['sound'])}\nPart summary: {summary}\nScenes: "
              + json.dumps([{"scene": sc["id"], "place": locs.get(sc["location"], {}).get("description") or sc["location"], "time": sc.get("time")}
                            for sc in scenes], ensure_ascii=False)
              + "\nAction shots: " + json.dumps([{"beat": x["id"], "action": x["motion"], "sfx_draft": x.get("sfx")}
                                                  for x in shots if x["kind"] == "action"], ensure_ascii=False)
              + '\n\nAnswer as JSON: {"ambience": {"s1": ""}, "sfx": {"s1b2": ""}, "music": ""}')
    data = ask(s, "sound designer", system("avos-sound-designer", SOUND_SYS), prompt, log, max_tokens=2500, temperature=0.5)
    data = data if isinstance(data, dict) else {}
    amb = data.get("ambience") if isinstance(data.get("ambience"), dict) else {}
    sfx = data.get("sfx") if isinstance(data.get("sfx"), dict) else {}
    out = {"ambience": {}, "sfx": {}, "music": str(data.get("music") or "").strip()[:300] or
           f"{dna['sound']['music']}, {dna['motion']['pacing']} energy, follows the part: {summary[:120]}"}
    for sc in scenes:
        loc = locs.get(sc["location"], {})
        out["ambience"][sc["id"]] = str(amb.get(sc["id"]) or "").strip()[:200] or \
            f"quiet room tone of {loc.get('description') or sc['location']}, {sc.get('time', 'day')}" + \
            (f", {dna['sound']['ambience']}" if dna["sound"].get("ambience") else "")
    for x in shots:
        if x["kind"] == "action":
            out["sfx"][x["id"]] = str(sfx.get(x["id"]) or x.get("sfx") or "").strip()[:200]
    return out


# ---------- 5c. shot QA (a vision model checks character, motion, art style, artifacts) ----------
QA_SYS = """You are an animation supervisor checking one shot against the character sheets and the Design DNA:
character, motion, art style, artifacts. Fail only clear, visible problems and say how to fix each in one sentence."""


def qa_shot(s: dict, shot: dict, images: list, stage: str, log: Callable[[dict], None] | None = None) -> dict | None:
    """images: the sheets of the characters in the shot, then the frame (keyframe) or a start/middle/end strip (clip).
    None when the crew can't see pictures (then only the technical checks run)."""
    c = crew(s, "shot QA", log)
    if not c.enabled or not c.vision():
        return None
    cast = {x["id"]: x for x in s.get("characters") or []}
    names = [cast[i]["name"] for i in shot.get("subjects") or [] if i in cast]
    prompt = (f"Design DNA: {DNA.style_clause(s.get('dna') or {})}\n"
              f"The first {len(images) - 1} picture(s) are the character sheets of: {', '.join(names) or 'nobody'}. "
              f"The last picture is the {'keyframe' if stage == 'key' else 'clip: start, middle and end frames side by side'} of the shot.\n"
              f"The shot should show: {shot.get('picture')}" + (f"; motion: {shot.get('motion')}" if stage == "clip" else "") + "\n"
              '\nAnswer as JSON: {"character": {"ok": true, "why": ""}, '
              + ('"motion": {"ok": true, "why": ""}, ' if stage == "clip" else "")
              + '"style": {"ok": true, "why": ""}, "artifacts": {"ok": true, "why": ""}, "fix": "one sentence for the regeneration"}')
    try:
        data = ask(s, "shot QA", system("avos-shot-qa", QA_SYS), prompt, log, max_tokens=800, temperature=0.1, images=images)
    except WriterError as e:
        return {"pass": True, "skipped": str(e)[:200]}
    if not isinstance(data, dict):
        return {"pass": True, "skipped": "no answer"}
    checks = {k: {"ok": bool((data.get(k) or {}).get("ok", True)), "why": str((data.get(k) or {}).get("why") or "")[:200]}
              for k in ("character", "motion", "style", "artifacts") if isinstance(data.get(k), dict)}
    return {"pass": all(v["ok"] for v in checks.values()), "checks": checks, "fix": str(data.get("fix") or "")[:300]}


# ---------- 6. continuity ----------
CONT_SYS = """You keep the story memory of an animated series. Summarise what happened in this part in 1-3
sentences (who did what, what changed), and list any NEW facts that must stay true later (a broken TV, a new
neighbour, a secret). English."""


def remember(s: dict, script: dict, log: Callable[[dict], None] | None = None) -> dict:
    lines = [f"{b.get('character') or ''}: {b['text']}" if b["type"] == "line" else f"[{b['text']}]"
             for sc in script.get("scenes") or [] for b in sc.get("beats") or []]
    data = ask(s, "continuity", system("avos-continuity", CONT_SYS), "\n".join(lines)[:12000] + '\n\nAnswer as JSON: {"summary": "", "facts": [""]}', log, max_tokens=1200)
    if not isinstance(data, dict) or not data.get("summary"):
        acts = [b["text"] for sc in script.get("scenes") or [] for b in sc.get("beats") or [] if b["type"] == "action"]
        data = {"summary": " ".join(acts[:3])[:400] or "The story continued.", "facts": []}
    return {"summary": str(data.get("summary"))[:600], "facts": [str(f)[:200] for f in (data.get("facts") or []) if f][:8]}
