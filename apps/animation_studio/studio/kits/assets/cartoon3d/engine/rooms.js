/* Cartoon Shorts engine: rich places. Rooms with wainscoting and arched windows, chalkboards, globes, rocks,
   a pendulum clock, a satellite, a throne. Rich places + simple characters = the look. Free from Anylancer.com. */
(function () {
const CS = window.CS = window.CS || {};
const { rand, shade } = CS;
const Wd = CS.world;
const P = CS.paint.PAINTERS;

// ---------- extra painted textures ----------
P.checker = function (g, w, h, o) { const a = o.color || "#e9dfc8", b = o.color2 || "#7a6a58", n = o.n || 4, s = w / n;
  for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) { g.fillStyle = (i + j) % 2 ? b : a; g.fillRect(i * s, j * s, s, s); }
  g.globalAlpha = .12; for (let i = 0; i < 300; i++) { g.fillStyle = rand(i) > .5 ? "#fff" : "#000"; g.fillRect(rand(i * 3) * w, rand(i * 3 + 1) * h, 6, 6); } g.globalAlpha = 1; };
P.tiles = function (g, w, h, o) { const c = o.color || "#e8eef2", n = o.n || 4, s = w / n; g.fillStyle = c; g.fillRect(0, 0, w, h);
  for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) { g.fillStyle = shade(c, (rand(i * 7 + j) - .5) * .06); g.fillRect(i * s + 3, j * s + 3, s - 6, s - 6); } };
P.panels = function (g, w, h, o) { const c = o.color || "#8a5a33"; g.fillStyle = c; g.fillRect(0, 0, w, h);   // wainscot / wooden panels
  const n = o.n || 2, s = w / n; g.strokeStyle = shade(c, -.28); g.lineWidth = 8;
  for (let i = 0; i < n; i++) { g.strokeRect(i * s + s * .12, h * .14, s * .76, h * .72); g.fillStyle = shade(c, .06); g.fillRect(i * s + s * .12 + 6, h * .14 + 6, s * .76 - 12, h * .72 - 12); }
  g.fillStyle = shade(c, -.2); g.fillRect(0, 0, w, h * .06); };
P.stripes = function (g, w, h, o) { const c = o.color || "#efe1c3", n = o.n || 8; g.fillStyle = c; g.fillRect(0, 0, w, h); g.fillStyle = shade(c, -.06); for (let i = 0; i < n; i++) g.fillRect(i * w / n, 0, w / n / 2, h); };
P.carpet = function (g, w, h, o) { const c = o.color || "#a8323e"; g.fillStyle = c; g.fillRect(0, 0, w, h); g.strokeStyle = o.trim || "#e8c048"; g.lineWidth = 14; g.strokeRect(24, -10, w - 48, h + 20); g.globalAlpha = .1; for (let i = 0; i < 200; i++) { g.fillStyle = "#000"; g.fillRect(rand(i) * w, rand(i + 9) * h, 5, 5); } g.globalAlpha = 1; };
P.panelsBlue = (g, w, h, o) => P.panels(g, w, h, Object.assign({ color: "#4f6f8f" }, o));

// ---------- room ----------
/* room({w, d, h, wall, wallTex, wain, wainH, floor, floorTex, floor2, windows:[x…], winY, winW, winH, door: x | null, sconces:[x…],
         sky, sides: true}, parent) -> group. Back wall at z = -d/2, floor at y 0, open towards +z (the camera side).
   Returns {group, back: z of the back wall, sign(text, x, y), frame(...)} */
