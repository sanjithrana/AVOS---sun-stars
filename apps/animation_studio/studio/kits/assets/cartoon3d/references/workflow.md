# Workflow: voiceover → finished short

## 0. Files
Work in a project folder: `story.js`, `voice.mp3` (the user's file, never edited), `script.txt`, and `words.json` if exact word timings exist. The engine, `scripts/pack.py` and `scripts/render.mjs` stay in this skill folder.

## 1. Shot plan (before code)
Write it as the comment at the top of `story.js`:
`#  starts on "word"   place · camera · who does what · effect · sound`
- One shot per sentence (merge tiny phrases). Frame 0 is already the hook image: it must work as a thumbnail.
- Illustrate literally. A number gets a crowd, a place gets an establishing wide, a reaction gets a close-up.
- Vary shot sizes: hook close-up → wide reveal → medium → insert on the key object → reaction close-up → payoff.
- Light tells time: day for normal, golden for drama or "later", night-blue for secrets. A time jump gets a white flash.
- The twist: the music stops a beat before it, a sting on its key word, a slow push-in with a small camera roll, and the final visual gag lands on the very last word.

## 2. Build the world once (`setup`)
- One set per location (`CS.set("farm")`). Ground → big shapes → props → background (hills, trees, clouds) → characters → effects.
- Re-use the example worlds for structure; invent the look for the new story.

## 3. Animate (`frame`)
Order inside `frame(t, T)`: work out which shot we're in from `T.w(...)` → `CS.showSet` → `CS.light` → camera (`this.cam(t)` + `CS.cam`) → `CS.lens` → `CS.shadowAt` → world motion → every character's pose and position → `fx.update(t)`.
- Characters never freeze: `CS.alive` + blinks on everyone, every frame.
- Actions: anticipation → move with `ease.back` overshoot → settle. Impacts get a dust burst and a tiny camera shake.
- Something always moves: flags, water, clouds, a windmill, idle bobbing.
- Cards face the camera, so "people looking at each other" = eyes turned with `look`, and crowds that stare at something are shot from that something's side.

## 4. Sound (`sound`)
- One music style for the story, a different style or `stop` for the twist, back on for the payoff.
- An effect on every visible action: whooshes on camera cuts, pops on things appearing, thunks on landings, a sting on the twist.

## 5. Pack, look, fix, render
1. `python3 scripts/pack.py story.js voice.mp3 -o <slug>.html [--words words.json]`
2. Stills at the middle of every shot: `node scripts/render.mjs <slug>.html --stills "2,5.5,9,…" [--gpu]` and look at every one.
3. Fix with `references/checklist.md`: faces out of frame, characters hidden behind props, empty frames, a beat that lands late, text that is mirrored or cut.
4. Full render: `node scripts/render.mjs <slug>.html [out.mp4] [--gpu]` (needs Node 18+, ffmpeg and puppeteer/playwright; with `--gpu` about 0.1 s a frame, without a GPU 1-4 s a frame). No Node or ffmpeg? Hand over the HTML: Chrome + **Export video** records it with sound.
