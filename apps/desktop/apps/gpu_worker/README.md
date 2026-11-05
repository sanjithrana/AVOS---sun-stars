# AVOS GPU worker

A small service that runs **on each GPU machine**: your own PC with an RTX card, a RunPod / Vast.ai / Lambda pod, or
a cloud VM. AVOS's **Model Router** sends it jobs it has already planned: which model, which backend, which
precision and which attention kernel. The worker then:

- queues the jobs, running one GPU job at a time;
- keeps models **loaded between shots**, so shot 2 with the same model skips the load;
- evicts the least recently used model when VRAM runs out;
- runs each job through **ComfyUI**, **Wan2GP** or **Diffusers**, and reports progress;
- keeps the output until AVOS downloads it.

AVOS doesn't care where the GPU is. Add the worker's address in **Settings → GPU workers** and it appears on the
**GPU** page.

```
AVOS (your PC)                         GPU machine
 Model Router ── POST /jobs ─────────▶ AVOS GPU worker :8700
   (model, backend, precision,          ├─ ComfyUI   (workflows/<model id>.json)
    attention, VRAM need)               ├─ Wan2GP    (wan2gp_templates/<model id>.json, wgp.py --process)
 GPU page  ◀── GET /status ───────────  ├─ Diffusers (Hugging Face pipelines, torchao / Nunchaku quantization)
                                        └─ PyTorch + CUDA → Triton · SageAttention · FlashAttention → GPU
```

## Downloading models onto this machine

On the AVOS **Models** page, **Download → Where: <this worker>** makes the worker fetch the model's ComfyUI files from
Hugging Face into `WORKER_MODELS_DIR` (set it to your ComfyUI `models` folder, or set `COMFYUI_DIR`), with progress,
resume and a folder picker. `HF_TOKEN` on the worker is used for gated repos.

## Queue priorities

Jobs carry a priority: 0 for a Studio edit someone is waiting for, 5 for normal production, 9 for background
warm-ups. The queue runs the most urgent first (then in arrival order); `GET /status` lists it.

## What it reports (`GET /status`)

| Field | Contents |
|---|---|
| GPU | Name, total and free VRAM, temperature, utilisation, compute capability, driver and CUDA versions (from `nvidia-smi`) |
| Supports | `bf16` on compute capability ≥ 8.0 (RTX 30, A100); `fp8` on ≥ 8.9 (RTX 40, L40S, H100); `fp4` on ≥ 10 (RTX 50, B200); `int8` / `int4`. Also which of `triton`, `sageattention`, `flash_attn`, `nunchaku` and `torchao` are installed. |
| Backends | For each backend: whether it is ready (and why not), which AVOS models it can run, the precisions it can apply, and the fastest attention kernel installed |
| Loaded models | Each loaded model with its precision, VRAM, when it was last used, and whether it is pinned |
| Queue | Queue depth, the running job, and average job time |
| Cost | Your cost per hour (`WORKER_COST_PER_HOUR`), used for the router's cost estimate |

## Install

### Option A: directly on the machine (recommended with Wan2GP)

Wan2GP and ComfyUI each have their own Python environment with matching PyTorch, CUDA, Triton and SageAttention
versions. The worker itself only needs FastAPI.

```bash
cd apps/gpu_worker
python -m venv .venv && . .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# optional, the in-process Diffusers backend (install the right torch build first):
# pip install torch --index-url https://download.pytorch.org/whl/cu128 && pip install -r requirements-diffusers.txt
export GPU_WORKER_TOKEN=change-me WORKER_COST_PER_HOUR=0.69
export WAN2GP_DIR=/workspace/Wan2GP WAN2GP_PYTHON=/workspace/Wan2GP/.venv/bin/python
export COMFYUI_URL=http://127.0.0.1:8188
python -m worker                                      # listens on :8700
```

### Option B: Docker (needs the NVIDIA Container Toolkit)

```bash
cd apps/gpu_worker
GPU_WORKER_TOKEN=change-me WITH_DIFFUSERS=1 docker compose -f docker-compose.gpu.yml up -d --build
```

### RunPod / Vast.ai

1. Start a pod from a PyTorch or ComfyUI template. Expose HTTP port **8700**, and 8188 if you also want the ComfyUI UI.
2. Copy `apps/gpu_worker` to the pod (git clone your repo, or `scp`) and follow option A.
3. In AVOS add the pod's public URL for port 8700 (e.g. `https://<pod id>-8700.proxy.runpod.net`) under
   **Settings → GPU workers**. Enter what the pod costs per hour so the router can weigh it against fal.ai.

**Several GPUs in one machine:** run one worker per GPU with `WORKER_GPU_INDEX=0`, `1`… and `CUDA_VISIBLE_DEVICES`
set to the same index, on ports 8700, 8701…

