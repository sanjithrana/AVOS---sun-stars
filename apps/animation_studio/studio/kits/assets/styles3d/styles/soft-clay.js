/* Claude 3D Styles: Soft Clay (reference animation: "How a seed becomes a tree") */
(window.STYLES = window.STYLES || {})["soft-clay"] = {
  name: "Soft Clay",
  card: {
    family: "Handmade materials",
    look: "Everything is modelled in plasticine on a small tabletop in front of a seamless coloured paper sweep: chunky, slightly lumpy forms with fingerprints in them, in a handful of bright clay colours. Words sit on little paper signs stuck into the clay.",
    motion: "Stop-motion: objects move in steps at 12 frames a second and 'boil' a tiny bit on every step, like a hand nudged them between photos. Things squash when they land and stretch when they jump. The camera itself moves smoothly and slowly.",
    light: "One big soft key from the upper left (a softbox) with soft round shadows on the paper, a cool fill from the right, no hard highlights.",
    materials: "Plasticine: satin roughness about 0.5 with a little sheen, a fine bump of fingerprints and tool marks, saturated flat colours. Matte paper for the backdrop and the signs.",
    camera: "Close tabletop camera (fov 30-35) a little above the subject, shallow depth of field so the backdrop falls soft, slow push-ins.",
    finish: "Warm-neutral grade, neutral tone mapping, soft vignette, light grain.",
    goodFor: "Growth, nature, cooking, kids' science, anything friendly that changes shape over a few steps.",
  },
  content: { title: "How a seed becomes a tree", steps: ["Plant a seed", "Add water + sun", "Watch it grow"] },
  duration: 8,
  samples: 24,
  fonts: ["Fredoka:700"],
  grade: { exposure: 1.08, tonemap: "neutral", bloom: 0.08, saturation: 1.12, contrast: 1.04, vignette: 0.45, grain: 0.016, warm: 0.4 },

  build(S) {
    const T = S.THREE, K = S.K, C = this.content;
    const bump = S.noiseTex("clay", 256, 11, 22, 5, 1.6, [2, 2]);
    const clay = (c, o = {}) => { const m = new T.MeshPhysicalMaterial({ color: c, roughness: 0.52, sheen: 0.5, sheenRoughness: 0.6, sheenColor: new T.Color("#ffffff"), bumpMap: bump, bumpScale: 1.6, ...o }); return m; };
    S.env({ top: "#ffffff", bottom: "#d8d0c4", intensity: 0.45 });
    const paper = S.mat.matte("#36b5ac"); paper.bumpMap = S.noiseTex("paper", 256, 4, 90, 3, 0.6, [6, 6]); paper.bumpScale = 0.4;
    S.mesh(K.sweep(60, 30, 30, 7), paper, { pos: [0, 0, -5] });
    S.scene.background = new T.Color("#36b5ac");
    S.sun({ pos: [-7, 11, 7], intensity: 3.1, soft: 2.6, size: 9, color: "#fff6ea" });
    S.hemi("#dff5ff", "#b9a28a", 0.7);
    S.point({ pos: [6, 3, 4], intensity: 18, color: "#cfe6ff" });

    // stop-motion helpers: time in 12 fps steps + a tiny "boil" per step
    const step = (t) => Math.floor(t * 12) / 12;
    const boil = (o, t, seed, amt = 0.012) => { const r = K.rng(Math.floor(t * 12) * 31 + seed); o.rotation.z = (r() - 0.5) * amt * 2; o.rotation.x = (r() - 0.5) * amt * 2; return 1 + (r() - 0.5) * amt; };
    const lumpy = (geo, seed, amt = 0.04) => { const P = geo.attributes.position, r = K.rng(seed); const v = new T.Vector3(); const a = [r() * 9, r() * 9, r() * 9]; for (let i = 0; i < P.count; i++) { v.fromBufferAttribute(P, i); const n = Math.sin(v.x * 3.1 + a[0]) * Math.sin(v.y * 2.7 + a[1]) * Math.sin(v.z * 3.3 + a[2]); v.multiplyScalar(1 + n * amt); P.setXYZ(i, v.x, v.y, v.z); } geo.computeVertexNormals(); return geo; };

    // the pot
    const pot = S.group(S.scene, [0, 0, 0]);
    const prof = [[0, 0], [0.78, 0], [0.86, 0.06], [1.02, 1.0], [1.18, 1.02], [1.2, 1.22], [1.1, 1.3], [0.96, 1.26], [0.95, 1.05], [0, 1.05]].map((p) => new T.Vector2(...p));
    S.mesh(lumpy(new T.LatheGeometry(prof, 64), 3, 0.015), clay("#e9784d"), { parent: pot });
    const soil = S.mesh(lumpy(new T.SphereGeometry(0.97, 48, 24, 0, Math.PI * 2, 0, Math.PI / 2), 5, 0.05), clay("#6b4630", { roughness: 0.8 }), { pos: [0, 1.0, 0], scale: [1, 0.16, 1], parent: pot });

    // the seed
    const seed = S.mesh(lumpy(new T.SphereGeometry(0.17, 32, 20), 8, 0.06), clay("#a8673d"), { scale: [1, 0.7, 0.8] });
    // stem, trunk, leaves, canopy, apples
    const plant = S.group(pot, [0, 1.12, 0]);
    const stemCurve = new T.CatmullRomCurve3([[0, 0, 0], [0.06, 0.8, 0.02], [-0.05, 1.6, 0], [0.04, 2.3, 0.02]].map((p) => new T.Vector3(...p)));
    const stem = S.mesh(new T.TubeGeometry(stemCurve, 48, 0.07, 14, false), clay("#59b04e"), { parent: plant });
    const trunk = S.mesh(lumpy(new T.TubeGeometry(stemCurve, 48, 0.17, 18, false), 9, 0.03), clay("#8a5638"), { parent: plant });
    const leafGeo = lumpy(new T.SphereGeometry(0.22, 24, 14), 10, 0.05); leafGeo.scale(1.3, 0.28, 0.7);
    const leaves = [[0.2, 0.55, 0.6], [-0.2, 0.75, -0.6]].map(([x, y, r], i) => { const l = S.mesh(leafGeo, clay(i ? "#4fa646" : "#6cc35c"), { parent: plant }); l.position.set(x, y, 0); l.rotation.set(0, 0, r); return l; });
    const blobs = [[0, 2.55, 0, 0.9], [-0.65, 2.2, 0.15, 0.62], [0.7, 2.25, 0.05, 0.66], [0.25, 2.95, 0.2, 0.55], [-0.35, 2.85, -0.25, 0.6], [0.05, 2.15, 0.5, 0.55]].map(([x, y, z, r], i) => { const m = S.mesh(lumpy(new T.SphereGeometry(r, 40, 24), 20 + i, 0.06), clay(["#4fb04a", "#5dbd55", "#45a043"][i % 3]), { pos: [x, y, z], parent: plant }); m.userData.t0 = 5.3 + i * 0.12; return m; });
    const apples = [[0.5, 2.3, 0.86], [-0.55, 2.05, 0.7], [0.12, 2.95, 0.72], [-0.85, 2.45, 0.5], [0.98, 2.5, 0.52]].map(([x, y, z], i) => { const m = S.mesh(lumpy(new T.SphereGeometry(0.14, 24, 16), 40 + i, 0.05), clay("#e8413c", { roughness: 0.4 }), { pos: [x, y, z], parent: plant }); m.userData.t0 = 6.3 + i * 0.13; return m; });

    // watering can + water drops
    const can = S.group(S.scene, [1.9, 2.6, 0.2]);
    S.mesh(lumpy(K.rbox(0.9, 0.7, 0.6, 0.25), 51, 0.02), clay("#4f7df0"), { parent: can });
    S.mesh(new T.CylinderGeometry(0.05, 0.09, 0.9, 16), clay("#4f7df0"), { pos: [-0.6, 0.25, 0], rot: [0, 0, 1.0], parent: can });
    S.mesh(new T.TorusGeometry(0.22, 0.06, 12, 24, Math.PI), clay("#3d66d0"), { pos: [0.2, 0.36, 0], parent: can });
    const drops = []; for (let i = 0; i < 9; i++) drops.push(S.mesh(new T.SphereGeometry(0.06, 16, 12), clay("#7fd0ff", { roughness: 0.25 }), { shadow: false }));
    // the clay sun
    const sun = S.group(S.scene, [-1.8, 4.4, -1.4]);
    S.mesh(lumpy(new T.SphereGeometry(0.5, 40, 24), 60, 0.04), clay("#ffcf3a", { emissive: "#ffb000", emissiveIntensity: 0.25 }), { parent: sun, scale: [1, 1, 0.6] });
    for (let i = 0; i < 10; i++) { const a = (i / 10) * Math.PI * 2; S.mesh(new T.ConeGeometry(0.1, 0.32, 12), clay("#ffb42e"), { pos: [Math.cos(a) * 0.72, Math.sin(a) * 0.72, 0], rot: [0, 0, a - Math.PI / 2], parent: sun }); }

    // a little clay garden on the table + clouds hanging in front of the paper
    const floorProp = (geo, mat, pos, sc = 1) => S.mesh(geo, mat, { pos, scale: sc });
    [[-1.7, 0.12, 1.2, 0.2, "#c9c2b6"], [-2.1, 0.09, 0.4, 0.14, "#b3aa9c"], [1.6, 0.1, 1.5, 0.16, "#d4ccbf"], [2.3, 0.12, -0.6, 0.18, "#b8afa2"]].forEach(([x, y, z, r, c], i) => floorProp(lumpy(new T.SphereGeometry(r, 24, 14), 70 + i, 0.1), clay(c), [x, y, z], [1.3, 0.75, 1]));
    const mush = (x, z, s) => { const g = S.group(S.scene, [x, 0, z]); g.scale.setScalar(s); S.mesh(lumpy(new T.CylinderGeometry(0.1, 0.13, 0.35, 16), 81, 0.05), clay("#fff2dc"), { pos: [0, 0.17, 0], parent: g }); S.mesh(lumpy(new T.SphereGeometry(0.28, 28, 14, 0, Math.PI * 2, 0, Math.PI / 2), 82, 0.04), clay("#ef4a5a"), { pos: [0, 0.32, 0], parent: g }); for (let i = 0; i < 4; i++) { const a = i * 1.7; S.mesh(new T.SphereGeometry(0.045, 12, 8), clay("#ffffff"), { pos: [Math.cos(a) * 0.17, 0.48, Math.sin(a) * 0.17], parent: g }); } return g; };
    mush(-1.55, 0.9, 1); mush(-1.95, 0.3, 0.7); mush(1.85, 0.95, 0.8);
    const bug = S.group(S.scene, [1.3, 0, 1.8]); S.mesh(lumpy(new T.SphereGeometry(0.16, 24, 14, 0, Math.PI * 2, 0, Math.PI / 2), 90, 0.03), clay("#e8312f"), { parent: bug }); S.mesh(new T.SphereGeometry(0.08, 16, 10), clay("#232323"), { pos: [0.15, 0.05, 0], parent: bug }); [[-0.03, 0.12, 0.06], [0.05, 0.1, -0.08], [-0.08, 0.08, -0.05]].forEach((p) => S.mesh(new T.SphereGeometry(0.03, 10, 8), clay("#232323"), { pos: p, parent: bug }));
    const clouds = [[-1.6, 6.3, -2.6, 1.1], [1.9, 5.6, -2.8, 0.9], [0.4, 7.4, -3.2, 0.8]].map(([x, y, z, sc], i) => { const g = S.group(S.scene, [x, y, z]); g.scale.setScalar(sc); [[-0.5, 0, 0.4], [0, 0.2, 0.55], [0.5, 0, 0.42], [0.95, -0.08, 0.3], [-0.95, -0.08, 0.3]].forEach(([cx, cy, r], j) => S.mesh(lumpy(new T.SphereGeometry(r, 28, 16), 100 + i * 9 + j, 0.04), clay("#ffffff"), { pos: [cx, cy, 0], scale: [1, 1, 0.55], parent: g })); S.mesh(new T.CylinderGeometry(0.008, 0.008, 6, 6), S.mat.matte("#e8f7f5"), { pos: [0, 3, 0], parent: g }); return g; });

    // paper signs on toothpicks, one per step
    const sign = (n, word, x, t0, t1) => {
      const g = S.group(S.scene, [x, 1.15, 0.75]);
      S.mesh(new T.CylinderGeometry(0.018, 0.018, 1.0, 8), S.mat.matte("#f3e2c0"), { pos: [0, 0.5, 0], parent: g });
      const l = S.label(`${n}. ${word}`, { h: 0.36, font: "700 110px Fredoka", color: "#2b2b35", bg: "#fffaf0", radius: 30, pad: 40, parent: g, castShadow: true });
      l.position.set(0, 1.12, 0.01); g.userData = { t0, t1 }; return g;
    };
    const signs = [sign(1, C.steps[0], 0.45, 0.5, 2.6), sign(2, C.steps[1], 0.45, 2.75, 5.1), sign(3, C.steps[2], 0.45, 5.25, 9)];
    const sx = S.portrait ? 0 : 1.4;

    return (t) => {
      const ts = step(t);
      // seed drops in and squashes, then sinks into the soil
      const fall = K.tw(ts, 0.2, 0.75, K.ease.in), land = K.prog(ts, 0.75, 1.3), sink = K.tw(ts, 1.5, 2.2);
      seed.position.set(0.05, K.lerp(4.5, 1.2, fall) - sink * 0.22, 0.1);
      const sq = land > 0 && land < 1 ? Math.sin(land * Math.PI * 2) * 0.35 * (1 - land) : 0;
      seed.scale.set(1 + sq, 0.7 - sq * 0.8, 0.8 + sq); seed.visible = ts < 2.6;
      soil.scale.y = 0.16 + Math.max(0, Math.sin(K.prog(ts, 0.75, 1.1) * Math.PI)) * 0.03;
      // watering can tilts and pours
      const can01 = K.tw(ts, 2.6, 3.0, K.ease.back) * (1 - K.tw(ts, 4.6, 5.0));
      can.position.set(K.lerp(4.2, 1.55, can01), 2.6, 0.2); can.rotation.z = K.tw(ts, 3.0, 3.3) * 0.55 * (1 - K.tw(ts, 4.3, 4.6)); const cb = boil(can, ts, 3, 0.01); can.scale.setScalar(cb);
      drops.forEach((d, i) => { const ph = ((ts - 3.2) * 1.6 + i / drops.length) % 1, on = ts > 3.2 && ts < 4.5; d.visible = on; d.position.set(0.62 - ph * 0.25 + (i % 3) * 0.04, 2.35 - ph * 1.25, 0.2 + ((i % 2) - 0.5) * 0.1); });
      // the sun rises in the corner and turns slowly
      sun.position.y = K.lerp(7.6, 4.5, K.tw(ts, 2.9, 3.6, K.ease.back)); sun.rotation.z = ts * 0.4; sun.scale.setScalar(boil(sun, ts, 7, 0.006));
      // sprout -> sapling -> tree
      const grow = K.tw(ts, 3.4, 5.2, K.ease.out), big = K.tw(ts, 5.0, 6.4, K.ease.out);
      plant.scale.set(1, Math.max(0.001, grow * 0.55 + big * 0.45), 1);
      stem.visible = big < 0.5; trunk.visible = big >= 0.5; trunk.scale.set(1, 1, 1);
      leaves.forEach((l, i) => { const k = K.ease.spring(K.prog(ts, 3.9 + i * 0.25, 4.6 + i * 0.25)); l.scale.setScalar(Math.max(0.001, k * (1 - big))); });
      blobs.forEach((b, i) => { const k = K.ease.spring(K.prog(ts, b.userData.t0, b.userData.t0 + 0.7)); b.scale.setScalar(Math.max(0.001, k * boil(b, ts, 80 + i, 0.02))); });
      apples.forEach((a, i) => { a.scale.setScalar(Math.max(0.001, K.ease.spring(K.prog(ts, a.userData.t0, a.userData.t0 + 0.6)))); });
      clouds.forEach((g, i) => { g.rotation.z = Math.sin(ts * 1.2 + i) * 0.05; });
      bug.position.x = 1.3 - K.tw(ts, 1, 7) * 0.9; bug.rotation.y = Math.PI;
      pot.scale.setScalar(boil(pot, ts, 1, 0.006)); pot.rotation.x = pot.rotation.z = 0;
      // signs pop in and out (squash + stretch)
      signs.forEach((g, i) => { const a = K.ease.spring(K.prog(ts, g.userData.t0, g.userData.t0 + 0.6)), b = K.tw(ts, g.userData.t1 - 0.3, g.userData.t1, K.ease.in); const s = Math.max(0.001, a * (1 - b)); g.scale.set(s, s, s); g.rotation.z = (1 - a) * 0.4 - 0.08 + Math.sin(ts * 3 + i) * 0.02; });
      // camera: smooth, slow push then rise with the tree
      const ty = K.lerp(1.75, 2.4, K.tw(t, 3.5, 7.5)), reg = K.lerp(3.9, 4.7, K.tw(t, 3.5, 7.5));
      const d = S.fitDist(reg * (S.portrait ? 1.05 : 2.1), reg * 1.25, 32) * K.lerp(1.06, 1, K.tw(t, 0, 3));
      S.cam([sx * 0.4 + Math.sin(t * 0.25) * 0.5, ty + d * 0.18, d], [sx * 0.3, ty, 0], { fov: 32, aperture: 0.09 });
    };
  },

  sound(k) {
    k.bed("room", 0, 8, { vol: 0.9 });
    k.chords(0, 8, ["F4 A4 C5", "C4 E4 G4", "D4 F4 A4", "C4 E4 G4"], { bpm: 120, vol: 0.55, arp: true, arpVol: 0.25 });
    k.at(0.2, "whoosh", { dur: 0.5, vol: 0.35, down: true }); k.at(0.75, "clay", { vol: 0.9 }); k.at(1.05, "clay", { vol: 0.4, pitch: 1.3 });
    k.at(0.5, "pop", { vol: 0.4 }); k.at(1.5, "clay", { vol: 0.35, pitch: 0.8 });
    k.at(2.6, "whoosh", { dur: 0.4, vol: 0.4 }); k.at(2.75, "pop", { vol: 0.4 }); k.at(2.95, "spring", { vol: 0.35, pitch: 1.3 });
    for (let i = 0; i < 10; i++) k.at(3.25 + i * 0.12, "bubble", { vol: 0.25, pitch: 0.8 + (i % 4) * 0.12, pan: 0.2 });
    [3.9, 4.15].forEach((t) => k.at(t, "pop", { vol: 0.45, pitch: 1.3 }));
    k.at(5.0, "rise", { dur: 0.6, vol: 0.25 }); k.at(5.25, "pop", { vol: 0.4 });
    for (let i = 0; i < 6; i++) k.at(5.3 + i * 0.12, "clay", { vol: 0.45, pitch: 1 + i * 0.08 });
    for (let i = 0; i < 5; i++) k.at(6.3 + i * 0.13, "pop", { vol: 0.35, pitch: 1.5 + i * 0.1 });
    k.at(7.1, "sparkle", { vol: 0.4 });
  },
};
