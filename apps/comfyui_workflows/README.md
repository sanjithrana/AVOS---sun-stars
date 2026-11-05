# ComfyUI workflows (your own GPU server)

Two ways AVOS uses ComfyUI:

1. **The open models from the Models page** (Z-Image, Qwen-Image, FLUX, Wan 2.2, LTX-2.3, Wan VACE, LongCat Avatar,
   InfiniteTalk, Wan 2.2 Animate, SCAIL-2): one workflow file per model, named after the model id. When the file is
   here and `COMFYUI_URL` points at your GPU server, that model runs there (free per call) instead of on fal.ai.
2. **The older "ComfyUI (your own GPU)" video choice**: a single `video.json` (section further down).

## The quick way (v16)

1. `apps\tools\setup-comfyui.bat` installs ComfyUI portable next to AVOS and points it at `apps\models` (the folder the
   Models page downloads into).
2. Start it: `apps\tools\start-gpu.bat` (NVIDIA card: ComfyUI + the GPU worker in Docker) or
   `apps\tools\start-cpu.bat` (no NVIDIA card: ComfyUI `--cpu` + the worker; slow, free; grow the page file first with
   `tools\set-pagefile.ps1` for models bigger than your RAM). Add `http://host.docker.internal:8700` on the GPU page.
3. In ComfyUI open the model's template, run it once, **Workflow → Export (API)**, and upload the file on the Settings
   page (Models → the model → Upload workflow). **No placeholders to type**: AVOS finds the positive prompt (following the
   sampler's links), the negative prompt, Load Image / Audio / Video, seeds, width / height, frame counts, frame rates
   and the diffusion model's weight dtype, puts its placeholders there (`agentic_core/models/comfy_autowire.py`) and
   sends the workflow to every GPU worker. Placeholders you typed yourself are kept as they are.

## Per-model workflows

Your laptop (Intel Iris Xe) can't run these. Rent a GPU (RunPod, Vast.ai, Lambda: an A100 80 GB or H100 runs all of
them; a 24 GB card runs the image models and Wan 2.2 with fp8 weights), install ComfyUI there, start it with
`--listen`, and set in `apps/.env`:

```
COMFYUI_URL=http://<gpu server ip>:8188
STUDIO_COMFYUI_URL=http://<gpu server ip>:8188   # the Animations tab too
```

For each model you want on your server: open the workflow in ComfyUI, run it once, then **Workflow → Export (API)**
and upload it on the Settings page (or save it here under this name; plain exports are auto-wired). The placeholders
each model gets:

| File | Model | Where to get the workflow | Placeholders it needs |
|---|---|---|---|
| `z-image.json` | Z-Image Turbo | Templates → Image → Z-Image Turbo | `{{PROMPT}}` `{{SEED}}` `{{WIDTH}}` `{{HEIGHT}}` (`{{STEPS}}` optional, 8) |
| `qwen-image.json` | Qwen-Image | Templates → Image → Qwen-Image | same as above (`{{STEPS}}` 30, `{{NEGATIVE_PROMPT}}`) |
| `flux-schnell.json` | FLUX.1 schnell | Templates → Image → Flux Schnell | same as above (`{{STEPS}}` 4) |
| `wan-2.2.json` | Wan 2.2 I2V A14B | Templates → Video → Wan 2.2 14B Image to Video | `{{PROMPT}}` `{{IMAGE}}` `{{SEED}}` `{{FRAMES}}` (16 fps, 4k+1) `{{WIDTH}}` `{{HEIGHT}}` |
| `ltx-2.3.json` | LTX-2.3 | LTXVideo nodes (Lightricks/ComfyUI-LTXVideo) image-to-video or audio-to-video example | `{{PROMPT}}` `{{IMAGE}}` `{{FRAMES}}` (25 fps, 8k+1); add `{{AUDIO}}` in a Load Audio node to follow the narration |
| `wan-vace.json` | Wan VACE 14B | Templates → Video → Wan VACE | `{{PROMPT}}` `{{IMAGE}}` (reference) `{{FRAMES}}`; `{{VIDEO}}` for depth/pose control |
| `longcat-avatar.json` | LongCat Avatar 1.5 | LongCat-Video-Avatar ComfyUI nodes (community) | `{{IMAGE}}` (presenter) `{{AUDIO}}` (narration) `{{PROMPT}}` `{{FRAMES}}` (25 fps) |
| `infinitetalk.json` | InfiniteTalk | kijai ComfyUI-WanVideoWrapper → InfiniteTalk example | `{{IMAGE}}` `{{AUDIO}}` `{{PROMPT}}` `{{FRAMES}}` (25 fps, 4k+1) |
| `wan-2.2-animate.json` | Wan 2.2 Animate | Templates → Video → Wan 2.2 Animate | `{{IMAGE}}` (character) `{{VIDEO}}` (driving video) `{{PROMPT}}` `{{FRAMES}}` |
| `scail-2.json` | SCAIL-2 | zai-org/SCAIL-2 ComfyUI nodes | `{{IMAGE}}` `{{VIDEO}}` `{{PROMPT}}` |
| `qwen-image-edit.json` | Qwen-Image-Edit 2511 (Series: character sheets, keyframes) | Templates → Image → Qwen Image Edit 2511 (`image_qwen_image_edit_2511`); add a third Load Image | `{{PROMPT}}` `{{SEED}}` and up to three reference pictures `{{IMAGE}}` `{{IMAGE2}}` `{{IMAGE3}}` (character sheets, then the location); `{{WIDTH}}` `{{HEIGHT}}` in the empty-latent node |
| `ace-step.json` | ACE-Step 1.5 (Series: music) | Templates → Audio → ACE-Step 1.5 (`audio_ace_step_1_5_checkpoint`) | `{{PROMPT}}` in the tags, `{{LYRICS}}` in the lyrics (`[instrumental]` is sent), `{{DURATION}}` (seconds), `{{SEED}}`; ends with **Save Audio** |

