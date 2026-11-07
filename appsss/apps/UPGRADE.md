# AVOS quality upgrade

Install (Git Bash):
    cd /d/star/apps
    tar -xf /d/path/to/avos-upgrade.zip        # overwrites 13 files, nothing else
    docker compose restart animation-studio     # skills reload by themselves; code needs this restart
    docker compose restart api worker

What changed
- skills/*: character design (silhouette, colour budget, model-sheet brief, voice-casting line), cinematography
  (coverage, 180 degree rule, thirds, motivated camera moves), dialogue for voice, layered sound + music-prompt
  format, stricter shot QA.
- compiler.py / dna.py (identical copies in agentic_core and animation_studio): composition and angle language,
  acting line, weight/anticipation/follow-through, "Sound:" clause for LTX-2.3, stronger negative prompt.
- media.py: real model sheet (front, 3/4, side, back, 6 expressions, hands); FIX: the sheet used to be generated
  with "character sheet layout" as a negative prompt; better voice and music prompts.

Recommended settings (AI settings panel and .env)
- AI crew: Groq (gpt-oss-120b) for planning; keep STUDIO_REASONING_EFFORT low on the free tier.
- .env: delete the second "LLM_PROVIDER=ollama" line if you want Facts to use Groq as well.
- Render quality 1080p, Pictures = AI images, Review rounds 3 / 3 / 2.
