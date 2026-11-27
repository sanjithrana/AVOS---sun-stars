"""fal.ai queue API: submit a job, poll it, fetch the result, download files. Shared by every catalog model on fal.

Files (images, audio, video) are sent inline as data URIs, which fal accepts for any file input.
"""
from __future__ import annotations

import asyncio
import base64
import os
import time
from typing import Any

import httpx

QUEUE = os.getenv("FAL_QUEUE_URL", "https://queue.fal.run").rstrip("/")


class FalError(RuntimeError):
    pass


def data_uri(data: bytes, kind: str = "auto") -> str:
    mime = "application/octet-stream"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        mime = "image/png"
    elif data[:3] == b"\xff\xd8\xff":
        mime = "image/jpeg"
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        mime = "image/webp"
    elif data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        mime = "audio/wav"
    elif data[:3] == b"ID3" or data[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        mime = "audio/mpeg"
    elif data[4:8] == b"ftyp":
        mime = "video/mp4"
    elif data[:4] == b"\x1aE\xdf\xa3":
        mime = "video/webm"
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def _check(r: httpx.Response, doing: str, endpoint: str) -> None:
    if r.status_code < 400:
        return
    try:
        detail: Any = r.json()
        detail = detail.get("detail") or detail
    except ValueError:
        detail = r.text[:400]
    from agentic_core.models import provider_health as PH
    kind = PH.classify(r.status_code, r.text)
    if kind:
        PH.mark("fal", kind, r.text)       # skip fal.ai for a while: the router falls through to your GPU / free tiers
    hint = ""
    if r.status_code in (401, 403):
        hint = " Check FAL_KEY (fal.ai/dashboard/keys)."
    elif r.status_code == 402 or "balance" in str(detail).lower():
        hint = " Your fal.ai balance is empty: add credit at fal.ai/dashboard/billing."
    elif r.status_code == 422:
        hint = " The model rejected an input."
    raise FalError(f"fal.ai {endpoint}: error {r.status_code} while {doing}: {str(detail)[:400]}.{hint}")


async def run(endpoint: str, payload: dict[str, Any], *, key: str | None = None, timeout: float = 1200.0,
              poll: float = 4.0) -> dict[str, Any]:
    """Submit to the queue, wait for COMPLETED, return the result JSON."""
    key = key or os.getenv("FAL_KEY")
    if not key:
        raise FalError("FAL_KEY is not set (create one at fal.ai/dashboard/keys).")
    headers = {"Authorization": f"Key {key}"}
    endpoint = endpoint.strip("/")
    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as c:
        try:
            r = await c.post(f"{QUEUE}/{endpoint}", headers=headers, json=payload)
            _check(r, "starting the job", endpoint)
            job = r.json()
            rid = job.get("request_id")
            status_url = job.get("status_url") or f"{QUEUE}/{endpoint}/requests/{rid}/status"
            result_url = job.get("response_url") or f"{QUEUE}/{endpoint}/requests/{rid}"
            deadline = time.monotonic() + timeout
            while True:
                s = await c.get(status_url, headers=headers)
                _check(s, "checking the job", endpoint)
                state = s.json().get("status")
                if state == "COMPLETED":
                    break
                if state not in ("IN_QUEUE", "IN_PROGRESS"):
                    raise FalError(f"fal.ai {endpoint} returned status {state}: {s.text[:300]}")
                if time.monotonic() > deadline:
                    raise FalError(f"fal.ai {endpoint} did not finish within {timeout:.0f}s.")
                await asyncio.sleep(poll)
            res = await c.get(result_url, headers=headers)
            _check(res, "fetching the result", endpoint)
            return res.json()
        except httpx.ConnectError as exc:
            raise FalError(f"Could not reach fal.ai ({QUEUE}).") from exc


def first_url(result: dict[str, Any], *keys: str) -> str | None:
    """The first file URL under any of keys: {"video": {"url"}} / {"video": "url"} / {"images": [{"url"}]}."""
    for k in keys:
        v = result.get(k)
        if isinstance(v, str) and v.startswith(("http", "data:")):
            return v
        if isinstance(v, dict) and v.get("url"):
            return v["url"]
        if isinstance(v, list) and v:
            x = v[0]
            if isinstance(x, str):
                return x
            if isinstance(x, dict) and x.get("url"):
                return x["url"]
    return None


async def download(url: str) -> bytes:
    if url.startswith("data:"):
        return base64.b64decode(url.split(",", 1)[1])
    async with httpx.AsyncClient(timeout=300.0, follow_redirects=True) as c:
        r = await c.get(url)
        if r.status_code >= 400:
            raise FalError(f"Could not download the result ({r.status_code}).")
        return r.content