Series voices (Chatterbox, IndicF5, Indic Parler-TTS) and sound effects (HunyuanVideo-Foley) don't need workflows:
they run in the GPU worker's own `speech` and `foley` backends (see `apps/gpu_worker/README.md`).

How the placeholders are filled:

- `{{IMAGE}}`, `{{IMAGE2}}`, `{{IMAGE3}}`, `{{AUDIO}}`, `{{VIDEO}}`: AVOS uploads the file to ComfyUI's input folder
  and puts its name there. Use them in **Load Image**, **Load Audio** and **Load Video** (VideoHelperSuite) nodes.
- `{{LYRICS}}` and `{{LANGUAGE}}` are text, like `{{PROMPT}}`.
- `{{SEED}}`, `{{WIDTH}}`, `{{HEIGHT}}`, `{{FRAMES}}`, `{{FPS}}`, `{{STEPS}}`, `{{DURATION}}` become numbers. ComfyUI's
  screen only accepts numbers in those fields, so edit the exported file: `"seed": 42` → `"seed": "{{SEED}}"`.
- `{{PROMPT}}` / `{{NEGATIVE_PROMPT}}` can sit inside longer text.

Image workflows end with **Save Image**; video workflows with **Save Video** (MP4) or VideoHelperSuite **Video
Combine** (`video/h264-mp4`); music workflows with **Save Audio** (FLAC / MP3 / WAV).

The Models page (sidebar) shows, for each model, whether it will run on your server, on fal.ai, or what's missing.
`MODEL_BACKEND=fal` or `MODEL_BACKEND=comfyui` in `apps/.env` forces one backend for every model.

Vista4D (re-shooting a video from a new camera path) has no ComfyUI nodes or hosted API yet; it's listed on the Models
page for reference only.

---

# The single video workflow (video provider "comfyui")

AVOS sends each shot to your own ComfyUI server and gets a clip back.
It needs one workflow file here: `video.json`.

## 1. Run ComfyUI with a video model

Install ComfyUI (or ComfyUI Desktop) on the PC with the NVIDIA GPU, then
open **Workflow → Browse Templates → Video** and pick an image-to-video
template, for example:

| Template | Model | GPU memory |
|---|---|---|
| LTXV Image to Video | LTX-Video 2B | about 8–12 GB, fastest |
| Wan 2.2 5B Image to Video | Wan 2.2 TI2V 5B | about 8–12 GB |
| Wan 2.1 / 2.2 14B Image to Video | Wan 14B | 16–24 GB, best quality, slow |

Let ComfyUI download the model files it asks for, then press **Run**
once with any image and prompt to be sure it works.

## 2. Put in the placeholders

In that workflow, type these exactly (including the braces) into the fields:

| Field | Type this |
|---|---|
| positive prompt text | `{{PROMPT}}` |
| **Load Image** → image | `{{IMAGE}}` |
| sampler / noise **seed** | `{{SEED}}` |
| **length** / frame count | `{{FRAMES}}` |
| width / height (optional) | `{{WIDTH}}` / `{{HEIGHT}}` |
| frame rate (optional) | `{{FPS}}` |
| negative prompt (optional) | `{{NEGATIVE_PROMPT}}` |

Number fields (seed, length, width...) only accept numbers in the
ComfyUI screen. Put those placeholders in after exporting (step 3): open
`video.json` in a text editor and replace the number with the quoted
placeholder, e.g. `"seed": 42` becomes `"seed": "{{SEED}}"` and
`"length": 97` becomes `"length": "{{FRAMES}}"`.

The workflow must end with a node that saves **MP4 or WebM**: core
**Save Video**, or VideoHelperSuite **Video Combine** with format
`video/h264-mp4`. Animated WebP/GIF savers won't work.

## 3. Export

**Workflow → Export (API)** and save the file as `video.json` in this
folder (`apps/comfyui_workflows/video.json`).

## 4. Settings (apps/.env)

```
COMFYUI_URL=http://host.docker.internal:8188
# LTX-Video wants 8k+1 frames; Wan wants 4k+1:
COMFYUI_FRAME_MULTIPLE=8
COMFYUI_FPS=24
COMFYUI_MAX_FRAMES=121
```

Then `docker compose up -d` and create a project with the video
provider **ComfyUI (your own GPU)**.

`host.docker.internal` is how the Docker containers reach ComfyUI
running on the same Windows/Mac machine. If ComfyUI runs on another PC,
start it with `--listen` and use that PC's IP.
