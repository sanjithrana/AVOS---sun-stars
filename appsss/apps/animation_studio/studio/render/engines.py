"""The seven 2D drawing engines of ReelMimic, as looks for the built-in renderer.

ReelMimic hands each style to a production skill (HyperFrames, painted-animation, crayon-storybook, pixel-art,
paper-cutout, whiteboard, anime-cel). Here every engine is a set of drawing rules (line, fill, texture, frame rate)
that the same scene renderer applies, so a plan made for one engine renders in any of them.
"""
from __future__ import annotations

ENGINES: dict[str, dict] = {
    "hyperframes": {"label": "Vector / motion graphics", "look": "vector", "step": 1, "line": True, "lw": 1.0, "jitter": 0.0,
                    "fill": "flat", "font": "baloo-2", "title_font": "anton", "post": ["vignette_soft"]},
    "painted-animation": {"label": "Hand-painted watercolor", "look": "watercolor", "step": 2, "line": True, "lw": 0.75, "jitter": 1.0,
                          "fill": "wash", "font": "caveat", "title_font": "caveat", "post": ["paper", "bleed"]},
    "crayon-storybook": {"label": "Crayon picture book", "look": "crayon", "step": 2, "line": True, "lw": 1.25, "jitter": 1.3,
                         "fill": "crayon", "font": "baloo-2", "title_font": "baloo-2", "post": ["crayon", "paper"]},
    "pixel-art": {"label": "Pixel art", "look": "pixel", "step": 2, "line": True, "lw": 1.0, "jitter": 0.0, "fill": "flat",
                  "font": "chakra-petch", "title_font": "chakra-petch", "post": ["pixel"], "pixel_h": 180},
    "paper-cutout": {"label": "Paper cut-out stop-motion", "look": "paper", "step": 2, "line": False, "lw": 0.0, "jitter": 0.0,
                     "fill": "paper", "font": "baloo-2", "title_font": "bangers", "post": ["fiber"]},
    "whiteboard": {"label": "Whiteboard doodle", "look": "whiteboard", "step": 1, "line": True, "lw": 1.15, "jitter": 0.35,
                   "fill": "line_only", "font": "caveat", "title_font": "caveat", "post": [], "reveal": True},
    "anime-cel": {"label": "Anime cel", "look": "cel", "step": 1, "line": True, "lw": 1.35, "jitter": 0.0, "fill": "cel",
                  "font": "baloo-2", "title_font": "bangers", "post": ["bloom", "vignette_soft"]},
}
ALIASES = {"remotion-best-practices": "hyperframes", "hyperframes-animation": "hyperframes", "motion-graphics": "hyperframes",
           "blender-product-film": "hyperframes", "faceless-explainer": "hyperframes", "music-to-video": "hyperframes",
           "product-launch-video": "hyperframes", "slideshow": "hyperframes", "general-video": "hyperframes"}
MEDIUM_ENGINE = {"2d-painted": "painted-animation", "2d-crayon": "crayon-storybook", "2d-vector": "hyperframes",
                 "2d-pixel": "pixel-art", "2d-paper": "paper-cutout", "2d-lineart": "whiteboard", "2d-cel": "anime-cel"}


def resolve(engine: str | None) -> str:
    e = (engine or "hyperframes").strip()
    if e in ENGINES:
        return e
    return ALIASES.get(e, "hyperframes")


def look(engine: str | None) -> dict:
    eid = resolve(engine)
    return {"id": eid, **ENGINES[eid]}


def engine_label(engine: str | None) -> str:
    if not engine:
        return ""
    eid = resolve(engine)
    lab = ENGINES[eid]["label"]
    return lab if eid == engine else f"{lab} (for {engine})"


def engine_snapshot(engine: str | None) -> dict:
    return look(engine)
