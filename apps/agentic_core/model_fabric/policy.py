"""Generation limits for a shot: how to trade quality, speed and cost, and when to stop.

Defaults come from Settings → Model Fabric; a project can override any of them (its generation_policy). The
generation service sets the project's policy for the duration of a shot with `use(policy)`, and the router and the
repair ladder read it with `current()`, so an agent can't regenerate forever or overspend on one shot.
"""
from __future__ import annotations

import contextlib
import contextvars
from dataclasses import asdict, dataclass
from typing import Any, Iterator

from agentic_core import settings_store


@dataclass(frozen=True)
class GenerationPolicy:
    preference: str = "balanced"             # quality | balanced | speed | cost
    max_cost_per_shot: float | None = None   # USD, estimated before the run
    max_seconds_per_shot: float | None = None
    max_attempts: int = 3                    # generations per shot including the first; then a person decides
    quality_threshold: float = 0.6           # QA score a real check must reach
    allow_hosted: bool = True                # paid hosted APIs (fal.ai, Replicate) allowed
    auto_qa: bool = True                     # QA every shot after it's generated; repair failures automatically
    review_shots: bool = False               # pause before the final render so a person can review the shots
    preferred_model: str | None = None
    fallback_model: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def resolve(project_policy: dict[str, Any] | None = None) -> GenerationPolicy:
    base = settings_store.fabric()
    merged = {**base, **{k: v for k, v in (project_policy or {}).items() if v is not None or k.startswith("max_")}}
    fields = GenerationPolicy.__dataclass_fields__
    return GenerationPolicy(**{k: v for k, v in merged.items() if k in fields})


_current: contextvars.ContextVar[GenerationPolicy | None] = contextvars.ContextVar("avos_generation_policy", default=None)


def current() -> GenerationPolicy:
    return _current.get() or resolve()


@contextlib.contextmanager
def use(policy: GenerationPolicy) -> Iterator[GenerationPolicy]:
    token = _current.set(policy)
    try:
        yield policy
    finally:
        _current.reset(token)
