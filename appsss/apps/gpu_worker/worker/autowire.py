"""Auto-wire a ComfyUI workflow exported with Workflow → Export (API): put AVOS's placeholders into it, so you don't
have to type {{PROMPT}} / {{IMAGE}} / {{SEED}} … into ComfyUI before exporting.

    wired, report = autowire(workflow)

What is found, following the graph (not node titles):
    the positive / negative text of every sampler or guider   → {{PROMPT}} / {{NEGATIVE_PROMPT}}
    LoadImage nodes (in id order)                             → {{IMAGE}}, {{IMAGE2}}, {{IMAGE3}}, {{IMAGE4}}
    LoadAudio / LoadVideo (and VHS loaders)                   → {{AUDIO}} / {{VIDEO}}
    seed / noise_seed                                         → {{SEED}}
    width + height on the same node (latents, image-to-video) → {{WIDTH}} / {{HEIGHT}}
    length / num_frames / frames / video_length / frame_count → {{FRAMES}}
    frame_rate / fps                                          → {{FPS}}
    weight_dtype of a Load Diffusion Model                    → {{WEIGHT_DTYPE}}
Values that are links ([node, output]) are never touched; a workflow that already has placeholders is left as is.
An identical copy lives in gpu_worker/worker/autowire.py (the worker wires files dropped into its workflows folder).
"""
from __future__ import annotations

import copy
from typing import Any

TEXT_KEYS = ("text", "prompt", "positive_prompt", "text_g", "text_l")
SEED_KEYS = ("seed", "noise_seed")
FRAME_KEYS = ("length", "num_frames", "frames", "video_length", "frame_count", "frames_number")
FPS_KEYS = ("frame_rate", "fps")
ALREADY = ("{{PROMPT}}", "{{IMAGE}}", "{{SEED}}", "{{FRAMES}}", "{{WIDTH}}")


def _is_link(v: Any) -> bool:
    return isinstance(v, list) and len(v) == 2 and isinstance(v[0], (str, int)) and isinstance(v[1], int)


def _nodes(wf: dict) -> dict[str, dict]:
    return {str(k): v for k, v in wf.items() if isinstance(v, dict) and "class_type" in v and isinstance(v.get("inputs"), dict)}


def _text_sources(nodes: dict[str, dict], start: Any, branch: str = "positive", seen: set[str] | None = None) -> list[str]:
    """Follow a conditioning link upstream to the text-encode nodes that write the prompt. Through nodes that carry
    both (e.g. LTXVConditioning, a guider) only the same branch (positive / negative) is followed."""
    seen = seen if seen is not None else set()
    if not _is_link(start):
        return []
    nid = str(start[0])
    if nid in seen or nid not in nodes:
        return []
    seen.add(nid)
    n = nodes[nid]
    if any(isinstance(n["inputs"].get(k), str) for k in TEXT_KEYS) and "encode" in n["class_type"].lower():
        return [nid]
    ins = n["inputs"]
    if _is_link(ins.get("positive")) or _is_link(ins.get("negative")):
        return _text_sources(nodes, ins.get(branch), branch, seen)
    out: list[str] = []
    for k, v in ins.items():
        if _is_link(v) and k not in ("clip", "model", "vae", "image", "pixels", "latent", "samples", "latent_image", "audio", "video"):
            out += _text_sources(nodes, v, branch, seen)
    return out


def needs_wiring(wf: dict) -> bool:
    import json
    text = json.dumps(wf)
    return not any(p in text for p in ALREADY)


def autowire(wf: dict) -> tuple[dict, dict[str, list[str]]]:
    """A copy of the workflow with AVOS placeholders, and a report {placeholder: ["<node id> <class>.<input>"]}."""
    wf = copy.deepcopy(wf)
    nodes = _nodes(wf)
    report: dict[str, list[str]] = {}

    def put(nid: str, key: str, ph: str) -> None:
        nodes[nid]["inputs"][key] = ph
        report.setdefault(ph, []).append(f"{nid} {nodes[nid]['class_type']}.{key}")

    order = sorted(nodes, key=lambda x: (len(x), x))
    pos: list[str] = []
    neg: list[str] = []
    for nid in order:
        ins = nodes[nid]["inputs"]
        for key in ("positive", "conditioning", "cond"):
            pos += _text_sources(nodes, ins.get(key), "positive")
        for key in ("negative", "uncond"):
            neg += _text_sources(nodes, ins.get(key), "negative")
    neg = [x for x in dict.fromkeys(neg) if x not in pos]
    pos = list(dict.fromkeys(pos))
    if not pos:                       # no sampler wiring found: the encode node with the longest text is the prompt
        enc = [nid for nid in order if "encode" in nodes[nid]["class_type"].lower()
               and any(isinstance(nodes[nid]["inputs"].get(k), str) for k in TEXT_KEYS)]
        enc.sort(key=lambda nid: -max(len(nodes[nid]["inputs"].get(k) or "") for k in TEXT_KEYS if isinstance(nodes[nid]["inputs"].get(k), str)))
        pos = enc[:1]
    for nid in pos:
        key = next(k for k in TEXT_KEYS if isinstance(nodes[nid]["inputs"].get(k), str))
        put(nid, key, "{{PROMPT}}")
    for nid in neg:
        key = next(k for k in TEXT_KEYS if isinstance(nodes[nid]["inputs"].get(k), str))
        put(nid, key, "{{NEGATIVE_PROMPT}}")

    images = ["{{IMAGE}}", "{{IMAGE2}}", "{{IMAGE3}}", "{{IMAGE4}}"]
    for nid in order:
        n = nodes[nid]
        ct, ins = n["class_type"].lower(), n["inputs"]
        if ct.startswith("loadimage") and isinstance(ins.get("image"), str) and "mask" not in ct and images:
            put(nid, "image", images.pop(0))
        elif "loadaudio" in ct or ct in ("vhs_loadaudio", "vhs_loadaudioupload"):
            key = next((k for k in ("audio", "audio_file", "file") if isinstance(ins.get(k), str)), None)
            if key and "{{AUDIO}}" not in report:
                put(nid, key, "{{AUDIO}}")
        elif "loadvideo" in ct:
            key = next((k for k in ("video", "file") if isinstance(ins.get(k), str)), None)
            if key and "{{VIDEO}}" not in report:
                put(nid, key, "{{VIDEO}}")
        for key in SEED_KEYS:
            if isinstance(ins.get(key), int) and not isinstance(ins.get(key), bool):
                put(nid, key, "{{SEED}}")
        if isinstance(ins.get("width"), int) and isinstance(ins.get("height"), int) and "upscale" not in ct and "resize" not in ct:
            put(nid, "width", "{{WIDTH}}")
            put(nid, "height", "{{HEIGHT}}")
        for key in FRAME_KEYS:
            if isinstance(ins.get(key), int) and not isinstance(ins.get(key), bool) and ins[key] > 1:
                put(nid, key, "{{FRAMES}}")
        for key in FPS_KEYS:
            if isinstance(ins.get(key), (int, float)) and not isinstance(ins.get(key), bool):
                put(nid, key, "{{FPS}}")
        if ct in ("unetloader", "loaddiffusionmodel") and ins.get("weight_dtype") in ("default", "fp8_e4m3fn", "fp8_e4m3fn_fast", "fp8_e5m2"):
            put(nid, "weight_dtype", "{{WEIGHT_DTYPE}}")
    return wf, report


def describe(report: dict[str, list[str]]) -> str:
    return "; ".join(f"{ph} → {', '.join(v)}" for ph, v in report.items()) or "nothing found"