Wd.room = function (o = {}, parent) {
  const G = new THREE.Group(); (parent || CS.scene).add(G);
  const w = o.w || 10, d = o.d || 8, h = o.h || 4.4, zb = -d / 2;
  const wall = Wd.painted(o.wallTex || "stripes", o.wall || "#efe1c3", o.wallOpt || {});
  const wain = Wd.painted("panels", o.wain || "#8a5a33", { n: 2 });
  const floor = Wd.painted(o.floorTex || "checker", o.floor || "#e9dfc8", Object.assign({ color2: o.floor2 || "#7a6a58" }, o.floorOpt || {}));
  Wd.ground([w + 8, d + 10], floor, G, { tile: o.floorTile || 2.4, z: 1 });
  const wh = o.wainH ?? 1.15;
  Wd.box(w + 8, h, .3, wall, [0, 0, zb - .15], G, { tile: o.wallTile || 2.5 });
  if (wh) { Wd.box(w + 8, wh, .12, wain, [0, 0, zb + .06], G, { tile: 2.2 }); Wd.box(w + 8, .1, .22, CS.mat(shade(o.wain || "#8a5a33", -.25)), [0, wh, zb + .08], G); }
  Wd.box(w + 8, .22, .3, CS.mat(o.trim || "#f6efe0"), [0, h - .22, zb + .05], G);   // crown moulding
  if (o.sides !== false) for (const s of [-1, 1]) {
    Wd.box(.3, h, d + 6, wall, [s * (w / 2 + .15), 0, zb + (d + 6) / 2], G, { tile: o.wallTile || 2.5 });
    if (wh) Wd.box(.12, wh, d + 6, wain, [s * (w / 2 - .06), 0, zb + (d + 6) / 2], G, { tile: 2.2 });
  }
  for (const x of o.windows || []) Wd.archWindow([x, o.winY ?? 1.5, zb + .02], { w: o.winW || 1.5, h: o.winH || 2.3, sky: o.sky, frame: o.winFrame }, G);
  if (o.door != null) Wd.door([o.door, 0, zb + .02], { color: o.doorColor, sign: o.doorSign }, G);
  for (const x of o.sconces || []) Wd.sconce([x, 2.6, zb + .05], G);
  return { group: G, back: zb + .03, w, d, h };
};
// arched window (the sky is bright and unlit, so it reads as daylight): archWindow([x,y,z], {w, h, sky, frame})
Wd.archWindow = function (p, o = {}, parent) {
  const G = new THREE.Group(); G.position.set(...p); const w = o.w || 1.5, h = o.h || 2.3, r = w / 2;
  const shape = (pad) => { const s = new THREE.Shape(); s.moveTo(-r - pad, -pad); s.lineTo(r + pad, -pad); s.lineTo(r + pad, h - r); s.absarc(0, h - r, r + pad, 0, Math.PI, false); s.lineTo(-r - pad, -pad); return s; };
  const fr = new THREE.Mesh(new THREE.ExtrudeGeometry(shape(.14), { depth: .08, bevelEnabled: false }), CS.mat(o.frame || "#f4ecd8")); G.add(fr);
  const skyTex = CS.paint.canvasTex(256, 384, (g) => { const gr = g.createLinearGradient(0, 0, 0, 384); gr.addColorStop(0, o.sky || "#7ec0ff"); gr.addColorStop(1, o.sky2 || "#d8efff"); g.fillStyle = gr; g.fillRect(0, 0, 256, 384);
    g.fillStyle = "rgba(255,255,255,.9)"; for (const [x, y, s] of [[60, 120, 40], [100, 110, 50], [150, 125, 36], [190, 240, 30], [220, 232, 38]]) { g.beginPath(); g.arc(x, y, s, 0, 7); g.fill(); } });
  const pane = new THREE.Mesh(new THREE.ShapeGeometry(shape(0)), new THREE.MeshBasicMaterial({ map: skyTex, fog: false }));
  const uv = pane.geometry.attributes.uv, pos = pane.geometry.attributes.position; for (let i = 0; i < uv.count; i++) uv.setXY(i, (pos.getX(i) + r) / w, pos.getY(i) / h);
  pane.position.z = .1; pane.userData.ink = "world"; G.add(pane);
  const mm = CS.mat(o.frame || "#f4ecd8"); Wd.box(.08, h - .05, .06, mm, [0, 0, .12], G); Wd.box(w, .07, .06, mm, [0, h * .45, .12], G);
  Wd.box(w + .5, .12, .3, mm, [0, -.2, .1], G);   // sill
  return CS.add(G, parent);
};
Wd.door = function (p, o = {}, parent) {
  const G = new THREE.Group(); G.position.set(...p); const c = o.color || "#7a4a2a";
  Wd.box(1.5, 2.6, .1, CS.mat("#f4ecd8"), [0, 0, 0], G);
  for (const s of [-1, 1]) Wd.box(.66, 2.45, .12, Wd.painted("panels", c, { n: 1 }), [s * .34, 0, .04], G, { tile: 2.5 });
  for (const s of [-1, 1]) Wd.ball(.05, CS.mat("#e8c048"), [s * .1, 1.2, .14], G);
  if (o.sign) { const t = Wd.textPanel(o.sign, { w: 1.1, h: .34, bg: "#f4ecd8", size: 130 }); t.position.set(0, 2.95, .03); G.add(t); }
  return CS.add(G, parent);
};
Wd.sconce = function (p, parent) {
  const G = new THREE.Group(); G.position.set(...p);
  Wd.box(.12, .3, .06, CS.mat("#c8962e"), [0, -.15, 0], G); Wd.box(.36, .05, .2, CS.mat("#c8962e"), [0, -.05, .08], G);
  for (const s of [-1, 1]) { Wd.cyl(.035, .035, .22, CS.mat("#f8f2e2"), [s * .14, 0, .1], G); Wd.ball(.045, CS.mat("#ffd46a", { emissive: "#ffb030", emissiveI: 1.2 }), [s * .14, .27, .1], G, { scale: [1, 1.5, 1] }); }
  return CS.add(G, parent);
};

