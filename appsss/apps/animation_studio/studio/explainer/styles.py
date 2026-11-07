"""Look presets. A style is a sentence added to every picture prompt (characters, set, storyboard), so the whole video keeps one look."""
from __future__ import annotations

STYLES: list[dict] = [
    {"id": "auto", "name": "Auto", "prompt": ""},
    {"id": "3d", "name": "3D animated", "prompt": "3D animated look, glossy Pixar-like render, soft studio lighting, saturated colours, shallow depth of field, clean background"},
    {"id": "cinematic", "name": "Cinematic", "prompt": "cinematic film still, dramatic soft lighting, shallow depth of field, rich colour grade, realistic materials"},
    {"id": "photoreal", "name": "Photorealistic", "prompt": "photorealistic, natural light, real-life documentary photography, sharp detail"},
    {"id": "doc70", "name": "70s documentary", "prompt": "1970s documentary film look, grainy 16mm film, warm faded colours, soft vignette"},
    {"id": "anime", "name": "Anime", "prompt": "anime style, clean line art, vivid cel shading, expressive eyes, detailed painted backgrounds"},
    {"id": "chalk", "name": "Chalkboard", "prompt": "white chalk drawing on a dark green chalkboard, hand-drawn diagrams, simple clear shapes"},
    {"id": "ink", "name": "Brush ink", "prompt": "hand-painted brush ink illustration, watercolour washes, bold black ink outlines, paper texture"},
    {"id": "cgi", "name": "Scientific CGI", "prompt": "clean scientific 3D visualisation, translucent materials, glowing labels-free diagrams, dark gradient background"},
]


def prompt_for(style_id: str | None) -> str:
    return next((s["prompt"] for s in STYLES if s["id"] == (style_id or "auto")), "")
