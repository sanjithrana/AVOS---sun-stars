"""The interface every execution backend on the worker implements (ComfyUI, Wan2GP, Diffusers, mock).

AVOS sends a job that already names the backend ("adapter"), the precision and the attention kernel the Model
Router chose; the adapter turns it into a run on its engine and returns the output bytes.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

Progress = Callable[[float, str], Awaitable[None]]


@dataclass
class JobSpec:
    model: str
    adapter: str
    precision: str = "bf16"
    attention: str = "sdpa"
    offload: bool = False
    task: str = "video"          # image | video | avatar
    want: str = "video"          # what to return: video | image
    prompt: str = ""
    negative_prompt: str = ""
    width: int = 1280
    height: int = 720
    seconds: float = 5.0
    frames: int | None = None
    fps: int | None = None
    seed: int | None = None
    steps: int | None = None
    vram_gb: float | None = None
    inputs: dict[str, bytes] = field(default_factory=dict)     # image / audio / video
    timeout: float = 1800.0
    priority: int = 5            # 0 = someone is waiting (a Studio edit) … 9 = background warm-up
    tag: str | None = None       # who asked (project / shot), shown in the queue

    @classmethod
    def from_body(cls, body: dict[str, Any], inputs: dict[str, bytes]) -> "JobSpec":
        fields = cls.__dataclass_fields__
        spec = cls(**{k: v for k, v in body.items() if k in fields and k != "inputs" and v is not None}, inputs=inputs)
        spec.priority = max(0, min(9, int(spec.priority)))
        return spec


class Adapter(ABC):
    name = "base"
    #: precisions this backend can apply (intersected with what the GPU supports)
    precisions: tuple[str, ...] = ("bf16",)
    #: attention kernels this backend can switch between per job
    attentions: tuple[str, ...] = ("sdpa",)
    #: can it run a model that doesn't fit in VRAM by offloading to CPU RAM
    offload = True
    #: keeps models loaded between jobs (False: every job loads the model again)
    keeps_loaded = True

    @abstractmethod
    async def ready(self) -> tuple[bool, str | None]:
        """(usable now, why not)."""

    @abstractmethod
    def models(self) -> list[str]:
        """AVOS model ids this backend can run on this machine."""

    async def load(self, job: JobSpec, progress: Progress) -> None:  # noqa: B027 - optional
        """Load the model at job.precision with job.attention (no-op for backends that load per run)."""

    async def unload(self, model: str) -> None:  # noqa: B027 - optional
        """Free the model's VRAM."""

    @abstractmethod
    async def run(self, job: JobSpec, progress: Progress) -> tuple[bytes, str]:
        """Generate; returns (bytes, file extension)."""

    async def cancel(self) -> None:  # noqa: B027 - optional
        """Stop the running job if the engine supports it."""

    def describe(self) -> dict[str, Any]:
        return {"precisions": list(self.precisions), "attentions": list(self.attentions), "offload": self.offload,
                "keeps_loaded": self.keeps_loaded}
