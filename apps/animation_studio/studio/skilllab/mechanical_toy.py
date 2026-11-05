"""Mechanical Toy skill (after SJinn's "mechanical-toy"): any subject becomes a hyper-realistic premium mechanical transformation
toy. One locked design drives three prompts that share every word of the look:

  1. COMPACT DEVICE      a sealed one-hand pod, held in one hand over a clean white tabletop, revealing nothing of what it becomes
  2. FULLY TRANSFORMED   the same object unfolded (1.5-2x the size), no hands, built from the pod via reference image 1
  3. TRANSFORMATION      one continuous portrait clip: hand holds pod, thumb clicks the button, pod set down, hand withdraws,
                         seams separate, parts deploy in order, final locking clunk, camera drifts closer; ASMR, no music

The design lock (form, finish, palette, what must stay hidden, anatomy, deployment order) is written by the AI crew when there is
one, otherwise picked deterministically from presets so the skill also works with the built-in crew."""
from __future__ import annotations

import hashlib
import re
from typing import Any, Callable

ID = "mechanical-toy"
INFO = {
    "id": ID, "name": "Mechanical Toy", "group": "Product and toys", "kind": "transformation",
    "made_for": "Turn any creature, animal, vehicle, robot, mythical being or object into a premium mechanical transformation toy",
    "about": "A locked design, then three production prompts: the sealed handheld pod, the fully transformed collectible, and one continuous "
             "portrait transformation clip with mechanical ASMR. With media on, it draws both pictures and makes the clip from them.",
    "input": "Name a subject, e.g. a seven-headed hydra, a snow leopard, a vintage locomotive, a samurai crab",
    "outputs": ["Compact device image", "Fully transformed image", "Transformation video"],
    "aspect": "9:16", "seconds": [8, 10, 12, 15], "default_seconds": 15, "native_audio": True,
    "examples": ["a seven-headed hydra", "a snow leopard", "a vintage steam locomotive", "a phoenix", "a hermit crab", "a Viking longship"],
    "credit": "Workflow modelled on SJinn's mechanical-toy skill.",
}

CAMERA = ("handheld downward-looking POV captured like iPhone 15 Pro Max footage, portrait orientation, shallow depth of field, natural ambient lighting, "
          "subtle lens imperfections, realistic reflections and shadows, tactile metallic materials")
SET = "a clean white tabletop with no background clutter"
NEVER = "No text, logos, labels, watermarks, magical effects, glow, or clutter."
NEVER_T = ("Hyper-realistic cinematic realism, photorealistic metallic detailing, no text, logos, labels, watermarks, background clutter, magical effects, "
           "energy effects, anime glow, smoke, or explosions.")

FORMS = ["flattened-sphere pod", "rounded capsule", "thick puck-shaped disc", "faceted egg-shaped pod", "rounded cube with chamfered edges", "smooth river-stone pebble"]
FINISHES = ["satin-blackened titanium with micro-brushed surfaces", "gunmetal anodized aluminium with fine bead-blasted texture",
            "brushed champagne steel with polished bevels", "graphite ceramic composite with satin metal inlays", "dark bronze with hand-rubbed patina",
            "pearl-white enamel over brushed silver alloy"]
PALETTES = ["deep marsh green, oxidized bronze, and muted bone", "midnight blue, warm brass, and soft ivory", "oxblood red, blackened steel, and pale gold",
            "slate grey, burnt copper, and chalk white", "forest green, aged gold, and charcoal", "arctic white, cobalt blue, and gunmetal"]

DESIGN = """You are a premium collectible-toy designer and a mechanical engineer. Lock ONE design for a hyper-realistic mechanical transformation toy of the subject.
The compact state is a sealed, one-hand-held geometric pod that reveals NOTHING of the subject. The transformed state is the same object unfolded to roughly 1.5 to 2 times its size, every part believably folding, telescoping, rotating, nesting or interlocking back into the pod (volume-conserving). No magic, no glow, no energy effects.
Answer with ONE JSON object:
{"subject":"the subject as a short noun phrase","form":"the pod shape, e.g. flattened-sphere pod","finish":"one material finish, e.g. satin-blackened titanium with micro-brushed surfaces",
 "palette":"three colour names joined like 'deep marsh green, oxidized bronze, and muted bone'","shell":"the pod's outer shell details (seam lines, panel separations, one small recessed button)",
 "hidden":["the subject's give-away parts that must NOT show in the compact state, e.g. heads, necks, scales"],
 "anatomy":"3-5 sentences: the fully transformed toy's body, built from engineered parts (chassis, joints, hinges, rails, servos, pistons, linkages), its signature features made mechanical, how it stands on the table",
 "torso":"one sentence: how the pod's shell panels become the main body",
 "sequence":["5-8 ordered deployment steps, each a physical mechanical motion with its sound, from 'seams separate' to the last part locking"],
 "reveal":"the finished features the camera drifts closer to show, as a short list"}"""


