/* Claude 3D Styles: Studio Product (reference animation: "Meet Hum, the smart speaker" - a made-up product) */
(window.STYLES = window.STYLES || {})["studio-product"] = {
  name: "Studio Product",
  card: {
    family: "Products and screens",
    look: "One product in a near-black studio, filmed like a flagship launch: the object is carved out of the dark by tall strip softboxes, stands on a black mirror floor that reflects it, and one restrained line of type sits beside it. Premium, quiet, confident.",
    motion: "Slow and deliberate: the product turns a few degrees, light sweeps across its edges, details glow on at the right moment, soft rings ripple out across the floor. The camera starts on a macro detail and pulls back to the hero shot.",
    light: "Two tall strip lights left and right for long edge highlights, a narrow top light, a light sweep that crosses the object once; no fill, so the shadows stay deep.",
    materials: "Fine knitted fabric with a woven bump, glossy black glass on top, an emissive light ring, a black mirror floor (reflection made by a mirrored copy under a dark glossy floor).",
    camera: "Long lens (fov 22-28), slow dolly and arc, shallow depth of field, starting close on a detail.",
    finish: "Deep blacks, ACES tone mapping, soft bloom on the light ring, fine grain, strong vignette.",
    goodFor: "Product reveals and launches, features one by one, premium brands, any single hero object.",
  },
  content: { title: "Meet Hum", steps: ["Meet Hum.", "Sound in every direction.", "It lights up when you talk."] },
  duration: 8,
  samples: 28,
  fonts: ["Sora:600"],
  grade: { exposure: 1.0, tonemap: "aces", bloom: 0.35, bloomThreshold: 0.9, saturation: 1.05, contrast: 1.08, vignette: 0.55, grain: 0.014 },

  build(S) {
    const T = S.THREE, K = S.K, C = this.content;
    S.scene.background = new T.Color("#050507");
    S.env({ top: "#0a0a0d", bottom: "#000000", boxes: [{ pos: [-5, 2, 1], size: [0.8, 7], color: "#ffffff", power: 9 }, { pos: [5, 2, 1], size: [0.8, 7], color: "#ffffff", power: 7 }, { pos: [0, 7, 0], size: [3, 0.6], color: "#ffffff", power: 6 }], intensity: 0.55 });
    // visible strip softboxes far behind
    [-6.5, 6.5].forEach((x) => S.mesh(new T.PlaneGeometry(0.6, 9), S.mat.glow("#ffffff", 1.4), { pos: [x, 4, -7], shadow: false }));
    const key = S.spot({ pos: [-4, 6, 3], target: [0, 1.2, 0], intensity: 80, angle: 0.45, penumbra: 0.8, soft: 0.5 });
    const rim = S.spot({ pos: [3, 5, -4], target: [0, 1.4, 0], intensity: 90, angle: 0.5, penumbra: 0.7, soft: 0.4, shadow: false });
    const sweep = S.point({ pos: [0, 2, 3], intensity: 0, color: "#ffffff", distance: 8 });

    // fabric
    const weave = K.canvas(256, 256), w = weave.getContext("2d"); w.fillStyle = "#808080"; w.fillRect(0, 0, 256, 256);
    for (let y = 0; y < 256; y += 4) for (let x = 0; x < 256; x += 4) { const v = ((x / 4 + y / 4) % 2) ? 170 : 90; w.fillStyle = `rgb(${v},${v},${v})`; w.fillRect(x, y, 4, 2); w.fillStyle = `rgb(${250 - v},${250 - v},${250 - v})`; w.fillRect(x, y + 2, 4, 2); }
    const bump = K.tex(weave, { srgb: false, repeat: [24, 10] });
    const fabric = new T.MeshPhysicalMaterial({ color: "#cfcac2", roughness: 0.85, sheen: 1, sheenRoughness: 0.5, sheenColor: new T.Color("#ffffff"), bumpMap: bump, bumpScale: 1.2 });

    const product = S.group(S.scene);
    const prof = [[0, 0.02], [0.85, 0.02], [0.98, 0.1], [1.02, 0.25], [1.02, 2.15], [0.98, 2.3], [0.9, 2.36], [0, 2.36]].map((p) => new T.Vector2(...p));
    S.mesh(new T.LatheGeometry(prof, 96), fabric, { parent: product });
    S.mesh(new T.CylinderGeometry(0.9, 0.9, 0.03, 96), S.mat.phys("#060608", { roughness: 0.05, clearcoat: 1, clearcoatRoughness: 0.02 }), { pos: [0, 2.37, 0], parent: product });
    const ring = S.mesh(new T.TorusGeometry(0.62, 0.025, 16, 128), S.mat.glow("#ffffff", 0.1), { pos: [0, 2.395, 0], rot: [Math.PI / 2, 0, 0], parent: product, shadow: false });
    const dots = [0, 1, 2, 3].map((i) => S.mesh(new T.CylinderGeometry(0.035, 0.035, 0.01, 20), S.mat.glow("#ffffff", 0.6), { pos: [-0.24 + i * 0.16, 2.39, 0.15], parent: product, shadow: false }));
    S.mesh(new T.CylinderGeometry(0.86, 0.86, 0.02, 64), S.mat.std("#1a1a1d", { roughness: 0.6 }), { pos: [0, 0.01, 0], parent: product });
    // the mirror: a flipped copy under a dark glossy semi-transparent floor
    const mirror = product.clone(true); mirror.scale.y = -1; S.scene.add(mirror);
    const floor = S.mesh(new T.PlaneGeometry(80, 80), S.mat.phys("#060607", { roughness: 0.18, clearcoat: 1, transparent: true, opacity: 0.86 }), { rot: [-Math.PI / 2, 0, 0], shadow: false }); floor.receiveShadow = true;
    // sound rings on the floor
    const rings = [0, 1, 2, 3].map(() => S.mesh(new T.RingGeometry(1, 1.03, 128), S.mat.glow("#9fd8ff", 1.2), { rot: [-Math.PI / 2, 0, 0], pos: [0, 0.004, 0], shadow: false }));
    rings.forEach((r) => { r.material.transparent = true; });

    const cap = (txt, t0, t1) => { const l = S.label(txt, { h: 1, font: "600 110px Sora", color: "#f2f2f4", pad: 20, lit: false, power: 0.85 }); l.userData = { t0, t1, size: l.userData.size }; return l; };
    const caps = [cap(C.steps[0], 2.0, 3.7), cap(C.steps[1], 3.8, 5.6), cap(C.steps[2], 5.7, 9)];
    const ringCols = ["#ffffff", "#7ad7ff", "#b38cff", "#ff7ac8", "#ffb35c"];

    return (t) => {
      product.rotation.y = -0.6 + t * 0.12; mirror.rotation.y = product.rotation.y;
      // light sweep crosses once
      const sw = K.tw(t, 0.6, 2.4, K.ease.inOut); sweep.position.set(K.lerp(-3, 3, sw), 2.2, 2.2); sweep.intensity = Math.sin(sw * Math.PI) * 30;
      key.intensity = K.lerp(10, 80, K.tw(t, 0, 1.6)); rim.intensity = K.lerp(30, 90, K.tw(t, 0, 1.2));
      // ring glows on, then talks (colour cycle + pulse)
      const on = K.tw(t, 1.2, 1.9), talk = K.prog(t, 5.7, 8);
      const c = new T.Color(); if (talk > 0) { const u = (t * 0.9) % 1, i = Math.floor(((t * 0.9) % ringCols.length)); c.set(ringCols[i % ringCols.length]).lerp(new T.Color(ringCols[(i + 1) % ringCols.length]), u); } else c.set("#ffffff");
      const pulse = talk > 0 ? 1 + Math.abs(Math.sin(t * 9)) * 1.2 : 1;
      ring.material.color.copy(c).multiplyScalar(0.1 + on * 3.2 * pulse); mirror.traverse((o) => { if (o.material === ring.material) return; });
      dots.forEach((d, i) => d.material.color.setScalar(0.1 + (talk > 0 ? (Math.sin(t * 10 + i * 1.3) * 0.5 + 0.5) * 3 : on * 0.6)));
      // floor rings during "sound in every direction"
      rings.forEach((r, i) => { const ph = ((t - 3.8) * 0.6 + i / rings.length) % 1, vis = K.prog(t, 3.8, 4.2) * (1 - K.prog(t, 5.6, 6.0)); r.visible = t > 3.8 && vis > 0; r.scale.setScalar(1.05 + ph * 5); r.material.opacity = (1 - ph) * vis; });
      // camera: macro on the top ring, then the hero shot
      const k = K.tw(t, 0.2, 3.6, K.ease.inOut);
      const d = K.lerp(3.2, S.portrait ? 11.5 : 8.5, k), el = K.lerp(0.75, 0.16, k), az = K.lerp(0.5, -0.25, K.tw(t, 0, 8, K.ease.sine));
      const tgt = [0, K.lerp(2.3, S.portrait ? 1.7 : 1.3, k), 0];
      S.cam([Math.sin(az) * Math.cos(el) * d, tgt[1] + Math.sin(el) * d, Math.cos(az) * Math.cos(el) * d], tgt, { fov: 26, aperture: K.lerp(0.06, 0.12, k) });
      caps.forEach((l) => { const a = K.tw(t, l.userData.t0, l.userData.t0 + 0.6, K.ease.out), b = K.tw(t, l.userData.t1 - 0.3, l.userData.t1, K.ease.in); l.material.opacity = a * (1 - b); S.pin(l, 0, S.portrait ? 0.66 : -0.78, S.portrait ? 0.66 : 0.36, l.userData.size[0], 0.96 + a * 0.04); });
    };
  },

  sound(k) {
    k.bed("room", 0, 8, { vol: 0.5, pitch: 0.7 });
    k.chords(0.5, 8, ["A3 E4 B4", "F3 C4 G4", "D3 A3 E4", "E3 B3 F#4"], { bpm: 100, vol: 0.55, bright: 900 });
    k.at(0.2, "rise", { dur: 1.6, vol: 0.15 }); k.at(0.6, "whoosh", { dur: 1.8, vol: 0.25 }); k.at(1.3, "chime", { f: "A5", vol: 0.35 });
    k.at(2.0, "hit", { vol: 0.3, pitch: 0.8 }); for (let i = 0; i < 4; i++) k.at(3.85 + i * 0.42, "drop", { vol: 0.12, pitch: 0.5, dur: 0.6 });
    k.at(3.8, "boom", { vol: 0.25, pitch: 0.7 }); for (let i = 0; i < 6; i++) k.at(5.8 + i * 0.3, "blip", { f: ["A5", "C#6", "E6", "A6", "E6", "C#6"][i], vol: 0.18 }); k.at(5.7, "sparkle", { vol: 0.3 });
  },
};
