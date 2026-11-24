# Anime Watercolor

A hand-painted anime background come to life: deep summer blue sky, towering cumulus clouds, layered watercolour washes with soft bleeding edges and paper grain.

## Must have
- Every shape painted as a "wash": 3-6 translucent passes of the same wobbly polygon (alpha ~0.2 each), so edges bleed and pool slightly darker.
- Big, bright cumulus clouds: white washes over pale blue-violet shadow washes at the base.
- Layered depth with parallax: sky (0.1), far mountains in blue-grey (0.3), hills and round tree canopies (0.55), the near ground (1.0).
- A soft light bloom from the sun (radial gradient, screen-like), and a paper-grain overlay multiplied on top of everything.
- Clean, saturated anime colours: cobalt sky, fresh greens, one warm accent (a red bridge, a lantern, a scarf).

## Make any script work
- Places: anime settings carry the mood (a summer bridge, a train platform, a rooftop at dusk, a classroom with sun on the desks).
- People: simple cel-like figures with clean outlines and two-tone shading over the painted background.
- Details that sell the season: petals, fireflies, wind bells, dragonflies, light on water, reflections.

## Motion
Calm and floaty: slow camera drift, petals and leaves on gentle curves, wind in the grass. Let held moments breathe.

## Text
Rounded Japanese-style sans (M PLUS Rounded 1c ExtraBold) in white with a soft blue glow, or hand-lettered titles. Short and quiet.

## Avoid
Flat vector fills with hard edges, grey skies, crowded frames, fast cutting.

## Code starter
```js
function wash(c, pts, col, edge, seed, passes = 5, wob = 10) {
  for (let p = 0; p < passes; p++) {
    c.beginPath(); pts.forEach(([x, y], i) => { const jx = (rand(seed + i * 7 + p * 131) - .5) * wob, jy = (rand(seed + i * 11 + p * 97) - .5) * wob; i ? c.lineTo(x + jx, y + jy) : c.moveTo(x + jx, y + jy); });
    c.closePath(); c.globalAlpha = .2; c.fillStyle = col; c.fill();
  }
  if (edge) { c.globalAlpha = .22; c.strokeStyle = edge; c.lineWidth = 2.5; c.stroke(); }
  c.globalAlpha = 1;
}
const blob = (cx, cy, rx, ry, n = 24, seed = 1, k = .18) => Array.from({ length: n }, (_, i) => { const a = i / n * 6.283, r = 1 + (rand(seed + i) - .5) * k; return [cx + Math.cos(a) * rx * r, cy + Math.sin(a) * ry * r]; });
// paint static layers once in setup() into offscreen canvases, then drawImage them with parallax offsets in draw(t)
```
