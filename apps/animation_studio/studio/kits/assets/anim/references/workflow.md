# Workflow: script → beats → frames

## 1. Break the script into beats
Read the script once for the story, then once for pictures. Every sentence usually holds something to show: a subject, an action, a change, a comparison, a number, a payoff. Write a beat list before any code:

| # | start-end (s) | words | what we see | camera | transition out |
|---|---|---|---|---|---|

- Timing: with a voiceover, the audio length wins (measure it, never speed it up). Without one, about 150 words a minute plus short pauses after big lines.
- A beat lasts as long as its idea needs, usually 2-5 s. A punchline can be 1 s; a process may need 6.
- The first beat must show the subject or the most interesting moment at once. No logos or slow fades at the start.
- If a beat only decorates, replace it with one that explains or entertains.

## 2. Decide the cast and the world (continuity sheet)
Write down, once, how each recurring thing looks: silhouette, colours, size relative to others, clothing or markings, the light direction, the typeface. Reuse those exact values in every beat. A character never changes look unless the story says so.

## 3. Draw it in the style's own language
Open the style file and translate every beat into that medium: boiling ink lines for Stickman, cut paper with shadows for Paper Cut-out, typed characters for ASCII Art, and so on. Everything in the frame (people, sky, ground, text, effects) follows the style, not only the hero object.

## 4. Build the file
Start from `player-template.html`:
- Put all drawing in `draw(t)` where `t` is seconds. It must give the same picture for the same `t` every time, in any order (no `Math.random()` at draw time, no clocks, no `requestAnimationFrame` inside `draw`). Use the template's seeded `rand()` and precompute random layouts once.
- Set `CONFIG` (width, height, fps, duration, background).
- 2D styles: draw on the main canvas. 3D styles: render three.js into the template's WebGL canvas, then copy it onto the main canvas (this is also where film grain, blur or any overlays happen).
- Load fonts and textures before setting `window.ready = true`.
- Plan motion with easing: things accelerate and settle; nothing moves at constant speed unless it's travelling.

## 5. Look before you hand over
Open the file, scrub through it, and look at the first frame, every beat change and the last frame. Fix anything from `checklist.md` that fails. Then export (Export button, or `scripts/render.mjs` when available) and check the result plays, has the right size and length, and includes the audio if there was any.

## 6. Audio and captions
- Use only audio the user gives you or creates. Don't invent music or voice.
- Captions only when asked: a few words at a time, from the real script, inside the safe area, styled to fit the look.
- Labels that belong to the picture (a sign, a diagram arrow, a comic sound word) are part of the art, not captions.

## 7. Edits later
Keep the beat list at the top of the HTML in a comment. When the user asks for a change, change that beat only and leave the rest as it was.
