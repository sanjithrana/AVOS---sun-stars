"""Model residency: keep models loaded between shots, evict the least recently used when VRAM runs out.

    Shot 1 → LTX (load 90 s) · Shot 2 → LTX (already loaded) · Shot 3 → Wan 2.2 (evict LTX only if Wan doesn't fit)

Models in WORKER_PIN are never evicted. The manager works from the job's VRAM need (sent by AVOS from the catalog)
and the GPU's free VRAM (nvidia-smi), so it also respects memory used by other programs on the GPU.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from worker import config


@dataclass
class Resident:
    model: str
    adapter: str
    precision: str
    vram_gb: float
    loaded_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    uses: int = 0

    def public(self) -> dict[str, Any]:
        return {"model": self.model, "adapter": self.adapter, "precision": self.precision, "vram_gb": self.vram_gb,
                "loaded_at": self.loaded_at, "last_used": self.last_used, "uses": self.uses,
                "pinned": self.model in config.PINNED}


class Residency:
    def __init__(self, total_gb: Callable[[], float], free_gb: Callable[[], float | None],
                 unload: Callable[[Resident], Awaitable[None]], reserve_gb: float = config.RESERVE_GB) -> None:
        self.total_gb, self.free_gb, self.unload, self.reserve_gb = total_gb, free_gb, unload, reserve_gb
        self.resident: dict[tuple[str, str], Resident] = {}

    def get(self, model: str, adapter: str) -> Resident | None:
        return self.resident.get((model, adapter))

    def used_gb(self) -> float:
        return sum(r.vram_gb for r in self.resident.values())

    def available_gb(self) -> float:
        """Free VRAM for a new model: the smaller of what the GPU reports and what our own bookkeeping says."""
        estimate = self.total_gb() - self.used_gb()
        measured = self.free_gb()
        free = estimate if measured is None else min(measured, estimate)
        return free - self.reserve_gb

    async def make_room(self, model: str, adapter: str, precision: str, need_gb: float) -> list[Resident]:
        """Evict least-recently-used models until this one fits; returns what was evicted. The same model loaded at a
        different precision is evicted first. Stops (and lets the backend offload) when nothing else can go."""
        evicted: list[Resident] = []
        cur = self.get(model, adapter)
        if cur and cur.precision == precision:
            return evicted
        if cur:
            await self._evict(cur)
            evicted.append(cur)
        while self.available_gb() < need_gb:
            victims = sorted((r for r in self.resident.values() if r.model not in config.PINNED), key=lambda r: r.last_used)
            if not victims:
                break
            await self._evict(victims[0])
            evicted.append(victims[0])
        return evicted

    async def _evict(self, r: Resident) -> None:
        self.resident.pop((r.model, r.adapter), None)
        await self.unload(r)

    def loaded(self, model: str, adapter: str, precision: str, vram_gb: float) -> Resident:
        r = Resident(model, adapter, precision, vram_gb)
        self.resident[(model, adapter)] = r
        return r

    def touch(self, model: str, adapter: str) -> None:
        r = self.get(model, adapter)
        if r:
            r.last_used = time.time()
            r.uses += 1

    def forget(self, model: str, adapter: str) -> None:
        self.resident.pop((model, adapter), None)
