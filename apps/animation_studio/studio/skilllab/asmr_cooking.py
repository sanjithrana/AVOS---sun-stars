"""ASMR Cooking skill: name a dish, get a hyper-realistic vertical cooking video.

One look is locked for every shot so the video cuts together as one piece: matte-black latex gloves (never a face, never a person),
a pristine white board against a pitch-black background, softbox light and a macro lens. The AI writes the recipe and the shot list;
the look, the camera and the sound are built here in code, so they cannot drift shot to shot.

The pipeline: recipe and shot list -> one picture per shot (each drawn from the one before, so the food keeps its state) -> one clip
per shot (Seedance with its own ASMR sound, or a macro camera move on the picture) -> joined with the kitchen foley under it.

Ingredient continuity runs raw -> washed -> peeled -> chopped -> seasoned -> cooked -> plated, and every shot states what is left
over from the shot before it, so nothing appears or vanishes between cuts.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from .. import house
from ..series import media, writers
from . import base, compose, store, takes

ID = "asmr-cooking"
INFO = {
    "id": ID, "name": "ASMR Cooking", "group": "Food and ASMR", "kind": "recipe",
    "made_for": "Name a dish: it writes the recipe and the shot list, then makes a hyper-realistic cooking video with ASMR sound",
    "about": "One locked look for every shot - a wooden board filling the frame, one soft window light, a macro lens, never a face. The AI writes the "
             "recipe and a shot list that walks the ingredients from raw to plated, emptying the board as it goes; shots continue from one another "
             "while the cooking stays in one place and are set up fresh when it moves to the bowl, the pan or the plate. Then each is animated and "
             "given its own kitchen sound (sizzle, chop, pour, simmer).",
    "input": "A dish, e.g. cheese corn nuggets, paneer butter masala, garlic butter prawns",
    "outputs": ["Recipe and shot list", "Shot pictures", "ASMR video"],
    "aspect": "9:16", "aspects": ["9:16", "16:9"], "seconds": [30, 45, 60, 90, 120, 180], "default_seconds": 45, "native_audio": True,
    "examples": ["cheese corn nuggets", "paneer butter masala", "chocolate lava cake", "garlic butter prawns", "masala dosa", "Korean corn dogs"],
    "credit": "Workflow modelled on the 'Hyper-Realistic ASMR Cooking Studio' skill.",
    "make": [["media", "Recipe, shots and video"], ["prompts", "Recipe and prompts only"]],
    "cta": ["Write the recipe and the shot list", "Write the recipe and make the video"],
    "note": "The AI writes a real recipe and a shot list that walks the ingredients from raw to plated, then each "
            "shot is drawn and animated. Needs an AI writer (Models) and a picture model. A video model is optional: "
            "without a fal.ai key with credit each shot gets a macro camera move and kitchen sound made in code, and "
            "the video still gets finished rather than stopping.",
    "motions": [["video", "AI video for every shot with its own sound (Seedance, needs fal.ai credit)"],
                ["macro", "Macro camera move on each picture + kitchen sound made in code (free)"]],
    "hands": [["gloved", "Matte-black latex gloves - the ASMR channel look"],
              ["bare", "Bare hands - warmer, right for home cooking"]],
    "hands_label": "Hands",
}

# ---------- the locked look (every picture prompt carries it, short, because the free picture models cut long prompts) ----------
HANDS = ("exactly two hands in matte-black latex gloves, no more than two hands in frame, cropped at the wrist, "
         "no arms, no face, no person")
BARE = ("exactly two bare hands, warm natural skin, short clean nails, no more than two hands in frame, cropped at the wrist, "
        "no arms, no face, no person")
# The board FILLS the frame. Said plainly, because "a white board against a pitch-black background" makes the model draw a
# small white slab floating in black bands -- which is what the first version of this skill produced, shot after shot.
# The surface changes with the place. Describing a chopping board while the shot is at the stove is the kind of
# contradiction a picture model resolves by drawing both, which is how a pan ends up sitting next to the raw onions.
SURFACES = {
    "board": "a scratched pale wooden board filling the frame edge to edge, warm dark counter at the corners",
    "bowl": "a steel mixing bowl filling the frame, warm dark counter around it",
    "stove": "a dark steel pan filling the frame over a gas flame, the dark kitchen falling off behind it",
    "plate": "the dish filling the frame on a warm dark table, one cloth edge in the corner",
}
LIGHT = "one soft window light from the left, deep shadow to the right, shallow depth of field, macro lens, natural colour"
NEVER = "No text, no logo, no watermark, no face, no person, no third hand, no black bands - the food fills the frame."


def look_for(where: str) -> str:
    return f"Hyper-realistic macro food photography, {SURFACES.get(where or 'board', SURFACES['board'])}, {LIGHT}"


LOOK = look_for("board")

# Worded without naming the board: the same five angles have to read at the stove and over a plate too.
CAMERAS = {"top-down": "a locked top-down overhead macro shot", "45-degree": "a 45-degree macro shot from just above",
           "eye-level": "a low eye-level macro shot level with the surface", "side": "a tight side-on macro shot",
           "close": "an extreme close-up macro shot, the subject filling the frame"}
ORDER = ("top-down", "45-degree", "close", "side", "top-down", "eye-level")   # when the writer repeats itself, rotate
WHERE = {"board": "on the cutting board", "stove": "in the pan on the stove, the board out of shot",
         "bowl": "in the mixing bowl, the board out of shot", "plate": "on the serving plate, the board out of shot"}
STATES = ("raw", "washed", "peeled", "chopped", "seasoned", "cooked", "plated")
WORK = [("teaser", "the raw ingredients in their raw state, grouped on the board, nothing cut yet"),
        ("prep", "cutting and precision prep on the board: slicing, dicing, peeling or grating"),
        ("season", "spicing, seasoning and tactile mixing in a bowl"),
        ("assembly", "assembly and coating: dipping, breading, pouring or layering"),
        ("climax", "the cooking climax and the plating: high heat, sizzling, bubbling, then the finished dish and a macro reveal")]

SHOT_SECONDS = (3.0, 6.0)                 # one action per shot: shorter than this reads as a glitch, longer drags
MAX_CHAIN = 2                             # at most two shots in a row drawn FROM the one before; see balance()
COOKING_SHARE = 0.30                      # at least this much of the video is at the stove or on the plate


def balance(shots: list[dict], n: int) -> list[dict]:
    """Makes sure the video actually cooks something.

    A writer handed "eleven shots of paneer butter masala" will happily spend nine of them chopping, and a measured run
    did exactly that: nine near-identical boards, then two of a pan. So the cooking end of the recipe gets a floor. The
    writer keeps every choice it made well -- this only moves shots when it left too few at the stove.
    """
    if not shots:
        return shots
    shots[-1].update(where="plate", stage="climax")            # the video always ends on the finished dish
    want = max(1, round(n * COOKING_SHARE))
    cooking = [sh for sh in shots if sh["where"] in ("stove", "plate")]
    i = len(shots) - 2
    while len(cooking) < want and i > 0:                       # never shot 1: that one lays the ingredients out
        if shots[i]["where"] not in ("stove", "plate"):
            shots[i].update(where="stove", stage="climax")
            cooking.append(shots[i])
        i -= 1
    run = 0
    last_where = ""
    for sh in shots:                                           # a long chain of edits drifts back to its own input
        moved = sh["where"] != last_where
        run = 0 if moved else run + 1
        sh["fresh"] = moved or run >= MAX_CHAIN
        if sh["fresh"]:
            run = 0
        last_where = sh["where"]
    shots[0]["fresh"] = True
    return shots

RECIPE = """You are the director of a hyper-realistic ASMR cooking channel: vertical macro videos where two hands cook a real dish, no voice and no music, only the sound of the cooking. You are given a dish and a number of shots. You write the real recipe and then the shot list.