def _pick(options: list[str], subject: str, salt: str) -> str:
    return options[int(hashlib.sha1(f"{salt}|{subject.lower()}".encode()).hexdigest()[:6], 16) % len(options)]


def subject_of(text: str) -> str:
    """'Turn a seven-headed hydra into a mechanical transformation toy...' → 'a seven-headed hydra'."""
    t = " ".join(str(text or "").split())
    m = re.search(r"(?:turn|make|transform|convert)\s+(.+?)\s+into\b", t, re.I)
    s = m.group(1) if m else re.split(r"[.!?\n]", t)[0]
    return s.strip(" .,'\"")[:120] or "a dragon"


def _bare(subject: str) -> str:
    return re.sub(r"^(a|an|the)\s+", "", subject.strip(), flags=re.I)


def default_lock(subject: str) -> dict:
    """The built-in design: preset form, finish and palette from the subject, generic but engineered anatomy and deployment."""
    b = _bare(subject)
    form = _pick(FORMS, b, "form")
    return {
        "subject": subject, "form": form, "finish": _pick(FINISHES, b, "finish"), "palette": _pick(PALETTES, b, "palette"),
        "shell": "restrained concentric seam lines, tiny precision panel separations, and one small recessed button under the visible thumb",
        "hidden": ["limbs", "heads", "eyes", "faces", "tails", "wings", "scales", "wheels", "anatomy clues"],
        "anatomy": (f"A sturdy, low centre chassis carries the unmistakable silhouette of {subject}, every signature feature rebuilt as precision mechanics: "
                    "nested telescoping segments, micro-hinged armour plates, braided actuator cables and compact ball-and-yoke joints. "
                    f"Its head or front section unfolds from concealed housings with engineered plates and articulated details, its limbs telescope from "
                    "underbody rail housings with ratcheting joints and splayed stabilising feet, and every surface shows hinge pins, rails, servos, pistons "
                    "and functional linkages, premium collectible quality."),
        "torso": f"curved shell panels visibly derived from the {form}, rotated outward and locked around a dense central gear cage",
        "sequence": ["concentric shell seams separate with tight servo ticks", "curved outer panels rotate downward on concealed hinges and lock into a low central chassis",
                     "limb assemblies slide from underbody rails and telescope outward through ratcheting joints into stabilising feet",
                     f"the signature features of {b} rise and unfold from concealed housings, segment by segment, as armour plates ratchet into alignment",
                     "head or front-section housings unfold, plates rotate outward and articulated parts open then settle closed with precise servo motion",
                     "braided actuator cables tension while miniature pistons stabilise the final pose"],
        "reveal": f"the finished articulated features of {b}, the central chassis and the stabilising limbs",
    }


def _s(v: Any, n: int, fb: str) -> str:
    v = " ".join(str(v or "").split())
    return v[:n] if v else fb


def norm_lock(d: Any, subject: str) -> dict:
    base = default_lock(subject)
    if not isinstance(d, dict):
        return base
    out = {k: _s(d.get(k), 900 if k == "anatomy" else 300, base[k]) for k in ("subject", "form", "finish", "palette", "shell", "anatomy", "torso", "reveal")}
    out["hidden"] = [_s(x, 40, "") for x in (d.get("hidden") or []) if str(x).strip()][:12] or base["hidden"]
    seq = [_s(x, 300, "") for x in (d.get("sequence") or []) if str(x).strip()][:9]
    out["sequence"] = seq if len(seq) >= 3 else base["sequence"]
    out["finish"] = re.sub(r"\s*#[0-9a-f]{3,8}\b", "", out["finish"], flags=re.I)
    return out


