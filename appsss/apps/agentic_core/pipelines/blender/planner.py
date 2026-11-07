"""
Shot description -> Blender scene JSON (the contract in
blender_service/avos_scene.py).

The LLM (the project's provider - Groq / Ollama / OpenAI) picks from a
catalog of what the render service actually has, so it can't ask for
assets that don't exist; its answer is then validated and clamped. With
no LLM (or an unusable answer) a keyword planner builds the scene, so a
render never fails because of planning.
"""

import json
import logging
import random
import re
from typing import Any

from agentic_core.models.llm.base import LLMProvider

logger = logging.getLogger(__name__)

DEFAULT_CATALOG = {
    "environments": ["grid_studio", "desert", "space", "night_city_floor"],
    "builtin_characters": ["mannequin"],
    "variants": ["man", "woman", "giant", "kid", "robot", "astronaut"],
    "builtin_actions": ["idle", "walk", "run", "punch", "push", "jump", "wave", "fall", "celebrate",
                        "dance", "point", "shocked", "fight_idle"],
    "builtin_props": ["box", "sphere", "ball", "gold_bar", "balloon", "wall", "pillar", "rock", "tree",
                      "bullet", "coin", "car_block", "planet", "moon", "sun_orb"],
    "library_characters": [],
    "library_animations": [],
    "library_props": [],
}
SHOTS = ("wide", "medium", "close")
MOVES = ("static", "push_in", "pull_out", "orbit", "pan", "low_angle", "track")
MOTIONS = ("none", "spin", "float", "fall", "bounce", "shake", "fly")
MATERIALS = ("plastic", "matte", "gold", "metal", "glass", "glow", "rubber")

SYSTEM_PROMPT = (
    "You are the 3D scene director for short vertical videos rendered in Blender. "
    "Turn one shot description into a simple, readable 3D scene using ONLY names from the catalog. "
    "Respond with ONLY a JSON object, no prose."
)

ACTION_WORDS = [
    (r"punch|fight|\bhits?\b|boxing|boxer|attack|smash|kick|\bbeat|brawl", "punch"),
    (r"push|shove", "push"),
    (r"run|chase|sprint|race|flee|rush", "run"),
    (r"walk|stroll|step|approach|march", "walk"),
    (r"jump|leap|hop|bounce", "jump"),
    (r"fall|collapse|knock|faint|drop|die", "fall"),
    (r"dance|party", "dance"),
    (r"wave|hello|greet", "wave"),
    (r"celebrat|win|cheer|victory|happy", "celebrate"),
    (r"point|show|look at|discover", "point"),
    (r"shock|scared|surpris|afraid|panic|fear", "shocked"),
]
PROP_WORDS = [
    (r"gold", "gold_bar"), (r"bullet|\bguns?\b|gunshot|fired", "bullet"), (r"balloon", "balloon"), (r"coin|money", "coin"),
    (r"rock|stone|boulder", "rock"), (r"tree|forest", "tree"), (r"car|vehicle", "car_block"),
    (r"wall|barrier", "wall"), (r"ball", "ball"), (r"planet|earth", "planet"), (r"moon", "moon"),
    (r"\bsun\b|\bstars?\b", "sun_orb"), (r"pillar|column", "pillar"), (r"\bbox(es)?\b|crate|cube", "box"),
]


def _norm(name: Any) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", str(name or "").lower()).strip("_")


def _num(value: Any, default: float, lo: float, hi: float) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, v))


