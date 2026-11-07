"""GPU worker settings (environment variables). Everything has a sensible default; see README.md."""
from __future__ import annotations

import os
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent

VERSION = "1.0"
NAME = os.getenv("WORKER_NAME") or os.uname().nodename
HOST = os.getenv("WORKER_HOST", "0.0.0.0")
PORT = int(os.getenv("WORKER_PORT", "8700"))
TOKEN = os.getenv("GPU_WORKER_TOKEN") or None                 # same value as AVOS Settings → API keys
COST_PER_HOUR = float(os.getenv("WORKER_COST_PER_HOUR") or 0)  # what this GPU costs you per hour (0 for your own PC)
GPU_INDEX = int(os.getenv("WORKER_GPU_INDEX") or 0)            # one worker per GPU; run another worker for GPU 1
ADAPTERS = [a.strip() for a in (os.getenv("WORKER_ADAPTERS") or "comfyui,wan2gp,diffusers").split(",") if a.strip()]
if os.getenv("WORKER_MOCK") == "1" and "mock" not in ADAPTERS:
    ADAPTERS.append("mock")
RESERVE_GB = float(os.getenv("WORKER_VRAM_RESERVE_GB") or 1.5)
PINNED = {m.strip() for m in (os.getenv("WORKER_PIN") or "").split(",") if m.strip()}   # never evict these models
DATA = Path(os.getenv("WORKER_DATA") or HERE / "data")
RESULTS = DATA / "results"
RESULT_TTL = float(os.getenv("WORKER_RESULT_TTL") or 3600)

# ComfyUI (runs next to the worker on the same GPU machine)
COMFYUI_URL = (os.getenv("COMFYUI_URL") or "http://127.0.0.1:8188").rstrip("/")
COMFYUI_WORKFLOWS = Path(os.getenv("COMFYUI_WORKFLOW_DIR") or HERE / "workflows")
COMFYUI_ATTENTION = os.getenv("COMFYUI_ATTENTION") or "sdpa"   # "sage" if ComfyUI runs with --use-sage-attention

# Wan2GP (github.com/deepbeepmeep/Wan2GP), run headless with `wgp.py --process <settings.json>`
WAN2GP_DIR = Path(os.getenv("WAN2GP_DIR") or "/opt/Wan2GP")
WAN2GP_PYTHON = os.getenv("WAN2GP_PYTHON") or "python"
WAN2GP_TEMPLATES = Path(os.getenv("WAN2GP_TEMPLATES") or HERE / "wan2gp_templates")
WAN2GP_PROFILE = os.getenv("WAN2GP_PROFILE") or None

# Diffusers (in-process pipelines; models download from Hugging Face on first use)
DIFFUSERS_MODELS = os.getenv("WORKER_DIFFUSERS_MODELS") or ""          # comma list to limit, empty = all known
DIFFUSERS_MODELS_JSON = os.getenv("WORKER_DIFFUSERS_MODELS_JSON") or "" # file with extra/overridden model entries

# Model downloads (AVOS Models page → Download → this worker): where ComfyUI's models folder is
MODELS_DIR = os.getenv("WORKER_MODELS_DIR") or (str(Path(os.environ["COMFYUI_DIR"]) / "models") if os.getenv("COMFYUI_DIR") else str(DATA / "models"))

# Mock adapter (no GPU needed: for trying AVOS and for tests)
MOCK_SECONDS = float(os.getenv("WORKER_MOCK_SECONDS") or 1.5)
FAKE_GPU = os.getenv("WORKER_FAKE_GPU") or ""   # JSON, e.g. {"name": "NVIDIA GeForce RTX 4090", "vram_gb": 24, "compute_capability": "8.9"}
