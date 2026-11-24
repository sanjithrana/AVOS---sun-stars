/* Claude 3D Styles: Floating Screens (reference animation: "How a message gets delivered") */
(window.STYLES = window.STYLES || {})["floating-screens"] = {
  name: "Floating Screens",
  card: {
    family: "Products and screens",
    look: "App screens as physical objects: crisp white cards printed with a real interface, each backed by a slab of clear glass, floating one behind another in a bright, airy pastel room. The card in focus is sharp; the others fall softly out of focus.",
    motion: "Interfaces come alive (typing, buttons pressing, messages arriving, ticks turning blue). A small glossy object carries the data from card to card along a smooth arc. The camera travels from screen to screen and racks focus as it goes, then pulls back to show the whole flow.",
    light: "Big soft daylight from the upper left, a gentle bounce from below, bright reflections on the glass edges.",
    materials: "Matte white card with a printed UI (canvas texture), clear glass slabs (transmission), a glossy coloured carrier, a soft matte room.",
    camera: "fov 30-35, a smooth travel between screens with a rack focus on each, ending on a wide view; shallow depth of field.",
    finish: "Bright, clean, slightly cool; neutral tone mapping, light bloom, very light grain.",
    goodFor: "Apps and websites, how software works, user journeys, onboarding, product demos, any flow between screens or devices.",
  },
  content: { title: "How a message gets delivered", steps: ["You hit send", "A server passes it on", "Delivered"], msg: "Lunch at 1?", from: "Maya", to: "Sam" },
  duration: 8,
  samples: 24,
  fonts: ["Inter:700", "Inter:800"],
  grade: { exposure: 1.04, tonemap: "neutral", bloom: 0.1, saturation: 1.06, contrast: 1.04, vignette: 0.2, grain: 0.006 },

  build(S) {
    const T = S.THREE, K = S.K, C = this.content;
    S.env({ top: "#ffffff", bottom: "#d9dcf6", boxes: [{ pos: [-6, 6, 6], size: [6, 5], color: "#ffffff", power: 6 }, { pos: [6, 3, 2], size: [2, 6], color: "#ffffff", power: 3 }], intensity: 0.9 });
    S.scene.background = new T.Color("#b9c3ff");
    S.mesh(K.sweep(80, 40, 40, 10), S.mat.matte("#bcc6ff"), { pos: [0, -1, -9] });
    // soft colour glows on the back wall
    [[-6, 6, -8.6, "#ff9ad5", 9], [7, 3, -8.6, "#7fe0ff", 10], [0, 11, -8.6, "#c7b3ff", 12]].forEach(([x, y, z, c, r]) => { const cv = K.canvas(256, 256), q = cv.getContext("2d"), gr = q.createRadialGradient(128, 128, 0, 128, 128, 128); gr.addColorStop(0, c); gr.addColorStop(1, "rgba(255,255,255,0)"); q.fillStyle = gr; q.fillRect(0, 0, 256, 256); S.mesh(new T.PlaneGeometry(r, r), new T.MeshBasicMaterial({ map: K.tex(cv), transparent: true, opacity: 0.55, depthWrite: false }), { pos: [x, y, z], shadow: false }); });
    S.sun({ pos: [-7, 11, 9], intensity: 2.2, soft: 2.4, size: 12 });
    S.hemi("#ffffff", "#d6d9f7", 0.8);
    const blue = "#3d6bff";

    // a screen card: white printed face + glass slab behind
    const card = (w, h, pos, draw) => {
      const g = S.group(S.scene, pos); const cw = Math.round(w * 300), ch = Math.round(h * 300), c = K.canvas(cw, ch), tex = K.tex(c); tex.wrapS = tex.wrapT = T.ClampToEdgeWrapping;
      S.mesh(K.rbox(w, h, 0.05, 0.12, 4), S.mat.std("#ffffff", { roughness: 0.6 }), { parent: g });
      S.mesh(new T.PlaneGeometry(w - 0.06, h - 0.06), new T.MeshStandardMaterial({ map: tex, roughness: 0.55 }), { pos: [0, 0, 0.027], parent: g, shadow: false });
      S.mesh(K.rbox(w + 0.16, h + 0.16, 0.36, 0.16, 4), S.mat.glass("#eaf2ff", { thickness: 0.5, roughness: 0.04, attenuationColor: new T.Color("#9fc4ff"), attenuationDistance: 1.5 }), { pos: [0, 0, -0.22], parent: g }).castShadow = false;
      let last = ""; g.userData.draw = (state) => { const k = JSON.stringify(state); if (k === last) return; last = k; draw(c.getContext("2d"), cw, ch, state); tex.needsUpdate = true; };
      return g;
    };
    const rr = (x, X, Y, W, H, R, fill) => { x.fillStyle = fill; x.beginPath(); x.roundRect(X, Y, W, H, R); x.fill(); };
    const chatHeader = (x, w, name, col) => { rr(x, 0, 0, w, 150, 0, "#f6f7fb"); rr(x, 40, 35, 80, 80, 40, col); x.fillStyle = "#fff"; x.font = "800 44px Inter"; x.textAlign = "center"; x.fillText(name[0], 80, 92); x.textAlign = "left"; x.fillStyle = "#1b2033"; x.font = "800 46px Inter"; x.fillText(name, 145, 92); };
    // phone A (sender)
    const A = card(2.1, 4.2, [-2.0, 2.4, 3.2], (x, w, h, s) => {
      x.fillStyle = "#ffffff"; x.fillRect(0, 0, w, h); chatHeader(x, w, C.to, "#ff8a3d");
      rr(x, 40, 210, 380, 90, 45, "#eef0f6"); x.fillStyle = "#1b2033"; x.font = "700 40px Inter"; x.fillText("Hey! Free today?", 70, 268);
      if (s.sent) { rr(x, w - 420, 330, 380, 90, 45, blue); x.fillStyle = "#fff"; x.font = "700 40px Inter"; x.fillText(C.msg, w - 390, 388); x.fillStyle = "#8a90a6"; x.font = "700 30px Inter"; x.textAlign = "right"; x.fillText(s.ticks ? "Delivered ✓✓" : "Sent ✓", w - 50, 460); x.textAlign = "left"; }
      rr(x, 30, h - 150, w - 190, 100, 50, "#f1f2f7"); x.fillStyle = "#1b2033"; x.font = "700 40px Inter"; x.fillText(s.typed + (s.caret ? "|" : ""), 70, h - 85);
      rr(x, w - 140, h - 150, 100, 100, 50, s.press ? "#2a4fd0" : blue); x.fillStyle = "#fff"; x.beginPath(); x.moveTo(w - 112, h - 120); x.lineTo(w - 62, h - 100); x.lineTo(w - 112, h - 80); x.fill();
    });
    // server card
    const SV = card(2.6, 2.2, [0.6, 3.3, -0.4], (x, w, h, s) => {
      x.fillStyle = "#ffffff"; x.fillRect(0, 0, w, h); x.fillStyle = "#1b2033"; x.font = "800 52px Inter"; x.fillText("Server", 50, 95);
      for (let i = 0; i < 3; i++) { rr(x, 50, 140 + i * 115, w - 100, 90, 18, "#f1f3fa"); for (let j = 0; j < 3; j++) rr(x, 80 + j * 40, 172 + i * 115, 22, 22, 11, s.blink && (i + j + s.blink) % 2 ? "#3ddc84" : "#c9cee0"); x.fillStyle = "#8a90a6"; x.font = "700 30px Inter"; x.fillText(["inbox queue", "routing", "push service"][i], 230, 197 + i * 115); }
      if (s.lock) { rr(x, w - 290, 40, 240, 70, 35, "#e8fff1"); x.fillStyle = "#1a9e57"; x.font = "800 30px Inter"; x.fillText("Encrypted", w - 250, 86); }
    });
    // phone B (receiver)
    const B = card(2.1, 4.2, [2.4, 2.4, -3.8], (x, w, h, s) => {
      x.fillStyle = "#ffffff"; x.fillRect(0, 0, w, h); chatHeader(x, w, C.from, "#7a5cff");
      if (s.notif) { rr(x, 30, 180, w - 60, 130, 30, "#1b2033"); x.fillStyle = "#fff"; x.font = "800 36px Inter"; x.fillText(C.from, 70, 235); x.font = "700 34px Inter"; x.fillStyle = "#cdd2e6"; x.fillText(C.msg, 70, 285); }
      if (s.msg) { rr(x, 40, 360, 380, 90, 45, "#eef0f6"); x.fillStyle = "#1b2033"; x.font = "700 40px Inter"; x.fillText(C.msg, 70, 418); }
    });
    // the carrier: a glossy message bubble
    const bubble = S.group(S.scene);
    S.mesh(K.rbox(0.62, 0.38, 0.22, 0.17, 5), S.mat.gloss(blue, { roughness: 0.15 }), { parent: bubble });
    S.mesh(new T.ConeGeometry(0.08, 0.16, 12), S.mat.gloss(blue, { roughness: 0.15 }), { pos: [-0.2, -0.22, 0], rot: [0, 0, 2.6], parent: bubble });
    const lock = S.group(bubble, [0.3, 0.22, 0.12]); S.mesh(K.rbox(0.16, 0.13, 0.08, 0.03), S.mat.gloss("#1fc46b"), { parent: lock }); S.mesh(new T.TorusGeometry(0.05, 0.016, 8, 20, Math.PI), S.mat.metal("#e6e9f0"), { pos: [0, 0.07, 0], parent: lock });
    const path = new T.CatmullRomCurve3([new T.Vector3(-1.35, 0.9, 3.5), new T.Vector3(-0.6, 3.2, 2.2), new T.Vector3(0.6, 3.3, 0.1), new T.Vector3(1.8, 3.6, -2.0), new T.Vector3(2.2, 3.1, -3.3)]);
    const cap = (n, word, t0, t1) => { const l = S.label(`${n}  ${word}`, { h: 1, font: "800 120px Inter", color: "#1b2033", bg: "#ffffff", radius: 999, pad: 54, lit: false, draw: n === 3 ? (x, w, h) => { x.fillStyle = blue; x.font = "800 110px Inter"; x.textAlign = "right"; x.fillText("✓✓", w - 54, h * 0.72); } : null, extraW: n === 3 ? 190 : 0, align: n === 3 ? "left" : "center" }); l.userData = { t0, t1, size: l.userData.size }; return l; };
    const caps = [cap(1, C.steps[0], 0.4, 2.7), cap(2, C.steps[1], 2.8, 5.1), cap(3, C.steps[2], 5.2, 9)];
    const cams = [[0, [-1.4, 2.9, 9.4], [-2.0, 2.4, 3.2]], [2.0, [-1.0, 3.0, 8.6], [-1.9, 2.5, 3.2]], [3.3, [1.6, 3.8, 6.2], [0.6, 3.3, -0.4]], [5.2, [2.8, 3.3, 3.4], [2.4, 2.5, -3.8]], [8, [3.9, 3.5, 4.6], [2.2, 2.6, -3.8]]];

    return (t) => {
      const msg = C.msg, typed = msg.slice(0, Math.floor(K.prog(t, 0.6, 1.8) * msg.length));
      const sent = t > 2.05;
      A.userData.draw({ typed: sent ? "" : typed, caret: !sent && Math.floor(t * 3) % 2 === 0, press: t > 1.9 && t < 2.1, sent, ticks: t > 6.2 });
      SV.userData.draw({ lock: t > 3.4, blink: t > 3.2 && t < 5.2 ? 1 + (Math.floor(t * 6) % 2) : 0 });
      B.userData.draw({ notif: t > 5.4 && t < 6.6, msg: t > 6.2 });
      // bubble flight: A -> server (pause, lock on) -> B
      const u = K.keys(t, [[2.05, 0], [3.2, 0.5, K.ease.inOut], [4.6, 0.5], [5.6, 1.0, K.ease.inOut]]);
      bubble.visible = t > 2.05 && t < 5.65; const p = path.getPointAt(u); bubble.position.copy(p); bubble.rotation.set(0, Math.sin(t * 2) * 0.3, Math.sin(t * 3) * 0.08);
      bubble.scale.setScalar(K.ease.back(K.prog(t, 2.05, 2.35)) * (1 - K.prog(t, 5.45, 5.65)) + 0.001); lock.scale.setScalar(K.ease.back(K.prog(t, 3.4, 3.8)) + 0.001);
      [A, SV, B].forEach((g, i) => { g.position.y = [2.4, 3.3, 2.4][i] + Math.sin(t * 1.1 + i * 2) * 0.05; g.rotation.y = Math.sin(t * 0.6 + i) * 0.05 + [0.18, 0.05, -0.12][i]; });
      // camera with rack focus on the active screen
      const cp = K.keys(t, cams.map(([a, b]) => [a, b])), tg = K.keys(t, cams.map(([a, , b]) => [a, b]));
      const back = S.portrait ? 1.75 : 1.2, pos = [tg[0] + (cp[0] - tg[0]) * back, tg[1] + (cp[1] - tg[1]) * back, tg[2] + (cp[2] - tg[2]) * back];
      S.cam(pos, tg, { fov: 32, aperture: K.lerp(0.14, 0.07, K.tw(t, 5.6, 8)) });
      caps.forEach((l) => { const a = K.ease.back(K.prog(t, l.userData.t0, l.userData.t0 + 0.4)), b = K.tw(t, l.userData.t1 - 0.25, l.userData.t1, K.ease.in); S.pin(l, 0, S.portrait ? -0.56 : -0.8, S.portrait ? 0.66 : 0.4, l.userData.size[0], a * (1 - b)); });
    };
  },

  sound(k) {
    k.bed("room", 0, 8, { vol: 0.7 });
    k.chords(0, 8, ["F4 A4 C5", "D4 F4 A4", "Bb3 D4 F4", "C4 E4 G4"], { bpm: 120, vol: 0.45, arp: true, arpVol: 0.22 });
    k.at(0.6, "type", { n: 11, gap: 0.105, vol: 0.5 }); k.at(1.95, "click", { vol: 0.6 }); k.at(2.05, "swish", { vol: 0.5 }); k.at(2.1, "blip", { f: "C6", vol: 0.25 });
    k.at(3.2, "tick", { vol: 0.3 }); k.at(3.4, "snap", { vol: 0.4 }); k.at(3.45, "ping", { f: "G5", vol: 0.25 }); for (let i = 0; i < 8; i++) k.at(3.5 + i * 0.17, "blip", { f: 1500 + (i % 3) * 200, vol: 0.06 });
    k.at(4.6, "whoosh", { dur: 1.0, vol: 0.4 }); k.at(5.4, "chime", { f: "E6", vol: 0.45 }); k.at(5.45, "bubble", { vol: 0.4 }); k.at(6.2, "pop", { vol: 0.4, pitch: 1.3 }); k.at(6.25, "blip", { f: "A6", vol: 0.2 }); k.at(6.4, "sparkle", { vol: 0.3 });
  },
};
