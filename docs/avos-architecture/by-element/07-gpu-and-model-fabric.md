# GPU and Model Fabric
Router scores each placement (worker x backend x precision; ComfyUI; Cloudflare; fal; Replicate) after hard checks (VRAM, precision, model installed, limits).
Weights quality/speed/cost: quality .70/.15/.15; balanced .50/.25/.25; speed .30/.55/.15; cost .30/.15/.55.
Limits: preference, max cost/seconds per shot, max attempts 3, allow hosted, preferred/fallback model.
GPU worker :8700: one job at a time, VRAM manager (LRU, pins), token GPU_WORKER_TOKEN; backends ComfyUI, Wan2GP, Diffusers, mock (WORKER_MOCK=1).
Scheduler: parallel shots, in-flight ledger, warm-up, priorities. Telemetry: gpu_jobs rows + events; learned speed/QA. Downloads to PC or worker; S3-compatible storage.