// ---------- chalkboard: board(text, {w, h, bg, fg, frame}) -> group; .write(text, k 0..1) reveals text as if written ----------
Wd.board = function (text, o = {}, parent) {
  const G = new THREE.Group(); const w = o.w || 2.6, h = o.h || 1.7;
  Wd.box(w + .24, h + .24, .1, CS.mat(o.frame || "#8a5a33", { tex: "wood", texOpt: { color: o.frame || "#8a5a33" } }), [0, -.12, -.06], G);
  Wd.box(w * .9, .06, .18, CS.mat(o.frame || "#8a5a33"), [0, -.18, .02], G);
  const pxw = 1024, pxh = Math.round(1024 * h / w), c = document.createElement("canvas"); c.width = pxw; c.height = pxh;
  const tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace;
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshToonMaterial({ map: tex, gradientMap: CS.mat("#fff").gradientMap })); mesh.position.set(0, h / 2 - .12, .01); mesh.userData.ink = "world"; G.add(mesh);
  let key = null;
  G.write = function (txt, k = 1) {
    const total = txt.replace(/\n/g, "").length, show = Math.round(total * CS.clamp(k)), id = txt + "|" + show; if (id === key) return G; key = id;
    const g = c.getContext("2d"); g.fillStyle = o.bg || "#2f5a48"; g.fillRect(0, 0, pxw, pxh);
    g.globalAlpha = .07; for (let i = 0; i < 160; i++) { g.fillStyle = "#fff"; g.beginPath(); g.ellipse(rand(i) * pxw, rand(i + 7) * pxh, 30 + rand(i + 3) * 60, 8, rand(i + 5) * 3, 0, 7); g.fill(); } g.globalAlpha = 1;
    const lines = txt.split("\n"), fs = o.size || Math.min(pxh / lines.length * .5, pxw / Math.max(...lines.map(l => l.length)) * 1.5);
    g.font = "700 " + fs + "px " + (o.font || CS.FONT); g.textAlign = "center"; g.textBaseline = "middle"; g.fillStyle = o.fg || "#f6f3e8";
    let left = show; lines.forEach((l, i) => { const part = l.slice(0, Math.max(0, left)); left -= l.length; const y = pxh / 2 + (i - (lines.length - 1) / 2) * fs * 1.25;
      if (o.underline && i === 0 && part.length === l.length) { const tw = g.measureText(l).width; g.fillRect(pxw / 2 - tw / 2, y + fs * .55, tw, 8); }
      g.textAlign = "left"; const tw = g.measureText(l).width; g.fillStyle = i === 0 && o.head ? o.head : (o.fg || "#f6f3e8"); g.fillText(part, pxw / 2 - tw / 2, y); });
    tex.needsUpdate = true; return G;
  };
  G.write(text, 1);
  return CS.add(G, parent);
};

// ---------- globe: globe(r, {ocean, land, lines: 24}) -> group; .spin.rotation.y turns it; meridians every 15° ----------
Wd.globe = function (r = 1, o = {}, parent) {
  const G = new THREE.Group(), spin = new THREE.Group(); G.add(spin); G.spin = spin;
  const tex = CS.paint.canvasTex(1024, 512, (g) => {
    g.fillStyle = o.ocean || "#3f8fd8"; g.fillRect(0, 0, 1024, 512);
    g.fillStyle = o.land || "#6cbf4a"; g.strokeStyle = shade(o.land || "#6cbf4a", -.3); g.lineWidth = 5;
    const blobs = [[150, 150, 120, 70], [210, 330, 60, 100], [520, 150, 70, 50], [540, 300, 75, 110], [720, 160, 170, 80], [820, 360, 60, 40], [400, 120, 30, 30]];
    for (const [x, y, rx, ry] of blobs) { g.beginPath(); for (let i = 0; i <= 24; i++) { const a = i / 24 * Math.PI * 2, k = 1 + (rand(x + i) - .5) * .35; const px = x + Math.cos(a) * rx * k, py = y + Math.sin(a) * ry * k; i ? g.lineTo(px, py) : g.moveTo(px, py); } g.closePath(); g.fill(); g.stroke(); }
    g.fillStyle = "#f4f8ff"; g.fillRect(0, 0, 1024, 26); g.fillRect(0, 486, 1024, 26);
    if (o.lines !== 0) { g.strokeStyle = "rgba(255,255,255,.7)"; g.lineWidth = 3; const n = o.lines || 24; for (let i = 0; i < n; i++) { const x = i * 1024 / n; g.beginPath(); g.moveTo(x, 0); g.lineTo(x, 512); g.stroke(); } }
  });
  Wd.ball(r, CS.mat("#ffffff", { tex }), [0, 0, 0], spin, { seg: 48 });
  if (o.wedge) {   // one highlighted 15° slice
    const geo = new THREE.SphereGeometry(r * 1.004, 12, 24, 0, Math.PI / 12, 0, Math.PI);
    G.wedge = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ color: o.wedge, transparent: true, opacity: .55, depthWrite: false })); G.wedge.userData.ink = "none"; spin.add(G.wedge);
  }
  return CS.add(G, parent);
};

