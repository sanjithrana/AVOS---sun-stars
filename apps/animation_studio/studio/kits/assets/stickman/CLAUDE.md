# Stickman Shorts (free from Anylancer.com)

This folder makes stickman cartoon videos (9:16) with the `/stickman-shorts` skill in `.claude/skills/stickman-shorts/`.
Type `/stickman-shorts why do cats always land on their feet?` (any question), or just ask for a stickman video.

## Setup (when the user says "run the setup", or before the first video)
1. Check Python 3: `python --version` (Windows) or `python3 --version` (Mac). Missing: tell the user to install it from python.org (Windows: tick "Add python.exe to PATH") and restart.
2. Check a browser: Chrome or Edge (used for stills and the Export video button).
3. Test: `python scripts/pack.py examples/salty-ocean/story.js examples/salty-ocean/voice.mp3 -o examples/salty-ocean/salty-ocean.html --words examples/salty-ocean/words.json`, then `python scripts/stills.py examples/salty-ocean/salty-ocean.html 1 8 16` and look at the PNGs.
4. Optional, for one-click MP4s: Node 18+ and ffmpeg on PATH plus a browser driver (`npm i puppeteer-core` in this folder; `CHROME_PATH` pointing at Chrome or Edge). Ask the user before installing anything. Without it, the HTML player's **Export video** button records the video in Chrome.
5. Tell the user it's ready and suggest a first question from `references/ideas.md`.

## Folders
- `engine/` the 2D cartoon engine (stick people, places, props, effects, shots, captions, sound). Edit only to add new props or places.
- `scripts/` pack.py (story → one HTML player), stills.py (PNG frames with the browser already on this PC), render.mjs (frame-exact MP4), voice.py (free computer voice or ElevenLabs, with word timings).
- `references/` engine.md (every helper), script.md, ideas.md, checklist.md.
- `examples/` three finished videos with their story files: onion-tears, black-hole, salty-ocean.
- `videos/` put each new video in its own folder here.

Free to use in your own videos and projects. Not for resale.
