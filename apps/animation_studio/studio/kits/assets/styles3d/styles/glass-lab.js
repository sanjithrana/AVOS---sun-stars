/* Claude 3D Styles: Glass Lab (reference animation: "Why oil floats on water") */
(window.STYLES = window.STYLES || {})["glass-lab"] = {
  name: "Glass Lab",
  card: {
    family: "Light and glass",
    look: "Clear lab glass in a bright white studio: a tall cylinder with printed measure marks, a small pouring beaker, and coloured liquids with crisp boundaries and a lighter surface on top. Each liquid throws a soft pool of its own coloured light on the white table.",
    motion: "Liquids pour in thin streams, levels rise smoothly, heavier liquids sink through lighter ones as droplets and push the layers up. The beaker tilts in, pours, tilts back. Callout tags slide out on thin lines.",
    light: "Tall strip softboxes left and right that draw long clean reflections down the glass, a back light that makes the liquids glow, a soft overhead fill.",
    materials: "Glass: transmission 1, roughness ~0.02, ior 1.5. Liquids: glossy, semi-transparent colour with a slightly lighter top. Table: white gloss. White printed marks.",
    camera: "fov 26-30, eye level with the glass, a slow push-in and a small arc; shallow depth of field.",
    finish: "Clean, bright, slightly cool; neutral tone mapping, gentle bloom on the highlights.",
    goodFor: "Chemistry and density, mixing and layers, recipes and drinks, comparing amounts, anything about liquids, light or measurement.",
  },
  content: { title: "Why oil floats on water", steps: ["Pour in oil", "Water sinks under it", "Honey sinks lowest"], layers: [["Oil", "0.9 g/ml"], ["Water", "1.0 g/ml"], ["Honey", "1.4 g/ml"]] },
  duration: 8,
  samples: 28,
  fonts: ["Manrope:800"],
  grade: { exposure: 1.02, tonemap: "neutral", bloom: 0.16, bloomThreshold: 1.05, saturation: 1.08, contrast: 1.05, vignette: 0.22, grain: 0.008 },

  build(S) {
    const T = S.THREE, K = S.K, C = this.content;
    S.env({ boxes: [{ pos: [-6, 3, 2], size: [1.4, 9], color: "#ffffff", power: 9 }, { pos: [6, 3, 2], size: [1.4, 9], color: "#ffffff", power: 7 }, { pos: [0, 9, 0], size: [6, 2], color: "#ffffff", power: 4 }, { pos: [0, 2, -8], size: [8, 5], color: "#ffffff", power: 2 }], intensity: 0.7, top: "#dbe7ff", bottom: "#6f8fc9", horizon: "#b3c8ee" });
    S.scene.background = new T.Color("#9db8e6");
    S.mesh(K.sweep(60, 30, 30, 6), S.mat.phys("#a9c3ee", { roughness: 0.45, clearcoat: 0.3 }), { pos: [0, 0, -3.5] });
    S.sun({ pos: [-4, 9, -5], intensity: 1.6, soft: 1.8, size: 6 });
    S.sun({ pos: [5, 7, 8], intensity: 0.9, soft: 2.5, size: 6 }).castShadow = false;
    S.hemi("#ffffff", "#e9edf2", 0.6);

    const glass = (o = {}) => new T.MeshPhysicalMaterial({ color: "#ffffff", transmission: 1, roughness: 0.03, thickness: 0.12, ior: 1.5, specularIntensity: 1, envMapIntensity: 1.4, ...o });
    // liquids are NOT transmissive: three.js glass only refracts opaque things behind it. A soft emissive makes them glow from within.
    const liquid = (c, o = {}) => new T.MeshPhysicalMaterial({ color: c, roughness: 0.12, clearcoat: 1, clearcoatRoughness: 0.05, emissive: c, emissiveIntensity: 0.28, attenuationColor: new T.Color(c), ...o });
    const cols = { oil: "#ffd23a", water: "#1e8fff", honey: "#e8930f" };

    // the cylinder (hollow lathe: outer wall, rim, inner wall, thick base)
    const H = 4.3, Ro = 1.05, Ri = 0.97;
    const prof = [[0, 0], [Ro - 0.05, 0], [Ro, 0.05], [Ro, H], [Ro + 0.04, H + 0.03], [Ro - 0.02, H + 0.07], [Ri, H], [Ri, 0.2], [0, 0.2]].map((p) => new T.Vector2(...p));
    const cyl = S.mesh(new T.LatheGeometry(prof, 96), glass({ side: T.DoubleSide }), {}); cyl.castShadow = false;
    // printed white measure marks (a thin transparent sleeve just outside the glass)
    const marks = S.picture(2 * Math.PI * (Ro + 0.005), H, (x, w, h) => { x.clearRect(0, 0, w, h); x.fillStyle = "rgba(255,255,255,0.95)"; x.font = `700 ${h * 0.03}px Manrope`; for (let i = 1; i <= 16; i++) { const y = h - (i / 18) * h - h * 0.04, long = i % 4 === 0; x.fillRect(w * 0.47, y, long ? w * 0.05 : w * 0.025, h * 0.004); if (long) x.fillText(String(i * 25), w * 0.53, y + h * 0.01); } }, { transparent: true, ppu: 300 });
    marks.geometry.dispose(); marks.geometry = new T.CylinderGeometry(Ro + 0.006, Ro + 0.006, H, 96, 1, true); marks.position.y = H / 2; marks.rotation.y = -Math.PI / 2; marks.material.side = T.FrontSide; marks.material.alphaTest = 0.3; marks.castShadow = false;

    // liquid layers (cylinders with a slightly lighter meniscus top)
    const layer = (c) => { const g = S.group(); const m = S.mesh(new T.CylinderGeometry(Ri - 0.012, Ri - 0.012, 1, 72), liquid(c), { parent: g }); const top = S.mesh(new T.CircleGeometry(Ri - 0.012, 72), liquid(new T.Color(c).lerp(new T.Color("#ffffff"), 0.35).getStyle(), { emissiveIntensity: 0.45 }), { rot: [-Math.PI / 2, 0, 0], parent: g }); m.castShadow = top.castShadow = false; return { g, m, top }; };
    const L = { honey: layer(cols.honey), water: layer(cols.water), oil: layer(cols.oil) };
    const setLayer = (l, y0, h) => { l.g.visible = h > 0.005; l.m.scale.y = Math.max(h, 0.001); l.m.position.y = y0 + h / 2; l.top.position.y = y0 + h + 0.001; };

    // the pouring beaker (one beaker, refilled with each liquid)
    const beak = S.group(S.scene);
    const bprof = [[0, 0], [0.52, 0], [0.55, 0.04], [0.55, 1.15], [0.62, 1.22], [0.58, 1.25], [0.5, 1.15], [0.5, 0.08], [0, 0.08]].map((p) => new T.Vector2(...p));
    S.mesh(new T.LatheGeometry(bprof, 64), glass({ side: T.DoubleSide }), { parent: beak }).castShadow = false;
    const bliq = S.mesh(new T.CylinderGeometry(0.48, 0.48, 0.7, 48), liquid(cols.oil), { pos: [0, 0.45, 0], parent: beak }); bliq.castShadow = false;
    const stream = S.mesh(new T.CylinderGeometry(0.055, 0.04, 1, 20), liquid(cols.oil), {}); stream.castShadow = false;
    const drops = []; for (let i = 0; i < 6; i++) drops.push(S.mesh(new T.SphereGeometry(0.12, 24, 16), liquid(cols.water), { shadow: false }));

    // coloured light pools on the table
    const poolTex = K.tex((() => { const c = K.canvas(256, 256), x = c.getContext("2d"), g = x.createRadialGradient(128, 128, 0, 128, 128, 128); g.addColorStop(0, "rgba(255,255,255,1)"); g.addColorStop(0.45, "rgba(255,255,255,.5)"); g.addColorStop(1, "rgba(255,255,255,0)"); x.fillStyle = g; x.fillRect(0, 0, 256, 256); return c; })());
    const pool = (c, x, z, s) => { const m = S.mesh(new T.PlaneGeometry(s, s * 0.7), new T.MeshBasicMaterial({ map: poolTex, color: c, transparent: true, blending: T.AdditiveBlending, depthWrite: false }), { rot: [-Math.PI / 2, 0, 0], pos: [x, 0.006, z], shadow: false }); return m; };
    const pools = { oil: pool(cols.oil, 0.8, 2.0, 3.4), water: pool(cols.water, 0.3, 2.3, 3.6), honey: pool(cols.honey, -0.3, 2.0, 3.2) };

    // tags: step line at the top, density callouts at the end
    const stepTag = (n, word, t0, t1) => { const l = S.label(`${n}  ${word}`, { h: 0.5, font: "800 120px Manrope", color: "#ffffff", bg: "#1b2433", radius: 999, pad: 46, lit: false }); l.userData = { t0, t1, size: l.userData.size }; return l; };
    const steps = [stepTag(1, C.steps[0], 0.4, 2.7), stepTag(2, C.steps[1], 2.8, 5.1), stepTag(3, C.steps[2], 5.2, 9)];
    const call = ([name, val], c) => { const g = S.group(); const l = S.label(`${name}  ${val}`, { h: 0.36, font: "800 110px Manrope", color: "#1b2433", bg: "#ffffff", radius: 999, pad: 40, extraW: 70, align: "right", lit: false, parent: g, draw: (x, w, h) => { x.fillStyle = c; x.beginPath(); x.arc(40 + 34, h / 2, 26, 0, 7); x.fill(); } }); l.position.x = l.userData.size[0] / 2 + 0.25; S.mesh(new T.BoxGeometry(0.28, 0.012, 0.012), S.mat.basic("#1b2433"), { pos: [0.12, 0, 0], parent: g, shadow: false }); return g; };
    const calls = [call(C.layers[0], cols.oil), call(C.layers[1], cols.water), call(C.layers[2], cols.honey)];

    return (t) => {
      const o = K.tw(t, 0.6, 2.3) * 1.15, w = K.tw(t, 3.0, 4.7) * 1.15, h = K.tw(t, 5.3, 6.9) * 1.0, base = 0.2;
      setLayer(L.honey, base, h); setLayer(L.water, base + h, w); setLayer(L.oil, base + h + w, o);
      // beaker: which liquid, tilt, position over the cylinder
      const phase = t < 2.75 ? "oil" : t < 5.05 ? "water" : "honey", p0 = { oil: 0.2, water: 2.75, honey: 5.05 }[phase], [a, b] = { oil: [0.6, 2.3], water: [3.0, 4.7], honey: [5.3, 6.9] }[phase];
      bliq.material.color.set(cols[phase]); bliq.material.emissive.set(cols[phase]); stream.material.color.set(cols[phase]); stream.material.emissive.set(cols[phase]);
      const inn = K.tw(t, p0, p0 + 0.45, K.ease.out), out = phase === "honey" ? K.tw(t, 7.0, 7.6, K.ease.in) : K.tw(t, b + 0.05, b + 0.4, K.ease.in), tilt = K.tw(t, a - 0.35, a, K.ease.inOut) * (1 - K.tw(t, b - 0.05, b + 0.25));
      beak.position.set(K.lerp(3.2, 1.25, inn) + out * 2.6, H + 0.55 + out * 0.6, 0.15); beak.rotation.z = tilt * 1.55; bliq.scale.y = Math.max(0.05, 1 - K.prog(t, a, b) * 0.9); bliq.position.y = 0.08 + 0.35 * bliq.scale.y;
      // stream from the lip down to the right level
      const pouring = t > a && t < b, lip = new T.Vector3(-0.6, 1.2, 0).applyMatrix4(beak.matrixWorld.compose(beak.position, beak.quaternion, beak.scale));
      const target = phase === "oil" ? base + h + w + o : phase === "water" ? base + h + w : base + h;
      const sx = K.lerp(lip.x, 0.15, 0.6), top = lip.y, len = Math.max(0.01, top - target);
      stream.visible = pouring; stream.scale.set(1, len, 1); stream.position.set(sx, target + len / 2, 0.1);
      // water drops sinking through the oil while water pours; honey drops sink through both
      drops.forEach((d, i) => { const dp = phase === "water" ? K.prog(t, 3.0 + i * 0.25, 3.6 + i * 0.25) : phase === "honey" ? K.prog(t, 5.3 + i * 0.25, 5.9 + i * 0.25) : 0; d.visible = dp > 0 && dp < 1; const yTop = base + h + w + o, yBot = phase === "water" ? base + h + w : base + h; d.position.set(0.15 + Math.sin(i * 2.1) * 0.35, K.lerp(yTop, yBot, K.ease.in(dp)), 0.1 + Math.cos(i * 1.7) * 0.3); d.scale.set(1, 1.2, 1); d.material.color.set(cols[phase === "honey" ? "honey" : "water"]); d.material.emissive.set(cols[phase === "honey" ? "honey" : "water"]); });
      // light pools grow with each layer
      pools.oil.material.opacity = 0.55 * K.clamp(o / 1.15); pools.water.material.opacity = 0.6 * K.clamp(w / 1.15); pools.honey.material.opacity = 0.6 * K.clamp(h);
      // labels
      const camP = S.portrait ? [0.95, 3.15, 0] : [0.9, 2.7, 0];
      [[base + h + w + o / 2, 6.0], [base + h + w / 2, 6.35], [base + h / 2, 6.7]].forEach(([y, t0], i) => { const k = K.tw(t, t0, t0 + 0.5, K.ease.out); calls[i].visible = k > 0.01; calls[i].position.set(Ro + 0.05, y, 0.25); calls[i].scale.set(Math.max(0.001, k), Math.max(0.001, k), 1); });
      // camera
      const d = (S.portrait ? S.fitDist(5.3, 8.4, 28) : S.fitDist(9.5, 7.2, 28)) * K.lerp(1.08, 0.97, K.tw(t, 0, 8, K.ease.sine)), ang = K.lerp(-0.18, 0.12, K.tw(t, 0, 8, K.ease.sine));
      S.cam([Math.sin(ang) * d + camP[0], camP[1] + 0.5, Math.cos(ang) * d], [camP[0], camP[1], 0], { fov: 28, aperture: 0.05 });
      steps.forEach((l) => { const k = K.ease.back(K.prog(t, l.userData.t0, l.userData.t0 + 0.45)), q = K.tw(t, l.userData.t1 - 0.25, l.userData.t1, K.ease.in); S.pin(l, 0, S.portrait ? 0.66 : 0.78, S.portrait ? 0.7 : 0.4, l.userData.size[0], k * (1 - q)); });
    };
  },

  sound(k) {
    k.bed("room", 0, 8, { vol: 0.7 });
    k.chords(0, 8, ["E4 G#4 B4", "C#4 E4 G#4", "A3 C#4 E4", "B3 D#4 F#4"], { bpm: 120, vol: 0.45, arp: true, arpVol: 0.2 });
    [[0.2, 0.6, 2.3], [2.75, 3.0, 4.7], [5.05, 5.3, 6.9]].forEach(([inn, a, b], i) => { k.at(inn, "glass", { f: ["E6", "G#6", "B6"][i], vol: 0.55 }); k.at(a - 0.2, "glass", { f: "C#7", vol: 0.2, pitch: 1.0 }); k.bed("water", a, b, { vol: 1.3, pitch: 1.6 - i * 0.3 }); });
    for (let i = 0; i < 6; i++) { k.at(3.0 + i * 0.25 + 0.5, "bubble", { vol: 0.45, pitch: 0.7 }); k.at(5.3 + i * 0.25 + 0.5, "bubble", { vol: 0.45, pitch: 0.5 }); }
    k.at(6.0, "ping", { f: "E6", vol: 0.3 }); k.at(6.35, "ping", { f: "G#6", vol: 0.3 }); k.at(6.7, "ping", { f: "B6", vol: 0.3 }); k.at(7.1, "chime", { f: "E6", vol: 0.4 });
  },
};
