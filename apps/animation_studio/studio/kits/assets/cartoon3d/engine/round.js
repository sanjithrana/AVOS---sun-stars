/* Cartoon Shorts engine: round-head people. A big white round head, dot eyes, stick arms and legs, white mitten hands,
   simple clothes. Same pose API as CS.person: use CS.person({style: "round", ...}). Free from Anylancer.com. */
(function () {
const CS = window.CS = window.CS || {};
const { shade } = CS;
const { fillStroke, line } = CS.draw;
const OL = CS.INK, D2R = Math.PI / 180;
const HX = 300, HY = 262, HR = 172;          // head centre and radius on the 600 x 1000 design canvas

// ---------- face: dot eyes ----------
function mouth(g, cx, my, s, m) {
  g.lineWidth = 7 * s; g.strokeStyle = OL; g.beginPath();
  if (m === "smile") { g.arc(cx, my - 20 * s, 28 * s, Math.PI * .2, Math.PI * .8); g.stroke(); }
  else if (m === "grin" || m === "laugh") {
    const h = m === "laugh" ? 52 : 36, w = m === "laugh" ? 48 : 40;
    const p = () => { g.beginPath(); g.moveTo(cx - w * s, my - 10 * s); g.quadraticCurveTo(cx, my - 2 * s, cx + w * s, my - 10 * s); g.quadraticCurveTo(cx, my + h * s, cx - w * s, my - 10 * s); };
    p(); g.fillStyle = "#6a1f2e"; g.fill(); g.save(); g.clip(); g.fillStyle = "#fff"; g.fillRect(cx - 50 * s, my - 14 * s, 100 * s, 12 * s);
    g.fillStyle = "#e86a7a"; g.beginPath(); g.ellipse(cx, my + h * s * .78, 24 * s, 13 * s, 0, 0, 7); g.fill(); g.restore(); p(); g.stroke();
  }
  else if (m === "o" || m === "o_small" || m === "shout") {
    const r = m === "o_small" ? 10 : m === "shout" ? 28 : 18; g.ellipse(cx, my, r * s * (m === "shout" ? 1.4 : 1), r * 1.3 * s, 0, 0, 7); g.fillStyle = "#6a1f2e"; g.fill(); g.stroke();
  }
  else if (m === "frown") { g.arc(cx, my + 20 * s, 24 * s, Math.PI * 1.2, Math.PI * 1.8); g.stroke(); }
  else if (m === "smirk") { g.moveTo(cx - 24 * s, my); g.quadraticCurveTo(cx + 10 * s, my + 10 * s, cx + 32 * s, my - 13 * s); g.stroke(); }
  else if (m === "wavy") { g.moveTo(cx - 32 * s, my); for (let i = 1; i <= 6; i++) g.lineTo(cx - 32 * s + i * 10.6 * s, my + (i % 2 ? -5 : 5) * s); g.stroke(); }
  else { g.moveTo(cx - 24 * s, my); g.lineTo(cx + 24 * s, my); g.stroke(); }
}
CS.drawDotFace = function (g, cx, cy, st, skin, s = 1) {
  const F = CS.FACES[st.face] || CS.FACES.neutral, look = (st.look ?? F.look ?? 0) * 12 * s, lookY = (st.lookY || 0) * 9 * s;
  const ex = 54 * s, ey = cy - 4 * s;
  for (const side of [-1, 1]) {
    const x = cx + side * ex;
    let eye = F.eye; if (st.blink > .5 && eye !== "arc" && eye !== "closed") eye = "closed";
    g.strokeStyle = OL; g.lineWidth = 7 * s; g.lineCap = "round";
    if (eye === "arc") { g.beginPath(); g.arc(x, ey + 10 * s, 20 * s, Math.PI * 1.15, Math.PI * 1.85); g.stroke(); }
    else if (eye === "closed") { g.beginPath(); g.arc(x, ey - 6 * s, 20 * s, Math.PI * .15, Math.PI * .85); g.stroke(); }
    else if (eye === "big") {
      g.beginPath(); g.ellipse(x, ey, 30 * s, 37 * s, 0, 0, 7); g.fillStyle = "#fff"; g.fill(); g.lineWidth = 6 * s; g.stroke();
      g.fillStyle = OL; g.beginPath(); g.arc(x + look * .7, ey + 4 * s + lookY, 12 * s, 0, 7); g.fill();
    } else {
      const ry = eye === "half" ? 13 : 22;
      g.fillStyle = OL; g.beginPath(); g.ellipse(x + look, ey + lookY + (eye === "half" ? 8 * s : 0), 14 * s, ry * s, 0, 0, 7); g.fill();
      g.fillStyle = "#fff"; g.beginPath(); g.arc(x + look - 5 * s, ey + lookY - 8 * s + (eye === "half" ? 8 * s : 0), 4.5 * s, 0, 7); g.fill();
      if (eye === "half") { g.lineWidth = 7 * s; g.beginPath(); g.moveTo(x - 20 * s, ey - 4 * s); g.lineTo(x + 20 * s, ey - 4 * s); g.stroke(); }
      if (eye === "lid") { g.lineWidth = 8 * s; g.beginPath(); g.moveTo(x - 22 * s * side, ey - 22 * s); g.lineTo(x + 22 * s * side, ey - 8 * s); g.stroke(); }
    }
    if (eye !== "lid") {   // brows: [tilt, lift], tilt > 0 = angry
      const bt = F.brow[0] * side * D2R * 1.5, bl = F.brow[1] * s * .9;
      g.save(); g.translate(x, ey - 50 * s - bl); g.rotate(bt); g.lineWidth = 9 * s; g.beginPath(); g.moveTo(-20 * s, 0); g.lineTo(20 * s, 0); g.stroke(); g.restore();
    }
  }
  mouth(g, cx, cy + 74 * s, s, st.talk > .5 ? "o" : F.mouth);
  if (!st.noBlush) { g.fillStyle = "rgba(240,120,130,.28)"; for (const side of [-1, 1]) { g.beginPath(); g.ellipse(cx + side * 96 * s, cy + 44 * s, 22 * s, 12 * s, 0, 0, 7); g.fill(); } }
};

// ---------- hair for a round head ----------
function hairBack(g, spec) {
  const hc = spec.hair?.color || "#5a3a26", hs = spec.hair?.style || "none";
  g.fillStyle = hc;
  if (hs === "long") { g.beginPath(); g.roundRect(HX - HR - 14, HY - 40, (HR + 14) * 2, 300, 80); fillStroke(g, hc); }
  if (hs === "wig") {          // 18th-century powdered wig: rolls at the sides, ribbon tail at the back
    for (const side of [-1, 1]) for (let i = 0; i < 3; i++) { g.beginPath(); g.ellipse(HX + side * (HR - 6), HY + 10 + i * 46, 40, 26, 0, 0, 7); fillStroke(g, hc, 6); }
  }
  if (hs === "bun") { g.beginPath(); g.arc(HX, HY - HR - 30, 52, 0, 7); fillStroke(g, hc); }
}
function hairFront(g, spec) {
  const hc = spec.hair?.color || "#5a3a26", hs = spec.hair?.style || "none";
  const clipHead = () => { g.beginPath(); g.arc(HX, HY, HR, 0, 7); };
  g.save(); clipHead(); g.clip(); g.fillStyle = hc;
  if (hs === "short" || hs === "side" || hs === "long") { g.beginPath(); g.moveTo(HX - HR - 10, HY - 50); g.quadraticCurveTo(HX - 60, HY - 120, HX + (hs === "side" ? -20 : 30), HY - 96); g.quadraticCurveTo(HX + 90, HY - 130, HX + HR + 10, HY - 40); g.lineTo(HX + HR + 10, HY - HR - 20); g.lineTo(HX - HR - 10, HY - HR - 20); g.fill(); }
  if (hs === "curly") for (let i = 0; i < 9; i++) { g.beginPath(); g.arc(HX - 150 + i * 37, HY - 128 + Math.abs(i - 4) * 12, 40, 0, 7); g.fill(); }
  if (hs === "bun") { g.beginPath(); g.moveTo(HX - HR - 10, HY - 34); g.quadraticCurveTo(HX, HY - 150, HX + HR + 10, HY - 34); g.lineTo(HX + HR + 10, HY - HR - 20); g.lineTo(HX - HR - 10, HY - HR - 20); g.fill(); }
  if (hs === "wig") { g.beginPath(); g.moveTo(HX - HR - 10, HY - 30); g.quadraticCurveTo(HX - 40, HY - 140, HX + 20, HY - 110); g.quadraticCurveTo(HX + 110, HY - 140, HX + HR + 10, HY - 30); g.lineTo(HX + HR + 10, HY - HR - 20); g.lineTo(HX - HR - 10, HY - HR - 20); g.fill(); }
  g.restore();
  if (hs !== "none" && hs !== "bald" && hs !== "tufts" && hs !== "balding") { clipHead(); g.strokeStyle = OL; g.lineWidth = 8; g.stroke(); }
  if (hs === "tufts" || hs === "balding") for (const side of [-1, 1]) {   // side tufts over the ears, like a professor
    g.beginPath(); g.moveTo(HX + side * (HR - 30), HY - 70); g.quadraticCurveTo(HX + side * (HR + 34), HY - 40, HX + side * (HR + 18), HY + 10); g.quadraticCurveTo(HX + side * (HR + 30), HY + 40, HX + side * (HR - 4), HY + 52); g.quadraticCurveTo(HX + side * (HR - 30), HY - 10, HX + side * (HR - 30), HY - 70); fillStroke(g, hc, 6);
  }
}

// ---------- body ----------
CS.drawRound = function (g, spec, st) {
  const skin = spec.skin || "#fbfaf5", top = spec.top || {}, tc = top.color || "#4f7fb8", shoes = spec.shoes || "#2a2226", hand = spec.hand || "#ffffff";
  const stride = st.stride ?? 0, ph = (st.step || 0) * Math.PI * 2, swing = Math.sin(ph) * 24 * stride * D2R, jump = st.jump || 0;
  const tt = top.type || "coat", dress = tt === "dress", long = tt === "coat" || tt === "smock" || dress || tt === "robe" || tt === "redcoat";
  const nk = 440, bot = dress ? 940 : tt === "robe" ? 955 : long ? 800 : 760, wt = 92, wb = dress ? 165 : tt === "robe" ? 150 : long ? 128 : 112;
  // legs (thin sticks) + small shoes
  const hipY = bot - 30;
  if (!dress && tt !== "robe") for (const side of [-1, 1]) {
    const a = side * swing + (jump ? side * -.25 : 0), len = 958 - hipY - 12 - jump * 30;
    const x0 = HX + side * 36, x1 = x0 + Math.sin(a) * len, y1 = hipY + Math.cos(a) * len - (side * Math.sin(ph) > 0 ? Math.abs(Math.sin(ph)) * 16 * stride : 0);
    if (spec.pants) { line(g, [x0, hipY, x1, y1], OL, 30); line(g, [x0, hipY, x1, y1], spec.pants, 18); } else line(g, [x0, hipY, x1, y1], OL, 11);
    g.beginPath(); g.ellipse(x1 + side * 14, y1 + 6, 30, 15, 0, 0, 7); fillStroke(g, shoes, 6);
  }
  // torso
  g.beginPath(); g.moveTo(HX - wt * .62, nk); g.quadraticCurveTo(HX - wt, nk + 20, HX - wb, bot); g.lineTo(HX + wb, bot); g.quadraticCurveTo(HX + wt, nk + 20, HX + wt * .62, nk); g.closePath();
  g.fillStyle = tc; g.fill(); CS.draw.celShade(g, HX - wb, nk + 170, wb * 2, 240, tc, -.14); g.strokeStyle = OL; g.lineWidth = 8; g.stroke();
  g.lineWidth = 6; g.strokeStyle = OL;
  const ac = top.accent || shade(tc, -.3);
  if (tt === "coat" || tt === "suit") {
    g.fillStyle = top.shirt || "#f6f3ea"; g.beginPath(); g.moveTo(HX - 40, nk); g.lineTo(HX, nk + 120); g.lineTo(HX + 40, nk); g.fill(); g.stroke();
    if (top.vest) { g.fillStyle = top.vest; g.beginPath(); g.moveTo(HX - 40, nk + 40); g.lineTo(HX, nk + 120); g.lineTo(HX + 40, nk + 40); g.lineTo(HX + 46, nk + 230); g.lineTo(HX - 46, nk + 230); g.closePath(); g.fill(); g.stroke(); }
    for (let i = 0; i < 3; i++) { g.beginPath(); g.arc(HX, nk + 150 + i * 46, 7, 0, 7); g.fillStyle = top.vest ? "#e8c048" : ac; g.fill(); g.stroke(); }
  } else if (tt === "uniform" || tt === "redcoat") {
    for (let i = 0; i < 4; i++) { g.beginPath(); g.arc(HX, nk + 60 + i * 50, 7, 0, 7); g.fillStyle = "#e8c048"; g.fill(); g.stroke(); }
    g.fillStyle = top.belt || "#3a2a20"; g.fillRect(HX - wb + 8, bot - 90, wb * 2 - 16, 22); g.strokeRect(HX - wb + 8, bot - 90, wb * 2 - 16, 22);
    if (top.trim) { g.fillStyle = top.trim; g.fillRect(HX - 26, nk, 52, bot - nk - 90); g.strokeRect(HX - 26, nk, 52, bot - nk - 90); for (let i = 0; i < 4; i++) { g.beginPath(); g.arc(HX, nk + 60 + i * 50, 7, 0, 7); g.fillStyle = "#e8c048"; g.fill(); g.stroke(); } }
  } else if (tt === "smock") {
    g.fillStyle = top.apron || "#f6f3ea"; g.beginPath(); g.roundRect(HX - 70, nk + 90, 140, bot - nk - 100, 12); g.fill(); g.stroke();
  } else if (tt === "dress") {
    g.fillStyle = ac; g.fillRect(HX - 70, nk + 150, 140, 18);
  } else if (tt === "robe") {
    g.fillStyle = top.trim || "#f4f0e6"; g.fillRect(HX - 18, nk + 10, 36, bot - nk - 14); g.strokeRect(HX - 18, nk + 10, 36, bot - nk - 14);
    for (let i = 0; i < 6; i++) { g.beginPath(); g.arc(HX - 6 + (i % 2) * 12, nk + 30 + i * 70, 5, 0, 7); g.fillStyle = OL; g.fill(); }
  } else {   // shirt / sweater
    g.beginPath(); g.moveTo(HX - 34, nk); g.lineTo(HX, nk + 42); g.lineTo(HX + 34, nk); g.fillStyle = shade(tc, .25); g.fill(); g.stroke();
  }
  if (top.tie) {   // bow tie under the chin
    g.fillStyle = top.tie; g.beginPath(); g.moveTo(HX, nk + 14); g.lineTo(HX - 34, nk - 4); g.lineTo(HX - 34, nk + 32); g.closePath(); g.moveTo(HX, nk + 14); g.lineTo(HX + 34, nk - 4); g.lineTo(HX + 34, nk + 32); g.closePath(); g.fill(); g.stroke();
    g.beginPath(); g.arc(HX, nk + 14, 9, 0, 7); g.fill(); g.stroke();
  }
  if (spec.medal) { g.beginPath(); g.arc(HX - 55, nk + 110, 14, 0, 7); g.fillStyle = "#e8c048"; g.fill(); g.stroke(); }
  // arms: thin sticks from the shoulders, white mitten hands
  const arms = st.arms || ["hang", "hang"], wav = st.wave || 0, hands = [];
  for (let i = 0; i < 2; i++) {
    const side = i === 0 ? -1 : 1, p = Array.isArray(arms[i]) ? arms[i] : CS.ARMS[arms[i]] || CS.ARMS.hang;
    const a = (p[0] + (arms[i] === "wave" ? Math.sin(wav * Math.PI * 2) * 18 : 0)) * D2R, b = p[1] * D2R;
    const sx = HX + side * (wt * .66), sy = nk + 46;
    const ex = sx + side * Math.sin(a) * 118, ey = sy + Math.cos(a) * 118;
    const fx = ex + side * Math.sin(a + b) * 112, fy = ey + Math.cos(a + b) * 112;
    line(g, [sx, sy, ex, ey, fx, fy], OL, 11);
    hands.push([fx, fy, side, a + b]);
  }
  // head
  hairBack(g, spec);
  g.beginPath(); g.arc(HX, HY, HR, 0, 7); g.fillStyle = skin; g.fill(); CS.draw.celShade(g, HX - HR, HY + 50, HR * 2, 220, skin, -.07);
  g.beginPath(); g.arc(HX, HY, HR, 0, 7); g.strokeStyle = OL; g.lineWidth = 8; g.stroke();
  hairFront(g, spec);
  CS.drawDotFace(g, HX, HY + 18, st, skin);
  if (spec.nose === "big") { g.beginPath(); g.ellipse(HX, HY + 52, 22, 18, 0, 0, 7); fillStroke(g, shade(skin, -.05), 6); }
  if (spec.glasses) { g.lineWidth = 6; g.strokeStyle = OL; for (const s of [-1, 1]) { g.beginPath(); g.arc(HX + s * 54, HY + 14, 40, 0, 7); g.stroke(); } g.beginPath(); g.moveTo(HX - 14, HY + 14); g.lineTo(HX + 14, HY + 14); g.stroke(); }
  if (spec.monocle) { g.lineWidth = 6; g.strokeStyle = "#c8962e"; g.beginPath(); g.arc(HX + 54, HY + 14, 38, 0, 7); g.stroke(); line(g, [HX + 70, HY + 50, HX + 96, HY + 190], "#c8962e", 4); }
  const mc = spec.mustacheColor || spec.hair?.color || "#5a3a26";
  if (spec.mustache) {
    g.fillStyle = mc; g.beginPath(); const my = HY + 70;
    if (spec.mustache === "handlebar") { g.moveTo(HX, my); g.bezierCurveTo(HX - 36, my - 14, HX - 80, my + 14, HX - 86, my - 14); g.bezierCurveTo(HX - 72, my + 30, HX - 26, my + 26, HX, my + 14); g.bezierCurveTo(HX + 26, my + 26, HX + 72, my + 30, HX + 86, my - 14); g.bezierCurveTo(HX + 80, my + 14, HX + 36, my - 14, HX, my); }
    else { g.ellipse(HX - 26, my + 6, 32, 14, -.15, 0, 7); g.ellipse(HX + 26, my + 6, 32, 14, .15, 0, 7); }
    g.fill(); g.lineWidth = 5; g.strokeStyle = OL; g.stroke();
  }
  if (spec.beard) { g.beginPath(); g.moveTo(HX - 120, HY + 60); g.quadraticCurveTo(HX - 100, HY + 190, HX, HY + 214); g.quadraticCurveTo(HX + 100, HY + 190, HX + 120, HY + 60); g.quadraticCurveTo(HX, HY + 140, HX - 120, HY + 60); fillStroke(g, spec.beardColor || mc, 6); }
  if (spec.hat) CS.drawHat(g, HX, HY + 6 + (spec.hat.drop || 0), spec.hat);
  // hands and held props last, so a hand raised to the face stays in front of it
  for (let i = 0; i < 2; i++) {
    const [x, y, side, ang] = hands[i], name = arms[i];
    if (st.prop && (st.prop.hand === "L" ? 0 : 1) === i && CS.PROPS[st.prop.kind]) CS.PROPS[st.prop.kind](g, x, y, side, ang, st.prop);
    g.beginPath(); g.ellipse(x, y, 27, 30, ang * side * .3, 0, 7); fillStroke(g, hand, 6);       // mitten
    g.beginPath(); g.ellipse(x - side * 22, y - 10, 11, 15, -side * .6, 0, 7); fillStroke(g, hand, 5);   // thumb
    if (name === "thumb") { g.beginPath(); g.roundRect(x - 8, y - 52, 16, 32, 8); fillStroke(g, hand, 5); }
    if (name === "point") { g.beginPath(); g.roundRect(x + side * 16 - (side < 0 ? 40 : 0), y - 8, 40, 16, 8); fillStroke(g, hand, 5); }
  }
};

// ---------- extra hats ----------
const baseHat = CS.drawHat;
CS.drawHat = function (g, hx, hy, h) {
  const c = h.color || "#2a2226", band = h.band || shade(c, -.35);
  if (h.type === "tricorn") {      // 18th-century three-cornered hat
    g.beginPath(); g.moveTo(hx - 120, hy - 125); g.bezierCurveTo(hx - 110, hy - 250, hx + 110, hy - 250, hx + 120, hy - 125); g.closePath(); fillStroke(g, c);
    g.beginPath(); g.moveTo(hx - 230, hy - 150); g.quadraticCurveTo(hx - 130, hy - 92, hx, hy - 104); g.quadraticCurveTo(hx + 130, hy - 92, hx + 230, hy - 150); g.quadraticCurveTo(hx + 140, hy - 132, hx + 110, hy - 200); g.quadraticCurveTo(hx, hy - 150, hx - 110, hy - 200); g.quadraticCurveTo(hx - 140, hy - 132, hx - 230, hy - 150); g.closePath(); fillStroke(g, c);
    if (h.trim !== false) { g.beginPath(); g.moveTo(hx - 226, hy - 150); g.quadraticCurveTo(hx - 130, hy - 92, hx, hy - 104); g.quadraticCurveTo(hx + 130, hy - 92, hx + 226, hy - 150); g.strokeStyle = h.trim || "#e8c048"; g.lineWidth = 9; g.stroke(); }
    return;
  }
  if (h.type === "crown") {
    g.beginPath(); g.moveTo(hx - 120, hy - 120); g.lineTo(hx - 130, hy - 250); g.lineTo(hx - 66, hy - 190); g.lineTo(hx, hy - 270); g.lineTo(hx + 66, hy - 190); g.lineTo(hx + 130, hy - 250); g.lineTo(hx + 120, hy - 120); g.closePath(); fillStroke(g, h.color || "#f2c230");
    for (const [x, y, col] of [[-66, -150, "#d23a4a"], [0, -158, "#3a7ad2"], [66, -150, "#3ab06a"]]) { g.beginPath(); g.arc(hx + x, hy + y, 15, 0, 7); fillStroke(g, col, 5); }
    for (const [x, y] of [[-130, -250], [0, -270], [130, -250]]) { g.beginPath(); g.arc(hx + x, hy + y, 12, 0, 7); fillStroke(g, "#fff3c0", 5); }
    return;
  }
  if (h.type === "nurse") { g.beginPath(); g.roundRect(hx - 110, hy - 230, 220, 90, 18); fillStroke(g, "#fff"); line(g, [hx, hy - 210, hx, hy - 160], "#d23a4a", 12); line(g, [hx - 25, hy - 185, hx + 25, hy - 185], "#d23a4a", 12); return; }
  baseHat(g, hx, hy, h);
};

// ---------- extra hand props ----------
Object.assign(CS.PROPS, {
  watch(g, x, y, side, a, o) { const cx = x + side * 4, cy = y - 58, r = o.r || 54; line(g, [x, y, cx, cy - r], "#c8962e", 5);
    g.beginPath(); g.arc(cx, cy, r, 0, 7); fillStroke(g, "#e8b93c", 7); g.beginPath(); g.arc(cx, cy, r * .78, 0, 7); fillStroke(g, "#fffaf0", 5);
    g.strokeStyle = OL; g.lineWidth = 3; for (let i = 0; i < 12; i++) { const q = i / 12 * Math.PI * 2; g.beginPath(); g.moveTo(cx + Math.sin(q) * r * .62, cy - Math.cos(q) * r * .62); g.lineTo(cx + Math.sin(q) * r * .7, cy - Math.cos(q) * r * .7); g.stroke(); }
    const hr = (o.hours ?? 10.1) / 12 * Math.PI * 2; line(g, [cx, cy, cx + Math.sin(hr) * r * .4, cy - Math.cos(hr) * r * .4], OL, 6); const mn = (o.hours ?? 10.1) % 1 * Math.PI * 2; line(g, [cx, cy, cx + Math.sin(mn) * r * .6, cy - Math.cos(mn) * r * .6], OL, 4); },
  phone(g, x, y, side, a, o) { g.save(); g.translate(x, y - 70); g.beginPath(); g.roundRect(-46, -86, 92, 172, 16); fillStroke(g, "#2a2a33", 6); g.fillStyle = o.screen || "#bfe3c8"; g.fillRect(-36, -72, 72, 144);
    g.strokeStyle = "#ffffff"; g.lineWidth = 6; g.beginPath(); g.moveTo(-36, 10); g.lineTo(36, -20); g.moveTo(-10, -72); g.lineTo(6, 72); g.stroke();
    g.fillStyle = "#e5484d"; g.beginPath(); g.arc(0, -12, 15, Math.PI, 0); g.lineTo(0, 16); g.closePath(); g.fill(); g.fillStyle = "#fff"; g.beginPath(); g.arc(0, -12, 6, 0, 7); g.fill(); g.restore(); },
  scroll(g, x, y, side, a, o) { g.save(); g.translate(x - side * 30, y - 110); g.beginPath(); g.rect(-80, -10, 160, 200); fillStroke(g, "#f4ead2", 6); g.fillStyle = OL; for (let i = 0; i < 6; i++) g.fillRect(-58, 20 + i * 26, i % 3 === 2 ? 70 : 116, 7);
    if (o.text) { g.font = "900 34px Georgia, serif"; g.textAlign = "center"; g.fillText(o.text, 0, 10 + 0); } g.beginPath(); g.ellipse(0, -10, 90, 14, 0, 0, 7); fillStroke(g, "#e6d8b6", 5); g.beginPath(); g.ellipse(0, 190, 90, 14, 0, 0, 7); fillStroke(g, "#e6d8b6", 5); g.restore(); },
  book(g, x, y, side) { g.save(); g.translate(x, y - 40); g.rotate(side * .1); g.beginPath(); g.rect(-70, -50, 140, 100); fillStroke(g, "#8a2e3a", 6); g.fillStyle = "#e8c048"; g.fillRect(-40, -12, 80, 10); g.restore(); },
  bowl(g, x, y, side) { g.beginPath(); g.ellipse(x - side * 50, y - 30, 80, 20, 0, 0, 7); fillStroke(g, "#cfe6f2", 6); g.beginPath(); g.moveTo(x - side * 50 - 80, y - 30); g.quadraticCurveTo(x - side * 50, y + 50, x - side * 50 + 80, y - 30); fillStroke(g, "#f4f4f4", 6); },
  chalk(g, x, y) { g.beginPath(); g.roundRect(x - 6, y - 40, 12, 34, 4); fillStroke(g, "#ffffff", 4); },
});

// ---------- hook into CS.person ----------
const basePerson = CS.person;
CS.person = function (spec, o = {}) {
  if (spec.style !== "round") return basePerson(spec, o);
  const design = "round:" + JSON.stringify(spec);
  const c = CS.card({ cw: 600, ch: 1000, h: (o.h || 2.1) * (spec.size || 1), scale: o.scale ?? 2, design, name: o.name, parent: o.parent, draw: (g, st) => CS.drawRound(g, spec, st) });
  c.spec = spec; c.pose = st => c.set(st); return c;
};
})();
