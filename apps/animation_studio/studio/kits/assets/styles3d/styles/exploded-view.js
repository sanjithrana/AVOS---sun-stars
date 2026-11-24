/* Claude 3D Styles: Exploded View (reference animation: "What's inside a wireless earbud") */
(window.STYLES = window.STYLES || {})["exploded-view"] = {
  name: "Exploded View",
  card: {
    family: "Diagrams with depth",
    look: "A product teardown film: one object floats over a pale seamless studio, comes apart along its axis into its parts, and every part gets a numbered callout in ink blue on a white tag with a thin leader line. Clean, precise, premium.",
    motion: "The object turns slowly on its own, then the parts slide apart along one axis with a soft overshoot and keep a gentle float. Callouts tick on one by one. A glowing pulse travels from part to part to show how they work together.",
    light: "Large soft key from the upper left, a bright rim from behind so every edge reads, a white fill; soft contact shadow on the floor.",
    materials: "Gloss white plastic (clearcoat), brushed and polished metal, a green circuit board with black chips, soft grey silicone. The studio is matte off-white.",
    camera: "fov 26-30 at the object's height, a slow orbit and a pull-back when it explodes; shallow depth of field.",
    finish: "Neutral tone mapping, very clean, light vignette, almost no grain.",
    goodFor: "What's inside a product or device, how a machine is built, parts of anything, product launches and comparisons.",
  },
  content: { title: "What's inside a wireless earbud", steps: ["One tiny earbud", "Five parts inside", "Battery to chip to sound"], parts: ["Ear tip", "Speaker", "Chip", "Battery", "Shell"] },
  duration: 8,
  samples: 28,
  fonts: ["Inter:800"],
  grade: { exposure: 0.98, tonemap: "neutral", bloom: 0.14, bloomThreshold: 1.1, saturation: 1.06, contrast: 1.05, vignette: 0.25, grain: 0.006 },

  build(S) {
    const T = S.THREE, K = S.K, C = this.content, ink = "#1f3fc4";
    S.env({ top: "#ffffff", bottom: "#d9dee6", boxes: [{ pos: [-5, 6, 5], size: [5, 4], color: "#ffffff", power: 6 }, { pos: [4, 4, -6], size: [6, 2], color: "#ffffff", power: 5 }, { pos: [6, 2, 4], size: [2, 5], color: "#ffffff", power: 3 }], intensity: 1 });
    S.scene.background = new T.Color("#c9d3e3");
    S.mesh(K.sweep(60, 30, 30, 6), S.mat.matte("#c9d3e3"), { pos: [0, -1.6, -4] });
    S.sun({ pos: [-5, 10, 6], intensity: 2.0, soft: 2.2, size: 6 });
    S.spot({ pos: [3, 5, -6], target: [0, 1, 0], intensity: 70, angle: 0.6, soft: 0.6, shadow: false });
    S.hemi("#ffffff", "#dde3ec", 0.6);

    const white = S.mat.gloss("#fbfbfd", { roughness: 0.25 });
    const metal = S.mat.metal("#c9ced6", { roughness: 0.28 });
    const parts = [];
    const part = (g, rest, out, i) => { g.position.y = rest; parts.push({ g, rest, out, i }); return g; };
    // 1 ear tip (silicone dome)
    const tip = S.group(); S.mesh(new T.LatheGeometry([[0, 0.42], [0.18, 0.4], [0.36, 0.3], [0.46, 0.12], [0.44, 0.02], [0.24, 0.0], [0.2, -0.12], [0, -0.12]].map((p) => new T.Vector2(...p)), 48), S.mat.phys("#c7ccd4", { roughness: 0.55, sheen: 0.5 }), { parent: tip });
    part(tip, 1.55, 4.9, 0);
    // 2 speaker driver: metal ring + dark cone membrane
    const drv = S.group(); S.mesh(new T.CylinderGeometry(0.52, 0.52, 0.16, 48), metal, { parent: drv }); S.mesh(new T.ConeGeometry(0.44, 0.14, 48, 1, true), S.mat.std("#20242c", { roughness: 0.4, side: T.DoubleSide }), { pos: [0, 0.12, 0], parent: drv }); S.mesh(new T.CylinderGeometry(0.12, 0.12, 0.06, 24), S.mat.metal("#e7c46a", { roughness: 0.2 }), { pos: [0, 0.12, 0], parent: drv });
    part(drv, 1.2, 3.75, 1);
    // 3 chip board
    const pcb = S.group(); S.mesh(K.rbox(0.8, 0.07, 0.72, 0.03), S.mat.std("#1f8a4c", { roughness: 0.45 }), { parent: pcb }); S.mesh(K.rbox(0.34, 0.07, 0.34, 0.02), S.mat.std("#15171c", { roughness: 0.35 }), { pos: [0, 0.07, 0], parent: pcb }); [[-0.25, 0.18], [0.25, -0.2], [0.26, 0.18], [-0.24, -0.2]].forEach(([x, z]) => S.mesh(K.rbox(0.12, 0.05, 0.08, 0.01), S.mat.metal("#d9b25b", { roughness: 0.3 }), { pos: [x, 0.05, z], parent: pcb }));
    const chipGlow = S.mesh(new T.PlaneGeometry(0.3, 0.3), S.mat.glow("#4fd1ff", 2.5), { pos: [0, 0.112, 0], rot: [-Math.PI / 2, 0, 0], parent: pcb, shadow: false });
    part(pcb, 0.9, 2.65, 2);
    // 4 battery (button cell)
    const bat = S.group(); S.mesh(new T.CylinderGeometry(0.4, 0.4, 0.28, 48), S.mat.metal("#b8bec8", { roughness: 0.2 }), { parent: bat }); S.mesh(new T.CylinderGeometry(0.3, 0.3, 0.3, 48), S.mat.metal("#9aa1ac", { roughness: 0.3 }), { pos: [0, 0.01, 0], parent: bat });
    part(bat, 0.55, 1.6, 3);
    // 5 shell + stem with mic holes
    const shell = S.group(); S.mesh(new T.SphereGeometry(0.62, 48, 24, 0, Math.PI * 2, Math.PI / 2, Math.PI / 2), white, { pos: [0, 0.75, 0], parent: shell }); S.mesh(new T.CylinderGeometry(0.62, 0.62, 0.55, 48, 1, true), white, { pos: [0, 1.02, 0], parent: shell });
    S.mesh(K.rbox(0.36, 1.7, 0.3, 0.15), white, { pos: [0.3, -0.25, 0.1], rot: [0, 0, 0.15], parent: shell });
    [0.2, -0.2, -0.95].forEach((y, i) => S.mesh(new T.CylinderGeometry(0.035, 0.035, 0.02, 16), S.mat.std("#2a2e36"), { pos: [0.31 + y * -0.15 + 0.02, y, 0.26], rot: [Math.PI / 2, 0, 0], parent: shell }));
    part(shell, 0, 0, 4);
    const all = S.group(); parts.forEach((p) => all.add(p.g));

    // pulse (battery -> chip -> speaker -> tip)
    const pulse = S.mesh(new T.SphereGeometry(0.11, 24, 16), S.mat.glow("#4fd1ff", 4), { shadow: false });
    // callouts: number badge + name, leader line to the part
    const callouts = C.parts.map((name, i) => {
      const g = S.group(); const side = i % 2 ? -1 : 1;
      const l = S.label(name, { h: 0.33, font: "800 110px Inter", color: ink, bg: "#ffffff", radius: 999, pad: 40, extraW: 120, align: "right", lit: false, parent: g, draw: (x, w, h) => { x.fillStyle = ink; x.beginPath(); x.arc(40 + 52, h / 2, 52, 0, 7); x.fill(); x.fillStyle = "#fff"; x.font = "800 80px Inter"; x.textAlign = "center"; x.fillText(String(i + 1), 40 + 52, h / 2 + 28); } });
      const w = l.userData.size[0]; l.position.x = side * (w / 2 + 0.5);
      const line = S.mesh(new T.BoxGeometry(0.5, 0.012, 0.012), S.mat.basic(ink), { pos: [side * 0.3, 0, 0], parent: g, shadow: false });
      S.mesh(new T.SphereGeometry(0.03, 12, 8), S.mat.basic(ink), { pos: [side * 0.05, 0, 0], parent: g, shadow: false });
      g.userData = { side, i }; return g;
    });
    const cap = (n, word, t0, t1) => { const l = S.label(`${n}  ${word}`, { h: 1, font: "800 120px Inter", color: "#ffffff", bg: ink, radius: 999, pad: 50, lit: false }); l.userData = { t0, t1, size: l.userData.size }; return l; };
    const caps = [cap(1, C.steps[0], 0.4, 2.5), cap(2, C.steps[1], 2.6, 5.0), cap(3, C.steps[2], 5.1, 9)];

    return (t) => {
      const ex = K.ease.back(K.prog(t, 2.5, 3.6));
      parts.forEach((p) => { p.g.position.y = K.lerp(p.rest, p.out, ex) + (ex > 0.5 ? Math.sin(t * 1.6 + p.i) * 0.03 : 0); p.g.rotation.y = ex * p.i * 0.15; });
      all.rotation.y = t * 0.35 + 0.4; all.rotation.z = -0.08 * (1 - ex);
      // pulse path with glow on the chip
      const pk = K.prog(t, 5.3, 7.3), stops = [1.6, 2.65, 3.75, 4.9], seg = Math.min(2.999, pk * 3), si = Math.floor(seg);
      pulse.visible = t > 5.2 && t < 7.4; pulse.position.set(0, K.lerp(stops[si], stops[si + 1], K.ease.inOut(seg - si)) + 0.3, 0.55);
      chipGlow.material.color.setRGB(0.3, 0.8, 1).multiplyScalar(1 + Math.max(0, Math.sin(K.prog(t, 5.8, 6.4) * Math.PI)) * 4);
      // camera: close on the earbud, then pulls back to show the stack
      const k = K.tw(t, 2.3, 3.8), d = K.lerp(S.portrait ? 9 : 6.5, S.portrait ? 14.5 : 10, k), ty = K.lerp(0.8, 2.5, k);
      const camPos = [Math.sin(0.25) * d, ty + 1.0, Math.cos(0.25) * d];
      S.cam(camPos, [0, ty, 0], { fov: 27, aperture: 0.06 });
      // callouts appear one by one after the explode, beside each part, facing the camera
      callouts.forEach((g, i) => { const p = parts[i], a = K.ease.back(K.prog(t, 3.3 + i * 0.25, 3.7 + i * 0.25)); g.visible = a > 0.01; g.position.set(0, p.g.position.y + (i === 4 ? 0.9 : 0.15), 0); g.scale.setScalar(Math.max(0.001, a)); g.lookAt(camPos[0], g.position.y, camPos[2]); g.translateX(g.userData.side * 0.45); });
      caps.forEach((l) => { const a = K.ease.back(K.prog(t, l.userData.t0, l.userData.t0 + 0.4)), b = K.tw(t, l.userData.t1 - 0.25, l.userData.t1, K.ease.in); S.pin(l, 0, S.portrait ? -0.56 : -0.82, S.portrait ? 0.66 : 0.42, l.userData.size[0], a * (1 - b)); });
    };
  },

  sound(k) {
    k.bed("room", 0, 8, { vol: 0.7 });
    k.chords(0, 8, ["E4 G4 B4", "C4 E4 G4", "A3 C4 E4", "B3 D#4 F#4"], { bpm: 120, vol: 0.4, arp: true, arpVol: 0.2 });
    k.at(0.4, "ping", { f: "B5", vol: 0.3 }); k.at(2.4, "rise", { dur: 0.4, vol: 0.2 }); k.at(2.55, "whoosh", { dur: 0.6, vol: 0.45 }); k.at(2.75, "snap", { vol: 0.5 });
    for (let i = 0; i < 5; i++) { k.at(2.8 + i * 0.07, "click", { vol: 0.3 }); k.at(3.3 + i * 0.25, "tick", { vol: 0.35, pitch: 0.9 + i * 0.08 }); }
    k.bed("hum", 5.3, 7.3, { vol: 0.8, pitch: 2 }); [5.3, 5.97, 6.63, 7.3].forEach((t, i) => k.at(t, "blip", { f: ["E5", "G5", "B5", "E6"][i], vol: 0.3 }));
    k.at(7.35, "chime", { f: "E6", vol: 0.45 }); k.at(7.5, "whoosh", { dur: 0.6, vol: 0.3, down: true }); k.at(8.0, "snap", { vol: 0.3 });
  },
};
