/* Claude 3D Styles: Data Towers (reference animation: "$1,000 at 10% a year") */
(window.STYLES = window.STYLES || {})["data-towers"] = {
  name: "Data Towers",
  card: {
    family: "Diagrams with depth",
    look: "A chart built as an architect's presentation model: towers of stacked pale stone blocks on a printed plinth, one block per unit, with the hero bar in vivid vermilion. Tiny model trees and people stand around for scale, and printed labels sit on the plinth in front of each tower.",
    motion: "Blocks drop onto the towers one at a time with a soft thud and settle, so bars grow by counting; value tags count up as they grow. The camera starts low at the first bar and rises with the tallest one.",
    light: "Bright late-morning sun from the left with long soft shadows across the plinth, a soft sky fill.",
    materials: "Matte stone and card (roughness 0.85) with tiny rounded edges, a printed paper top on the plinth, a glossy vermilion hero bar.",
    camera: "fov 30-34, low three-quarter view that cranes up and pulls back; shallow depth of field.",
    finish: "Neutral tone mapping, clean contrast, soft vignette.",
    goodFor: "Any numbers: growth, comparisons, rankings, money, statistics, before and after, timelines with values. Real figures only.",
  },
  content: { title: "$1,000 at 10% a year", steps: ["Put in $1,000", "It grows 10% a year", "30 years later: $17,449"], bars: [["TODAY", 1000], ["10 YEARS", 2594], ["20 YEARS", 6727], ["30 YEARS", 17449]], unit: 1000 },
  duration: 8,
  samples: 24,
  fonts: ["Inter:800", "Space Grotesk:700"],
  grade: { exposure: 1.04, tonemap: "neutral", bloom: 0.06, saturation: 1.06, contrast: 1.06, vignette: 0.3, grain: 0.01 },

  build(S) {
    const T = S.THREE, K = S.K, C = this.content, R = K.rng(3);
    S.gradientBg("#d8e6f5", "#f6f3ee", { mid: "#eef2f6" });
    S.env({ top: "#ffffff", bottom: "#d7d0c4", intensity: 0.45 });
    S.sun({ pos: [-12, 13, 7], intensity: 2.9, soft: 1.2, size: 12, map: 4096 });
    S.hemi("#eef5ff", "#cbbfae", 0.7);
    S.shadowFloor(0.12, 120, -0.8);

    // plinth with a printed top
    const PW = 10.5, PD = 6.5;
    const top = K.canvas(2100, 1300), x = top.getContext("2d");
    x.fillStyle = "#f4f0e8"; x.fillRect(0, 0, 2100, 1300);
    for (let i = 0; i <= 2100; i += 50) { x.fillStyle = "rgba(60,70,90,.07)"; x.fillRect(i, 0, 2, 1300); } for (let j = 0; j <= 1300; j += 50) { x.fillStyle = "rgba(60,70,90,.07)"; x.fillRect(0, j, 2100, 2); }
    x.fillStyle = "#2a3346"; x.font = "700 64px 'Space Grotesk'"; x.textAlign = "center";
    C.bars.forEach(([lab], i) => x.fillText(lab, 2100 / 2 + (i - 1.5) * 500, 1080));
    x.fillStyle = "rgba(42,51,70,.75)"; x.font = "700 46px 'Space Grotesk'"; x.fillText(C.title.toUpperCase(), 1050, 1220);
    S.mesh(K.rbox(PW, 0.7, PD, 0.12), S.mat.std("#e7e0d4", { roughness: 0.85 }), { pos: [0, -0.35, 0] });
    S.mesh(new T.PlaneGeometry(PW - 0.2, PD - 0.2), new T.MeshStandardMaterial({ map: K.tex(top), roughness: 0.9 }), { pos: [0, 0.002, 0], rot: [-Math.PI / 2, 0, 0], shadow: false }).receiveShadow = true;

    // towers of blocks
    const BH = 0.5, BW = 1.25, gap = 0.035, stone = ["#ece6da", "#e6dfd2", "#efe9de", "#e2dacb"];
    const towers = C.bars.map(([, v], i) => {
      const n = v / C.unit, cnt = Math.ceil(n), g = S.group(S.scene, [(i - 1.5) * 2.5, 0, -0.6]);
      const hero = i === C.bars.length - 1, blocks = [];
      for (let b = 0; b < cnt; b++) { const frac = b === cnt - 1 && n % 1 > 0.001 ? n % 1 : 1; const m = S.mesh(K.rbox(BW, BH * frac - gap, BW, 0.05, 3), hero ? S.mat.gloss("#e8452c", { roughness: 0.35, clearcoat: 0.6 }) : S.mat.std(stone[(b + i) % 4], { roughness: 0.85 }), { parent: g }); m.userData = { y: b * BH + (BH * frac) / 2, frac }; blocks.push(m); }
      return { g, blocks, n, v, hero };
    });
    const times = [[0.6, 1.0], [2.5, 3.3], [3.3, 4.7], [5.0, 7.0]];
    // tiny trees and people for scale
    const tinyTree = (px, pz, s) => { const g = S.group(S.scene, [px, 0, pz]); g.scale.setScalar(s); S.mesh(new T.CylinderGeometry(0.02, 0.025, 0.25, 8), S.mat.matte("#8a6a4a"), { pos: [0, 0.12, 0], parent: g }); S.mesh(new T.SphereGeometry(0.16, 16, 12), S.mat.matte("#7fb069"), { pos: [0, 0.34, 0], parent: g }); };
    for (let i = 0; i < 16; i++) tinyTree(-PW / 2 + 0.4 + R() * (PW - 0.8), (R() < 0.5 ? -1 : 1) * (1.4 + R() * 1.3) - 0.3, 0.8 + R() * 0.6);
    const person = (px, pz, c) => { const g = S.group(S.scene, [px, 0, pz]); S.mesh(new T.CapsuleGeometry(0.035, 0.12, 4, 8), S.mat.matte(c), { pos: [0, 0.1, 0], parent: g }); S.mesh(new T.SphereGeometry(0.035, 10, 8), S.mat.matte("#3a3f4a"), { pos: [0, 0.22, 0], parent: g }); };
    [[-3.2, 0.9, "#4c6ef5"], [-2.9, 1.1, "#e8452c"], [0.4, 1.2, "#2a3346"], [2.1, 0.8, "#4c6ef5"], [3.9, 1.0, "#f2b134"], [4.2, 0.7, "#2a3346"]].forEach((a) => person(...a));

    // value tags that count up (redrawn only when the number changes)
    const tags = towers.map((tw, i) => {
      const c = K.canvas(640, 200), tex = K.tex(c); tex.wrapS = tex.wrapT = T.ClampToEdgeWrapping;
      const m = S.mesh(new T.PlaneGeometry(1.92, 0.6), new T.MeshBasicMaterial({ map: tex, transparent: true, toneMapped: false }), { shadow: false });
      let last = ""; const draw = (val) => { const s = "$" + Math.round(val).toLocaleString("en-US"); if (s === last) return; last = s; const q = c.getContext("2d"); q.clearRect(0, 0, 640, 200); q.fillStyle = tw.hero ? "#e8452c" : "#ffffff"; q.beginPath(); q.roundRect(10, 10, 620, 150, 75); q.fill(); q.beginPath(); q.moveTo(290, 158); q.lineTo(320, 196); q.lineTo(350, 158); q.fill(); q.fillStyle = tw.hero ? "#ffffff" : "#2a3346"; q.font = "800 96px Inter"; q.textAlign = "center"; q.fillText(s, 320, 120); tex.needsUpdate = true; };
      return { m, draw };
    });
    const cap = (n, word, t0, t1) => { const l = S.label(`${n}  ${word}`, { h: 1, font: "800 120px Inter", color: "#ffffff", bg: "#2a3346", radius: 999, pad: 52, lit: false }); l.userData = { t0, t1, size: l.userData.size }; return l; };
    const caps = [cap(1, C.steps[0], 0.3, 2.4), cap(2, C.steps[1], 2.5, 4.9), cap(3, C.steps[2], 5.0, 9)];

    return (t) => {
      let camH = 0;
      towers.forEach((tw, i) => {
        const [a, b] = times[i], per = (b - a) / tw.blocks.length; let h = 0;
        tw.blocks.forEach((m, j) => { const k = K.prog(t, a + j * per, a + j * per + 0.32); m.visible = k > 0; m.position.y = m.userData.y + (1 - K.ease.bounce(k)) * 2.5; if (k > 0) h = m.userData.y + (BH * m.userData.frac) / 2; });
        const shown = K.prog(t, a, b) * tw.v; const tg = tags[i]; const tf = Math.round(t * 30) / 30; tg.draw(K.lerp(0, tw.v, K.prog(tf, a, b))); // one value per frame (no ghosting under motion blur)
        const on = K.ease.back(K.prog(t, a + 0.1, a + 0.5)); const zoom = 1 + K.tw(t, 1.8, 7.4) * (S.portrait ? 1.1 : 0.7); tg.m.scale.setScalar(Math.max(0.001, on * zoom)); tg.m.position.set(tw.g.position.x, h + 0.35 + 0.3 * zoom, tw.g.position.z);
        if (i === 3) camH = h;
      });
      // camera cranes up with the hero tower
      const k = K.tw(t, 0, 8, K.ease.sine), rise = K.tw(t, 4.8, 7.4, K.ease.inOut);
      const tgt = [K.lerp(-2.6, 0.2, K.tw(t, 0.5, 5.2)), K.lerp(0.9, 4.6, rise), -0.6];
      const d = (S.portrait ? K.lerp(14, 31, K.tw(t, 1.8, 7.4)) : K.lerp(10, 18, K.tw(t, 1.8, 7.4)));
      const az = K.lerp(0.5, 0.28, k), el = K.lerp(0.2, 0.24, k);
      const cp = [tgt[0] + Math.sin(az) * Math.cos(el) * d, tgt[1] + Math.sin(el) * d, tgt[2] + Math.cos(az) * Math.cos(el) * d];
      S.cam(cp, tgt, { fov: 32, aperture: 0.1 });
      tags.forEach((tg) => tg.m.lookAt(cp[0], tg.m.position.y, cp[2]));
      caps.forEach((l) => { const a = K.ease.back(K.prog(t, l.userData.t0, l.userData.t0 + 0.4)), b = K.tw(t, l.userData.t1 - 0.25, l.userData.t1, K.ease.in); S.pin(l, 0, S.portrait ? 0.66 : 0.8, S.portrait ? 0.8 : 0.42, l.userData.size[0], a * (1 - b)); });
    };
  },

  sound(k) {
    k.bed("room", 0, 8, { vol: 0.7 });
    k.chords(0, 8, ["C4 E4 G4", "D4 F4 A4", "E4 G4 B4", "F4 A4 C5"], { bpm: 120, vol: 0.45, arp: true, arpVol: 0.22 });
    const times = [[0.6, 1.0, 1], [2.5, 3.3, 3], [3.3, 4.7, 7], [5.0, 7.0, 18]];
    times.forEach(([a, b, n], i) => { for (let j = 0; j < n; j++) { const t = a + j * ((b - a) / n) + 0.3; k.at(t, "wood", { vol: 0.35, pitch: 0.8 + (j / n) * 0.6 + i * 0.05 }); } k.at(b + 0.3, "coin", { vol: 0.3 }); });
    k.at(4.9, "rise", { dur: 2.2, vol: 0.25 }); k.at(7.3, "chime", { f: "C6", vol: 0.5 }); k.at(7.35, "sparkle", { vol: 0.45 });
  },
};
