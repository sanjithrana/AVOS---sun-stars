# Ink Wash

East Asian sumi-e painting: black ink on rice paper, misty graded washes, confident single brush strokes, lots of empty space and one red seal.

## Must have
- Rice-paper background: off-white with faint fibres and specks (paint once into an offscreen canvas).
- Graded ink washes for distance: mountains as vertical strips of ink that fade into mist at their base, lighter the further away.
- Brush strokes with bristles: draw each stroke as 7-9 slightly offset thin lines plus a body of dots, width changing along the stroke (pressure), dry-brush gaps near the end.
- Restraint: most of the frame is paper. Black ink, greys, and a single red accent (a seal stamp, a sun, a lantern).
- Strokes that paint themselves on screen are the signature move.

## Make any script work
- Nature first: mountains, pine branches, bamboo, birds as single brush ticks, water as a few horizontal strokes.
- People: a few strokes for a figure (robe, hat), never detailed faces.
- Ideas: an ensō (one brushed circle) for completion or calm, a single stroke for a path or a timeline, a seal to stamp a conclusion.

## Motion
Slow and deliberate. A stroke draws on with ease-in-out; mist drifts; birds glide. Let silence and empty space do the work.

## Text
A brush-style font (Ma Shan Zheng) in ink black, or hand-painted words, next to a small red seal.

## Avoid
Colour everywhere, busy frames, outlined vector shapes, fast cuts, fake Chinese or Japanese characters used as decoration.

## Code starter
```js
function brush(pts, wf, k, seed, alpha = .92) {   // pts: path, wf(f): width at fraction f, k: how much is painted (0..1)
  const n = Math.max(2, Math.floor(pts.length * clamp(k)));
  for (let b = 0; b < 9; b++) { const off = b / 8 - .5; ctx.beginPath();
    for (let i = 0; i < n; i++) { const [x, y] = pts[i], [x2, y2] = pts[Math.min(pts.length - 1, i + 1)], a = Math.atan2(y2 - y, x2 - x), w = wf(i / (pts.length - 1));
      const px = x - Math.sin(a) * off * w, py = y + Math.cos(a) * off * w; i ? ctx.lineTo(px, py) : ctx.moveTo(px, py); }
    ctx.strokeStyle = "#16130f"; ctx.globalAlpha = alpha * (.35 + rand(seed + b) * .2); ctx.lineWidth = wf(.5) / 5 + 2; ctx.lineCap = "round"; ctx.stroke(); }
  ctx.globalAlpha = alpha; ctx.fillStyle = "#16130f";
  for (let i = 0; i < n; i++) { const [x, y] = pts[i]; ctx.beginPath(); ctx.arc(x, y, wf(i / (pts.length - 1)) * .38, 0, 7); ctx.fill(); }
  ctx.globalAlpha = 1;
}
```
