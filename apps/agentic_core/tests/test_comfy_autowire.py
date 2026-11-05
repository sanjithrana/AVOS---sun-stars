"""Auto-wiring a plain ComfyUI API export: AVOS's placeholders go where the graph says, links are never touched."""
from pathlib import Path

from agentic_core.models.comfy_autowire import autowire, describe, needs_wiring

ROOT = Path(__file__).resolve().parents[2]

LTX = {
    "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "ltx.safetensors", "weight_dtype": "fp8_e4m3fn"}},
    "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "gemma.safetensors", "type": "ltxv"}},
    "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "a wolf drives a red car", "clip": ["2", 0]}},
    "4": {"class_type": "CLIPTextEncode", "inputs": {"text": "blurry, low quality", "clip": ["2", 0]}},
    "5": {"class_type": "LoadImage", "inputs": {"image": "start.png"}},
    "6": {"class_type": "LTXVImgToVideo", "inputs": {"positive": ["3", 0], "negative": ["4", 0], "vae": ["9", 0], "image": ["5", 0],
                                                    "width": 768, "height": 512, "length": 97, "batch_size": 1}},
    "7": {"class_type": "LTXVConditioning", "inputs": {"positive": ["6", 0], "negative": ["6", 1], "frame_rate": 25}},
    "8": {"class_type": "SamplerCustom", "inputs": {"model": ["1", 0], "positive": ["7", 0], "negative": ["7", 1], "noise_seed": 42,
                                                   "cfg": 3, "latent_image": ["6", 2]}},
    "10": {"class_type": "LoadAudio", "inputs": {"audio": "line.wav"}},
    "11": {"class_type": "CreateVideo", "inputs": {"images": ["8", 0], "fps": 25}},
}


def test_an_ltx_export_is_wired_through_the_conditioning_nodes():
    w, r = autowire(LTX)
    i = {k: v["inputs"] for k, v in w.items()}
    assert i["3"]["text"] == "{{PROMPT}}" and i["4"]["text"] == "{{NEGATIVE_PROMPT}}"       # positive / negative kept apart
    assert i["5"]["image"] == "{{IMAGE}}" and i["10"]["audio"] == "{{AUDIO}}" and i["8"]["noise_seed"] == "{{SEED}}"
    assert (i["6"]["width"], i["6"]["height"], i["6"]["length"]) == ("{{WIDTH}}", "{{HEIGHT}}", "{{FRAMES}}")
    assert i["7"]["frame_rate"] == "{{FPS}}" and i["11"]["fps"] == "{{FPS}}" and i["1"]["weight_dtype"] == "{{WEIGHT_DTYPE}}"
    assert i["6"]["batch_size"] == 1 and i["8"]["positive"] == ["7", 0] and LTX["3"]["inputs"]["text"].startswith("a wolf")
    assert needs_wiring(LTX) and not needs_wiring(w) and "{{PROMPT}} → 3 CLIPTextEncode.text" in describe(r)


def test_without_a_sampler_the_longest_text_is_the_prompt_and_extra_images_are_numbered():
    wf = {"1": {"class_type": "TextEncodeQwenImageEditPlus", "inputs": {"prompt": "make the sofa red, keep everything else"}},
          "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "x"}},
          "3": {"class_type": "LoadImage", "inputs": {"image": "a.png"}}, "4": {"class_type": "LoadImage", "inputs": {"image": "b.png"}},
          "5": {"class_type": "LoadImageMask", "inputs": {"image": "m.png"}}}
    w, _ = autowire(wf)
    assert w["1"]["inputs"]["prompt"] == "{{PROMPT}}" and w["2"]["inputs"]["text"] == "x"
    assert (w["3"]["inputs"]["image"], w["4"]["inputs"]["image"], w["5"]["inputs"]["image"]) == ("{{IMAGE}}", "{{IMAGE2}}", "m.png")


def test_the_worker_has_an_identical_copy():
    assert (ROOT / "agentic_core/models/comfy_autowire.py").read_text() == (ROOT / "gpu_worker/worker/autowire.py").read_text()
