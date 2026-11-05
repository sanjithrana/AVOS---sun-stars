"""
Prompt Compiler (Week 3 Day 13, Engineer 2 - AVOS-03 v1.1 s10).

Pure function: ShotSpec content -> generation parameters. No I/O, no
randomness beyond what the caller controls, so the same inputs always
compile to the same CompiledPrompt (that determinism is the whole point:
it's what makes the idempotency-key default downstream in
VideoGenerationService reproducible, and it's proven directly by
agentic_core/tests/test_prompt_compiler.py).

Three things make it deterministic:
  - the prompt text is built from ShotContent fields in a fixed order,
    with dict-valued fields (characters/objects) iterated in sorted-key
    order rather than insertion order;
  - the seed defaults to a value derived from a sha256 of the content +
    physics proxy id + candidate index, rather than randomness, unless
    the caller supplies one explicitly;
  - params_hash is the sha256 of every other field, sorted, so any
    change to the compiled output is visible as a changed hash.
"""

import hashlib
import json

from packages.contracts.prompt_compiler import CompiledPrompt
from packages.contracts.shotspec import ShotContent

# Final generation resolution per aspect ratio (higher than the Blender
# physics-proxy resolution in src/core/blender/client.py, which only
# needs to be big enough to condition generation, not display it).
RESOLUTIONS: dict[str, tuple[int, int]] = {
    "9:16": (576, 1024),
    "16:9": (1024, 576),
    "1:1": (768, 768),
}

DEFAULT_NEGATIVE_PROMPT = (
    "blurry, distorted anatomy, extra limbs, text artifacts, watermark, "
    "flicker, inconsistent lighting"
)


def _seed_from(*parts: str) -> int:
    """Deterministic non-negative seed from arbitrary strings."""
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:15], 16)  # fits comfortably in a signed 64-bit int


def _describe_entities(entities: dict, kind: str) -> list[str]:
    lines = []
    for name in sorted(entities):
        state = entities[name]
        state_dict = state.model_dump() if hasattr(state, "model_dump") else dict(state)
        if kind == "character":
            bits = [name]
            if state_dict.get("clothing"):
                bits.append(f"wearing {state_dict['clothing']}")
            if state_dict.get("emotion"):
                bits.append(f"looking {state_dict['emotion']}")
            if state_dict.get("props"):
                bits.append("holding " + ", ".join(state_dict["props"]))
            if state_dict.get("position"):
                bits.append(f"positioned {state_dict['position']}")
            lines.append(", ".join(bits))
        else:
            bits = [name]
            if state_dict.get("state"):
                bits.append(state_dict["state"])
            if state_dict.get("position"):
                bits.append(f"at {state_dict['position']}")
            lines.append(" ".join(bits))
    return lines


def build_prompt_text(content: ShotContent) -> str:
    """Fixed-order prompt assembly. Every input is deterministic
    (sorted dict iteration), so re-running this on the same ShotContent
    always yields byte-identical text."""
    env = content.environment
    parts: list[str] = []

    if content.description:
        parts.append(content.description)

    char_lines = _describe_entities(content.characters, "character")
    if char_lines:
        parts.append("Characters: " + "; ".join(char_lines) + ".")

    obj_lines = _describe_entities(content.objects, "object")
    if obj_lines:
        parts.append("Objects: " + "; ".join(obj_lines) + ".")

    env_bits = [b for b in (env.location, env.time_of_day, env.weather) if b]
    if env_bits:
        parts.append("Setting: " + ", ".join(env_bits) + ".")

    parts.append(
        f"Camera: {content.camera.shot_type.value.replace('_', ' ')} shot, "
        f"{content.camera.angle.replace('_', ' ')} angle, {content.camera.movement} movement, "
        f"{content.camera.lens_mm}mm lens."
    )
    parts.append(f"Lighting: {content.lighting.key}, {content.lighting.mood} mood.")

    if content.style:
        parts.append(f"Style: {content.style}.")

    return " ".join(parts)


def compile_prompt(
    content: ShotContent,
    *,
    physics_proxy_asset_id: str,
    aspect_ratio: str = "9:16",
    candidate_index: int = 0,
    seed: int | None = None,
    negative_prompt: str = DEFAULT_NEGATIVE_PROMPT,
) -> CompiledPrompt:
    """Compile one ShotSpec ShotContent into generation parameters for one
    candidate. Conditioned on the physics proxy (physics-before-pixels):
    the proxy id and the four control passes it grounds generation on are
    recorded in `conditioning_passes` so a downstream ComfyUI/video model
    knows what to condition on, and so the compiled output changes if the
    proxy does (an edited ShotSpec always gets a fresh proxy - see
    services/physics_gate.py - which changes physics_proxy_asset_id and
    therefore the default seed and params_hash here too)."""
    width, height = RESOLUTIONS.get(aspect_ratio, RESOLUTIONS["9:16"])
    prompt = build_prompt_text(content)

    resolved_seed = (
        seed
        if seed is not None
        else _seed_from(content.model_dump_json(), physics_proxy_asset_id, str(candidate_index))
    )

    fields = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "seed": resolved_seed,
        "candidate_index": candidate_index,
        "width": width,
        "height": height,
        "duration_seconds": content.duration_seconds,
        "camera_movement": content.camera.movement,
        "lens_mm": content.camera.lens_mm,
        "style": content.style,
        "physics_proxy_asset_id": physics_proxy_asset_id,
        "conditioning_passes": ["depth", "normal", "canny", "mask"],
    }
    params_hash = hashlib.sha256(
        json.dumps(fields, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()

    return CompiledPrompt(**fields, params_hash=params_hash)
