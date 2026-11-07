"""What GPU this worker has and what it can do: VRAM, temperature, compute capability → precisions, installed kernels.

nvidia-smi is the source (it needs no Python CUDA libraries); PyTorch fills in the CUDA version when present.
WORKER_FAKE_GPU describes a pretend GPU for trying the worker on a machine without one.
"""
from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import os
import platform
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


def memory() -> tuple[float, float, float]:
    """(RAM GB, swap / page file GB, free RAM GB) of this machine."""
    ram = swap = free = 0.0
    if os.name == "nt":
        import ctypes

        class MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = MS()
        m.dwLength = ctypes.sizeof(MS)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):      # type: ignore[attr-defined]
            ram, free = m.ullTotalPhys / 2**30, m.ullAvailPhys / 2**30
            swap = max(0.0, m.ullTotalPageFile / 2**30 - ram)                 # commit limit = RAM + page file
    else:
        try:
            info_ = {ln.split(":")[0]: float(ln.split()[1]) for ln in open("/proc/meminfo") if ":" in ln}
            ram, free, swap = info_.get("MemTotal", 0) / 2**20, info_.get("MemAvailable", 0) / 2**20, info_.get("SwapTotal", 0) / 2**20
        except OSError:
            pass
    if config.RAM_GB:
        ram = config.RAM_GB
    if config.SWAP_GB >= 0:
        swap = config.SWAP_GB
    return round(ram, 1), round(swap, 1), round(free, 1)


def cpu_name() -> str:
    name = ""
    try:
        if os.name == "nt":
            name = os.environ.get("PROCESSOR_IDENTIFIER", "")
            out = subprocess.run(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Processor).Name"],
                                 capture_output=True, text=True, timeout=8)
            name = out.stdout.strip().splitlines()[0] if out.returncode == 0 and out.stdout.strip() else name
        else:
            name = next((ln.split(":", 1)[1].strip() for ln in open("/proc/cpuinfo") if ln.startswith("model name")), "")
    except (OSError, subprocess.SubprocessError, IndexError):
        pass
    return re.sub(r"\s+", " ", name or platform.processor() or "CPU")


def _cpu() -> dict[str, Any]:
    """This machine as a 'GPU' for the router: its memory is RAM + swap (weights beyond RAM page from the SSD)."""
    ram, swap, free = memory()
    total = round(ram + swap, 1)
    return {"name": f"{_cache.get('cpu') or cpu_name()} (CPU)", "device": "cpu", "vram_gb": total, "used_vram_gb": round(max(0.0, ram - free), 1),
            "free_vram_gb": round(free + swap, 1), "ram_gb": ram, "swap_gb": swap, "temperature_c": None, "utilization": None,
            "compute_capability": "cpu", "driver": None, "cuda": None, "power_w": None, "index": 0,
            "max_side": config.CPU_MAX_SIDE, "max_seconds": config.CPU_MAX_SECONDS}


def is_cpu(gpu: dict[str, Any] | None = None) -> bool:
    return (gpu if gpu is not None else info() or {}).get("device") == "cpu"


def info(max_age: float = 2.0) -> dict[str, Any] | None:
    if time.monotonic() - _cache["t"] < max_age:
        return _cache["gpu"]
    if config.DEVICE == "cpu":
        gpu = _cpu()
    else:
        gpu = _smi() or _fake() or (_cpu() if config.DEVICE == "auto" else None)
    if gpu and gpu.get("device") == "cpu" and not _cache.get("cpu"):
        _cache["cpu"] = gpu["name"][:-6]
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
    if (gpu or {}).get("device") == "cpu":
        # ComfyUI on the CPU computes in bf16/fp32; fp8 checkpoints are kept fp8 in memory and cast layer by layer
        return {"cuda": False, "cpu": True, "bf16": True, "fp8": True, "fp4": False, "int8": True, "triton": False,
                "sage_attention": False, "sage_attention_version": None, "flash_attention": False, "xformers": False,
                "nunchaku": False, "torchao": _has("torchao"), "torch": _version("torch")}
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
