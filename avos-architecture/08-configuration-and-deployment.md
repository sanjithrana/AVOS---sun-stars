# 8. Configuration and deployment

## Running it

```bat
cd apps
docker compose up -d --build        REM postgres, redis, temporal, temporal-ui, api, worker, animation-studio
cd desktop && npm install && npm run dev     REM UI on http://localhost:3000
```

- Optional Blender renderer: `docker compose --profile blender up -d blender` (only for old "Blender" projects).
- `start-animations.bat` / `.sh`: runs the Animation Studio without Docker (Python venv on :8020).
- Ollama runs on your PC (:11434); containers reach it as `host.docker.internal`.
- See `RUNBOOK.md` for day-to-day commands.

## Compose services and volumes

| Service | Image | Volumes / mounts |
|---|---|---|
| postgres | postgres:16 | `solunex_postgres_data` |
| redis | redis:7 | `solunex_redis_data` |
| object-store (profile `storage`) | chrislusf/seaweedfs | `avos_object_store` (S3 API :8333) |
| temporal / temporal-ui | temporalio/auto-setup, temporalio/ui | — |
| api | solunex-api | `solunex_assets` (`/data/assets`), `avos_settings` (`/data/settings`), `./comfyui_workflows`, music |
| worker | solunex-api | same as api |
| animation-studio | avos-animation-studio | `animation_projects` (`/data`), `avos_settings`, `catalog.json` (read-only), `./comfyui_workflows` |
| blender (profile `blender`) | solunex-blender | `blender_assets` |

## Settings precedence

```mermaid
flowchart LR
  env[apps/.env] --> proc[process environment]
  store[Settings page →<br/>/data/settings/avos.json<br/>(no Docker: apps/.avos/settings.json)] -->|overrides| proc
  proc --> api & worker & studio
```

- `settings_store.py` (copied as `animation_studio/studio/avos_settings.py`) loads the shared file into the
  environment on every read; a value saved in Settings wins over `.env`; clearing it restores the `.env` value.
- The file holds: keys (any name), GPU server (`COMFYUI_URL`, `MODEL_BACKEND`), your models, and uploaded workflows
  live in `comfyui_workflows/`. `AVOS_SETTINGS_FILE` overrides its location.
- The API returns keys **masked** with their source (settings / .env). Never commit `.env` or the settings file.

## Environment variables (main ones)