def keyword_plan(description: str, catalog: dict, rng: random.Random) -> dict:
    text = description.lower()
    env = "grid_studio"
    if re.search(r"desert|sand|dune|egypt|sahara|camel", text):
        env = "desert"
    elif re.search(r"space|moon|planet|astronaut|orbit|galaxy|mars", text):
        env = "space"
    elif re.search(r"night|city|neon|street", text):
        env = "night_city_floor"
    if env not in catalog["environments"]:
        env = catalog["environments"][0]

    action = next((a for pattern, a in ACTION_WORDS if re.search(pattern, text)), "idle")
    hero_variant = "man"
    for pattern, variant in ((r"woman|girl|lady|she\b", "woman"), (r"kid|child|boy|baby", "kid"),
                             (r"robot|android|machine", "robot"), (r"astronaut", "astronaut")):
        if re.search(pattern, text):
            hero_variant = variant
            break
    actors = [{"id": "a1", "asset": "mannequin", "variant": hero_variant, "action": action,
               "position": [0.0, 0.0], "facing": 0}]
    opponent = re.search(r"gorilla|giant|monster|huge|bear|beast|titan|vs\b|versus|against|another", text)
    crowd = re.search(r"(\d+)\s*(men|people|guys|soldiers|kids|humans)", text)
    if opponent:
        actors[0].update(position=[-0.9, 0.0], facing=70)
        big = re.search(r"gorilla|giant|monster|huge|bear|beast|titan", text)
        actors.append({"id": "a2", "asset": "mannequin", "variant": "giant" if big else "man",
                       "action": "fight_idle" if action in ("punch", "push") else "idle",
                       "position": [1.0, 0.3], "facing": -70})
    elif crowd:
        n = min(5, max(2, int(crowd.group(1))))
        actors = []
        for i in range(n):
            x = (i - (n - 1) / 2) * 0.9
            actors.append({"id": f"a{i + 1}", "asset": "mannequin", "variant": "man", "action": action,
                           "position": [round(x, 2), round(rng.uniform(-0.3, 0.6), 2)], "facing": 0})
    # Your own (Mixamo) characters named after a variant - man.fbx,
    # woman.fbx, giant.fbx ... - replace the built-in mannequin.
    library = set(catalog.get("library_characters", []))
    for actor in actors:
        if actor["variant"] in library:
            actor["asset"] = actor["variant"]
    if action in ("walk", "run"):
        actors[0]["position"] = [-1.6, 0.0]
        actors[0]["move_to"] = [1.6, 0.0]

    props = []
    for pattern, prop in PROP_WORDS:
        if re.search(pattern, text) and prop in catalog["builtin_props"] + catalog.get("library_props", []):
            motion = "fall" if re.search(r"fall|drop", text) else ("float" if prop in ("balloon", "planet", "moon") else "none")
            props.append({"type": prop, "position": [0.0, -1.0, 0.0] if prop not in ("planet", "moon", "sun_orb") else [2.0, 6.0, 4.0],
                          "scale": 1.0, "motion": motion, "material": "gold" if prop in ("gold_bar", "coin") else "plastic"})
            if len(props) >= 2:
                break
    camera = {"shot": "wide", "move": "push_in", "target": "a1"}
    if action == "punch":
        camera = {"shot": "medium" if len(actors) <= 2 else "wide", "move": "orbit", "target": "a1"}
    elif action in ("walk", "run"):
        camera = {"shot": "wide", "move": "track", "target": "a1"}
    elif action == "jump":
        camera = {"shot": "wide", "move": "low_angle", "target": "a1"}
    elif re.search(r"close|face|detail", text):
        camera = {"shot": "close", "move": "push_in", "target": "a1"}
    return {"environment": env, "actors": actors, "props": props, "camera": camera}


def _llm_prompt(description: str, catalog: dict, duration: float, environment_hint: str | None) -> str:
    actions = catalog["builtin_actions"] + catalog.get("library_animations", [])
    characters = ["mannequin"] + catalog.get("library_characters", [])
    return (
        "TASK: blender_scene\n"
        f"SHOT_DESCRIPTION: {description}\n"
        f"DURATION_SECONDS: {duration:.1f}\n"
        "CATALOG:\n"
        f"  environments: {catalog['environments']}\n"
        f"  characters (asset): {characters}  (mannequin takes a variant: {catalog['variants']})\n"
        f"  actions: {actions}\n"
        f"  props: {catalog['builtin_props'] + catalog.get('library_props', [])}\n"
        f"  prop motions: {list(MOTIONS)}; prop materials: {list(MATERIALS)}\n"
        f"  camera shots: {list(SHOTS)}; camera moves: {list(MOVES)}\n"
        + (f"PREFERRED_ENVIRONMENT: {environment_hint}\n" if environment_hint else "")
        + "RULES: 1-4 actors (a big crowd = 4-5 actors). Coordinates in metres: x left/right in [-3, 3], "
        "y depth in [-1, 3] (camera is at negative y looking toward +y). facing is degrees: 0 = faces the "
        "camera, 90 = faces screen-right, -90 = faces screen-left; two characters facing each other "
        "use about 70 and -70. Use move_to [x, y] for walking/running. Keep it simple and readable.\n"
        "OUTPUT JSON SHAPE: {\"environment\": str, \"actors\": [{\"id\": \"a1\", \"asset\": str, "
        "\"variant\": str, \"action\": str, \"position\": [x, y], \"facing\": number, \"scale\": number, "
        "\"color\": \"#rrggbb\" or null, \"move_to\": [x, y] or null}], \"props\": [{\"type\": str, "
        "\"position\": [x, y, z], \"scale\": number, \"color\": \"#rrggbb\" or null, \"material\": str, "
        "\"motion\": str}], \"camera\": {\"shot\": str, \"move\": str, \"target\": \"a1\"}}"
    )


