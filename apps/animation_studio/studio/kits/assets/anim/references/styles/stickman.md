# Stickman

Black hand-drawn lines on white paper: circle heads, single-line bodies, big readable poses. The joke is in the timing.

## Must have
- Off-white paper background with a faint grain. Ink lines 7-10 px, round caps, pure black or near-black.
- "Line boil": every line is a short polyline whose points jitter by 1-2 px, re-seeded 8 times a second, so the drawing feels alive.
- Figures built from a tiny skeleton (hip, knees, shoulders, elbows, head) with angles you animate, not from pre-drawn frames.
- At most one accent colour for the thing the story is about. Everything else is black on white.
- Simple doodle setting: a ground line with grass ticks, outline clouds, a sun with ray dashes. Fill the lower frame with light pencil hatching or doodles so it never feels empty.

## Make any script work
- People: pose is the whole performance. Anticipation (crouch), action, overshoot, settle. Faces are two dots and a mouth (dot, line, "o", X eyes when dazed).
- Places and objects: outline them in the same line weight (boxes with an X brace, seesaws, doors, laptops).
- Ideas: diagrams, arrows, thought clouds and labels drawn in the same ink, as if sketched live.
- Comedy: bonk lines, dizzy stars, a fall on the punchline word.

## Motion
Snappy poses with eased transitions between them; 2-3 frames of hold on key poses. Camera pans are smooth; the boil never stops.

## Text
Handwriting font (Patrick Hand, Gochi Hand) in the same black, or hand-lettered words drawn as paths. 2-5 words.

## Avoid
Perfect vector lines with no boil, grey mush, detailed faces, many colours, tiny figures (keep them at least 25% of frame height).

## Code starter
```js
let boil = 0;   // set in draw: boil = Math.floor(t * 8)
function ink(pts, w = 9, col = "#141414", seed = 1) {
  ctx.save(); ctx.strokeStyle = col; ctx.lineWidth = w; ctx.lineCap = ctx.lineJoin = "round"; ctx.beginPath();
  pts.forEach(([x, y], i) => { const jx = (rand(seed * 97 + i * 13 + boil * 7) - .5) * 3.2, jy = (rand(seed * 53 + i * 31 + boil * 11) - .5) * 3.2; i ? ctx.lineTo(x + jx, y + jy) : ctx.moveTo(x + jx, y + jy); });
  ctx.stroke(); ctx.restore();
}
// stick figure: angles in radians (0 = limb straight down, torso upright)
function stick(x, footY, p, s = 1.4) {
  const L = 56 * s, TO = 96 * s, HR = 33 * s, hip = [x, footY - 2 * L];
  const limb = (o, a1, a2, len) => { const k = [o[0] + Math.sin(a1) * len, o[1] + Math.cos(a1) * len]; ink([o, k, [k[0] + Math.sin(a2) * len, k[1] + Math.cos(a2) * len]]); };
  limb(hip, p.ll ?? -.2, p.ll2 ?? -.1, L); limb(hip, p.lr ?? .2, p.lr2 ?? .1, L);
  const sh = [hip[0] + Math.sin(p.lean || 0) * TO, hip[1] - Math.cos(p.lean || 0) * TO]; ink([hip, sh]);
  limb(sh, p.al ?? -.4, p.al2 ?? -.2, 54 * s); limb(sh, p.ar ?? .4, p.ar2 ?? .2, 54 * s);
  ctx.fillStyle = "#fbfaf6"; ctx.beginPath(); ctx.arc(sh[0], sh[1] - HR - 10, HR, 0, 7); ctx.fill();
  const c = []; for (let i = 0; i <= 28; i++) c.push([sh[0] + Math.cos(i / 4.46) * HR, sh[1] - HR - 10 + Math.sin(i / 4.46) * HR]); ink(c);
}
```
