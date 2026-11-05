"""Model downloads: fetch a model's files from Hugging Face into a folder you choose, with progress, resume and
cancel. The same file runs in the AVOS API (download to this PC) and in the GPU worker (download straight onto the
GPU machine, where the model runs): apps/gpu_worker/worker/downloads.py is an identical copy
(agentic_core/model_fabric/downloads.py is the original; keep them the same).

    job = start(files=[{"url": ..., "folder": "diffusion_models", "name": "x.safetensors", "size": 123}],
                dest="/models", label="Wan 2.2 (fp8)")
    job.public()      # status, bytes done / total, speed, ETA, per file
    cancel(job.id)

Files land in <dest>/<folder>/<name> (ComfyUI's models layout). A file already there with the right size is skipped;
a partial download (<name>.part) resumes with an HTTP Range request. Before starting, the free disk space is checked.
Standard library + httpx only.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

CHUNK = 4 * 1024 * 1024
PARALLEL_FILES = int(os.getenv("DOWNLOAD_PARALLEL_FILES") or 2)
HEADROOM = 1.02            # keep 2 % free space margin
FOLDERS = {"diffusion_models", "text_encoders", "vae", "loras", "checkpoints", "clip_vision", "audio_encoders",
           "model_patches", "latent_upscale_models", "upscale_models", "unet", "clip", "controlnet",
           "hunyuanvideo_foley"}


def hf_endpoint() -> str:
    return (os.getenv("HF_ENDPOINT") or "https://huggingface.co").rstrip("/")


def hf_url(repo: str, path: str, revision: str = "main") -> str:
    return f"{hf_endpoint()}/{repo}/resolve/{revision}/{path}"


def _headers() -> dict[str, str]:
    tok = os.getenv("HF_TOKEN") or os.getenv("HUGGING_FACE_HUB_TOKEN")
    return {"Authorization": f"Bearer {tok}"} if tok else {}


@dataclass
class FileState:
    url: str
    folder: str
    name: str
    size: int | None = None
    done: int = 0
    status: str = "waiting"            # waiting | downloading | done | skipped | error | cancelled
    error: str | None = None

    def public(self) -> dict[str, Any]:
        return {"name": self.name, "folder": self.folder, "size": self.size, "done": self.done, "status": self.status,
                "error": self.error}


@dataclass
class Job:
    dest: str
    files: list[FileState]
    label: str = ""
    model: str | None = None
    variant: str | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    status: str = "queued"             # queued | running | done | error | cancelled
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    _samples: list[tuple[float, int]] = field(default_factory=list)
    _task: asyncio.Task | None = None

    @property
    def total(self) -> int:
        return sum(f.size or 0 for f in self.files)

    @property
    def done(self) -> int:
        return sum(f.done for f in self.files)

    def speed(self) -> float:
        """Bytes per second over the last ~10 s."""
        now = time.monotonic()
        self._samples = [s for s in self._samples if now - s[0] < 10] + [(now, self.done)]
        if len(self._samples) < 2:
            return 0.0
        (t0, b0), (t1, b1) = self._samples[0], self._samples[-1]
        return max(0.0, (b1 - b0) / (t1 - t0)) if t1 > t0 else 0.0

    def public(self) -> dict[str, Any]:
        sp = self.speed() if self.status == "running" else 0.0
        left = max(0, self.total - self.done)
        return {"id": self.id, "label": self.label, "model": self.model, "variant": self.variant, "dest": self.dest,
                "status": self.status, "error": self.error, "total": self.total, "done": self.done,
                "progress": round(self.done / self.total, 4) if self.total else (1.0 if self.status == "done" else 0.0),
                "speed": round(sp), "eta": round(left / sp) if sp > 0 else None,
                "created_at": self.created_at, "started_at": self.started_at, "finished_at": self.finished_at,
                "files": [f.public() for f in self.files]}


JOBS: dict[str, Job] = {}


def jobs() -> list[dict[str, Any]]:
    return [j.public() for j in sorted(JOBS.values(), key=lambda j: -j.created_at)][:50]


def get(job_id: str) -> Job | None:
    return JOBS.get(job_id)


def _safe_name(name: str) -> str:
    n = Path(name).name
    if not n or n in (".", "..") or n != name.split("/")[-1]:
        raise ValueError(f"Bad file name: {name!r}")
    return n


def plan_files(files: list[dict[str, Any]], dest: str) -> list[FileState]:
    out, seen = [], set()
    for f in files:
        folder = str(f.get("folder") or "").strip("/")
        if folder and folder not in FOLDERS:
            raise ValueError(f"Unknown model folder {folder!r}.")
        name = _safe_name(str(f.get("name") or Path(str(f.get("path") or "")).name))
        url = str(f.get("url") or (hf_url(f["repo"], f["path"]) if f.get("repo") and f.get("path") else ""))
        if not url.startswith(("http://", "https://")):
            raise ValueError(f"No download address for {name}.")
        key = (folder, name)
        if key in seen:          # shared files (VAE, text encoder) listed twice
            continue
        seen.add(key)
        out.append(FileState(url=url, folder=folder, name=name, size=int(f["size"]) if f.get("size") else None))
    return out


def target(dest: str, fs: FileState) -> Path:
    return Path(dest) / fs.folder / fs.name if fs.folder else Path(dest) / fs.name


def needed_bytes(dest: str, files: list[FileState]) -> int:
    need = 0
    for fs in files:
        t = target(dest, fs)
        if fs.size and t.exists() and t.stat().st_size == fs.size:
            continue
        part = t.with_name(t.name + ".part")
        have = part.stat().st_size if part.exists() else 0
        need += max(0, (fs.size or 0) - have)
    return need


def free_bytes(path: str) -> int:
    p = Path(path)
    while not p.exists() and p != p.parent:
        p = p.parent
    return shutil.disk_usage(p).free


def start(*, files: list[dict[str, Any]], dest: str, label: str = "", model: str | None = None,
          variant: str | None = None) -> Job:
    dest = str(Path(dest).expanduser())
    planned = plan_files(files, dest)
    if not planned:
        raise ValueError("Nothing to download.")
    need = needed_bytes(dest, planned)
    free = free_bytes(dest)
    if need * HEADROOM > free:
        raise ValueError(f"Not enough free space in {dest}: needs {need / 1e9:.1f} GB, {free / 1e9:.1f} GB free.")
    for j in JOBS.values():
        if j.status in ("queued", "running") and j.dest == dest and {(f.folder, f.name) for f in j.files} & \
                {(f.folder, f.name) for f in planned}:
            raise ValueError(f"These files are already downloading ({j.label or j.id}).")
    job = Job(dest=dest, files=planned, label=label, model=model, variant=variant)
    JOBS[job.id] = job
    job._task = asyncio.get_running_loop().create_task(_run(job))
    return job


def cancel(job_id: str) -> Job | None:
    job = JOBS.get(job_id)
    if job and job._task and not job._task.done():
        job._task.cancel()
    return job


def forget(job_id: str) -> None:
    j = JOBS.get(job_id)
    if j and j.status not in ("queued", "running"):
        JOBS.pop(job_id, None)


async def _run(job: Job) -> None:
    job.status, job.started_at = "running", time.time()
    sem = asyncio.Semaphore(max(1, PARALLEL_FILES))
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, read=300.0), follow_redirects=True,
                                     headers=_headers()) as client:
            async def one(fs: FileState) -> None:
                async with sem:
                    await _download(client, job, fs)
            results = await asyncio.gather(*(one(fs) for fs in job.files), return_exceptions=True)
        errors = [f"{fs.name}: {fs.error}" for fs in job.files if fs.status == "error"]
        cancelled = any(isinstance(r, asyncio.CancelledError) for r in results)
        if cancelled:
            raise asyncio.CancelledError()
        job.status = "error" if errors else "done"
        job.error = "; ".join(errors)[:1000] or None
    except asyncio.CancelledError:
        job.status = "cancelled"
        for fs in job.files:
            if fs.status in ("waiting", "downloading"):
                fs.status = "cancelled"
    except Exception as exc:  # noqa: BLE001 - reported on the job
        job.status, job.error = "error", str(exc)[:1000]
    finally:
        job.finished_at = time.time()


async def _download(client: httpx.AsyncClient, job: Job, fs: FileState) -> None:
    t = target(job.dest, fs)
    t.parent.mkdir(parents=True, exist_ok=True)
    if t.exists() and (fs.size is None or t.stat().st_size == fs.size):
        fs.status, fs.done = "skipped", t.stat().st_size
        fs.size = fs.size or fs.done
        return
    part = t.with_name(t.name + ".part")
    have = part.stat().st_size if part.exists() else 0
    if fs.size and have > fs.size:
        part.unlink()
        have = 0
    fs.status, fs.done = "downloading", have
    headers = {"Range": f"bytes={have}-"} if have else {}
    try:
        async with client.stream("GET", fs.url, headers=headers) as r:
            if r.status_code in (401, 403):
                raise RuntimeError("Hugging Face refused the download: this repo needs a token (set HF_TOKEN) or "
                                   "accepting its terms on huggingface.co.")
            if r.status_code == 404:
                raise RuntimeError("File not found on Hugging Face (it may have been renamed).")
            if r.status_code == 416 and fs.size and have == fs.size:
                pass
            elif r.status_code >= 400:
                raise RuntimeError(f"HTTP {r.status_code}")
            if have and r.status_code == 200:     # server ignored the Range: start over
                have, fs.done = 0, 0
                part.unlink(missing_ok=True)
            if r.status_code != 416:
                total = r.headers.get("content-length")
                if fs.size is None and total:
                    fs.size = have + int(total)
                with open(part, "ab") as out:
                    async for chunk in r.aiter_bytes(CHUNK):
                        out.write(chunk)
                        fs.done += len(chunk)
        got = part.stat().st_size
        if fs.size and got != fs.size:
            raise RuntimeError(f"incomplete: {got} of {fs.size} bytes (start the download again to resume)")
        os.replace(part, t)
        fs.status = "done"
    except asyncio.CancelledError:
        fs.status = "cancelled"
        raise
    except Exception as exc:  # noqa: BLE001
        fs.status, fs.error = "error", str(exc)[:300] or type(exc).__name__


# ---------- folder picker ----------
def roots() -> list[str]:
    """Folders downloads may go into (DOWNLOAD_ROOTS, ':' or ';' separated). Empty = anywhere."""
    raw = os.getenv("DOWNLOAD_ROOTS") or ""
    return [str(Path(p).expanduser()) for p in raw.replace(";", ":").split(":") if p.strip()] if raw else []


def allowed(path: str) -> bool:
    rs = roots()
    if not rs:
        return True
    p = Path(path).expanduser().resolve()
    return any(p == Path(r).resolve() or Path(r).resolve() in p.parents for r in rs)


def browse(path: str | None) -> dict[str, Any]:
    """Sub-folders of a folder, for picking where to download (on this machine)."""
    rs = roots()
    if not path:
        if rs:
            return {"path": None, "parent": None, "dirs": [{"name": r, "path": r} for r in rs], "roots": rs,
                    "free": None, "writable": False}
        path = str(Path.home())
    p = Path(path).expanduser()
    if not allowed(str(p)):
        raise ValueError(f"Downloads can only go under: {', '.join(rs)} (DOWNLOAD_ROOTS).")
    if not p.is_dir():
        raise ValueError(f"No such folder: {p}")
    dirs = []
    try:
        for c in sorted(p.iterdir(), key=lambda c: c.name.lower()):
            if c.is_dir() and not c.name.startswith("."):
                dirs.append({"name": c.name, "path": str(c)})
    except PermissionError:
        pass
    parent = str(p.parent) if p.parent != p and allowed(str(p.parent)) else None
    has_models = any((p / f).is_dir() for f in ("diffusion_models", "checkpoints", "text_encoders", "vae"))
    return {"path": str(p), "parent": parent, "dirs": dirs[:500], "roots": rs, "free": shutil.disk_usage(p).free,
            "writable": os.access(p, os.W_OK), "looks_like_models": has_models}


def mkdir(path: str, name: str) -> str:
    if not name or "/" in name or "\\" in name or name in (".", ".."):
        raise ValueError("Folder names can't contain / or \\.")
    p = Path(path).expanduser() / name
    if not allowed(str(p)):
        raise ValueError("Not allowed here (DOWNLOAD_ROOTS).")
    p.mkdir(parents=False, exist_ok=True)
    return str(p)


def check(dest: str, files: list[dict[str, Any]]) -> list[bool]:
    """For each {folder, name, size}: is it in dest, complete?"""
    out = []
    for f in files:
        p = Path(dest) / str(f.get("folder") or "") / Path(str(f.get("name") or "")).name
        out.append(p.is_file() and (not f.get("size") or p.stat().st_size == int(f["size"])))
    return out