THE ONE RULE THAT MATTERS
Each shot must look DIFFERENT from the one before it. Different thing in frame, different camera, different place. A viewer must never see the same arrangement twice. If two shots would photograph the same, merge them and use the spare shot somewhere else in the recipe.

WRITE THE INSTANT, NOT THE INGREDIENTS
Every "action" is a single physical movement caught at its peak: the blade already halfway through the onion and touching the board, the cream already falling in a ribbon and already landing, the paneer already dropping into the oil. Never "the hands prepare the onion" and never a list of what is on the table. If the action could be photographed with nothing moving, it is the wrong action.

HOW MANY SHOTS WHERE
Chopping is not the video. At most half the shots are prep; at least a third are at the stove and the plate, where the dish actually becomes the dish. A recipe that is nine shots of a cutting board and two of a pan is a failed shot list, however good the chopping is.

RECIPE
- A real, correct recipe. Real ingredients, real quantities, real method, in the right order. If the dish is regional, keep it authentic.
- ONE action per shot: one cut, one pour, one mix, one fry. Never two.
- The shots walk the whole recipe in order through five stages: 1 raw ingredients laid out, 2 cutting and prep, 3 seasoning and mixing, 4 assembly or coating, 5 the cooking and the plating. Spend the most shots on whichever stages this dish actually needs. THE LAST SHOT IS ALWAYS THE FINISHED DISH, plated and garnished.

