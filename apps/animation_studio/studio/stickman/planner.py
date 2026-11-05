"""The AI's creative stages as small structured calls (Groq-friendly sizes). Facts are never invented by the app:
the brief says what is well-established, what to check, and names the kinds of sources to check; nothing is marked verified."""
from __future__ import annotations

from typing import Any, Callable

from ..series import languages, writers
from . import spec, styles

RULES = """You are a researcher, stickman animation director, writer and character designer for faceless stickman video channels. Answer with ONE JSON object only.
Be accurate: if you are not sure of a date, number or name, leave it out or mark it for checking. Never invent quotations, statistics, motives, casualty figures, named witnesses, product claims or decisive actions. Use narration, not invented dialogue. Keep suffering respectful and non-graphic. Fictional analogies are labelled as staging, never presented as fact."""

GENERAL_TOPICS = """Give EIGHT specific video ideas that suit this style ({made_for}), each built on a counter-intuitive question, a surprising mechanism or a relatable conflict (never a broad category).
{{"topics":[{{"title":str,"date_place":"the domain or setting","premise":"one factual sentence","opening_visual":"the paradox we see in the first two seconds","conflict":str,"ending":"the truth or payoff","duration_s":60,"clips":6,"difficulty":"easy|medium|hard"}}],"recommended":index,"why":"one sentence"}}"""

TOPICS = """Give EIGHT specific historical events (never broad categories like "ancient history"). Mix eras and regions, include lesser-known events with strong visual storytelling.
{"topics":[{"title":str,"date_place":str,"premise":"one factual sentence","opening_visual":"what we see in the first two seconds","conflict":str,"ending":"consequence or memorable factual insight","duration_s":60,"clips":6,"difficulty":"easy|medium|hard"}],"recommended":index,"why":"one sentence"}"""

BRIEF = """Write the fact brief for the topic (a historical event, a science or psychology idea, a business or tech story). Prefer what museums, archives, scholarly publications and reputable institutions agree on.
{"event":str,"date":str,"location":str,"people":[str],"cause":str,"turning_point":str,"outcome":str,
 "facts":[{"claim":str,"confidence":"well-established|check"}],"disputed":["where sources disagree, briefly"],
 "sources_to_check":["names of institutions, archives or publications to check (no web addresses)"],"dramatization_notes":["anything in the video that is staging, not record"]}"""

STORY = """Write the director's treatment as exactly {n} clips of ten seconds. {arc} Every clip has a different narrative job and turns an abstract idea into a concrete physical stick-figure action or visual metaphor (anxiety becomes a cage; attention becomes a battery running low). Narration: English, {lo}-{hi} spoken words per clip, natural sentence boundaries, fewer for complex names.
{{"title":str,"hook":str,"clips":[{{"purpose":str,"narration":str,"main_action":"the one dominant visual action"}}]}}"""

ROSTER = """Design the smallest cast the story needs: 1 to 3 recurring characters, all drawn in this style: {grammar} {fixed}Give each named character two or three fixed identity cues that differ without relying on colour alone, and at most three saturated accent colours (an ordinary colour name plus its hex code). Generic crowd figures stay subordinate.
{"characters":[{"name":str,"role":str,"age_presentation":str,"head_shape":str,"height_heads":number,"proportions":str,"eyes":str,"brows":str,"mouth":str,"hair_or_headwear":str,"clothing":"layers","footwear":str,"accents":[{"name":str,"hex":"#rrggbb"}],"signature_prop":str,"distinguishing_feature":str,"planned_damage":str}]}"""

CLIP = """Direct clip {n} of {total} (ten seconds) in this style: {look} Three timed beats tied to the narration: setup (0-3s, establish or inherit the premise), escalation (3-7s, the character physically acts on the metaphor), payoff (7-10s, the climax that starts the outgoing motion). Use at least four relevant visual devices (expressive action, environmental change, a concrete metaphor, an icon-only symbol, particles or light, a camera move, a foreground wipe, a match cut), a visible change every two to three seconds, concrete physical actions (leaping, pushing, drawing luminous lines, opening doors), never idle standing, never abstract liquid morphing, no visible words or numbers. {location_rule} Use only these character ids: {ids}.
{{"location":str,"time_of_day":str,"scenery":"period-correct","framing":str,"camera_angle":str,"foreground":str,"middle":str,"background":str,
 "chars":[{{"id":str,"position":str,"facing":str,"pose":str,"expression":str,"clothing_state":str,"prop_grip":str}}],
 "opening_setup":"the state BEFORE the main action",
 "beats":{{"setup":"0-3s","escalation":"3-7s with a clear body pose and prop movement","payoff":"7-10s, ends in an explicitly described final state"}},
 "camera_move":"static|slow push in|slow pull out|pan left|pan right|tilt up|tilt down","prop_interaction":str,
 "final_state":{{"summary":str,"chars":[{{"id":str,"position":str,"facing":str,"holds":str,"emotion":str}}]}},
 "sfx":["a few motivated sound effects"],"music":"unobtrusive direction","transition":"match|cut","transition_note":"for a cut: what changes and what stays fixed"}}"""

