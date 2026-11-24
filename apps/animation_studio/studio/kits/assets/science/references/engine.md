# Engine reference (everything `story.js` can call)

All helpers live on the global `CS`. three.js is the global `THREE`. Units are metres; y is up; the camera usually looks toward -z.
A person card is ~2 m tall, an emu ~2 m, a pig ~1 m. The frame is 1080x1920 (9:16), 30 fps.

## The story file
```js
window.SHORT = {
  title: "The Pig War", slug: "the-pig-war",
  script: `…the exact narration text…`,      // drives the timing
  tail: .9,                                  // seconds after the voice ends
  setup(T) { /* build the world and the cast ONCE; store them on `this` */ this.cam = CS.camPath(this.camKeys(T)); },
  camKeys(T) { return [ /* camera keys, see Camera */ ]; },
  frame(t, T) { /* set light, camera, lens, poses, effects for time t. Pure: same t → same picture */ },
  sound(A, T) { /* music + sound effects */ },
};
```
`frame` must be a pure function of `t`: no `Math.random()`, no clocks. Use `CS.rand(seed)`, `CS.noise1(x, seed)`.

## Timing: `T`
- `T.w("words", after = 0)` start time of the first match of those words at or after `after` (case and punctuation ignored).
- `T.we("words", after)` end time of that match. `T.p(i)` / `T.e(i)` start / end of phrase i. `T.duration`.
- Repeated words: ALWAYS pass `after` (`T.w("major", 20)`), or you get the first one.
- Helpers: `CS.seg(t, a, b)` → 0..1 progress, `CS.lerp`, `CS.clamp`, `CS.ease.smooth | inOut | out | in | back | spring | lin`.

## World: `CS.world` (call it `Wd`)
- `Wd.ground([w, d], mat, parent, {tile, x, y, z})` flat plane. Painted materials: `Wd.painted("grass" | "dirt" | "sand" | "wheat" | "planks" | "stone" | "brick" | "plaster" | "roof" | "marble" | "wallpaper" | "water" | "metal" | "wood" | "flat", colour, opts)`.
- `CS.mat(colour, {tex, texOpt, repeat, emissive, emissiveI, side})` toon material.
- Shapes (y = bottom): `Wd.box(w, h, d, mat, [x,y,z], parent, {tile, rot, shadow})`, `Wd.cyl(rTop, rBot, h, mat, p)`, `Wd.cone(r, h, mat, p)`, `Wd.ball(r, mat, [x,y,z], parent, {scale})`, `Wd.roof(w, d, h, mat, p)`.
- Scenery: `Wd.hill(r, colour, [x,0,z], parent, {squash})`, `Wd.mountain(r, h, colour, p)`, `Wd.tree("round"|"pine"|"cypress"|"gum"|"palm", h, p, parent, seed)`, `Wd.clouds(n, radius, height, seed, parent, {cz, size})`, `Wd.water(w, d, colour, p)` (+ `.flow(t)`), `Wd.tufts(n, [x0,z0,x1,z1], {colour, h, r}, seed, avoid)` (wheat, grass, crops), `Wd.scatter(n, area, seed, (i, x, z) => …, avoid)`.
- Buildings and props: `Wd.house({w, d, h, wall, roof, tex, rot, windows}, p)`, `Wd.fence([x0,z0], [x1,z1])`, `Wd.textPanel("TEXT", {w, h, bg, fg, size})` (signs, never mirrored), `Wd.frame(w, h, canvasOrTexture, {color})` (+ `.setImage()`), `Wd.lamp(p)` (`.globe` glows), `Wd.clock(r, p)` (`.set(hours)`), `Wd.flag("stars"|"union"|"#colour"|drawFn, p, parent, {pole, w, h})` (`.wave(t)`, `.cloth.position.y` raises it), `Wd.truck({color})` (`.spin(distance)`, `.bed` height), `Wd.gun()` (`.pivot`), `Wd.cannon(p)` (`.barrel`, `.mouth`), `Wd.ship({flag, hull})` (`.bob(t)`, bow along +x), `Wd.windmill(p)` (`.rotor`), `Wd.crate(s, p)`, `Wd.hay(p)`.
- Locations: build each place in its own set: `const G = CS.set("museum")`, pass `G` as `parent`, and call `CS.showSet("museum")` in `frame`.

