# Engine reference (everything `story.js` can call)

All helpers live on the global `CS`. The frame is 1080 x 1920 (9:16), 30 fps. Coordinates are design pixels: x right, y down.
Every drawing function is pure: the same `t` always draws the same picture. Never use `Math.random()`; use `CS.rand(seed)` and `CS.noise1(x, seed)`.

## The story file
```js
window.SHORT = {
  title: "Why Is the Ocean Salty?", slug: "salty-ocean",
  script: `…the exact narration…`,            // drives the timing; *word* = yellow caption
  tail: 1.2,                                  // seconds after the voice ends
  captions: { y: 1440, size: 108, subs: { "twenty five": "25" }, hide: [[t0, t1]] },   // or false
  shots(T) { return [ /* shot list, see below */ ]; },
  sound(A, T) { /* music + effects */ },
  overlay(g, t, T) {},                        // optional: draw on top of everything (screen space)
  flash(t, T) { return 0; },                  // optional: white flash 0..1
};
```

## Timing: `T`
`T.w("words", after = 0)` start of the first match at or after `after`; `T.we(...)` its end. `T.duration`. Helpers: `CS.seg(t, a, b)` → 0..1, `CS.lerp`, `CS.clamp`, `CS.ease.smooth | inOut | out | in | back | spring | lin`.

## Shots
Each shot: `{ at: "words" | seconds, after, lead, tr, cam, shake, draw(g, s) }`
- `at`: the shot starts .06 s before those words (`lead` changes that). The first shot always starts at 0.
- `tr`: how we ARRIVE: `"whip"` (default, a blurred pan), `"pop"` (punch-in + white flash, for punchlines), `"cut"`.
- `cam: { from: [x, y, zoom, rotDeg], to: [...], ease, drift }`: the view centre in design pixels. `[540, 960, 1]` = no move. Zoom 1.3-1.5 = medium, 2 = face close-up. A slow push-in is `to` zoom +0.08.
- `shake: [[t0, dur, amp], …]` camera shake (amp 12-30).
- `draw(g, s)`: draw the world in design pixels. `s = { t, lt (time in shot), k (0..1 through the shot), dur, T, shot, cam, toScreen(x, y), screen(fn) }`.
  `s.screen(g => …)` draws in screen space (zoom circles, labels that must not be cropped); `s.toScreen(x, y)` converts a world point.

## Stick people: `CS.stick(g, x, y, o)` (feet at x, y; scale 1 ≈ 590 px tall)
`o = { s, face, look (-1..1), lookY, blink, talk (0/1), t, shirt, pattern: "plain"|"stripes"|"dots"|"hoodie"|"chef"|"suit", stripe, belt, shoes,
hat: "cap"|"chef"|"helmet"|"party"|"tuft"|"bun"|"curl", hatColor, glasses, arms: [L, R], legs: [L, R], step (walk phase 0..1), stride,
lean (deg), bob (px), squash, stretch: [sx, sy], headTilt, green (0..1 sick tint), hold: { R: (g, x, y, ang) => drawProp, L: … }, shadowA }`
- faces: neutral happy joy laugh shock scream worried sad cry sob angry smug sick yuck dizzy wow curious think sleepy ko love
- arms: hang hip up wave point shrug cheek head fist think reach hold cross back low wide, or `[shoulderDeg, elbowDeg]` (0 = down, + = outwards)
- legs: stand wide sit kick jump tip, or `[hipDeg, kneeDeg]`
- Keep them alive: spread `CS.alive(t, seed)` into the options (bob, lean, blink). `CS.talk(t, T, from, to)` flaps the mouth.
- Rotate a whole person: `g.save(); g.translate(x, y); g.rotate(a); CS.stick(g, 0, 0, o); g.restore();`
- Faces on anything: `CS.drawFace(g, cx, cy, r, {face, t, blink})` (onions, clouds, suns, salt crystals…).

