# ASCII Art

The whole picture is typed: every frame is drawn as a tiny low-resolution image, then re-written as monospace characters on a dark terminal.

## Must have
- Render the scene into a small buffer where 1 pixel = 1 character cell (for 1080x1920 with 12x20 px cells: 90 columns x 96 rows), read it with `getImageData`, and print one character per cell.
- A density ramp maps brightness to glyphs: ` .,:;-=+*%#@`. Colour comes from the cell too: green phosphor for the world, one accent colour (amber, orange) for the hero.
- A real monospace font (JetBrains Mono, Fira Code) at a weight that stays crisp. Load it before rendering.
- Terminal finish: near-black background, faint scanlines, a soft vignette, sparse dim dots in empty areas.
- Exact glyphs for important props (a `=` track, `|` `/` `_` for things falling, `[ ]` boxes) typed directly on the grid.

## Make any script work
- Anything can be drawn as shapes in the buffer first (buildings, faces, charts, planets); the conversion makes it ASCII automatically.
- Reveal ideas like a terminal: type lines in, blink a cursor, re-type a region when something changes.
- A punch-in on the hero (scale the typed frame 2-3x) proves it's made of characters.

## Motion
Characters only change on the grid (no sub-cell drift for text); the scene underneath can move smoothly. Glitch beats: re-type random cells as letters for a blink.

## Text
The same monospace font, typed character by character with a block cursor: `> like_this_`.

## Avoid
Characters too small to read, fonts that aren't monospaced, rainbow colours, smearing the glyphs with blur.

## Code starter
```js
const CW = 12, CH = 20, COLS = W / CW, ROWS = H / CH, RAMP = " .,:;-=+*%#@";
const low = document.createElement("canvas"); low.width = COLS; low.height = ROWS; const lc = low.getContext("2d", { willReadFrequently: true });
function typeOut() {   // after drawing the scene into lc with lc.setTransform(1 / CW, 0, 0, 1 / CH, 0, 0)
  const d = lc.getImageData(0, 0, COLS, ROWS).data; ctx.fillStyle = "#020803"; ctx.fillRect(0, 0, W, H);
  ctx.font = `700 ${CH * .9}px "JetBrains Mono"`; ctx.textBaseline = "top";
  for (let r = 0; r < ROWS; r++) for (let c = 0; c < COLS; c++) {
    const i = (r * COLS + c) * 4, L = Math.max(d[i], d[i + 1], d[i + 2]) / 255; if (L < .06) continue;
    const hero = d[i] - d[i + 2] > 50;   // orange-ish cells keep their colour
    ctx.fillStyle = hero ? "#ff9a3a" : `rgb(${40 * L | 0},${110 + 145 * L | 0},${60 + 70 * L | 0})`;
    ctx.fillText(RAMP[Math.round(L * (RAMP.length - 1))], c * CW, r * CH);
  }
}
```