THE BOARD EMPTIES AS YOU COOK
This is what makes it look real. Once an ingredient is chopped it goes into a bowl or into the pan, and it is GONE from the board. By the cooking stage the board is nearly bare. Never leave the whole mise en place sitting in frame for ten shots.
- "gone": what has LEFT the frame since the last shot ("the onion is now in the pan, the peel is cleared"). Write "nothing yet" only for shot 1.
- "state": what is still in frame from the shot before, and how far along it is.

WHERE YOU ARE
- "where": board | bowl | stove | plate. Prep happens on the board. Mixing happens in a bowl. Anything cooking is at the stove with the board OUT OF SHOT - never show the pan sitting next to the raw ingredients. Plating is on the plate.

SHOW, DO NOT NAME
Picture models do not know what your ingredients look like. The first time an ingredient appears, describe it physically in "subject" instead of naming it alone: paneer is "matte ivory fresh paneer, slightly crumbly cut edges, not silky or translucent"; ghee is "golden semi-solid ghee"; curry leaves are "small glossy dark-green curry leaves on a stem". Never write a bare noun where a description would do.

Each shot has:
- "title": 2-5 words, the action, e.g. "Slicing the onion"
- "stage": teaser|prep|season|assembly|climax
- "where": board|bowl|stove|plate
- "state": one sentence, what is still in frame from the shot before and how far along it is
- "gone": one short clause, what has left the frame since the last shot
- "subject": exactly what is in frame, described physically - colour, texture, cut, sheen, size - plus the tool or vessel
- "action": what the hands do, as one physical movement
- "physics": what the food does - steam, oil splatter, bubbling viscosity, knife pressure, how the liquid falls, crumbs scattering
- "asmr": the sound, in the words of the sound itself, e.g. "crisp dry crunch", "loud oil sizzle tsssss", "soft knife thud on the board"
- "camera": top-down|45-degree|eye-level|side|close - and NEVER the same one twice in a row. Top-down for the board, side or eye-level for anything in a pan, close for the reveal.

