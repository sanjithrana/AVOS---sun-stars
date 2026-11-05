"""Idea → plan (title, presenter, props, world, shots with narration and camera). The AI crew writes it as JSON;
with the built-in crew (no AI) a sensible outline comes from rules so the whole flow still runs."""
from __future__ import annotations

import re
from typing import Any, Callable

from ..series import languages, writers
from . import cinema, memory, prompts, research, spec

SYSTEM = """You are the director of a short vertical science/explainer video channel (3D, bright, funny, fast). Answer with ONE JSON object only.
{"title":str,"hook":str,"music":str,
 "characters":[{"id":str,"name":str,"look":"face, hair, outfit colours, age, one casting sentence of voice","voice":str,"role":"presenter|supporting"}],
 "props":[{"id":str,"name":str,"look":"shape, material, colour, size"}],
 "world":{"name":str,"look":"set, colours, lighting"},
 "shots":[{"shot_type":"presenter|demonstration|macro_close_up|scientific_cutaway|result|reaction|establishing",
  "seconds":2-8,"narration":"what the voice says (speakable, ~14 characters per second)","action":"what we SEE, concrete",
  "characters":[ids],"props":[ids],"camera":{"type":"wide|medium|close_up|macro_close_up|over_shoulder|top_down|cutaway",
  "movement":"static|push_in|pull_out|pan_right|pan_left|orbit|tilt_up|tilt_down","lens_mm":24-85},
  "physics":bool,"visualization":{"cross_section":bool,"force_arrows":bool},"sfx":str}]}
Rules: shot 1 is a strong visual hook that makes people stay (a question or a surprise); every action follows from the one before; each beat says what happens and how each character reacts; escalate to a reveal and a payoff held on a clear final image. Alternate medium shots of the presenter with macro close-ups of hands, props and the key detail. When the explanation is invisible (air pressure, heat, electricity) show it as ONE 3D cutaway with glowing arrows or colour flows - never letters, numbers or charts in the picture. Keep the same presenter outfit and the same set in every shot. End on a short funny reaction or a surprising result. Total length must match the requested seconds. Narration must be true and simple; if unsure of a fact, say less."""


def builtin(brief: str, seconds: int, fmt: str) -> dict:
    topic = " ".join(str(brief).split())[:90] or "a surprising science trick"
    third = max(2.0, round(seconds / 6, 1))
    P, T = "host", "thing"
    shots = [
        {"shot_type": "presenter", "seconds": third, "narration": f"{topic} Sounds impossible, right?", "action": "the presenter looks at the camera and points at the prop on the table",
         "characters": [P], "props": [T], "camera": {"type": "medium", "movement": "push_in"}},
        {"shot_type": "macro_close_up", "seconds": third, "narration": "Look closely at what we are using.", "action": "macro shot of the main prop on the table, hands placing it",
         "props": [T], "camera": {"type": "macro_close_up", "movement": "pan_right", "lens_mm": 85}},
        {"shot_type": "demonstration", "seconds": third * 1.2, "narration": "Now watch what happens when I try it.", "action": "the presenter performs the experiment with the prop",
         "characters": [P], "props": [T], "physics": True, "camera": {"type": "over_shoulder", "movement": "push_in"}},
        {"shot_type": "scientific_cutaway", "seconds": third * 1.5, "narration": "Inside, the hidden force explains everything.", "action": "3D cross-section of the prop with glowing arrows showing the force",
         "props": [T], "physics": True, "camera": {"type": "cutaway", "movement": "orbit"}},
        {"shot_type": "result", "seconds": third, "narration": "And that is why it works.", "action": "the presenter shows the result proudly",
         "characters": [P], "props": [T], "camera": {"type": "medium", "movement": "static"}},
        {"shot_type": "reaction", "seconds": third, "narration": "Try it yourself!", "action": "a second funny character reacts in surprise",
         "characters": [P], "camera": {"type": "close_up", "movement": "push_in"}},
    ]
    film = [("medium shot, slow push-in, 50mm, shallow depth of field", "soft key light from the left, warm and even", "light curious hum, a small clack"),
            ("macro close-up, slow pan, 85mm lens", "warm side light with bright highlights on the material", "close, crisp handling sounds"),
            ("over-the-shoulder, push-in, 35mm", "bright overhead studio light, gentle fill", "a short whoosh as it moves"),
            ("3D cutaway, slow orbit, 24mm", "cool blue-cyan glow inside, dark surroundings", "rising electric hum"),
            ("medium shot, static, 50mm", "warm and inviting, wrapped around the presenter", "soft resolving chord"),
            ("close-up, push-in, 85mm", "warm light, soft shadows", "a short happy sting")]
    for sh, (c, l, a) in zip(shots, film):
        sh.update({"camera_note": c, "lighting": l, "audio": a})
    return {"title": topic[:60], "hook": shots[0]["narration"],
            "logline": f"A friendly host shows {topic[:70]} and explains the hidden reason it works.",
            "palette": [{"name": "Warm yellow", "hex": "#F2C94C"}, {"name": "Soft orange", "hex": "#F2994A"}, {"name": "Beige stone", "hex": "#D9C7A1"},
                        {"name": "Olive green", "hex": "#6B8E23"}, {"name": "Sky blue", "hex": "#7FAFD4"}],
            "camera_language": "Medium shots of the host, macro close-ups of the prop, one 3D cutaway for the hidden force.",
            "lighting_note": "Warm key light on the host; cool cyan glow for the invisible force.", "sound_design": "Light curious music, small clean sound effects.", "music": "light curious suspense, playful, instrumental",
            "characters": [{"id": P, "name": "Host", "look": "friendly young presenter, short dark hair, bright jacket, expressive face", "voice": "warm, energetic, clear"}],
            "props": [{"id": T, "name": "Main prop", "look": f"the main object of the experiment: {topic}"}],
            "world": {"name": "Studio", "look": "bright cyan studio, soft light, clean table"}, "shots": shots}