## Cast (2D drawings standing in the 3D world, always facing the camera)
- `CS.person(spec, {h, scale, parent})` → card. Spec (fixed look):
  `{ skin, hair: {style: "short"|"side"|"curly"|"bun"|"long"|"balding"|"bald", color}, hat: {type: "slouch"|"peaked"|"kepi"|"shako"|"bowler"|"top"|"straw"|"beret"|"flat"|"helmet"|"cap"|"wide", color, band}, top: {type: "shirt"|"uniform"|"redcoat"|"suit"|"coat"|"overalls"|"smock"|"dress", color, accent, tie, bib}, pants, shoes, mustache: "thin"|"walrus"|"handlebar", beard: true, beardColor, nose: "big", glasses: true, medal: true, size }`
- Pose each frame: `card.pose({ face, arms: [left, right], look, lookY, blink, talk, step, stride, prop, bulge, beardLen, wave, jump })`
  - faces: neutral happy joy laugh shock scared angry furious smug sad worried sly determined sleepy bored proud stern awe
  - arms: hang hip point up wave salute thumb hold fist shrug cheek carry reach back aim tray scratch (or `[shoulderDeg, elbowDeg]`)
  - props: `{kind: "rifle"|"newspaper"|"board"|"sign"|"flag"|"potato"|"painting"|"lantern"|"telescope"|"cup"|"cards", hand: "L"|"R", text, color}`
  - `step` 0..1 walk phase with `stride` 0..1; `look` -1..1 moves the eyes; `blink: CS.blinkAt(t, seed)`.
- Animals: `CS.emu()` → `.pose({face: "norm"|"angry"|"smug"|"shock"|"happy", run, step, peck, beak, neck, look, blink, hat: "helmet"|"slouch"})`; `CS.pig()` → `.pose({face, trot, step, munch, food, angel, look, blink})`.
- Every card: `.at(x, y, z)` (y = ground under it), `.flip(true)` (mirror), `.show(bool)`, `.group` / `.pivot` for extra moves (`pivot.rotation.z` tilts at the feet).
- Keep them alive: `CS.alive(card, t, seed, {tilt, bob, sway})` every frame. Quantise fast-changing values (`Math.round(x * 8) / 8`) so drawings are reused.
- New characters: write a draw function on a 600x1000 canvas (soles at y 975, plum outline `CS.INK`, `CS.draw.fillStroke`) and wrap it with `CS.card({draw, cw, ch, h, scale, design})`.

## Effects (sprites, deterministic)
- `CS.burst(kind, [x,y,z], t0, {n, size, spread, up, gravity, dur, seed, grow, colors, parent})` → call `.update(t)` every frame.
- `CS.pop(kind, [x,y,z], t0, t1, {size, o: {text}})` → one sprite that pops in and out; `.update(t)`.
- kinds: dust smoke star spark feather bang (text "BANG!") zzz ! ? sweat heart confetti potato paper (text) note cloud speed bird.
- `CS.sprite(CS.fxTex(kind), size, parent)` for your own moving sprite.

## Light, camera, lens
- `CS.light("day"|"golden"|"dusk"|"night"|"indoor"|"dawn")`, or blend: `CS.light("day", "night", k)`. Make your own preset: `CS.LIGHTS.myLook = Object.assign({}, CS.LIGHTS.day, {hor: "#…", top: "#…", az, el, card})`.
- `CS.shadowAt(x, z, size)` centre the sun's shadows on the action every frame.
- `CS.camPath([{t, p: [x,y,z], l: [lookX,lookY,lookZ], fov, roll, e}])` → `cam(t)`. `e` = how we arrive at that key: smooth (default) | out | in | inOut | lin | back | cut.
- `CS.cam(c, t, {shake: CS.shake(t, t0, dur, amp), creep})`.
- `CS.lens({focus: metres or [x,y,z], blur: 0..0.5, flash: 0..1, flashColor})`. Close-ups 0.25-0.4, wides 0-0.1. A time jump = a white flash peaking on its word.
- Narrow frame: at distance d and fov 40, the visible width is only about ±0.36·d. Stage people in depth, not side by side.

