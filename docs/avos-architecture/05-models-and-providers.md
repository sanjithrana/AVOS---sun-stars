# 5. Models and providers

Everything that calls an AI model goes through a small provider interface, picked per project (Facts) or per setting
(Animations). All of them are in `apps/agentic_core/models` (Facts) and `apps/animation_studio/studio/models.py` +
`studio/llm` (Animations), and both read the same **model catalog** and **settings store**.

```mermaid
flowchart TB
  subgraph Choice
    proj[Project: llm_provider · image_provider · video_provider]
    anim[Animations AI settings: crew · backdrop model · AI finish]
  end
  proj --> F1[llm/factory.get_llm_provider]
  proj --> F2[image/factory.get_image_provider]
  proj --> F3[video/factory.get_video_provider]
  F2 & F3 --> cat[models/catalog.py<br/>catalog.json + your models]
  anim --> sm[studio/models.py]
  sm --> cat2[same catalog.json + same settings]
  cat --> be{backend_for(model)}
  be -->|Model Router: online worker, fits VRAM| workers[Your GPU workers · ComfyUI / Wan2GP / Diffusers]
  be -->|workflow exported + COMFYUI_URL| comfy[ComfyUI on your GPU · free per call]
  be -->|FLUX + Cloudflare keys| cf[Cloudflare Workers AI · free tier]
  be -->|FAL_KEY| fal[fal.ai · paid per use]
  be -->|your model| custom[fal / Replicate / ComfyUI / OpenAI-compatible]
```

## Text (LLM) — `agentic_core/models/llm`

| Choice | Provider |
|---|---|
| Auto (default) | OpenAI if `OPENAI_API_KEY`, else Groq if `GROQ_API_KEY`, else Mock |
| `ollama` | Local Ollama (`OLLAMA_BASE_URL`, `OLLAMA_MODEL`) |
| `groq` | Groq (free tier) |
| `openai` | OpenAI |
| `mock` | Deterministic offline text (tests) |
| your text model | Any OpenAI-compatible API added in Settings (DeepSeek, Together, LM Studio, vLLM…) |

Animations crews (`studio/llm`): Ollama (default, local), Groq, Gemini, OpenRouter, OpenAI, Anthropic, Claude Code,
Codex, built-in rules (no AI), plus your text models from Settings as extra crews.

## Pictures — `agentic_core/models/image`

| Choice | Provider | Cost |
|---|---|---|
| **`best`** (default for new projects) | Qwen-Image when the picture must show text, else Z-Image; next ready model on failure; free chain when none is set up | per backend |
| `z-image` · `qwen-image` · `flux-schnell` | Catalog models on your GPU / Cloudflare (FLUX) / fal.ai | free / free tier / paid |
| `free` | Chain: Cloudflare Workers AI → Pollinations → your image server | free |
| `pollinations` · `cloudflare` · `local` | Single free providers (`local` = Automatic1111-compatible `IMAGE_SERVICE_URL`) | free |
| `chain` | Free chain, then Replicate/Stability under a daily spend cap | free → paid |
| `replicate` · `stability` | Paid APIs | paid |
| your image model | fal.ai / Replicate / ComfyUI model added in Settings | per backend |
| (none / `mock`) | Deterministic placeholder frames | free |

## Video and avatars — `agentic_core/models/video`

| Choice | What each shot gets |
|---|---|
| **`best`** (default for new projects) | Wan 2.2 image-to-video (LTX-2.3 for shots over ~10 s); next ready model on failure; free camera motion when none is set up |
| `wan-2.2` · `ltx-2.3` · `wan-vace` | One catalog model. LTX-2.3 follows the narration audio when available; Wan VACE keeps look/identity consistent |
| `avatar` | A presenter speaking the shot's narration: LongCat Avatar, or InfiniteTalk for long takes |
| `longcat-avatar` · `infinitetalk` | One avatar model |
| `motion` | Free: the shot's picture with a smooth camera move (ffmpeg) |
| `comfyui` | Your single `video.json` workflow on your GPU |
| `fal` | Kling 2.1 on fal.ai (`FAL_VIDEO_MODEL`) |
| `replicate` | Hosted video model on Replicate |
| `local` | Your own video service (`VIDEO_SERVICE_URL`) |
| your video / avatar model | Added in Settings |
| (none) | No clips; the final render animates the pictures |
| `blender` (older projects only) | Blender 3D mannequins; not offered for new projects |

Providers that animate pictures (`IMAGE_TO_VIDEO_PROVIDERS` / `is_image_to_video`) make the project use the free
picture chain if no image provider was chosen. Avatar providers (`needs_presenter`, `wants_audio`) receive the
presenter portrait and the shot's narration slice.

## The model catalog — `agentic_core/models/catalog.json` + `catalog.py`

