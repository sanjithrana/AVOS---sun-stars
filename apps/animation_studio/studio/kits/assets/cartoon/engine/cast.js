/* Cartoon Shorts engine: the cast. Bean-head people, animals, props and effect sprites, drawn in 2D with plum ink.
   Design canvas for people: 600 x 1000, soles at y 975. Free from Anylancer.com. */
(function () {
const CS = window.CS = window.CS || {};
const { shade, rand, clamp, lerp } = CS;
const OL = "#2a1a2c", LW = 8;
const D2R = Math.PI / 180;
CS.INK = OL;

function fillStroke(g, fill, lw = LW) { if (fill) { g.fillStyle = fill; g.fill(); } g.strokeStyle = OL; g.lineWidth = lw; g.stroke(); }
// soft cel shade: darker crescent on the right side of the current clip
function celShade(g, x, y, w, h, color, k = -.16) { g.save(); g.clip(); g.fillStyle = shade(color, k); const p = new Path2D(); p.ellipse(x + w * .62, y, w * .55, h * 1.2, 0, 0, 7); g.fill(p); g.restore(); }   // keeps the current path for the outline
function line(g, pts, color, w) { g.beginPath(); g.moveTo(pts[0], pts[1]); for (let i = 2; i < pts.length; i += 2) g.lineTo(pts[i], pts[i + 1]); g.strokeStyle = color; g.lineWidth = w; g.stroke(); }
function limb(g, pts, color, w) { line(g, pts, OL, w + LW * 1.6); line(g, pts, color, w); }
CS.draw = { fillStroke, line, limb, celShade, OL, LW };

// ---------- faces ----------
const FACES = {
  neutral: { eye: "open", brow: [0, 0], mouth: "smile" },
  happy: { eye: "open", brow: [-4, 4], mouth: "grin" },
  joy: { eye: "arc", brow: [-6, 6], mouth: "grin" },
  laugh: { eye: "arc", brow: [-6, 6], mouth: "laugh" },
  shock: { eye: "big", brow: [-14, 10], mouth: "o" },
  scared: { eye: "big", brow: [-12, -12], mouth: "wavy" },
  angry: { eye: "lid", brow: [14, -10], mouth: "frown" },
  furious: { eye: "lid", brow: [18, -14], mouth: "shout" },
  smug: { eye: "half", brow: [6, -2], mouth: "smirk" },
  sad: { eye: "open", brow: [-14, -10], mouth: "frown" },
  worried: { eye: "open", brow: [-12, -8], mouth: "wavy" },
  sly: { eye: "half", brow: [10, -6], mouth: "smirk", look: .7 },
  determined: { eye: "lid", brow: [10, -4], mouth: "flat" },
  sleepy: { eye: "closed", brow: [0, 4], mouth: "o_small" },
  bored: { eye: "half", brow: [0, 2], mouth: "flat" },
  proud: { eye: "arc", brow: [-4, 4], mouth: "smile" },
  stern: { eye: "open", brow: [12, -6], mouth: "flat" },
  awe: { eye: "big", brow: [-10, 8], mouth: "o_small" },
};
CS.FACES = FACES;
// face(g, cx, cy, s, {face, look, lookY, blink, talk}) draws eyes, brows, mouth around head centre (cx, cy); s = scale
function drawFace(g, cx, cy, s, st, skin) {
  const F = FACES[st.face] || FACES.neutral, look = (st.look ?? F.look ?? 0) * 14 * s, lookY = (st.lookY || 0) * 10 * s;
  const ex = 58 * s, ey = cy + 4 * s;
  for (const side of [-1, 1]) {
    const x = cx + side * ex;
    let eye = F.eye; if (st.blink > .5 && eye !== "arc" && eye !== "closed") eye = "closed";
    g.lineWidth = 6 * s; g.strokeStyle = OL;
    if (eye === "arc") { g.beginPath(); g.arc(x, ey + 12 * s, 26 * s, Math.PI * 1.15, Math.PI * 1.85); g.stroke(); }
    else if (eye === "closed") { g.beginPath(); g.arc(x, ey - 8 * s, 26 * s, Math.PI * .15, Math.PI * .85); g.stroke(); }
    else {
      const big = eye === "big" ? 1.18 : 1, rx = 38 * s * big, ry = 48 * s * big;
      g.beginPath(); g.ellipse(x, ey, rx, ry, 0, 0, 7); g.fillStyle = "#fff"; g.fill(); g.stroke();
      const pr = (eye === "big" ? 11 : 17) * s;
      g.save(); g.beginPath(); g.ellipse(x, ey, rx, ry, 0, 0, 7); g.clip();
      g.fillStyle = OL; g.beginPath(); g.arc(x + look, ey + 6 * s + lookY, pr, 0, 7); g.fill();
      g.fillStyle = "#fff"; g.beginPath(); g.arc(x + look - pr * .35, ey + 6 * s + lookY - pr * .4, pr * .32, 0, 7); g.fill();
      if (eye === "lid" || eye === "half") {   // eyelid
        g.fillStyle = skin; const lidY = eye === "half" ? ey + 2 * s : ey - 22 * s;
        g.beginPath(); g.rect(x - rx - 2, ey - ry - 2, rx * 2 + 4, lidY - (ey - ry) + 2); g.fill();
        g.beginPath(); g.moveTo(x - rx, lidY); g.lineTo(x + rx, lidY + (eye === "lid" ? side * -6 * s : 0)); g.stroke();
      }
      g.restore();
    }
    // brow: [tilt, lift] tilt > 0 = angry (inner end down)
    const bt = F.brow[0] * side * D2R * 1.4, bl = F.brow[1] * s;
    g.save(); g.translate(x, ey - 68 * s - bl); g.rotate(bt); g.lineWidth = 11 * s; g.beginPath(); g.moveTo(-28 * s, 0); g.lineTo(28 * s, 0); g.stroke(); g.restore();
  }
  // mouth
  const my = cy + 92 * s, m = st.talk > .5 ? "o" : F.mouth; g.lineWidth = 7 * s; g.strokeStyle = OL;
  g.beginPath();
  if (m === "smile") { g.arc(cx, my - 22 * s, 30 * s, Math.PI * .2, Math.PI * .8); g.stroke(); }
  else if (m === "grin" || m === "laugh") {
    const h = m === "laugh" ? 46 : 34; g.moveTo(cx - 42 * s, my - 10 * s); g.quadraticCurveTo(cx, my - 2 * s, cx + 42 * s, my - 10 * s); g.quadraticCurveTo(cx, my + h * s, cx - 42 * s, my - 10 * s);
    g.fillStyle = "#7a2235"; g.fill(); g.save(); g.clip(); g.fillStyle = "#fff"; g.fillRect(cx - 45 * s, my - 14 * s, 90 * s, 12 * s); g.fillStyle = "#e86a7a"; g.beginPath(); g.ellipse(cx, my + h * s * .75, 22 * s, 12 * s, 0, 0, 7); g.fill(); g.restore();
    g.beginPath(); g.moveTo(cx - 42 * s, my - 10 * s); g.quadraticCurveTo(cx, my - 2 * s, cx + 42 * s, my - 10 * s); g.quadraticCurveTo(cx, my + h * s, cx - 42 * s, my - 10 * s); g.stroke();
  }
  else if (m === "o" || m === "o_small" || m === "shout") {
    const r = m === "o_small" ? 11 : m === "shout" ? 30 : 20; g.ellipse(cx, my, r * s * (m === "shout" ? 1.5 : 1), r * 1.25 * s, 0, 0, 7); g.fillStyle = "#7a2235"; g.fill(); g.stroke();
  }
  else if (m === "frown") { g.arc(cx, my + 22 * s, 26 * s, Math.PI * 1.2, Math.PI * 1.8); g.stroke(); }
  else if (m === "smirk") { g.moveTo(cx - 26 * s, my); g.quadraticCurveTo(cx + 10 * s, my + 10 * s, cx + 34 * s, my - 14 * s); g.stroke(); }
  else if (m === "wavy") { g.moveTo(cx - 34 * s, my); for (let i = 1; i <= 6; i++) g.lineTo(cx - 34 * s + i * 11.3 * s, my + (i % 2 ? -6 : 6) * s); g.stroke(); }
  else { g.moveTo(cx - 26 * s, my); g.lineTo(cx + 26 * s, my); g.stroke(); }
  if (!st.noBlush) { g.fillStyle = "rgba(240,110,120,.32)"; for (const side of [-1, 1]) { g.beginPath(); g.ellipse(cx + side * 98 * s, cy + 58 * s, 24 * s, 14 * s, 0, 0, 7); g.fill(); } }
}
CS.drawFace = drawFace;

// ---------- people ----------
const ARMS = {          // [shoulder angle, elbow bend] degrees: 0 = straight down, + = outward/up
  hang: [10, 4], hip: [52, -118], point: [96, -4], up: [158, 6], wave: [140, 28], salute: [112, 118], thumb: [36, 112],
  hold: [24, 96], fist: [128, -22], shrug: [58, -96], cheek: [26, 152], carry: [14, 110], reach: [70, 10], back: [-14, -20],
  aim: [70, 40], tray: [40, 70], scratch: [100, 150],
};
CS.ARMS = ARMS;
/* person spec (fixed look): { skin, hair:{style, color}, hat:{type, color, band}, top:{type, color, accent}, pants, shoes, mustache, beard, nose, glasses, size }
   state (changes): { face, look, lookY, blink, talk, arms:['hang','point'] or [[a,b],[a,b]], step (walk phase 0..1), stride (0..1), prop:{kind, hand:'R'|'L'}, jump } */
CS.drawPerson = function (g, spec, st) {
  const skin = spec.skin || "#f6c9a0", top = spec.top || {}, tc = top.color || "#4f7fb8", pants = spec.pants || OL, shoes = spec.shoes || "#3a2a24";
  const hx = 300, hy = 290;
  // legs
  const stride = st.stride ?? 0, ph = (st.step || 0) * Math.PI * 2, swing = Math.sin(ph) * 26 * stride * D2R, jump = st.jump || 0;
  const hipY = 750;
  for (const side of [-1, 1]) {
    const a = side * swing + (jump ? side * -.25 : 0), len = 210 - jump * 40;
    const x0 = 300 + side * 34, x1 = x0 + Math.sin(a) * len, y1 = hipY + Math.cos(a) * len - (side * Math.sin(ph) > 0 ? Math.abs(Math.sin(ph)) * 18 * stride : 0);
    if (spec.pants && spec.pants !== OL) limb(g, [x0, hipY - 10, x1, y1], pants, 26); else line(g, [x0, hipY, x1, y1], OL, 13);
    g.beginPath(); g.ellipse(x1 + side * 10, y1 + 8, 30, 17, 0, 0, 7); fillStroke(g, shoes, 6);
  }
  // torso
  const tt = top.type || "shirt";
  const long = tt === "coat" || tt === "smock" || tt === "dress" || tt === "redcoat";
  const bot = tt === "dress" ? 955 : long ? 850 : 772, wt = tt === "dress" ? 150 : long ? 128 : 112, wb = tt === "dress" ? 175 : long ? 138 : 116;
  g.beginPath(); g.moveTo(hx - wt * .62, 470); g.quadraticCurveTo(hx - wt, 480, hx - wb, bot); g.lineTo(hx + wb, bot); g.quadraticCurveTo(hx + wt, 480, hx + wt * .62, 470); g.closePath();
  g.fillStyle = tc; g.fill(); celShade(g, hx - wb, 620, wb * 2, 220, tc); g.strokeStyle = OL; g.lineWidth = LW; g.stroke();
  const ac = top.accent || shade(tc, -.3);
  g.lineWidth = 6; g.strokeStyle = OL;
  if (tt === "uniform" || tt === "redcoat") {
    g.fillStyle = top.belt || "#5a3a22"; g.fillRect(hx - wb + 4, bot - 70, wb * 2 - 8, 26); g.strokeRect(hx - wb + 4, bot - 70, wb * 2 - 8, 26);
    g.fillStyle = "#e8c048"; g.fillRect(hx - 14, bot - 72, 28, 30); g.strokeRect(hx - 14, bot - 72, 28, 30);
    for (let i = 0; i < 4; i++) { g.beginPath(); g.arc(hx, 520 + i * 52, 7, 0, 7); g.fillStyle = "#e8c048"; g.fill(); g.stroke(); }
    if (tt === "redcoat") { line(g, [hx - 90, 480, hx + 70, bot - 74], "#f4f0e6", 18); line(g, [hx + 90, 480, hx - 70, bot - 74], "#f4f0e6", 18); }
    else for (const side of [-1, 1]) { g.beginPath(); g.roundRect(hx + side * 62 - 26, 540, 52, 44, 6); g.fillStyle = shade(tc, -.08); g.fill(); g.stroke(); }
  } else if (tt === "suit" || tt === "coat") {
    g.fillStyle = top.shirt || "#f4f0e6"; g.beginPath(); g.moveTo(hx - 46, 470); g.lineTo(hx, 600); g.lineTo(hx + 46, 470); g.fill(); g.stroke();
    if (top.tie) { g.fillStyle = top.tie; g.beginPath(); g.moveTo(hx - 12, 480); g.lineTo(hx + 12, 480); g.lineTo(hx + 16, 580); g.lineTo(hx, 604); g.lineTo(hx - 16, 580); g.closePath(); g.fill(); g.stroke(); }
    for (let i = 0; i < 3; i++) { g.beginPath(); g.arc(hx + 6, 640 + i * 50, 7, 0, 7); g.fillStyle = ac; g.fill(); g.stroke(); }
  } else if (tt === "overalls") {
    g.fillStyle = top.bib || "#3d6db0"; g.beginPath(); g.roundRect(hx - 78, 560, 156, bot - 560, 14); g.fill(); g.stroke();
    line(g, [hx - 66, 566, hx - 80, 476], top.bib || "#3d6db0", 16); line(g, [hx + 66, 566, hx + 80, 476], top.bib || "#3d6db0", 16);
    for (const side of [-1, 1]) { g.beginPath(); g.arc(hx + side * 60, 580, 8, 0, 7); g.fillStyle = "#e8c048"; g.fill(); g.stroke(); }
  } else if (tt === "smock") {
    g.beginPath(); g.moveTo(hx - 30, 470); g.lineTo(hx, 520); g.lineTo(hx + 30, 470); g.stroke();
    for (let i = 0; i < 3; i++) { g.beginPath(); g.moveTo(hx - 70 + i * 50, 640); g.lineTo(hx - 80 + i * 55, 830); g.strokeStyle = shade(tc, -.15); g.lineWidth = 4; g.stroke(); }
    g.strokeStyle = OL;
  } else if (tt === "dress") {
    g.fillStyle = ac; g.fillRect(hx - wt * .7, 600, wt * 1.4, 22);
  } else { // shirt
    g.beginPath(); g.moveTo(hx - 34, 472); g.lineTo(hx, 520); g.lineTo(hx + 34, 472); g.fillStyle = shade(tc, .25); g.fill(); g.stroke();
  }
  if (st.bulge) { const b = st.bulge; g.save(); g.beginPath(); g.roundRect(hx - 92 * b, 560, 184 * b, 230, 10); g.fillStyle = shade(tc, -.07); g.fill(); g.strokeStyle = OL; g.lineWidth = 6; g.stroke();
    g.beginPath(); g.rect(hx + 60 * b, 760, 40, 46); g.fillStyle = "#c8962e"; g.fill(); g.strokeStyle = OL; g.stroke(); g.restore(); }
  if (spec.medal) { g.beginPath(); g.arc(hx - 60, 560, 14, 0, 7); g.fillStyle = "#e8c048"; g.fill(); g.stroke(); }
  // arms
  const arms = st.arms || ["hang", "hang"], wav = st.wave || 0;
  const hands = [];
  for (let i = 0; i < 2; i++) {
    const side = i === 0 ? -1 : 1, p = Array.isArray(arms[i]) ? arms[i] : ARMS[arms[i]] || ARMS.hang;
    let a = (p[0] + (arms[i] === "wave" ? Math.sin(wav * Math.PI * 2) * 18 : 0)) * D2R, b = p[1] * D2R;
    const sx = hx + side * (wt * .74), sy = 492;
    const ex = sx + side * Math.sin(a) * 112, ey = sy + Math.cos(a) * 112;
    const fx = ex + side * Math.sin(a + b) * 104, fy = ey + Math.cos(a + b) * 104;
    limb(g, [sx, sy, ex, ey, fx, fy], top.sleeve || tc, 26);
    hands.push([fx, fy, side, a + b]);
  }
  for (let i = 0; i < 2; i++) {
    const [x, y, side, ang] = hands[i], name = arms[i];
    if (st.prop && (st.prop.hand === "L" ? 0 : 1) === i && CS.PROPS[st.prop.kind]) CS.PROPS[st.prop.kind](g, x, y, side, ang, st.prop);
    g.beginPath(); g.arc(x, y, 19, 0, 7); fillStroke(g, skin, 6);
    if (name === "thumb") { g.beginPath(); g.roundRect(x - 6, y - 44, 13, 30, 6); fillStroke(g, skin, 5); }
    if (name === "point") { g.beginPath(); g.roundRect(x + side * 10 - (side < 0 ? 34 : 0), y - 6, 34, 13, 6); fillStroke(g, skin, 5); }
  }
  // head
  const hc = spec.hair?.color || "#4a2e22", hs = spec.hair?.style || "short";
  if (hs === "long") { g.beginPath(); g.roundRect(hx - 170, hy - 60, 340, 300, 90); fillStroke(g, hc); }
  g.beginPath(); g.ellipse(hx - 152, hy + 20, 26, 34, 0, 0, 7); fillStroke(g, skin, 6); g.beginPath(); g.ellipse(hx + 152, hy + 20, 26, 34, 0, 0, 7); fillStroke(g, skin, 6);
  const head = () => { g.beginPath(); g.moveTo(hx, hy - 185); g.bezierCurveTo(hx + 120, hy - 185, hx + 158, hy - 110, hx + 158, hy + 10); g.bezierCurveTo(hx + 158, hy + 120, hx + 108, hy + 170, hx, hy + 172); g.bezierCurveTo(hx - 108, hy + 170, hx - 158, hy + 120, hx - 158, hy + 10); g.bezierCurveTo(hx - 158, hy - 110, hx - 120, hy - 185, hx, hy - 185); g.closePath(); };
  head(); g.fillStyle = skin; g.fill(); celShade(g, hx - 158, hy + 40, 316, 200, skin, -.1); head(); g.strokeStyle = OL; g.lineWidth = LW; g.stroke();
  // hair on top
  g.save(); head(); g.clip(); g.fillStyle = hc;
  if (hs === "short" || hs === "long" || hs === "side") { g.beginPath(); g.moveTo(hx - 170, hy - 40); g.quadraticCurveTo(hx - 60, hy - 120, hx + (hs === "side" ? -10 : 40), hy - 82); g.quadraticCurveTo(hx + 90, hy - 120, hx + 170, hy - 30); g.lineTo(hx + 170, hy - 200); g.lineTo(hx - 170, hy - 200); g.fill(); }
  if (hs === "curly") for (let i = 0; i < 9; i++) { g.beginPath(); g.arc(hx - 150 + i * 37, hy - 120 + Math.abs(i - 4) * 12, 42, 0, 7); g.fill(); }
  if (hs === "balding") { g.fillRect(hx - 170, hy - 40, 40, 110); g.fillRect(hx + 130, hy - 40, 40, 110); }
  if (hs === "bun") { g.beginPath(); g.moveTo(hx - 170, hy - 30); g.quadraticCurveTo(hx, hy - 150, hx + 170, hy - 30); g.lineTo(hx + 170, hy - 200); g.lineTo(hx - 170, hy - 200); g.fill(); }
  g.restore();
  if (hs === "bun") { g.beginPath(); g.arc(hx, hy - 200, 52, 0, 7); fillStroke(g, hc); }
  if (hs !== "bald" && hs !== "balding" && hs !== "none") { head(); g.strokeStyle = OL; g.lineWidth = LW; g.stroke(); }
  if (hs === "bald") { g.fillStyle = "rgba(255,255,255,.5)"; g.beginPath(); g.ellipse(hx - 60, hy - 130, 30, 14, -.4, 0, 7); g.fill(); }
  // face
  drawFace(g, hx, hy, 1, st, skin);
  if (spec.nose === "big") { g.beginPath(); g.ellipse(hx, hy + 52, 26, 22, 0, 0, 7); fillStroke(g, shade(skin, -.06), 6); }
  if (spec.glasses) { g.lineWidth = 6; g.strokeStyle = OL; for (const s of [-1, 1]) { g.beginPath(); g.arc(hx + s * 58, hy + 4, 50, 0, 7); g.stroke(); } }
  if (spec.mustache) {
    g.fillStyle = spec.mustacheColor || hc; g.beginPath();
    if (spec.mustache === "handlebar") { g.moveTo(hx, hy + 64); g.bezierCurveTo(hx - 40, hy + 50, hx - 90, hy + 80, hx - 96, hy + 50); g.bezierCurveTo(hx - 80, hy + 96, hx - 30, hy + 92, hx, hy + 80); g.bezierCurveTo(hx + 30, hy + 92, hx + 80, hy + 96, hx + 96, hy + 50); g.bezierCurveTo(hx + 90, hy + 80, hx + 40, hy + 50, hx, hy + 64); }
    else { g.ellipse(hx - 30, hy + 70, 38, 18, -.15, 0, 7); g.ellipse(hx + 30, hy + 70, 38, 18, .15, 0, 7); }
    g.fill(); g.lineWidth = 5; g.strokeStyle = OL; g.stroke();
  }
  if (spec.beard && (st.beardLen ?? 1) > .05) { const bl = st.beardLen ?? 1; g.beginPath(); g.moveTo(hx - 140, hy + 40); g.quadraticCurveTo(hx - 120, hy + 170 + 120 * (bl - 1), hx, hy + 200 + 260 * (bl - 1)); g.quadraticCurveTo(hx + 120, hy + 170 + 120 * (bl - 1), hx + 140, hy + 40); g.quadraticCurveTo(hx, hy + 120, hx - 140, hy + 40); fillStroke(g, spec.beardColor || hc, 6); if (bl > 1.2 || !spec.mustache) { /* keep mouth visible */ g.fillStyle = "#7a2235"; } }
  // hat
  if (spec.hat) CS.drawHat(g, hx, hy, spec.hat);
};

// ---------- hats ----------
CS.drawHat = function (g, hx, hy, h) {
  const c = h.color || "#7a6a48", band = h.band || shade(c, -.35), t = h.type;
  g.save();
  if (t === "slouch") {        // wide brim, left side pinned up
    g.beginPath(); g.ellipse(hx + 20, hy - 120, 210, 34, -.05, 0, 7); fillStroke(g, c);
    g.beginPath(); g.moveTo(hx - 120, hy - 125); g.quadraticCurveTo(hx - 100, hy - 270, hx + 10, hy - 262); g.quadraticCurveTo(hx + 130, hy - 260, hx + 128, hy - 125); g.closePath(); fillStroke(g, c);
    g.fillStyle = band; g.fillRect(hx - 120, hy - 165, 248, 36); g.strokeRect(hx - 120, hy - 165, 248, 36);
    g.beginPath(); g.moveTo(hx - 128, hy - 128); g.quadraticCurveTo(hx - 200, hy - 170, hx - 158, hy - 268); g.quadraticCurveTo(hx - 120, hy - 200, hx - 100, hy - 140); g.closePath(); fillStroke(g, shade(c, -.1));
    g.beginPath(); g.arc(hx - 132, hy - 168, 12, 0, 7); fillStroke(g, "#e8c048", 5);
  } else if (t === "peaked" || t === "kepi") {
    const tall = t === "kepi" ? 1.25 : 1;
    g.beginPath(); g.moveTo(hx - 150, hy - 105); g.lineTo(hx - 150 + (t === "kepi" ? 20 : -14), hy - 105 - 120 * tall); g.lineTo(hx + 150 + (t === "kepi" ? -40 : 14), hy - 105 - 120 * tall + (t === "kepi" ? 30 : 0)); g.lineTo(hx + 150, hy - 105); g.closePath(); fillStroke(g, c);
    g.fillStyle = band; g.fillRect(hx - 150, hy - 140, 300, 36); g.strokeRect(hx - 150, hy - 140, 300, 36);
    g.beginPath(); g.moveTo(hx - 140, hy - 106); g.quadraticCurveTo(hx, hy - 50, hx + 160, hy - 100); g.lineTo(hx + 150, hy - 110); g.closePath(); fillStroke(g, OL, 4);
    if (h.badge !== false) { g.beginPath(); g.arc(hx, hy - 170, 16, 0, 7); fillStroke(g, "#e8c048", 5); }
  } else if (t === "shako") {
    g.beginPath(); g.moveTo(hx - 130, hy - 108); g.lineTo(hx - 118, hy - 300); g.lineTo(hx + 118, hy - 300); g.lineTo(hx + 130, hy - 108); g.closePath(); fillStroke(g, c);
    g.fillStyle = band; g.fillRect(hx - 128, hy - 150, 256, 40); g.strokeRect(hx - 128, hy - 150, 256, 40);
    g.beginPath(); g.moveTo(hx - 130, hy - 108); g.quadraticCurveTo(hx, hy - 60, hx + 150, hy - 100); g.lineTo(hx + 130, hy - 112); g.closePath(); fillStroke(g, OL, 4);
    g.beginPath(); g.ellipse(hx, hy - 330, 22, 36, 0, 0, 7); fillStroke(g, h.plume || "#f4f0e6", 5);
  } else if (t === "bowler" || t === "top") {
    const tall = t === "top" ? 230 : 120;
    g.beginPath(); g.ellipse(hx, hy - 118, 190, 30, 0, 0, 7); fillStroke(g, c);
    g.beginPath(); if (t === "top") { g.rect(hx - 110, hy - 118 - tall, 220, tall); } else { g.moveTo(hx - 120, hy - 118); g.bezierCurveTo(hx - 120, hy - 260, hx + 120, hy - 260, hx + 120, hy - 118); g.closePath(); } fillStroke(g, c);
    g.fillStyle = band; g.fillRect(hx - (t === "top" ? 110 : 118), hy - 158, t === "top" ? 220 : 236, 30);
  } else if (t === "straw") {
    g.beginPath(); g.ellipse(hx, hy - 120, 230, 40, 0, 0, 7); fillStroke(g, c);
    g.beginPath(); g.moveTo(hx - 120, hy - 125); g.bezierCurveTo(hx - 120, hy - 250, hx + 120, hy - 250, hx + 120, hy - 125); g.closePath(); fillStroke(g, c);
    g.fillStyle = band; g.fillRect(hx - 118, hy - 165, 236, 28);
    g.strokeStyle = shade(c, -.2); g.lineWidth = 3; for (let i = -6; i <= 6; i++) { g.beginPath(); g.moveTo(hx + i * 34, hy - 100); g.lineTo(hx + i * 30, hy - 140); g.stroke(); }
  } else if (t === "beret" || t === "flat") {
    g.beginPath(); g.ellipse(hx + (t === "beret" ? 20 : 0), hy - 150, 190, 70, t === "beret" ? .12 : 0, Math.PI, Math.PI * 2.02); g.closePath(); fillStroke(g, c);
    if (t === "flat") { g.beginPath(); g.moveTo(hx - 40, hy - 150); g.quadraticCurveTo(hx + 120, hy - 120, hx + 190, hy - 140); g.lineTo(hx + 150, hy - 156); g.closePath(); fillStroke(g, shade(c, -.15)); }
    else { g.beginPath(); g.arc(hx + 30, hy - 222, 12, 0, 7); fillStroke(g, c, 5); }
  } else if (t === "helmet") {
    g.beginPath(); g.ellipse(hx, hy - 118, 200, 30, 0, 0, 7); fillStroke(g, c);
    g.beginPath(); g.moveTo(hx - 140, hy - 118); g.bezierCurveTo(hx - 140, hy - 280, hx + 140, hy - 280, hx + 140, hy - 118); g.closePath(); fillStroke(g, c);
  } else if (t === "wide") {
    g.beginPath(); g.ellipse(hx, hy - 128, 250, 46, -.06, 0, 7); fillStroke(g, c);
    g.beginPath(); g.moveTo(hx - 120, hy - 136); g.bezierCurveTo(hx - 120, hy - 250, hx + 120, hy - 250, hx + 120, hy - 136); g.closePath(); fillStroke(g, c);
    g.fillStyle = band; g.fillRect(hx - 118, hy - 172, 236, 26);
    for (let i = 0; i < 5; i++) { g.beginPath(); g.arc(hx + 92 + Math.cos(i * 1.256) * 22, hy - 172 + Math.sin(i * 1.256) * 22, 18, 0, 7); fillStroke(g, h.flower || "#ff7a9a", 5); }
    g.beginPath(); g.arc(hx + 92, hy - 172, 12, 0, 7); fillStroke(g, "#ffd84a", 5);
  } else if (t === "cap") {
    g.beginPath(); g.moveTo(hx - 150, hy - 110); g.bezierCurveTo(hx - 150, hy - 260, hx + 150, hy - 260, hx + 150, hy - 110); g.closePath(); fillStroke(g, c);
    g.beginPath(); g.ellipse(hx + 120, hy - 108, 110, 24, .08, 0, 7); fillStroke(g, shade(c, -.15));
  }
  g.restore();
};

// ---------- props held in a hand: PROPS[kind](g, handX, handY, side, angle, opts) ----------
CS.PROPS = {
  rifle(g, x, y, side) { g.save(); g.translate(x, y); g.rotate(side * -1.25); g.fillStyle = "#6b4426"; g.beginPath(); g.roundRect(-30, -24, 150, 40, 10); fillStroke(g, "#6b4426", 6); g.beginPath(); g.roundRect(110, -16, 190, 20, 6); fillStroke(g, "#4a4f52", 6); g.restore(); },
  newspaper(g, x, y, side, a, o) { g.save(); g.translate(x - side * 10, y - 150); g.rotate(side * .06); g.beginPath(); g.rect(-120, -10, 240, 300); fillStroke(g, "#f4efe2", 6); g.fillStyle = OL; g.font = "900 46px Georgia, serif"; g.textAlign = "center"; g.fillText(o.text || "NEWS", 0, 50); for (let i = 0; i < 7; i++) g.fillRect(-96, 80 + i * 26, i % 3 === 2 ? 120 : 192, 9); g.restore(); },
  board(g, x, y, side, a, o) { g.save(); g.translate(300, 650); g.rotate(Math.sin(o.wob || 0) * .05); g.beginPath(); g.rect(-150, -80, 300, 160); fillStroke(g, o.color || "#f4efe2", 8); g.fillStyle = o.ink || OL; g.font = "900 " + (o.size || 60) + "px Georgia, serif"; g.textAlign = "center"; g.textBaseline = "middle"; g.fillText(o.text || "", 0, 4); g.restore(); },
  potato(g, x, y) { g.beginPath(); g.ellipse(x, y - 24, 32, 24, .3, 0, 7); fillStroke(g, "#c8964e", 6); },
  sign(g, x, y, side, a, o) { const cx = Math.max(130, Math.min(470, x * .55 + 135)), top = Math.max(8, y - 380); line(g, [x, y + 40, cx, top + 150], "#8a5a33", 14); g.beginPath(); g.rect(cx - 125, top, 250, 150); fillStroke(g, o.color || "#f4efe2", 7); g.fillStyle = OL; g.font = "900 " + (o.size || 48) + "px Georgia, serif"; g.textAlign = "center"; g.textBaseline = "middle"; g.fillText(o.text || "", cx, top + 77); },
  flag(g, x, y, side, a, o) { line(g, [x, y + 60, x, y - 300], "#6b4426", 12); g.beginPath(); g.moveTo(x, y - 300); g.quadraticCurveTo(x + side * 90, y - 330, x + side * 180, y - 290); g.lineTo(x + side * 180, y - 190); g.quadraticCurveTo(x + side * 90, y - 230, x, y - 200); g.closePath(); fillStroke(g, o.color || "#d23a3a", 6); },
  painting(g, x, y, side) { g.save(); g.translate(x - side * 60, y - 120); g.beginPath(); g.rect(-80, -110, 160, 220); fillStroke(g, "#b8862e", 7); g.drawImage(CS.monaCanvas(), -64, -94, 128, 188); g.restore(); },
  lantern(g, x, y) { line(g, [x, y, x, y + 30], OL, 5); g.beginPath(); g.roundRect(x - 26, y + 30, 52, 70, 10); fillStroke(g, "#ffd46a", 6); },
  telescope(g, x, y, side) { g.save(); g.translate(x, y); g.rotate(side * -1.9); g.beginPath(); g.roundRect(-20, -14, 170, 28, 8); fillStroke(g, "#b8862e", 6); g.restore(); },
  cup(g, x, y) { g.beginPath(); g.roundRect(x - 24, y - 56, 48, 52, 8); fillStroke(g, "#f4efe2", 6); },
  cards(g, x, y, side) { for (let i = 0; i < 3; i++) { g.save(); g.translate(x + side * i * 14, y - 40); g.rotate(side * (i - 1) * .25); g.beginPath(); g.roundRect(-22, -34, 44, 64, 6); fillStroke(g, "#fff", 5); g.restore(); } },
};

// ---------- person card helper ----------
/* person(spec, {h, scale, name, parent}) -> card with .pose(state); spec as in drawPerson
   idle motion, blinks and bobbing come from CS.alive(card, t, seed) in your frame code. */
CS.person = function (spec, o = {}) {
  const design = "person:" + JSON.stringify(spec);
  const c = CS.card({ cw: 600, ch: 1000, h: (o.h || 2.2) * (spec.size || 1), scale: o.scale ?? 2, design, name: o.name, parent: o.parent, draw: (g, st) => CS.drawPerson(g, spec, st) });
  c.spec = spec; c.pose = st => c.set(st); return c;
};
// blinkAt(t, seed): 1 while the eyes are closed (deterministic, every 2.5-4.5 s)
CS.blinkAt = function (t, seed = 1) { let k = rand(seed) * 2; let i = 0; while (k < t + 1 && i < 200) { if (t >= k && t < k + .12) return 1; k += 2.5 + rand(seed * 31 + i) * 2; i++; } return 0; };
// alive(card, t, seed, {bob, sway}): breathing, sway and a tiny idle bob so no character is ever frozen
CS.alive = function (c, t, seed = 1, o = {}) {
  const b = Math.sin(t * 2.2 + seed) * .012 * (o.bob ?? 1);
  c.pivot.scale.y = 1 + b; c.pivot.scale.x = Math.sign(c.pivot.scale.x || 1) * (1 - b * .5);
  c.pivot.rotation.z = CS.noise1(t * .6, seed) * .025 * (o.sway ?? 1) + (o.tilt || 0);
};

// ---------- emu ----------
/* emu state: { face:'norm'|'angry'|'smug'|'shock'|'happy', step, run (0..1), peck (0..1), beak (0..1 open), look, blink, hat:'helmet'|'slouch'|null, neck (lean) } */
CS.drawEmu = function (g, st) {
  const body = "#6e4c34", fluff = "#8a6244", skin = "#7f97ad", leg = "#6d7a86";
  const run = st.run || 0, ph = (st.step || 0) * Math.PI * 2, bob = Math.abs(Math.sin(ph)) * 16 * run;
  const bx = 330, by = 520 - bob;
  // legs (behind body)
  for (const side of [-1, 1]) {
    const sw = Math.sin(ph + (side > 0 ? 0 : Math.PI)) * run;
    const hx = bx + side * 26 + 10, hy = by + 90, kx = hx - 30 + sw * 70, ky = hy + 150 - Math.max(0, sw) * 30;
    const fx = kx + 30 + sw * 90, fy = 958 - Math.max(0, -Math.sin(ph + (side > 0 ? 0 : Math.PI))) * 60 * run;
    limb(g, [hx, hy, kx, ky, fx, fy], leg, 14);
    for (const toe of [-.5, 0, .5]) line(g, [fx, fy, fx + 46 * Math.cos(toe), fy + 10 + 16 * Math.sin(toe)], OL, 9);
  }
  // body: shaggy oval with feather strokes
  g.beginPath();
  for (let i = 0; i <= 40; i++) { const a = i / 40 * Math.PI * 2, r = 1 + (i % 2 ? .07 : -.02); const x = bx + Math.cos(a) * 172 * r, y = by + Math.sin(a) * 128 * r + (Math.cos(a) < -.6 ? 30 : 0); i ? g.lineTo(x, y) : g.moveTo(x, y); }
  g.closePath(); g.fillStyle = body; g.fill(); celShade(g, bx - 172, by + 60, 344, 140, body, -.2);
  g.strokeStyle = OL; g.lineWidth = LW; g.stroke();
  g.save(); g.strokeStyle = fluff; g.lineWidth = 6;
  for (let i = 0; i < 26; i++) { const x = bx - 140 + rand(i * 7) * 270, y = by - 90 + rand(i * 7 + 1) * 170; g.beginPath(); g.moveTo(x, y); g.quadraticCurveTo(x - 20, y + 20, x - 34, y + 46); g.stroke(); }
  g.restore();
  // neck + head
  const peck = st.peck || 0, lean = (st.neck || 0) + run * .45 + peck * 1.3;
  const nx0 = bx + 120, ny0 = by - 60;
  const hx = nx0 + Math.sin(.15 + lean) * 260, hy = ny0 - Math.cos(.15 + lean) * 260 + peck * 60;
  const mx = (nx0 + hx) / 2 + 20, my = (ny0 + hy) / 2;
  g.beginPath(); g.moveTo(nx0, ny0); g.quadraticCurveTo(mx, my, hx, hy); g.strokeStyle = OL; g.lineWidth = 62; g.stroke(); g.strokeStyle = skin; g.lineWidth = 46; g.stroke();
  g.strokeStyle = fluff; g.lineWidth = 50; g.beginPath(); g.moveTo(nx0, ny0); g.quadraticCurveTo((nx0 * 3 + hx) / 4 + 10, (ny0 * 3 + hy) / 4, (nx0 + hx) / 2, (ny0 + hy) / 2); g.stroke();
  // head
  g.save(); g.translate(hx, hy); g.rotate(lean * .35);
  g.beginPath(); g.ellipse(0, 0, 60, 52, 0, 0, 7); fillStroke(g, skin);
  g.fillStyle = "#3a2c28"; for (let i = 0; i < 7; i++) { g.beginPath(); g.moveTo(-50 + i * 14, -36); g.lineTo(-44 + i * 14, -64 - (i % 2) * 10); g.lineTo(-36 + i * 14, -38); g.fill(); }
  // beak
  const bo = (st.beak || 0) * .5;
  g.save(); g.translate(48, 10); g.rotate(-bo * .5); g.beginPath(); g.moveTo(0, -14); g.quadraticCurveTo(60, -12, 76, 2); g.lineTo(0, 6); g.closePath(); fillStroke(g, "#4a4a4a", 6); g.restore();
  g.save(); g.translate(48, 12); g.rotate(bo * .6); g.beginPath(); g.moveTo(0, 0); g.lineTo(70, 4); g.quadraticCurveTo(40, 18, 0, 14); g.closePath(); fillStroke(g, "#3a3a3a", 6); g.restore();
  // eye
  const f = st.face || "norm", look = (st.look || 0) * 8;
  if (st.blink > .5 || f === "happy") { g.lineWidth = 6; g.strokeStyle = OL; g.beginPath(); g.arc(10, f === "happy" ? 2 : -10, 18, f === "happy" ? Math.PI * 1.15 : Math.PI * .15, f === "happy" ? Math.PI * 1.85 : Math.PI * .85); g.stroke(); }
  else {
    const r = f === "shock" ? 30 : 24; g.beginPath(); g.ellipse(10, -6, r, r * 1.15, 0, 0, 7); fillStroke(g, "#fff", 6);
    g.fillStyle = OL; g.beginPath(); g.arc(14 + look, -2, f === "shock" ? 8 : 12, 0, 7); g.fill();
    if (f === "angry" || f === "smug") { g.fillStyle = skin; g.beginPath(); g.rect(-20, -40, 60, f === "smug" ? 30 : 20); g.fill(); g.beginPath(); g.moveTo(-16, f === "smug" ? -10 : -22); g.lineTo(38, f === "angry" ? -12 : -10); g.lineWidth = 6; g.strokeStyle = OL; g.stroke(); }
    if (f === "angry") { g.lineWidth = 9; g.beginPath(); g.moveTo(-14, -44); g.lineTo(36, -26); g.stroke(); }
  }
  if (st.hat === "helmet") { g.save(); g.scale(.36, .36); CS.drawHat(g, 0, 22, { type: "helmet", color: "#6f7a52" }); g.restore(); }
  g.restore();
  if (st.hat === "slouch") { g.save(); g.translate(hx - 4, hy - 34); g.scale(.42, .42); g.rotate(-.1); CS.drawHat(g, 0, 150, { type: "slouch", color: "#9a8558" }); g.restore(); }
};
CS.emu = function (o = {}) {
  const c = CS.card({ cw: 700, ch: 1000, h: o.h || 2.2, scale: o.scale ?? 1.4, design: "emu", name: o.name, parent: o.parent, blobW: 1.4, draw: (g, st) => CS.drawEmu(g, st) });
  c.pose = st => c.set(st); return c;
};

// ---------- pig ----------
/* pig state: { face:'norm'|'happy'|'shock'|'smug'|'sad', step, trot, munch (0..1), look, blink, angel (0..1 halo + wings) } */
CS.drawPig = function (g, st) {
  const pink = "#f4a6b4", dark = "#e07f92", trot = st.trot || 0, ph = (st.step || 0) * Math.PI * 2;
  const bx = 380, by = 390 - Math.abs(Math.sin(ph)) * 10 * trot;
  if (st.angel) { g.save(); g.globalAlpha = clamp(st.angel * 1.5); for (const s of [-1, 1]) { g.beginPath(); g.ellipse(bx - 40 + s * 10, by - 140, 110, 54, s * .5 - .3, 0, 7); fillStroke(g, "#ffffff", 6); } g.restore(); }
  // legs
  for (const [lx, ofs] of [[-150, 0], [-90, Math.PI], [110, Math.PI], [170, 0]]) { const sw = Math.sin(ph + ofs) * 22 * trot; limb(g, [bx + lx, by + 90, bx + lx + sw, 560], pink, 34); g.beginPath(); g.roundRect(bx + lx + sw - 22, 548, 44, 30, 6); fillStroke(g, "#7a4a4a", 6); }
  // tail
  g.beginPath(); g.moveTo(bx - 225, by - 20); g.bezierCurveTo(bx - 300, by - 60, bx - 260, by - 120, bx - 240, by - 70); g.bezierCurveTo(bx - 225, by - 40, bx - 290, by - 30, bx - 300, by - 70); g.strokeStyle = OL; g.lineWidth = 16; g.stroke(); g.strokeStyle = pink; g.lineWidth = 7; g.stroke();
  // body
  g.beginPath(); g.ellipse(bx, by, 235, 150, 0, 0, 7); g.fillStyle = pink; g.fill(); celShade(g, bx - 235, by + 60, 470, 160, pink, -.12); g.beginPath(); g.ellipse(bx, by, 235, 150, 0, 0, 7); g.strokeStyle = OL; g.lineWidth = LW; g.stroke();
  // head
  const hx = bx + 205, hy = by - 50, mu = st.munch ? Math.abs(Math.sin(st.munch * Math.PI * 6)) : 0;
  for (const s of [-1, 1]) { g.beginPath(); g.moveTo(hx + s * 60 - 30, hy - 80); g.lineTo(hx + s * 70, hy - 160); g.lineTo(hx + s * 60 + 34, hy - 70); g.closePath(); fillStroke(g, dark, 6); }
  g.beginPath(); g.ellipse(hx, hy, 118, 108, 0, 0, 7); fillStroke(g, pink);
  g.beginPath(); g.ellipse(hx + 92, hy + 30 + mu * 6, 52, 42, 0, 0, 7); fillStroke(g, dark, 6);
  g.fillStyle = OL; for (const s of [-1, 1]) { g.beginPath(); g.ellipse(hx + 92 + s * 18, hy + 30 + mu * 6, 8, 13, 0, 0, 7); g.fill(); }
  const f = st.face || "norm";
  for (const s of [-1, 1]) {
    const ex = hx - 10 + s * 42, ey = hy - 28;
    if (st.blink > .5 || f === "happy") { g.lineWidth = 6; g.strokeStyle = OL; g.beginPath(); g.arc(ex, ey + 6, 16, Math.PI * 1.15, Math.PI * 1.85); g.stroke(); continue; }
    const r = f === "shock" ? 26 : 20; g.beginPath(); g.ellipse(ex, ey, r, r * 1.2, 0, 0, 7); fillStroke(g, "#fff", 6);
    g.fillStyle = OL; g.beginPath(); g.arc(ex + 4 + (st.look || 0) * 6, ey + 4, f === "shock" ? 6 : 9, 0, 7); g.fill();
    if (f === "smug" || f === "sad") { g.fillStyle = pink; g.fillRect(ex - 24, ey - 30, 48, 24); g.lineWidth = 6; g.strokeStyle = OL; g.beginPath(); g.moveTo(ex - 22, ey - 6); g.lineTo(ex + 22, ey - 6 + (f === "sad" ? s * 6 : 0)); g.stroke(); }
  }
  g.lineWidth = 7; g.strokeStyle = OL; g.beginPath();
  if (f === "shock") g.ellipse(hx + 40, hy + 78, 14, 18, 0, 0, 7); else if (f === "sad") g.arc(hx + 40, hy + 100, 22, Math.PI * 1.2, Math.PI * 1.8); else g.arc(hx + 34, hy + 56 + mu * 8, 30, Math.PI * .15, Math.PI * .75);
  g.stroke();
  if (st.food) CS.PROPS.potato(g, hx + 120, hy + 96);
  if (st.angel) { g.save(); g.globalAlpha = clamp(st.angel * 1.5); g.beginPath(); g.ellipse(hx - 10, hy - 170, 70, 18, 0, 0, 7); g.strokeStyle = OL; g.lineWidth = 18; g.stroke(); g.strokeStyle = "#ffd84a"; g.lineWidth = 10; g.stroke(); g.restore(); }
};
CS.pig = function (o = {}) {
  const c = CS.card({ cw: 800, ch: 600, h: o.h || 1.1, scale: o.scale ?? 1.6, design: "pig", name: o.name, parent: o.parent, blobW: 1.3, draw: (g, st) => CS.drawPig(g, st) });
  c.pose = st => c.set(st); return c;
};

// ---------- a famous painting, cartoon version (our own drawing) ----------
const monas = {};
CS.monaCanvas = function (v = "smile") {
  if (monas[v]) return monas[v];
  const mona = monas[v] = document.createElement("canvas"); mona.width = 400; mona.height = 600; const g = mona.getContext("2d"); g.lineJoin = g.lineCap = "round";
  const bg = g.createLinearGradient(0, 0, 0, 600); bg.addColorStop(0, "#9fb08a"); bg.addColorStop(.45, "#6f7c55"); bg.addColorStop(1, "#4a3a22"); g.fillStyle = bg; g.fillRect(0, 0, 400, 600);
  g.strokeStyle = "#c8a66a"; g.lineWidth = 8; g.beginPath(); g.moveTo(20, 220); g.bezierCurveTo(60, 200, 40, 160, 90, 150); g.stroke(); g.beginPath(); g.moveTo(330, 260); g.bezierCurveTo(350, 230, 390, 220, 380, 190); g.stroke();
  g.fillStyle = "#566848"; g.beginPath(); g.moveTo(0, 170); g.quadraticCurveTo(80, 120, 140, 150); g.lineTo(140, 260); g.lineTo(0, 260); g.fill(); g.beginPath(); g.moveTo(260, 160); g.quadraticCurveTo(340, 120, 400, 150); g.lineTo(400, 270); g.lineTo(260, 270); g.fill();
  // body
  g.fillStyle = "#2e2a22"; g.beginPath(); g.moveTo(70, 600); g.quadraticCurveTo(80, 360, 200, 340); g.quadraticCurveTo(320, 360, 330, 600); g.fill(); g.strokeStyle = OL; g.lineWidth = 5; g.stroke();
  g.fillStyle = "#c98f5c"; g.beginPath(); g.moveTo(150, 350); g.quadraticCurveTo(200, 400, 250, 350); g.lineTo(240, 340); g.lineTo(160, 340); g.fill();
  // hands folded
  g.fillStyle = "#e2b07c"; g.beginPath(); g.ellipse(170, 520, 50, 26, -.2, 0, 7); g.fill(); g.stroke(); g.beginPath(); g.ellipse(225, 515, 50, 26, .25, 0, 7); g.fill(); g.stroke();
  // hair + head
  g.fillStyle = "#2a1c14"; g.beginPath(); g.ellipse(200, 230, 105, 150, 0, 0, 7); g.fill();
  g.fillStyle = "#e6b47e"; g.beginPath(); g.ellipse(200, 220, 78, 98, 0, 0, 7); g.fill(); g.stroke();
  g.fillStyle = "#2a1c14"; g.beginPath(); g.moveTo(122, 200); g.quadraticCurveTo(200, 100, 278, 200); g.quadraticCurveTo(250, 130, 200, 128); g.quadraticCurveTo(150, 130, 122, 200); g.fill();
  g.fillStyle = "#fff"; for (const s of [-1, 1]) { if (v === "wink" && s > 0) { g.lineWidth = 5; g.beginPath(); g.arc(230, 210, 13, Math.PI * .15, Math.PI * .85); g.stroke(); continue; } g.beginPath(); g.ellipse(200 + s * 30, 215, 13, 15, 0, 0, 7); g.fill(); g.stroke(); g.fillStyle = OL; g.beginPath(); g.arc(200 + s * 30 + 4, 218, 6, 0, 7); g.fill(); g.fillStyle = "#fff"; }
  g.lineWidth = 4; g.beginPath(); if (v === "wink") { g.moveTo(176, 262); g.quadraticCurveTo(204, 284, 228, 258); } else { g.moveTo(178, 266); g.quadraticCurveTo(200, 276, 224, 264); } g.stroke();
  g.fillStyle = "rgba(60,40,10,.25)"; g.fillRect(0, 0, 400, 600);
  if (v === "small") { /* reserved */ }
  return mona;
};

// ---------- effect sprite textures: fxTex(kind) ----------
const fxc = {};
CS.fxTex = function (kind, o = {}) {
  const key = kind + JSON.stringify(o); if (fxc[key]) return fxc[key];
  return fxc[key] = CS.paint.canvasTex(256, 256, (g) => {
    g.lineJoin = g.lineCap = "round"; g.translate(128, 128);
    if (kind === "dust") { g.fillStyle = o.color || "#e8d2b0"; for (let i = 0; i < 6; i++) { g.beginPath(); g.arc(Math.cos(i) * 46, Math.sin(i * 1.7) * 34, 56 - i * 4, 0, 7); g.fill(); } g.strokeStyle = shade(o.color || "#e8d2b0", -.25); g.lineWidth = 8; g.beginPath(); g.arc(0, 0, 92, .2, 2.6); g.stroke(); }
    else if (kind === "star") { g.beginPath(); for (let i = 0; i < 10; i++) { const r = i % 2 ? 46 : 110, a = i / 10 * Math.PI * 2 - Math.PI / 2; g.lineTo(Math.cos(a) * r, Math.sin(a) * r); } g.closePath(); fillStroke(g, o.color || "#ffd84a", 10); }
    else if (kind === "feather") { g.rotate(.6); g.beginPath(); g.ellipse(0, 0, 40, 110, 0, 0, 7); fillStroke(g, o.color || "#7a5a40", 9); line(g, [0, -110, 0, 120], OL, 6); }
    else if (kind === "bang") { g.beginPath(); for (let i = 0; i < 16; i++) { const r = i % 2 ? 74 : 124, a = i / 16 * Math.PI * 2; g.lineTo(Math.cos(a) * r, Math.sin(a) * r * .8); } g.closePath(); fillStroke(g, o.color || "#ffd84a", 10); g.fillStyle = OL; g.font = "900 " + (o.size || 62) + "px Impact, Arial Black, sans-serif"; g.textAlign = "center"; g.textBaseline = "middle"; g.fillText(o.text || "BANG!", 0, 4); }
    else if (kind === "zzz") { g.fillStyle = "#fff"; g.strokeStyle = OL; g.lineWidth = 10; g.font = "900 150px Arial Black, sans-serif"; g.textAlign = "center"; g.textBaseline = "middle"; g.strokeText("Z", 0, 0); g.fillText("Z", 0, 0); }
    else if (kind === "!" || kind === "?") { g.fillStyle = o.color || "#ff4a4a"; g.strokeStyle = OL; g.lineWidth = 14; g.font = "900 220px Arial Black, sans-serif"; g.textAlign = "center"; g.textBaseline = "middle"; g.strokeText(kind, 0, 10); g.fillText(kind, 0, 10); }
    else if (kind === "sweat") { g.beginPath(); g.moveTo(0, -100); g.quadraticCurveTo(70, 20, 0, 90); g.quadraticCurveTo(-70, 20, 0, -100); fillStroke(g, "#8fd0ff", 10); }
    else if (kind === "heart") { g.beginPath(); g.moveTo(0, 90); g.bezierCurveTo(-140, -10, -60, -120, 0, -50); g.bezierCurveTo(60, -120, 140, -10, 0, 90); fillStroke(g, "#ff5a7a", 10); }
    else if (kind === "confetti") { g.rotate(o.r || 0); g.fillStyle = o.color || "#ff5a7a"; g.fillRect(-50, -28, 100, 56); }
    else if (kind === "potato") { g.beginPath(); g.ellipse(0, 0, 96, 70, .3, 0, 7); fillStroke(g, "#c8964e", 10); g.fillStyle = "#8a6030"; for (let i = 0; i < 4; i++) { g.beginPath(); g.arc(Math.cos(i * 2) * 50, Math.sin(i * 2) * 30, 7, 0, 7); g.fill(); } }
    else if (kind === "paper") { g.rotate(o.r || .2); g.beginPath(); g.rect(-90, -110, 180, 220); fillStroke(g, "#f4efe2", 8); g.fillStyle = OL; g.font = "900 34px Georgia, serif"; g.textAlign = "center"; g.fillText(o.text || "NEWS", 0, -70); for (let i = 0; i < 5; i++) g.fillRect(-70, -40 + i * 26, 140, 8); }
    else if (kind === "note") { g.fillStyle = OL; g.beginPath(); g.ellipse(-20, 60, 40, 30, -.3, 0, 7); g.fill(); g.fillRect(14, -100, 14, 160); g.fillRect(14, -100, 70, 24); }
    else if (kind === "cloud") { g.fillStyle = "#ffffff"; for (const [x, y, r] of [[-60, 20, 60], [0, -10, 80], [64, 20, 58], [-100, 46, 40], [104, 48, 40]]) { g.beginPath(); g.arc(x, y, r, 0, 7); g.fill(); } g.fillStyle = "rgba(170,190,220,.45)"; g.fillRect(-140, 50, 280, 40); }
    else if (kind === "smoke") { g.fillStyle = o.color || "rgba(240,240,240,.95)"; for (let i = 0; i < 7; i++) { g.beginPath(); g.arc(Math.cos(i * 2.1) * 50, Math.sin(i * 1.3) * 40, 60, 0, 7); g.fill(); } }
    else if (kind === "spark") { g.strokeStyle = o.color || "#ffd84a"; g.lineWidth = 16; for (let i = 0; i < 8; i++) { const a = i / 8 * Math.PI * 2; g.beginPath(); g.moveTo(Math.cos(a) * 40, Math.sin(a) * 40); g.lineTo(Math.cos(a) * 110, Math.sin(a) * 110); g.stroke(); } }
    else if (kind === "bird") { g.beginPath(); g.ellipse(0, 10, 80, 66, 0, 0, 7); fillStroke(g, o.color || "#5aa0e0", 10); g.beginPath(); g.ellipse(-20, 30, 44, 26, .4, 0, 7); fillStroke(g, shade(o.color || "#5aa0e0", -.15), 8); g.beginPath(); g.moveTo(70, 0); g.lineTo(118, 14); g.lineTo(70, 28); g.closePath(); fillStroke(g, "#ffb02e", 8); g.fillStyle = "#fff"; g.beginPath(); g.arc(34, -10, 18, 0, 7); g.fill(); g.strokeStyle = OL; g.lineWidth = 6; g.stroke(); g.fillStyle = OL; g.beginPath(); g.arc(38, -8, 8, 0, 7); g.fill(); }
    else if (kind === "speed") { g.strokeStyle = "rgba(255,255,255,.9)"; g.lineWidth = 10; for (let i = 0; i < 5; i++) { g.beginPath(); g.moveTo(-110, -60 + i * 30); g.lineTo(110 - (i % 2) * 60, -60 + i * 30); g.stroke(); } }
  });
};
// burst(kind, at:[x,y,z], t0, {n, dur, spread, up, size, gravity, seed, spin, parent, o}) -> update(t) ; deterministic particle puff
CS.burst = function (kind, at, t0, o = {}) {
  const n = o.n || 8, list = [];
  for (let i = 0; i < n; i++) list.push(CS.sprite(CS.fxTex(kind, Object.assign({ r: i * .7, color: o.colors ? o.colors[i % o.colors.length] : o.color }, o.o || {})), o.size || .5, o.parent));
  const seed = o.seed || 1, dur = o.dur || .8;
  const b = { list, t0, update(t) {
    const k = (t - b.t0) / dur;
    list.forEach((s, i) => {
      s.visible = k >= 0 && k <= 1; if (!s.visible) return;
      const a = rand(seed + i * 5) * Math.PI * 2, sp = (o.spread ?? 1) * (.4 + rand(seed + i * 5 + 1) * .8), up = (o.up ?? 1) * (.5 + rand(seed + i * 5 + 2));
      const tt = k * dur;
      s.position.set(at[0] + Math.cos(a) * sp * tt * 2, at[1] + up * tt * 2 - (o.gravity ?? 2) * tt * tt, at[2] + Math.sin(a) * sp * tt * 2);
      const sz = (o.size || .5) * (o.grow ? (.6 + k) : 1) * (k > .75 ? (1 - k) * 4 : 1);
      s.scale.set(sz, sz, 1); s.material.rotation = (o.spin ?? 1) * (rand(seed + i) - .5) * tt * 6;
    });
  } };
  b.update(-1); return b;
};
// pop(kind, at, t0, t1, {size, bob}) -> update(t): one sprite that pops in with overshoot and out
CS.pop = function (kind, at, t0, t1, o = {}) {
  const s = CS.sprite(CS.fxTex(kind, o.o || {}), o.size || .6, o.parent);
  const p = { s, t0, t1, update(t) {
    s.visible = t >= p.t0 && t <= p.t1; if (!s.visible) return;
    const kin = CS.ease.back(CS.seg(t, p.t0, p.t0 + .25)), kout = 1 - CS.seg(t, p.t1 - .15, p.t1);
    const sz = (o.size || .6) * kin * kout; s.scale.set(sz, sz, 1);
    s.position.set(at[0], at[1] + Math.sin((t - p.t0) * 6) * (o.bob ?? .04) + (o.rise || 0) * (t - p.t0), at[2]);
  } };
  p.update(-1); return p;
};
})();
