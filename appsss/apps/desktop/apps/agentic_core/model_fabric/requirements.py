"""What each model needs and what each GPU can do: the numbers the Model Router reasons with.

Model needs come from catalog.json (each model's "fabric" block). GPU abilities come from the worker's own report
(compute capability, VRAM, which kernels are installed). This module only holds the shared tables and small
helpers; it never talks to the network.
"""
from __future__ import annotations

from typing import Any

# Precisions in order of output quality (best first). A worker can only use the ones its GPU and the backend support.
PRECISIONS = ("bf16", "fp8", "int8", "fp4", "int4")
PRECISION_QUALITY = {"bf16": 1.0, "fp16": 1.0, "fp8": 0.99, "int8": 0.985, "fp4": 0.97, "int4": 0.955}
# GPU time relative to bf16 when the GPU has native support (fp8 on Ada/Hopper/Blackwell, fp4 on Blackwell).
PRECISION_SPEED = {"bf16": 1.0, "fp16": 1.0, "fp8": 0.8, "int8": 1.0, "fp4": 0.6, "int4": 0.85}
# Attention kernels (Wan2GP's own numbers: sage ~30 %, sage2 ~40 % faster than PyTorch SDPA).
ATTENTION_SPEED = {"sdpa": 1.0, "flash": 0.85, "sage": 0.77, "sage2": 0.71}
ATTENTION_ORDER = ("sage2", "sage", "flash", "sdpa")

# GPU speed relative to an RTX 4090 (the catalog's "speed" numbers are measured against it).
GPU_SPEED = [
    ("B200", 3.2), ("H200", 2.1), ("H100", 1.9), ("GH200", 2.0), ("A100", 1.05), ("L40S", 0.95), ("L40", 0.85),
    ("RTX PRO 6000", 1.45), ("RTX 6000 ADA", 0.95), ("A6000", 0.6), ("A40", 0.6), ("A10", 0.4), ("L4", 0.3),
    ("5090", 1.4), ("5080", 0.95), ("5070 TI", 0.75), ("5070", 0.6), ("5060", 0.4),
    ("4090", 1.0), ("4080", 0.75), ("4070 TI", 0.6), ("4070", 0.5), ("4060", 0.35),
    ("3090", 0.55), ("3080", 0.45), ("3070", 0.33), ("3060", 0.28), ("T4", 0.12), ("V100", 0.35),
]

REF_SECONDS = {"image": 20.0, "video": 240.0, "avatar": 300.0, "control": 300.0}   # "fast enough" for speed scores
REF_COST = {"image": 0.005, "video": 0.2, "avatar": 0.4, "control": 0.25}            # "cheap enough" for cost scores
OFFLOAD_SLOWDOWN = 3.0          # running with CPU offload when the model doesn't fit in VRAM
RESERVE_GB = 1.5                # VRAM kept free for activations / the desktop


def gpu_speed(name: str | None) -> float:
    n = (name or "").upper()
    for key, factor in GPU_SPEED:
        if key in n:
            return factor
    return 0.5


def supported_precisions(supports: dict[str, Any]) -> set[str]:
    """Precisions this GPU runs natively (the worker reports bf16/fp8/fp4/int8 from its compute capability)."""
    out = {"int8", "int4"} if supports.get("int8", True) else set()
    out.add("bf16" if supports.get("bf16", True) else "fp16")
    if supports.get("fp8"):
        out.add("fp8")
    if supports.get("fp4"):
        out.add("fp4")
    return out


DEFAULT_FABRIC: dict[str, Any] = {"quality": 0.8, "vram_gb": {}, "min_vram_gb": 0, "speed": 60.0, "load_seconds": 60,
                                  "strengths": [], "adapters": []}


def fabric_of(model: dict[str, Any]) -> dict[str, Any]:
    """The model's routing data with defaults filled in (models you add yourself have none)."""
    f = {**DEFAULT_FABRIC, **(model.get("fabric") or {})}
    if model.get("custom"):
        f.setdefault("strengths", [])
        f["quality"] = float((model.get("definition") or {}).get("quality") or 0.8)
    return f


def vram_need(fabric: dict[str, Any], precision: str) -> float | None:
    v = (fabric.get("vram_gb") or {}).get("bf16" if precision == "fp16" else precision)
    return float(v) if v else None
