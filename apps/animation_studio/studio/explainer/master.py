"""The master prompt: the whole video written as ONE timed, multi-shot prompt for multi-shot video models (Seedance, Kling,
Veo, Picsart Cartoon Director, Lovart...), in the shape the best published prompts use:

    style and quality paragraph  ->  CHARACTERS (full description once)  ->  SETTING AND PROPS
    ->  timed beats "0–3 SEC — TITLE" (what happens, how each character reacts, dialogue as  Name: "line")
    ->  VISUAL DIRECTION (look, light, camera, the moments that must read)  ->  AUDIO  ->  STRICT RULES

Videos longer than one generation (about 15 seconds on Seedance) are split into PARTS at shot boundaries; every part after
the first opens with "Continue seamlessly from the previous part" and repeats the characters, so the tool keeps them identical.
Built from the approved plan, never invented."""
from __future__ import annotations

from . import cinema, engines

PART_SECONDS = 15.0
QUALITY = ("feature-film quality, expressive stylized characters, sophisticated lighting, detailed textures, smooth animation, "
           "dynamic cinematic camera movement and perfectly timed physical comedy")


def _fmt(t: float) -> str:
    return f"{round(t, 1):g}"


def _used(pl: dict, shots: list[dict]) -> tuple[list[dict], list[dict]]:
    cs = [c for c in pl["characters"] if any(c["id"] in s["characters"] or s.get("speaker") == c["id"] for s in shots)] or pl["characters"][:1]
    xs = [x for x in pl["props"] if any(x["id"] in s["props"] for s in shots)]
    return cs, xs


def _beat(s: dict, a: float, b: float, chars: dict) -> str:
    title = (s.get("scene_title") or s["shot_type"].replace("_", " ")).upper()
    lines = [f"{_fmt(a)}–{_fmt(b)} SEC — {title}"]
    frame = "; ".join(cinema.phrases(s))
    if frame:
        lines.append("Shot: " + frame + ".")
    if s.get("cam_note"):
        lines.append(f"Camera: {s['cam_note'].rstrip('.')}.")
    lines.append(s["action"].rstrip(".") + ".")
    if s.get("performance"):
        lines.append(f"Reaction: {s['performance'].rstrip('.')}.")
    if s.get("lighting"):
        lines.append(f"Light: {s['lighting'].rstrip('.')}.")
    if s.get("narration"):
        who = chars.get(s.get("speaker") or "")
        emo = f" ({s['emotion']})" if s.get("emotion") else ""
        lines.append(f"{who['name']}{emo}: “{s['narration']}”" if who else f"Narrator (voice-over): “{s['narration']}”")
    if s.get("end_state"):
        lines.append(f"End on: {s['end_state'].rstrip('.')}.")
    return "\n".join(x for x in lines if x)


def _part(p: dict, shots: list[dict], start: float, n: int, of: int) -> str:
    pl = p["plan"]
    look = engines.look(p)
    chars = {c["id"]: c for c in pl["characters"]}
    used, props = _used(pl, shots)
    total = sum(float(s["seconds"]) for s in shots)
    aspect = p.get("aspect") or pl.get("aspect") or "16:9"
    out: list[str] = []
    if of > 1:
        out.append(f"PART {n} OF {of} ({_fmt(total)} seconds)")
    if n > 1:
        out.append("Continue seamlessly from the previous part. Maintain the exact same characters, clothing, facial features, "
                   "lighting, environment and animation style.")
    out.append(f"Create a cinematic multi-shot animated short film, {_fmt(total)} seconds, {aspect}. {pl.get('logline') or pl['title']} "
               f"Style: {look.rstrip('.')}. Quality: {QUALITY}." + (" Open with a strong visual hook in the first three seconds." if n == 1 else ""))
    cast = ["CHARACTERS"] + [f"{c['name']}: {c['look'].rstrip('.')}." for c in used]
    out.append("\n".join(cast))
    sp = ["SETTING AND PROPS", f"Setting: {pl['world']['look'].rstrip('.')}."] + [f"{x['name']}: {x['look'].rstrip('.')}." for x in props]
    out.append("\n".join(sp))
    t = start
    for s in shots:
        a, b = t, t + float(s["seconds"])
        out.append(_beat(s, a - start if of > 1 else a, b - start if of > 1 else b, chars))
        t = b
    vd = ["VISUAL DIRECTION", f"{look[0].upper() + look[1:]}."]
    for k in ("lighting_note", "camera_language"):
        if pl.get(k):
            vd.append(pl[k].rstrip(".") + ".")
    if pl.get("palette"):
        vd.append("Palette: " + ", ".join(f"{c['name']} {c['hex']}" for c in pl["palette"][:6]) + ".")
    vd.append("Maintain consistent characters, outfits, locations and props throughout.")
    keys = [s["end_state"].rstrip(".") for s in shots if s.get("end_state")][:3]
    if keys:
        vd.append("These moments must be visually understandable: " + "; ".join(keys) + ".")
    out.append("\n".join(vd))
    narrated = any(s.get("narration") and not chars.get(s.get("speaker") or "") for s in shots)
    spoken = sum(1 for s in shots if s.get("narration") and chars.get(s.get("speaker") or ""))
    au = ["AUDIO", f"Music: {(pl.get('music') or 'light, playful, instrumental').rstrip('.')}."]
    if pl.get("sound_design"):
        au.append(pl["sound_design"].rstrip(".") + ".")
    au += [f"{s['id']}: {s['audio'].rstrip('.')}." for s in shots if s.get("audio")][:10]
    au.append("Narration as written above." if narrated else ("Minimal dialogue and no narration." if spoken else "No dialogue and no narration."))
    out.append("\n".join(au))
    rules = ["STRICT RULES",
             "Keep every face, outfit, colour, vehicle and prop identical in every shot.",
             "Keep each character's position, screen direction and the set consistent from shot to shot.",
             "Every action follows logically from the one before; each shot has one clear action and one camera move, and fits its time.",
             f"Spoken dialogue only where written{f' ({spoken} line' + ('s' if spoken != 1 else '') + ')' if spoken else ''}; clear and accurately lip-synced. No other speech.",
             "Only these characters appear: " + ", ".join(c["name"] for c in used) + ". No extra people or animals.",
             "No subtitles, captions, logos, watermarks or text in the picture."]
    out.append("\n".join(rules))
    return "\n\n".join(out)


def parts(p: dict, scene: int | None = None, limit: float = PART_SECONDS) -> list[str]:
    """The prompt in parts of at most `limit` seconds (whole shots only)."""
    pl = p["plan"]
    shots = [s for s in pl["shots"] if scene is None or int(s.get("scene") or 1) == scene]
    if not shots:
        return []
    groups: list[list[dict]] = [[]]
    for s in shots:
        if groups[-1] and sum(float(x["seconds"]) for x in groups[-1]) + float(s["seconds"]) > limit:
            groups.append([])
        groups[-1].append(s)
    out, t = [], 0.0
    for i, g in enumerate(groups):
        out.append(_part(p, g, t, i + 1, len(groups)))
        t += sum(float(x["seconds"]) for x in g)
    return out


def build(p: dict, scene: int | None = None, limit: float = PART_SECONDS) -> str:
    return "\n\n────────\n\n".join(parts(p, scene, limit))
