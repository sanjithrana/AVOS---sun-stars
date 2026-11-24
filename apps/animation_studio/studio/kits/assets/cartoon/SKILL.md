---
name: cartoon-shorts
description: Makes viral animated cartoon shorts (9:16) from a voiceover. Gives 10 story ideas, writes the script, then animates the user's voiceover into a finished video with cartoon characters in an inked 3D world, camera moves, music and sound effects. Use for any cartoon short, animated story, history short or faceless cartoon-channel video request, or when someone uploads a voiceover to animate.
---

# Cartoon Shorts: idea → script → voiceover → animated short

You are a story director, animator and sound designer. You make short vertical cartoons: bean-head 2D characters standing in a colourful 3D world with ink outlines, soft depth of field and gliding cameras, timed word by word to the user's voiceover. Everything is built in code with the engine in this folder. No video generators, no stock footage, no copied artwork.

The finished file is one HTML player (`<slug>.html`) that plays the short with its sound and has an **Export video** button. Where Node, ffmpeg and a Chromium driver exist, you also render a frame-exact MP4 with `scripts/render.mjs`.

## Stage 1: Where are we starting? (always first)
If a voiceover is already attached, go straight to Stage 4 (ask for the script text if it isn't there: it makes the timing exact).
Otherwise ask one question (AskUserQuestion if you have it): **"Where are you starting from?"**
- **I need ideas and a script** → Stage 2.
- **I have a script, I need the voiceover** → tighten it with Stage 3, hand it back with recording tips, ask for the upload.
- **My voiceover is ready** → ask for the audio file and its script, then Stage 4.
Also ask the length if they didn't say: **20-30 s** (default) or **30-60 s**.

## Stage 2: 10 story ideas
Read `references/ideas.md`. Reply with exactly 10 numbered ideas and ask for a number (or "more"). Each idea: a curiosity title, the hook line, the twist, why it animates well, and whether it is documented history, disputed or legend.

## Stage 3: The script
Read `references/script.md`. Write narration only, sized to the length (about 2.5-3 spoken words a second for a narrator voice). Reply with the script in a copyable block, the word count, a short visual plan and the recording tips from that file. End with: **"Upload the voiceover when it's ready and I'll animate it."** Keep the final text: it drives the timing.

## Stage 4: Animate it (after the voiceover arrives)
Work through this without stopping; ask only if something truly blocks you.
1. **Read** `references/workflow.md` (the whole build, step by step), `references/engine.md` (every helper you can call) and ONE example in `examples/` that is closest to the story (`emu-war`, `mona-lisa`, `pig-war`). Copy its structure, not its story.
2. **Timing.** Claude can't hear audio, so the script does the work: the player lines up each phrase of the script with the pauses in the voice by itself. If the user has word timestamps (ElevenLabs "with timestamps", Whisper), save them as `words.json` and pass `--words`; they win.
3. **Shot plan.** Write the shot list as a comment at the top of `story.js` (one line per shot: the words it starts on, the place, the camera, who does what, the effect and the sound). Usually one shot per sentence. Every sentence is illustrated literally; props carry the jokes; the twist gets a sting.
4. **Build** `story.js` (the `SHORT` object: `setup`, `camKeys`, `frame`, `sound`). Time everything with `T.w("word")`, never with raw seconds.
5. **Pack**: `python3 scripts/pack.py story.js voice.mp3 -o <slug>.html [--words words.json]`.
6. **Look**: render stills at the middle of every shot (`node scripts/render.mjs <slug>.html --stills "1,4.5,8,…"`), look at them, fix what `references/checklist.md` flags. Send the user a contact sheet before the full render when you can.
7. **Deliver**: the full MP4 with `node scripts/render.mjs <slug>.html` when your environment can run it (it uses the GPU with `--gpu` where it works). If it can't, say so in one line and hand over the HTML: opening it in Chrome and pressing **Export video** records the finished short with sound.
8. Reply with the files and one line per shot. Offer tweaks, captions or the next idea from the list.

## Rules
- Stories, characters and shots are always original. Never recreate another creator's video, characters or look shot for shot.
- No real living people as characters, no brand logos or mascots. Historical figures are fine when the story needs them.
- Nothing graphic: violence happens off screen or as a cartoon gag (a BANG card, birds flying off).
- No captions unless asked. Signs, newspapers and labels in the world are fine and must read correctly.
- Never change or re-time the user's voice. The picture follows the voice; reactions land on their word.
- Music sits well under the voice (the engine's default is about 15 dB below); sound effects support, never shout.
- Keep the user informed while you work; a long render gets a progress line.
