# Kurzgesagt Style

Inspired by the science explainers that made bold flat vector famous: rounded geometric shapes, rich gradients, rim light and glow, deep space and biology colour palettes. Our own shapes, never their characters or birds.

## Must have
- Flat vector shapes with one gentle gradient each, plus a thin rim-light arc on the lit side and a soft night-side shadow.
- Deep, saturated backgrounds (navy to violet, teal to blue) with soft glowing nebula or light blobs and twinkling stars.
- Glow: radial gradients behind bright objects (planets, cells, the hero) so they feel lit from within.
- Clean rounded geometry: circles, capsules, rounded rectangles. Small craters, bands and details in lighter or darker tints of the base colour.
- Science-diagram moments: dashed orbit lines, arrows for forces, tidy labels, drawn on while explained.

## Make any script work
- Big ideas: scale (zoom from a planet to a cell), cause and effect (arrows, flows), comparisons (two things side by side).
- People and animals: simple rounded figures with no mouths or simple dots for eyes, consistent palette.
- Numbers: clean bars and pies with the same glow and rim light.

## Motion
Smooth, eased, often orbiting or floating. Particles and stars drift. Camera glides and zooms slowly; big reveals get a short pause.

## Text
A rounded heavy sans (Nunito Black) in white with a soft glow. Short labels, never paragraphs.

## Avoid
Hard outlines, noisy textures, photo elements, muddy dark colours (dark backgrounds must still be vivid), copying their mascots.

## Code starter
```js
function glow(x, y, r, rgba) { const g = ctx.createRadialGradient(x, y, r * .2, x, y, r); g.addColorStop(0, rgba.replace("A", .45)); g.addColorStop(1, rgba.replace("A", 0)); ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, r, 0, 7); ctx.fill(); }
function planet(x, y, r, c1, c2, rim) {
  glow(x, y, r * 1.6, "rgba(120,200,255,A)");
  const g = ctx.createLinearGradient(x - r, y - r, x + r, y + r); g.addColorStop(0, c1); g.addColorStop(1, c2);
  ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, r, 0, 7); ctx.fill();
  ctx.save(); ctx.clip(); const n = ctx.createLinearGradient(x, y, x + r, y + r); n.addColorStop(0, "rgba(10,10,40,0)"); n.addColorStop(1, "rgba(10,10,40,.45)"); ctx.fillStyle = n; ctx.fillRect(x - r, y - r, 2 * r, 2 * r); ctx.restore();
  ctx.strokeStyle = rim; ctx.lineWidth = 6; ctx.beginPath(); ctx.arc(x, y, r - 3, Math.PI * .95, Math.PI * 1.6); ctx.stroke();
}
```