EXAMPLES = [
    {"title": "The Great Stink of London", "date_place": "Summer 1858, London, England", "premise": "A hot summer made the sewage-filled River Thames smell so foul that Parliament, beside the river, rushed through a plan for London's modern sewer system.",
     "opening_visual": "A stickman politician presses a cloth to his face as the river steams outside a Parliament window.", "conflict": "Years of political delay against a stench no one could ignore.",
     "ending": "Engineer Joseph Bazalgette's sewers were built, and parts of the network still serve London.", "duration_s": 60, "clips": 6, "difficulty": "easy"},
    {"title": "The Christmas Truce", "date_place": "December 1914, Western Front, Belgium and France", "premise": "In parts of the front, British and German soldiers paused the fighting around Christmas, sang carols and met in no man's land.",
     "opening_visual": "Two stickman soldiers raise their heads over opposite trenches as a song drifts across frozen mud.", "conflict": "Orders to keep fighting against a shared wish for a pause.",
     "ending": "The truce was local and temporary, and the war resumed.", "duration_s": 60, "clips": 6, "difficulty": "medium"},
    {"title": "The Emu War", "date_place": "November-December 1932, Western Australia", "premise": "Farmers asked for help against thousands of emus damaging crops, and soldiers with machine guns were sent.",
     "opening_visual": "A stickman farmer stares at a huge flock of tall birds standing in his wheat field.", "conflict": "Soldiers with machine guns against fast, scattering birds.",
     "ending": "The operation was widely seen as a failure and was called off; the emus remained.", "duration_s": 60, "clips": 6, "difficulty": "easy"},
    {"title": "Operation Mincemeat", "date_place": "April 1943, Spain and Britain", "premise": "British planners dressed a dead man as a fictional officer and let him wash ashore in Spain carrying false papers to mislead the Axis about where the Allies would invade.",
     "opening_visual": "A stickman in a naval uniform lies still in the shallows of a Spanish beach at dawn while a fisherman stares.", "conflict": "Allied secrecy against Axis suspicion.",
     "ending": "The Allies invaded Sicily in July 1943, and historians credit the deception with helping.", "duration_s": 70, "clips": 7, "difficulty": "hard"},
    {"title": "The Year Without a Summer", "date_place": "1815-1816, Indonesia to Europe and North America", "premise": "The April 1815 eruption of Mount Tambora put so much ash and gas into the sky that the following year's weather turned cold and harvests failed.",
     "opening_visual": "A stickman farmer stares at frost on his crops in the middle of summer.", "conflict": "Farmers against a sky that would not warm.",
     "ending": "Hunger and migration followed in places, and the gloomy summer of 1816 is often linked to the writing of Frankenstein.", "duration_s": 60, "clips": 6, "difficulty": "medium"},
    {"title": "The Halifax Explosion", "date_place": "6 December 1917, Halifax, Nova Scotia, Canada", "premise": "Two ships collided in Halifax harbour; one carried explosives, and the blast destroyed much of the city's north end.",
     "opening_visual": "Two stickman ships drift toward each other in a narrow harbour while a small fire starts on one deck.", "conflict": "A busy wartime harbour against a collision no one could stop.",
     "ending": "The city received help from nearby places, including Boston, and rebuilt.", "duration_s": 60, "clips": 6, "difficulty": "hard"},
    {"title": "The Carrington Event", "date_place": "1-2 September 1859, worldwide", "premise": "A huge solar storm lit the sky with auroras far from the poles and disrupted telegraph systems.",
     "opening_visual": "A stickman telegraph operator jumps back as sparks fly from his machine.", "conflict": "A fragile new technology against the Sun.",
     "ending": "The event is still used to show how a similar storm could affect today's electronics.", "duration_s": 60, "clips": 6, "difficulty": "easy"},
    {"title": "Mansa Musa's Pilgrimage", "date_place": "1324, Mali to Egypt and Arabia", "premise": "The ruler of the Mali Empire travelled to Mecca with a vast caravan and gave away so much gold that prices in Cairo were reported to be affected.",
     "opening_visual": "A long stickman caravan crosses sand dunes, a camel carrying a gleaming sack of gold.", "conflict": "A long desert journey against its cost and risk.",
     "ending": "Accounts of his wealth spread across the Mediterranean world and put Mali on maps.", "duration_s": 60, "clips": 6, "difficulty": "medium"},
]
WHY = "The Great Stink has a clear problem, a ticking clock, a turning point and a lasting result, and every beat is easy to draw."


