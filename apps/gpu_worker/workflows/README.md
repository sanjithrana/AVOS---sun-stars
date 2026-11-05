# ComfyUI workflows for this worker

One API-format workflow per AVOS model, named `<model id>.json`, e.g. `wan-2.2.json`, `z-image.json`.
You can copy the files you already made for `apps/comfyui_workflows/`, they use the same placeholders.
Add `{{WEIGHT_DTYPE}}` to the *Load Diffusion Model* node's `weight_dtype` field to let the router choose
bf16 / fp8 per GPU. See ../README.md.