Answer with ONE JSON object:
{"title":"the dish, title case","ingredients":["quantity + ingredient", ...],"tools":["the tools and vessels used"],"shots":[{...}, ...]}"""


def shots_for(total: float) -> int:
    """How many shots a video of this length holds: one action each, three to six seconds."""
    return max(5, min(40, round(float(total) / 4.2)))


def seconds_each(total: float, n: int) -> float:
    lo, hi = SHOT_SECONDS
    return max(lo, min(hi, float(total) / max(1, n)))


INFO["lengths"] = [{"seconds": n, "scenes": shots_for(n), "each": round(seconds_each(n, shots_for(n)), 1)} for n in INFO["seconds"]]


def subject_of(text: str) -> str:
    t = " ".join(str(text or "").split())
    m = re.search(r"(?:make|cook|recipe for|how to make)\s+(.+)", t, re.I)
    return (m.group(1) if m else re.split(r"[.!?\n]", t)[0]).strip(" .,'\"")[:120] or "a dish"


def _s(v: Any, n: int, fb: str = "") -> str:
    v = " ".join(str(v or "").split())
    return v[:n] if v else fb


def norm_recipe(d: Any, dish: str, n: int) -> dict:
    if not isinstance(d, dict) or not isinstance(d.get("shots"), list) or not d["shots"]:
        raise writers.WriterError("The AI writer didn't return a usable shot list. Try again, or pick another AI crew.")
    shots, last_cam, last_where = [], "", ""
    for i, sh in enumerate(d["shots"][:n]):
        sh = sh if isinstance(sh, dict) else {}
        stage = _s(sh.get("stage"), 12, "").lower()
        stage = stage if stage in {k for k, _ in WORK} else WORK[min(i * len(WORK) // max(1, n), len(WORK) - 1)][0]
        where = _s(sh.get("where"), 10, "").lower()
        if where not in WHERE:                                  # the stage says where it must be happening
            where = {"teaser": "board", "prep": "board", "season": "bowl", "assembly": "board", "climax": "stove"}[stage]
        cam = _s(sh.get("camera"), 12, "").lower()
        if cam not in CAMERAS or cam == last_cam:               # two shots in a row from the same angle look like one shot
            cam = next((c for c in ORDER[i % len(ORDER):] + ORDER[:i % len(ORDER)] if c != last_cam), "45-degree")
        shots.append({"n": i + 1, "title": _s(sh.get("title"), 60, f"Step {i + 1}"), "stage": stage, "where": where,
                      "state": _s(sh.get("state"), 300, "the board as it was left in the shot before"),
                      "gone": _s(sh.get("gone"), 160, "nothing yet" if i == 0 else ""),
                      "subject": _s(sh.get("subject"), 400, dish), "action": _s(sh.get("action"), 300, "the hands work on the board"),
                      "physics": _s(sh.get("physics"), 300, ""), "asmr": _s(sh.get("asmr"), 160, "soft handling sounds"),
                      "camera": cam, "fresh": True,
                      "picture": None, "video": None})
        last_cam, last_where = cam, where
    if len(shots) < n:
        raise writers.WriterError(f"The AI writer wrote {len(shots)} of {n} shots. Try again.")
    balance(shots, n)                                           # the cooking floor, then which shots may be edits
    return {"title": _s(d.get("title"), 90, dish.title()),
            "ingredients": [_s(x, 90) for x in (d.get("ingredients") or []) if str(x).strip()][:20],
            "tools": [_s(x, 60) for x in (d.get("tools") or []) if str(x).strip()][:12], "shots": shots}


def recipe(s: dict, dish: str, n: int, log: Callable[[dict], None] | None = None, secs: float = 4.2) -> dict:
    if not writers.uses_ai(s):
        raise writers.WriterError("ASMR Cooking needs an AI writer for the recipe (pick Groq or another AI crew in Models).")
    system = writers.directed("avos-asmr-cooking", RECIPE)
    stages = "; ".join(f"{i + 1} {what}" for i, (_, what) in enumerate(WORK))
    ask = (f"Dish: {dish}\nWrite exactly {n} shots. The five stages in order: {stages}.\nEach shot is on screen for about "
           f"{round(secs, 1)} seconds, so it holds ONE action.\nWrite the JSON.")
    return norm_recipe(writers.ask(s, "story", system, ask, log, max_tokens=4000, temperature=0.5), dish, n)


# ---------- prompts ----------
def _sentence(text: str) -> str:
    """A clause from the writer, turned into its own sentence so the prompt does not read as one run-on line."""
    t = " ".join(str(text or "").split()).rstrip(".")
    return f" {t[:1].upper()}{t[1:]}." if t else ""


def _hands(p: dict | None = None) -> str:
    return BARE if (p or {}).get("hands") == "bare" else HANDS


def _cap(body: str, tail: str = "", limit: int = 900) -> str:
    """Pollinations cuts a prompt at about 900 characters.

    The tail is the part that must never be the part that gets cut -- the "no face, no black bands" rules are worth more
    than the last clause of the description -- so it is reserved out of the limit and added back after the trim.
    """
    body, tail = " ".join(str(body or "").split()), " ".join(str(tail or "").split())
    room = limit - (len(tail) + 1 if tail else 0)
    if len(body) > room:
        cut = body[:room]
        body = cut[:cut.rfind(". ") + 1] if ". " in cut else cut
    return f"{body} {tail}".strip()


# Stems, not whole words: the writer says "slices", "slicing" and "sliced" in roughly equal measure, and an earlier
# pattern that listed only "slice" and "slicing" quietly missed the commonest form of all.
CUTTING = re.compile(r"\b(cut|slic|chop|dic|minc|julienn|halv|quarter|shred|grat|carv|score)(e|es|ed|ing|s)?\b", re.I)
POURING = re.compile(r"\b(pour|drizzl|tip|sprinkl|scatter|ladl|spoon|splash|stream)(e|es|ed|ing|s)?\b", re.I)


def peak_of(action: str) -> str:
    """The instant to photograph.

    "A knife and an onion on a board" is what a model draws when it is given nouns, and that is what eleven shots of a
    measured run looked like: the blade hovering, never touching anything. Naming the exact instant -- the blade
    already halfway through, the stream already falling -- is the difference between a photograph of ingredients and a
    photograph of cooking.
    """
    a = action or ""
    if CUTTING.search(a):
        return ("Caught mid-stroke: the blade is already buried halfway through, the cut piece has fallen away from "
                "the rest, and the knife is in contact with the board. Not hovering, not finished -")
    if POURING.search(a):
        return ("Caught mid-pour: the stream is already falling and has already landed, mid-air and in motion. Not "
                "about to pour, not finished -")
    return "Caught at the peak of the movement, not before it and not after it -"


def _still(sh: dict) -> str:
    t = (sh.get("state") or "").strip().rstrip(".")
    return f"Still in frame from the moment before: {t}. " if t else ""


def _offscreen(sh: dict) -> str:
    """What has already been used. Saying it is gone is the only thing that empties the board."""
    t = (sh.get("gone") or "").strip().rstrip(".")
    if not t or t.lower() in ("nothing yet", "nothing", "none"):
        return ""
    return f"Already used and now OUT OF FRAME, do not draw it: {t}. "


def image_prompt(r: dict, sh: dict, aspect: str = "9:16", hands: str = "") -> str:
    """One shot's picture, drawn from nothing.

    The differences lead and the look follows. The old version opened every prompt with the same forty words of look, so
    eleven shots began identically and the model, handed the previous frame as well, simply gave the frame back. What
    changes between shots - the angle, the subject, the action - now comes first.
    """
    shape = "vertical 9:16, the frame filled edge to edge" if aspect == "9:16" else "horizontal 16:9, the frame filled edge to edge"
    hand = BARE if hands == "bare" else HANDS
    where = sh.get("where") or "board"
    return _cap(
        f"{CAMERAS.get(sh['camera'], CAMERAS['top-down']).capitalize()}, {shape}. "
        f"{peak_of(sh['action'])} {sh['action'].rstrip('.')}.{_sentence(sh.get('physics'))} "
        f"In frame: {sh['subject'].rstrip('.')}, {WHERE.get(where, WHERE['board'])}. {hand}. "
        f"{_still(sh)}{_offscreen(sh)}"
        f"{look_for(where)}, every crumb and droplet sharp.",
        NEVER)


def edit_prompt(r: dict, sh: dict, hands: str = "") -> str:
    """One shot's picture, drawn FROM the shot before it.

    An edit model handed a full scene description and a photograph keeps the photograph: that is what it is for. So when
    there is a reference, the prompt says only what CHANGED - which is the difference between eleven shots of one dish
    and eleven photographs of the same board.
    """
    hand = BARE if hands == "bare" else HANDS
    gone = (sh.get("gone") or "").strip().rstrip(".")
    drop = f"Gone since the last shot, remove it: {gone}. " if gone and gone.lower() != "nothing yet" else ""
    return _cap(
        f"Keep the surface, the light and the style of the reference photograph, and change the scene to this: "
        f"{sh['subject'].rstrip('.')}. {drop}"
        f"{hand}, now: {sh['action'].rstrip('.')}.{_sentence(sh.get('physics'))} "
        f"Re-frame as {CAMERAS.get(sh['camera'], CAMERAS['top-down'])}. "
        f"This must look clearly different from the reference, not the same photograph again.",
        NEVER)


NEGATIVE = ("face, person, portrait, arm, elbow, third hand, extra fingers, deformed hands, text, letters, numbers, logo, label, "
            "packaging text, watermark, caption, cartoon, illustration, 3d render, plastic food, tofu, silken tofu, "
            "white rubbery cubes, cluttered counter, full mise en place, every ingredient laid out at once, untouched "
            "ingredients in rows, knife hovering above the food, knife not touching anything, "
            "black bars, letterbox, empty black space, blurry, low detail, duplicate ingredients, same frame repeated")


def motion_prompt(sh: dict, secs: float = 4.0, hands: str = "") -> str:
    """The image-to-video prompt: the picture is the first frame, one action happens, the sound is the shot's own ASMR."""
    hand = "matte-black latex gloves" if hands != "bare" else "bare hands"
    return (f"Animate this exact photograph as a {round(secs)}-second hyper-realistic macro cooking shot. Keep the frame, the {hand}, "
            f"the board and the lighting exactly as they are. One thing happens: "
            f"{sh['action'].rstrip('.')}.{_sentence(sh.get('physics'))} "
            f"{CAMERAS.get(sh['camera'], CAMERAS['top-down']).capitalize()}, the camera barely moves - a slow push or a small drift, nothing more. "
            "Real physics and real weight: food deforms, liquids fall and splash, steam rises, oil spits, crumbs scatter. No face, no person, no arm "
            f"above the wrist, no new objects, no cuts, no text. Sound: close ASMR of the action only - {sh['asmr'].rstrip('.')} - with quiet kitchen "
            "air under it. No music, no voice, no narration.")


