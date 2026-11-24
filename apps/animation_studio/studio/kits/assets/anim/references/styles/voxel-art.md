# Voxel Art

A world made only of cubes with tiny 16x16 pixel textures, seen from a slightly raised camera. Blocky, bright and satisfying.

## Must have
- three.js with `BoxGeometry` blocks on a fixed grid (one block = one unit or half a unit). Use `InstancedMesh` for terrain (thousands of blocks stay fast).
- 16x16 canvas textures with `NearestFilter` (no smoothing): grass top, grass side (green strip over dirt), dirt, stone with ore specks, wood, leaves, water.
- Flat, readable light: `MeshLambertMaterial`, a hemisphere light plus one directional sun with shadows. Light fog toward the sky colour for depth.
- A camera raised a little above the ground and tilted down, so block tops are visible.
- Everything blocky: trees as trunk + leaf cubes, clouds as flat white slabs, flowers as tiny cubes. Only the story's hero may break the grid.

## Make any script work
- Building and progress: blocks dropping into place one by one is the most satisfying move in this style.
- Places: terrain cross-sections (grass, dirt, stone, ores) show "inside" stories; houses and machines built from blocks.
- Characters: box heads and box limbs, simple pixel faces on the front texture.

## Motion
Blocks snap and clunk into place with a tiny bounce; particles are small cubes that pop and fall. Smooth camera, stepped object placement.

## Text
A pixel font (Silkscreen Bold) in white with a stacked blocky shadow (several hard offsets in darker greens and browns).

## Avoid
Smooth spheres and curves everywhere, blurry textures, realistic lighting, using a famous game's characters, logos or exact textures.

## Code starter
```js
function pixTex(n, fn) {   // fn(x, y) → css colour
  const c = document.createElement("canvas"); c.width = c.height = n; const g = c.getContext("2d");
  for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) { g.fillStyle = fn(x, y); g.fillRect(x, y, 1, 1); }
  const t = new THREE.CanvasTexture(c); t.magFilter = t.minFilter = THREE.NearestFilter; return t;
}
const tone = (r, g, b, k) => `rgb(${r * k | 0},${g * k | 0},${b * k | 0})`;
const grassTop = pixTex(16, (x, y) => tone(92, 200, 74, .85 + rand(x * 31 + y) * .3));
const dirt = pixTex(16, (x, y) => tone(160, 104, 60, .8 + rand(x * 17 + y * 3) * .35));
const side = pixTex(16, (x, y) => y < 3 ? tone(92, 200, 74, .9) : tone(160, 104, 60, .8 + rand(x + y * 7) * .35));
const L = t => new THREE.MeshLambertMaterial({ map: t });
const grassMat = [L(side), L(side), L(grassTop), L(dirt), L(side), L(side)];   // +x -x +y -y +z -z
```
