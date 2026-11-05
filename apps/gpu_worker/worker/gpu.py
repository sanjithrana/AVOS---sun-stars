"""What GPU this worker has and what it can do: VRAM, temperature, compute capability → precisions, installed kernels.

nvidia-smi is the source (it needs no Python CUDA libraries); PyTorch fills in the CUDA version when present.
WORKER_FAKE_GPU describes a pretend GPU for trying the worker on a machine without one.
"""
from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import re
import shutil
import subprocess
import time
from typing import Any

from worker import config

_cache: dict[str, Any] = {"t": 0.0, "gpu": None}
FIELDS = "name,memory.total,memory.used,memory.free,temperature.gpu,utilization.gpu,compute_cap,driver_version,power.draw"


def _smi() -> dict[str, Any] | None:
    if not shutil.which("nvidia-smi"):
        return None
    try:
        out = subprocess.run(["nvidia-smi", f"--query-gpu={FIELDS}", "--format=csv,noheader,nounits",
                              f"--id={config.GPU_INDEX}"], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None
    v = [x.strip() for x in out.stdout.strip().splitlines()[0].split(",")]

    def num(x: str) -> float | None:
        try:
            return float(x)
        except ValueError:
            return None

    gpu = {"name": v[0], "vram_gb": round((num(v[1]) or 0) / 1024, 1), "used_vram_gb": round((num(v[2]) or 0) / 1024, 1),
           "free_vram_gb": round((num(v[3]) or 0) / 1024, 1), "temperature_c": num(v[4]), "utilization": num(v[5]),
           "compute_capability": v[6], "driver": v[7], "power_w": num(v[8]) if len(v) > 8 else None, "index": config.GPU_INDEX}
    try:
        head = subprocess.run(["nvidia-smi"], capture_output=True, text=True, timeout=5).stdout
        m = re.search(r"CUDA Version:\s*([\d.]+)", head)
        gpu["cuda"] = m.group(1) if m else None
    except (OSError, subprocess.SubprocessError):
        gpu["cuda"] = None
    return gpu


def _fake() -> dict[str, Any] | None:
    if not config.FAKE_GPU:
        return None
    f = json.loads(config.FAKE_GPU)
    total = float(f.get("vram_gb") or 24)
    return {"name": f.get("name") or "Pretend GPU", "vram_gb": total, "used_vram_gb": 0.0, "free_vram_gb": total,
            "temperature_c": f.get("temperature_c", 45), "utilization": 0, "compute_capability": str(f.get("compute_capability") or "8.9"),
            "driver": "fake", "cuda": f.get("cuda") or "12.8", "power_w": None, "index": 0, "fake": True}


def info(max_age: float = 2.0) -> dict[str, Any] | None:
    if time.monotonic() - _cache["t"] < max_age:
        return _cache["gpu"]
    gpu = _smi() or _fake()
    _cache.update(t=time.monotonic(), gpu=gpu)
    return gpu


def _has(mod: str) -> bool:
    try:
        return importlib.util.find_spec(mod) is not None
    except (ImportError, ValueError):
        return False


def _version(dist: str) -> str | None:
    try:
        return importlib.metadata.version(dist)
    except importlib.metadata.PackageNotFoundError:
        return None


def supports(gpu: dict[str, Any] | None = None) -> dict[str, Any]:
    gpu = gpu if gpu is not None else info()
    try:
        cc = float((gpu or {}).get("compute_capability") or 0)
    except ValueError:
        cc = 0.0
    sage = _version("sageattention")
    return {
        "cuda": bool(gpu),
        "bf16": cc >= 8.0,                      # Ampere (RTX 30, A100) and newer
        "fp8": cc >= 8.9,                       # Ada (RTX 40, L40), Hopper (H100), Blackwell
        "fp4": cc >= 10.0,                      # Blackwell (RTX 50, B200): NV FP4
        "int8": bool(gpu),
        "triton": _has("triton"),
        "sage_attention": bool(sage),
        "sage_attention_version": sage,
        "flash_attention": _has("flash_attn"),
        "xformers": _has("xformers"),
        "nunchaku": _has("nunchaku"),
        "torchao": _has("torchao"),
        "torch": _version("torch"),
    }


def best_attention(sup: dict[str, Any], allowed: tuple[str, ...] = ("sage2", "sage", "flash", "sdpa")) -> str:
    """Fastest attention kernel installed that this GPU can use."""
    try:
        cc = float((info() or {}).get("compute_capability") or 0)
    except ValueError:
        cc = 0.0
    v = sup.get("sage_attention_version") or ""
    if "sage2" in allowed and v.startswith("2") and cc >= 8.0 and sup.get("triton"):
        return "sage2"
    if "sage" in allowed and v and sup.get("triton"):
        return "sage"
    if "flash" in allowed and sup.get("flash_attention") and cc >= 8.0:
        return "flash"
    return "sdpa"
