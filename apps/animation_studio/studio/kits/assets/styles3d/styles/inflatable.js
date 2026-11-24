/* Claude 3D Styles: Inflatable (reference animation: "How your phone charges") */
(window.STYLES = window.STYLES || {})["inflatable"] = {
  name: "Inflatable",
  card: {
    family: "Handmade materials",
    look: "Everything is a shiny inflatable toy in a bright one-colour studio: puffy rounded shapes in candy colours, welded seams around their middles, mirror-like highlights. When something is empty it is limp, flat and wrinkled; when it is full it is round and tight.",
    motion: "Air drives the story: things inflate from limp to round, bounce and wobble like balloons, squash on contact and bob gently while they wait. Small balls travel along fat tubes to show flow.",
    light: "Big soft studio light from the front-left plus a bright overhead softbox, so every object gets a long white highlight; soft contact shadows on the floor.",
    materials: "Glossy PVC: clearcoat on, roughness about 0.2, saturated colours, white seam rings. The studio sweep is matte in one bright colour.",
    camera: "fov 28-32 at product height, a slow orbit and push-in, light depth of field.",
    finish: "Bright and punchy: ACES tone mapping, a touch of bloom on the highlights, light vignette.",
    goodFor: "Energy, filling up, growth, before/after, tech basics and product ideas told in a fun, friendly way.",
  },
  content: { title: "How your phone charges", steps: ["Plug in", "Energy flows in", "100% charged!"] },
  duration: 8,
  samples: 24,
  fonts: ["Baloo 2:800"],
  grade: { exposure: 0.92, tonemap: "aces", bloom: 0.18, bloomThreshold: 1.0, saturation: 1.12, contrast: 1.04, vignette: 0.25, grain: 0.01 },

  build(S) {
    const T = S.THREE, K = S.K, C = this.content;
    const vinyl = (c, o = {}) => new T.MeshPhysicalMaterial({ color: c, roughness: 0.22, clearcoat: 1, clearcoatRoughness: 0.12, ...o });
    S.env({ top: "#ffffff", bottom: "#ffd34d", horizon: "#fff1c2", boxes: [{ pos: [-4, 5, 6], size: [5, 4], color: "#ffffff", power: 7 }, { pos: [0, 9, 0], size: [8, 3], color: "#ffffff", power: 5 }, { pos: [7, 2, 3], size: [2, 6], color: "#ffffff", power: 3 }], intensity: 1.0 });
    S.scene.background = new T.Color("#ffc928");
    S.mesh(K.sweep(70, 30, 30, 8), S.mat.std("#ffc928", { roughness: 0.75 }), { pos: [0, 0, -5] });
    S.sun({ pos: [-5, 10, 7], intensity: 2.2, soft: 2.2, size: 8 });
    S.hemi("#fff8e6", "#ffb400", 0.5);

    // deform a geometry like an inflatable: limp = squat, wide, wrinkled
    const balloon = (geo) => { const P = geo.attributes.position; geo.userData.base = P.array.slice(); geo.userData.nrm = geo.attributes.normal.array.slice(); return geo; };
    const inflate = (geo, k, seed) => { const B = geo.userData.base, Nn = geo.userData.nrm, P = geo.attributes.position.array, w = (1 - k); for (let i = 0; i < P.length; i += 3) { const x = B[i], y = B[i + 1], z = B[i + 2]; const n = Math.sin(x * 9 + seed) * Math.sin(y * 7 + seed * 2) * Math.cos(z * 8 + seed * 3); const d = n * 0.09 * w - 0.05 * w; P[i] = x * (1 + 0.18 * w) + Nn[i] * d; P[i + 1] = (y + 1.8) * (0.42 + 0.58 * k) - 1.8 + Nn[i + 1] * d; P[i + 2] = z * (1 + 0.12 * w) + Nn[i + 2] * d; } geo.attributes.position.needsUpdate = true; geo.computeVertexNormals(); };

    // the battery
    const bat = S.group(S.scene, [0.4, 1.8, 0]);
    const bodyG = balloon(K.rbox(2.4, 3.6, 1.5, 0.7, 9));
    const body = S.mesh(bodyG, vinyl("#ffffff"), { parent: bat });
    const capG = balloon(K.rbox(0.9, 0.5, 0.7, 0.24, 6)); capG.translate(0, 0, 0); const cap = S.mesh(capG, vinyl("#3a3f55"), { parent: bat });
    const seam = S.mesh(new T.TorusGeometry(1, 0.035, 10, 64), vinyl("#f2f2f2", { roughness: 0.3 }), { parent: bat, rot: [Math.PI / 2, 0, 0] });
    seam.scale.set(1.22, 0.78, 1);
    // level pills on the front
    const pills = [0, 1, 2, 3].map((i) => { const g = balloon(K.rbox(1.6, 0.58, 0.42, 0.26, 6)); const m = S.mesh(g, vinyl(i === 3 ? "#2fd06a" : "#38d873"), { parent: bat }); m.userData.g = g; return m; });

    // the plug + fat cable
    const plug = S.group(S.scene);
    S.mesh(K.rbox(0.9, 0.7, 0.7, 0.3, 6), vinyl("#2f6bff"), { parent: plug });
    [-0.17, 0.17].forEach((y) => S.mesh(K.rbox(0.42, 0.1, 0.16, 0.05), S.mat.metal("#d7dbe3", { roughness: 0.2 }), { pos: [0.6, y, 0], parent: plug }));
    const cablePts = (px, py, pz) => new T.CatmullRomCurve3([new T.Vector3(-9, 0.25, 2.4), new T.Vector3(-6, 0.25, 2.2), new T.Vector3(-4, 0.3, 1.2), new T.Vector3(px - 1.5, py - 0.4, pz), new T.Vector3(px - 0.45, py, pz)]);
    const cable = S.mesh(new T.TubeGeometry(cablePts(-3, 1, 0.5), 80, 0.17, 16), vinyl("#2f6bff"), {});
    const sparks = []; for (let i = 0; i < 14; i++) sparks.push(S.mesh(new T.SphereGeometry(0.12, 18, 12), vinyl("#ffe14d", { emissive: "#ffb300", emissiveIntensity: 1.6 }), { shadow: false }));

    // the bolt
    const boltS = new T.Shape([[0.15, 1], [-0.55, -0.1], [-0.05, -0.1], [-0.2, -1], [0.55, 0.15], [0.05, 0.15], [0.15, 1]].map((p) => new T.Vector2(...p)));
    const bolt = S.mesh(new T.ExtrudeGeometry(boltS, { depth: 0.18, bevelEnabled: true, bevelThickness: 0.16, bevelSize: 0.12, bevelSegments: 6, curveSegments: 12 }), vinyl("#ffdf3b", { emissive: "#ffb000", emissiveIntensity: 0.25 }), { parent: bat });

    // floating balloon tags for the words
    const tag = (n, word, pos, t0, t1, big) => { const l = S.label(big ? word : `${n}. ${word}`, { h: big ? 0.95 : 0.7, font: "800 130px 'Baloo 2'", color: big ? "#ffffff" : "#1f2a52", bg: big ? "#2fd06a" : "#ffffff", radius: 999, pad: 54, lit: false }); l.position.set(...pos); l.userData = { t0, t1, p: pos, big, size: l.userData.size }; return l; };
    const tags = [tag(1, C.steps[0], [-0.2, 4.75, 0.8], 0.9, 2.6), tag(2, C.steps[1], [0, 4.75, 0.8], 2.8, 5.6), tag(0, C.steps[2], [0.15, 4.95, 0.8], 5.9, 9, true)];
    // background balloons
    const bgB = [[-3.2, 4.6, -3, "#ff5c8a"], [3.4, 5.4, -3.5, "#2f6bff"], [3.0, 1.2, -2, "#ff7a2f"], [-3.4, 1.0, -1.5, "#7a5cff"]].map(([x, y, z, c], i) => { const g = S.group(S.scene, [x, y, z]); S.mesh(new T.SphereGeometry(0.75, 40, 24), vinyl(c), { scale: [1, 1.18, 1], parent: g }); S.mesh(new T.ConeGeometry(0.12, 0.2, 16), vinyl(c), { pos: [0, -0.95, 0], rot: [Math.PI, 0, 0], parent: g }); return g; });

    return (t) => {
      const fill = K.tw(t, 2.6, 5.6, K.ease.inOut), k = 0.15 + 0.85 * fill;
      inflate(bodyG, k, 1); inflate(capG, 0.4 + 0.6 * fill, 2);
      // battery wobble + happy bounce at the end
      const hop = Math.max(0, Math.sin(K.prog(t, 6.0, 6.7) * Math.PI)) * 0.6 + Math.max(0, Math.sin(K.prog(t, 6.7, 7.2) * Math.PI)) * 0.2;
      bat.position.y = 1.8 + hop - (1 - k) * 0.0; bat.rotation.z = Math.sin(t * 3) * 0.02 * (1 - fill) + Math.sin(t * 2) * 0.015;
      const top = -1.8 + 3.6 * (0.42 + 0.58 * k); cap.position.set(0, top + 0.12, 0); seam.position.y = -1.8 + 1.8 * (0.42 + 0.58 * k); seam.scale.set(1.22 * (1 + 0.15 * (1 - k)), 0.78 * (1 + 0.1 * (1 - k)), 1);
      pills.forEach((m, i) => { const pk = K.ease.spring(K.prog(t, 3.0 + i * 0.75, 3.6 + i * 0.75)); inflate(m.userData.g, 0.2 + 0.8 * K.clamp(pk), 5 + i); m.scale.setScalar(Math.max(0.001, K.clamp(pk * 1.1))); m.position.set(0, -1.8 + (0.42 + 0.58 * k) * (0.62 + i * 0.78), 0.62 + 0.12 * k); });
      // plug flies in and docks into the battery's side
      const dock = K.ease.spring(K.prog(t, 0.6, 1.6)), px = K.lerp(-6.5, -1.55, dock), py = K.lerp(2.2, 0.9, dock) + (1 - dock) * Math.sin(t * 6) * 0.1, pz = 0.25;
      plug.position.set(px, py, pz); plug.rotation.z = (1 - dock) * 0.5;
      cable.geometry.dispose(); const cv = cablePts(px, py, pz); cable.geometry = new T.TubeGeometry(cv, 80, 0.17, 16);
      // energy balls race along the cable into the battery
      sparks.forEach((s, i) => { const ph = ((t * 0.55 + i / sparks.length) % 1), on = K.prog(t, 2.2, 2.6) * (1 - K.prog(t, 5.8, 6.2)); const p = cv.getPointAt(ph); s.position.copy(p); s.scale.setScalar(Math.max(0.001, on * (0.7 + 0.3 * Math.sin(ph * Math.PI)))); });
      // bolt pops on the front
      const bk = K.ease.spring(K.prog(t, 5.6, 6.3)); bolt.scale.setScalar(Math.max(0.001, bk * 1.05)); bolt.position.set(0, 0.2 + hop * 0, 0.86); bolt.rotation.y = (1 - bk) * 1.5;
      pills.forEach((m) => (m.visible = bk < 0.98 || true));
      // tags
      tags.forEach((l, i) => { const a = K.ease.spring(K.prog(t, l.userData.t0, l.userData.t0 + 0.7)), b = K.tw(t, l.userData.t1 - 0.25, l.userData.t1, K.ease.in); l.visible = a * (1 - b) > 0.002; l.position.y += 0; l.userData.ab = Math.max(0.001, a * (1 - b)); });
      bgB.forEach((g, i) => { g.position.y += 0; g.rotation.z = Math.sin(t * 1.4 + i) * 0.08; g.children.forEach((c) => (c.position.y = (c.position.y < -0.5 ? -0.95 : 0) + Math.sin(t * 1.6 + i * 2) * 0.12)); });
      // camera
      const d = (S.portrait ? S.fitDist(5.0, 6.8, 30) : S.fitDist(10, 6.4, 30)) * K.lerp(1.06, 0.97, K.tw(t, 0, 8, K.ease.sine));
      const a = K.lerp(-0.28, 0.18, K.tw(t, 0, 8, K.ease.sine));
      S.cam([Math.sin(a) * d + 0.05, 2.5 + d * 0.1, Math.cos(a) * d], [0.05, 2.35, 0], { fov: 30, aperture: 0.06 });
      tags.forEach((l) => S.pin(l, 0, S.portrait ? 0.66 : 0.76, l.userData.big ? (S.portrait ? 0.66 : 0.34) : (S.portrait ? 0.56 : 0.3), l.userData.size[0], l.userData.ab || 0.001));
    };
  },

  sound(k) {
    k.bed("room", 0, 8, { vol: 0.8 });
    k.chords(0, 8, ["C4 E4 G4", "A3 C4 E4", "F3 A3 C4", "G3 B3 D4"], { bpm: 120, vol: 0.5, arp: true, arpVol: 0.25 });
    k.at(0.6, "whoosh", { dur: 0.6, vol: 0.45 }); k.at(1.25, "snap", { vol: 0.8 }); k.at(1.28, "thud", { vol: 0.5, pitch: 1.4 }); k.at(1.3, "zap", { vol: 0.5 });
    k.at(2.2, "rise", { dur: 3.4, vol: 0.22 }); k.bed("motor", 2.4, 5.8, { vol: 0.5, pitch: 2.4 });
    for (let i = 0; i < 18; i++) k.at(2.4 + i * 0.18, "blip", { vol: 0.12, f: 880 + (i % 4) * 110, pan: -0.5 });
    for (let i = 0; i < 4; i++) { k.at(3.05 + i * 0.75, "bubble", { vol: 0.6, pitch: 0.7 + i * 0.12 }); k.at(3.1 + i * 0.75, "ping", { f: ["C6", "E6", "G6", "C7"][i], vol: 0.3 }); }
    k.at(5.6, "spring", { vol: 0.6 }); k.at(5.7, "zap", { vol: 0.4 }); k.at(6.0, "boom", { vol: 0.35, pitch: 1.6 }); k.at(6.2, "chime", { f: "C6", vol: 0.55 }); k.at(6.3, "sparkle", { vol: 0.5 });
    k.at(6.05, "spring", { vol: 0.35, pitch: 0.8 }); k.at(6.75, "spring", { vol: 0.25, pitch: 1.1 });
  },
};
