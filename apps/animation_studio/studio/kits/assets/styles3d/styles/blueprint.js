/* Claude 3D Styles: Blueprint Build (reference animation: "How a suspension bridge holds up") */
(window.STYLES = window.STYLES || {})["blueprint"] = {
  name: "Blueprint Build",
  card: {
    family: "Diagrams with depth",
    look: "A real drafting sheet in deep blueprint blue with a faint grid, fold creases and a title block. Crisp white linework plots itself onto the paper, then the drawing stands up into a 3D wireframe and becomes a solid white model standing on its own plan. One warm orange is kept for forces and arrows.",
    motion: "Lines draw on stroke by stroke like a plotter, the flat drawing folds up off the paper like a pop-up, the solid model grows out of the wireframe, orange arrows travel along the structure to show how things work.",
    light: "Soft, even studio light from above-left with gentle shadows of the model on the paper; the paper stays rich blue.",
    materials: "Matte paper with grain and creases; white lines as thin flat strokes; the model is matte white card (roughness 0.8); arrows are glossy orange.",
    camera: "A three-quarter view from above (fov 28-32) that slowly orbits and lowers as the drawing becomes a model; light depth of field.",
    finish: "Neutral tone mapping, clean contrast, light vignette and fine paper grain.",
    goodFor: "How structures and machines work, engineering, architecture, product design, plans that become real, any 'from idea to object' story.",
  },
  content: { title: "How a suspension bridge holds up", steps: ["The deck hangs", "Cables carry the weight", "Towers push it down"], sheet: "SUSPENSION BRIDGE · SHEET 01 · SCALE 1:500" },
  duration: 8,
  samples: 24,
  fonts: ["IBM Plex Mono:700"],
  grade: { exposure: 1.05, tonemap: "neutral", bloom: 0.1, bloomThreshold: 1.0, saturation: 1.06, contrast: 1.06, vignette: 0.35, grain: 0.018 },

  build(S) {
    const T = S.THREE, K = S.K, C = this.content;
    S.env({ top: "#ffffff", bottom: "#24427a", intensity: 0.5 });
    S.scene.background = new T.Color("#173d86");
    S.sun({ pos: [-6, 12, 6], intensity: 2.4, soft: 1.6, size: 10 });
    S.hemi("#ffffff", "#2a4f99", 0.75);

    // the sheet: blue paper with grid, creases and a title block
    const sheet = K.canvas(2048, 2048), x = sheet.getContext("2d");
    x.fillStyle = "#1d4b9e"; x.fillRect(0, 0, 2048, 2048);
    for (let i = 0; i <= 2048; i += 32) { x.fillStyle = i % 256 === 0 ? "rgba(255,255,255,.16)" : "rgba(255,255,255,.06)"; x.fillRect(i, 0, i % 256 === 0 ? 2 : 1, 2048); x.fillRect(0, i, 2048, i % 256 === 0 ? 2 : 1); }
    const r = K.rng(5); for (let i = 0; i < 26000; i++) { x.fillStyle = `rgba(${r() > 0.5 ? "255,255,255" : "0,0,40"},${r() * 0.05})`; x.fillRect(r() * 2048, r() * 2048, 2, 2); }
    [[1024, 0, 1024, 2048], [0, 1024, 2048, 1024]].forEach(([a, b, c, d]) => { x.strokeStyle = "rgba(255,255,255,.12)"; x.lineWidth = 3; x.beginPath(); x.moveTo(a, b); x.lineTo(c, d); x.stroke(); x.strokeStyle = "rgba(0,0,30,.18)"; x.lineWidth = 2; x.beginPath(); x.moveTo(a + 3, b + 3); x.lineTo(c + 3, d + 3); x.stroke(); });
    x.strokeStyle = "rgba(255,255,255,.85)"; x.lineWidth = 4; x.strokeRect(60, 60, 1928, 1928); x.strokeRect(1240, 1760, 748, 228); x.font = "700 34px 'IBM Plex Mono'"; x.fillStyle = "rgba(255,255,255,.9)"; C.sheet.split(" · ").forEach((s, i) => x.fillText(s, 1270, 1812 + i * 56));
    const paper = S.mesh(new T.PlaneGeometry(26, 26), new T.MeshStandardMaterial({ map: K.tex(sheet), roughness: 0.92, bumpMap: S.noiseTex("pp", 256, 2, 120, 3, 1, [8, 8]), bumpScale: 0.3 }), { rot: [-Math.PI / 2, 0, 0], shadow: false }); paper.receiveShadow = true;
    S.mesh(new T.PlaneGeometry(200, 200), S.mat.matte("#11306b"), { rot: [-Math.PI / 2, 0, 0], pos: [0, -0.02, 0], shadow: false });

    // bridge geometry (x along the bridge, y up)
    const deckY = 1.2, towerX = 3.2, towerTop = 5.0, sagY = 1.65, anchorX = 7.0;
    const cableY = (xx) => { const ax = Math.abs(xx); if (ax <= towerX) return sagY + (towerTop - sagY) * (xx / towerX) ** 2; const u = (ax - towerX) / (anchorX - towerX); return towerTop + (0.45 - towerTop) * (u * (2 - u) * 0 + u) - Math.sin(u * Math.PI) * 0.35; };
    // white strokes: thin flat boxes that draw on from a to b
    const white = S.mat.basic("#ffffff"); white.color.setScalar(1.15);
    const strokes = [];
    const drawing = S.group(S.scene);
    const stroke = (a, b, w, t0, t1) => { const m = S.mesh(new T.BoxGeometry(1, w, 0.01), white, { parent: drawing, shadow: false }); strokes.push({ m, a: new T.Vector3(...a), b: new T.Vector3(...b), t0, t1 }); return m; };
    const poly = (pts, w, t0, t1) => { for (let i = 0; i < pts.length - 1; i++) stroke(pts[i], pts[i + 1], w, K.lerp(t0, t1, i / (pts.length - 1)), K.lerp(t0, t1, (i + 1) / (pts.length - 1))); };
    // deck, towers, cable, hangers, ground line, dimension line
    poly([[-anchorX - 0.6, 0, 0], [anchorX + 0.6, 0, 0]], 0.025, 0.1, 0.6);
    poly([[-anchorX, deckY, 0], [anchorX, deckY, 0]], 0.06, 0.3, 0.9); poly([[-anchorX, deckY - 0.28, 0], [anchorX, deckY - 0.28, 0]], 0.035, 0.4, 1.0);
    [-towerX, towerX].forEach((tx, i) => { poly([[tx - 0.25, 0, 0], [tx - 0.18, towerTop + 0.3, 0]], 0.06, 0.6 + i * 0.15, 1.0 + i * 0.15); poly([[tx + 0.25, 0, 0], [tx + 0.18, towerTop + 0.3, 0]], 0.06, 0.65 + i * 0.15, 1.05 + i * 0.15); poly([[tx - 0.2, towerTop - 0.4, 0], [tx + 0.2, towerTop - 0.4, 0]], 0.04, 1.05, 1.15); poly([[tx - 0.22, 2.6, 0], [tx + 0.22, 2.6, 0]], 0.04, 1.1, 1.2); });
    const cablePts = []; for (let i = 0; i <= 56; i++) { const xx = -anchorX + (i / 56) * anchorX * 2; cablePts.push([xx, cableY(xx), 0]); }
    poly(cablePts, 0.05, 1.1, 1.9);
    for (let xx = -towerX + 0.4; xx < towerX - 0.2; xx += 0.4) stroke([xx, cableY(xx), 0], [xx, deckY, 0], 0.022, 1.7 + (xx + towerX) * 0.06, 1.9 + (xx + towerX) * 0.06);
    // dimension line with ticks
    poly([[-towerX, -0.7, 0], [towerX, -0.7, 0]], 0.02, 2.0, 2.3); [-towerX, towerX].forEach((tx) => stroke([tx, -0.5, 0], [tx, -0.9, 0], 0.02, 2.0, 2.1));
    const dim = S.label("MAIN SPAN", { h: 0.32, font: "700 100px 'IBM Plex Mono'", color: "#ffffff", pad: 10, lit: false, parent: drawing }); dim.position.set(0, -1.05, 0.01);

    // the solid white model (grows out of the drawing)
    const model = S.group(S.scene);
    const card = S.mat.std("#f3f6fb", { roughness: 0.82 });
    S.mesh(K.rbox(anchorX * 2, 0.3, 1.6, 0.05), card, { pos: [0, deckY - 0.14, 0], parent: model });
    [-towerX, towerX].forEach((tx) => { [-0.62, 0.62].forEach((z) => S.mesh(K.rbox(0.36, towerTop + 0.3, 0.32, 0.05), card, { pos: [tx, (towerTop + 0.3) / 2, z], parent: model })); S.mesh(K.rbox(0.3, 0.3, 1.5, 0.05), card, { pos: [tx, towerTop - 0.4, 0], parent: model }); S.mesh(K.rbox(0.3, 0.25, 1.5, 0.05), card, { pos: [tx, 2.6, 0], parent: model }); });
    [-anchorX, anchorX].forEach((ax) => S.mesh(K.rbox(1.0, 0.8, 1.8, 0.08), card, { pos: [ax + Math.sign(ax) * 0.2, 0.4, 0], parent: model }));
    const cv = new T.CatmullRomCurve3(cablePts.map((p) => new T.Vector3(p[0], p[1], 0)));
    [-0.62, 0.62].forEach((z) => { const m = S.mesh(new T.TubeGeometry(cv, 160, 0.06, 10), card, { pos: [0, 0, z], parent: model }); });
    for (let xx = -towerX + 0.4; xx < towerX - 0.2; xx += 0.4) [-0.62, 0.62].forEach((z) => { const h = cableY(xx) - deckY; S.mesh(new T.CylinderGeometry(0.018, 0.018, h, 6), card, { pos: [xx, deckY + h / 2, z], parent: model }); });

    // orange force arrows
    const orange = S.mat.gloss("#ff8a1f", { emissive: "#ff6a00", emissiveIntensity: 0.35 });
    const arrow = () => { const g = S.group(S.scene); S.mesh(new T.ConeGeometry(0.16, 0.34, 18), orange, { pos: [0, 0.17, 0], parent: g }); S.mesh(new T.CylinderGeometry(0.05, 0.05, 0.4, 10), orange, { pos: [0, -0.2, 0], parent: g }); return g; };
    const upA = []; for (let i = 0; i < 6; i++) upA.push({ g: arrow(), xx: -2.4 + i * 0.95 });
    const alongA = []; for (let i = 0; i < 6; i++) alongA.push({ g: arrow(), side: i % 2 ? 1 : -1, d: (i >> 1) * 0.33 });
    const downA = []; for (let i = 0; i < 4; i++) downA.push({ g: arrow(), tx: i % 2 ? towerX : -towerX, d: (i >> 1) * 0.5 });
    const ripples = [-towerX, towerX].map((tx) => S.mesh(new T.RingGeometry(0.5, 0.7, 48), S.mat.basic("#ff8a1f", { transparent: true }), { rot: [-Math.PI / 2, 0, 0], pos: [tx, 0.02, 0], shadow: false }));

    // plotted captions (white single-weight caps on a dark-blue tab)
    const cap = (n, word, t0, t1) => { const l = S.label(`${n} · ${word.toUpperCase()}`, { h: 1, font: "700 100px 'IBM Plex Mono'", color: "#ffffff", bg: "#0f2f6e", border: "#ffffff", borderW: 5, radius: 8, pad: 40, lit: false }); l.userData = { t0, t1, size: l.userData.size }; return l; };
    const caps = [cap(1, C.steps[0], 0.5, 2.7), cap(2, C.steps[1], 2.8, 5.1), cap(3, C.steps[2], 5.3, 9)];

    const tmp = new T.Vector3();
    return (t) => {
      // strokes draw on
      for (const s of strokes) { const k = K.prog(t, s.t0, s.t1); s.m.visible = k > 0.001; const b = tmp.copy(s.a).lerp(s.b, k), len = s.a.distanceTo(b); s.m.position.copy(s.a).add(b).multiplyScalar(0.5); s.m.scale.set(Math.max(len, 0.001), 1, 1); s.m.rotation.z = Math.atan2(s.b.y - s.a.y, s.b.x - s.a.x); }
      dim.material.opacity = K.prog(t, 2.2, 2.5);
      // the drawing lies on the paper, then folds up to stand
      const up = K.tw(t, 2.5, 3.7, K.ease.inOut); drawing.rotation.x = -Math.PI / 2 * (1 - up); drawing.position.set(0, 0.015 * (1 - up), -0.8 * up);
      // solid model grows out of the standing drawing (depth from 0 to full), drawing fades
      const solid = K.tw(t, 3.6, 4.6, K.ease.out); model.visible = solid > 0.001; model.scale.set(1, 1, Math.max(0.001, solid)); model.position.y = 0;
      white.opacity = 1 - K.tw(t, 4.4, 5.0); white.transparent = true; dim.visible = t < 5;
      // arrows: weight goes up the hangers, along the cables to the towers, down into the ground
      upA.forEach((a, i) => { const k = K.prog(t, 4.0 + i * 0.05, 5.0 + i * 0.05); a.g.visible = k > 0 && k < 1; a.g.position.set(a.xx, K.lerp(deckY + 0.3, cableY(a.xx) - 0.2, K.ease.inOut(k)), 0.8); a.g.rotation.set(0, 0, 0); a.g.scale.setScalar(Math.sin(k * Math.PI) * 1.9 + 0.001); });
      alongA.forEach((a, i) => { const k = K.prog(t, 4.6 + a.d, 5.6 + a.d); a.g.visible = k > 0 && k < 1; const xx = a.side * K.lerp(0.4, towerX - 0.3, K.ease.inOut(k)), yy = cableY(xx) + 0.25; a.g.position.set(xx, yy, 0.8); const sl = (cableY(xx + 0.01 * a.side) - cableY(xx)) / 0.01; a.g.rotation.set(0, 0, -a.side * Math.PI / 2 + Math.atan(sl) * a.side * a.side); a.g.scale.setScalar(Math.sin(k * Math.PI) * 1.9 + 0.001); });
      downA.forEach((a, i) => { const k = K.prog(t, 5.4 + a.d, 6.4 + a.d); a.g.visible = k > 0 && k < 1; a.g.position.set(a.tx + 0.55, K.lerp(towerTop, 0.5, K.ease.in(k)), 0.8); a.g.rotation.set(0, 0, Math.PI); a.g.scale.setScalar(Math.sin(k * Math.PI) * 2.0 + 0.001); });
      ripples.forEach((m, i) => { const k = ((t - 6.2) * 0.8) % 1; m.visible = t > 6.2; m.scale.setScalar(0.5 + k * 3); m.material.opacity = (1 - k) * 0.9; });
      // camera: top-down-ish over the plan, then lowers and orbits as it stands up
      const k = K.tw(t, 1.8, 5.2, K.ease.inOut), d = S.portrait ? 31 : 21;
      const az = K.lerp(S.portrait ? 0.95 : 0.35, S.portrait ? 0.62 : 0.55, k) + Math.sin(t * 0.25) * 0.04, el = K.lerp(1.12, 0.42, k);
      const tgt = [0, K.lerp(-0.6, 2.9, k), 0];
      const cp = [Math.sin(az) * Math.cos(el) * d, Math.sin(el) * d + tgt[1], Math.cos(az) * Math.cos(el) * d];
      S.cam(cp, tgt, { fov: S.portrait ? 32 : 30, aperture: 0.07 });
      // captions pinned in the upper part of the frame (at the focus distance, so they stay sharp)
      caps.forEach((l) => { const a = K.ease.back(K.prog(t, l.userData.t0, l.userData.t0 + 0.4)), b = K.tw(t, l.userData.t1 - 0.25, l.userData.t1, K.ease.in); S.pin(l, 0, S.portrait ? 0.66 : 0.78, S.portrait ? 0.84 : 0.5, l.userData.size[0], a * (1 - b)); });
    };
  },

  sound(k) {
    k.bed("room", 0, 8, { vol: 0.8 });
    k.chords(0, 8, ["D4 F4 A4", "Bb3 D4 F4", "C4 E4 G4", "A3 C#4 E4"], { bpm: 120, vol: 0.45, arp: true, arpVol: 0.2 });
    k.bed("motor", 0.1, 2.4, { vol: 0.35, pitch: 3.2 }); for (let i = 0; i < 22; i++) k.at(0.12 + i * 0.1, "tick", { vol: 0.12, pitch: 0.6 + (i % 3) * 0.1 });
    k.at(2.5, "paper", { dur: 0.8, vol: 0.7 }); k.at(3.2, "thud", { vol: 0.5, pitch: 1.5 }); k.at(3.6, "rise", { dur: 1.0, vol: 0.2 }); k.at(4.4, "wood", { vol: 0.6 });
    for (let i = 0; i < 6; i++) k.at(4.0 + i * 0.05 + 0.4, "pop", { vol: 0.15, pitch: 1.6 }); for (let i = 0; i < 3; i++) k.at(4.6 + i * 0.33, "swish", { vol: 0.3 });
    k.at(5.4, "whoosh", { dur: 0.9, vol: 0.4, down: true }); k.at(6.2, "boom", { vol: 0.55 }); k.at(6.25, "thud", { vol: 0.6 }); k.at(6.9, "chime", { f: "D6", vol: 0.35 });
  },
};