def design(s: dict, subject: str, log: Callable[[dict], None] | None = None) -> dict:
    from ..series import writers
    if not writers.uses_ai(s):
        return default_lock(subject)
    data = writers.ask(s, "story", writers.system("avos-mechanical-toy", DESIGN), f"Subject: {subject}", log, max_tokens=1800, temperature=0.6)
    return norm_lock(data, subject)


def _hidden(lock: dict) -> str:
    h = [x for x in lock["hidden"] if x]
    return ", ".join(f"no {x}" for x in h) + f", no deployed components, and no recognizable {_bare(lock['subject'])} parts"


def compact_prompt(lock: dict) -> str:
    return (f"Hyper-realistic cinematic product realism, {CAMERA}, on {SET}. One compact, sealed mechanical pod is held in one human hand only; the other hand is "
            f"completely outside the frame. The device is a one-hand-held {lock['form']} with a {lock['finish']} finish and a {lock['palette']} color palette. "
            f"Its smooth matte metallic outer shell has {lock['shell']}. Slight natural handheld sway and subtle phone-camera motion blur. The object feels "
            "mysterious, dense, premium, industrial, and physically real, without revealing what it becomes. Absolutely no visible creature hints, "
            f"{_hidden(lock)}. {NEVER}")


def transformed_prompt(lock: dict) -> str:
    return (f"Use the supplied compact-device image as the exact visual continuity reference. Create the fully transformed state in the exact same "
            f"{SET.replace(' with no background clutter', '')} environment, {CAMERA}, and camera language. No hands visible anywhere. The same physical object "
            f"is now fully unfolded into {lock['subject']} mechanical transformation toy, roughly 1.5 to 2 times the size of the compact {lock['finish']} "
            f"{lock['form']}. Preserve exactly the {lock['finish']} finish and the {lock['palette']} color palette. {lock['anatomy']} The torso consists of "
            f"{lock['torso']}. Visible joints, segmented panels, hinge pins, rails, servos, pistons, and functional linkages make the anatomy physically "
            "believable and premium collectible quality. Preserve plausible material volume so every part clearly appears able to fold, telescope, rotate, "
            f"nest, or interlock back into the compact pod. {NEVER_T}")


def video_prompt(lock: dict, seconds: int = 15) -> str:
    steps = "; ".join(lock["sequence"])
    return ("[Style: hyper-realistic, handheld POV, shallow depth of field, natural ambient lighting, ASMR mechanical sounds, no music, portrait orientation] "
            "Use reference image 1 as the exact sealed starting state and reference image 2 as the exact fully transformed ending state, preserving the same "
            f"clean white tabletop, downward-looking iPhone 15 Pro Max camera character, {lock['finish']}, and {lock['palette']} color palette throughout. "
            f"One hand holds the sealed one-hand-held {lock['form']} above the white surface while the camera has gentle natural handheld sway and subtle "
            "phone-camera motion blur; the thumb presses the recessed button and an audible crisp mechanical click sounds. The device is placed onto the white "
            f"surface and the hand withdraws completely from the frame. The pod shudders with tight servo ticks and begins transforming: {steps}. "
            f"Remaining {lock['palette']} accent panels rotate and lock into place, with layered clicks, sliding rails, hydraulic micro-motions, ratcheting "
            f"joints, and tactile metallic locks. A final heavy locking clunk completes the transformation into the exact {_bare(lock['subject'])} mechanical toy "
            f"shown in reference image 2, roughly 1.5 to 2 times the size of the original compact device, and the camera subtly drifts closer to reveal "
            f"{lock['reveal']}. Pacing for {seconds} seconds: click and set-down in the first fifth, transformation through the middle, lockout and reveal in "
            "the last fifth. Keep the transformation physically continuous and volume-conserving; no cuts, no hands after withdrawal, no text, logos, labels, "
            "watermarks, clutter, music, explosions, smoke, magical effects, unrealistic energy effects, or glowing anime effects.")


def prompts(lock: dict, seconds: int = 15) -> dict:
    return {"compact": compact_prompt(lock), "transformed": transformed_prompt(lock), "video": video_prompt(lock, seconds)}