| Job | Best | Second | Fallback / other |
|---|---|---|---|
| Image | Z-Image Turbo (Apache-2.0) | Qwen-Image (Apache-2.0) — readable text | FLUX.1 schnell (Apache-2.0) |
| Video | Wan 2.2 I2V A14B (Apache-2.0) | LTX-2.3 22B (LTX-2 Community License: conditions) | Wan VACE 14B (continuity) |
| Avatar | LongCat Avatar (MIT) | InfiniteTalk (Apache-2.0) | Wan 2.2 Animate (Apache-2.0), SCAIL-2 (MIT, GPU only) |
| Control | Wan VACE | Vista4D (reference only) | |

Each entry carries: task, rank, role, best_for, why, licence (+ commercial yes/conditional, notes, URL), inputs,
VRAM size, fal endpoint + price, ComfyUI workflow file + template, and where AVOS uses it.

`catalog.py`:
- `available_backends(id)` → for each backend, `None` if usable or the reason it isn't;
- `backend_for(id)` → **your hardware first**: GPU workers → your ComfyUI server (if its workflow file exists) →
  Cloudflare (FLUX) → fal.ai; `MODEL_BACKEND=gpu|fal|comfyui` (or Settings → "Run models on") forces one. The catalog
  providers then ask the **Model Router** ([10](10-model-fabric-and-gpu-workers.md)) for ranked placements per call
  (model × GPU × backend × precision, by quality, speed, cost and VRAM) and fall through them on failure;
- routing: `route_image(prompt)` (text in the picture → Qwen-Image; "no text" doesn't count), `route_video(has_audio,
  seconds, continuity)`, `route_avatar(seconds, speakers)`;
- `status()` → the Models page / `GET /models` (includes your models, with `missing` reasons).

## Backends

| Backend | Code | How it works |
|---|---|---|
| **GPU workers** | `model_fabric/scheduler.py` → `apps/gpu_worker` | `POST /jobs` with the router's model, backend, precision, attention and VRAM need; poll progress; download; the worker keeps the model loaded for the next shot |
| **ComfyUI** (your GPU) | `video/comfyui_provider.py` (`run()`) | Loads `COMFYUI_WORKFLOW_DIR/<model id>.json` (API export), uploads `{{IMAGE}}` / `{{AUDIO}}` / `{{VIDEO}}` files, fills `{{PROMPT}} {{NEGATIVE_PROMPT}} {{SEED}} {{WIDTH}} {{HEIGHT}} {{FRAMES}} {{FPS}} {{DURATION}} {{STEPS}}`, queues `/prompt`, polls `/history`, downloads the first video (or image) via `/view`. Frame counts follow each model's rule (Wan 4k+1 at 16 fps, LTX 8k+1 at 25 fps). |
| **fal.ai** | `models/fal_client.py` | Queue API: POST `queue.fal.run/<endpoint>` → poll `status_url` → GET `response_url`; files inline as data URIs; clear errors for 401/402/422. Per-model input mapping in `image/catalog_image.py` and `video/catalog_video.py`; `<MODEL>_FAL_INPUT_JSON` overrides fields. |
| **Replicate** | `custom_models.replicate_run`, `video/replicate_provider.py` | Predictions API with `Prefer: wait`, then polling |
| **Cloudflare** | `image/cloudflare_provider.py` | Workers AI FLUX schnell (free daily allowance) |
| **OpenAI-compatible** | `llm/openai_provider.py` | `/chat/completions` with any base URL |

## Models you add (Settings) — `agentic_core/settings_store.py` + `models/custom_models.py`

A model definition: `id`, `name`, `task` (image | video | avatar | llm), `kind` (fal | replicate | comfyui | openai),
`endpoint` or `base_url` + `model`, `key_env` (any key name you saved), an **input template** (JSON with
placeholders) and an optional `output` path.

Placeholders: `{{prompt}} {{negative_prompt}} {{width}} {{height}} {{aspect_ratio}} {{seed}} {{duration}}
{{duration_int}} {{num_frames}} {{fps}} {{image_url}} {{audio_url}} {{video_url}}`. A field that is exactly one
placeholder keeps the value's type; a field whose value is missing (e.g. no audio) is dropped.

`CustomImageProvider` / `CustomVideoProvider` run them; text models become an `OpenAIProvider` with your base URL.
They appear in the catalog (`custom: true`), the Facts pickers, the Animations settings and crews, and project
validation accepts their ids.

## Narration — `agentic_core/pipelines/audio`

`TTS_PROVIDER=edge` (free Microsoft Edge voices, word timings included) or `mock`; Whisper-style alignment when the
voice gives no timings; `timestamps.py` (sentences) and `semantic_beats.py` (beats that become shots).