## Backends

### ComfyUI

Start ComfyUI on the same machine (`python main.py --listen`, plus `--use-sage-attention` if SageAttention is
installed; then set `COMFYUI_ATTENTION=sage`).

Save each model's workflow in API format as `workflows/<model id>.json`, for example `workflows/wan-2.2.json`. The
placeholders are the same as in `apps/comfyui_workflows/README.md`. One more lets the router pick the precision:
put `{{WEIGHT_DTYPE}}` in the `weight_dtype` field of the *Load Diffusion Model* node. It becomes `default` for
bf16, or `fp8_e4m3fn_fast` on RTX 40/50 for fp8.

### Wan2GP

```bash
git clone https://github.com/deepbeepmeep/Wan2GP /workspace/Wan2GP
```

Install it by following its own guide, which pins the Python, PyTorch, CUDA, Triton and SageAttention versions for
your card. Then:

1. Open Wan2GP's web UI once (`python wgp.py`).
2. Pick the model and settings you want for AVOS.
3. Save the settings file as `wan2gp_templates/<model id>.json`.
4. Replace the values AVOS should control with placeholders (see `wan2gp_templates/README.md`).

The worker runs `wgp.py --process <settings> --output-dir <tmp> --attention <sage2|sage|flash|sdpa>
--quantize-transformer <True|False>`. That is Wan2GP's documented headless batch mode. Precision maps as bf16 →
unquantized, int8 → Wan2GP's INT8.

Each job starts Wan2GP afresh, so the model loads every time. Use ComfyUI or Diffusers for warm models.

### Diffusers

These models run in the worker process and stay loaded:

| Model | Hugging Face repo |
|---|---|
| FLUX.1 schnell | `black-forest-labs/FLUX.1-schnell` |
| Qwen-Image | `Qwen/Qwen-Image` |
| Z-Image Turbo | `Tongyi-MAI/Z-Image-Turbo` |
| Wan 2.2 I2V | `Wan-AI/Wan2.2-I2V-A14B-Diffusers` |
| Wan VACE | `Wan-AI/Wan2.1-VACE-14B-diffusers` |

How the router's choices are applied:

- **Precision:** fp8, int8 and int4 use torchao weight-only quantization; fp4 and int4 use a Nunchaku transformer
  where one is configured.
- **Attention:** set with `set_attention_backend` (SageAttention or FlashAttention).
- **Offload:** CPU offload is used when the model doesn't fit in VRAM.

Add or override models with `WORKER_DIFFUSERS_MODELS_JSON`. Set `HF_HOME` to a big disk, and `HF_TOKEN` for gated
repos.

### Mock (no GPU)

`WORKER_MOCK=1 WORKER_ADAPTERS=mock` produces coloured stand-in pictures and clips, so you can try the GPU page and the
router on any PC. To pretend to be a particular card, set
`WORKER_FAKE_GPU='{"name":"NVIDIA GeForce RTX 4090","vram_gb":24,"compute_capability":"8.9"}'`.

## Settings

| Variable | Default | Meaning |
|---|---|---|
| `WORKER_PORT` | 8700 | Port |
| `WORKER_NAME` | host name | Shown in AVOS |
| `GPU_WORKER_TOKEN` | — | Shared secret. Set the same value in AVOS (Settings → API keys). **Set it whenever the worker is on the internet.** |
| `WORKER_COST_PER_HOUR` | 0 | What this GPU costs per hour, for the router's cost estimate |
| `WORKER_ADAPTERS` | comfyui,wan2gp,diffusers | Backends to offer, in order of preference |
| `WORKER_GPU_INDEX` | 0 | Which GPU this worker reports |
| `WORKER_PIN` | — | Models that are never unloaded (e.g. `ltx-2.3`) |
| `WORKER_VRAM_RESERVE_GB` | 1.5 | VRAM kept free |
| `WORKER_RESULT_TTL` | 3600 | Seconds before results that were never fetched are deleted |
| `COMFYUI_URL`, `COMFYUI_WORKFLOW_DIR`, `COMFYUI_ATTENTION` | | ComfyUI backend |
| `WAN2GP_DIR`, `WAN2GP_PYTHON`, `WAN2GP_TEMPLATES`, `WAN2GP_PROFILE` | | Wan2GP backend |
| `WORKER_DIFFUSERS_MODELS`, `WORKER_DIFFUSERS_MODELS_JSON`, `HF_HOME`, `HF_TOKEN` | | Diffusers backend |

## Your development PC

An Intel Iris Xe laptop runs all of AVOS except the generation itself: UI, API, Temporal, Postgres and Ollama.

Don't try to get CUDA, Triton or SageAttention working on it. Run this worker on a GPU machine and point AVOS at it.
