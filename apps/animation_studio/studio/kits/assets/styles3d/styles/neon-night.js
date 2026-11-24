/* Claude 3D Styles: Neon Night (reference animation: "How Wi-Fi reaches your phone") */
(window.STYLES = window.STYLES || {})["neon-night"] = {
  name: "Neon Night",
  card: {
    family: "Light and glass",
    look: "A retro-future night world: a glowing grid floor running to the horizon, a striped sunset sun, wireframe mountains, and objects drawn as dark solids outlined in bright neon tubes of cyan, magenta and violet. Words are glowing neon type.",
    motion: "The grid scrolls toward the camera, signals pulse outward as glowing rings, small light packets race along paths, outlines flicker on when an object appears. The camera glides low over the grid and flies toward the payoff.",
    light: "Almost no ordinary light: the neon itself is the light. A dim violet fill keeps the dark solids readable, strong bloom makes every line glow.",
    materials: "Glossy dark plastic bodies (roughness 0.35), emissive lines and tubes, an emissive canvas screen.",
    camera: "Low and wide (fov 40-50), one continuous forward glide with a slight roll on turns, little depth of field.",
    finish: "Dark purple-black base, saturated neon, strong bloom, a little grain and vignette.",
    goodFor: "Tech, the internet, signals, gaming, hacking and security, future ideas, music, nightlife, anything that should feel electric.",
  },
  content: { title: "How Wi-Fi reaches your phone", steps: ["Router sends waves", "Data rides them", "Phone decodes it"] },
  duration: 8,
  samples: 20,
  fonts: ["Orbitron:800"],
  grade: { exposure: 1.0, tonemap: "aces", bloom: 0.7, bloomThreshold: 0.95, saturation: 1.15, contrast: 1.08, vignette: 0.45, grain: 0.018 },
  shutter: 0.6,

  build(S) {
    const T = S.THREE, K = S.K, C = this.content;
    const neon = (c, p = 3) => S.mat.glow(c, p);
    const dark = (o = {}) => S.mat.phys("#14102a", { roughness: 0.35, clearcoat: 1, clearcoatRoughness: 0.2, ...o });
    S.gradientBg("#2a0b4a", "#05030f", { mid: "#12082e", power: 1.2 });
    S.scene.fog = new T.Fog("#0a0618", 18, 70);
    S.hemi("#5a3cff", "#1a0830", 0.5);
    S.env({ top: "#3a1a7a", bottom: "#05030f", boxes: [{ pos: [0, 4, -10], size: [10, 2], color: "#ff3cac", power: 4 }, { pos: [-6, 2, 4], size: [2, 4], color: "#2ef2ff", power: 3 }], intensity: 0.8 });

    // grid floor (lines) on a dark mirror-ish plane
    S.mesh(new T.PlaneGeometry(200, 200), S.mat.phys("#07040f", { roughness: 0.3, metalness: 0.2 }), { rot: [-Math.PI / 2, 0, 0], pos: [0, -0.01, 0], shadow: false });
    const grid = S.group(S.scene);
    const gl = []; for (let i = -40; i <= 40; i++) { gl.push(i, 0, -120, i, 0, 20); } for (let j = -120; j <= 20; j++) gl.push(-40, 0, j, 40, 0, j);
    const gg = new T.BufferGeometry(); gg.setAttribute("position", new T.Float32BufferAttribute(gl, 3));
    grid.add(new T.LineSegments(gg, new T.LineBasicMaterial({ color: new T.Color("#ff2fd0").multiplyScalar(2.2), fog: true })));
    // sunset sun with stripes
    const sunTex = K.tex((() => { const c = K.canvas(512, 512), x = c.getContext("2d"), g = x.createLinearGradient(0, 0, 0, 512); g.addColorStop(0, "#ffe25a"); g.addColorStop(0.55, "#ff7a3d"); g.addColorStop(1, "#ff2fa0"); x.fillStyle = g; x.beginPath(); x.arc(256, 256, 250, 0, 7); x.fill(); x.globalCompositeOperation = "destination-out"; for (let i = 0; i < 7; i++) { const y = 300 + i * 30, h = 4 + i * 3.2; x.fillRect(0, y, 512, h); } return c; })());
    const sun = S.mesh(new T.PlaneGeometry(26, 26), new T.MeshBasicMaterial({ map: sunTex, transparent: true, fog: false, color: new T.Color(1.6, 1.6, 1.6) }), { pos: [0, 7, -90], shadow: false });
    // wireframe mountains
    const mtn = (x, z, w, h, c) => { const g = new T.ConeGeometry(w, h, 4, 3); const m = new T.LineSegments(new T.WireframeGeometry(g), new T.LineBasicMaterial({ color: new T.Color(c).multiplyScalar(1.4) })); m.position.set(x, h / 2, z); S.scene.add(m); const f = S.mesh(g, S.mat.basic("#0a0518"), { pos: [x, h / 2 - 0.02, z], shadow: false }); f.scale.setScalar(0.99); };
    [[-30, -70, 12, 14, "#7a3cff"], [-14, -80, 9, 10, "#5a2cff"], [22, -72, 13, 16, "#7a3cff"], [36, -60, 8, 9, "#2ef2ff"], [6, -95, 10, 8, "#5a2cff"]].forEach((a) => mtn(...a));

    // outlined objects: dark body + neon edges
    const outlined = (geo, c, parent, p = 3) => { const g = S.group(parent); S.mesh(geo, dark(), { parent: g }); const e = new T.LineSegments(new T.EdgesGeometry(geo, 25), new T.LineBasicMaterial({ color: new T.Color(c).multiplyScalar(p) })); g.add(e); g.userData.edge = e; return g; };
    // the router
    const router = S.group(S.scene, [0, 0, 6]);
    const rb = outlined(K.rbox(2.6, 0.55, 1.6, 0.08, 2), "#2ef2ff", router); rb.position.y = 0.4;
    const ants = [-0.9, 0.9].map((x) => { const a = S.mesh(new T.CylinderGeometry(0.05, 0.05, 1.5, 12), neon("#2ef2ff", 2.5), { pos: [x, 1.35, -0.55], parent: router, shadow: false }); return a; });
    const leds = [0, 1, 2, 3].map((i) => S.mesh(new T.SphereGeometry(0.06, 12, 8), neon(["#2ef2ff", "#ff2fd0", "#9b5cff", "#2ef2ff"][i], 4), { pos: [-0.6 + i * 0.4, 0.4, 0.81], parent: router, shadow: false }));
    // wifi wave arcs
    const waves = []; for (let i = 0; i < 6; i++) { const m = S.mesh(new T.TorusGeometry(1, 0.06, 10, 64, Math.PI * 0.7), neon(i % 2 ? "#ff2fd0" : "#2ef2ff", 3.4), { shadow: false }); m.material.transparent = true; waves.push(m); }
    // data packets
    const packets = []; for (let i = 0; i < 12; i++) packets.push(S.mesh(K.rbox(0.28, 0.28, 0.28, 0.06, 2), neon(i % 3 ? "#fff36b" : "#2ef2ff", 3.2), { shadow: false }));
    // the phone with a live screen
    const phone = S.group(S.scene, [0, 3.2, -14]);
    outlined(K.rbox(2.4, 4.8, 0.3, 0.32, 4), "#ff2fd0", phone, 3.2);
    const scr = K.canvas(480, 960), sx = scr.getContext("2d"), stex = K.tex(scr); stex.wrapS = stex.wrapT = T.ClampToEdgeWrapping;
    const screen = S.mesh(new T.PlaneGeometry(2.1, 4.4), new T.MeshBasicMaterial({ map: stex, toneMapped: false }), { pos: [0, 0, 0.16], parent: phone, shadow: false });
    let lastKey = "";
    const drawScreen = (bars, ok, play) => { const key = bars + "|" + ok + "|" + Math.round(play * 20); if (key === lastKey) return; lastKey = key; const x = sx; x.fillStyle = "#0b0720"; x.fillRect(0, 0, 480, 960); x.save(); x.translate(240, 330); for (let i = 0; i < 3; i++) { x.strokeStyle = i < bars ? "#2ef2ff" : "#2a2350"; x.lineWidth = 26; x.lineCap = "round"; x.beginPath(); x.arc(0, 60, 60 + i * 55, Math.PI * 1.22, Math.PI * 1.78); x.stroke(); } x.fillStyle = bars > 0 ? "#2ef2ff" : "#2a2350"; x.beginPath(); x.arc(0, 60, 18, 0, 7); x.fill(); x.restore(); x.textAlign = "center"; x.font = "800 44px Orbitron"; x.fillStyle = ok ? "#fff36b" : "#5a4f8a"; x.fillText(ok ? "CONNECTED" : "SEARCHING", 240, 520); if (play > 0) { x.fillStyle = "#ff2fd0"; x.globalAlpha = Math.min(1, play * 3); x.beginPath(); x.roundRect(60, 600, 360, 220, 24); x.fill(); x.fillStyle = "#0b0720"; x.beginPath(); x.moveTo(215, 665); x.lineTo(285, 710); x.lineTo(215, 755); x.fill(); x.fillStyle = "#2ef2ff"; x.fillRect(60, 850, 360 * play, 10); x.globalAlpha = 1; } stex.needsUpdate = true; };

    // neon captions
    const cap = (n, word, t0, t1) => { const l = S.label(`${n} ${word}`, { h: 1, font: "800 110px Orbitron", color: "#ffffff", bg: "rgba(20,8,48,0.78)", border: "#2ef2ff", borderW: 8, radius: 999, pad: 44, lit: false, power: 1.0 }); l.userData = { t0, t1, size: l.userData.size }; return l; };
    const caps = [cap(1, C.steps[0], 0.5, 2.7), cap(2, C.steps[1], 2.8, 5.1), cap(3, C.steps[2], 5.3, 9)];

    const path = (u) => new T.Vector3(0, K.lerp(1.4, 3.2, u) + Math.sin(u * Math.PI) * 1.2, K.lerp(5.6, -13.6, u));
    return (t) => {
      grid.position.z = (t * 3.2) % 1;
      // router boots: edges flicker on
      const boot = K.prog(t, 0.1, 0.7); rb.userData.edge.visible = boot > 0.9 || Math.sin(t * 90) > 0.2 - boot; leds.forEach((l, i) => (l.visible = t > 0.6 + i * 0.12));
      // waves travel from router to phone
      waves.forEach((w, i) => { const ph = (t * 0.42 + i / waves.length) % 1, on = K.prog(t, 0.8, 1.2) * (1 - K.prog(t, 5.4, 6.0)); const p = path(ph); w.position.copy(p); w.rotation.set(0, 0, Math.PI * 0.15 + Math.PI * 0.5 - 0.35 * 0); w.rotation.z = Math.PI * 0.15; w.scale.setScalar(Math.max(0.001, on * (0.8 + ph * 2.4))); w.material.opacity = 1; w.visible = on > 0 && ph < 0.96; });
      // packets ride the waves
      packets.forEach((p, i) => { const ph = (t * 0.5 + i / packets.length) % 1, on = K.prog(t, 2.8, 3.2) * (1 - K.prog(t, 6.0, 6.6)); const q = path(ph); p.position.set(q.x + Math.sin(i * 2.3) * 0.8 * Math.sin(ph * Math.PI), q.y + Math.cos(i * 1.7) * 0.5 * Math.sin(ph * Math.PI), q.z); p.rotation.set(t * 3 + i, t * 2 + i, 0); p.scale.setScalar(Math.max(0.001, on * (1 - K.prog(ph, 0.72, 0.9)))); });
      // phone screen
      const bars = t < 1.6 ? 0 : t < 2.2 ? 1 : t < 2.8 ? 2 : 3; drawScreen(bars, t > 5.3, K.prog(t, 5.6, 8));
      phone.rotation.y = Math.sin(t * 0.7) * 0.12; phone.position.y = 3.2 + Math.sin(t * 1.4) * 0.08;
      // camera glides from behind the router toward the phone
      const k = K.tw(t, 0, 8, K.ease.inOut), fly = K.tw(t, 4.8, 8, K.ease.inOut);
      const cz = K.lerp(13, 9.5, k) - fly * 10, cy = K.lerp(3.4, 4.2, k) + fly * 1.2;
      const tgt = [0, K.lerp(2.2, 2.9, k) + fly * 0.4, K.lerp(-2, -6, k) - fly * 6];
      S.cam([Math.sin(t * 0.5) * 0.5, cy, cz], tgt, { fov: S.portrait ? 50 : 40, roll: Math.sin(t * 0.5) * 0.02, aperture: 0.03 });
      // captions float just below the action, facing the camera
      caps.forEach((l) => { const a = K.ease.back(K.prog(t, l.userData.t0, l.userData.t0 + 0.4)), b = K.tw(t, l.userData.t1 - 0.25, l.userData.t1, K.ease.in); const flick = a > 0.99 ? 1 : (Math.sin(t * 80) > 0 ? 1 : 0.4); l.material.opacity = flick; l.material.transparent = true; S.pin(l, 0, S.portrait ? -0.56 : -0.62, S.portrait ? 0.86 : 0.46, l.userData.size[0], a * (1 - b)); });
    };
  },

  sound(k) {
    k.bed("hum", 0, 8, { vol: 1.2 }); k.bed("neon", 0.2, 8, { vol: 0.8 });
    k.chords(0, 8, ["A3 C4 E4", "F3 A3 C4", "D3 F3 A3", "E3 G#3 B3"], { bpm: 120, vol: 0.7, wave: "sawtooth", bright: 1100 });
    for (let i = 0; i < 16; i++) k.at(i * 0.5, "tick", { vol: 0.25, pitch: 0.5 }); for (let i = 0; i < 8; i++) k.at(i, "thud", { vol: 0.35, pitch: 1.2 });
    k.at(0.1, "zap", { vol: 0.4 }); for (let i = 0; i < 4; i++) k.at(0.6 + i * 0.12, "blip", { f: ["A5", "C6", "E6", "A6"][i], vol: 0.25 });
    for (let i = 0; i < 9; i++) k.at(1.0 + i * 0.8, "whoosh", { dur: 0.5, vol: 0.18, pitch: 1.4 });
    for (let i = 0; i < 3; i++) k.at(1.6 + i * 0.6, "ping", { f: ["E6", "A6", "C#7"][i], vol: 0.3 });
    for (let i = 0; i < 14; i++) k.at(2.9 + i * 0.17, "blip", { vol: 0.12, f: 1200 + (i % 5) * 200, pan: (i % 2) - 0.5 });
    k.at(4.8, "rise", { dur: 0.6, vol: 0.3 }); k.at(5.3, "chime", { f: "A5", vol: 0.5 }); k.at(5.35, "sparkle", { vol: 0.35 }); k.at(5.6, "whoosh", { dur: 1.6, vol: 0.4 });
  },
};
