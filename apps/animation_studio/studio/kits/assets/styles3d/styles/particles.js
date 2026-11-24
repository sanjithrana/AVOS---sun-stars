/* Claude 3D Styles: Particle Swarm (reference animation: "How AI learns") */
(window.STYLES = window.STYLES || {})["particles"] = {
  name: "Particle Swarm",
  card: {
    family: "Light and glass",
    look: "Tens of thousands of tiny glowing points floating in a deep night-blue space. They gather into clear shapes (a cloud, a network, an object), hold them while softly breathing, then swirl apart and fly into the next shape. Colour shifts with each stage.",
    motion: "Every point travels on its own slightly delayed path, so shapes dissolve and re-form in a wave with a little swirl in the middle of each move. Shapes turn slowly in space; the camera drifts with gentle depth of field so near points become soft bokeh.",
    light: "The points are the light: additive glow, strong bloom, nothing else lit.",
    materials: "A custom point shader (soft round sprites, additive blending), deep gradient background.",
    camera: "fov 35-40, slow drift and push-in, wide aperture so out-of-focus points bloom into discs.",
    finish: "ACES tone mapping, strong bloom, deep vignette, fine grain.",
    goodFor: "AI and data, ideas forming, transformations, abstract concepts, brand reveals, anything that changes from one form into another.",
  },
  content: { title: "How AI learns", steps: ["Lots of data", "Finds the patterns", "Makes a smart guess"] },
  duration: 8,
  samples: 20,
  fonts: ["Sora:800"],
  grade: { exposure: 1.0, tonemap: "aces", bloom: 0.75, bloomThreshold: 0.6, saturation: 1.15, contrast: 1.05, vignette: 0.5, grain: 0.016 },

  build(S) {
    const T = S.THREE, K = S.K, C = this.content, R = K.rng(9);
    S.gradientBg("#120a3a", "#03030c", { mid: "#08082a", power: 1.3 });
    const N = 36000;
    const A = new Float32Array(N * 3), B = new Float32Array(N * 3), Cc = new Float32Array(N * 3), rnd = new Float32Array(N), hue = new Float32Array(N);
    const gauss = () => { let u = 0; for (let i = 0; i < 4; i++) u += R(); return (u - 2) / 2; };
    // A: a loose data cloud with a few dense clumps
    const clumps = Array.from({ length: 9 }, () => [gauss() * 3, gauss() * 4, gauss() * 2]);
    for (let i = 0; i < N; i++) { const c = clumps[i % 9], s = R() < 0.55 ? 0.5 : 2.2; A[i * 3] = c[0] * 0.8 + gauss() * s; A[i * 3 + 1] = c[1] * 0.8 + gauss() * s; A[i * 3 + 2] = c[2] + gauss() * s; rnd[i] = R(); hue[i] = R(); }
    // B: a neural network, layers stacked top to bottom, nodes are small spheres, links are lines
    const layers = [4, 6, 6, 3], nodes = []; layers.forEach((n, li) => { for (let j = 0; j < n; j++) nodes.push({ li, p: [(j - (n - 1) / 2) * 1.05, 3.6 - li * 2.15, 0] }); });
    const links = []; for (const a of nodes) for (const b of nodes) if (b.li === a.li + 1) links.push([a.p, b.p]);
    for (let i = 0; i < N; i++) {
      if (i % 5 < 2) { const nd = nodes[i % nodes.length], th = R() * Math.PI * 2, ph = Math.acos(2 * R() - 1), r = 0.24 + R() * 0.04; B[i * 3] = nd.p[0] + Math.sin(ph) * Math.cos(th) * r; B[i * 3 + 1] = nd.p[1] + Math.cos(ph) * r; B[i * 3 + 2] = nd.p[2] + Math.sin(ph) * Math.sin(th) * r; }
      else { const [a, b] = links[i % links.length], u = R(); B[i * 3] = K.lerp(a[0], b[0], u) + gauss() * 0.015; B[i * 3 + 1] = K.lerp(a[1], b[1], u) + gauss() * 0.015; B[i * 3 + 2] = K.lerp(a[2], b[2], u) + gauss() * 0.015; }
    }
    // C: a light bulb (glass, neck, screw base, glowing filament)
    const bulbR = (y) => { if (y > 0) return Math.sqrt(Math.max(0, 1.75 * 1.75 - (y - 0.6) * (y - 0.6) * (y > 0.6 ? 1 : 0.35))); return K.lerp(0.72, 1.6, K.smooth(K.clamp((y + 1.2) / 1.2))); };
    for (let i = 0; i < N; i++) {
      const sel = i % 20, th = R() * Math.PI * 2;
      if (sel < 13) { const y = -1.2 + Math.pow(R(), 0.85) * 3.55, r = bulbR(Math.min(y, 2.3)); Cc[i * 3] = Math.cos(th) * r; Cc[i * 3 + 1] = y; Cc[i * 3 + 2] = Math.sin(th) * r; }
      else if (sel < 17) { const y = -1.25 - R() * 1.1, ridge = 0.68 + 0.06 * Math.sin(y * 18); Cc[i * 3] = Math.cos(th) * ridge; Cc[i * 3 + 1] = y; Cc[i * 3 + 2] = Math.sin(th) * ridge; }
      else { const u = R(); let x, y; if (u < 0.5) { const v = u * 2; x = K.lerp(-0.35, 0.35, v); y = 0.55 + Math.sin(v * Math.PI * 6) * 0.12; } else { const v = (u - 0.5) * 2; x = (v < 0.5 ? -0.35 : 0.35) * 1; y = K.lerp(-1.1, 0.55, v < 0.5 ? v * 2 : (v - 0.5) * 2); } Cc[i * 3] = x + gauss() * 0.02; Cc[i * 3 + 1] = y + gauss() * 0.02; Cc[i * 3 + 2] = gauss() * 0.02; hue[i] = -1; }
    }
    for (let i = 0; i < N * 3; i++) Cc[i] *= 1.18; for (let i = 0; i < N; i++) Cc[i * 3 + 1] += 0.35;
    const g = new T.BufferGeometry();
    g.setAttribute("position", new T.BufferAttribute(A, 3)); g.setAttribute("pB", new T.BufferAttribute(B, 3)); g.setAttribute("pC", new T.BufferAttribute(Cc, 3)); g.setAttribute("rnd", new T.BufferAttribute(rnd, 1)); g.setAttribute("hue", new T.BufferAttribute(hue, 1));
    const mat = new T.ShaderMaterial({
      uniforms: { uT: { value: 0 }, w1: { value: 0 }, w2: { value: 0 }, uScale: { value: S.H / 1920 } },
      vertexShader: `attribute vec3 pB, pC; attribute float rnd, hue; uniform float uT, w1, w2, uScale; varying vec3 vC;
        void main(){
          float k1 = smoothstep(0., 1., clamp(w1 * 1.7 - rnd * 0.7, 0., 1.)), k2 = smoothstep(0., 1., clamp(w2 * 1.7 - rnd * 0.7, 0., 1.));
          vec3 p = mix(mix(position, pB, k1), pC, k2);
          float sw = k1 * (1. - k1) * 4. + k2 * (1. - k2) * 4.; float a = rnd * 40. + uT * 1.3;
          p += vec3(cos(a), sin(a * 1.3), sin(a)) * sw * (0.6 + rnd * 1.2);
          p += vec3(sin(uT * 1.1 + rnd * 30.), cos(uT * 0.9 + rnd * 20.), sin(uT * 1.3 + rnd * 10.)) * 0.025;
          vec3 cA = mix(vec3(.15, .75, 1.), vec3(.35, .5, 1.), hue), cB = mix(vec3(.75, .35, 1.), vec3(1., .3, .7), hue), cC = hue < 0. ? vec3(1.6, 1.2, .5) : mix(vec3(1., .78, .35), vec3(1., .9, .6), hue);
          vC = mix(mix(cA, cB, k1), cC, k2) * (0.55 + rnd * 0.6);
          vec4 mv = modelViewMatrix * vec4(p, 1.); gl_Position = projectionMatrix * mv;
          gl_PointSize = (hue < 0. ? 5.5 : 3.6) * uScale * (12. / -mv.z) * (0.6 + rnd * 0.8);
        }`,
      fragmentShader: "varying vec3 vC; void main(){ float d = length(gl_PointCoord - .5); float a = smoothstep(.5, .05, d); gl_FragColor = vec4(vC * a, 1.); }",
      transparent: true, depthWrite: false, blending: T.AdditiveBlending,
    });
    const pts = new T.Points(g, mat); pts.frustumCulled = false; S.scene.add(pts);
    // background dust
    const dg = new T.BufferGeometry(), dp = new Float32Array(3000 * 3); for (let i = 0; i < 3000; i++) { dp[i * 3] = (R() - 0.5) * 60; dp[i * 3 + 1] = (R() - 0.5) * 60; dp[i * 3 + 2] = -10 - R() * 30; } dg.setAttribute("position", new T.BufferAttribute(dp, 3));
    S.scene.add(new T.Points(dg, new T.PointsMaterial({ color: new T.Color("#6f7cff").multiplyScalar(0.8), size: 2.2 * (S.H / 1920), sizeAttenuation: false, transparent: true, depthWrite: false, blending: T.AdditiveBlending })));

    const cap = (n, word, t0, t1) => { const l = S.label(`${n}  ${word}`, { h: 1, font: "800 120px Sora", color: "#ffffff", bg: "rgba(255,255,255,0.10)", border: "rgba(255,255,255,0.55)", borderW: 6, radius: 999, pad: 50, lit: false, power: 0.7 }); l.userData = { t0, t1, size: l.userData.size }; return l; };
    const caps = [cap(1, C.steps[0], 0.4, 2.6), cap(2, C.steps[1], 2.7, 5.1), cap(3, C.steps[2], 5.2, 9)];

    return (t) => {
      mat.uniforms.uT.value = t; mat.uniforms.w1.value = K.tw(t, 2.3, 4.1, K.ease.sine); mat.uniforms.w2.value = K.tw(t, 4.8, 6.6, K.ease.sine);
      pts.rotation.y = Math.sin(t * 0.35) * 0.5 + (t > 4.8 ? (t - 4.8) * 0.25 : 0); pts.rotation.x = Math.sin(t * 0.3) * 0.08;
      const d = (S.portrait ? 16.5 : 12) * K.lerp(1.08, 0.94, K.tw(t, 0, 8, K.ease.sine));
      S.cam([Math.sin(t * 0.2) * 0.8, 0.3, d], [0, 0.3, 0], { fov: 36, aperture: 0.22 });
      caps.forEach((l) => { const a = K.ease.back(K.prog(t, l.userData.t0, l.userData.t0 + 0.4)), b = K.tw(t, l.userData.t1 - 0.25, l.userData.t1, K.ease.in); S.pin(l, 0, S.portrait ? -0.56 : -0.82, S.portrait ? 0.66 : 0.4, l.userData.size[0], a * (1 - b)); });
    };
  },

  sound(k) {
    k.bed("hum", 0, 8, { vol: 1.0, pitch: 0.8 }); k.bed("wind", 0, 8, { vol: 0.35, pitch: 1.8 });
    k.chords(0, 8, ["D4 F4 A4 C5", "Bb3 D4 F4 A4", "G3 Bb3 D4 F4", "A3 C#4 E4 G4"], { bpm: 120, vol: 0.6, bright: 1300 });
    for (let i = 0; i < 24; i++) k.at(0.2 + i * 0.09, "ping", { f: 1800 + (i % 7) * 220, vol: 0.08, pan: (i % 5) / 2.5 - 0.8 });
    k.at(2.2, "rise", { dur: 1.2, vol: 0.25 }); k.at(2.4, "whoosh", { dur: 1.6, vol: 0.4 }); for (let i = 0; i < 4; i++) k.at(3.4 + i * 0.12, "blip", { f: ["D6", "F6", "A6", "C7"][i], vol: 0.2 });
    k.at(4.7, "rise", { dur: 1.2, vol: 0.3 }); k.at(4.9, "whoosh", { dur: 1.6, vol: 0.45 }); k.at(6.3, "chime", { f: "D6", vol: 0.5 }); k.at(6.35, "sparkle", { vol: 0.5 }); k.at(6.4, "boom", { vol: 0.3, pitch: 1.4 });
  },
};
