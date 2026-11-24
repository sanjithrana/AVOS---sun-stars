/* Stickman Shorts engine: the stick people. A big white head with expressive eyes, a coloured shirt, thick ink stick
   arms and legs, round white hands and chunky shoes. Everything is drawn in code on a 2D canvas. Free from Anylancer.com. */
(function () {
const CS = window.CS = window.CS || {};
const INK = CS.INK = "#1f1a24";
const D = Math.PI / 180;

// ---------- small drawing helpers ----------
const fs = CS.fs = function (g, fill, lw = 8, stroke = INK) {
  if (fill) { g.fillStyle = fill; g.fill(); }
  if (lw) { g.lineWidth = lw; g.strokeStyle = stroke; g.lineJoin = "round"; g.lineCap = "round"; g.stroke(); }
};
CS.circle = function (g, x, y, r, fill, lw = 8) { g.beginPath(); g.arc(x, y, r, 0, Math.PI * 2); fs(g, fill, lw); };
CS.ell = function (g, x, y, rx, ry, rot, fill, lw = 8) { g.beginPath(); g.ellipse(x, y, Math.abs(rx), Math.abs(ry), rot || 0, 0, Math.PI * 2); fs(g, fill, lw); };
CS.rrect = function (g, x, y, w, h, r, fill, lw = 8) { g.beginPath(); g.roundRect(x, y, w, h, r); fs(g, fill, lw); };
CS.seg2 = function (g, x1, y1, x2, y2, lw = 14, col = INK) { g.beginPath(); g.moveTo(x1, y1); g.lineTo(x2, y2); g.lineWidth = lw; g.strokeStyle = col; g.lineCap = "round"; g.stroke(); };
CS.shadow = function (g, x, y, rx, a = .18) { g.save(); g.fillStyle = `rgba(30,20,40,${a})`; g.beginPath(); g.ellipse(x, y, rx, rx * .22, 0, 0, 7); g.fill(); g.restore(); };

// ---------- faces ----------
// eyes: open wide happy closed squint cry spiral angry sad x side ; mouth: smile grin o shout frown flat wavy smirk teeth tongue
CS.FACES = {
  neutral: { eyes: "open", mouth: "flat", brow: [0, 0] },
  happy: { eyes: "open", mouth: "smile", brow: [-4, 4] },
  joy: { eyes: "happy", mouth: "grin", brow: [-6, 8] },
  laugh: { eyes: "happy", mouth: "laugh", brow: [-6, 10] },
  shock: { eyes: "wide", mouth: "o", brow: [-10, 18] },
  scream: { eyes: "wide", mouth: "shout", brow: [-14, 22] },
  worried: { eyes: "open", mouth: "wavy", brow: [-16, 8] },
  sad: { eyes: "sad", mouth: "frown", brow: [-18, 6] },
  cry: { eyes: "cry", mouth: "shout", brow: [-18, 8] },
  sob: { eyes: "squint", mouth: "wavy", brow: [-18, 6], tears: true },
  angry: { eyes: "angry", mouth: "teeth", brow: [22, 0] },
  smug: { eyes: "half", mouth: "smirk", brow: [6, 2] },
  sick: { eyes: "half", mouth: "wavy", brow: [-10, 0], green: true },
  yuck: { eyes: "squint", mouth: "tongue", brow: [-8, 4], green: true },
  dizzy: { eyes: "spiral", mouth: "wavy", brow: [0, 6] },
  wow: { eyes: "wide", mouth: "grin", brow: [-8, 20] },
  curious: { eyes: "open", mouth: "smirk", brow: [-2, 12], look: .6 },
  think: { eyes: "open", mouth: "flat", brow: [-4, 10], lookY: -1, look: .5 },
  sleepy: { eyes: "closed", mouth: "flat", brow: [0, 0] },
  ko: { eyes: "x", mouth: "o", brow: [0, 0] },
  love: { eyes: "heart", mouth: "grin", brow: [-6, 10] },
};
function eye(g, x, y, s, kind, look, lookY, side, blink) {
  if (blink && ["open", "wide", "half", "sad", "angry"].includes(kind)) kind = "closed";
  g.lineCap = "round"; g.strokeStyle = INK;
  const rx = 23 * s, ry = 29 * s;
  if (kind === "happy") { g.lineWidth = 8 * s; g.beginPath(); g.arc(x, y + 10 * s, 18 * s, Math.PI * 1.15, Math.PI * 1.85); g.stroke(); return; }
  if (kind === "closed") { g.lineWidth = 8 * s; g.beginPath(); g.arc(x, y - 4 * s, 18 * s, Math.PI * .15, Math.PI * .85); g.stroke(); return; }
  if (kind === "squint" || kind === "cry") {   // > <  (or tightly shut)
    g.lineWidth = 8 * s; g.beginPath(); g.moveTo(x - 18 * s * side, y - 14 * s); g.lineTo(x + 12 * s * side, y); g.lineTo(x - 18 * s * side, y + 12 * s); g.stroke(); return;
  }
  if (kind === "x") { g.lineWidth = 8 * s; g.beginPath(); g.moveTo(x - 15 * s, y - 15 * s); g.lineTo(x + 15 * s, y + 15 * s); g.moveTo(x + 15 * s, y - 15 * s); g.lineTo(x - 15 * s, y + 15 * s); g.stroke(); return; }
  if (kind === "spiral") { g.lineWidth = 6 * s; g.beginPath(); for (let a = 0; a < 12; a += .2) { const r = a * 2.2 * s; g.lineTo(x + Math.cos(a * side) * r, y + Math.sin(a * side) * r); } g.stroke(); return; }
  if (kind === "heart") { g.save(); g.translate(x, y); g.scale(s, s); g.beginPath(); g.moveTo(0, 14); g.bezierCurveTo(-30, -6, -16, -30, 0, -14); g.bezierCurveTo(16, -30, 30, -6, 0, 14); g.restore(); fs(g, "#ff4f6d", 5 * s); return; }
  const big = kind === "wide" ? 1.18 : 1;
  CS.ell(g, x, y, rx * big, ry * big, 0, "#fff", 6 * s);
  const pr = (kind === "wide" ? 9 : 12.5) * s;
  const px = x + look * 9 * s, py = y + 3 * s + lookY * 10 * s;
  g.beginPath(); g.arc(px, py, pr, 0, 7); g.fillStyle = INK; g.fill();
  g.beginPath(); g.arc(px - pr * .35, py - pr * .4, pr * .32, 0, 7); g.fillStyle = "#fff"; g.fill();
  if (kind === "half" || kind === "sad" || kind === "angry") {     // eyelid
    g.save(); g.beginPath(); g.ellipse(x, y, rx * big + 2, ry * big + 2, 0, 0, 7); g.clip();
    g.beginPath();
    if (kind === "half") g.rect(x - 40 * s, y - 40 * s, 80 * s, 38 * s);
    else if (kind === "sad") { g.moveTo(x - 30 * s, y - 40 * s); g.lineTo(x + 30 * s, y - 40 * s); g.lineTo(x + 30 * s * -side, y - 8 * s); g.lineTo(x - 30 * s * -side, y - 22 * s); }
    else { g.moveTo(x - 30 * s, y - 40 * s); g.lineTo(x + 30 * s, y - 40 * s); g.lineTo(x + 30 * s * side, y - 6 * s); g.lineTo(x - 30 * s * side, y - 26 * s); }
    g.closePath(); g.fillStyle = "#f3eee8"; g.fill(); g.lineWidth = 6 * s; g.strokeStyle = INK; g.stroke(); g.restore();
    CS.ell(g, x, y, rx * big, ry * big, 0, null, 6 * s);
  }
}
function mouth(g, x, y, s, m, open) {
  g.lineCap = "round"; g.lineJoin = "round"; g.strokeStyle = INK; g.lineWidth = 7 * s;
  if (open > .5 && (m === "flat" || m === "smile" || m === "smirk")) m = "talk";
  const dark = "#5c1b2c", tongue = "#ff7a8a";
  if (m === "smile") { g.beginPath(); g.arc(x, y - 16 * s, 26 * s, Math.PI * .2, Math.PI * .8); g.stroke(); }
  else if (m === "grin" || m === "laugh" || m === "talk" || m === "tongue") {
    const w = (m === "laugh" ? 40 : m === "talk" ? 20 : 34) * s, h = (m === "laugh" ? 46 : m === "talk" ? 22 : 32) * s;
    const p = () => { g.beginPath(); g.moveTo(x - w, y - 6 * s); g.quadraticCurveTo(x, y + 2 * s, x + w, y - 6 * s); g.quadraticCurveTo(x, y + h * 1.25, x - w, y - 6 * s); g.closePath(); };
    p(); g.fillStyle = dark; g.fill(); g.save(); p(); g.clip();
    if (m !== "talk") { g.fillStyle = "#fff"; g.fillRect(x - w, y - 12 * s, w * 2, 11 * s); }
    g.fillStyle = tongue; g.beginPath(); g.ellipse(x + (m === "tongue" ? 8 * s : 0), y + h * (m === "tongue" ? .95 : .8), w * .55, h * .38, 0, 0, 7); g.fill(); g.restore();
    p(); g.stroke();
    if (m === "tongue") { CS.ell(g, x + 10 * s, y + h * 1.05, 14 * s, 18 * s, 0, tongue, 5 * s); }
  }
  else if (m === "o" || m === "shout") {
    const rx = (m === "shout" ? 24 : 15) * s, ry = (m === "shout" ? 34 : 19) * s;
    CS.ell(g, x, y + 4 * s, rx, ry, 0, dark, 6 * s);
    if (m === "shout") { g.save(); g.beginPath(); g.ellipse(x, y + 4 * s, rx, ry, 0, 0, 7); g.clip(); CS.ell(g, x, y + ry * .9, rx * .7, ry * .4, 0, tongue, 0); g.restore(); CS.ell(g, x, y + 4 * s, rx, ry, 0, null, 6 * s); }
  }
  else if (m === "frown") { g.beginPath(); g.arc(x, y + 18 * s, 22 * s, Math.PI * 1.2, Math.PI * 1.8); g.stroke(); }
  else if (m === "smirk") { g.beginPath(); g.moveTo(x - 20 * s, y); g.quadraticCurveTo(x + 8 * s, y + 10 * s, x + 26 * s, y - 12 * s); g.stroke(); }
  else if (m === "wavy") { g.beginPath(); g.moveTo(x - 28 * s, y); for (let i = 1; i <= 6; i++) g.lineTo(x - 28 * s + i * 9.3 * s, y + (i % 2 ? -6 : 6) * s); g.stroke(); }
  else if (m === "teeth") { CS.rrect(g, x - 30 * s, y - 12 * s, 60 * s, 26 * s, 9 * s, "#fff", 6 * s); g.beginPath(); for (let i = 1; i < 4; i++) { g.moveTo(x - 30 * s + i * 15 * s, y - 12 * s); g.lineTo(x - 30 * s + i * 15 * s, y + 14 * s); } g.moveTo(x - 30 * s, y + 1 * s); g.lineTo(x + 30 * s, y + 1 * s); g.lineWidth = 4 * s; g.stroke(); }
  else { g.beginPath(); g.moveTo(x - 20 * s, y); g.lineTo(x + 20 * s, y); g.stroke(); }
}
// face(g, cx, cy, r, {face, look, lookY, blink, talk, t})
CS.drawFace = function (g, cx, cy, r, o = {}) {
  const F = Object.assign({}, CS.FACES[o.face] || CS.FACES.neutral, o.eyes ? { eyes: o.eyes } : {}, o.mouth ? { mouth: o.mouth } : {});
  const s = r / 100, look = o.look ?? F.look ?? 0, lookY = o.lookY ?? F.lookY ?? 0;
  const ex = 34 * s, ey = cy - 8 * s;
  for (const side of [-1, 1]) {
    eye(g, cx + side * ex + look * 10 * s, ey + lookY * 8 * s, s, F.eyes, look, lookY, side, o.blink);
    if (!["x", "spiral", "heart"].includes(F.eyes)) {     // brows: [tilt, lift] tilt > 0 = angry
      const bt = F.brow[0] * side * D, bl = F.brow[1] * s;
      g.save(); g.translate(cx + side * ex + look * 10 * s, ey - 46 * s - bl + lookY * 6 * s); g.rotate(bt); CS.seg2(g, -16 * s, 0, 16 * s, 0, 8 * s); g.restore();
    }
  }
  mouth(g, cx + look * 8 * s, cy + 52 * s + lookY * 5 * s, s, F.mouth, o.talk || 0);
  if (F.eyes !== "x") { g.fillStyle = F.green ? "rgba(110,190,90,.35)" : "rgba(255,120,140,.32)"; for (const side of [-1, 1]) { g.beginPath(); g.ellipse(cx + side * 64 * s, cy + 30 * s, 15 * s, 9 * s, 0, 0, 7); g.fill(); } }
  if (F.tears || F.eyes === "cry") CS.tears(g, cx, ey, s, o.t || 0, F.eyes === "cry" ? 1.4 : 1);
};
// two little tear fountains / streams from the eyes
CS.tears = function (g, cx, ey, s, t, amt = 1) {
  g.fillStyle = "#7fd3ff"; g.strokeStyle = INK; g.lineWidth = 4 * s;
  for (const side of [-1, 1]) {
    const x0 = cx + side * 40 * s, y0 = ey + 18 * s;
    g.beginPath(); g.moveTo(x0 - 8 * s, y0); g.quadraticCurveTo(x0 + side * 4 * s, y0 + 90 * s * amt, x0 + side * 10 * s, y0 + 120 * s * amt); g.lineTo(x0 + side * 26 * s, y0 + 116 * s * amt); g.quadraticCurveTo(x0 + side * 14 * s, y0 + 60 * s, x0 + 8 * s, y0); g.closePath(); g.fill(); g.stroke();
    for (let i = 0; i < 3; i++) {   // flying drops
      const k = ((t * 1.8 + i / 3 + (side > 0 ? .17 : 0)) % 1), dx = side * (30 + 80 * k) * s * amt, dy = (-20 * Math.sin(k * Math.PI) + 140 * k * k) * s;
      CS.drop(g, x0 + dx, y0 + dy, 9 * s * (1 - k * .4), 3.5 * s);
    }
  }
};
CS.drop = function (g, x, y, r, lw = 4) { g.beginPath(); g.moveTo(x, y - r * 1.8); g.quadraticCurveTo(x + r * 1.1, y - r * .3, x + r, y + r * .2); g.arc(x, y + r * .2, r, 0, Math.PI); g.quadraticCurveTo(x - r * 1.1, y - r * .3, x, y - r * 1.8); fs(g, "#7fd3ff", lw); };

// ---------- the rig ----------
// arms: name or [shoulderDeg, elbowDeg]; 0 = straight down, + = out from the body (towards the arm's own side)
CS.ARMS = {
  hang: [10, 6], hip: [42, -118], up: [168, 6], wave: [150, 40], point: [90, 0], shrug: [62, 96], cheek: [26, 152], head: [120, 120],
  fist: [150, 60], think: [30, 150], reach: [70, 10], hold: [32, 64], cross: [-20, -100], back: [-12, -10], low: [24, 20], wide: [110, 10],
};
CS.LEGS = { stand: [4, 0], wide: [16, -4], sit: [80, -86], kick: [60, 0], jump: [20, -60], tip: [2, 0] };
function limb(g, x, y, a1, a2, l1, l2, side, lw) {
  // a in degrees from straight down, positive = outward on `side`
  const r1 = a1 * D, r2 = (a1 + a2) * D;
  const ex = x + side * Math.sin(r1) * l1, ey = y + Math.cos(r1) * l1;
  const hx = ex + side * Math.sin(r2) * l2, hy = ey + Math.cos(r2) * l2;
  g.beginPath(); g.moveTo(x, y); g.lineTo(ex, ey); g.lineTo(hx, hy); g.lineWidth = lw; g.strokeStyle = INK; g.lineCap = "round"; g.lineJoin = "round"; g.stroke();
  return { ex, ey, hx, hy, ang: r2 };
}
const pick = (v, table, d) => Array.isArray(v) ? v : (table[v] || table[d]);
/* CS.stick(g, x, y, o) draws a stick person standing with its feet at (x, y).
   o: { s (scale, 1 = 590 px tall), face, look, lookY, blink, talk, t,
        shirt: colour, pattern: "plain"|"stripes"|"dots"|"hoodie"|"chef"|"suit", stripe: colour,
        hat: "none"|"cap"|"chef"|"helmet"|"party"|"tuft"|"bun"|"curl", hatColor, glasses,
        arms: [L, R] (names or [shoulder, elbow]), legs: [L, R], step (walk phase), stride,
        lean (deg), bob (px), squash (1 = normal; <1 squashes, >1 stretches), stretch: [sx, sy] (free scaling),
        hold: { R: (g, x, y, ang) => draw, L: … }, headTilt (deg), green (0..1 sick tint) } */
CS.stick = function (g, x, y, o = {}) {
  const s = o.s || 1, t = o.t || 0;
  g.save(); g.translate(x, y);
  CS.shadow(g, 0, 4, 120 * s * (o.shadowK ?? 1), o.shadowA ?? .16);
  g.scale(s, s);
  if (o.stretch) g.scale(o.stretch[0], o.stretch[1]);
  const sq = o.squash || 1; g.scale(1 / Math.sqrt(sq), sq);
  g.rotate((o.lean || 0) * D);
  g.translate(0, -(o.bob || 0));
  const lw = 15;
  // legs
  let L = pick(o.legs?.[0], CS.LEGS, "stand"), Rl = pick(o.legs?.[1], CS.LEGS, "stand");
  if (o.step != null) { const p = o.step * Math.PI * 2, st = (o.stride ?? 1) * 26; L = [Math.sin(p) * st, Math.max(0, -Math.cos(p)) * -30]; Rl = [-Math.sin(p) * st, Math.max(0, Math.cos(p)) * -30]; }
  const hipY = -205;
  for (const [side, a] of [[-1, L], [1, Rl]]) {
    const k = limb(g, side * 26, hipY, a[0], a[1], 104, 104, side, lw);
    g.save(); g.translate(k.hx, k.hy); g.rotate(-(a[0] + a[1]) * D * side * .4); CS.ell(g, side * 16, -4, 34, 17, 0, o.shoes || INK, 6); g.restore();
  }
  // body (shirt)
  const shirt = o.shirt || "#ff5a5f", top = -372;
  const body = () => { g.beginPath(); g.moveTo(-50, top + 10); g.quadraticCurveTo(-56, hipY + 20, -48, hipY + 6); g.lineTo(48, hipY + 6); g.quadraticCurveTo(56, hipY + 20, 50, top + 10); g.quadraticCurveTo(0, top - 14, -50, top + 10); g.closePath(); };
  body(); g.fillStyle = shirt; g.fill();
  g.save(); body(); g.clip();
  const pat = o.pattern || "plain", sc = o.stripe || "#fff";
  if (pat === "stripes") { g.fillStyle = sc; for (let yy = top; yy < hipY + 10; yy += 34) g.fillRect(-70, yy + 14, 140, 15); }
  if (pat === "dots") { g.fillStyle = sc; for (let i = 0; i < 9; i++) { g.beginPath(); g.arc(-30 + (i % 3) * 30 + (Math.floor(i / 3) % 2) * 15, top + 40 + Math.floor(i / 3) * 44, 7, 0, 7); g.fill(); } }
  if (pat === "hoodie") { g.fillStyle = CS.shade(shirt, -.18); g.fillRect(-70, hipY - 24, 140, 40); g.fillStyle = CS.shade(shirt, .12); g.beginPath(); g.roundRect(-28, hipY - 72, 56, 36, 10); g.fill(); }
  if (pat === "suit") { g.fillStyle = "#fff"; g.beginPath(); g.moveTo(-18, top); g.lineTo(0, top + 70); g.lineTo(18, top); g.fill(); g.fillStyle = sc; g.beginPath(); g.moveTo(-7, top + 14); g.lineTo(7, top + 14); g.lineTo(9, top + 90); g.lineTo(0, top + 104); g.lineTo(-9, top + 90); g.fill(); }
  if (pat === "chef") { g.fillStyle = "#ffffff"; g.fillRect(-70, top - 20, 140, 260); g.fillStyle = INK; for (const yy of [top + 50, top + 92]) for (const xx of [-16, 16]) { g.beginPath(); g.arc(xx, yy, 5.5, 0, 7); g.fill(); } }
  if (o.green) { g.fillStyle = `rgba(120,200,90,${o.green * .0})`; }
  g.fillStyle = "rgba(0,0,0,.08)"; g.fillRect(14, top - 20, 60, 260);     // a soft side shade
  g.restore();
  body(); fs(g, null, 8);
  if (pat !== "chef" && pat !== "suit") { g.beginPath(); g.arc(0, top - 2, 22, .15 * Math.PI, .85 * Math.PI); g.lineWidth = 6; g.strokeStyle = INK; g.stroke(); }
  if (o.belt) { CS.rrect(g, -50, hipY - 12, 100, 18, 4, o.belt, 5); CS.rrect(g, -10, hipY - 14, 20, 22, 3, "#ffd23a", 4); }
  // arms (behind the hands, in front of the body)
  const A = [pick(o.arms?.[0], CS.ARMS, "hang"), pick(o.arms?.[1], CS.ARMS, "hang")];
  const hands = [];
  for (const [i, side] of [[0, -1], [1, 1]]) {
    let a = A[i].slice(); if (o.arms?.[i] === "wave") a[1] += Math.sin(t * 14) * 22;
    const k = limb(g, side * 46, top + 30, a[0], a[1], 92, 88, side, lw);
    hands.push(k);
  }
  // head
  const tilt = (o.headTilt || 0) * D, R = 100, hy = top - 22 - R + 6;
  g.save(); g.translate(0, top - 10); g.rotate(tilt); g.translate(0, -(top - 10));
  if (o.hat === "bun" || o.hat === "curl") drawHat(g, o, R, hy, true);
  CS.circle(g, 0, hy, R, o.green ? mix("#ffffff", "#c9ecb0", o.green) : "#fff", 9);
  g.save(); g.beginPath(); g.arc(0, hy, R - 4, 0, 7); g.clip(); g.fillStyle = "rgba(60,40,80,.07)"; g.beginPath(); g.arc(28, hy + 22, R, 0, 7); g.fill(); g.restore();
  CS.circle(g, 0, hy, R, null, 9);
  CS.drawFace(g, 0, hy + 6, R, o);
  if (o.glasses) { for (const sd of [-1, 1]) CS.circle(g, sd * 34 + (o.look || 0) * 10, hy - 2, 30, null, 6); CS.seg2(g, -6, hy - 4, 6, hy - 4, 6); }
  drawHat(g, o, R, hy, false);
  g.restore();
  // hands + held props
  for (const [i, side] of [[0, -1], [1, 1]]) {
    const k = hands[i], key = i ? "R" : "L";
    if (o.hold && o.hold[key]) { g.save(); o.hold[key](g, k.hx, k.hy, k.ang, side); g.restore(); }
    CS.circle(g, k.hx, k.hy, 21, "#fff", 7);
  }
  g.restore();
  return { head: [x, y + (hy - (o.bob || 0)) * s], hands: hands.map(k => [x + k.hx * s, y + k.hy * s]) };
};
function mix(a, b, k) { const p = c => [1, 3, 5].map(i => parseInt(c.slice(i, i + 2), 16)); const A = p(a), B = p(b); return "#" + A.map((v, i) => Math.round(v + (B[i] - v) * k).toString(16).padStart(2, "0")).join(""); }
CS.mix = mix;
function drawHat(g, o, R, hy, back) {
  const h = o.hat || "none", c = o.hatColor || "#3a7bff";
  if (back) { if (h === "bun") CS.circle(g, 0, hy - R - 18, 40, c, 8); if (h === "curl") { for (const sd of [-1, 1]) CS.circle(g, sd * 86, hy - 40, 40, c, 8); } return; }
  if (h === "cap") { g.beginPath(); g.arc(0, hy - 18, R + 4, Math.PI * 1.05, Math.PI * 1.95); g.closePath(); fs(g, c, 8); g.beginPath(); g.ellipse(70, hy - 30, 62, 16, -.08, 0, 7); fs(g, CS.shade(c, -.15), 8); CS.circle(g, 0, hy - R - 2, 10, CS.shade(c, -.2), 5); }
  if (h === "chef") { CS.rrect(g, -70, hy - R - 30, 140, 60, 10, "#fff", 8); for (const xx of [-52, 0, 52]) CS.circle(g, xx, hy - R - 70, 46, "#fff", 8); g.fillStyle = "#fff"; g.fillRect(-64, hy - R - 50, 128, 40); }
  if (h === "party") { g.beginPath(); g.moveTo(-50, hy - R + 20); g.lineTo(10, hy - R - 120); g.lineTo(60, hy - R + 20); g.closePath(); fs(g, c, 8); CS.circle(g, 10, hy - R - 124, 16, "#ffd23a", 6); }
  if (h === "tuft") { g.beginPath(); g.moveTo(-20, hy - R + 4); g.quadraticCurveTo(-30, hy - R - 50, 4, hy - R - 40); g.quadraticCurveTo(10, hy - R - 70, 30, hy - R - 46); g.quadraticCurveTo(26, hy - R - 10, 14, hy - R + 4); fs(g, c, 7); }
  if (h === "helmet") { g.save(); CS.circle(g, 0, hy + 4, R + 34, "rgba(190,230,255,.28)", 8); g.beginPath(); g.arc(-34, hy - 40, 52, Math.PI * 1.1, Math.PI * 1.5); g.lineWidth = 12; g.strokeStyle = "rgba(255,255,255,.75)"; g.stroke(); g.restore(); CS.rrect(g, -86, hy + R + 6, 172, 34, 14, "#e9edf5", 8); }
}

// ---------- keep them alive ----------
// CS.alive(t, seed) -> {bob, lean, blink} small idle motion; spread into the stick options.
CS.alive = function (t, seed = 1, amt = 1) {
  return { bob: (Math.sin(t * 2.6 + seed) * 4 + 4) * amt, lean: CS.noise1(t * .7, seed) * 2.2 * amt, blink: CS.blinkAt(t, seed), t };
};
CS.blinkAt = function (t, seed = 1) { const p = 2.6 + CS.rand(seed) * 1.8, ph = (t + CS.rand(seed + 3) * p) % p; return ph < .12; };
CS.talk = function (t, T, from, to) { if (t < from || t > to) return 0; return (Math.sin(t * 26) > .1) ? 1 : 0; };
})();
