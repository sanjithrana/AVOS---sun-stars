/* Cartoon Shorts engine: world builders. Simple shapes + painted textures = a toy-like, inked 3D world. Free from Anylancer.com. */
(function () {
const CS = window.CS = window.CS || {};
const { rand, shade } = CS;
const Wd = CS.world = {};

// texture-mapped box with constant texel density: tbox(w, h, d, mat, texSize metres per tile)
function boxUV(geo, w, h, d, s) {
  const uv = geo.attributes.uv, dims = [[d, h], [d, h], [w, d], [w, d], [w, h], [w, h]];
  for (let f = 0; f < 6; f++) for (let v = 0; v < 4; v++) { const i = f * 4 + v; uv.setXY(i, uv.getX(i) * dims[f][0] / s, uv.getY(i) * dims[f][1] / s); }
  uv.needsUpdate = true; return geo;
}
// box(w, h, d, mat, [x, y, z], parent, {tile, rot}) : y is the BOTTOM of the box
Wd.box = function (w, h, d, mat, p = [0, 0, 0], parent, o = {}) {
  const geo = new THREE.BoxGeometry(w, h, d); if (mat.map) boxUV(geo, w, h, d, o.tile || 2);
  const m = new THREE.Mesh(geo, mat); m.position.set(p[0], p[1] + h / 2, p[2]); if (o.rot) m.rotation.set(...o.rot);
  return CS.add(m, parent, o);
};
Wd.cyl = function (rt, rb, h, mat, p = [0, 0, 0], parent, o = {}) {
  const m = new THREE.Mesh(new THREE.CylinderGeometry(rt, rb, h, o.seg || 20), mat); m.position.set(p[0], p[1] + h / 2, p[2]); if (o.rot) m.rotation.set(...o.rot);
  return CS.add(m, parent, o);
};
Wd.ball = function (r, mat, p = [0, 0, 0], parent, o = {}) {
  const m = new THREE.Mesh(new THREE.SphereGeometry(r, o.seg || 24, Math.max(8, (o.seg || 24) / 2)), mat); m.position.set(...p); if (o.scale) m.scale.set(...o.scale);
  return CS.add(m, parent, o);
};
Wd.cone = function (r, h, mat, p = [0, 0, 0], parent, o = {}) {
  const m = new THREE.Mesh(new THREE.ConeGeometry(r, h, o.seg || 16), mat); m.position.set(p[0], p[1] + h / 2, p[2]); return CS.add(m, parent, o);
};
// prism roof along x: roof(w, d, h, mat, [x, y, z])
Wd.roof = function (w, d, h, mat, p = [0, 0, 0], parent, o = {}) {
  const s = new THREE.Shape(); s.moveTo(-d / 2 - .25, 0); s.lineTo(0, h); s.lineTo(d / 2 + .25, 0); s.lineTo(-d / 2 - .25, 0);
  const geo = new THREE.ExtrudeGeometry(s, { depth: w + .5, bevelEnabled: false }); geo.translate(0, 0, -(w + .5) / 2); geo.rotateY(Math.PI / 2);
  if (mat.map) { const uv = geo.attributes.uv; for (let i = 0; i < uv.count; i++) uv.setXY(i, uv.getX(i) / 2, uv.getY(i) / 2); }
  const m = new THREE.Mesh(geo, o.capMat ? [o.capMat, mat] : mat); m.position.set(...p); return CS.add(m, parent, o);
};
// ground(size, mat, {y}) flat plane
Wd.ground = function (size, mat, parent, o = {}) {
  const geo = new THREE.PlaneGeometry(size[0], size[1]); geo.rotateX(-Math.PI / 2);
  if (mat.map) { const uv = geo.attributes.uv; for (let i = 0; i < uv.count; i++) uv.setXY(i, uv.getX(i) * size[0] / (o.tile || 4), uv.getY(i) * size[1] / (o.tile || 4)); }
  const m = new THREE.Mesh(geo, mat); m.position.set(o.x || 0, o.y || 0, o.z || 0); m.receiveShadow = true; m.userData.ink = "world";
  (parent || CS.scene).add(m); return m;
};
// hill: half-buried squashed sphere
Wd.hill = function (r, color, p, parent, o = {}) { const sq = o.squash ?? .55; return Wd.ball(r, CS.mat(color, o.tex ? { tex: o.tex, texOpt: o.texOpt } : {}), [p[0], (p[1] || 0) - r * sq * (o.sink ?? .45), p[2]], parent, { scale: [1, sq, 1], seg: 28 }); };
Wd.mountain = function (r, h, color, p, parent, snow = true) {
  const g = new THREE.Group(); g.position.set(...p);
  Wd.cone(r, h, CS.mat(color), [0, 0, 0], g, { seg: 7 });
  if (snow) Wd.cone(r * .32, h * .32, CS.mat("#f6f8ff"), [0, h * .68 + .01, 0], g, { seg: 7 });
  return CS.add(g, parent);
};
// trees: tree(kind 'round'|'pine'|'cypress'|'gum'|'palm', height, [x,y,z], seed)
Wd.tree = function (kind, h, p, parent, seed = 1, o = {}) {
  const g = new THREE.Group(); g.position.set(...p); const leaf = o.leaf || (kind === "gum" ? "#7fae6a" : kind === "pine" ? "#3f8a52" : "#5cb04a"), trunk = CS.mat(o.trunk || (kind === "gum" ? "#e9e2d2" : "#7a5032"));
  const lm = CS.mat(leaf);
  if (kind === "pine") { Wd.cyl(.12 * h / 4, .18 * h / 4, h * .3, trunk, [0, 0, 0], g); for (let i = 0; i < 3; i++) Wd.cone(h * (.32 - i * .07), h * .42, lm, [0, h * (.22 + i * .2), 0], g, { seg: 9 }); }
  else if (kind === "cypress") { Wd.cyl(.1, .14, h * .2, trunk, [0, 0, 0], g); Wd.ball(h * .16, lm, [0, h * .55, 0], g, { scale: [1, 2.6, 1], seg: 14 }); }
  else if (kind === "palm") { Wd.cyl(.1, .16, h, trunk, [0, 0, 0], g); for (let i = 0; i < 6; i++) { const a = i / 6 * Math.PI * 2; const f = Wd.ball(h * .22, lm, [Math.cos(a) * h * .18, h * .98, Math.sin(a) * h * .18], g, { scale: [1, .18, .45], seg: 10 }); f.rotation.y = -a; f.rotation.z = -.4; } }
  else {
    const tr = kind === "gum" ? .13 : .16; Wd.cyl(tr * .7, tr, h * .55, trunk, [0, 0, 0], g);
    const n = kind === "gum" ? 4 : 3;
    for (let i = 0; i < n; i++) { const a = rand(seed + i) * Math.PI * 2, r = h * (kind === "gum" ? .2 : .26) * (.75 + rand(seed + i * 3) * .4); Wd.ball(r, lm, [Math.cos(a) * h * .14, h * (.62 + rand(seed + i * 7) * .22), Math.sin(a) * h * .14], g, { seg: 14, scale: kind === "gum" ? [1.3, .7, 1.3] : [1, .9, 1] }); }
  }
  return CS.add(g, parent);
};
// house({w, d, h, wall, roof, tex, door, windows, roofH}) at [x,y,z]
Wd.house = function (o, p, parent) {
  const g = new THREE.Group(); g.position.set(...p); if (o.rot) g.rotation.y = o.rot;
  const w = o.w || 4, d = o.d || 4, h = o.h || 3;
  Wd.box(w, h, d, CS.mat(o.wall || "#f2e4c8", { tex: o.tex || "plaster", texOpt: { color: o.wall || "#f2e4c8" } }), [0, 0, 0], g);
  Wd.roof(w, d, o.roofH || 1.6, CS.mat(o.roof || "#c4553a", { tex: "roof", texOpt: { color: o.roof || "#c4553a" } }), [0, h, 0], g, { capMat: CS.mat(o.wall || "#f2e4c8") });
  const fm = CS.mat(o.trim || "#6b4426");
  if (o.door !== false) Wd.box(.9, 1.8, .12, CS.mat(o.doorColor || "#8a4a2a", { tex: "planks", texOpt: { color: o.doorColor || "#8a4a2a", n: 4 } }), [0, 0, d / 2], g, { tile: 1 });
  for (let i = 0; i < (o.windows ?? 2); i++) { const x = (i % 2 ? 1 : -1) * w * .3; Wd.box(.8, .8, .1, CS.mat("#7fb6e0"), [x, h * .5, d / 2], g); Wd.box(1, .12, .16, fm, [x, h * .5 - .12, d / 2], g); }
  return CS.add(g, parent);
};
// fence from (x0,z0) to (x1,z1)
Wd.fence = function (a, b, parent, o = {}) {
  const g = new THREE.Group(), m = CS.mat(o.color || "#a77a4a", { tex: "wood", texOpt: { color: o.color || "#a77a4a" } });
  const dx = b[0] - a[0], dz = b[1] - a[1], L = Math.hypot(dx, dz), n = Math.max(2, Math.round(L / (o.gap || 1.6)));
  for (let i = 0; i <= n; i++) Wd.box(.14, o.h || 1.1, .14, m, [a[0] + dx * i / n, 0, a[1] + dz * i / n], g, { tile: 1 });
  for (const y of [.4, .85]) { const r = Wd.box(L, .1, .08, m, [(a[0] + b[0]) / 2, y * (o.h || 1.1), (a[1] + b[1]) / 2], g, { tile: 1 }); r.rotation.y = -Math.atan2(dz, dx); }
  return CS.add(g, parent);
};
// sign / board with text: textPanel(text, {w, h, bg, fg, font, size}) -> mesh facing +z (never mirrored)
Wd.textPanel = function (text, o = {}) {
  const w = o.w || 2, h = o.h || 1, pxw = 1024, pxh = Math.round(1024 * h / w);
  const tex = CS.paint.canvasTex(pxw, pxh, (g) => {
    g.fillStyle = o.bg || "#f4efe2"; g.fillRect(0, 0, pxw, pxh);
    if (o.border !== false) { g.strokeStyle = CS.INK; g.lineWidth = 18; g.strokeRect(9, 9, pxw - 18, pxh - 18); }
    if (o.paint) o.paint(g, pxw, pxh);
    g.fillStyle = o.fg || CS.INK; g.textAlign = "center"; g.textBaseline = "middle";
    const lines = String(text).split("\n"), fs = o.size || Math.min(pxh / lines.length * .62, pxw / Math.max(...lines.map(l => l.length)) * 1.6);
    g.font = (o.weight || 900) + " " + fs + "px " + (o.font || "Georgia, serif");
    lines.forEach((l, i) => g.fillText(l, pxw / 2, (o.y0 || pxh / 2) + (i - (lines.length - 1) / 2) * fs * 1.1));
  });
  const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshToonMaterial({ map: tex, gradientMap: CS.mat("#fff").gradientMap }));
  m.userData.ink = "world"; return m;
};
// painted cloud billboards around a centre: clouds(n, radius, height, seed)
Wd.clouds = function (n, R, y, seed = 3, parent, o = {}) {
  const tex = CS.fxTex("cloud"), list = [];
  for (let i = 0; i < n; i++) {
    const a = rand(seed + i) * Math.PI * 2, r = R * (.6 + rand(seed + i * 3) * .5), s = (o.size || 30) * (.7 + rand(seed + i * 5) * .6);
    const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false, fog: true, opacity: .95 }));
    sp.position.set((o.cx || 0) + Math.cos(a) * r, y + rand(seed + i * 9) * (o.dy || 20), (o.cz || 0) + Math.sin(a) * r); sp.scale.set(s, s * .55, 1);
    sp.userData.ink = "none"; sp.renderOrder = -5; (parent || CS.scene).add(sp); list.push(sp);
  }
  return list;
};
// water plane whose ripples drift: water(w, d, color, [x,y,z]) -> mesh; call water.flow(t) each frame
Wd.water = function (w, d, color, p, parent) {
  const tex = CS.paint.tex("water", { color }).clone(); tex.needsUpdate = true; tex.repeat.set(w / 6, d / 6);
  const geo = new THREE.PlaneGeometry(w, d); geo.rotateX(-Math.PI / 2);
  const m = new THREE.Mesh(geo, CS.mat(color, { tex })); m.position.set(...p); m.receiveShadow = true; m.userData.ink = "world";
  m.flow = t => { tex.offset.set(t * .03, t * .05); }; (parent || CS.scene).add(m); return m;
};
// scatter(builder(i, x, z), n, area:[x0,z0,x1,z1], seed, avoid(x,z)->bool)
Wd.scatter = function (n, area, seed, fn, avoid) {
  for (let i = 0, k = 0; i < n && k < n * 20; k++) {
    const x = area[0] + rand(seed + k * 2) * (area[2] - area[0]), z = area[1] + rand(seed + k * 2 + 1) * (area[3] - area[1]);
    if (avoid && avoid(x, z)) continue; fn(i, x, z); i++;
  }
};
// tufts(n, area:[x0,z0,x1,z1], {color, h, r}, seed, avoid) -> one InstancedMesh of little cones (wheat, grass, reeds)
Wd.tufts = function (n, area, o = {}, seed = 7, avoid, parent) {
  const geo = new THREE.ConeGeometry(o.r || .14, o.h || .9, 5); geo.translate(0, (o.h || .9) / 2, 0);
  const m = new THREE.InstancedMesh(geo, CS.mat(o.color || "#e2b23a"), n), M = new THREE.Matrix4(), q = new THREE.Quaternion(), s = new THREE.Vector3(), p = new THREE.Vector3(), e = new THREE.Euler();
  let i = 0, k = 0;
  while (i < n && k < n * 10) { k++; const x = area[0] + rand(seed + k * 2) * (area[2] - area[0]), z = area[1] + rand(seed + k * 2 + 1) * (area[3] - area[1]); if (avoid && avoid(x, z)) continue;
    const sc = .7 + rand(seed + k * 5) * .6; e.set((rand(k) - .5) * .25, rand(k * 3) * 6, (rand(k * 7) - .5) * .25); q.setFromEuler(e); s.set(sc, sc * (.8 + rand(k * 9) * .5), sc); p.set(x, 0, z); M.compose(p, q, s); m.setMatrixAt(i++, M); }
  m.count = i; m.castShadow = false; m.receiveShadow = true; m.userData.ink = o.ink || "none"; (parent || CS.scene).add(m); return m;
};
// truck({color}) -> group facing +x, wheels at y 0; .wheels to spin; .bed = height of the cargo bed floor
Wd.truck = function (o = {}, parent) {
  const g = new THREE.Group(), c = o.color || "#7d8a5a", m = CS.mat(c, { tex: "metal", texOpt: { color: c } }), dark = CS.mat("#2a2a2e"), wood = Wd.painted("planks", "#9a7048", { n: 4 });
  Wd.box(3.6, .25, 2.1, dark, [-1, .55, 0], g); Wd.box(3.6, .1, 2.1, wood, [-1, .8, 0], g, { tile: 1.5 });
  for (const z of [-1, 1]) Wd.box(3.6, .55, .1, wood, [-1, .9, z * 1.02], g, { tile: 1.5 }); Wd.box(.1, .55, 2.1, wood, [-2.78, .9, 0], g, { tile: 1.5 });
  Wd.box(1.3, 1.5, 2.0, m, [1.5, .7, 0], g); Wd.box(.95, .5, 1.6, CS.mat("#a8d0ea"), [1.5, 1.45, 0], g);
  Wd.box(1.3, .85, 1.6, m, [2.75, .7, 0], g); Wd.box(.1, .6, 1.4, CS.mat("#3a3a3a"), [3.42, .75, 0], g);
  for (const z of [-.6, .6]) Wd.ball(.13, CS.mat("#fff4b0", { emissive: "#ffe28a", emissiveI: .6 }), [3.45, 1.35, z], g);
  for (const z of [-1, 1]) Wd.box(1.2, .15, .55, m, [2.75, .95, z * .95], g);
  g.wheels = [];
  for (const [x, z] of [[2.7, -1.05], [2.7, 1.05], [-1.9, -1.05], [-1.9, 1.05], [-.9, -1.05], [-.9, 1.05]]) {
    const w = new THREE.Group(); w.position.set(x, .45, z); g.add(w);
    const tyre = new THREE.Mesh(new THREE.CylinderGeometry(.45, .45, .32, 20), dark); tyre.rotation.x = Math.PI / 2; w.add(tyre);
    const hub = new THREE.Mesh(new THREE.CylinderGeometry(.2, .2, .34, 8), CS.mat("#c9c2a8")); hub.rotation.x = Math.PI / 2; w.add(hub); g.wheels.push(w);
  }
  g.bed = .9; g.spin = d => g.wheels.forEach(w => w.rotation.z = -d / .45);
  return CS.add(g, parent);
};
// machine gun on a tripod; .pivot tilts it (pivot.rotation.z)
Wd.gun = function (o = {}, parent) {
  const g = new THREE.Group(), m = CS.mat("#3c4044"), wood = CS.mat("#7a4a2a");
  for (let i = 0; i < 3; i++) { const a = i / 3 * Math.PI * 2, l = new THREE.Mesh(new THREE.CylinderGeometry(.03, .04, .9, 6), m); l.position.set(Math.cos(a) * .22, .38, Math.sin(a) * .22); l.rotation.set(Math.sin(a) * .5, 0, -Math.cos(a) * .5); g.add(l); }
  const p = new THREE.Group(); p.position.y = .8; g.add(p); g.pivot = p;
  const barrel = new THREE.Mesh(new THREE.CylinderGeometry(.09, .09, 1.3, 12), m); barrel.rotation.z = Math.PI / 2; barrel.position.x = .45; p.add(barrel);
  const drum = new THREE.Mesh(new THREE.CylinderGeometry(.2, .2, .08, 16), m); drum.position.set(.1, .14, 0); p.add(drum);
  const stock = new THREE.Mesh(new THREE.BoxGeometry(.45, .14, .1), wood); stock.position.set(-.35, -.04, 0); p.add(stock);
  g.muzzle = new THREE.Object3D(); g.muzzle.position.set(1.15, 0, 0); p.add(g.muzzle);
  return CS.add(g, parent);
};
Wd.crate = function (s, p, parent, color = "#a8794a") { return Wd.box(s, s * .8, s * .8, Wd.painted("planks", color, { n: 4 }), p, parent, { tile: s }); };
Wd.hay = function (p, parent) { return Wd.cyl(.6, .6, 1, Wd.painted("wheat", "#e2b84a"), p, parent, { rot: [Math.PI / 2, 0, 0], seg: 18 }); };
// windmill (farm water pump): .rotor spins (rotor.rotation.z)
Wd.windmill = function (p, parent) {
  const g = new THREE.Group(); g.position.set(...p); const m = CS.mat("#8a8f96");
  for (const [x, z] of [[-.6, -.6], [.6, -.6], [-.6, .6], [.6, .6]]) { const l = new THREE.Mesh(new THREE.CylinderGeometry(.05, .07, 7.4, 6), m); l.position.set(x * .55, 3.6, z * .55); l.rotation.set(-z * .08, 0, x * .08); g.add(l); }
  const r = new THREE.Group(); r.position.set(0, 7.3, .5); g.add(r); g.rotor = r;
  for (let i = 0; i < 12; i++) { const b = new THREE.Mesh(new THREE.BoxGeometry(.28, 1.4, .04), CS.mat(i % 2 ? "#d8dcde" : "#c23b2f")); b.position.set(Math.cos(i / 12 * 6.283) * .8, Math.sin(i / 12 * 6.283) * .8, 0); b.rotation.z = i / 12 * 6.283 - Math.PI / 2; r.add(b); }
  const tail = new THREE.Mesh(new THREE.BoxGeometry(.06, .8, 1.4), CS.mat("#d8dcde")); tail.position.set(0, 7.3, -.9); g.add(tail);
  return CS.add(g, parent);
};
// picture frame on a wall: frame(w, h, texture or canvas, {color, depth}) -> group (picture faces +z); .pic is the picture mesh
Wd.frame = function (w, h, img, o = {}, parent) {
  const g = new THREE.Group(), m = CS.mat(o.color || "#c8962e"), b = o.border || .09, d = o.depth || .08;
  for (const [x, y, ww, hh] of [[0, h / 2 + b / 2, w + 2 * b, b], [0, -h / 2 - b / 2, w + 2 * b, b], [-w / 2 - b / 2, 0, b, h], [w / 2 + b / 2, 0, b, h]]) { const bar = new THREE.Mesh(new THREE.BoxGeometry(ww, hh, d), m); bar.position.set(x, y, d / 2); g.add(bar); }
  let tex = img; if (img && img.getContext) { tex = new THREE.CanvasTexture(img); tex.colorSpace = THREE.SRGBColorSpace; }
  const pic = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshToonMaterial({ map: tex, gradientMap: CS.mat("#fff").gradientMap })); pic.position.z = d * .3; g.add(pic); g.pic = pic;
  g.setImage = c => { let t2 = c; if (c && c.getContext) { t2 = c._tex || (c._tex = new THREE.CanvasTexture(c)); t2.colorSpace = THREE.SRGBColorSpace; } if (pic.material.map !== t2) { pic.material.map = t2; pic.material.needsUpdate = true; } };
  return CS.add(g, parent);
};
// street lamp with a glowing globe
Wd.lamp = function (p, parent, o = {}) {
  const g = new THREE.Group(); g.position.set(...p); const m = CS.mat(o.color || "#2c3a3a");
  Wd.cyl(.08, .12, 3.6, m, [0, 0, 0], g); Wd.cyl(.22, .26, .3, m, [0, 0, 0], g); Wd.box(.5, .08, .5, m, [0, 3.55, 0], g);
  g.globe = Wd.ball(.26, CS.mat("#fff2b8", { emissive: "#ffd870", emissiveI: o.on === false ? 0 : 1 }), [0, 3.9, 0], g); Wd.cone(.3, .25, m, [0, 4.12, 0], g, { seg: 8 });
  return CS.add(g, parent);
};
// wall clock facing +z: clock(r) -> group with .set(hours) (hands turn)
Wd.clock = function (r, p, parent) {
  const g = new THREE.Group(); g.position.set(...p);
  const face = CS.paint.canvasTex(256, 256, (c) => { c.fillStyle = "#f6f1e4"; c.beginPath(); c.arc(128, 128, 124, 0, 7); c.fill(); c.strokeStyle = CS.INK; c.lineWidth = 10; c.stroke(); c.fillStyle = CS.INK; for (let i = 0; i < 12; i++) { const a = i / 12 * Math.PI * 2; c.beginPath(); c.arc(128 + Math.sin(a) * 96, 128 - Math.cos(a) * 96, i % 3 ? 5 : 9, 0, 7); c.fill(); } });
  const disc = new THREE.Mesh(new THREE.CylinderGeometry(r, r, .08, 32), [CS.mat("#8a5a33"), new THREE.MeshToonMaterial({ map: face, gradientMap: CS.mat("#fff").gradientMap }), CS.mat("#8a5a33")]); disc.rotation.x = Math.PI / 2; g.add(disc);
  const mk = (l, w) => { const h = new THREE.Group(); h.position.z = .06; const b = new THREE.Mesh(new THREE.BoxGeometry(w, l, .02), CS.mat(CS.INK)); b.position.y = l / 2; h.add(b); g.add(h); return h; };
  const hh = mk(r * .5, r * .09), mh = mk(r * .78, r * .06);
  g.set = hours => { hh.rotation.z = -hours / 12 * Math.PI * 2; mh.rotation.z = -hours * Math.PI * 2; };
  return CS.add(g, parent);
};
// flag on a pole: flag(drawFn(g, w, h) or "stars"|"union"|"#colour", {pole, w, h}) -> group; call .wave(t) each frame; .cloth.position.y raises it
Wd.flagTex = function (kind) {
  return CS.paint.canvasTex(512, 320, (g, w, h) => {
    if (typeof kind === "function") return kind(g, w, h);
    if (kind === "stars") { for (let i = 0; i < 13; i++) { g.fillStyle = i % 2 ? "#ffffff" : "#c8323a"; g.fillRect(0, i * h / 13, w, h / 13 + 1); } g.fillStyle = "#2a3a7a"; g.fillRect(0, 0, w * .42, h * 7 / 13); g.fillStyle = "#fff"; for (let r = 0; r < 5; r++) for (let c = 0; c < 6; c++) { g.beginPath(); g.arc(18 + c * 34 + (r % 2) * 16, 18 + r * 32, 7, 0, 7); g.fill(); } }
    else if (kind === "union") { g.fillStyle = "#24387a"; g.fillRect(0, 0, w, h); g.strokeStyle = "#fff"; g.lineWidth = 60; g.beginPath(); g.moveTo(0, 0); g.lineTo(w, h); g.moveTo(w, 0); g.lineTo(0, h); g.stroke(); g.strokeStyle = "#c8323a"; g.lineWidth = 22; g.stroke(); g.fillStyle = "#fff"; g.fillRect(w / 2 - 50, 0, 100, h); g.fillRect(0, h / 2 - 50, w, 100); g.fillStyle = "#c8323a"; g.fillRect(w / 2 - 30, 0, 60, h); g.fillRect(0, h / 2 - 30, w, 60); }
    else { g.fillStyle = kind; g.fillRect(0, 0, w, h); }
  });
};
Wd.flag = function (kind, p, parent, o = {}) {
  const g = new THREE.Group(); g.position.set(...p); const H = o.pole || 4.5, fw = o.w || 1.6, fh = o.h || 1;
  Wd.cyl(.05, .06, H, CS.mat("#e8e2d0"), [0, 0, 0], g); Wd.ball(.1, CS.mat("#e8c048"), [0, H + .06, 0], g);
  const geo = new THREE.PlaneGeometry(fw, fh, 16, 6); geo.translate(fw / 2, -fh / 2, 0); const base = geo.attributes.position.array.slice();
  const cloth = new THREE.Mesh(geo, new THREE.MeshToonMaterial({ map: Wd.flagTex(kind), side: THREE.DoubleSide, gradientMap: CS.mat("#fff").gradientMap }));
  cloth.position.set(.05, H, 0); cloth.userData.ink = "world"; g.add(cloth); g.cloth = cloth; g.top = H;
  g.wave = (t, amp = 1) => { const a = geo.attributes.position.array; for (let i = 0; i < a.length; i += 3) { const x = base[i], k = x / fw; a[i + 2] = Math.sin(x * 3.2 - t * 7) * .14 * k * amp; a[i + 1] = base[i + 1] + Math.sin(x * 2 - t * 5) * .05 * k * amp; } geo.attributes.position.needsUpdate = true; geo.computeVertexNormals(); };
  return CS.add(g, parent);
};
// field cannon on a wooden carriage, barrel along +x; .barrel tilts (barrel.rotation.z)
Wd.cannon = function (p, parent, o = {}) {
  const g = new THREE.Group(); g.position.set(...p); const wood = Wd.painted("wood", "#7a4a2a"), metal = CS.mat(o.color || "#3a3e42");
  Wd.box(1.6, .3, .5, wood, [-.3, .45, 0], g, { tile: 1 });
  for (const z of [-.42, .42]) { const wh = new THREE.Mesh(new THREE.CylinderGeometry(.5, .5, .1, 14), wood); wh.rotation.x = Math.PI / 2; wh.position.set(.1, .5, z); g.add(wh); const hb = new THREE.Mesh(new THREE.CylinderGeometry(.1, .1, .14, 8), metal); hb.rotation.x = Math.PI / 2; hb.position.set(.1, .5, z); g.add(hb); }
  const b = new THREE.Group(); b.position.set(.1, .82, 0); g.add(b); g.barrel = b;
  const tube = new THREE.Mesh(new THREE.CylinderGeometry(.14, .2, 1.7, 14), metal); tube.rotation.z = -Math.PI / 2; tube.position.x = .55; b.add(tube);
  const lip = new THREE.Mesh(new THREE.TorusGeometry(.15, .04, 6, 14), metal); lip.rotation.y = Math.PI / 2; lip.position.x = 1.4; b.add(lip);
  g.mouth = new THREE.Object3D(); g.mouth.position.set(1.45, 0, 0); b.add(g.mouth);
  return CS.add(g, parent);
};
// sailing warship, bow along +x: ship({hull, sail, flag}) -> group (float it with .bob(t))
Wd.ship = function (o = {}, parent) {
  const g = new THREE.Group(), L = o.L || 14, B = o.B || 3.6, Hh = o.H || 2.4;
  const sh = new THREE.Shape(); sh.moveTo(-L / 2, -B / 2); sh.lineTo(L * .25, -B / 2); sh.quadraticCurveTo(L * .45, -B * .35, L / 2, 0); sh.quadraticCurveTo(L * .45, B * .35, L * .25, B / 2); sh.lineTo(-L / 2, B / 2); sh.lineTo(-L / 2, -B / 2);
  const geo = new THREE.ExtrudeGeometry(sh, { depth: Hh, bevelEnabled: false }); geo.rotateX(-Math.PI / 2);
  const hull = new THREE.Mesh(geo, [CS.mat("#c8a46a"), CS.mat(o.hull || "#3a2a22", { tex: "planks", texOpt: { color: o.hull || "#3a2a22", n: 5 } })]); hull.position.y = -.8; g.add(hull);
  const band = new THREE.Mesh(new THREE.ExtrudeGeometry(sh, { depth: .35, bevelEnabled: false }), CS.mat(o.band || "#e8c048")); band.geometry.rotateX(-Math.PI / 2); band.scale.set(1.004, 1, 1.01); band.position.y = Hh - 1.35; g.add(band);
  for (let i = 0; i < 6; i++) for (const z of [-1, 1]) { const port = new THREE.Mesh(new THREE.BoxGeometry(.4, .35, .05), CS.mat("#151515")); port.position.set(-L * .38 + i * L * .12, Hh - 1.75, z * (B / 2 + .02)); g.add(port); }
  const sails = [];
  for (const [x, h] of [[-L * .28, 9], [0, 11], [L * .26, 9.5]]) {
    const mast = new THREE.Mesh(new THREE.CylinderGeometry(.12, .16, h, 8), CS.mat("#6a4a2a")); mast.position.set(x, Hh - .8 + h / 2, 0); g.add(mast);
    for (const [y, sw] of [[.45, 1], [.75, .8]]) { const sg = new THREE.PlaneGeometry(B * 1.5 * sw, h * .26, 6, 3); const a = sg.attributes.position; for (let i = 0; i < a.count; i++) a.setZ(i, (1 - (a.getX(i) / (B * .75 * sw)) ** 2) * .35); sg.computeVertexNormals();
      const sail = new THREE.Mesh(sg, CS.mat(o.sail || "#f4efe2", { side: THREE.DoubleSide })); sail.rotation.y = Math.PI / 2; sail.position.set(x + .25, Hh - .8 + h * y, 0); g.add(sail); sails.push(sail); }
  }
  if (o.flag) { const f = Wd.flag(o.flag, [-L / 2 + .3, Hh - .8, 0], g, { pole: 3, w: 1.6, h: 1 }); g.flagObj = f; }
  g.bob = t => { g.position.y = Math.sin(t * 1.3 + (o.seed || 0)) * .12; g.rotation.x = Math.sin(t * 1.1 + (o.seed || 0)) * .025; if (g.flagObj) g.flagObj.wave(t); };
  return CS.add(g, parent);
};
// easy colour helper for materials with a painted texture
Wd.painted = (tex, color, o = {}) => CS.mat(color, { tex, texOpt: Object.assign({ color }, o) });
})();
