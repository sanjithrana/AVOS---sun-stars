# Paper Cut-out

A pop-up book: every shape is cut from coloured paper, with torn or scissor edges, paper grain and real drop shadows between layers.

## Must have
- Shapes filled with flat paper colours, edges slightly irregular (torn: jitter the outline every ~14 px by a few pixels; scissor-cut: smooth curves).
- Every layer casts a soft shadow onto the one below (`shadowBlur` ~14, offset ~5-8 px). This is what makes it read as paper.
- A paper-grain texture multiplied inside every shape (fibres and specks), so no fill is perfectly flat.
- Bright, friendly colour: sky-blue paper, three greens for the hills, warm accents for houses and flowers.
- Things pop up: elements hinge up from the page (scaleY 0→1 with overshoot), bridges and flaps fold over.

## Make any script work
- Places: layered paper hills, cut-out houses, trees on tabs, clouds made of overlapping paper circles.
- People and objects: build them from a few cut pieces (body, head, arms) joined at pivots, like real cut-out puppets.
- Ideas: pop-up mechanisms (a chart that unfolds, a bridge that folds out, a door that flips open).

## Motion
Pieces move as rigid paper: rotate around pivots, slide in layers, flip up with a springy overshoot. Optional stepped timing (12 fps) for a handmade feel.

## Text
Each letter on its own paper tile (Archivo Black on coloured squares, slightly rotated) or cut-out letters with shadows.

## Avoid
Gradients, glossy highlights, outlines, perfectly geometric edges everywhere, flat shapes without shadows.

## Code starter
```js
function torn(pts, seed, amp = 5) { const o = []; for (let i = 0; i < pts.length; i++) { const [x0, y0] = pts[i], [x1, y1] = pts[(i + 1) % pts.length], n = Math.max(1, Math.ceil(Math.hypot(x1 - x0, y1 - y0) / 14)); for (let k = 0; k < n; k++) { const f = k / n; o.push([lerp(x0, x1, f) + (rand(seed + i * 31 + k) - .5) * amp, lerp(y0, y1, f) + (rand(seed + i * 17 + k * 3) - .5) * amp]); } } return o; }
function paper(c, pts, col, sh = 1) {
  c.save(); c.shadowColor = `rgba(40,30,20,${.28 * sh})`; c.shadowBlur = 14 * sh; c.shadowOffsetX = 5 * sh; c.shadowOffsetY = 8 * sh;
  c.fillStyle = col; c.beginPath(); pts.forEach(([x, y], i) => i ? c.lineTo(x, y) : c.moveTo(x, y)); c.closePath(); c.fill(); c.restore();
  // then clip to the same path and multiply a grain canvas at ~0.5 alpha
}
```