def prompts_of(r: dict, aspect: str, secs: float, hands: str = "") -> list[dict]:
    return [{"n": sh["n"], "title": sh["title"], "stage": sh["stage"], "where": sh.get("where", "board"),
             "state": sh["state"], "gone": sh.get("gone", ""), "asmr": sh["asmr"], "camera": sh["camera"],
             "image": image_prompt(r, sh, aspect, hands),
             "edit": "" if sh.get("fresh") else edit_prompt(r, sh, hands),
             "motion": motion_prompt(sh, secs, hands)} for sh in r["shots"]]


def _meter(kind: str, model: str, units: float, pid: str = "", skill: str = "", ok: bool = True) -> None:
    """One line in the usage ledger. Wrapped because a run must never fail over its own bookkeeping."""
    try:
        from ..usage import record
        record(kind, model, units, run=pid, skill=skill, ok=ok)
    except Exception:  # noqa: BLE001
        pass


def outputs_of(p: dict) -> list[dict]:
    """One card per shot -- the clip once it exists, the still until then -- and the finished film at the end.

    Each entry carries its own file, so the run page never has to guess which field holds what.
    """
    shots = (p.get("recipe") or {}).get("shots") or []
    out = [{"key": f"shot{sh['n']}", "step": "motion" if sh.get("video") else "pictures",
            "title": f"{sh['n']}. {(sh.get('title') or 'Shot').strip()[:40]}",
            "kind": "video" if sh.get("video") else "image",
            "file": sh.get("video") or sh.get("picture"),
            "prompt": f"shot{sh['n']}"} for sh in shots]
    out.append({"key": "final", "step": "finish", "title": "The video", "kind": "video",
                "file": p.get("video"), "prompt": None})
    return out