// ---------- sea rocks: rocks(n, [x0,z0,x1,z1], {color, size}, seed) ----------
Wd.rocks = function (n, area, o = {}, seed = 3, parent) {
  const G = new THREE.Group(), m = CS.mat(o.color || "#6b6a72");
  for (let i = 0; i < n; i++) { const x = area[0] + rand(seed + i) * (area[2] - area[0]), z = area[1] + rand(seed + i * 5) * (area[3] - area[1]), s = (o.size || 2) * (.5 + rand(seed + i * 9));
    const r = new THREE.Mesh(new THREE.DodecahedronGeometry(s, 0), m); r.position.set(x, s * .25, z); r.rotation.set(rand(i) * 3, rand(i + 1) * 3, 0); r.scale.y = .8 + rand(i * 2) * .6; G.add(r); }
  return CS.add(G, parent);
};

// ---------- longcase clock with a swinging pendulum: tallClock({color}) -> group; .swing(angle) sets the pendulum; .face.set(hours) ----------
Wd.tallClock = function (o = {}, parent) {
  const G = new THREE.Group(), c = o.color || "#7a4a2a", m = CS.mat(c, { tex: "wood", texOpt: { color: c } });
  Wd.box(.9, .35, .55, m, [0, 0, 0], G); Wd.box(.7, 1.5, .45, m, [0, .35, 0], G); Wd.box(.95, .9, .55, m, [0, 1.85, 0], G); Wd.roof(.95, .55, .3, CS.mat(shade(c, -.15)), [0, 2.75, 0], G);
  Wd.box(.46, 1.2, .02, CS.mat("#2a1e1a"), [0, .5, .23], G);
  G.face = Wd.clock(.32, [0, 2.3, .28], G);
  const pend = new THREE.Group(); pend.position.set(0, 1.62, .25); G.add(pend);
  Wd.box(.03, .95, .02, CS.mat("#e8c048"), [0, -.95, 0], pend); Wd.cyl(.13, .13, .03, CS.mat("#e8c048"), [0, -1.0, 0], pend, { rot: [Math.PI / 2, 0, 0] });
  G.swing = a => { pend.rotation.z = a; }; G.pend = pend;
  return CS.add(G, parent);
};

// ---------- satellite: satellite() -> group; panels along x ----------
Wd.satellite = function (o = {}, parent) {
  const G = new THREE.Group();
  Wd.box(1, 1, 1, CS.mat(o.body || "#e8c048", { tex: "metal", texOpt: { color: o.body || "#e8c048" } }), [0, -.5, 0], G);
  const pm = CS.mat("#2f4f9a", { tex: CS.paint.canvasTex(256, 128, (g) => { g.fillStyle = "#2f4f9a"; g.fillRect(0, 0, 256, 128); g.strokeStyle = "#9ec0ff"; g.lineWidth = 4; for (let i = 0; i <= 8; i++) { g.beginPath(); g.moveTo(i * 32, 0); g.lineTo(i * 32, 128); g.stroke(); } for (let j = 0; j <= 4; j++) { g.beginPath(); g.moveTo(0, j * 32); g.lineTo(256, j * 32); g.stroke(); } }) });
  for (const s of [-1, 1]) { Wd.box(.8, .08, .08, CS.mat("#b8b8c0"), [s * .9, -.04, 0], G); Wd.box(2.2, .06, 1, pm, [s * 2.4, -.03, 0], G); }
  Wd.cone(.35, .4, CS.mat("#e8e8ee"), [0, .5, 0], G);
  return CS.add(G, parent);
};

