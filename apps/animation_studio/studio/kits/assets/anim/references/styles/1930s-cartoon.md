# 1930s Cartoon

Rubber-hose animation on old black-and-white film: thick ink outlines, pie-cut eyes, everything bouncing on the beat, film grain and flicker.

## Must have
- Greys only (paper white, two light greys, a dark grey, ink black), plus at most one hand-tinted colour for the hero.
- Thick black outlines (8-10 px) around every shape; flat grey fills.
- Characters and buildings with pie-cut eyes (black pupil with a wedge cut out), big grins, white gloves, rubbery limbs with no elbows.
- Everything bobs to a steady beat (twice a second): clouds, buildings, the sun, trees, using `abs(sin)` bounces.
- Film finish: grain overlay re-seeded every frame at 24 fps, brightness flicker, gate weave (whole frame jitters 2 px), vertical scratches, dust specks, vignette.

## Make any script work
- Gags: a spring boxing glove, a jack-in-the-box, an anvil, a banana peel, slide-whistle bounces.
- Places: a cartoon street with grinning buildings, rolling hills with dotted trees, checkered floors.
- Ideas: personify them (a smiling sun, a dancing chart, a worried clock).

## Motion
Bouncy and elastic: big squash and stretch, anticipation before every move, follow-through after. Hits get a starburst.

## Text
A vintage display face (Rye) in white with a black outline and a hard black drop shadow, on an oval title card.

## Avoid
Colour (except the one tinted hero), clean digital edges with no film texture, copying any studio's characters (a generic glove or a generic grinning house is fine; a famous mouse or cat is not).

## Code starter
```js
const BEAT = .5, bob = (t, ph = 0) => Math.abs(Math.sin((t / BEAT + ph) * Math.PI));
function filmFinish(t, grain) {   // grain: a 512x512 noise canvas made once in setup()
  const f = Math.floor(t * 24);
  ctx.save(); ctx.globalAlpha = .07 + rand(f) * .06; ctx.fillStyle = rand(f + 3) > .5 ? "#000" : "#fff"; ctx.fillRect(0, 0, W, H); ctx.restore();
  ctx.save(); ctx.globalCompositeOperation = "overlay"; ctx.globalAlpha = .35; const ox = rand(f + 5) * 512, oy = rand(f + 6) * 512;
  for (let x = -ox; x < W; x += 512) for (let y = -oy; y < H; y += 512) ctx.drawImage(grain, x, y); ctx.restore();
  ctx.strokeStyle = "rgba(20,20,20,.5)"; ctx.lineWidth = 2; if (rand(f * 3) > .55) { const x = rand(f * 7) * W; ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x + 10, H); ctx.stroke(); }
  const v = ctx.createRadialGradient(W / 2, H / 2, H * .3, W / 2, H / 2, H * .72); v.addColorStop(0, "rgba(0,0,0,0)"); v.addColorStop(1, "rgba(0,0,0,.5)"); ctx.fillStyle = v; ctx.fillRect(0, 0, W, H);
}
// whole-frame gate weave: ctx.translate((rand(f) - .5) * 4, (rand(f + 9) - .5) * 4) before drawing the scene
```