| Variable | Used by | Meaning |
|---|---|---|
| `DATABASE_URL`, `REDIS_URL`, `TEMPORAL_HOST` | api, worker | Infrastructure |
| `ASSETS_STORAGE_PATH` | api, worker | Asset Registry folder |
| `OPENAI_API_KEY`, `GROQ_API_KEY`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | Facts text | Text models |
| `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN` | pictures | Free FLUX |
| `FAL_KEY`, `FAL_VIDEO_MODEL`, `<MODEL>_FAL_INPUT_JSON` | pictures, clips, finish | fal.ai |
| `REPLICATE_API_TOKEN`, `STABILITY_API_KEY` | pictures, clips | Paid APIs |
| `COMFYUI_URL`, `COMFYUI_WORKFLOW_DIR` | all | Your GPU server and its workflows |
| `MODEL_BACKEND` | all | `auto` (your GPUs first) · `gpu` · `fal` · `comfyui` |
| `GPU_WORKER_TOKEN` | all + workers | Shared secret for GPU workers |
| `GPU_JOB_TIMEOUT` | Facts | Seconds before a GPU job is cancelled (default 1800) |
| `IMAGE_SERVICE_URL`, `VIDEO_SERVICE_URL` | Facts | Your own services |
| `VIDEO_PROVIDER`, `TTS_PROVIDER` | Facts | Defaults (`edge` / `mock` for TTS) |
| `RENDER_SIZE`, `CAPTIONS`, `MUSIC` | final render | Output size (default Full HD by aspect), captions on/off, music on/off |
| `BLENDER_SERVICE_URL` | physics proxy | Real Blender instead of the mock |
| `OLLAMA_URL`, `STUDIO_OLLAMA_MODEL`, `STUDIO_OLLAMA_VISION_MODEL`, `STUDIO_DEFAULT_AGENT`, `STUDIO_BUILDERS`, `STUDIO_COMFYUI_URL` | Animation Studio | Crew and GPU |
| `STUDIO_PROJECTS`, `STUDIO_PORT`, `STUDIO_STYLES`, `STUDIO_SECRETS`, `STUDIO_QUALITY`, `STUDIO_IMAGES` | Animation Studio | Folders, port, quality |
| `NEXT_PUBLIC_API_URL`, `ANIMATION_STUDIO_URL` | desktop | Where the API / studio are |
| `VISUAL_CONCURRENCY`, `IMAGE_CANDIDATE_CONCURRENCY`, `RENDER_PARALLEL`, `FINISH_CONCURRENCY` | all | How much runs at once (shots, pictures per shot, render segments, AI finish shots) |
| `LLM_CACHE_TTL` | Facts | Seconds a text-model answer is reused (0 = off) |
| `ASSETS_STORAGE`, `S3_ENDPOINT`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_REGION` | api, worker | S3-compatible asset storage (`ASSETS_STORAGE=s3`) |
| `AVOS_MODELS_HOST_DIR` (→ `/models`), `DOWNLOAD_ROOTS`, `HF_TOKEN`, `HF_ENDPOINT` | api | Model downloads to this PC |
| `WORKER_MODELS_DIR` / `COMFYUI_DIR` | GPU worker | Where downloads land on the GPU machine |
| `LLAMACPP_URL`, `LLAMACPP_MODEL` | Facts, Animations | llama.cpp server (small GGUF text model) |
| `SERIES_CONCURRENCY`, `SERIES_EDIT_STEPS` | Animations (Series) | Shots at once (auto: 2 per online GPU worker); keyframe steps (empty = the workflow's) |
| `STUDIO_REASONING_EFFORT` | Animations | gpt-oss on Groq: `low` (default), `medium`, `high` |
| `SPEECH_MODELS`, `FOLEY_DIR`, `FOLEY_MODELS`, `FOLEY_SIZE`, `FOLEY_PYTHON` | GPU worker | Series voices and sound effects backends |

## Using GPU workers (recommended)

1. On each GPU machine (your RTX PC, a RunPod / Vast.ai pod, a cloud VM): copy `apps/gpu_worker`, then
   `pip install -r requirements.txt` and `python -m worker` (or `docker compose -f docker-compose.gpu.yml up -d`).
   Set `GPU_WORKER_TOKEN`, `WORKER_COST_PER_HOUR`, and the backends you installed (ComfyUI / Wan2GP / Diffusers).
2. In AVOS: Settings → API keys → `GPU_WORKER_TOKEN` (same value), then GPU page → Add a GPU worker (its URL, e.g.
   `https://<pod>-8700.proxy.runpod.net`). Test shows the GPU and what it can run; Send workflows copies the
   workflows uploaded in Settings.
3. Facts and Animations now route to the workers; the GPU page shows every run. Details: [10](10-model-fabric-and-gpu-workers.md).

`WORKER_MOCK=1 WORKER_ADAPTERS=mock` runs a worker with no GPU (stand-in output) to try it on any PC.

## Using a single GPU server (ComfyUI)

1. Rent a GPU (e.g. RunPod, 24–48 GB VRAM for Wan 2.2 / LTX-2.3) with a ComfyUI template; download the model files
   listed on the Models page into ComfyUI.
2. In ComfyUI, export each model's workflow in **API format**, put `{{PROMPT}}`, `{{IMAGE}}`, `{{SEED}}`… in it, and
   upload it in Settings (or save as `comfyui_workflows/<model id>.json`).
3. Settings → GPU server: paste the ComfyUI URL, **Test**, choose "Run models on: Auto / my GPU / fal.ai".
4. The Models page shows each model as ready on "your GPU"; Facts and Animations then use it free per call.

## Output quality

Final Facts render: 1080×1920 (9:16), 1920×1080 (16:9), 1080×1080 (1:1); H.264 `preset medium`, `crf 18`, AAC 192k.
New projects default to the best open picture model and best open video model.