# ---------- stages ----------
STAGES = ("recipe", "pictures", "motion", "finish")
LABELS = {"recipe": "Recipe and shot list", "pictures": "Shot pictures", "motion": "Motion and sound", "finish": "Final video"}


def _w_h(p: dict) -> tuple[int, int]:
    return base.SIZES.get(p.get("aspect") or "9:16", base.SIZES["9:16"])


def _each(p: dict) -> float:
    shots = ((p.get("recipe") or {}).get("shots") or [])
    return seconds_each(float(p.get("seconds") or 45), len(shots) or shots_for(float(p.get("seconds") or 45)))


def do_recipe(pid: str) -> None:
    p = store.load(pid)
    base.step(pid, "recipe", status="working")
    total = float(p.get("seconds") or 45)
    n = shots_for(total)
    r = recipe(base.sdict(p), p["subject"], n, base.logger(pid), seconds_each(total, n))
    base.put(pid, recipe=r, title=r["title"], prompts=prompts_of(r, p.get("aspect") or "9:16", seconds_each(total, len(r["shots"])), p.get("hands") or ""))
    found = house.review([house.card(sh["n"], sh["subject"], sh["action"], sh["camera"]) for sh in r["shots"]])
    note = f"{len(r['shots'])} shots, {len(r['ingredients'])} ingredients"
    if found:
        r["house"] = {"found": [list(f) for f in found], "note": house.note_of(found)}
        base.put(pid, recipe=r)
        note += ". " + r["house"]["note"]
    base.step(pid, "recipe", status="done", note=note)


ROLES = ("The attached photograph is the SCENE SO FAR: keep its board, its light and its style, and change only what the "
         "instruction below changes. It is not a layout to copy - re-frame it as asked. ")