def _extract_json(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[4:] if text.startswith("json") else text
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def sanitize(plan: dict, catalog: dict) -> dict:
    """Clamp an LLM plan into something the renderer accepts."""
    from_alias = {
        "walking": "walk", "running": "run", "boxing": "punch", "fighting": "punch", "kick": "punch",
        "jumping": "jump", "waving": "wave", "falling": "fall", "dancing": "dance", "standing": "idle",
        "pointing": "point", "scared": "shocked", "surprised": "shocked", "cheering": "celebrate",
        "guard": "fight_idle", "stance": "fight_idle",
    }
    actions = set(catalog["builtin_actions"]) | set(catalog.get("library_animations", []))
    characters = {"mannequin"} | set(catalog.get("library_characters", []))
    props_ok = set(catalog["builtin_props"]) | set(catalog.get("library_props", []))
    env = _norm(plan.get("environment"))
    out: dict[str, Any] = {"environment": env if env in catalog["environments"] else catalog["environments"][0]}

    actors = []
    for i, a in enumerate((plan.get("actors") or [])[:5]):
        if not isinstance(a, dict):
            continue
        asset = _norm(a.get("asset")) or "mannequin"
        action = _norm(a.get("action")) or "idle"
        action = action if action in actions else from_alias.get(action, "idle")
        pos = a.get("position") or [0, 0]
        item = {
            "id": str(a.get("id") or f"a{i + 1}"),
            "asset": asset if asset in characters else "mannequin",
            "variant": _norm(a.get("variant")) if _norm(a.get("variant")) in catalog["variants"] else "man",
            "action": action,
            "position": [_num(pos[0] if len(pos) > 0 else 0, 0, -3, 3), _num(pos[1] if len(pos) > 1 else 0, 0, -1, 3)],
            "facing": _num(a.get("facing"), 0, -180, 180),
            "scale": _num(a.get("scale"), 1.0, 0.3, 3.0),
        }
        if isinstance(a.get("color"), str) and re.fullmatch(r"#[0-9a-fA-F]{6}", a["color"]):
            item["color"] = a["color"]
        move = a.get("move_to")
        if isinstance(move, (list, tuple)) and len(move) >= 2:
            item["move_to"] = [_num(move[0], 0, -4, 4), _num(move[1], 0, -1, 4)]
        actors.append(item)
    out["actors"] = actors

    props = []
    for p in (plan.get("props") or [])[:8]:
        if not isinstance(p, dict) or _norm(p.get("type")) not in props_ok:
            continue
        pos = list(p.get("position") or [0, 0, 0]) + [0, 0, 0]
        item = {
            "type": _norm(p.get("type")),
            "position": [_num(pos[0], 0, -6, 6), _num(pos[1], 0, -2, 20), _num(pos[2], 0, 0, 12)],
            "scale": _num(p.get("scale"), 1.0, 0.1, 6.0),
            "material": _norm(p.get("material")) if _norm(p.get("material")) in MATERIALS else "plastic",
            "motion": _norm(p.get("motion")) if _norm(p.get("motion")) in MOTIONS else "none",
        }
        if isinstance(p.get("color"), str) and re.fullmatch(r"#[0-9a-fA-F]{6}", p["color"]):
            item["color"] = p["color"]
        props.append(item)
    out["props"] = props

    cam = plan.get("camera") if isinstance(plan.get("camera"), dict) else {}
    shot, move = _norm(cam.get("shot")), _norm(cam.get("move"))
    out["camera"] = {
        "shot": shot if shot in SHOTS else "wide",
        "move": move if move in MOVES else "push_in",
        "target": str(cam.get("target") or (actors[0]["id"] if actors else "a1")),
    }
    return out


async def plan_scene(
    description: str,
    *,
    catalog: dict | None = None,
    duration: float = 4.0,
    llm: LLMProvider | None = None,
    seed: int | None = None,
    environment_hint: str | None = None,
) -> dict:
    catalog = {**DEFAULT_CATALOG, **(catalog or {})}
    rng = random.Random(seed or 0)
    plan: dict | None = None
    source = "keywords"
    if llm is not None and getattr(llm, "name", "") != "mock":
        try:
            raw = await llm.complete(_llm_prompt(description, catalog, duration, environment_hint),
                                     system=SYSTEM_PROMPT)
            parsed = _extract_json(raw)
            if parsed:
                plan = sanitize(parsed, catalog)
                source = getattr(llm, "name", "llm")
                if not plan["actors"] and not plan["props"]:
                    plan = None
        except Exception as exc:  # noqa: BLE001 - planning must never fail a render
            logger.warning("Scene planning with %s failed (%s); using the keyword planner.",
                           getattr(llm, "name", "llm"), exc)
    if plan is None:
        plan = sanitize(keyword_plan(description, catalog, rng), catalog)
        source = "keywords"
        if environment_hint and environment_hint in catalog["environments"]:
            if plan["environment"] == "grid_studio":
                plan["environment"] = environment_hint
    plan["duration"] = round(max(1.0, float(duration)), 2)
    plan["seed"] = int(seed or 0) % 2_147_483_647
    plan["planner"] = source
    return plan
