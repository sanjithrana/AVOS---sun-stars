/* Claude 3D Styles: Paper Layers (reference animation: "How a rainbow forms") */
(window.STYLES = window.STYLES || {})["paper-layers"] = {
  name: "Paper Layers",
  card: {
    family: "Handmade materials",
    look: "A cut-paper shadow box: flat sheets of thick coloured card cut into hills, clouds, a sun and arcs, standing in layers one behind the other so each throws a soft shadow on the next. Bright, clean colours with visible paper fibre.",
    motion: "Pieces slide in from the sides or rise from behind the hills like a theatre set, with a soft spring at the end of each move; small pieces sway on invisible threads. Diagrams are made of paper strips that grow out of each other.",
    light: "One soft key light from the upper left at a low angle so every layer casts a clear soft shadow on the layer behind, plus a gentle front fill.",
    materials: "Matte card (roughness 0.95) with a fine fibre bump, a slightly lighter cut edge, no gloss anywhere.",
    camera: "Straight-on, long lens (fov 25-30) with a slow drift that shows the parallax between layers; shallow depth of field on the middle layers.",
    finish: "Neutral tone mapping, gentle vignette, fine grain. Bright and cheerful.",
    goodFor: "Light, colour, nature, stories for kids, simple science, seasons, anything that reads best as a picture-book page.",
  },
  content: { title: "How a rainbow forms", steps: ["Sunlight", "Raindrops split it", "A rainbow!"] },
  duration: 8,
  samples: 24,
  fonts: ["Nunito:900"],
  grade: { exposure: 1.06, tonemap: "neutral", bloom: 0.06, saturation: 1.1, contrast: 1.04, vignette: 0.35, grain: 0.014 },

  build(S) {
    const T = S.THREE, K = S.K, C = this.content;
    const fibre = S.noiseTex("fibre", 256, 21, 70, 4, 1.4, [3, 3]);
    const card = (c) => new T.MeshStandardMaterial({ color: c, roughness: 0.95, bumpMap: fibre, bumpScale: 0.5 });
    const layer = (shape, c, z, o = {}) => { const g = new T.ExtrudeGeometry(shape, { depth: 0.05, bevelEnabled: false, curveSegments: 48 }); const m = S.mesh(g, card(c), { pos: [o.x || 0, o.y || 0, z], parent: o.parent }); return m; };
    S.scene.background = new T.Color("#9fd9ff");
    S.sun({ pos: [-7, 9, 14], target: [0, 0, 0], intensity: 3.0, soft: 1.4, size: 13, map: 4096, bias: -0.0002, normalBias: 0.01 });
    S.hemi("#ffffff", "#cfd8e8", 0.9);
    S.env({ intensity: 0.3 });

    // shapes
    const circle = (r) => { const s = new T.Shape(); s.absarc(0, 0, r, 0, Math.PI * 2, false); return s; };
    const hill = (y, amp, f, ph, w = 40, bottom = -14) => { const s = new T.Shape(); s.moveTo(-w / 2, bottom); for (let i = 0; i <= 80; i++) { const x = -w / 2 + (i / 80) * w; s.lineTo(x, y + Math.sin(x * f + ph) * amp + Math.sin(x * f * 2.3 + ph * 2) * amp * 0.3); } s.lineTo(w / 2, bottom); return s; };
    const arc = (R, r) => { const s = new T.Shape(); s.absarc(0, 0, R, 0, Math.PI, false); s.lineTo(-r, 0); s.absarc(0, 0, r, Math.PI, 0, true); s.lineTo(R, 0); return s; };
    const drop = (h) => { const s = new T.Shape(), w = h * 0.36; s.moveTo(0, h / 2); s.bezierCurveTo(w * 0.2, h * 0.25, w, 0, w, -h * 0.18); s.bezierCurveTo(w, -h * 0.42, w * 0.5, -h / 2, 0, -h / 2); s.bezierCurveTo(-w * 0.5, -h / 2, -w, -h * 0.42, -w, -h * 0.18); s.bezierCurveTo(-w, 0, -w * 0.2, h * 0.25, 0, h / 2); return s; };
    const strip = (len, w) => { const s = new T.Shape(); s.moveTo(0, -w / 2); s.lineTo(len, -w / 2); s.lineTo(len, w / 2); s.lineTo(0, w / 2); return s; };

    // back layers: sky bands, far hills
    layer(hill(6.5, 0.4, 0.3, 0.5, 40, -14), "#b7e4ff", -1.6);
    layer(hill(-2.4, 0.7, 0.35, 1.2), "#a8dca0", -0.9);
    // the rainbow arcs (rise from behind the hills)
    const RB = ["#ff5a5a", "#ff9f43", "#ffd93d", "#5fd068", "#4aa8ff", "#8a6dff"];
    const arcs = RB.map((c, i) => layer(arc(5.2 - i * 0.42, 4.78 - i * 0.42), c, -0.75 + i * 0.012, { y: -2.2 }));
    // near hills
    layer(hill(-3.3, 0.6, 0.45, 2.7), "#7cc874", -0.45);
    layer(hill(-4.4, 0.5, 0.5, 0.2), "#5cb860", -0.2);
    layer(hill(-5.6, 0.45, 0.62, 4.0), "#46a24f", 0.05);
    // little paper trees on the near hill
    const treeS = (() => { const s = new T.Shape(); s.moveTo(0, 1.1); s.lineTo(0.5, 0); s.lineTo(0.15, 0); s.lineTo(0.15, -0.35); s.lineTo(-0.15, -0.35); s.lineTo(-0.15, 0); s.lineTo(-0.5, 0); s.lineTo(0, 1.1); return s; })();
    [[-3.6, -4.1, 0.9], [-2.8, -4.4, 0.7], [3.2, -4.5, 0.85], [4.0, -4.1, 0.65]].forEach(([x, y, sc]) => { const m = layer(treeS, "#2f8a45", 0.12, { x, y }); m.scale.setScalar(sc); });

    // paper flowers along the front
    const petalS = circle(0.16);
    for (let i = 0; i < 14; i++) { const x = -4.8 + i * 0.74 + Math.sin(i * 7) * 0.2, y = -7.6 - Math.abs(Math.sin(i * 3.1)) * 0.9, g = S.group(S.scene, [x, y, 0.45]); layer(strip(0.9, 0.06), "#2e8a3e", -0.02, { parent: g, x: -0.03 }).rotation.z = -Math.PI / 2; const fc = ["#ff6fa5", "#ffd23f", "#ffffff", "#ff8a3d"][i % 4]; for (let k = 0; k < 5; k++) { const a = (k / 5) * Math.PI * 2; layer(petalS, fc, 0, { parent: g, x: Math.cos(a) * 0.17, y: Math.sin(a) * 0.17 }); } layer(circle(0.1), "#ffb52e", 0.03, { parent: g }); }
    layer(hill(-8.4, 0.35, 0.7, 1.0), "#3a9645", 0.3);

    // the sun with rays
    const sun = S.group(S.scene, [-3.0, 5.3, -0.3]);
    layer(circle(1.15), "#ffd23f", 0.05, { parent: sun });
    const rays = S.group(sun, [0, 0, 0]);
    for (let i = 0; i < 12; i++) { const s = new T.Shape(), a = (i / 12) * Math.PI * 2; s.moveTo(Math.cos(a - 0.12) * 1.25, Math.sin(a - 0.12) * 1.25); s.lineTo(Math.cos(a) * 1.85, Math.sin(a) * 1.85); s.lineTo(Math.cos(a + 0.12) * 1.25, Math.sin(a + 0.12) * 1.25); layer(s, "#ffb52e", -0.06, { parent: rays }); }

    // rain cloud + falling drops
    const cloud = S.group(S.scene, [3.0, 5.6, 0.35]);
    [[-1.0, 0, 0.75], [0, 0.35, 0.95], [1.0, 0, 0.75], [1.7, -0.25, 0.5], [-1.7, -0.25, 0.5]].forEach(([x, y, r]) => layer(circle(r), "#e9f0f8", 0, { x, y, parent: cloud }));
    layer((() => { const s = new T.Shape(); s.moveTo(-2.2, -0.75); s.lineTo(2.2, -0.75); s.lineTo(2.2, -0.2); s.lineTo(-2.2, -0.2); return s; })(), "#e9f0f8", 0, { parent: cloud });
    const rain = []; for (let i = 0; i < 10; i++) { const m = layer(drop(0.36), "#5ab4ff", 0.2); rain.push({ m, x: 1.2 + (i % 5) * 0.75, d: i * 0.37 }); }

    // the explainer: one big raindrop splits a white beam into colours
    const big = S.group(S.scene, [0.3, 0.9, 0.6]);
    const bigDrop = layer(drop(2.6), "#8fd1ff", 0, { parent: big });
    layer(drop(2.0), "#b9e3ff", 0.06, { parent: big, y: 0.1 });
    const beam = S.group(S.scene, [-2.6, 4.4, 0.5]); beam.rotation.z = -0.9;
    const beamStrip = layer(strip(3.9, 0.36), "#ffffff", 0, { parent: beam });
    const fan = RB.map((c, i) => { const g = S.group(S.scene, [0.95, 0.4, 0.55 - i * 0.01]); g.rotation.z = -0.32 - i * 0.11; const m = layer(strip(4.8, 0.3), c, 0, { parent: g }); return g; });

    // paper birds
    const birdS = (() => { const s = new T.Shape(); s.moveTo(-0.5, 0.15); s.quadraticCurveTo(-0.25, 0.3, 0, 0); s.quadraticCurveTo(0.25, 0.3, 0.5, 0.15); s.quadraticCurveTo(0.25, 0.12, 0, -0.08); s.quadraticCurveTo(-0.25, 0.12, -0.5, 0.15); return s; })();
    const birds = [0, 1, 2].map((i) => layer(birdS, "#2a3550", 0.4 + i * 0.05));

    // paper tags with the words
    const tag = (n, word, y, t0, t1) => { const l = S.label(`${n}  ${word}`, { h: 1.3, font: "900 120px Nunito", color: "#253050", bg: "#fffdf6", radius: 18, pad: 46, castShadow: true }); l.position.set(0, y, 0.9); l.userData = { t0, t1, y }; l.material.bumpMap = fibre; return l; };
    const tags = [tag(1, C.steps[0], -6.0, 0.5, 2.5), tag(2, C.steps[1], -6.0, 2.75, 5.0), tag(3, C.steps[2], -6.0, 5.4, 9)];

    return (t) => {
      // sun slides in, rays turn
      const sIn = K.ease.spring(K.prog(t, 0.0, 1.0)); sun.position.x = K.lerp(-8, -3.0, sIn); rays.rotation.z = -t * 0.35;
      // cloud and rain
      const cIn = K.ease.spring(K.prog(t, 2.2, 3.2)); cloud.position.x = K.lerp(9, 3.0, cIn); cloud.rotation.z = Math.sin(t * 1.3) * 0.02;
      rain.forEach((r) => { const ph = ((t * 0.9 + r.d) % 1), on = t > 2.6 && t < 7.2; r.m.visible = on; r.m.position.set(cloud.position.x - 3.0 + r.x - 1.5, 4.6 - ph * 6.5, 0.2); });
      // big drop, white beam, colour fan
      const dIn = K.ease.spring(K.prog(t, 2.8, 3.6)), dOut = K.tw(t, 5.0, 5.5, K.ease.in);
      big.scale.setScalar(Math.max(0.001, dIn * (1 - dOut)) * 1.45);
      beam.scale.set(Math.max(0.001, K.tw(t, 3.3, 3.9, K.ease.out) * (1 - dOut)), 1, 1);
      fan.forEach((g, i) => g.scale.set(Math.max(0.001, K.tw(t, 3.9 + i * 0.08, 4.6 + i * 0.08, K.ease.out) * (1 - dOut)), 1, 1));
      // rainbow rises
      arcs.forEach((m, i) => { const k = K.ease.spring(K.prog(t, 5.25 + i * 0.12, 6.25 + i * 0.12)); m.position.y = K.lerp(-8.5, -2.2, k); });
      // birds glide across at the end
      birds.forEach((b, i) => { const k = K.prog(t, 5.8 + i * 0.25, 8.3); b.position.set(K.lerp(-6.5, 5.5, k) + i * 0.6, 3.0 + i * 0.5 + Math.sin(t * 4 + i) * 0.12, 0.4 + i * 0.05); b.scale.set(0.8, 0.8 * (0.6 + 0.4 * Math.abs(Math.sin(t * 9 + i))), 1); });
      // tags drop in on a thread and swing
      tags.forEach((l) => { const a = K.ease.spring(K.prog(t, l.userData.t0, l.userData.t0 + 0.8)), b = K.tw(t, l.userData.t1 - 0.3, l.userData.t1, K.ease.in); l.position.y = l.userData.y - (1 - a) * 4 - b * 4; l.rotation.z = Math.sin(t * 2.2) * 0.04 * a; l.visible = a > 0.001 && b < 0.999; });
      // camera: straight on, slow drift for parallax
      const d = S.portrait ? S.fitDist(10.6, 18.4, 28) : S.fitDist(19, 10.8, 28);
      const dx = Math.sin(t * 0.35) * 0.9 - 0.4, dy = K.lerp(0.4, -0.2, K.tw(t, 0, 8, K.ease.sine));
      S.cam([dx, dy, d * K.lerp(1.04, 0.98, K.tw(t, 0, 8, K.ease.sine))], [0, S.portrait ? -0.6 : -0.2, 0], { fov: 28, aperture: 0.12, focus: d });
    };
  },

  sound(k) {
    k.bed("room", 0, 8, { vol: 0.8 }); k.bed("rain", 2.6, 7.2, { vol: 0.6 });
    k.chords(0, 8, ["G4 B4 D5", "E4 G4 B4", "C4 E4 G4", "D4 F#4 A4"], { bpm: 120, vol: 0.5, arp: true, arpVol: 0.22 });
    k.at(0.05, "paper", { dur: 0.6, vol: 0.7 }); k.at(0.5, "paper", { dur: 0.3, vol: 0.5 }); k.at(0.6, "chime", { f: "G5", vol: 0.35 });
    k.at(2.2, "paper", { dur: 0.7, vol: 0.6 }); k.at(2.75, "paper", { dur: 0.3, vol: 0.5 });
    k.at(2.85, "bubble", { vol: 0.45 }); k.at(3.3, "swish", { vol: 0.4 }); for (let i = 0; i < 6; i++) k.at(3.9 + i * 0.08, "ping", { f: ["C6", "D6", "E6", "G6", "A6", "C7"][i], vol: 0.22 });
    k.at(5.0, "paper", { dur: 0.3, vol: 0.4 }); for (let i = 0; i < 6; i++) k.at(5.3 + i * 0.12, "paper", { dur: 0.18, vol: 0.4 }); k.at(5.4, "rise", { dur: 0.8, vol: 0.18 }); k.at(6.3, "sparkle", { vol: 0.45 });
    k.at(5.9, "whoosh", { dur: 1.2, vol: 0.25 });
  },
};