def do_pictures(pid: str) -> None:
    """Each shot continues the one before it, until the cooking moves somewhere else and the board is left behind.

    Chaining every shot to the last one is what made the first version repeat itself: an edit model holding a photograph
    and a prompt that describes the whole scene again has been asked, in effect, to change nothing. So the chain now
    breaks whenever the shot moves to a new place - board to bowl, bowl to stove, stove to plate - and within a place
    the prompt says only what changed.
    """
    p = store.load(pid)
    s, (w, h) = base.sdict(p), _w_h(p)
    hands = p.get("hands") or ""
    base.step(pid, "pictures", status="working")
    prev: bytes | None = None
    fresh_count = 0
    for sh in p["recipe"]["shots"]:
        base.check(pid)
        if sh.get("picture") and store.file_path(pid, sh["picture"]):
            prev = base.read(pid, sh["picture"]) or prev
            continue
        chain = bool(prev) and not sh.get("fresh")
        seed = media.seed_of(pid, sh["n"], p.get("version", 1))
        aspect = p.get("aspect") or "9:16"

        def draw(as_edit: bool, salt: int = 0):
            prompt = edit_prompt(p["recipe"], sh, hands) if as_edit else image_prompt(p["recipe"], sh, aspect, hands)
            raw, meta = media.picture(prompt, [prev] if as_edit else [], w, h, seed + salt, f"{pid}-S{sh['n']}", s=s,
                                      negative=NEGATIVE, roles=ROLES if as_edit else "")
            return compose.fill(raw, w, h), meta       # bands cut and the frame filled before anything else sees it

        img, info = draw(chain)
        if chain and prev and compose.too_same(prev, img):
            # The edit model has handed back the photograph it was given. Asking it again the same way gets the same
            # answer, so this shot is drawn from its own words instead, with no reference at all.
            base.logger(pid)({"text": f"Shot {sh['n']} came back as the shot before it; drew it fresh from the words instead.",
                              "kind": "warn"})
            img, info = draw(False, salt=977)
            chain = False
        fresh_count += not chain
        seq = len([t for t in (sh.get("takes") or []) if t.get("kind") == "picture"]) + 1
        name = base.write(pid, f"S{sh['n']:02d}{'' if seq == 1 else chr(96 + seq)}.png", img)
        model = str(info.get("model") or "")

        def record(q, n=sh["n"], name=name, m=model, drawn=not chain):
            t = q["recipe"]["shots"][n - 1]
            takes.add(t, "picture", name, model=m, note="drawn fresh" if drawn else "continued from the shot before")
            t["picture_model"] = m
        store.update(pid, record)
        prev = img
        if sh["n"] == 1:
            base.put(pid, thumb=name)
    total = len(p["recipe"]["shots"])
    base.step(pid, "pictures", status="done",
              note=f"{total} shots drawn: {fresh_count} set up fresh, {total - fresh_count} continued from the shot before")