// ---------- throne ----------
Wd.throne = function (p, o = {}, parent) {
  const G = new THREE.Group(); G.position.set(...p); const c = o.color || "#b8862e", red = CS.mat(o.cushion || "#b8323e");
  Wd.box(1.6, .6, 1.2, CS.mat(c), [0, 0, 0], G); Wd.box(1.3, .18, 1, red, [0, .6, .05], G);
  Wd.box(1.6, 2.6, .25, CS.mat(c), [0, 0, -.55], G); Wd.box(1.2, 1.7, .05, red, [0, .85, -.42], G);
  for (const s of [-1, 1]) { Wd.box(.2, .5, 1.2, CS.mat(c), [s * .8, .6, 0], G); Wd.ball(.16, CS.mat("#f2c230"), [s * .7, 2.7, -.55], G); }
  return CS.add(G, parent);
};
})();

/* ---------- shot list: fast cuts made easy ----------
   const plan = CS.shots(T, [
     { at: "In",        set: "street", light: "day",   from: {p:[0,1.6,6], l:[0,1.4,0], fov:40}, to: {p:[0,1.5,4.5]}, blur: .1 },
     { at: "laughed", after: 15, set: "hall", light: "indoor", from: {...}, to: {...}, shake: .05 },
   ]);
   frame(t)  : const s = plan.apply(t);   // shows the set, sets light, camera (from → to over the shot), lens; returns {i, k, shot, t0, t1}
   sound(A)  : plan.cutSounds(A, ["whoosh", "swish"], .5)   // a sound on every cut
   `at` = the words the shot starts on (it cuts .06 s before them) or a time in seconds. `to` keys you leave out stay as in `from`.
   ease: smooth (default) | out | in | lin | inOut. focus: metres or [x,y,z]. roll in degrees. */
CS.shots = function (T, list) {
  const shots = list.map(s => Object.assign({}, s, { t0: typeof s.at === "number" ? s.at : Math.max(0, T.w(s.at, s.after || 0) - (s.lead ?? .06)) }));
  shots[0].t0 = 0;
  shots.forEach((s, i) => { s.t1 = i + 1 < shots.length ? shots[i + 1].t0 : 1e9; s.i = i; });
  const plan = { shots,
    find(t) { let i = 0; while (i < shots.length - 1 && shots[i + 1].t0 <= t) i++; return shots[i]; },
    apply(t) {
      const s = plan.find(t), dur = Math.min(s.t1, T.duration + 2) - s.t0, k = CS.clamp((t - s.t0) / Math.max(dur, .01)), e = (CS.ease[s.ease || "smooth"] || CS.ease.smooth)(k);
      if (s.set) CS.showSet(s.set);
      if (s.light) Array.isArray(s.light) ? CS.light(...s.light) : CS.light(s.light);
      const a = s.from, b = Object.assign({}, a, s.to || {}), L = (x, y) => x.map((v, j) => CS.lerp(v, y[j], e));
      const c = { p: L(a.p, b.p), l: L(a.l, b.l), fov: CS.lerp(a.fov || 40, b.fov || 40, e), roll: CS.lerp(a.roll || 0, b.roll || 0, e) };
      CS.cam(c, t, { creep: s.creep ?? .03, shake: s.shake ? CS.shake(t, s.shakeAt ?? s.t0, s.shakeDur || .3, s.shake) : [0, 0] });
      CS.lens({ focus: s.focus ?? CS.lerp(Math.hypot(a.p[0] - a.l[0], a.p[1] - a.l[1], a.p[2] - a.l[2]), Math.hypot(b.p[0] - b.l[0], b.p[1] - b.l[1], b.p[2] - b.l[2]), e), blur: s.blur ?? .12, flash: s.flash ? s.flash(t) : 0, flashColor: s.flashColor });
      if (s.shadow) CS.shadowAt(...s.shadow); else CS.shadowAt(c.l[0], c.l[2], 14);
      return { i: s.i, k, shot: s, t0: s.t0, t1: s.t1, local: t - s.t0 };
    },
    cutSounds(A, names = ["whoosh", "swish"], gain = .45) { shots.forEach((s, i) => { if (!i || s.cutSfx === false) return; const n = s.cutSfx || names[i % names.length]; A.sfx(n, s.t0 - (n === "whoosh" ? .22 : .04), s.cutGain ?? gain); }); },
  };
  return plan;
};
