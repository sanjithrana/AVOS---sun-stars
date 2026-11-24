# Settings and configuration
Run: `docker compose up -d --build` in apps; `npm run dev` in desktop. After studio code changes: `docker compose restart animation-studio`.
Precedence: apps/.env, overridden by Settings page (avos.json); clearing restores .env. Keys masked; never commit .env.
Settings: API keys, GPU server (COMFYUI_URL, Run models on), your models, workflow uploads.
Main variables: DATABASE_URL, REDIS_URL, TEMPORAL_HOST, OLLAMA_BASE_URL, OLLAMA_MODEL, LLAMACPP_URL, FAL_KEY, REPLICATE_API_TOKEN, CLOUDFLARE_*, MODEL_BACKEND, GPU_WORKER_TOKEN, TTS_PROVIDER, VISUAL_CONCURRENCY, SERIES_CONCURRENCY, STUDIO_*, ASSETS_STORAGE, S3_*, RENDER_SIZE, CAPTIONS, MUSIC.
