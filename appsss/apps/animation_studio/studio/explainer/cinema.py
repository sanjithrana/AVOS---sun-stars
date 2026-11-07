"""Film language for the Autopilot: camera angles, composition, lens and movement as plain prompt phrases, the 14 fields a
complete shot needs, and a check for what a shot is still missing. Every phrase here is something an image or video model
understands as ordinary words; nothing is JSON or code."""
from __future__ import annotations

ANGLES: dict[str, dict[str, str]] = {
    "eye_level": {"label": "Eye-level", "feel": "neutral, intimate, human", "phrase": "eye-level camera, natural and observational", "best": "dialogue, reactions, restrained drama"},
    "low_angle": {"label": "Low angle", "feel": "power, pressure, scale", "phrase": "low-angle shot, camera below the subject looking upward, adds authority and scale", "best": "heroes, threats, architecture over character"},
    "high_angle": {"label": "High angle", "feel": "vulnerable, small", "phrase": "high-angle shot looking down at the subject, making it feel small and exposed", "best": "defeat, a lost character, showing layout"},
    "ground_level": {"label": "Ground level", "feel": "extreme perspective", "phrase": "ground-level camera close to the floor, dramatic foreground and towering subject", "best": "feet, chases, tiny characters in a big world"},
    "shoulder_height": {"label": "Shoulder height", "feel": "common for dialogue", "phrase": "camera at shoulder height, relaxed conversational view", "best": "talking, walking beside a character"},
    "overhead": {"label": "Overhead", "feel": "layout and movement", "phrase": "overhead top-down view showing the whole layout and movement paths", "best": "tables, maps, choreography"},
    "profile": {"label": "Profile / side", "feel": "direction and shape", "phrase": "profile side view, clear silhouette and direction of travel", "best": "running, driving, pointing"},
    "three_quarter": {"label": "Three-quarter", "feel": "depth and dimension", "phrase": "three-quarter view, shows depth and volume of face and body", "best": "portraits, character introductions"},
}
COMPOSITIONS: dict[str, dict[str, str]] = {
    "rule_of_thirds": {"phrase": "subject placed on the left third looking toward open space on the right, balanced and open"},
    "center": {"phrase": "subject centred in the frame, symmetrical, emphasising importance"},
    "negative_space": {"phrase": "small subject with vast empty space around it, isolation and scale"},
    "symmetry": {"phrase": "perfectly symmetrical frame around a central axis, ordered and formal"},
    "leading_lines": {"phrase": "lines in the environment lead the eye to the subject at the end of converging lines"},
    "frame_within_frame": {"phrase": "subject seen through a doorway, window or arch that frames them, adds depth"},
    "layers": {"phrase": "clear foreground, midground and background layers, strong depth"},
    "asymmetrical_balance": {"phrase": "a large element on one side balanced by a small bright subject on the other"},
    "blocking": {"phrase": "characters arranged in a triangle, positions showing their relationship and who has power"},
    "movement_space": {"phrase": "open space left in front of the moving subject, in the direction of travel"},
}
LENSES = {14: "ultra-wide, exaggerated depth", 24: "wide, strong perspective, feels bigger and immersive", 35: "natural and versatile, slightly wide", 50: "close to human vision, balanced",
          85: "portrait, tighter framing, compressed and intimate", 135: "telephoto, compressed depth, isolating"}
MOVES = {"static": "locked-off camera, no movement", "push_in": "slow push-in, increases pressure and focus", "pull_out": "slow pull-back, reveals context",
         "pan_right": "smooth pan right, follows the action", "pan_left": "smooth pan left, follows the action", "orbit": "slow orbit around the subject, reveals dimension",
         "tilt_up": "tilt up, reveals scale", "tilt_down": "tilt down, drops to the detail"}
SIZES = {"wide": "wide shot, whole scene and characters small but readable", "medium": "medium shot, waist up, action and relationship",
         "close_up": "close-up on the face, emotion and tension", "macro_close_up": "extreme close-up, tight detail and texture",
         "over_shoulder": "over-the-shoulder shot, the other character's perspective", "top_down": "top-down shot", "cutaway": "insert cutaway of a key detail"}
BY_TYPE = {"presenter": ("eye_level", "center"), "reaction": ("eye_level", "rule_of_thirds"), "establishing": ("high_angle", "layers"),
           "demonstration": ("shoulder_height", "rule_of_thirds"), "macro_close_up": ("ground_level", "negative_space"),
           "scientific_cutaway": ("three_quarter", "symmetry"), "result": ("low_angle", "center")}

# The 14 fields of one complete shot, and where each one lives on the shot dict.
FIELDS = [("scene", "setting (place, environment, time of day)"), ("characters", "who is in the shot"), ("objective", "what the character is trying to do"),
          ("action", "precise action and reaction"), ("shot_size", "wide / medium / close-up"), ("angle", "camera height and angle"), ("lens", "focal length"),
          ("move", "one camera move with distance and timing"), ("composition", "where things sit in the frame"), ("lighting", "source, direction, hardness"),
          ("performance", "eyes, gestures, reaction timing"), ("duration", "seconds"), ("end_state", "the exact final pose"), ("continuity", "what must stay the same")]


def guide() -> str:
    """The film-language cheat sheet put in front of the script writer."""
    return ("Camera height/angle words (pick one per shot): " + "; ".join(f"\"{k}\" = {v['feel']}" for k, v in ANGLES.items()) + ". "
            "Composition words (pick one per shot): " + ", ".join(f"\"{k}\"" for k in COMPOSITIONS) + ". "
            "Lens: 24mm wide and immersive, 35mm natural, 50mm balanced, 85mm intimate, macro for detail. "
            "Choose each angle for what it should make the viewer feel, not because it looks cool: dramatic power = low angle, vulnerability = high angle, intimacy = eye level. ")


def phrases(shot: dict) -> list[str]:
    """Plain prompt phrases for a shot's angle, size, lens and composition (what the picture model is told)."""
    cam = shot.get("camera") or {}
    out = []
    if shot.get("shot_size") or cam.get("type") in SIZES:
        out.append(SIZES.get(shot.get("shot_size") or cam.get("type"), ""))
    if shot.get("angle") in ANGLES:
        out.append(ANGLES[shot["angle"]]["phrase"])
    lens = int(cam.get("lens_mm") or 0)
    if lens:
        near = min(LENSES, key=lambda k: abs(k - lens))
        out.append(f"{lens}mm lens, {LENSES[near]}")
    if shot.get("composition") in COMPOSITIONS:
        out.append(COMPOSITIONS[shot["composition"]]["phrase"])
    return [x for x in out if x]


def missing(shot: dict) -> list[str]:
    """Which of the 14 fields this shot still leaves for the model to guess (plain names)."""
    cam = shot.get("camera") or {}
    have = {"scene": bool(shot.get("scene_title") or shot.get("scene")), "characters": bool(shot.get("characters") or shot.get("props")), "objective": bool(shot.get("objective")),
            "action": len(str(shot.get("action") or "")) > 25, "shot_size": bool(cam.get("type")), "angle": shot.get("angle") in ANGLES, "lens": bool(cam.get("lens_mm")),
            "move": bool(cam.get("movement")) and (shot.get("cam_note") or cam.get("movement") == "static"), "composition": shot.get("composition") in COMPOSITIONS,
            "lighting": bool(shot.get("lighting")), "performance": bool(shot.get("performance") or shot.get("emotion")), "duration": bool(shot.get("seconds")),
            "end_state": bool(shot.get("end_state")), "continuity": bool(shot.get("continuity"))}
    return [k for k, ok in have.items() if not ok]
