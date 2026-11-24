/* Claude 3D Styles: Low-Poly (reference animation: "How a hurricane forms") */
(window.STYLES = window.STYLES || {})["low-poly"] = {
  name: "Low-Poly",
  card: {
    family: "Worlds and journeys",
    look: "A faceted world where every triangle is one flat tone: a sea of moving triangles, a little island with cone palms, chunky gem-like clouds and a polygon sun, in a fresh palette of turquoise, sand, leaf green and warm coral against a peach-to-blue sky.",
    motion: "The sea rolls in slow triangle waves. Pieces rise, gather and swirl along clear paths; colours shift across the facets to show change (cool water warming up). The camera sweeps from a low view over the water up to a high, top-down view for the finale.",
    light: "Bright low sun from one side so the facets alternate light and shade, soft shadows, sky fill so the shade stays colourful.",
    materials: "flatShading on everything, roughness 0.8, a short palette with neighbours differing slightly, no textures.",
    camera: "fov 35-40, one continuous sweeping move with light depth of field.",
    finish: "Fresh and bright: ACES tone mapping, gentle bloom on the sun, soft vignette.",
    goodFor: "Nature and science processes that happen in a place: weather, water, volcanoes, ecosystems, journeys across a landscape.",
  },
  content: { title: "How a hurricane forms", steps: ["Warm water", "Rising air", "The storm spins"] },
  duration: 8,
  samples: 24,
  fonts: ["Rubik:800"],
  grade: { exposure: 1.0, tonemap: "aces", bloom: 0.25, bloomThreshold: 1.1, saturation: 1.12, contrast: 1.05, vignette: 0.3, grain: 0.01 },

  build(S) {
    const T = S.THREE, K = S.K, C = this.content, R = K.rng(4);
    const flat = (c, o = {}) => new T.MeshStandardMaterial({ color: c, roughness: 0.8, flatShading: true, ...o });
    S.gradientBg("#5aa9f0", "#ffd7b0", { mid: "#a9d4f7" });
    S.scene.fog = new T.Fog("#f3d9c2", 22, 55);
    S.env({ top: "#cfe6ff", bottom: "#ffd8b8", intensity: 0.5 });
    S.sun({ pos: [-12, 9, -6], intensity: 3.2, soft: 0.8, size: 14, color: "#fff0dc" });
    S.hemi("#bfe0ff", "#ffcfa8", 0.75);

    // the sea: one flat-shaded sheet of triangles, waves move the vertices, colours warm up in the middle
    const sea = new T.PlaneGeometry(60, 60, 64, 64).rotateX(-Math.PI / 2).toNonIndexed();
    const P = sea.attributes.position, base = P.array.slice(), cols = new Float32Array(P.count * 3); sea.setAttribute("color", new T.BufferAttribute(cols, 3));
    const seaMesh = S.mesh(sea, new T.MeshStandardMaterial({ vertexColors: true, roughness: 0.55, flatShading: true }), { shadow: false }); seaMesh.receiveShadow = true;
    const cool = [new T.Color("#22b4c8"), new T.Color("#2ebfcd"), new T.Color("#1ba9c2")], warm = [new T.Color("#ff9466"), new T.Color("#ffa071"), new T.Color("#fb875e")];
    const triShade = []; for (let i = 0; i < P.count / 3; i++) triShade.push(Math.floor(R() * 3));

    // the island with cone palms
    const isle = S.group(S.scene, [-3.4, 0, 4.2]);
    const rock = new T.IcosahedronGeometry(2.4, 1); rock.scale(1, 0.32, 0.8); S.mesh(rock, flat("#f2d29b"), { pos: [0, -0.15, 0], parent: isle });
    const hill = new T.IcosahedronGeometry(1.3, 0); hill.scale(1, 0.6, 0.8); S.mesh(hill, flat("#6cbf5a"), { pos: [0.3, 0.35, -0.2], parent: isle });
    const palm = (x, z, s) => { const g = S.group(isle, [x, 0.3, z]); g.scale.setScalar(s); S.mesh(new T.CylinderGeometry(0.07, 0.12, 1.4, 5), flat("#b98551"), { pos: [0, 0.7, 0], rot: [0, 0, 0.12], parent: g }); for (let i = 0; i < 5; i++) { const a = (i / 5) * Math.PI * 2, l = S.mesh(new T.ConeGeometry(0.22, 1.0, 4), flat(i % 2 ? "#3fa35a" : "#56b867"), { pos: [Math.cos(a) * 0.4 + 0.08, 1.38, Math.sin(a) * 0.4], parent: g }); l.rotation.set(Math.sin(a) * 1.3, 0, -Math.cos(a) * 1.3); } return g; };
    const palms = [palm(-0.9, 0.3, 1), palm(1.1, 0.5, 0.85), palm(0, -0.8, 0.75)];

    // the sun
    const sunG = S.group(S.scene, [-6, 9.5, -24]);
    S.mesh(new T.IcosahedronGeometry(2.6, 1), S.mat.glow("#ffc04a", 1.15), { parent: sunG, shadow: false });

    // sky clouds and far islands fill the upper frame
    [[-9, 8.5, -20, 2.2], [7, 10.5, -26, 2.8], [1, 13, -30, 2.4], [-14, 12, -30, 2.0], [12, 7, -18, 1.6]].forEach(([x, y, z, sc], i) => { const g = S.group(S.scene, [x, y, z]); g.scale.setScalar(sc); [[-0.8, 0, 0.7], [0, 0.35, 0.95], [0.85, 0, 0.75], [1.6, -0.15, 0.5], [-1.5, -0.15, 0.5]].forEach(([cx, cy, r]) => S.mesh(new T.IcosahedronGeometry(r, 0), flat("#ffffff", { roughness: 0.9 }), { pos: [cx, cy, 0], scale: [1, 0.8, 0.7], parent: g, shadow: false })); });
    [[-16, -30, 4.5, "#7fae8f"], [-6, -34, 3.2, "#8bb89a"], [14, -32, 5.5, "#78a689"], [24, -26, 3.5, "#86b495"]].forEach(([x, z, h, c]) => { const g = new T.ConeGeometry(h * 1.6, h, 5); S.mesh(g, flat(c), { pos: [x, h / 2 - 0.3, z], shadow: false }); });

    // heat arrows rising off the warm water
    const arrows = []; for (let i = 0; i < 7; i++) { const g = S.group(S.scene); S.mesh(new T.ConeGeometry(0.26, 0.5, 4), flat("#ff7a4a", { emissive: "#ff5a2a", emissiveIntensity: 0.4 }), { pos: [0, 0.5, 0], parent: g, shadow: false }); S.mesh(new T.CylinderGeometry(0.07, 0.07, 0.6, 4), flat("#ff7a4a", { emissive: "#ff5a2a", emissiveIntensity: 0.4 }), { pos: [0, 0, 0], parent: g, shadow: false }); const a = (i / 7) * Math.PI * 2; arrows.push({ g, x: Math.cos(a) * (1.4 + (i % 3) * 0.8), z: Math.sin(a) * (1.4 + (i % 3) * 0.8), d: i * 0.13 }); }

    // vapour puffs that rise, gather into clouds, then wind into a spiral storm
    const puffs = [], N = 95;
    for (let i = 0; i < N; i++) {
      const r = 0.22 + R() * 0.3, m = S.mesh(new T.IcosahedronGeometry(r, 0), flat(i % 4 === 0 ? "#dfe6ef" : "#ffffff", { roughness: 0.9 }), { shadow: true });
      const a0 = R() * Math.PI * 2, r0 = 0.6 + R() * 3.4, arm = i % 3, rr = 0.8 + (i / N) * 5.6, aa = (arm * Math.PI * 2) / 3 + (i / N) * 4.2;
      puffs.push({ m, start: [Math.cos(a0) * r0, 0.2, Math.sin(a0) * r0], cloud: [Math.cos(a0) * r0 * 0.9, 3.0 + R() * 1.4, Math.sin(a0) * r0 * 0.9], rr, aa, h: 2.6 + R() * 0.8 + (1 - i / N) * 0.6, d: R() * 0.9, rot: R() * 6 });
    }
    // labels (white banners with a coral number) that face the camera
    const banner = (n, word, pos, t0) => { const l = S.label(word, { h: 0.85, font: "800 120px Rubik", color: "#24324d", bg: "#ffffff", radius: 30, pad: 40, extraW: 150, lit: false, draw: (x, w, h) => { x.clearRect(0, 0, w, h); x.fillStyle = "#fff"; x.beginPath(); x.roundRect(0, 0, w, h, 30); x.fill(); x.font = "800 120px Rubik"; x.fillStyle = "#24324d"; x.textAlign = "left"; x.fillText(word, 190, 40 + 104); x.fillStyle = "#ff6f4f"; x.beginPath(); x.roundRect(28, 22, 130, h - 44, 22); x.fill(); x.fillStyle = "#fff"; x.textAlign = "center"; x.fillText(n, 93, 40 + 104); } }); l.position.set(...pos); l.userData = { t0, p: pos }; return l; };
    const labels = [banner("1", C.steps[0], [1.2, 2.3, 3.2], 0.7), banner("2", C.steps[1], [-0.4, 6.2, 0.6], 2.9), banner("3", C.steps[2], [0, 5.2, 4.6], 5.3)];

    const cam = [[0, [2.5, 3.2, 19], [-0.6, 1.6, 0]], [2.6, [4.5, 6.5, 19], [0, 3.0, 0]], [4.9, [3.5, 13, 16], [0, 3.2, 0]], [8, [0.8, 24, 7.5], [0, 2.4, 0.4]]];

    return (t) => {
      const heat = K.tw(t, 0.4, 2.4), spin = K.tw(t, 4.9, 8, K.ease.in);
      // waves + colour
      const c = new T.Color();
      for (let i = 0; i < P.count; i++) { const x = base[i * 3], z = base[i * 3 + 2]; P.array[i * 3 + 1] = Math.sin(x * 0.42 + t * 1.3) * 0.3 + Math.cos(z * 0.5 - t * 1.1) * 0.26 + Math.sin((x + z) * 0.23 + t) * 0.16; }
      for (let f = 0; f < P.count / 3; f++) { const i = f * 3, x = (base[i * 3] + base[i * 3 + 3] + base[i * 3 + 6]) / 3, z = (base[i * 3 + 2] + base[i * 3 + 5] + base[i * 3 + 8]) / 3; const d = Math.hypot(x, z), w = heat * K.clamp(1.15 - d / 6.5); const sh = triShade[f]; c.copy(cool[sh]).lerp(warm[sh], K.smooth(K.clamp(w * 1.4))); for (let k = 0; k < 3; k++) { cols[(i + k) * 3] = c.r; cols[(i + k) * 3 + 1] = c.g; cols[(i + k) * 3 + 2] = c.b; } }
      P.needsUpdate = true; sea.attributes.color.needsUpdate = true;
      palms.forEach((p, i) => (p.rotation.z = Math.sin(t * 2 + i) * 0.05 + spin * 0.25));
      sunG.rotation.y = t * 0.2;
      // heat arrows
      arrows.forEach((a, i) => { const ph = ((t * 0.7 + a.d) % 1), on = K.prog(t, 0.8, 1.3) * (1 - K.prog(t, 4.6, 5.2)); a.g.position.set(a.x, 0.2 + ph * 2.4, a.z); a.g.scale.setScalar(Math.max(0.001, on * Math.sin(ph * Math.PI))); });
      // vapour -> clouds -> spiral
      puffs.forEach((p) => {
        const rise = K.tw(t, 2.5 + p.d, 4.4 + p.d * 0.6, K.ease.inOut), sw = K.tw(t, 4.8 + p.d * 0.3, 6.6 + p.d * 0.3, K.ease.inOut);
        const ang = p.aa + spin * 9 + t * 0.4 * sw, sx = Math.cos(ang) * p.rr, sz = Math.sin(ang) * p.rr;
        const x = K.lerp(K.lerp(p.start[0], p.cloud[0], rise), sx, sw), y = K.lerp(K.lerp(p.start[1], p.cloud[1], rise), p.h + Math.sin(ang * 2) * 0.15, sw), z = K.lerp(K.lerp(p.start[2], p.cloud[2], rise), sz, sw);
        p.m.position.set(x, y, z); p.m.rotation.set(p.rot + t * 0.3, p.rot + t * 0.5, 0); const s = K.ease.back(K.prog(t, 2.4 + p.d, 2.9 + p.d)); p.m.scale.set(s * (1 + sw * 0.6), s * (1 - sw * 0.25), s * (1 + sw * 0.6));
      });
      // camera + labels facing it
      const pos = K.keys(t, cam.map(([a, b]) => [a, b])), tgt = K.keys(t, cam.map(([a, , b]) => [a, b]));
      const back = S.portrait ? 1 : 0.62; const cp = [pos[0] * back, pos[1], pos[2] * back];
      labels.forEach((l, i) => { const a = K.ease.back(K.prog(t, l.userData.t0, l.userData.t0 + 0.5)), b = i < 2 ? K.tw(t, [2.6, 4.9][i], [2.9, 5.2][i]) : 0; l.scale.setScalar(Math.max(0.001, a * (1 - b))); l.lookAt(cp[0], cp[1], cp[2]); });
      S.cam(cp, tgt, { fov: 38, aperture: 0.06 });
    };
  },

  sound(k) {
    k.bed("water", 0, 8, { vol: 0.9 }); k.bed("wind", 2.4, 8, { vol: 1.2 }); k.bed("wind", 5, 8, { vol: 1.4, pitch: 1.6 });
    k.chords(0, 8, ["D4 F#4 A4", "B3 D4 F#4", "G3 B3 D4", "A3 C#4 E4"], { bpm: 120, vol: 0.5 });
    k.at(0.7, "pop", { vol: 0.4 }); k.at(0.9, "rise", { dur: 1.4, vol: 0.18 });
    for (let i = 0; i < 6; i++) k.at(2.5 + i * 0.25, "bubble", { vol: 0.25, pitch: 0.7 + i * 0.1, pan: (i % 2) - 0.5 });
    k.at(2.9, "pop", { vol: 0.4, pitch: 1.2 }); k.at(3.2, "whoosh", { dur: 1.2, vol: 0.4 });
    k.at(4.8, "rise", { dur: 1.6, vol: 0.3 }); k.at(5.3, "pop", { vol: 0.45, pitch: 1.4 }); k.at(5.6, "whoosh", { dur: 0.9, vol: 0.5 }); k.at(6.3, "whoosh", { dur: 0.8, vol: 0.5, down: true });
    k.at(6.8, "boom", { vol: 0.6 }); k.at(7.0, "whoosh", { dur: 1, vol: 0.4 });
  },
};
