# Models and providers
- Text: Auto (OpenAI, Groq, mock), Ollama, Groq, OpenAI, llama.cpp, mock, any OpenAI-compatible model. Animation crews add Gemini, OpenRouter, Anthropic, Claude Code, Codex, built-in rules.
- Pictures: best (Qwen-Image if text needed, else Z-Image), z-image, qwen-image, flux-schnell, free chain (Cloudflare, Pollinations, your server), Replicate, Stability, your models, mock.
- Video: best (Wan 2.2; LTX-2.3 over ~10 s), wan-2.2, ltx-2.3, wan-vace, avatar (LongCat, InfiniteTalk), camera motion, ComfyUI, fal Kling, Replicate, your own.
- Narration: Edge TTS or mock.
Catalog: Image Z-Image / Qwen-Image / FLUX schnell. Video Wan 2.2 / LTX-2.3 / Wan VACE. Avatar LongCat / InfiniteTalk / Wan 2.2 Animate / SCAIL-2.
Run order: GPU workers -> your ComfyUI -> Cloudflare -> fal.ai (MODEL_BACKEND forces one).
Add your own model in Settings: name, type, provider (fal/Replicate/ComfyUI/OpenAI-compatible), key name, input template with placeholders.
