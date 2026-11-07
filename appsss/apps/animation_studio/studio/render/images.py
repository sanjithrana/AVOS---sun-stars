"""Optional AI background plates (Settings → Pictures: "AI images").

AI settings → "Image model" picks the model: an open model from the shared AVOS catalog (best / Z-Image / Qwen-Image /
FLUX.1 schnell, on your GPU server or fal.ai, see studio/models.py) or, by default, the free chain. The free chain
(also the fallback when the chosen model fails) uses the same free providers as the Facts tab: Cloudflare Workers AI (CLOUDFLARE_ACCOUNT_ID + CLOUDFLARE_API_TOKEN),
then Pollinations (no key), then a self-hosted Automatic1111-compatible server (IMAGE_SERVICE_URL). Characters are
always drawn by the rig, so they stay identical in every shot; only the backdrop is generated.
"""
from __future__ import annotations

import base64
import hashlib
import os
import urllib.parse
from pathlib import Path

import httpx

from .. import config

LAST_ERROR: dict[str, str] = {}

STYLE_PROMPT = {
    "hyperframes": "flat vector illustration, clean shapes, bold colors, motion graphics background",
    "painted-animation": "hand-painted watercolor illustration, soft washes, paper texture, storybook",
    "crayon-storybook": "crayon and colored pencil children's picture book illustration, paper grain",
    "pixel-art": "16-bit pixel art background, limited palette, retro game",
    "paper-cutout": "layered paper cut-out craft diorama, construction paper, soft shadows",
    "whiteboard": "black marker line drawing on white background, simple doodle",
    "anime-cel": "anime background art, cel shaded, vivid sky, Makoto Shinkai inspired lighting",
}


def image_model() -> str:
    from .. import models
    m = (os.environ.get("STUDIO_IMAGE_MODEL") or "free").strip()
    return m if m in models.image_choices() else "free"


def images_status() -> tuple[bool, str]:
    from .. import models
    choice = image_model()
    if choice != "free":
        cands = models.route_image("") if choice == "best" else [choice]
        for mid in cands:
            ok, how = models.ready(mid)
            if ok:
                return True, f"{models.get(mid)['name']} on {how}" + (" (best model per picture)" if choice == "best" else "") + ", free chain as fallback"
        return True, f"{choice}: {models.ready(cands[0])[1]} Using the free chain until then."
    if os.environ.get("CLOUDFLARE_ACCOUNT_ID") and os.environ.get("CLOUDFLARE_API_TOKEN"):
        return True, "Cloudflare Workers AI (free tier), then Pollinations"
    if os.environ.get("IMAGE_SERVICE_URL"):
        return True, "Your own image server at " + os.environ["IMAGE_SERVICE_URL"]
    return True, "Pollinations (free, no key; can be slow or rate-limited). Add Cloudflare keys for a faster free option."


def plate_prompt(setting: str, time: str, engine: str, palette: list[str], extra: str = "") -> str:
    tod = {"night": "at night", "sunset": "at sunset", "day": "daytime"}.get(time, "")
    pal = ", ".join(palette[:4])
    return (f"empty {setting.replace('_', ' ')} scene {tod}, background only, no people, no characters, no text, "
            f"wide shot, eye level, ground visible at the bottom, {STYLE_PROMPT.get(engine, STYLE_PROMPT['hyperframes'])}, "
            f"color palette {pal}. {extra}").strip()


def generate_plate(prompt: str, out: Path, w: int = 1280, h: int = 720, timeout: float = 90) -> Path | None:
    """Best effort: returns the saved image or None (the engine then draws the backdrop itself)."""
    if out.exists():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    data = None
    choice = image_model()
    if choice != "free":
        from .. import models
        seed = int(hashlib.md5(prompt.encode()).hexdigest()[:6], 16)
        for mid in (models.route_image(prompt) if choice == "best" else [choice]):
            if not models.ready(mid)[0]:
                continue
            try:
                data = models.image(mid, prompt, w, h, seed)
                break
            except Exception as e:   # next model, then the free chain
                LAST_ERROR[str(out)] = (LAST_ERROR.get(str(out), "") + f" {mid}: {e};").strip()
    acc, tok = os.environ.get("CLOUDFLARE_ACCOUNT_ID"), os.environ.get("CLOUDFLARE_API_TOKEN")
    if data is None and acc and tok:
        try:
            model = os.environ.get("CLOUDFLARE_IMAGE_MODEL") or "@cf/black-forest-labs/flux-1-schnell"
            r = httpx.post(f"https://api.cloudflare.com/client/v4/accounts/{acc}/ai/run/{model}", headers={"Authorization": f"Bearer {tok}"},
                           json={"prompt": prompt[:2000], "steps": 6}, timeout=timeout)
            if r.status_code == 200:
                j = r.json()
                img = (j.get("result") or {}).get("image")
                if img:
                    data = base64.b64decode(img)
        except Exception:
            data = None
    if data is None and os.environ.get("IMAGE_SERVICE_URL"):
        try:
            r = httpx.post(os.environ["IMAGE_SERVICE_URL"].rstrip("/") + "/sdapi/v1/txt2img",
                           json={"prompt": prompt, "width": min(w, 1024), "height": min(h, 576), "steps": 20}, timeout=timeout * 3)
            if r.status_code == 200 and r.json().get("images"):
                data = base64.b64decode(r.json()["images"][0])
        except Exception:
            data = None
    if data is None:
        try:
            seed = int(hashlib.md5(prompt.encode()).hexdigest()[:6], 16)
            url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt[:900])}?width={w}&height={h}&nologo=true&seed={seed}"
            r = httpx.get(url, timeout=timeout, follow_redirects=True)
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("image"):
                data = r.content
        except Exception:
            data = None
    if not data:
        return None
    out.write_bytes(data)
    return out


