# System architecture
Two studios, **Facts** (durable multi-service video pipeline) and **Animations** (Animation Studio: Explainer + Series), share one model layer and one settings store.

| Part | Technology | Port | Job |
|---|---|---|---|
| Desktop UI | Next.js 16, React 19, Tailwind 4, TanStack Query | 3000 | Pages |
| AVOS API | FastAPI | 8001 | Projects, gates, shots, QA, SSE events, settings, GPU routes |
| Workflow worker | Temporal (`CreateVideoWorkflow`) | 7233 (UI 8233) | Facts pipeline, durable |
| Database | PostgreSQL 16 | 5435 | Projects, shots, audit, gpu_jobs |
| Event bus | Redis 7 | 6380 | Live updates |
| Animation Studio | FastAPI + skia | 8020 | Animations, Explainer, Series (folders on disk) |
| GPU workers | FastAPI per GPU machine | 8700+ | ComfyUI / Wan2GP / Diffusers |
| Blender | optional | 8090 | Physics, 3D cutaways |
| Local models | Ollama, ComfyUI, llama.cpp | 11434, 8188, 8080 | Free models |
| Object store | SeaweedFS optional | 8333 | S3 assets |

Principles: local/free first; durable and resumable; humans approve before money is spent; every agent action audited; physics and continuity before pixels; AVOS decides what, GPU workers decide how; one model layer, one settings store.
