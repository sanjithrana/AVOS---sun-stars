"""AVOS Model Fabric: model registry (catalog.json) + Model Router + GPU workers + generation limits + telemetry.

AVOS decides WHAT should happen (which model, at what quality, within which limits); GPU workers decide HOW to run
it (ComfyUI, Wan2GP, Diffusers, at a precision and attention kernel their GPU supports). Adding a model is a
catalog entry (or Settings → Models); adding a GPU is Settings → GPU workers. Nothing else changes.

    router.py       score every (model × GPU × backend × precision) placement for a shot
    workers.py      configured GPU workers and their live status
    scheduler.py    run a job on a worker (submit, progress, download)
    policy.py       per-shot limits: preference, max cost, max time, max attempts, QA bar
    performance.py  measured speed / success / QA per model and GPU → routing learns
    telemetry.py    every run reported (gpu_jobs rows + GPU_JOB_* live events in the API)
    requirements.py precision / attention / GPU speed tables
"""
