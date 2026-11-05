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


def load_plate(p: Path | None):
    if not p or not Path(p).exists():
        return None
    import skia
    try:
        return skia.Image.open(str(p))
    except Exception:
        return None


__all__ = ["images_status", "plate_prompt", "generate_plate", "load_plate", "config"]