## Sound: `A`
- `A.music({bpm, key, sections: [{at, style}], end})`; styles: march sneak folk whimsy tense drone stop.
- `A.sfx(name, t, gain, opt)`; names: whoosh swish pop boing thunk step ting magic sting crash bang boom rattle squawk boomdrum oink crowd gasp creak paper engine splash bell drumroll snore kaching slideup slidedown click tick horn cannon hit wind waves birds flap.
- Levels: `CS.audio.levels = {voice: 1, music: .06, sfx: .36}` (music stays ~15 dB under the voice).

## Science Story Shorts additions
### Round-head characters (the main look)
`CS.person({style: "round", hair: {style: "short"|"side"|"curly"|"bun"|"long"|"tufts"|"wig"|"bald"|"none", color}, hat: {type: …same as above… | "tricorn" | "crown" | "nurse"}, top: {type: "coat"|"suit"|"uniform"|"redcoat"|"smock"|"dress"|"robe"|"shirt", color, vest, shirt, tie, trim, apron}, pants, shoes, mustache, beard, glasses, monocle, skin, hand, size}, {parent: G})`
White round head, dot eyes, stick arms and legs, white mitten hands. Same `pose()` as above. Hands and held props draw in front of the head, so a raised watch or phone is visible. Extra props: `watch` ({r, hours}), `phone`, `scroll`, `book`, `bowl`, `chalk`. Arms can be `[shoulderDeg, elbowDeg]`: `[120, 30]` holds something up beside the face.

### Rich places
- `Wd.room({w, d, h, wall, wallTex: "stripes"|"planks"|"plaster"|"wallpaper", wain, wainH, floor, floorTex: "checker"|"planks"|"marble"|"tiles", floor2, windows: [x…], winH, door: x, doorSign, sconces: [x…]}, G)` back wall at z = -d/2, open towards the camera.
- `Wd.archWindow`, `Wd.door`, `Wd.sconce`, `Wd.throne([x,y,z], {}, G)`, `Wd.tallClock({color}, G)` (`.swing(angle)`, `.face.set(hours)`), `Wd.globe(r, {wedge: "#ffb02e"}, G)` (`.spin.rotation.y`), `Wd.satellite({}, G)`, `Wd.rocks(n, [x0,z0,x1,z1], {size}, seed, G)`.
- `Wd.board("TITLE\nline 2", {w, h, head: "#ffd23a"}, G)` chalkboard; `.write(text, k)` reveals k (0..1) of the text as if written.
- Painted textures added: `checker`, `tiles`, `panels`, `stripes`, `carpet`.

### Shots: `CS.shots(T, list)`
Each item: `{at: "words" | seconds, after, set, light: "day" | ["day", "golden", .4], from: {p, l, fov, roll}, to: {…}, ease, blur, focus, shake, shakeAt, shakeDur, flash: t => 0..1, id, cutSfx, cutGain}`. It cuts .06 s before the words. `plan.apply(t)` does showSet + light + camera + lens + shadows and returns `{i, k, shot, local}`. `plan.cutSounds(A, ["whoosh", "swish"], .42)` puts a sound on every cut.

### Overlay (drawn on top of the picture, also in Export and render.mjs)
- Captions: `SHORT.captions = {y: 1390, size: 112, subs: {"seventeen thirty": "1730"}, hide: [[t0, t1]], upper: false}`. One or two words at a time, `*star*` words in yellow. Title cards hide them by themselves.
- `CS.title("19 YEARS", t0, t1, {size, sub: "later…", color})` big outlined title card (blur the picture with `blur` in the shot).
- `CS.rain(t0, t1, {n, speed, angle})`, `CS.bolt(t0, x, {seed})`, `CS.flashAt(t, [times])` (use as a shot's `flash`).
- `SHORT.overlay(g, t, T)` your own 2D drawing on top; `CS.outlined(g, text, x, y, {size, color})` draws outlined text.

### Recorded crowd sounds
`A.sfx("laugh" | "laugh2" | "gasp" | "murmur" | "cheer" | "ooh" | "moo" | "moo2", t, gain, {dur, rate, offset})`, gain ~.4-.7. Any MP3 you drop into `engine/sfx/` becomes a sound with its file name.

### Lights for story moods
Make your own from a preset: `CS.LIGHTS.storm = Object.assign({}, CS.LIGHTS.night, {top: "#0b1430", hor: "#2c3e66", fog: [70, 300]})`. The example has bright, hall, shop, fog, storm, voyage, space and city.