def _macro_clip(src, out, w: int, h: int, secs: float, kind: str, ffmpeg: str):
    """A macro camera move on the still: the free stand-in for a video model. zoompan does it in ffmpeg, so it stays fast."""
    import subprocess
    fps, n = 24, max(2, round(secs * 24))
    z = {"in": "min(zoom+0.0012,1.22)", "out": f"max(1.22-(on/{n})*0.22,1.0)"}.get(kind, "min(zoom+0.0012,1.22)")
    x = {"left": f"(iw-iw/zoom)*(1-on/{n})", "right": f"(iw-iw/zoom)*(on/{n})"}.get(kind, "iw/2-(iw/zoom/2)")
    vf = (f"scale={w * 2}:{h * 2}:force_original_aspect_ratio=increase,crop={w * 2}:{h * 2},"
          f"zoompan=z='{z}':d={n}:x='{x}':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={fps},format=yuv420p")
    subprocess.run([ffmpeg, "-v", "error", "-y", "-loop", "1", "-i", str(src), "-t", f"{secs:.3f}", "-vf", vf,
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", str(out)], check=True)
    return out


MOVES = ("in", "left", "out", "right")


def do_motion(pid: str) -> None:
    from .. import config
    from ..stickman import video
    p = store.load(pid)
    s = base.sdict(p)
    w, h = _w_h(p)
    secs = _each(p)
    base.step(pid, "motion", status="working")
    d = store.pdir(pid)
    want_video = (p.get("motion") or "video") == "video" and video.ready(s)
    if (p.get("motion") or "video") == "video" and not want_video:
        store.say(pid, "No video model is ready (add a fal.ai key with credit in Settings), so each shot gets a macro camera move and the kitchen "
                       "sound made in code. The video still gets made.", "warn")
    kinds: list[str] = []
    for sh in p["recipe"]["shots"]:
        base.check(pid)
        if sh.get("video") and store.file_path(pid, sh["video"]):
            continue
        img = base.read(pid, sh.get("picture"))
        if not img:
            raise RuntimeError(f"shot {sh['n']} has no picture yet")
        vseq = len([t for t in (sh.get("takes") or []) if t.get("kind") == "video"]) + 1
        out = d / f"S{sh['n']:02d}{'' if vseq == 1 else chr(96 + vseq)}.mp4"   # a redo must not land on the last take's file
        made = False
        if want_video:
            try:
                out.write_bytes(video.clip(motion_prompt(sh, secs), [img], None, round(secs), p.get("aspect") or "9:16", audio=True))
                made, _ = True, kinds.append("Seedance 2.0")
                _meter("video", "Seedance 2.0", round(secs), pid, p.get("skill") or "")
            except Exception as e:  # noqa: BLE001 - a finished video beats a stopped run
                want_video = False
                store.say(pid, f"Shot {sh['n']}: the AI video failed ({str(e)[:160]}). Carrying on with macro camera moves and the kitchen sound made "
                               "in code for the rest of this run.", "warn")
        if not made:
            still = d / f"{out.stem}_still.png"
            still.write_bytes(img)
            _macro_clip(still, out, w, h, secs, MOVES[(sh["n"] - 1) % len(MOVES)], config.ffmpeg())
            kinds.append("macro move")
            _meter("video", "macro move", round(secs), pid, p.get("skill") or "")
        def record_clip(q, n=sh["n"], name=out.name, how=kinds[-1] if kinds else ""):
            takes.add(q["recipe"]["shots"][n - 1], "video", name, model=how)
        store.update(pid, record_clip)
    base.step(pid, "motion", status="done", model=" + ".join(sorted(set(kinds))) or None,
              note="" if kinds == ["Seedance 2.0"] * len(kinds) else "Macro camera moves, with the kitchen sound synthesised per shot from its ASMR line.")


def do_finish(pid: str) -> None:
    from ..series import assemble
    from ..stickman import video
    from . import foley
    p = store.load(pid)
    w, h = _w_h(p)
    secs = _each(p)
    base.step(pid, "finish", status="working")
    d = store.pdir(pid)
    work = d / "work"
    work.mkdir(exist_ok=True)
    parts, total, made = [], 0.0, 0
    for sh in p["recipe"]["shots"]:
        clip = d / (sh.get("video") or "")
        if not clip.is_file():
            raise RuntimeError(f"shot {sh['n']} has no clip yet")
        fit = assemble.fit_shot(clip, work / f"S{sh['n']:02d}_fit.mp4", secs, w, h)
        sfx = None
        if not video.has_audio(clip):                     # Seedance brings its own sound; a macro move does not
            sfx = work / f"S{sh['n']:02d}.wav"
            sfx.write_bytes(foley.wav(sh.get("asmr") or "", secs, seed=sh["n"] * 17))
            made += 1
        aud = assemble.shot_audio(work / f"S{sh['n']:02d}_a.wav", secs, None, sfx, line_at=0.0)
        parts.append({"video": fit, "audio": aud, "seconds": secs})
        total += secs
    joined = assemble.part(parts, work, work / "joined.mp4", w, h, None, [])
    import shutil
    shutil.copyfile(joined, d / "final.mp4")
    base.put(pid, video="final.mp4", finalSeconds=round(total, 1))
    base.step(pid, "finish", status="done",
              note=f"No music, as the look asks: {made} shot(s) carry kitchen sound made in code" if made else "No music: the shots carry their own sound")


RUN = {"recipe": do_recipe, "pictures": do_pictures, "motion": do_motion, "finish": do_finish}


def last_stage(p: dict) -> str:
    return "recipe" if p.get("media") == "prompts" else "finish"


def reset(p: dict, step: str, n: int | None = None) -> None:
    """Clear what `step` (and every later step) made. With n: only that shot."""
    order = STAGES[STAGES.index(step):]
    for st in order:
        p.setdefault("steps", {}).pop(st, None)
    if "recipe" in order:
        p.pop("recipe", None)
        p.pop("prompts", None)
        return
    for sh in (p.get("recipe") or {}).get("shots") or []:
        if n and sh["n"] != n:
            continue
        if "pictures" in order:
            takes.clear_pointer(sh, "picture")     # the pointer goes so it is drawn again; the old take stays
        if "motion" in order:
            takes.clear_pointer(sh, "video")
    if "finish" in order:
        p.pop("video", None)
