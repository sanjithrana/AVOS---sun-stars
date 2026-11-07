# AVOS Animation Studio

ReelMimic ([edenfunf/reelmimic](https://github.com/edenfunf/reelmimic)) rebuilt in Python for the AVOS **Animations** tab:
show it a video you love, get a new video in the same style. Same workflow, same API, same project files as ReelMimic,
but the AI crew is **local first** (Ollama) and the video is drawn by a built-in Python 2D engine, so no Claude Code /
Codex subscription is needed. Those (and free/paid cloud models) are optional crews.

## Run

| How | Command |
|---|---|
| Docker (from `apps/`) | `docker compose up -d --build animation-studio` |
| Windows, no Docker | double-click `apps\start-animations.bat` |
| macOS / Linux | `apps/start-animations.sh` |

Service: http://127.0.0.1:8020 (`/api/health`). Local crew: install [Ollama](https://ollama.com), `ollama pull qwen2.5:7b`
(optional vision model for reviewers: `ollama pull qwen2.5vl:7b`, then set it in AI settings).

## How it maps to ReelMimic

| ReelMimic (Node + Claude Code/Codex) | Here (Python) |
|---|---|
| `app/server/index.ts` (REST + SSE) | `studio/server.py`: the same endpoints and JSON shapes, plus `/api/agents/info`, `/api/agents/settings`, `/api/agents/pull` |
| `app/server/jobs.ts` (stage machine, gates, rounds, needs, retry/accept/resume) | `studio/jobs.py`: a line-by-line port |
| `app/server/prompts.ts` + agent CLIs writing files | `studio/director/` (`pre.py`, `prod.py`, `final.py`): one function per phase, writing the same contract files (`plan.json`, `STORYBOARD.md`, `build/production.json`, reviews, fixes, `critique.json`, `out/video.mp4`) |
| `agents/index.ts` (Claude Code / Codex) | `studio/llm/`: Ollama (default), Groq, Gemini, OpenRouter, OpenAI, Anthropic, Claude Code, Codex, built-in rules |
| 7 drawing engines (HyperFrames, painted-animation, crayon, pixel, paper, whiteboard, anime-cel; JS + Chrome) | `studio/render/`: one skia renderer with the 7 looks, a jointed character rig with one-piece outlines and expressions, props, settings, camera moves, transitions, effects, captions, karaoke lyrics |
| `.claude/skills/video-clone/scripts/*.py` and `styles/*.md` | `reelmimic_assets/` (unchanged copies, see `NOTICE.md`) |
| `app/web` (React) | `apps/desktop/components/reelmimic/` (ported into the AVOS Next.js app) |

Agents in ReelMimic write code and render it; here the AI writes the plan, characters and shot specs as JSON and the
engine renders them. That keeps a 7B local model reliable: whatever the model answers is checked and clamped, and when
an answer is unusable the step falls back to the engine's own draft instead of failing. Reviewers measure what was
drawn (subject size, text over faces, characters out of frame, overlap, dead static shots, flicker, empty frames,
length, the 180° rule, caption consistency, silent audio) and, with a vision model, also look at the sheets and frames.
Every fix comes with before/after crops and is verified by the next reviewer.

## Open AI models

The same open models as the Facts tab (shared list: `apps/agentic_core/models/catalog.json`, see the Models page):

- **AI backdrops**: AI settings → "Model for AI backdrops": free chain (default), best (Z-Image; Qwen-Image when the
  picture needs text), Z-Image, Qwen-Image or FLUX.1 schnell. A failed call falls back to the free chain.
- **AI finish** (Final tab, `POST /api/projects/{id}/finish {"model"}`): Wan VACE (re-style keeping the motion),
  Wan 2.2 Animate / SCAIL-2 (each shot's first frame performs the engine's motion) or LTX-2.3. Result:
  `out/video_ai.mp4`, same length and soundtrack; progress in `out/finish.json`.

They run on your GPU server (ComfyUI address in AI settings or `COMFYUI_URL`, workflows in
`apps/comfyui_workflows/<model id>.json`) or on fal.ai (key in AI settings or `FAL_KEY`). Code: `studio/models.py`,
`studio/finish.py`.

## Tests

`python -m pytest -q` (FFmpeg needed): parsing, all 7 looks, framing, the whole workflow through the HTTP API with the
built-in crew and with a stand-in Ollama server (`tests/fake_ollama.py`, which also sends broken replies to test retries).