MODES = {"summarize": "summarizes the article's main ideas for a general viewer",
         "explain": "explains the article's ideas simply, step by step, as a friendly teacher",
         "story": "retells the article as a short story with a hook, a turn and an ending",
         "highlights": "shows the article's key points one by one, each as a short punchy beat"}


DIRECTOR_RULES = prompts.DIRECTOR          # the built-in text; the live version (possibly improved) comes from the prompt library

BRIEF_EXTRA = ("If the brief already contains a title, duration, visual style, narration style or numbered scenes, FOLLOW them: keep its scene order and "
               "mood, and do not invent a different story. Also add a field \"style\": one sentence describing the look of every picture, taken from "
               "the brief if it names one (else an empty string). ")
BRIEF_RULES = DIRECTOR_RULES + BRIEF_EXTRA


def plan(s: dict, log: Callable[[dict], None] | None = None, note: str = "") -> dict:
    """The plan for project `s` (brief, seconds, aspect, language, crew)."""
    lang = languages.get(s.get("language") or "en")
    rules, rv = prompts.pick("director.rules", s.get("id") or "")
    cine, cv = prompts.pick("director.cinema", s.get("id") or "")
    used = [["director.rules", rv], ["director.cinema", cv]]
    rules += cine + cinema.guide()
    if s.get("mode") == "story" or re.search(r"\b(story|stories|funny|comedy|chase[sd]?|heist|cartoon|adventure|villain|revenge|prank|thief|steals?|twist|short film|pixar|mistakes?)\b", s.get("brief") or "", re.I):
        st, sv = prompts.pick("director.story", s.get("id") or "")
        rules += st
        used.append(["director.story", sv])
    else:
        ex, ev = prompts.pick("director.explain", s.get("id") or "")
        rules += ex
        used.append(["director.explain", ev])
    rules += BRIEF_EXTRA
    src = s.get("source")
    if src:
        from . import article
        if not writers.uses_ai(s):
            raise writers.WriterError("A video from an article needs an AI script writer. Choose Ollama or Groq under Models → Script writer.")
        mode = MODES.get(s.get("mode") or "summarize", MODES["summarize"])
        prompt = (f"Source article (facts come ONLY from this text; do not invent facts):\n{article.excerpt(src)}\n\n"
                  f"Make a video that {mode}. Length: about {s['seconds']} seconds. Format: {s['aspect']}. Narration language: {lang.name}.\n"
                  + (f"Change requested: {note}\n" if note else "") + rules + "Write the JSON plan.")
    else:
        prompt = (f"Idea: {s['brief']}\nLength: about {s['seconds']} seconds. Format: {s['aspect']}. Narration language: {lang.name}.\n"
                  + research.facts_block(s.get("research")) + memory.cast_block(s["brief"])
                  + (f"Change requested: {note}\n" if note else "") + rules + "Write the JSON plan.")
    data = writers.ask(s, "story", writers.system("avos-explainer-director", SYSTEM), prompt, log, max_tokens=3600, temperature=0.7)
    if data is None:
        return spec.norm_plan(builtin(s["brief"], s["seconds"], s["aspect"]), s["seconds"], s["aspect"])
    try:
        out = spec.norm_plan(data, s["seconds"], s["aspect"])
        out["pk"] = used               # which prompt version wrote this plan (the library learns from how it turns out)
        return out
    except ValueError as e:
        writers.need(s, False, f"video plan ({e})")
        return spec.norm_plan(builtin(s["brief"], s["seconds"], s["aspect"]), s["seconds"], s["aspect"])
