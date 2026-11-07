"""The shot router: for each shot, the best way to make it with what is actually available right now.

Rules (in order): scientific cutaways, exact object contact and arrows → Blender (precise); people, reactions, macro
looks → AI video (natural); anything else a model can't make right now → a still picture with a camera move, so a
video always comes out. A shot can be forced by hand (shot["force"]).
"""
from __future__ import annotations

PRECISE = ("scientific_cutaway",)
HUMAN = ("presenter", "reaction", "establishing", "result")


def route(shot: dict, caps: dict) -> tuple[str, str]:
    """(engine, why). caps: {"ai_video": bool, "blender": bool}."""
    forced = shot.get("force")
    if forced in ("ai_video", "blender", "still", "lipsync") and (forced == "still" or caps.get(forced)):
        return forced, "chosen by you"
    st = shot.get("shot_type")
    wants_precise = st in PRECISE or (shot.get("physics") and not shot.get("characters"))
    if wants_precise and caps.get("blender"):
        return "blender", "exact objects, cutaway and arrows need a 3D scene"
    if shot.get("speaker") and caps.get("lipsync") and shot.get("characters"):
        return "lipsync", "this character speaks the line, so a lip-sync model makes the mouth match"
    if st in HUMAN or shot.get("characters"):
        if caps.get("ai_video"):
            return "ai_video", "a person on screen looks most natural from an AI video model"
    if caps.get("ai_video"):
        return "ai_video", "an AI video model animates the picture" + (" (3D not set up for the exact part)" if wants_precise else "")
    if caps.get("blender"):
        return "blender", "no AI video model is ready; the 3D scene can still show it"
    return "still", "no video model is ready: the picture with a camera move (add fal.ai credit or a GPU to animate it)"


def route_all(shots: list[dict], caps: dict) -> list[dict]:
    for s in shots:
        s["engine"], s["engine_why"] = route(s, caps)
    return shots
