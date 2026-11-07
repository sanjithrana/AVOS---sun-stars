"""Which files each model needs for ComfyUI (agentic_core/models/downloads.json), per precision, for the Models
page's Download button. Verified against the Hugging Face file listings and ComfyUI's official templates.

    options("wan-2.2")                       → variants (fp8 / bf16 …) with total sizes, extras, notes
    files("wan-2.2", "fp8", extras=[...])    → the file list to give downloads.start()
    present(dest, "wan-2.2")                 → which variants are already complete in a folder
"""
from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Any

from agentic_core.model_fabric import downloads

PATH = Path(__file__).resolve().parent.parent / "models" / "downloads.json"
ORDER = ("bf16", "fp16", "xxl", "fp8", "xl", "int8", "fp4", "int4", "turbo")
LABEL = {"bf16": "Full quality (bf16/fp16)", "fp8": "fp8 (half the memory, near-full quality)",
         "int8": "int8 (half the memory)", "fp4": "fp4 (RTX 50 / Blackwell)", "int4": "int4 (smallest)",
         "xxl": "XXL (best sound, ~20 GB VRAM)", "xl": "XL (~16 GB VRAM)", "turbo": "Turbo (all-in-one)"}


@functools.lru_cache(maxsize=1)
def manifest() -> dict[str, Any]:
    return json.loads(PATH.read_text("utf-8"))["models"]


def has(model_id: str) -> bool:
    return model_id in manifest()


def _entry(model_id: str) -> dict[str, Any]:
    try:
        return manifest()[model_id]
    except KeyError as e:
        raise KeyError(f"No download list for {model_id}.") from e


def _id(f: dict[str, Any]) -> str:
    return f"{f['folder']}/{Path(f['path']).name}"


def _pub(f: dict[str, Any]) -> dict[str, Any]:
    return {"id": _id(f), "repo": f["repo"], "path": f["path"], "folder": f["folder"], "name": Path(f["path"]).name,
            "size": f["size"], "label": f.get("label"), "recommended": bool(f.get("recommended")),
            "url": downloads.hf_url(f["repo"], f["path"])}


def options(model_id: str, vram_gb: float | None = None) -> dict[str, Any]:
    e = _entry(model_id)
    shared = [_pub(f) for f in e.get("shared") or []]
    shared_size = sum(f["size"] for f in shared)
    variants = []
    for key in sorted(e["variants"], key=lambda k: ORDER.index(k) if k in ORDER else 99):
        fs = [_pub(f) for f in e["variants"][key]]
        size = sum(f["size"] for f in fs)
        variants.append({"key": key, "label": LABEL.get(key, key), "files": fs, "size": size,
                         "total": size + shared_size, "default": key == e.get("default")})
    rec = e.get("default")
    if vram_gb:   # the best variant whose main weights fit the GPU (as ComfyUI loads them, plus headroom)
        needs = e.get("needs_gb") or {}     # VRAM a variant needs when that isn't just its weights' size
        fitting = [v for v in variants if (needs.get(v["key"]) or v["size"] / 1e9) <= vram_gb * 0.95]
        if fitting:
            rec = fitting[0]["key"]
    return {"model": model_id, "verified": bool(e.get("verified")), "template": e.get("template"),
            "notes": e.get("notes"), "variants": variants, "shared": shared,
            "optional": [_pub(f) for f in e.get("optional") or []], "recommended": rec}


def files(model_id: str, variant: str | None = None, extras: list[str] | None = None) -> list[dict[str, Any]]:
    e = _entry(model_id)
    variant = variant or e.get("default")
    if variant not in e["variants"]:
        raise ValueError(f"{model_id} has no {variant} version (it has: {', '.join(e['variants'])}).")
    wanted = set(extras or [])
    chosen = list(e["variants"][variant]) + list(e.get("shared") or []) + \
        [f for f in e.get("optional") or [] if _id(f) in wanted]
    return [{"repo": f["repo"], "path": f["path"], "folder": f["folder"], "name": Path(f["path"]).name,
             "size": f["size"], "url": downloads.hf_url(f["repo"], f["path"])} for f in chosen]


def present(dest: str, model_id: str) -> dict[str, Any]:
    """{variant: True when every file of that variant + the shared files is in dest with the right size}."""
    e = _entry(model_id)
    root = Path(dest)

    def ok(f: dict[str, Any]) -> bool:
        p = root / f["folder"] / Path(f["path"]).name
        return p.is_file() and p.stat().st_size == f["size"]
    shared_ok = all(ok(f) for f in e.get("shared") or [])
    return {k: shared_ok and all(ok(f) for f in fs) for k, fs in e["variants"].items()}
