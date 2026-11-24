# 3D Movie Style

The polished look of an animated feature film: glossy toy-like materials, soft image-based reflections, gentle shadows, a dreamy out-of-focus background and a cinematic camera.

## Must have
- three.js `MeshPhysicalMaterial` with clearcoat (0.6-1.0) and low roughness for hero props; a prefiltered environment (`PMREMGenerator.fromScene` of a soft gradient sky with one bright window panel) for reflections.
- Lighting like a film set: a big soft key (directional with soft shadows), a cool rim light from behind, a warm-cool contrast. ACES tone mapping, exposure a little under 1 so colours stay rich.
- Saturated, cheerful colours on clean shapes with bevels (cannon red, sky blue, sunflower yellow), set against a softly blurred background (paint it on the 2D canvas behind the WebGL layer with `ctx.filter = "blur(18px)"` and bokeh circles).
- Contact: every object sits on something and casts a shadow.
- A camera with intention: it slows, pushes in for the payoff, shakes briefly on an impact.

## Make any script work
- Turn every idea into a toy-sized physical moment (a cannon for a launch, a ramp for progress, confetti for success).
- Characters: big heads, big eyes, soft rounded bodies, clear silhouettes, expressive poses.
- Big moments: flash + recoil + particles (confetti as an `InstancedMesh` of small coloured planes with drag and flutter).

## Motion
Smooth arcs, anticipation and overshoot, a short hold before the big hit, then celebration. Use easing everywhere; nothing linear except travel.

## Text
A chunky rounded display face (Lilita One) with a warm gradient fill, white outline and a coloured extrusion shadow.

## Avoid
Flat lighting, grey reflections, washed-out exposure, sharp backgrounds that compete with the subject, studio logos or famous characters.

## Code starter
```js
const env = new THREE.Scene();
env.add(new THREE.Mesh(new THREE.SphereGeometry(50, 32, 16), new THREE.MeshBasicMaterial({ side: THREE.BackSide, color: 0xdff2ff })));
const win = new THREE.Mesh(new THREE.PlaneGeometry(30, 18), new THREE.MeshBasicMaterial({ color: 0xffffff })); win.position.set(-20, 20, 10); win.lookAt(0, 0, 0); env.add(win);
scene.environment = new THREE.PMREMGenerator(renderer).fromScene(env, .02).texture;
const toy = (c, o = {}) => new THREE.MeshPhysicalMaterial({ color: c, roughness: .32, clearcoat: .8, clearcoatRoughness: .2, envMapIntensity: .55, ...o });
renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = .92;
// confetti: const conf = new THREE.InstancedMesh(new THREE.PlaneGeometry(.16, .26), new THREE.MeshStandardMaterial({ side: THREE.DoubleSide }), 400);
// conf.frustumCulled = false;  (instances move far from the origin)
```