def _ask(s: dict, stage: str, system: str, prompt: str, log: Callable[[dict], None] | None, max_tokens: int, temperature: float = 0.6) -> Any:
    data = writers.ask(s, "story", writers.system("avos-stickman-director", RULES) + "\n\n" + system, prompt, log, max_tokens=max_tokens, temperature=temperature)
    if data is None:
        raise writers.WriterError(f"Stickman Studio needs an AI writer for the {stage} (pick Groq or another AI crew); the built-in crew can't write history responsibly.")
    return data


def topics(s: dict, log: Callable[[dict], None] | None = None, note: str = "") -> dict:
    if not writers.uses_ai(s):
        return {"topics": [dict(t) for t in EXAMPLES], "recommended": 0, "why": WHY}
    st = styles.get(s.get("style"))
    system = TOPICS if st.get("history") else GENERAL_TOPICS.format(made_for=st["made_for"])
    data = _ask(s, "topic ideas", system, (f"Interest: {s['interest']}\n" if s.get("interest") else "") + (f"Change: {note}\n" if note else "") + "Give the eight ideas.", log, 3200, 0.8)
    try:
        return spec.norm_topics(data)
    except ValueError as e:
        writers.need(s, False, f"topic list ({e})")
        return {"topics": [dict(t) for t in EXAMPLES], "recommended": 0, "why": WHY}


def brief(s: dict, p: dict, log: Callable[[dict], None] | None = None) -> dict:
    t = p["project"]
    data = _ask(s, "fact brief", BRIEF, f"Event: {t['title']} ({t['date_place']}). Premise: {t['premise']}" + (f"\nSource copy:\n{p['source_text'][:4000]}" if p.get("source_text") else ""), log, 2600, 0.3)
    return spec.norm_brief(data)


def story(s: dict, p: dict, log: Callable[[dict], None] | None = None, note: str = "") -> dict:
    t, b = p["project"], p["brief"]
    n = int(p["clip_count"])
    facts = "; ".join(f["claim"] for f in b["facts"][:10])
    src = (f"Source copy (preserve its core claim, names, numbers and meaning; strengthen a weak opening; remove repetition):\n{p['source_text'][:5000]}\n"
           if p.get("source_text") else "")
    prompt = (src + f"Event: {t['title']} ({t['date_place']}). Tone: {t['tone']}. Language: {languages.get(p['language']).name}.\nFacts to rely on: {facts}\n"
              f"Cause: {b['cause']} Turning point: {b['turning_point']} Outcome: {b['outcome']}\n" + (f"Change: {note}\n" if note else "") + "Write the clips.")
    system = STORY.format(n=n, lo=spec.NARRATION_WORDS[0], hi=spec.NARRATION_WORDS[1], arc=styles.ARC[styles.get(p.get("style"))["arc"]])
    return spec.norm_story(_ask(s, "story", system, prompt, log, 2800, 0.7), n)


BIBLE = """Write the continuity bible for this film, like a director's proposal: what must stay identical in every clip.
{"premise":"one sentence","theme":str,"audience":str,"layout":"the fixed spatial arrangement of the main location: what is left, right, near, far, where each light source and prop sits","props":[{"name":str,"look":"exact count, shape, material, colour","rule":"who holds it, which hand, where it stays"}],"visual_logic":["rules the images must obey, e.g. a shadow stays physically connected to its source and never becomes a creature"],"music":"one continuous theme: instruments, how it develops, never restarting at an edit","text_policy":"no subtitles, titles, readable signs or on-screen text"}"""


