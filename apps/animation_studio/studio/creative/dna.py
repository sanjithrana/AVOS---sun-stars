"""Design DNA: the visual and motion system of a series (or a Facts style), written down once and compiled into every
prompt, so shots share one look instead of each being an isolated prompt.

    dna = normalize({"line": "thick dark outlines", "palette": ["#2B2D42", ...]})
    style_clause(dna)   → "Art style: … ; line: … ; colours: …"
    motion_clause(dna)  → "Animation: snappy cartoon timing, holds on key poses, …"
    negative(dna)       → what the models must avoid
"""
from __future__ import annotations

import re
from typing import Any

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")

DEFAULT: dict[str, Any] = {
    "name": "",
    "medium": "2D cartoon animation",
    "line": "clean dark outlines",
    "shading": "flat cel shading with soft shadows",
    "proportions": "expressive faces, slightly big heads",
    "texture": "clean digital paint",
    "palette": [],
    "lighting": "bright, readable, warm",
    "camera": {"default_lens": 35, "angle": "eye level", "max_speed": "slow", "allowed_moves": []},
    "motion": {"pacing": "lively", "ease": "power2.inOut", "squash_stretch": True, "holds": True, "feel": "smooth, expressive"},
    "sound": {"ambience": "", "music": "light, playful", "sfx_style": "cartoon, clear"},
    "avoid": ["photorealism", "3D render look", "text", "watermark"],
}
STR_FIELDS = ("name", "medium", "line", "shading", "proportions", "texture", "lighting")


def normalize(dna: dict | None) -> dict[str, Any]:
    """Fill gaps with defaults, clamp lengths, keep only valid colours. Safe on any input (LLM output, user edits)."""
    d = dna if isinstance(dna, dict) else {}
    out: dict[str, Any] = {}
    for k in STR_FIELDS:
        v = d.get(k)
        out[k] = str(v).strip()[:300] if isinstance(v, (str, int, float)) and str(v).strip() else DEFAULT[k]
    out["palette"] = [c.upper() for c in (d.get("palette") or []) if isinstance(c, str) and HEX.match(c.strip())][:8]
    for k in ("camera", "motion", "sound"):
        src = d.get(k) if isinstance(d.get(k), dict) else {}
        merged = dict(DEFAULT[k])
        for kk, vv in src.items():
            if kk not in merged:
                continue
            cur = merged[kk]
            if isinstance(cur, bool):
                merged[kk] = bool(vv)
            elif isinstance(cur, (int, float)) and isinstance(vv, (int, float)) and not isinstance(vv, bool):
                merged[kk] = vv
            elif isinstance(cur, str) and isinstance(vv, str) and vv.strip():
                merged[kk] = vv.strip()[:200]
            elif isinstance(cur, list) and isinstance(vv, list):
                merged[kk] = [str(x)[:40] for x in vv][:12]
        out[k] = merged
    try:
        out["camera"]["default_lens"] = int(max(14, min(135, float(out["camera"]["default_lens"]))))
    except (TypeError, ValueError):
        out["camera"]["default_lens"] = 35
    avoid = d.get("avoid") if isinstance(d.get("avoid"), list) else DEFAULT["avoid"]
    out["avoid"] = [str(a)[:60] for a in avoid if str(a).strip()][:12]
    return out


def style_clause(dna: dict) -> str:
    d = normalize(dna)
    bits = [f"Art style: {d['medium']}" + (f" ({d['name']})" if d["name"] else ""), f"line: {d['line']}", f"shading: {d['shading']}",
            f"proportions: {d['proportions']}", f"texture: {d['texture']}", f"lighting: {d['lighting']}"]
    if d["palette"]:
        bits.append("colour palette " + ", ".join(d["palette"]))
    return "; ".join(bits) + "."


def motion_clause(dna: dict) -> str:
    m = normalize(dna)["motion"]
    bits = [f"{m['pacing']} pacing", m["feel"]]
    if m.get("squash_stretch"):
        bits.append("squash and stretch on big moves")
    if m.get("holds"):
        bits.append("clear holds on key poses")
    return "Animation: " + ", ".join(b for b in bits if b) + "."


def negative(dna: dict, extra: str = "") -> str:
    d = normalize(dna)
    base = ["blurry", "deformed hands", "extra limbs", "extra fingers", "duplicate character", "flicker", "morphing face",
            "speech bubble", "character sheet layout"]
    return ", ".join(dict.fromkeys([*d["avoid"], *base, *([extra] if extra else [])]))


def from_style_preset(preset: Any) -> dict[str, Any]:
    """A Facts style preset (agentic_core/styles.py) as Design DNA."""
    name = getattr(preset, "name", None) or getattr(preset, "id", "") or ""
    prompt = getattr(preset, "visual_style", None) or getattr(preset, "prompt", None) or getattr(preset, "style", "") or ""
    motion_hint = getattr(preset, "motion_hint", "") or ""
    return normalize({"name": str(name), "medium": str(prompt)[:200] or DEFAULT["medium"],
                      "motion": {"feel": str(motion_hint)[:120] or DEFAULT["motion"]["feel"]}})
