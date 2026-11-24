---
name: avos-free-models
description: Which image and video models are actually free to use with AVOS Studio, by hardware, and which popular ones to skip. Read before choosing a model or telling the user what is free.
---

# Free image and video models (checked Nov 2026)

"Free" means one of three things: free to call (hosted free tier), free to run (your own GPU), or free to licence (commercial use allowed). Check all three.

## Ladder by hardware
| You have | Images | Video |
|---|---|---|
| No GPU, no card | Pollinations, Cloudflare Workers AI (free tier about 10,000 neurons/day) | None. Cloudflare has no text-to-video model. Skills fall back to still picture + camera move. |
| GPU 8 GB | FLUX.2 klein 4B (Apache 2.0, about 13 GB download), SDXL class | Wan 2.2 via ComfyUI with offload (slow), short clips |
| GPU 24 GB | FLUX.2, Qwen-Image / Qwen-Image-Edit (Apache 2.0) | Wan 2.2, LTX 2.3 through the GPU worker |
| Rented GPU (RunPod 4090 about $0.34/h community, $0.89/h secure) | same | same; roughly $0.7 to $1.8 per 60 s film, versus about $4.8 on fal Wan and $9.3 on Seedance Mini (estimates) |

## How AVOS uses them
- Explainer / Series: Wan 2.2 and LTX 2.3 through the model fabric (GPU worker, ComfyUI, fal).
- Skills and Stickman: Seedance 2.0 Mini first when a fal key is set. With no key, or with Video set to **Wan 2.2** or **LTX-2.3**, they use the open model on your GPU worker / ComfyUI. Open models animate the first picture only, make no sound (foley and music are mixed in), and a Wan clip is about 5 s.
- "This PC only" blocks fal and Cloudflare; Seedance is fal-only, so it is off in that mode.

## Free parts that need only a key or nothing (checked Nov 2026)
- **Stock footage: Pexels.** Free key (pexels.com/api), 200 requests/hour and 20,000/month, a visible link to Pexels is required and the film-maker should be credited (AVOS keeps the credit lines in `series/stock.py`: `credit_lines()`). Footage matches keywords, not your character, so it is a choice (Footage = Stock) and never an automatic stand-in. Skills and Stickman only.
- **Voices: Edge TTS.** Free, no key, an online call to a Microsoft endpoint. Already in AVOS.
- **Scripts: Groq, Gemini and OpenRouter free tiers, or Ollama.** Free tiers may use your prompts to improve products: fine for public scripts. Google's page says new projects should use `gemini-3.5-flash-lite` or `gemini-3.8-flash` (the 2.5 models stay up but are limited to people who already used them), so AVOS now defaults to `gemini-3.5-flash-lite`; whether your free key can use it is unchecked.
- **Images: Cloudflare Workers AI and Pollinations.** Already in AVOS.

## Best paid, for AVOS (prices per second at 720p from fal pages dated Nov 2026; estimates)
1. **fal.ai with Seedance 2.0 Mini (about $0.155/s)**: already wired; takes reference pictures and can make sound; one key covers images too. Best for characters.
2. **fal.ai with MiniMax H3 Max Turbo (about $0.04/s) or Max ($0.08/s)**: the cheapest quality motion; no references, so best for plain scenes. Not wired yet.
3. **fal.ai with Kling 2.6 Pro (about $0.07/s, $0.14 with sound)**: strong motion, optional sound. Not wired yet.
Direct BytePlus ModelArk (ByteDance's own Seedance) may be cheaper than fal, but its prices were not checked.

## Resellers (sponsor lists)
Offers like "Claude at 6% of official price" cannot be genuine resale; skip them. Unverified aggregators (APIMart, RunningHub, Jalapeno, AstraFlow, Shengsuan, OfoxAI, Metaso): trial credit only, small top-up, nothing private. Every one pays the listing author a referral.

## Skip these (and why)
- **Ollama image generation**: macOS-only per Ollama's own page; no video at all. Not usable on Windows or in Docker.
- **Kimi K3 in C**: text only, about 0.04 to 0.18 tokens/s. Not an image or video model, and far too slow to be a writer.
- **Qwen-Image 2.1**: non-commercial licence. Fine for practice, not for monetised content. Qwen-Image and Qwen-Image-Edit (Apache 2.0) are fine.
- **HunyuanVideo 1.5**: licence not confirmed; do not add until it is.
- **Wan 2.2 TI2V-5B**: Apache 2.0 and light, but not wired in yet (needs 24 fps handling, its own fal endpoints and router entries).

Never promise a model is free without naming which of the three meanings applies.