# ---------------------------------------------------------------------------------------------------------------------
# The free picture chain for the studios: honours the SEED and the SIZE (the plate chain above does not), and can look at
# up to four REFERENCE pictures (a character portrait, a prop, the set) through Cloudflare's FLUX.2 [klein] on the free tier.
# ---------------------------------------------------------------------------------------------------------------------
CF_REF_MODEL = "@cf/black-forest-labs/flux-2-klein-9b"
LAST_FREE: dict[str, str] = {}


def cloudflare_ready() -> bool:
    return bool(os.environ.get("CLOUDFLARE_ACCOUNT_ID") and os.environ.get("CLOUDFLARE_API_TOKEN"))


def _small_png(data: bytes, side: int = 500) -> bytes:
    """A reference must be smaller than 512x512 for FLUX.2 [klein]."""
    import io
    from PIL import Image
    im = Image.open(io.BytesIO(data)).convert("RGB")
    im.thumbnail((side, side))
    out = io.BytesIO()
    im.save(out, "PNG")
    return out.getvalue()


def _cf_image(r: httpx.Response) -> bytes | None:
    if r.status_code != 200:
        LAST_FREE["cloudflare"] = f"HTTP {r.status_code}: {r.text[:200]}"
        return None
    if r.headers.get("content-type", "").startswith("image/"):
        return r.content
    try:
        j = r.json()
    except ValueError:
        return None
    img = (j.get("result") or {}).get("image") if isinstance(j, dict) else None
    return base64.b64decode(img) if img else None


def cloudflare_flux2(prompt: str, w: int, h: int, seed: int, refs: list[bytes] | None = None, timeout: float = 120) -> bytes | None:
    """FLUX.2 [klein] on Cloudflare Workers AI: text to picture, or picture FROM up to four reference pictures."""
    acc, tok = os.environ.get("CLOUDFLARE_ACCOUNT_ID"), os.environ.get("CLOUDFLARE_API_TOKEN")
    if not (acc and tok):
        return None
    model = os.environ.get("CLOUDFLARE_REF_MODEL") or CF_REF_MODEL
    k = min(1.0, 1920 / max(w, h))
    W, H = max(256, int(w * k) // 16 * 16), max(256, int(h * k) // 16 * 16)
    files: dict = {}
    for i, b in enumerate((refs or [])[:4]):
        try:
            files[f"input_image_{i}"] = (f"ref{i}.png", _small_png(b), "image/png")
        except Exception:  # noqa: BLE001 - an unreadable reference is skipped
            continue
    parts = {"prompt": (None, prompt[:2000]), "width": (None, str(W)), "height": (None, str(H)), "seed": (None, str(int(seed) % 2_147_483_647)), **files}
    try:                                                # always multipart/form-data, even without pictures (the model requires it)
        r = httpx.post(f"https://api.cloudflare.com/client/v4/accounts/{acc}/ai/run/{model}", headers={"Authorization": f"Bearer {tok}"},
                       files=parts, timeout=timeout)
        return _cf_image(r)
    except Exception as e:  # noqa: BLE001
        LAST_FREE["cloudflare"] = str(e)[:200]
        return None


def free_picture(prompt: str, w: int, h: int, seed: int, refs: list[bytes] | None = None, timeout: float = 120) -> tuple[bytes, str] | None:
    """(picture, which service) from the free chain, or None. With refs, only a service that really looks at them is used."""
    if cloudflare_ready():
        img = cloudflare_flux2(prompt, w, h, seed, refs, timeout)
        if img:
            return img, ("Cloudflare FLUX.2 klein (from references)" if refs else "Cloudflare FLUX.2 klein")
        if not refs:
            acc, tok = os.environ["CLOUDFLARE_ACCOUNT_ID"], os.environ["CLOUDFLARE_API_TOKEN"]
            try:
                r = httpx.post(f"https://api.cloudflare.com/client/v4/accounts/{acc}/ai/run/@cf/black-forest-labs/flux-1-schnell",
                               headers={"Authorization": f"Bearer {tok}"}, json={"prompt": prompt[:2000], "steps": 6, "seed": int(seed) % 2_147_483_647}, timeout=timeout)
                img = _cf_image(r)
                if img:
                    return img, "Cloudflare FLUX.1 schnell"
            except Exception as e:  # noqa: BLE001
                LAST_FREE["cloudflare"] = str(e)[:200]
    if refs:
        return None
    try:
        url = (f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt[:900])}?width={w}&height={h}&nologo=true"
               f"&seed={int(seed) % 2_147_483_647}&model=flux")
        r = httpx.get(url, timeout=timeout, follow_redirects=True)
        if r.status_code == 200 and r.headers.get("content-type", "").startswith("image"):
            return r.content, "Pollinations"
        LAST_FREE["pollinations"] = f"HTTP {r.status_code}"
    except Exception as e:  # noqa: BLE001
        LAST_FREE["pollinations"] = str(e)[:200]
    return None


def load_plate(p: Path | None):
    if not p or not Path(p).exists():
        return None
    import skia
    try:
        return skia.Image.open(str(p))
    except Exception:
        return None


__all__ = ["images_status", "plate_prompt", "generate_plate", "free_picture", "cloudflare_ready", "load_plate", "config"]
