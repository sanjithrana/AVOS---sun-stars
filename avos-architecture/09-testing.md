# 9. Testing

| Suite | Where | Run | Notes |
|---|---|---|---|
| Core | `apps/agentic_core/tests` | `pytest agentic_core/tests` | Pure logic: script/audio pipelines, shotspec builder, continuity, prompt compiler, constitution, Director, QA committee, repair classifier, image chain, model catalog, LLM/image/video factories, quota, settings store, video render |
| API | `apps/api/tests` (+ `integration/`, `tool_gateway/`) | `pytest api/tests` | Projects, gates, shots/shotspec, physics-before-pixels, generation (idempotency, real-provider path with stand-ins), QA, repair ladder, final render, asset registry, event bus, models and settings routes, **shot edit**, `CreateVideoWorkflow`. Tests needing Postgres, Redis or Temporal **skip** when those aren't reachable |
| Animation Studio | `apps/animation_studio/tests` | `pytest animation_studio/tests` | 45 tests: units, renderer, models (pictures, finish, custom, Replicate, GPU workers), full pipeline against `fake_ollama.py`, Series end to end (`test_series.py`) |
| GPU worker | `apps/gpu_worker/tests` | `cd gpu_worker && pytest tests` | Pretend GPUs (RTX 4090 / 5090): status, precisions, queue, warm models and LRU eviction, pins, cancel, ComfyUI templating, Wan2GP headless command, workflow push |
| UI end to end | `apps/desktop/tests/e2e` | `npx playwright test` | `create-project`, `day15-checkpoint`, `generation-monitor`, `qa-dashboard`, `final-video`, `models`, `settings`, `gpu`, `downloads`, `animations`; `animations-live` only with `STUDIO_LIVE=1`; `series` with `E2E_GPU_WORKER_URL` |
| Static | `apps/desktop` | `npx tsc --noEmit`, `npm run lint` | Types and ESLint |

## Conventions

- Tests use **mock providers** (`mock` text, mock image frames, `motion` clips, mock TTS) so they are free and
  deterministic; e2e specs that check QA pick picture model "" (Mock).
- Paid / GPU paths (fal.ai, Replicate, ComfyUI) are tested against local stand-in servers that speak the same API;
  real calls need your keys or GPU.
- Settings tests write to a temporary settings file (`AVOS_SETTINGS_FILE`) and clear it afterwards so keys never
  leak between tests.
- Model Fabric: `agentic_core/tests/test_model_fabric.py` (routing, VRAM / precision, limits, learned speed) and
  `api/tests/test_gpu_fabric.py` (a shot generated on a real worker process with the mock backend: gpu_jobs rows,
  events, warm models, failure → fal.ai fallback, QA feedback, the GPU API). `gpu.spec.ts` takes
  `E2E_GPU_WORKER_URL` to also check a live worker.
- v12: `test_downloads.py` (verified manifest, resume / skip / errors / cancel / folder roots against a fake Hugging
  Face), `test_gpu_fabric.py::test_download_a_model_to_this_pc_and_to_a_gpu_worker`, scheduler tests in
  `test_model_fabric.py` (spreading, warm affinity, priorities, warm-up), `test_s3_storage.py` (SigV4 = botocore,
  moto round trip), QA visual check on real frames, the review gate in `test_create_video_workflow.py`, worker
  priority queue, `downloads.spec.ts`.
- v13 (Series): `animation_studio/tests/test_series.py` (the whole flow on a mock GPU worker process, the writers'
  room through the stand-in Ollama), `gpu_worker/tests/test_series_backends.py` (speech, foley, ComfyUI references
  and audio), `series.spec.ts`.
- The agent trace is asserted through `GET /agents/trace` (every tool call has exactly one audit row).

## Before shipping a change

1. `pytest agentic_core/tests api/tests animation_studio/tests`
2. `cd desktop && npx tsc --noEmit && npm run lint`
3. With the stack up: `npx playwright test`
4. One real Facts project end to end (topic → approve script → final MP4), and one shot edit + regenerate.
