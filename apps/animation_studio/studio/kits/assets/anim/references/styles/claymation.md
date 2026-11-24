# Claymation

Plasticine stop-motion in real 3D: matte clay with thumbprints, a little diorama set, animated "on twos" so it feels hand-moved.

## Must have
- three.js. Matte clay materials (`MeshStandardMaterial`, roughness ~0.75-0.8, no clearcoat) with a canvas bump map of small arcs and dents (thumbprints).
- Saturated plasticine colours: tomato red, sunflower yellow, grass green, sky blue, violet. Bright, not muddy.
- Stop-motion timing: quantise time to 12 steps a second (`T = Math.floor(t * 12) / 12`) for every animated thing, including the camera.
- Hand-placed wobble: each puppet gets a tiny random offset and rotation that changes every step (position ±0.006, rotation ±0.004 rad).
- A built set: a soil-and-grass diorama block, a painted backdrop card for the sky, clay clouds and sun, small props in the foreground.

## Make any script work
- People and animals: rounded bodies, ball joints, big bead eyes. Squash on landings, stretch on jumps, exaggerated poses.
- Places: build the miniature (table-top town, kitchen, lab) from rounded boxes, capsules and spheres.
- Ideas: turn them into physical toys (a xylophone for steps, a mushroom trampoline for bounce, a clay chart with stacked bars).

## Motion
Stepped at 12 fps, strong squash and stretch, little settle wobbles. Camera moves are slow and also stepped.

## Text
Chunky rounded type (Fredoka Bold) where each letter is a different clay colour with a soft highlight on top and a shadow under it.

## Avoid
Glossy plastic, perfect smooth motion at 30 fps, grey lighting, floating objects without contact shadows.

## Code starter
```js
const bump = new THREE.CanvasTexture((() => { const c = document.createElement("canvas"); c.width = c.height = 512; const g = c.getContext("2d");
  g.fillStyle = "#808080"; g.fillRect(0, 0, 512, 512);
  for (let i = 0; i < 900; i++) { g.strokeStyle = rand(i) > .5 ? "rgba(255,255,255,.1)" : "rgba(0,0,0,.1)"; g.lineWidth = 1 + rand(i + 3) * 2.5; g.beginPath(); g.arc(rand(i + 1) * 512, rand(i + 2) * 512, 6 + rand(i + 4) * 26, rand(i + 5) * 6, rand(i + 5) * 6 + 2); g.stroke(); }
  return c; })());
const clay = col => new THREE.MeshStandardMaterial({ color: col, roughness: .78, bumpMap: bump, bumpScale: 2.2 });
// in draw(t): const step = Math.floor(t * 12), T = step / 12;  then nudge every puppet:
// m.position.x = base.x + (rand(step * 31 + id) - .5) * .012; m.rotation.z = base.rz + (rand(step * 13 + id) - .5) * .008;
```
