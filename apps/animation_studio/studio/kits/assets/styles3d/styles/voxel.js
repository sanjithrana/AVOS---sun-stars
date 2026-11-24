/* Claude 3D Styles: Voxel (reference animation: "How a city grows") */
(window.STYLES = window.STYLES || {})["voxel"] = {
  name: "Voxel",
  card: {
    family: "Worlds and journeys",
    look: "Everything is built from small cubes on a square display plinth: a short, cheerful palette where every cube is a shade apart from its neighbours, tiny bevels that catch the light, water and glass in see-through blue. Like a hand-built block model on a desk.",
    motion: "Cubes drop in from above one by one and land with a little bounce, building things up layer by layer in a wave across the board. Things grow upward to show time passing. The camera slowly turns around the plinth.",
    light: "Bright top-left sun with crisp soft shadows between the blocks, a cool sky fill, gentle reflections on the glass cubes.",
    materials: "Matte painted blocks (roughness ~0.6) with small rounded edges; glassy blue cubes for water and windows; a dark wooden plinth.",
    camera: "Three-quarter view from above (fov 28-32), a slow quarter turn around the model, rising as things grow; light depth of field.",
    finish: "Bright and crisp, ACES tone mapping, soft vignette, light grain.",
    goodFor: "Growth over time, building and construction, games and Minecraft-style topics, cities, maps, data made physical.",
  },
  content: { title: "How a city grows", steps: ["Village", "Town", "City"] },
  duration: 8,
  samples: 20,
  fonts: ["Press Start 2P:400", "Inter:800"],
  grade: { exposure: 1.02, tonemap: "aces", bloom: 0.1, saturation: 1.1, contrast: 1.05, vignette: 0.3, grain: 0.012 },

  build(S) {
    const T = S.THREE, K = S.K, C = this.content, R = K.rng(12);
    S.gradientBg("#7cc4ff", "#eaf6ff", { mid: "#b9e0ff" });
    S.env({ top: "#d6ecff", bottom: "#9bb3c9", intensity: 0.5 });
    S.sun({ pos: [-12, 20, 9], intensity: 3.0, soft: 1.4, size: 16, map: 4096 });
    S.hemi("#cfe8ff", "#a28b6c", 0.65);
    S.shadowFloor(0.18, 120, -3.2);

    const N = 20, half = N / 2;
    const vox = []; // {x,y,z,c,t}
    const add = (x, y, z, c, t) => vox.push({ x: x - half + 0.5, y: y + 0.5, z: z - half + 0.5, c, t });
    const shade = (c, j = 0.06) => { const col = new T.Color(c); const hsl = {}; col.getHSL(hsl); return new T.Color().setHSL(hsl.h, hsl.s, K.clamp(hsl.l + (R() - 0.5) * j * 2)); };
    // river path: x = f(z)
    const riverX = (z) => 4 + Math.round(Math.sin(z * 0.45) * 1.6);
    const isRiver = (x, z) => Math.abs(x - riverX(z)) <= 1;
    const roadZ = 11, isRoad = (x, z, stage) => (z === roadZ || z === roadZ + 1) && x > 6 || (stage > 0 && (x === 12 || x === 13) && z > 2);
    // ground: two layers, dirt + grass (water sits lower)
    for (let x = 0; x < N; x++) for (let z = 0; z < N; z++) {
      const w = isRiver(x, z), t0 = 0.05 + (x + z) * 0.012;
      add(x, 0, z, shade("#9b6a43"), t0);
      if (!w) add(x, 1, z, shade("#6cc04a"), t0 + 0.05); else add(x, 0.6, z, new T.Color("#3aa6ff"), t0 + 0.08);
    }
    // roads (grey tops replace grass visually by sitting a hair above)
    const roadVox = [];
    for (let x = 0; x < N; x++) for (let z = 0; z < N; z++) { if (isRiver(x, z)) continue; if ((z === roadZ || z === roadZ + 1) && x > 6) roadVox.push([x, z, 2.7]); else if ((x === 12 || x === 13) && z > 2 && z !== roadZ && z !== roadZ + 1) roadVox.push([x, z, 2.9]); }
    roadVox.forEach(([x, z, t]) => add(x, 1.05, z, shade("#8d95a3", 0.03), t + (x + z) * 0.01));
    // bridge over the river at the road
    for (let x = 2; x <= 7; x++) for (let z = roadZ; z <= roadZ + 1; z++) add(x, 1.3, z, shade("#b5835a"), 3.0 + x * 0.04);
    // trees
    const tree = (x, z, t) => { add(x, 2, z, shade("#7a4e2e"), t); add(x, 3, z, shade("#3e9e45"), t + 0.08); [[1, 0], [-1, 0], [0, 1], [0, -1]].forEach(([a, b], i) => add(x + a, 3, z + b, shade("#4fb04f"), t + 0.12 + i * 0.02)); add(x, 4, z, shade("#5cbf58"), t + 0.2); };
    [[1, 2], [0, 7], [2, 15], [8, 1], [17, 2], [18, 16], [9, 18], [15, 8]].forEach(([x, z], i) => tree(x, z, 0.7 + i * 0.08));
    // buildings: footprint w x d, height h, colour, roof colour, start time
    const building = (x, z, w, d, h, wall, roof, t0, glass = false) => { let k = 0; for (let y = 2; y < 2 + h; y++) for (let a = 0; a < w; a++) for (let b = 0; b < d; b++) { const edge = a === 0 || b === 0 || a === w - 1 || b === d - 1; if (!edge && y < 1 + h) continue; const win = glass ? (y % 2 === 0 && edge && (a + b) % 2 === 1) : (y > 2 && edge && (a + b + y) % 3 === 0); add(x + a, y, z + b, win ? new T.Color(glass ? "#bfe6ff" : "#ffe08a") : shade(y === 1 + h ? roof : wall, 0.04), t0 + k++ * 0.012); } };
    // 1 village: little houses with red roofs
    [[8, 4], [9, 7], [15, 4], [16, 13], [7, 14]].forEach(([x, z], i) => building(x, z, 2, 2, 2, "#fff0d6", "#e8553f", 0.9 + i * 0.22));
    // 2 town: bigger, varied buildings
    [[14, 5, 3, 3, 4, "#ffd166"], [15, 14, 3, 3, 5, "#9ad1ff"], [8, 14, 3, 3, 4, "#ffb3c7"], [16, 9, 2, 2, 3, "#c3f584"], [9, 3, 3, 2, 3, "#ffffff"]].forEach(([x, z, w, d, h, c], i) => building(x, z, w, d, h, c, "#5a6474", 2.9 + i * 0.3));
    // 3 city: tall glass towers
    [[14, 5, 3, 3, 12, "#3d7bd9"], [15, 14, 3, 3, 15, "#2f6cc6"], [8, 13, 3, 3, 10, "#5a8ee6"], [9, 6, 3, 3, 9, "#7aa6f0"], [17, 9, 2, 3, 8, "#4a82dd"]].forEach(([x, z, w, d, h, c], i) => building(x, z, w, d, h, c, "#e6eef8", 5.1 + i * 0.32, true));

    // instanced cubes
    const geo = K.rbox(0.96, 0.96, 0.96, 0.08, 2);
    const mat = new T.MeshStandardMaterial({ roughness: 0.6, metalness: 0 });
    const inst = new T.InstancedMesh(geo, mat, vox.length); inst.castShadow = inst.receiveShadow = true; S.scene.add(inst);
    vox.forEach((v, i) => inst.setColorAt(i, v.c)); inst.instanceColor.needsUpdate = true;
    // town buildings get replaced by city towers: anything in a tower footprint from the town set disappears when the tower starts
    const m4 = new T.Matrix4(), q = new T.Quaternion(), sc = new T.Vector3(), ps = new T.Vector3();
    // the plinth
    S.mesh(K.rbox(N + 1.2, 1.4, N + 1.2, 0.25), S.mat.std("#5b3b28", { roughness: 0.55 }), { pos: [0, -0.75, 0] });
    S.mesh(K.rbox(N + 1.6, 0.25, N + 1.6, 0.1), S.mat.std("#3d271b", { roughness: 0.5 }), { pos: [0, -1.55, 0] });
    // tags
    const tag = (n, word, t0, t1) => { const l = S.label(`${n}  ${word}`, { h: 1, font: "400 90px 'Press Start 2P'", color: "#1d2b4f", bg: "#ffffff", radius: 10, pad: 44, lit: false, border: "#1d2b4f", borderW: 10 }); l.userData = { t0, t1, size: l.userData.size }; return l; };
    const tags = [tag(1, C.steps[0], 0.8, 2.8), tag(2, C.steps[1], 2.9, 5.0), tag(3, C.steps[2], 5.1, 9)];
    const towerFoot = [[14, 5, 3, 3], [15, 14, 3, 3], [8, 13, 3, 3], [9, 6, 3, 3], [17, 9, 2, 3]].map(([x, z, w, d], i) => ({ x0: x - half, x1: x + w - half, z0: z - half, z1: z + d - half, t: 5.1 + i * 0.32 }));
    const villageFoot = (v) => towerFoot.find((f) => v.x > f.x0 - 0.6 && v.x < f.x1 + 0.6 && v.z > f.z0 - 0.6 && v.z < f.z1 + 0.6);

    return (t) => {
      vox.forEach((v, i) => {
        let k = K.prog(t, v.t, v.t + 0.45); let s = k > 0 ? 1 : 0;
        // older, smaller buildings in a tower's footprint vanish when the tower starts
        if (v.y > 2 && v.c && v.t < 5) { const f = villageFoot(v); if (f && t > f.t - 0.15) s = 0; }
        const y = v.y + (1 - K.ease.bounce(k)) * 6;
        ps.set(v.x, y, v.z); sc.setScalar(s * (0.6 + 0.4 * K.clamp(k * 3)) + 1e-4); m4.compose(ps, q, sc); inst.setMatrixAt(i, m4);
      });
      inst.instanceMatrix.needsUpdate = true;
      const grow = K.tw(t, 0.5, 7.5);
      const az = 0.62 + K.lerp(0, 0.55, K.tw(t, 0, 8, K.ease.sine)), el = 0.62, d = (S.portrait ? 64 : 40) * K.lerp(1.0, 1.06, grow);
      const tgt = [0, K.lerp(0.5, 5.0, grow), 0];
      S.cam([Math.sin(az) * Math.cos(el) * d, Math.sin(el) * d + tgt[1], Math.cos(az) * Math.cos(el) * d], tgt, { fov: 30, aperture: 0.12 });
      tags.forEach((l) => { const a = K.ease.back(K.prog(t, l.userData.t0, l.userData.t0 + 0.4)), b = K.tw(t, l.userData.t1 - 0.25, l.userData.t1, K.ease.in); S.pin(l, 0, S.portrait ? 0.66 : 0.8, S.portrait ? 0.62 : 0.32, l.userData.size[0], a * (1 - b)); });
    };
  },

  sound(k) {
    k.bed("wind", 0, 8, { vol: 0.5 });
    k.chords(0, 8, ["C4 E4 G4", "G3 B3 D4", "A3 C4 E4", "F3 A3 C4"], { bpm: 120, vol: 0.5, arp: true, arpVol: 0.28, wave: "square", bright: 1400 });
    for (let i = 0; i < 18; i++) k.at(0.1 + i * 0.05, "tap", { vol: 0.12, pitch: 0.8 + (i % 4) * 0.1 });
    for (let i = 0; i < 12; i++) k.at(0.9 + i * 0.12, "knock", { vol: 0.25, pitch: 1 + (i % 3) * 0.12 });
    k.at(0.8, "blip", { f: "C6", vol: 0.25 }); k.at(2.9, "blip", { f: "E6", vol: 0.25 }); k.at(5.1, "blip", { f: "G6", vol: 0.25 });
    for (let i = 0; i < 20; i++) k.at(2.9 + i * 0.1, "knock", { vol: 0.22, pitch: 0.9 + (i % 4) * 0.1 });
    k.at(5.0, "rise", { dur: 2, vol: 0.2 }); for (let i = 0; i < 26; i++) k.at(5.1 + i * 0.09, "tap", { vol: 0.18, pitch: 1.2 + (i % 5) * 0.08 });
    k.at(7.2, "sparkle", { vol: 0.4 }); k.at(7.25, "coin", { vol: 0.35 });
  },
};
