# Kits: 29 skills that render real videos inside AVOS

Skills tab → groups **Kits · Story engines** (Cartoon Shorts, Cartoon Shorts 3D+2D, Science Story Shorts, Stickman Shorts),
**Kits · Animation styles** (10) and **Kits · 3D styles** (15).

Each run: script (yours kept word for word if you paste 45+ words) → voice (edge-tts with exact word timings) → the writer crew
writes the story / style file the engine plays → it is loaded in a real browser and sent back for repair if the page throws
(3 rounds) → every frame is drawn and joined with the sound mix into an MP4. Finished videos appear in the Library with the style name.

## One-time engine install
It installs itself the first time a kit skill runs (Skills tab shows an "Install it now" button too). To do it by hand:

    docker compose exec animation-studio python -m studio.kits.engine

To bake it into the image instead, add to the animation-studio Dockerfile:

    RUN pip install playwright edge-tts && playwright install --with-deps chromium

## Honest limits
* Frames are drawn with software WebGL (no GPU). Draft size by default (540x960, 24 fps); `KITS_QUALITY=hd` gives 1080x1920 at 30 fps.
  Expect roughly 10-40 minutes for a 30 s video.
* The animation code is written by your AI crew. Code this size needs a strong writer (Claude, Gemini, OpenAI, a large Ollama model);
  small free models often fail the repair loop and the run stops with a clear message.
* The voice needs internet (Microsoft Edge TTS). The 3D animation styles load three.js r128 from cdnjs.
* Story engines are 9:16 only; animation styles and 3D styles also do 16:9 and 1:1.
* Kit engines and style recipes: Anylancer free kits (three.js MIT). See each kit's own licence notes.

## Auto Clip: GTA 6 Clip Kit
Auto Clip → "What kind of video" → **GTA 6 clips**: picks the moments people search for (cop chases, crashes, fails, glitches, funny
moments, first-time discoveries, rage, stunts) from what is said as well as how loud it is, burns a hook line over the first 2.8 s, and
titles each clip "GTA 6 <moment>: ...". The kit's own tool (OpenShorts) is linked in the guide card.
