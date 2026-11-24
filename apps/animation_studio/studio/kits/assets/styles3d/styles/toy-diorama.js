/* Claude 3D Styles: Toy Diorama (reference animation: "From farm to cup") */
(window.STYLES = window.STYLES || {})["toy-diorama"] = {
  name: "Toy Diorama",
  card: {
    family: "Worlds and journeys",
    look: "A whole little world on one floating slab of land, like a toy model on a designer's desk: chunky rounded houses, a toy truck, peg people and lollipop trees in a few soft matte colours. The cut sides of the slab show grass, soil and rock layers, and clouds drift around it in a bright sky.",
    motion: "Things pop up from the ground with a springy overshoot, vehicles drive along the road, smoke and steam puff in soft balls. The camera glides over the world from stop to stop like a drone, then pulls back to show the whole island.",
    light: "Bright morning sun from the upper right with soft-edged shadows, plus a bright sky fill so nothing goes dark.",
    materials: "Matte toy plastic and painted wood (roughness 0.7-0.9), slightly rounded edges on everything, no textures except a soft noise in the grass.",
    camera: "Medium-long lens (fov 28-32) looking down at about 30 degrees, gentle depth of field on the subject, one continuous move.",
    finish: "Clean and bright, neutral tone mapping, light bloom, very fine grain.",
    goodFor: "Processes that travel from place to place: supply chains, journeys, how something is made, step-by-step stories with a 'stop' for each step.",
  },
  content: { title: "From farm to cup", steps: ["Picked", "Roasted", "Brewed"] },
  duration: 8,
  samples: 24,
  fonts: ["Inter:800"],
  grade: { exposure: 1.05, tonemap: "neutral", bloom: 0.12, bloomThreshold: 1.2, saturation: 1.12, contrast: 1.03, vignette: 0.18, grain: 0.012 },

  build(S) {
    const T = S.THREE, K = S.K, C = this.content, R = K.rng(7);
    const col = { grass: "#86c96e", grass2: "#6fb85e", soil: "#b07a4f", rock: "#8a7a70", road: "#e9e4dc", cream: "#fff3df", roof: "#ef6a4c", blue: "#4c7dff", orange: "#ff8a1f", leaf: "#3f9a55", cherry: "#e0343c", trunk: "#8a5a3c", cup: "#ffffff", coffee: "#6b3b22" };
    // sky, light, fog
    S.gradientBg("#7fc3ff", "#e6f4ff", { mid: "#bfe2ff" });
    S.scene.fog = new T.Fog("#d4ecff", 30, 75);
    S.env({ top: "#cfe8ff", bottom: "#e8e2d6", intensity: 0.4 });
    S.sun({ pos: [10, 15, 5], intensity: 3.6, soft: 1.0, size: 12, color: "#fff4e2" });
    S.hemi("#d8ecff", "#8fae80", 0.55);
    const matte = (c) => S.mat.std(c, { roughness: 0.82 });

    // the island: layered slab with cut sides
    const isle = S.group();
    S.mesh(K.rbox(8, 0.5, 17, 0.22), matte(col.grass), { pos: [0, -0.25, 0], parent: isle }).material.bumpMap = S.noiseTex("g", 256, 3, 24, 4);
    S.mesh(K.rbox(7.9, 0.9, 16.9, 0.15), matte(col.soil), { pos: [0, -0.9, 0], parent: isle });
    S.mesh(K.rbox(7.6, 1.2, 16.6, 0.4), matte(col.rock), { pos: [0, -1.85, 0], parent: isle });
    // a few rocks poking out of the bottom
    for (let i = 0; i < 6; i++) S.mesh(new T.IcosahedronGeometry(0.6 + R() * 0.5, 0), S.mat.std(col.rock, { roughness: 0.9, flatShading: true }), { pos: [-3 + R() * 6, -2.5, -7 + R() * 14], scale: [1, 0.8, 1], parent: isle });

    // the road (a ribbon along a curve) with dashes
    const curve = new T.CatmullRomCurve3([[-0.6, 0, 8.2], [0.6, 0, 5.5], [1.6, 0, 2.6], [0.6, 0, 0.2], [-1.2, 0, -2.4], [-1.4, 0, -4.6], [0.2, 0, -6.6], [0.4, 0, -8.3]].map((p) => new T.Vector3(...p)));
    const ribbon = (cv, w, y) => { const n = 160, pos = [], idx = []; for (let i = 0; i <= n; i++) { const u = i / n, p = cv.getPointAt(u), tg = cv.getTangentAt(u), nx = -tg.z, nz = tg.x, l = Math.hypot(nx, nz); pos.push(p.x + (nx / l) * w / 2, y, p.z + (nz / l) * w / 2, p.x - (nx / l) * w / 2, y, p.z - (nz / l) * w / 2); if (i < n) { const a = i * 2; idx.push(a, a + 2, a + 1, a + 1, a + 2, a + 3); } } const g = new T.BufferGeometry(); g.setAttribute("position", new T.Float32BufferAttribute(pos, 3)); g.setIndex(idx); g.computeVertexNormals(); return g; };
    const road = S.mesh(ribbon(curve, 1.15, 0.012), matte(col.road), { parent: isle }); road.castShadow = false;
    for (let i = 0; i < 26; i++) { const u = (i + 0.5) / 26, p = curve.getPointAt(u), tg = curve.getTangentAt(u); const d = S.mesh(K.rbox(0.08, 0.02, 0.28, 0.01), matte("#ffffff"), { pos: [p.x, 0.025, p.z], parent: isle }); d.rotation.y = Math.atan2(tg.x, tg.z); }

    // popping helper: things grow from the ground with a spring
    const pops = [];
    const pop = (obj, t0, base = 1) => { pops.push({ obj, t0, base }); obj.scale.setScalar(0.0001); return obj; };

    // lollipop trees all around
    const tree = (x, z, s = 1, c = col.leaf, t0 = 0) => { const g = S.group(isle, [x, 0, z]); S.mesh(new T.CylinderGeometry(0.06 * s, 0.08 * s, 0.6 * s, 10), matte(col.trunk), { pos: [0, 0.3 * s, 0], parent: g }); S.mesh(new T.SphereGeometry(0.42 * s, 24, 16), matte(c), { pos: [0, 0.85 * s, 0], parent: g }); return t0 ? pop(g, t0) : g; };
    [[-3.2, 6.8], [3.3, 7.2], [-3.3, 2.6], [3.4, 0.8], [3.2, -2.5], [-3.3, -6.8], [3.3, -7.6], [-3.4, -1.0], [2.9, 4.4]].forEach(([x, z], i) => tree(x, z, 0.9 + R() * 0.5, i % 2 ? col.leaf : "#55b06a"));

    // 1 · the farm: rows of coffee bushes with cherries that ripen
    const cherries = [];
    for (let r = 0; r < 3; r++) for (let c = 0; c < 4; c++) {
      const x = -2.9 + c * 0.75, z = 4.6 + r * 1.05, g = S.group(isle, [x, 0, z]);
      S.mesh(new T.SphereGeometry(0.34, 20, 14), matte(col.leaf), { pos: [0, 0.32, 0], scale: [1, 1.1, 1], parent: g });
      S.mesh(new T.SphereGeometry(0.26, 20, 14), matte("#4aa862"), { pos: [0.12, 0.62, 0.05], parent: g });
      for (let k = 0; k < 4; k++) { const a = k * 1.7 + r, m = S.mesh(new T.SphereGeometry(0.075, 12, 10), S.mat.gloss(col.cherry, { roughness: 0.3 }), { pos: [Math.cos(a) * 0.3, 0.3 + (k % 2) * 0.3, Math.sin(a) * 0.3 + 0.08], parent: g }); cherries.push({ m, t0: 0.5 + (r * 4 + c) * 0.06 + k * 0.03 }); }
    }
    // the farmer (peg person) with a basket
    const peg = (x, z, c, parent = isle) => { const g = S.group(parent, [x, 0, z]); S.mesh(new T.CapsuleGeometry(0.16, 0.34, 6, 16), matte(c), { pos: [0, 0.33, 0], parent: g }); S.mesh(new T.SphereGeometry(0.15, 20, 14), matte("#f2c9a0"), { pos: [0, 0.78, 0], parent: g }); return g; };
    const farmer = peg(-0.4, 6.6, col.blue);
    const basket = S.mesh(new T.CylinderGeometry(0.17, 0.13, 0.16, 18), matte("#d9a35f"), { pos: [0.24, 0.42, 0.05], parent: farmer });

    // a sack that gets loaded on the truck
    const sackMat = S.mat.std("#d6b98a", { roughness: 0.95 }); sackMat.bumpMap = S.noiseTex("s", 128, 9, 40, 2); sackMat.bumpScale = 2;
    const sack = () => S.mesh(K.rbox(0.42, 0.34, 0.3, 0.13), sackMat);

    // the truck
    const truck = S.group(isle);
    S.mesh(K.rbox(0.62, 0.42, 0.56, 0.12), matte(col.orange), { pos: [0, 0.42, 0.42], parent: truck });
    S.mesh(K.rbox(0.5, 0.16, 0.05, 0.03), S.mat.gloss("#bfe3ff", { roughness: 0.1 }), { pos: [0, 0.52, 0.71], parent: truck });
    S.mesh(K.rbox(0.66, 0.1, 0.9, 0.04), matte("#ffffff"), { pos: [0, 0.26, -0.18], parent: truck });
    [[-0.3, 0.32], [0.3, 0.32], [-0.3, -0.42], [0.3, -0.42]].forEach(([x, z]) => S.mesh(new T.CylinderGeometry(0.13, 0.13, 0.1, 20), matte("#33384a"), { pos: [x, 0.13, z], rot: [0, 0, Math.PI / 2], parent: truck }));
    const load = sack(); load.position.set(0, 0.48, -0.2); truck.add(load);

    // 2 · the roastery: cream house, red roof, chimney with smoke
    const roast = pop(S.group(isle, [2.3, 0, -0.6]), 2.55);
    S.mesh(K.rbox(1.7, 1.2, 1.5, 0.12), matte(col.cream), { pos: [0, 0.6, 0], parent: roast });
    const roofG = new T.ExtrudeGeometry(new T.Shape([new T.Vector2(-1.05, 0), new T.Vector2(1.05, 0), new T.Vector2(0, 0.75)]), { depth: 1.7, bevelEnabled: true, bevelSize: 0.05, bevelThickness: 0.05, bevelSegments: 3 });
    roofG.translate(0, 0, -0.85); S.mesh(roofG, matte(col.roof), { pos: [0, 1.2, 0], parent: roast });
    S.mesh(K.rbox(0.28, 0.8, 0.28, 0.05), matte("#d55a3d"), { pos: [0.45, 1.75, -0.3], parent: roast });
    S.mesh(K.rbox(0.36, 0.5, 0.06, 0.05), matte("#7a4a33"), { pos: [-0.2, 0.3, 0.76], parent: roast });
    S.mesh(K.rbox(0.36, 0.3, 0.06, 0.05), S.mat.gloss("#ffd27a", { emissive: "#ffb347", emissiveIntensity: 0.5 }), { pos: [0.45, 0.68, 0.76], parent: roast });
    const smoke = []; for (let i = 0; i < 7; i++) smoke.push(S.mesh(new T.SphereGeometry(0.2, 18, 12), S.mat.std("#ffffff", { roughness: 1, transparent: true, opacity: 0.95 }), { parent: roast, shadow: false }));
    // beans pouring into roasted sacks
    const roasted = [sack(), sack()]; roasted.forEach((s, i) => { s.material = S.mat.std("#8a5a3a", { roughness: 0.95 }); s.position.set(1.2 + i * 0.1, 0.17, 0.6 - i * 0.45); roast.add(s); });

    // 3 · the café with a giant cup on top and steam
    const cafe = pop(S.group(isle, [-1.9, 0, -6.1]), 4.85);
    S.mesh(K.rbox(2.0, 1.1, 1.5, 0.14), matte("#ffd3dc"), { pos: [0, 0.55, 0], parent: cafe });
    const awn = S.picture(2.0, 0.42, (x, w, h) => { for (let i = 0; i < 10; i++) { x.fillStyle = i % 2 ? "#ffffff" : "#ff6f8e"; x.fillRect((i * w) / 10, 0, w / 10 + 1, h); } }, { pos: [0, 0.98, 0.86], parent: cafe }); awn.rotation.x = 0.55;
    S.mesh(K.rbox(0.4, 0.55, 0.06, 0.06), S.mat.gloss("#bfe3ff", { roughness: 0.1 }), { pos: [0.45, 0.34, 0.76], parent: cafe });
    const cup = S.group(cafe, [-0.15, 1.1, 0]);
    const lathe = new T.LatheGeometry([[0, 0], [0.42, 0], [0.5, 0.06], [0.58, 0.75], [0.6, 0.8], [0.55, 0.8], [0.5, 0.12], [0, 0.1]].map((p) => new T.Vector2(...p)), 48);
    S.mesh(lathe, S.mat.gloss(col.cup, { roughness: 0.25 }), { parent: cup });
    S.mesh(new T.TorusGeometry(0.2, 0.06, 14, 32, Math.PI * 1.2), S.mat.gloss(col.cup, { roughness: 0.25 }), { pos: [0.6, 0.42, 0], rot: [0, 0, -Math.PI * 0.6], parent: cup });
    S.mesh(new T.CircleGeometry(0.54, 40), S.mat.std(col.coffee, { roughness: 0.35 }), { pos: [0, 0.72, 0], rot: [-Math.PI / 2, 0, 0], parent: cup });
    const steam = []; for (let i = 0; i < 6; i++) steam.push(S.mesh(new T.SphereGeometry(0.16, 16, 12), S.mat.std("#ffffff", { roughness: 1, transparent: true }), { parent: cup, shadow: false }));
    // a customer
    const guest = peg(-0.5, 1.2, col.orange, cafe); guest.rotation.y = 2.8;

    // step flags: number + word on a little white sign on a post
    const flag = (n, word, x, z, t0) => {
      const g = pop(S.group(isle, [x, 0, z]), t0);
      S.mesh(new T.CylinderGeometry(0.035, 0.035, 1.5, 10), matte("#ffffff"), { pos: [0, 0.75, 0], parent: g });
      const l = S.label(word, { h: 0.52, font: "800 120px Inter", color: "#1d2b4f", bg: "#ffffff", radius: 44, pad: 44, extraW: 150, parent: g, lit: false, draw: (x, w, h) => {
        // shift the word right and draw the orange number badge on the left
        const img = x.getImageData(0, 0, w, h); x.clearRect(0, 0, w, h); x.fillStyle = "#ffffff"; x.beginPath(); x.roundRect(0, 0, w, h, 44); x.fill();
        x.font = "800 120px Inter"; x.textAlign = "left"; x.fillStyle = "#1d2b4f"; x.fillText(word, 44 + 150, 44 + 103);
        x.fillStyle = col.orange; x.beginPath(); x.arc(44 + 58, h / 2, 62, 0, 7); x.fill(); x.fillStyle = "#fff"; x.font = "800 92px Inter"; x.textAlign = "center"; x.fillText(n, 44 + 58, h / 2 + 33); } });
      l.position.set(0, 1.65, 0); l.castShadow = true; g.userData.l = l; return g;
    };
    const flags = [flag("1", C.steps[0], 0.9, 6.9, 0.55), flag("2", C.steps[1], 3.6, 0.6, 3.1), flag("3", C.steps[2], -3.5, -4.4, 5.35)];

    // distant islands + clouds fill the sky and the space under the island
    const far = (x, y, z, s) => { const g = S.group(S.scene, [x, y, z]); g.scale.setScalar(s); S.mesh(K.rbox(4, 0.6, 4, 0.25), matte(col.grass2), { parent: g }); S.mesh(K.rbox(3.8, 1.4, 3.8, 0.4), matte(col.soil), { pos: [0, -1, 0], parent: g }); const tr = S.group(g, [0.6, 0.3, 0.2]); S.mesh(new T.SphereGeometry(0.8, 20, 14), matte(col.leaf), { pos: [0, 1, 0], parent: tr }); S.mesh(new T.CylinderGeometry(0.1, 0.12, 0.8, 8), matte(col.trunk), { pos: [0, 0.4, 0], parent: tr }); return g; };
    far(-14, -3, -16, 1.2); far(15, -1, -22, 1.4); far(-10, -9, 10, 1.1); far(12, -10, 6, 1.0); far(-4, -6, -32, 1.5);
    const cloudMat = S.mat.std("#ffffff", { roughness: 1 });
    const clouds = [];
    const cloud = (x, y, z, s) => { const g = S.group(S.scene, [x, y, z]); for (let i = 0; i < 5; i++) S.mesh(new T.SphereGeometry(0.6 + R() * 0.5, 20, 14), cloudMat, { pos: [(i - 2) * 0.7, Math.sin(i) * 0.2, R() * 0.4], shadow: false, parent: g }); g.scale.setScalar(s); clouds.push({ g, x, s: 0.1 + R() * 0.15 }); };
    cloud(-6.5, 1.5, 3, 1.2); cloud(6.8, 2.5, -4, 1.4); cloud(-7, 0.5, -9, 1.6); cloud(5.5, -4.5, 9, 1.8); cloud(-6, -5, 1, 2); cloud(0, -7, 6, 2.4); cloud(7, -3.5, -11, 1.6);

    // camera stations: [time, target, region (w,h) that must fill the frame]
    const cam = [
      [0, [0.0, 0.6, 5.4], [6.2, 5.0]],
      [2.4, [1.0, 0.5, 2.0], [6.5, 5.5]],
      [4.0, [1.2, 0.7, -0.6], [6.0, 5.2]],
      [5.6, [-1.2, 0.8, -5.0], [6.0, 5.2]],
      [8.0, [0.7, -0.4, -0.4], [12.0, 17.5]],
    ];
    const fov = S.portrait ? 30 : 24;
    const dir = new T.Vector3(0.42, 0.62, 1).normalize();
    return (t) => {
      // pops
      for (const p of pops) { const k = K.prog(t, p.t0, p.t0 + 0.7); p.obj.scale.setScalar(Math.max(0.0001, K.ease.spring(k) * p.base)); }
      // cherries ripen: green -> red and swell
      for (const c of cherries) { const k = K.tw(t, c.t0, c.t0 + 0.5, K.ease.back); c.m.scale.setScalar(0.4 + 0.6 * k); }
      // farmer bobs while picking
      farmer.position.y = Math.abs(Math.sin(t * 7)) * 0.05 * (t < 2 ? 1 : 0); farmer.rotation.y = 0.4 + Math.sin(t * 2) * 0.2;
      // the truck: waits at the farm, sack flies in, drives to the roastery, then on to the café
      const u = K.keys(t, [[0, 0.06], [1.9, 0.06], [3.3, 0.42, K.ease.inOut], [4.3, 0.42], [5.6, 0.86, K.ease.inOut], [8, 0.86]]);
      const p = curve.getPointAt(u), tg = curve.getTangentAt(u); truck.position.set(p.x, Math.abs(Math.sin(t * 22)) * 0.02 * (t > 1.9 && t < 5.6 ? 1 : 0), p.z); truck.rotation.y = Math.atan2(tg.x, tg.z) + Math.PI;
      const sk = K.tw(t, 1.35, 1.85, K.ease.out); load.position.set(K.lerp(-1.0, 0, sk), 0.48 + Math.sin(sk * Math.PI) * 0.9, -0.2); load.scale.setScalar(t < 1.35 ? 0.0001 : 1);
      load.material = t < 4.1 ? sackMat : roasted[0].material; // roasted on the way out
      // smoke puffs from the chimney
      smoke.forEach((m, i) => { const ph = ((t * 0.55 + i / smoke.length) % 1), on = K.prog(t, 2.9, 3.3); m.position.set(0.45 + Math.sin(ph * 5 + i) * 0.15, 2.2 + ph * 2.2, -0.3 + ph * 0.4); m.scale.setScalar((0.5 + ph * 1.4) * on); m.material.opacity = (1 - ph) * 0.95; });
      roasted.forEach((s, i) => s.scale.setScalar(K.ease.spring(K.prog(t, 3.4 + i * 0.25, 4.0 + i * 0.25)) + 0.0001));
      // steam from the cup
      steam.forEach((m, i) => { const ph = ((t * 0.6 + i / steam.length) % 1), on = K.prog(t, 5.5, 5.9); m.position.set(Math.sin(ph * 6 + i * 2) * 0.12, 0.8 + ph * 1.4, 0); m.scale.setScalar((0.4 + ph) * on); m.material.opacity = (1 - ph) * 0.85; });
      // clouds drift
      clouds.forEach((c) => (c.g.position.x = c.x + Math.sin(t * c.s + c.x) * 0.6));
      // flags face the camera and sway
      const tgt = K.keys(t, cam.map(([tq, q]) => [tq, q])), reg = K.keys(t, cam.map(([tq, , r]) => [tq, r]));
      const d = S.fitDist(reg[0], reg[1] * (S.portrait ? 0.62 : 0.85), fov), pos = [tgt[0] + dir.x * d, tgt[1] + dir.y * d, tgt[2] + dir.z * d];
      flags.forEach((f, i) => { f.rotation.y = Math.atan2(pos[0] - f.position.x, pos[2] - f.position.z) * 0.8; f.userData.l.rotation.z = Math.sin(t * 2 + i) * 0.03; });
      const end = K.tw(t, 5.6, 8, K.ease.inOut);
      S.cam(pos, tgt, { fov, aperture: K.lerp(0.1, 0.04, end) });
    };
  },

  sound(k) {
    k.bed("wind", 0, 8, { vol: 0.8 });
    k.chords(0, 8, ["C4 E4 G4", "F3 A3 C4", "A3 C4 E4", "G3 B3 D4"], { bpm: 120, vol: 0.7, arp: true, arpVol: 0.22 });
    [0.3, 0.9, 1.5].forEach((t, i) => k.at(t, "ping", { f: ["E6", "G6", "C7"][i], vol: 0.25, pan: 0.5 }));
    for (let i = 0; i < 8; i++) k.at(0.55 + i * 0.12, "pop", { vol: 0.25, pitch: 1.2 + (i % 3) * 0.15, pan: -0.3 + i * 0.08 });
    k.at(0.6, "wood", { vol: 0.6 }); k.at(1.35, "whoosh", { dur: 0.45, vol: 0.5 }); k.at(1.84, "thud", { vol: 0.7 });
    k.bed("motor", 1.9, 3.3, { vol: 0.9, pitch: 1.3 }); k.bed("motor", 4.3, 5.6, { vol: 0.9, pitch: 1.3 });
    k.at(2.55, "spring", { vol: 0.4 }); k.at(3.1, "wood", { vol: 0.6 }); k.at(2.95, "whoosh", { dur: 0.9, vol: 0.35, down: true });
    k.at(3.4, "clay", { vol: 0.5 }); k.at(3.65, "clay", { vol: 0.5, pitch: 1.1 });
    k.at(4.85, "spring", { vol: 0.4, pitch: 1.2 }); k.at(5.35, "wood", { vol: 0.6 }); k.at(5.7, "glass", { f: "E6", vol: 0.6 }); k.at(5.85, "chime", { f: "G5", vol: 0.5 });
    k.at(6.2, "whoosh", { dur: 1.4, vol: 0.4 }); k.at(7.2, "sparkle", { vol: 0.35 });
  },
};