def bible(s: dict, p: dict, log: Callable[[dict], None] | None = None) -> dict:
    lines = " | ".join(f"{c['n']}: {c['main_action']} / {c['narration']}" for c in p["story"]["clips"])
    src = f"\nThe brief:\n{p['source_text'][:3000]}" if p.get("source_text") else ""
    d = _ask(s, "continuity bible", BIBLE, f"Film: {p['project']['title']}. Style: {styles.get(p.get('style'))['look']}{src}\nClips: {lines}", log, 1800, 0.5)
    d = d if isinstance(d, dict) else {}
    props = [{"name": spec._s(x.get("name"), 60), "look": spec._s(x.get("look"), 200), "rule": spec._s(x.get("rule"), 160)}
             for x in (d.get("props") or []) if isinstance(x, dict) and x.get("name")][:6]
    return {"premise": spec._s(d.get("premise"), 240), "theme": spec._s(d.get("theme"), 160), "audience": spec._s(d.get("audience"), 120),
            "layout": spec._s(d.get("layout"), 600), "props": props, "visual_logic": [spec._s(x, 200) for x in (d.get("visual_logic") or [])][:5],
            "music": spec._s(d.get("music"), 240) or styles.get(p.get("style"))["music"], "text_policy": spec._s(d.get("text_policy"), 160) or "no on-screen text"}


INSPECT = ("You inspect one generated frame of a stickman film against its continuity bible. Report ONLY material defects you can see: wrong character "
           "design, wrong prop count or hand, broken layout, broken visual logic (e.g. a shadow detached from its source), accidental text, duplicated anatomy. "
           'Answer JSON: {"ok": true|false, "defects": ["..."], "fix": "one sentence of targeted correction for the next try"}')


def inspect(s: dict, p: dict, images: list, what: str, log: Callable[[dict], None] | None = None) -> dict | None:
    """A vision model's continuity check of one image (None when the crew cannot see pictures)."""
    c = writers.crew(s, "inspector", log)
    if not c.enabled or not c.vision():
        return None
    b = p.get("bible") or {}
    rules = f"Character: {styles.get(p.get('style'))['anchor']} Layout: {b.get('layout', '')} Props: " + "; ".join(f"{x['name']} ({x['look']}; {x['rule']})" for x in b.get("props") or []) \
        + " Rules: " + "; ".join(b.get("visual_logic") or []) + f" Expected: {what}"
    try:
        d = writers.ask(s, "inspector", writers.system("avos-stickman-inspector", INSPECT), rules, log, max_tokens=500, temperature=0.1, images=images)
    except writers.WriterError as e:
        return {"ok": True, "skipped": str(e)[:160]}
    if not isinstance(d, dict):
        return None
    return {"ok": bool(d.get("ok", True)), "defects": [spec._s(x, 200) for x in (d.get("defects") or [])][:5], "fix": spec._s(d.get("fix"), 300)}


def roster(s: dict, p: dict, log: Callable[[dict], None] | None = None) -> list[dict]:
    t = p["project"]
    lines = " | ".join(f"{c['n']}: {c['narration']}" for c in p["story"]["clips"])
    st = styles.get(p.get("style"))
    system = ROSTER.replace("{grammar}", st["anchor"]).replace("{fixed}", "Character 1 is the style's fixed lead: keep exactly that design and give it only a name, role and prop. " if st.get("fixed") else "")
    return spec.norm_roster(_ask(s, "characters", system, f"Event: {t['title']} ({t['date_place']}).\nStory: {lines}", log, 2600, 0.6))


def clip_plan(s: dict, p: dict, n: int, log: Callable[[dict], None] | None = None) -> dict:
    ids = [c["id"] for c in p["roster"]]
    prev = p["clips"][-1]["outgoing"] if p.get("clips") else None
    sc = p["story"]["clips"][n - 1]
    cast = "; ".join(f"{c['id']} {c['name']} ({c['role']}; prop: {c['signature_prop']})" for c in p["roster"])
    prompt = (f"Event: {p['project']['title']} ({p['project']['date_place']}).\nCast: {cast}\nClip {n} purpose: {sc['purpose']}\nNarration: {sc['narration']}\nMain action: {sc['main_action']}\n"
              + (f"The previous clip ended in this state, so begin from it unless you mark a cut: {prev['summary']} " + "; ".join(f"{c['id']} {c['position']}, {c['facing']}, holding {c['holds']}" for c in prev["chars"]) + "\n" if prev else "")
              + ("The next clip is the last. End on the consequence.\n" if n == len(p["story"]["clips"]) - 1 else "") + "Write the clip plan.")
    st = styles.get(p.get("style"))
    rule = ("Each new clip opens in a different recognizable story location (name it); character, props and direction continue." if st["id"] == "a4-cozy"
            else "No unrelated locations or time jumps unless you mark a cut.")
    system = CLIP.format(n=n, total=len(p["story"]["clips"]), ids=", ".join(ids), look=st["look"], location_rule=rule)
    return spec.norm_clip(_ask(s, f"clip {n} plan", system, prompt, log, 2200, 0.6), n, set(ids), prev)