## Places
- `CS.sunnyDay(g, t, {top, bottom, sunX, sunY, sunFace, hillY, groundY, ground})` sky + sun + clouds + hills + meadow with flowers.
- Pieces: `CS.sky(g, top, bottom)`, `CS.sun(g, x, y, r, t, {face, rays})`, `CS.cloud(g, x, y, s, {color, shade})`, `CS.clouds(g, t, [[x, y, s]…], speed)`, `CS.hills(g, y, colour, {amp, freq, seed})`, `CS.meadow(g, y, t, {color, n, seed})`.
- `CS.kitchen(g, t, {wall, tile, counterY})` tiled wall, window, shelf with jars, counter. `CS.backdrop(g, c1, c2)` soft studio light.
- `CS.space(g, t, {c1, c2, n})` twinkling stars; `CS.planet(g, x, y, r, colour, {ring})`; `CS.blackHole(g, x, y, r, t, {tilt})`.
- `CS.sea(g, y, t, {color})` moving waves; `CS.mountain(g, x, y, w, h, colour, snow)`; `CS.rock(g, x, y, s, colour, seed)`; `CS.rainDrops(g, t, [x0, y0, x1, y1], {n, speed, r})`.

## Props
`CS.onion(g, x, y, s, {cut, rot, face, t})`, `CS.knife(g, x, y, ang, s)`, `CS.board(g, x, y, w, h)`, `CS.glass(g, x, y, s, fill, colour)`, `CS.crystal(g, x, y, s, ang)`,
`CS.sign(g, x, y, "TEXT", {w, h, bg, fg, size})`, `CS.puffy(g, x, y, r, {color, face, t})` (gas, smoke, cloud buddies), `CS.drop(g, x, y, r)`.
Shapes: `CS.circle`, `CS.ell`, `CS.rrect`, `CS.seg2` (thick line), `CS.shadow`, `CS.fs(g, fill, lineWidth)` (fill + ink outline of the current path). `CS.shade(hex, k)`, `CS.mix(a, b, k)`.
New props: write a function in `story.js` with the same ink outline (`CS.INK`, line width 6-9).

## Bubbles, zooms, effects
- `CS.thought(g, cx, cy, w, h, [tailX, tailY], k, inside(g))`, `CS.speech(g, cx, cy, "text", k, {size, tail})`.
- `CS.zoom(g, cx, cy, r, k, inside(g, r), {from: [x, y], ring})` a magnifier into a detail (use inside `s.screen`).
- `CS.burst(g, x, y, r, k, {color, text, size})` comic burst, `CS.pop(g, x, y, "!", k)`, `CS.sparkles(g, x, y, r, t, k)`, `CS.speedLines(g, cx, cy, t, alpha, {r0, n})`,
  `CS.sweat(g, x, y, t)`, `CS.tears(g, cx, eyeY, s, t, amount)`, `CS.stinkLines(g, x, y, t)`, `CS.arrow(g, x0, y0, x1, y1, k, {color, lw, dash})`, `CS.wisp(...)`.
- Text: `CS.label(g, "TEXT", x, y, {size, color, ink, scale, rot, alpha})` outlined cartoon text.
- `k` is usually `CS.seg(t, start, end)`: 0 before, grows, 1 after.

## Sound: `A`
- `A.music({style, bpm, key, sections: [{at, style}], end})`; styles: whimsy folk march sneak tense drone stop.
- `A.sfx(name, t, gain, opt)`: whoosh swish pop boing thunk step ting magic sting crash bang boom rattle squawk boomdrum oink crowd gasp creak paper engine splash bell drumroll snore kaching slideup slidedown click tick horn cannon hit wind waves birds flap, plus the recorded laugh laugh2 gasp murmur cheer ooh moo moo2 (any MP3 dropped in `engine/sfx/` becomes a sound named after the file).
- `CS.cutSounds(A, T, ["whoosh", "swish"], .4)` puts a sound on every transition.
- Levels: `CS.audio.levels = {voice: 1, music: .06, sfx: .36}`.
