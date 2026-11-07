"""Execution backends on this worker, in the order WORKER_ADAPTERS lists them (the router treats that as preference)."""
from __future__ import annotations

from worker import config
from worker.adapters.base import Adapter


def build() -> dict[str, Adapter]:
    out: dict[str, Adapter] = {}
    for name in config.ADAPTERS:
        if name == "comfyui":
            from worker.adapters.comfyui import ComfyUIAdapter

            out[name] = ComfyUIAdapter()
        elif name == "wan2gp":
            from worker.adapters.wan2gp import Wan2GPAdapter

            out[name] = Wan2GPAdapter()
        elif name == "diffusers":
            from worker.adapters.diffusers_adapter import DiffusersAdapter

            out[name] = DiffusersAdapter()
        elif name == "speech":
            from worker.adapters.speech import SpeechAdapter

            out[name] = SpeechAdapter()
        elif name == "foley":
            from worker.adapters.foley import FoleyAdapter

            out[name] = FoleyAdapter()
        elif name == "mock":
            from worker.adapters.mock import MockAdapter

            out[name] = MockAdapter()
    return out
