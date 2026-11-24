# Science Story Shorts (free kit from Anylancer.com)

This folder makes animated vertical Shorts (1080x1920, 30 fps) of true stories with a hidden science twist:
round-head cartoon characters in rich 3D places, one-word captions, a cut every 2-3 seconds, music and a sound on every cut.
Everything is drawn in code by the engine in `engine/`. No video generator, no stock footage, no paid tools needed.

The person you're helping may not be technical. Keep replies short and plain, do the work yourself, and ask only when
you need a choice from them (which story, which voice).

## The two commands
- `/find-story [area]`: research 3-4 real stories and offer them as numbered options (saved to `topics/latest_options.md`).
- `/make-video <number | a sentence>`: make the chosen story into a finished short in `stories/<slug>/`.

## "Run the setup for this folder"
When asked to set up (or before the first `/make-video`), check these and report in one short list:
1. **Python 3**: `python3 --version` (Mac) / `py --version` or `python --version` (Windows). Missing → tell them to install
   Python 3.12 from python.org (Windows: tick "Add python.exe to PATH") and stop. The kit's scripts use only the standard library.
2. **A browser for stills**: Chrome or Edge (`scripts/stills.py` finds it by itself). Missing → ask them to install Chrome.
3. **Test**: pack the example and make 3 stills:
   `<py> scripts/pack.py examples/the-clock-that-saved-sailors/story.js examples/the-clock-that-saved-sailors/voice.mp3 -o out/test.html --words examples/the-clock-that-saved-sailors/words.json`
   then `<py> scripts/stills.py out/test.html 2 20 58`. Look at the PNGs. If they look right, setup is done.
4. **Optional one-click MP4**: `node --version` and `ffmpeg -version`. If both exist, offer (ask first) to run
   `npm install puppeteer-core` inside this folder so `node scripts/render.mjs <file>.html --gpu` can render MP4s directly.
   Without it, every short still exports: open the HTML in Chrome and press **Export video**.
Everything stays inside this folder. Never install anything else.

## Files
- `engine/` the cartoon engine (three.js renderer, round-head cast, rooms, world, captions, audio, crowd sounds incl. moo).
- `scripts/` `pack.py` (story → one HTML player), `stills.py` (PNG frames to check), `voice.py` (free system voice,
  ElevenLabs, or the person's own recording → word timings), `render.mjs` (frame-exact MP4, optional).
- `references/` `formula.md` (the six beats, script rules, titles), `workflow.md`, `engine.md` (every helper), `checklist.md`, `script.md`.
- `examples/` three finished shorts with their story.js, script, facts and player: the clock (sea, storm, hall, workshop, space),
  sprouting cows (farm, village, study, inside the body, a custom cow and germ characters), the map (study, top-down desk,
  ice, ship, a cross-section diorama). Copy their structure, never their stories.
- `stories/` new shorts go here, one folder each. `topics/used.txt` lists stories already made (add every new one).

## Rules
- True stories only. Keep the drama, keep the facts: real dates and numbers, no invented quotes or headlines.
  Write what is dramatized in `facts.md` ("the experts laughed" when they only doubted).
- No real living people as characters, no brand logos, nothing graphic (harm happens off screen or as a cartoon gag).
- Make it yours: one signature look for the hero, original stories, the person's own voice if they can. YouTube does not
  pay for reused or mass-produced content.
