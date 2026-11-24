/* Claude 3D Styles: Toon Ink (reference animation: "How a rocket reaches orbit") */
(window.STYLES = window.STYLES || {})["toon-ink"] = {
  name: "Toon Ink",
  card: {
    family: "Drawn looks",
    look: "Real 3D that reads like a comic book: flat cel shading in three tones, a thick black ink outline around every shape, a halftone-dot sky, bold yellow caption boxes and a sound-effect burst for the big moment.",
    motion: "Punchy and snappy: anticipation before a big move, a fast action with a squash, smoke puffs that pop out in round cartoon balls, a whip move of the camera between places.",
    light: "One hard key light so the toon shading splits each form into clear light, mid and shadow bands; no soft fill.",
    materials: "MeshToonMaterial with a 3-step gradient, flat saturated colours, outlines made with a slightly bigger back-faced black copy of each shape (inverted hull).",
    camera: "Dynamic comic angles (fov 35-45): low hero angle on the action, a fast tilt-up to follow, a whip-pan to the next scene.",
    finish: "Crisp: no tone mapping on the inks, no blur except motion, light grain, halftone texture.",
    goodFor: "Action, space and science stories, history moments, kids' explainers, anything that should feel fun and energetic.",
  },
  content: { title: "How a rocket reaches orbit", steps: ["Liftoff!", "Stage 1 drops away", "Now it falls around Earth"], sfx: "WHOOSH!" },
  duration: 8,
  samples: 16,
  fonts: ["Bangers:400"],
  grade: { exposure: 1.0, tonemap: "none", bloom: 0, saturation: 1.05, contrast: 1.02, vignette: 0.15, grain: 0.02 },
  shutter: 0.55,

  build(S) {
    const T = S.THREE, K = S.K, C = this.content;
    const grad = new T.DataTexture(new Uint8Array([70, 70, 70, 255, 170, 170, 170, 255, 255, 255, 255, 255]), 3, 1, T.RGBAFormat); grad.minFilter = grad.magFilter = T.NearestFilter; grad.needsUpdate = true;
    const ink = new T.MeshBasicMaterial({ color: "#14121a", side: T.BackSide });
    const toon = (geo, color, parent, o = {}) => { const g = S.group(parent); const m = S.mesh(geo, new T.MeshToonMaterial({ color, gradientMap: grad, map: o.map || null }), { parent: g, shadow: false }); const line = new T.Mesh(geo, ink); line.scale.setScalar(o.line || 1.045); g.add(line); if (o.pos) g.position.set(...o.pos); if (o.rot) g.rotation.set(...o.rot); return g; };
    const sunL = new T.DirectionalLight("#ffffff", 3.2); sunL.position.set(-5, 8, 6); S.scene.add(sunL); S.scene.add(new T.AmbientLight("#ffffff", 0.6));

    // halftone sky backdrop (changes from day blue to space navy)
    const sky = K.canvas(1024, 2048), sx = sky.getContext("2d");
    const g = sx.createLinearGradient(0, 0, 0, 2048); g.addColorStop(0, "#0d1240"); g.addColorStop(0.45, "#2a4fd8"); g.addColorStop(0.75, "#5fb3ff"); g.addColorStop(1, "#bfe6ff"); sx.fillStyle = g; sx.fillRect(0, 0, 1024, 2048);
    for (let y = 0; y < 2048; y += 22) for (let x = (y / 22) % 2 ? 11 : 0; x < 1024; x += 22) { const r = 2 + 5 * (1 - y / 2048); sx.fillStyle = "rgba(255,255,255,0.13)"; sx.beginPath(); sx.arc(x, y, r, 0, 7); sx.fill(); }
    for (let i = 0; i < 160; i++) { const r = K.rng(i + 1); const y = r() * 700; sx.fillStyle = "#ffffff"; sx.beginPath(); sx.arc(r() * 1024, y, 1 + r() * 3, 0, 7); sx.fill(); }
    const skyM = S.mesh(new T.PlaneGeometry(120, 240), new T.MeshBasicMaterial({ map: K.tex(sky) }), { pos: [0, 70, -40], shadow: false });

    // ground + pad + tower
    toon(new T.CylinderGeometry(30, 30, 2, 48), "#7ccf6a", S.scene, { pos: [0, -1, -6], line: 1.003 });
    toon(new T.CylinderGeometry(2.2, 2.6, 0.6, 32), "#9aa3b5", S.scene, { pos: [0, 0.3, 0] });
    const tower = S.group(S.scene, [-1.9, 0, -0.4]); toon(new T.BoxGeometry(0.5, 7.5, 0.5), "#e8453c", tower, { pos: [0, 3.75, 0] }); [1.5, 3.5, 5.5].forEach((y) => toon(new T.BoxGeometry(1.0, 0.18, 0.18), "#e8453c", tower, { pos: [0.6, y, 0] }));
    [[-6, -4, 1.2], [5.5, -6, 1.6], [7, -2, 1.0], [-8, -1, 1.4]].forEach(([x, z, s]) => { toon(new T.SphereGeometry(1.2 * s, 18, 12), "#4fae55", S.scene, { pos: [x, 0.8 * s, z] }); });

    // the rocket: stage 2 (top) + stage 1 (bottom)
    const rocket = S.group(S.scene);
    const top = S.group(rocket); toon(new T.CylinderGeometry(0.6, 0.6, 2.4, 28), "#f4f4f8", top, { pos: [0, 3.9, 0] }); toon(new T.ConeGeometry(0.6, 1.4, 28), "#e8453c", top, { pos: [0, 5.8, 0] }); toon(new T.CylinderGeometry(0.28, 0.28, 0.1, 24), "#5fb3ff", top, { pos: [0, 4.4, 0.58], rot: [Math.PI / 2, 0, 0] });
    const stage1 = S.group(rocket); toon(new T.CylinderGeometry(0.66, 0.7, 2.6, 28), "#f4f4f8", stage1, { pos: [0, 1.4, 0] }); toon(new T.CylinderGeometry(0.67, 0.67, 0.25, 28), "#2b2f3d", stage1, { pos: [0, 2.6, 0] });
    for (let i = 0; i < 4; i++) { const f = S.group(stage1); f.rotation.y = (i / 4) * Math.PI * 2; const s = new T.Shape([[0, 0], [0.8, -0.3], [0.8, -0.9], [0, -0.5]].map((p) => new T.Vector2(...p))); toon(new T.ExtrudeGeometry(s, { depth: 0.12, bevelEnabled: false }), "#e8453c", f, { pos: [0.6, 1.0, -0.06] }); }
    const flame = S.group(rocket); toon(new T.ConeGeometry(0.55, 1.8, 18), "#ff9a1f", flame, { pos: [0, -0.7, 0], rot: [Math.PI, 0, 0] }); toon(new T.ConeGeometry(0.32, 1.1, 18), "#ffe14d", flame, { pos: [0, -0.4, 0], rot: [Math.PI, 0, 0] });
    // smoke puffs
    const puffs = []; for (let i = 0; i < 16; i++) puffs.push({ g: toon(new T.SphereGeometry(0.7, 18, 12), i % 3 ? "#ffffff" : "#e3e8f2", S.scene), a: (i / 16) * Math.PI * 2, d: (i % 4) * 0.1 });

    // space set (far above): Earth, orbit, a second rocket copy
    const SP = [0, 400, 0];
    const earthTex = K.canvas(1024, 512), ex = earthTex.getContext("2d"); ex.fillStyle = "#2f7de8"; ex.fillRect(0, 0, 1024, 512); const er = K.rng(4); ex.fillStyle = "#57c35e"; for (let i = 0; i < 26; i++) { ex.beginPath(); ex.ellipse(er() * 1024, 80 + er() * 350, 40 + er() * 110, 25 + er() * 70, er() * 3, 0, 7); ex.fill(); } ex.fillStyle = "#ffffff"; ex.fillRect(0, 0, 1024, 30); ex.fillRect(0, 482, 1024, 30);
    const earth = toon(new T.SphereGeometry(4.4, 48, 32), "#ffffff", S.scene, { pos: [SP[0], SP[1] - 3, SP[2]], map: K.tex(earthTex), line: 1.02 });
    const orbitDash = []; for (let i = 0; i < 48; i++) { const a = (i / 48) * Math.PI * 2; if (i % 2) continue; const m = S.mesh(new T.BoxGeometry(0.45, 0.1, 0.1), S.mat.basic("#ffffff"), { pos: [SP[0] + Math.cos(a) * 6.6, SP[1] - 3 + Math.sin(a) * 6.6, SP[2]], rot: [0, 0, a + Math.PI / 2], shadow: false }); orbitDash.push(m); }
    const mini = S.group(S.scene); mini.scale.setScalar(1.8); toon(new T.CylinderGeometry(0.35, 0.35, 1.3, 20), "#f4f4f8", mini, { pos: [0, 0, 0] }); toon(new T.ConeGeometry(0.35, 0.8, 20), "#e8453c", mini, { pos: [0, 1.05, 0] }); const miniFlame = toon(new T.ConeGeometry(0.25, 0.7, 14), "#ffb21f", mini, { pos: [0, -0.95, 0], rot: [Math.PI, 0, 0] });
    const stars = []; const sr = K.rng(11); for (let i = 0; i < 60; i++) stars.push(S.mesh(new T.OctahedronGeometry(0.06 + sr() * 0.1, 0), S.mat.basic("#ffffff"), { pos: [SP[0] + (sr() - 0.5) * 40, SP[1] + (sr() - 0.5) * 50, SP[2] - 10 - sr() * 10], shadow: false }));
    const spaceBg = S.mesh(new T.PlaneGeometry(200, 200), S.mat.basic("#0b0f33"), { pos: [SP[0], SP[1], SP[2] - 25], shadow: false });

    // comic captions + SFX burst
    const box = (txt, t0, t1) => { const l = S.label(txt.toUpperCase(), { h: 1, font: "400 130px Bangers", color: "#14121a", bg: "#ffe14d", border: "#14121a", borderW: 12, radius: 6, pad: 44, lit: false }); l.userData = { t0, t1, size: l.userData.size }; return l; };
    const caps = [box(C.steps[0], 0.3, 2.6), box(C.steps[1], 2.8, 5.0), box(C.steps[2], 5.3, 9)];
    const burst = S.label(C.sfx, { h: 1, font: "400 170px Bangers", color: "#ffe14d", stroke: "#14121a", strokeW: 26, pad: 120, lit: false, draw: (x, w, h) => { const d = x.getImageData(0, 0, w, h); x.clearRect(0, 0, w, h); x.fillStyle = "#e8453c"; x.strokeStyle = "#14121a"; x.lineWidth = 12; x.beginPath(); for (let i = 0; i <= 28; i++) { const a = (i / 28) * Math.PI * 2, r = i % 2 ? 0.36 : 0.5; x.lineTo(w / 2 + Math.cos(a) * w * r, h / 2 + Math.sin(a) * h * r * 1.1); } x.closePath(); x.fill(); x.stroke(); const c = K.canvas(w, h); c.getContext("2d").putImageData(d, 0, 0); x.drawImage(c, 0, 0); } });
    burst.userData.base = burst.userData.size[0];

    return (t) => {
      // ignition shake, liftoff, separation
      const ign = K.prog(t, 0.4, 0.9), lift = Math.max(0, t - 1.0), y = lift * lift * 2.4;
      rocket.position.set(Math.sin(t * 60) * 0.03 * ign * (t < 1.2 ? 1 : 0.3), y, 0);
      flame.visible = t > 0.4; flame.scale.set(1, (0.6 + Math.abs(Math.sin(t * 40)) * 0.5) * K.clamp(ign * 1.4), 1);
      const sep = K.prog(t, 3.4, 5.0); stage1.position.set(sep * 1.4, -sep * sep * 9, 0); stage1.rotation.z = -sep * 1.8; top.position.y = 0; if (sep > 0) { flame.position.y = 2.6; }
      puffs.forEach((p) => { const k = K.prog(t, 0.6 + p.d, 2.4 + p.d); const r = 1 + K.ease.out(k) * 4; p.g.position.set(Math.cos(p.a) * r, 0.6 + K.ease.out(k) * (p.a % 2) * 0.8, Math.sin(p.a) * r * 0.5); p.g.scale.setScalar(Math.max(0.001, K.ease.back(K.prog(t, 0.6 + p.d, 1.0 + p.d)) * (1 + k * 0.8))); });
      // camera: low hero angle -> tilt-up chase -> whip to space
      const inSpace = t >= 5.15;
      if (!inSpace) {
        const chase = K.tw(t, 1.05, 2.6, K.ease.inOut), ry = y + 3.4;
        const tgt = [0, K.lerp(2.6, ry, chase), 0];
        const whip = K.tw(t, 4.8, 5.15, K.ease.in);
        S.cam([K.lerp(5.5, 6.5, chase), K.lerp(1.0, ry - 1.5, chase) + whip * 60, K.lerp(12, 13, chase)], [tgt[0], tgt[1] + whip * 80, tgt[2]], { fov: S.portrait ? 45 : 38 });
      } else {
        const k = K.tw(t, 5.15, 6.0, K.ease.out), a = -Math.PI / 2 - 0.3 + (t - 5.15) * 0.75;
        mini.position.set(SP[0] + Math.cos(a) * 6.6, SP[1] - 3 + Math.sin(a) * 6.6, SP[2] + 0.5); mini.rotation.z = a; miniFlame.visible = Math.sin(t * 30) > -0.6;
        const d = S.portrait ? 36 : 24;
        S.cam([SP[0] + 2, SP[1] - 3 + K.lerp(30, 2, k), SP[2] + d], [SP[0], SP[1] - 3 + K.lerp(18, 0, k), SP[2]], { fov: 40 });
      }
      earth.rotation.y = t * 0.15;
      // captions top-left like a comic panel, burst at liftoff
      caps.forEach((l, i) => { const a = K.ease.back(K.prog(t, l.userData.t0, l.userData.t0 + 0.3)), b = K.tw(t, l.userData.t1 - 0.2, l.userData.t1, K.ease.in); S.pin(l, S.portrait ? -0.1 : -0.35, S.portrait ? 0.66 : 0.74, S.portrait ? 0.66 : 0.42, l.userData.size[0], a * (1 - b)); l.rotation.z += -0.03; });
      const bk = K.ease.back(K.prog(t, 1.0, 1.25)) * (1 - K.tw(t, 2.0, 2.2)); S.pin(burst, S.portrait ? 0.25 : 0.4, S.portrait ? 0.15 : 0.1, S.portrait ? 0.62 : 0.3, burst.userData.base, bk); burst.rotation.z += 0.12;
    };
  },

  sound(k) {
    k.chords(0, 8, ["G3 B3 D4", "C4 E4 G4", "D4 F#4 A4", "G3 B3 D4"], { bpm: 120, vol: 0.45, arp: true, arpVol: 0.3, wave: "square", bright: 1600 });
    k.at(0.1, "tick", { vol: 0.4 }); k.at(0.4, "zap", { vol: 0.4 }); k.bed("motor", 0.4, 5.0, { vol: 1.4, pitch: 0.6 }); k.bed("wind", 0.5, 5.1, { vol: 1.2, pitch: 0.7 });
    k.at(0.95, "boom", { vol: 0.9 }); k.at(1.0, "whoosh", { dur: 1.4, vol: 0.6 }); for (let i = 0; i < 6; i++) k.at(0.65 + i * 0.1, "pop", { vol: 0.35, pitch: 0.6 });
    k.at(3.4, "snap", { vol: 0.7 }); k.at(3.42, "thud", { vol: 0.5, pitch: 1.4 }); k.at(3.6, "drop", { dur: 1.2, vol: 0.4 });
    k.at(4.8, "whoosh", { dur: 0.4, vol: 0.7 }); k.at(5.15, "hit", { vol: 0.4, pitch: 1.6 }); k.bed("hum", 5.2, 8, { vol: 0.6 }); k.at(5.4, "sparkle", { vol: 0.4 }); k.at(6.6, "chime", { f: "G5", vol: 0.4 });
  },
};
