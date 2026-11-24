---
name: 3d-animation-styles
description: Make a 3D animated explainer or product video with three.js in one of 15 ready-made styles (Toy Diorama, Soft Clay, Low-Poly, Paper Layers, Inflatable, Glass Lab, Neon Night, Blueprint Build, Voxel, Exploded View, Particle Swarm, Data Towers, Studio Product, Toon Ink, Floating Screens), with sound, rendered to a frame-exact MP4. Use when the user asks for a 3D animation, a 3D explainer, or names one of these styles.
---

# 3D Animation Styles (free from Anylancer.com)

Everything lives in this folder: `engine/stage.js` (the render kit), `engine/sound.js` (sound effects made in code), `engine/three.min.js` (three.js r160, MIT), `styles/*.js` (15 finished reference animations), `player.html` (preview player) and `render.mjs` (MP4 renderer).

## Workflow
1. **Topic, style, format.** Take the user's topic (or script / timed voiceover). If they named no style, pick the best fit from the list below and say why in one line. Format: 9:16 (default for social), 16:9 or 1:1.
2. **Read the reference** `styles/<style>.js` fully. Its `card` is the look; its code shows the materials, lights, camera and motion that make the look. Keep the look, change the story.
3. **Write** `styles/<new-name>.js` registering `(window.STYLES = window.STYLES || {})["<new-name>"] = { name, card, content, duration, samples, fonts, grade, build(S), sound(k) }` (the same form as the references). Plan 3-4 beats that follow from each other; words are short captions pinned with `S.pin` and small labels. End on the payoff. Caption pattern: see `styles/blueprint.js` (`S.label`, then `S.pin(...)` in `update(t)` after `S.cam`; in 9:16 keep words between about 12% and 82% of the frame height). If the topic is a reference's own, make a new, fuller version.
4. **Check stills**: `node render.mjs <new-name> --fmt 9:16 --gpu --stills "0.5,2,4,6,7.8"` and look at every still. Fix framing (subject big, nothing important cut off), legibility, overlaps and dead areas. Repeat until clean.
5. **Render**: `node render.mjs <new-name> --fmt 9:16 --gpu` writes `renders/<new-name>-9x16.mp4` with the full sound mix at about -15 LUFS. With a voiceover: add `--vo path/to/voice.mp3` (the sound kit switches to its quieter voiceover mix).
6. Preview live any time: serve this folder (for example `npx serve`) and open `player.html?style=<new-name>&fmt=9:16`.

Needs Node 18+, ffmpeg on PATH and a browser driver (`npm i puppeteer` once in this folder). `--gpu` uses the graphics card; drop it if WebGL fails.

## The styles
| Style | Look | Best for |
|---|---|---|
| toy-diorama | toy world on a floating slab of land, drone camera | journeys, supply chains, step-by-step places |
| soft-clay | plasticine stop-motion on a paper sweep | growth, nature, kids' science, cooking |
| low-poly | faceted world, triangle sea, gem clouds | weather, nature processes, landscapes |
| paper-layers | cut-paper shadow box with soft layered shadows | light, colour, nature, picture-book stories |
| inflatable | glossy balloon objects that inflate and bounce | energy, filling up, friendly tech |
| glass-lab | lab glass and coloured liquids in a studio | chemistry, density, mixing, measuring |
| neon-night | synthwave grid, neon outlines, bloom | internet, signals, gaming, security |
| blueprint | drawing plots on blueprint paper, stands up into a model | engineering, structures, plans to objects |
| voxel | cubes drop in and build up on a plinth | growth over time, building, maps |
| exploded-view | product comes apart with numbered callouts | what's inside a device, parts |
| particles | 36k glowing points morph between shapes | AI, data, ideas, transformations |
| data-towers | bar chart as an architect's model | any real numbers, growth, comparisons |
| studio-product | dark studio, mirror floor, strip lights | product reveals and launches |
| toon-ink | cel shading, ink outlines, comic captions | action, space, history, kids |
| floating-screens | app screens as cards with glass, rack focus | apps, websites, user flows |

## The STAGE kit (what `build(S)` gets)
- `S.THREE`, `S.K`, `S.scene`, `S.W`, `S.H`, `S.aspect`, `S.portrait`, `S.fps`.
- Camera: `S.cam(pos, target, { fov, aperture, focus, roll })` every update. `S.fitDist(w, h, fov)` = distance at which a w×h region fills the frame (use it so 9:16 and 16:9 both frame well).
- Words: `S.label(text, { h, font, color, bg, border, radius, pad, lit, power, align, extraW, draw })` → plane mesh (`userData.size` = [w, h]). `S.pin(mesh, sx, sy, widthFraction, baseWidth, pop)` keeps it on screen at the focus distance: sharp, drawn on top, sized to the frame. `S.picture(w, h, (ctx, cw, ch) => {...})` for any canvas drawing.
- Light: `S.sun({ pos, intensity, soft, size })` (soft area shadows), `S.spot`, `S.point`, `S.hemi`, `S.env({ top, bottom, boxes, intensity })` (studio reflections), `S.gradientBg(top, bottom, { mid })`, `S.shadowFloor(opacity)`.
- Materials: `S.mat.std / phys / matte / gloss / metal / glass / glow / basic`; `S.noiseTex(...)` for bumps.
- Helpers: `S.mesh(geo, mat, { pos, rot, scale, parent })`, `S.group(parent, pos)`, `K.rbox(w, h, d, r)` (rounded box), `K.sweep(...)` (studio cyclorama), `K.rrectShape`, `K.rng(seed)`, `K.tw(t, a, b, ease)`, `K.keys(t, list)`, `K.prog`, `K.ease.*` (inOut, out, back, spring, bounce, sine...).
- `grade`: `{ exposure, tonemap: "aces" | "neutral" | "none", bloom, bloomThreshold, saturation, contrast, vignette, grain, warm }`. `samples` = renders averaged per frame (16-28). 
- Rules: `update(t)` sets the whole scene for time t (it runs many times per frame for blur and soft shadows); no `Math.random`, `Date` or timers; no downloaded models or textures.

## The SOUND kit (what `sound(k)` gets)
`k.at(time, voice, { vol, pitch, pan, f, dur })`, `k.bed(name, t0, t1, { vol, pitch })`, `k.chords(t0, t1, ["C4 E4 G4", ...], { bpm, vol, arp })`, `k.voiceover` (true when a voiceover is used).
Voices: pop click tick tap thud knock wood clay paper whoosh swish rise drop hit boom chime bell glass ping sparkle coin pluck zap bubble spring snap blip type servo. Beds: room wind hum neon rain water crowd motor. Put a sound on every visible event at its exact time.
