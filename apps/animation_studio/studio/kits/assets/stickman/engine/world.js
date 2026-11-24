/* Stickman Shorts engine: the world. Skies, sun, clouds, hills, meadows, rooms, space, sea, mountains, props, bubbles,
   zoom circles and cartoon effects. Pure functions of time: the same t always draws the same picture. Free from Anylancer.com. */
(function () {
const CS = window.CS = window.CS || {};
const { rand, clamp, lerp, ease } = CS;
const INK = CS.INK, fs = CS.fs;
const W = () => CS.W, H = () => CS.H;

// ---------- sky + light ----------
CS.sky = function (g, top = "#5cc4ff", bottom = "#d9f4ff", x = -400, y = -400, w = 1880, h = 2720) {
  const gr = g.createLinearGradient(0, y, 0, y + h * .6); gr.addColorStop(0, top); gr.addColorStop(1, bottom); g.fillStyle = gr; g.fillRect(x, y, w, h);
};
CS.sun = function (g, x, y, r, t, o = {}) {
  g.save(); g.translate(x, y); g.rotate(t * (o.spin ?? .12));
  const n = o.rays ?? 14, gl = g.createRadialGradient(0, 0, r * .6, 0, 0, r * 4);
  gl.addColorStop(0, "rgba(255,250,215,.85)"); gl.addColorStop(1, "rgba(255,250,215,0)");
  g.fillStyle = gl; g.beginPath(); g.arc(0, 0, r * 4, 0, 7); g.fill();
  g.fillStyle = "rgba(255,255,240,.42)";
  for (let i = 0; i < n; i++) { const a = i / n * Math.PI * 2; g.beginPath(); g.moveTo(Math.cos(a - .07) * r * 1.2, Math.sin(a - .07) * r * 1.2); g.lineTo(Math.cos(a) * r * 3.6, Math.sin(a) * r * 3.6); g.lineTo(Math.cos(a + .07) * r * 1.2, Math.sin(a + .07) * r * 1.2); g.fill(); }
  g.restore();
  CS.circle(g, x, y, r, o.color || "#ffe14d", o.lw ?? 0);
  CS.circle(g, x, y, r * .78, "#fff59a", 0);
  if (o.face) CS.drawFace(g, x, y, r * .8, { face: o.face, t });
};
CS.cloud = function (g, x, y, s = 1, o = {}) {
  g.save(); g.translate(x, y); g.scale(s, s);
  const p = () => { g.beginPath(); g.moveTo(-150, 40); g.arc(-90, 10, 62, Math.PI * .8, Math.PI * 1.6); g.arc(-10, -30, 80, Math.PI * 1.12, Math.PI * 1.9); g.arc(80, 0, 64, Math.PI * 1.35, Math.PI * .2); g.quadraticCurveTo(150, 52, 90, 54); g.lineTo(-120, 54); g.quadraticCurveTo(-170, 52, -150, 40); g.closePath(); };
  p(); g.fillStyle = o.color || "#fff"; g.fill();
  g.save(); p(); g.clip(); g.fillStyle = o.shade || "rgba(120,170,220,.25)"; g.fillRect(-200, 26, 400, 60); g.restore();
  p(); g.lineWidth = o.lw ?? 7; g.strokeStyle = o.ink || INK; g.stroke(); g.restore();
};
// drifting clouds across the sky; list of [x, y, s]
CS.clouds = function (g, t, list, speed = 14) { for (const [x, y, s] of list) CS.cloud(g, ((x + t * speed * s) % 1900 + 1900) % 1900 - 400, y, s); };
// wavy hills: CS.hills(g, y, colour, {amp, freq, seed, lw})
CS.hills = function (g, y, color, o = {}) {
  const amp = o.amp ?? 60, f = o.freq ?? .004, sd = o.seed ?? 1, x0 = -500, x1 = 1600;
  g.beginPath(); g.moveTo(x0, y + 2000);
  for (let x = x0; x <= x1; x += 20) g.lineTo(x, y - amp * (Math.sin(x * f + sd) * .6 + Math.sin(x * f * 2.3 + sd * 3) * .4));
  g.lineTo(x1, y + 2000); g.closePath(); fs(g, color, o.lw ?? 7);
};
// meadow ground with grass tufts and flowers from y down
CS.meadow = function (g, y, t, o = {}) {
  const c = o.color || "#5fcf4f";
  g.beginPath(); g.moveTo(-500, y); for (let x = -500; x <= 1600; x += 40) g.lineTo(x, y + Math.sin(x * .006) * 10); g.lineTo(1600, 3000); g.lineTo(-500, 3000); g.closePath();
  const gr = g.createLinearGradient(0, y, 0, y + 900); gr.addColorStop(0, c); gr.addColorStop(1, CS.shade(c, -.12)); g.fillStyle = gr; g.fill(); g.lineWidth = 7; g.strokeStyle = INK; g.stroke();
  const n = o.n ?? 70, sd = o.seed ?? 5;
  for (let i = 0; i < n; i++) {
    const x = -300 + rand(sd + i * 4) * 1700, yy = y + 40 + Math.pow(rand(sd + i * 4 + 1), .8) * 1100, k = .6 + (yy - y) / 1100;
    if (rand(sd + i * 4 + 2) < .55) {   // grass tuft
      g.strokeStyle = CS.shade(c, -.3); g.lineWidth = 4 * k; g.lineCap = "round"; g.beginPath();
      for (const dx of [-8, 0, 8]) { g.moveTo(x + dx * k, yy); g.lineTo(x + dx * 1.8 * k + Math.sin(t * 2 + i) * 2, yy - (18 + (dx === 0 ? 10 : 0)) * k); }
      g.stroke();
    } else {                              // flower
      const col = ["#ff7eb6", "#ffd23a", "#ffffff", "#b78cff", "#ff6b4a"][i % 5], r = 9 * k, sw = Math.sin(t * 1.6 + i) * 3;
      CS.seg2(g, x, yy, x + sw, yy - 26 * k, 4 * k, "#2f8a3a");
      for (let p = 0; p < 5; p++) { const a = p / 5 * Math.PI * 2; CS.circle(g, x + sw + Math.cos(a) * r, yy - 26 * k + Math.sin(a) * r, r * .75, col, 3 * k); }
      CS.circle(g, x + sw, yy - 26 * k, r * .6, "#ffb000", 3 * k);
    }
  }
};
// the standard sunny outdoor stage (sky, sun, clouds, two hill layers, meadow); camera is applied outside
CS.sunnyDay = function (g, t, o = {}) {
  CS.sky(g, o.top || "#4fbaff", o.bottom || "#d7f3ff");
  CS.sun(g, o.sunX ?? 190, o.sunY ?? 260, 95, t, { face: o.sunFace });
  CS.clouds(g, t, o.clouds || [[300, 330, .9], [980, 220, .7], [1500, 420, .6]]);
  CS.hills(g, o.hillY ?? 1060, o.hill1 || "#9be37d", { amp: 70, seed: 2 });
  CS.hills(g, (o.hillY ?? 1060) + 110, o.hill2 || "#76d45f", { amp: 50, seed: 7, freq: .005 });
  CS.meadow(g, o.groundY ?? 1250, t, { color: o.ground });
};

// ---------- indoors ----------
// CS.kitchen(g, t, {wall, tile}) back wall with tiles, window, shelf, counter top at y = counterY
CS.kitchen = function (g, t, o = {}) {
  const wall = o.wall || "#ffe7a8", tile = o.tile || "#fff4d6", cy = o.counterY ?? 1240;
  g.fillStyle = wall; g.fillRect(-500, -500, 2100, 3000);
  g.strokeStyle = CS.shade(wall, -.1); g.lineWidth = 4;
  for (let y = 600; y < cy; y += 90) for (let x = -480 + ((y / 90) % 2) * 45; x < 1600; x += 90) { g.strokeRect(x, y, 90, 90); }
  // window
  CS.rrect(g, 640, 250, 330, 300, 18, "#8fdcff", 9);
  g.save(); g.beginPath(); g.roundRect(640, 250, 330, 300, 18); g.clip(); CS.cloud(g, 760 + Math.sin(t * .3) * 20, 380, .55); CS.hills(g, 520, "#8ee070", { amp: 30, lw: 5 }); g.restore();
  CS.seg2(g, 805, 250, 805, 550, 9); CS.seg2(g, 640, 400, 970, 400, 9);
  CS.rrect(g, 620, 540, 370, 30, 8, "#ffffff", 8);
  // shelf with jars
  CS.rrect(g, 90, 430, 380, 26, 6, "#c98a55", 7);
  [["#ff6b4a", 130], ["#5fcf4f", 230], ["#3a7bff", 340]].forEach(([c, x], i) => { CS.rrect(g, x, 330 - i * 6, 80, 100 + i * 6, 16, c, 7); CS.rrect(g, x - 4, 320 - i * 6, 88, 24, 8, "#fff", 6); });
  // counter
  CS.rrect(g, -500, cy, 2100, 60, 0, "#ffffff", 9);
  g.fillStyle = "#e16b3a"; g.fillRect(-500, cy + 60, 2100, 2000); g.strokeStyle = INK; g.lineWidth = 9; g.beginPath(); g.moveTo(-500, cy + 60); g.lineTo(1600, cy + 60); g.stroke();
  for (let x = -260; x < 1600; x += 360) { CS.rrect(g, x, cy + 120, 320, 520, 16, CS.shade("#e16b3a", .1), 7); CS.rrect(g, x + 130, cy + 160, 60, 18, 9, "#ffd23a", 5); }
};
// plain studio backdrop with a soft radial light
CS.backdrop = function (g, c1 = "#fff3c2", c2 = "#ffc65a", cx = 540, cy = 860) {
  const gr = g.createRadialGradient(cx, cy, 80, cx, cy, 1400); gr.addColorStop(0, c1); gr.addColorStop(1, c2); g.fillStyle = gr; g.fillRect(-600, -600, 2300, 3200);
};

// ---------- space ----------
CS.space = function (g, t, o = {}) {
  const gr = g.createRadialGradient(540, 900, 100, 540, 900, 1600); gr.addColorStop(0, o.c1 || "#2b2060"); gr.addColorStop(1, o.c2 || "#0b0a22"); g.fillStyle = gr; g.fillRect(-600, -600, 2300, 3200);
  for (let i = 0; i < (o.n || 220); i++) {
    const x = -300 + rand(i * 3 + 7) * 1700, y = -300 + rand(i * 3 + 8) * 2500, r = 1.5 + rand(i * 3 + 9) * 3.5, tw = .55 + .45 * Math.sin(t * 3 + i);
    g.globalAlpha = tw; g.fillStyle = i % 9 ? "#ffffff" : "#ffd98a"; g.beginPath(); g.arc(x, y, r, 0, 7); g.fill();
    if (r > 4.4) { g.strokeStyle = "#fff"; g.lineWidth = 2; g.beginPath(); g.moveTo(x - r * 3, y); g.lineTo(x + r * 3, y); g.moveTo(x, y - r * 3); g.lineTo(x, y + r * 3); g.stroke(); }
  }
  g.globalAlpha = 1;
};
CS.planet = function (g, x, y, r, c, o = {}) {
  if (o.ring) { g.beginPath(); g.ellipse(x, y, r * 1.8, r * .45, -.3, Math.PI, Math.PI * 2); g.lineWidth = r * .16; g.strokeStyle = INK; g.stroke(); g.lineWidth = r * .1; g.strokeStyle = o.ring; g.stroke(); }
  CS.circle(g, x, y, r, c, 7);
  g.save(); g.beginPath(); g.arc(x, y, r - 3, 0, 7); g.clip(); g.fillStyle = CS.shade(c, -.25); g.beginPath(); g.arc(x + r * .5, y + r * .4, r, 0, 7); g.fill();
  for (let i = 0; i < 3; i++) { g.fillStyle = CS.shade(c, .2); g.beginPath(); g.ellipse(x - r * .3 + i * r * .25, y - r * .4 + i * r * .35, r * .25, r * .1, -.3, 0, 7); g.fill(); }
  g.restore(); CS.circle(g, x, y, r, null, 7);
  if (o.ring) { g.beginPath(); g.ellipse(x, y, r * 1.8, r * .45, -.3, 0, Math.PI); g.lineWidth = r * .16; g.strokeStyle = INK; g.stroke(); g.lineWidth = r * .1; g.strokeStyle = o.ring; g.stroke(); }
};
// a cartoon black hole: swirling orange disk, dark centre, a lensing ring
CS.blackHole = function (g, x, y, r, t, o = {}) {
  g.save(); g.translate(x, y);
  const gl = g.createRadialGradient(0, 0, r * .8, 0, 0, r * 3.2); gl.addColorStop(0, "rgba(255,150,60,.55)"); gl.addColorStop(1, "rgba(255,120,60,0)"); g.fillStyle = gl; g.beginPath(); g.arc(0, 0, r * 3.2, 0, 7); g.fill();
  g.scale(1, o.tilt ?? .42);
  for (let i = 0; i < 7; i++) {
    const rr = r * (2.6 - i * .22); g.save(); g.rotate(t * (1.2 + i * .35) + i);
    g.beginPath(); g.arc(0, 0, rr, 0, Math.PI * 1.55); g.lineWidth = r * .2; g.strokeStyle = ["#ff5d2e", "#ff8a2e", "#ffb347", "#ffd36b", "#fff0a8", "#ffb347", "#ff8a2e"][i]; g.lineCap = "round"; g.stroke(); g.restore();
  }
  g.restore();
  CS.circle(g, x, y, r * 1.02, "#ffe9a8", 0); CS.circle(g, x, y, r * .92, "#07050f", 8);
  g.save(); g.translate(x, y); g.scale(1, o.tilt ?? .42); g.beginPath(); g.arc(0, 0, r * 2.2, 0, Math.PI); g.lineWidth = r * .22; g.strokeStyle = "#ffb347"; g.stroke(); g.beginPath(); g.arc(0, 0, r * 1.7, 0, Math.PI); g.lineWidth = r * .14; g.strokeStyle = "#fff0a8"; g.stroke(); g.restore();
};

// ---------- sea, shore, mountains, weather ----------
CS.sea = function (g, y, t, o = {}) {
  const c = o.color || "#2fa8e8";
  const gr = g.createLinearGradient(0, y, 0, y + 1200); gr.addColorStop(0, CS.shade(c, .15)); gr.addColorStop(1, CS.shade(c, -.25)); g.fillStyle = gr;
  g.beginPath(); g.moveTo(-500, y); for (let x = -500; x <= 1600; x += 20) g.lineTo(x, y + Math.sin(x * .02 + t * 2.4) * 8); g.lineTo(1600, 3000); g.lineTo(-500, 3000); g.closePath(); g.fill(); g.lineWidth = 7; g.strokeStyle = INK; g.stroke();
  g.strokeStyle = "rgba(255,255,255,.7)"; g.lineWidth = 6; g.lineCap = "round";
  for (let i = 0; i < 26; i++) { const yy = y + 50 + rand(i * 5 + 3) * 900, x = ((rand(i * 5 + 4) * 1800 + t * 30 * (1 + yy / 1500)) % 1900) - 400, w = 40 + (yy - y) * .08; g.beginPath(); g.moveTo(x, yy); g.quadraticCurveTo(x + w / 2, yy - 12, x + w, yy); g.stroke(); }
};
CS.mountain = function (g, x, y, w, h, c = "#8a7ad8", snow = true) {
  g.beginPath(); g.moveTo(x - w / 2, y); g.lineTo(x - w * .08, y - h); g.lineTo(x + w * .06, y - h * .92); g.lineTo(x + w / 2, y); g.closePath(); fs(g, c, 7);
  g.save(); g.beginPath(); g.moveTo(x - w / 2, y); g.lineTo(x - w * .08, y - h); g.lineTo(x + w * .06, y - h * .92); g.lineTo(x + w / 2, y); g.closePath(); g.clip(); g.fillStyle = CS.shade(c, -.18); g.beginPath(); g.moveTo(x - w * .08, y - h); g.lineTo(x + w / 2, y); g.lineTo(x + w * .1, y); g.closePath(); g.fill(); g.restore();
  if (snow) { g.beginPath(); g.moveTo(x - w * .2, y - h * .72); g.lineTo(x - w * .08, y - h); g.lineTo(x + w * .06, y - h * .92); g.lineTo(x + w * .17, y - h * .7); g.lineTo(x + w * .06, y - h * .76); g.lineTo(x - w * .04, y - h * .68); g.lineTo(x - w * .12, y - h * .76); g.closePath(); fs(g, "#fff", 6); }
};
CS.rock = function (g, x, y, s = 1, c = "#a99d93", seed = 1) {
  g.save(); g.translate(x, y); g.scale(s, s); g.beginPath();
  const n = 9; for (let i = 0; i <= n; i++) { const a = Math.PI + i / n * Math.PI, r = 70 + rand(seed + i) * 26; g.lineTo(Math.cos(a) * r * 1.3, Math.sin(a) * r * .9); }
  g.closePath(); fs(g, c, 7); g.fillStyle = CS.shade(c, -.15); g.beginPath(); g.ellipse(30, -20, 40, 18, -.3, 0, 7); g.fill(); g.restore();
};
// falling raindrops inside a box [x0, y0, x1, y1]
CS.rainDrops = function (g, t, box, o = {}) {
  const [x0, y0, x1, y1] = box, n = o.n || 40, sp = o.speed || 900;
  for (let i = 0; i < n; i++) { const x = x0 + rand(i * 7 + 1) * (x1 - x0), y = y0 + ((rand(i * 7 + 2) * (y1 - y0) + t * sp) % (y1 - y0)); CS.drop(g, x, y, o.r || 11, 4); }
};

// ---------- props ----------
CS.onion = function (g, x, y, s = 1, o = {}) {       // o.cut: 0 = whole, 1 = cut in half (cross-section)
  g.save(); g.translate(x, y); g.scale(s, s); g.rotate(o.rot || 0);
  if (!o.cut) {
    g.beginPath(); g.moveTo(0, -120); g.bezierCurveTo(30, -70, 110, -60, 105, 10); g.bezierCurveTo(100, 80, -100, 80, -105, 10); g.bezierCurveTo(-110, -60, -30, -70, 0, -120); g.closePath(); fs(g, o.color || "#b36adb", 8);
    g.strokeStyle = CS.shade(o.color || "#b36adb", -.25); g.lineWidth = 5; for (const k of [-.5, 0, .5]) { g.beginPath(); g.moveTo(0, -110); g.quadraticCurveTo(k * 140, 0, k * 30, 62); g.stroke(); }
    g.beginPath(); g.moveTo(0, -118); g.quadraticCurveTo(-6, -150, 12, -170); g.lineWidth = 9; g.strokeStyle = "#7a5a2e"; g.stroke();
    for (let i = -2; i <= 2; i++) CS.seg2(g, i * 10, 66, i * 16, 86, 4, "#c9a26b");
  } else {
    CS.ell(g, 0, 0, 110, 90, 0, "#f7eefc", 8);
    for (let i = 1; i < 5; i++) CS.ell(g, 0, 10 * i / 4, 110 - i * 22, 90 - i * 18, 0, null, 4);
    g.strokeStyle = o.color || "#b36adb"; g.lineWidth = 10; g.beginPath(); g.ellipse(0, 0, 104, 84, 0, 0, 7); g.stroke(); CS.ell(g, 0, 0, 110, 90, 0, null, 8);
  }
  if (o.face) CS.drawFace(g, 0, o.cut ? 0 : -10, 62, { face: o.face, t: o.t, blink: o.blink });
  g.restore();
};
CS.knife = function (g, x, y, ang = 0, s = 1) {
  g.save(); g.translate(x, y); g.rotate(ang); g.scale(s, s);
  CS.rrect(g, -18, -12, 90, 26, 10, "#7a4a2a", 6);
  g.beginPath(); g.moveTo(70, -14); g.lineTo(250, -14); g.quadraticCurveTo(260, 10, 230, 22); g.lineTo(70, 22); g.closePath(); fs(g, "#e4ebf2", 6);
  CS.seg2(g, 90, -4, 220, -4, 5, "rgba(255,255,255,.9)"); g.restore();
};
CS.board = function (g, x, y, w = 520, h = 60) { CS.rrect(g, x - w / 2, y - h, w, h, 18, "#e0a764", 8); CS.seg2(g, x - w / 2 + 40, y - h + 20, x + w / 2 - 40, y - h + 20, 5, "rgba(255,255,255,.45)"); CS.circle(g, x + w / 2 - 50, y - h / 2, 12, "#c98a55", 5); };
// a wobbly gas wisp drifting along a path from (x0,y0) to (x1,y1); k = 0..1 progress
CS.wisp = function (g, x0, y0, x1, y1, k, t, o = {}) {
  const c = o.color || "rgba(170,240,120,.85)", n = o.n || 7;
  for (let i = 0; i < n; i++) {
    const kk = clamp(k * 1.4 - i * .06), x = lerp(x0, x1, kk) + Math.sin(t * 4 + i * 1.7) * 30, y = lerp(y0, y1, kk) + Math.cos(t * 3 + i) * 16, r = (o.r || 34) * (.5 + .5 * Math.sin(i * 2.1 + 1));
    if (kk <= 0) continue; g.globalAlpha = clamp(kk * 4) * (o.alpha ?? 1); CS.circle(g, x, y, r, c, 5); g.globalAlpha = 1;
  }
};
CS.glass = function (g, x, y, s = 1, fill = .7, c = "#6fd0ff") {
  g.save(); g.translate(x, y); g.scale(s, s);
  g.beginPath(); g.moveTo(-50, -140); g.lineTo(-40, 0); g.lineTo(40, 0); g.lineTo(50, -140); g.closePath(); fs(g, "rgba(220,245,255,.55)", 0);
  g.save(); g.clip(); g.fillStyle = c; g.fillRect(-60, -140 * fill, 120, 150); g.restore();
  g.beginPath(); g.moveTo(-50, -140); g.lineTo(-40, 0); g.lineTo(40, 0); g.lineTo(50, -140); fs(g, null, 7);
  CS.seg2(g, -30, -120, -24, -20, 6, "rgba(255,255,255,.8)"); g.restore();
};
CS.crystal = function (g, x, y, s = 1, ang = 0) { g.save(); g.translate(x, y); g.rotate(ang); g.scale(s, s); CS.rrect(g, -22, -22, 44, 44, 6, "#ffffff", 6); g.beginPath(); g.moveTo(-22, -22); g.lineTo(-10, -34); g.lineTo(34, -34); g.lineTo(22, -22); g.closePath(); fs(g, "#e7f2ff", 6); g.beginPath(); g.moveTo(22, -22); g.lineTo(34, -34); g.lineTo(34, 10); g.lineTo(22, 22); g.closePath(); fs(g, "#c6dcf5", 6); g.restore(); };
CS.sign = function (g, x, y, text, o = {}) {      // a board on a post, text reads correctly
  const w = o.w || 420, h = o.h || 150; CS.seg2(g, x, y, x, y - h - 120, 18, "#7a4a2a"); CS.rrect(g, x - w / 2, y - h - 200, w, h, 16, o.bg || "#fff6d8", 8);
  g.fillStyle = o.fg || INK; g.font = "700 " + (o.size || 64) + "px " + CS.FONT; g.textAlign = "center"; g.textBaseline = "middle"; g.fillText(text, x, y - h / 2 - 200);
};

// a soft puff (gas, smoke, a little cloud buddy) with an optional face
CS.puffy = function (g, x, y, r, o = {}) {
  g.beginPath(); for (let i = 0; i < 7; i++) { const a = i / 7 * Math.PI * 2; g.moveTo(x + Math.cos(a) * r * .55 + r * .5, y + Math.sin(a) * r * .5); g.arc(x + Math.cos(a) * r * .55, y + Math.sin(a) * r * .5, r * .5, 0, 7); }
  g.fillStyle = o.color || "#b8f58a"; g.fill();
  g.beginPath(); g.arc(x, y, r * .78, 0, 7); g.fill();
  g.lineWidth = o.lw ?? 5; g.strokeStyle = CS.INK; for (let i = 0; i < 7; i++) { const a = i / 7 * Math.PI * 2; g.beginPath(); g.arc(x + Math.cos(a) * r * .55, y + Math.sin(a) * r * .5, r * .5, a - 1.25, a + 1.25); g.stroke(); }
  if (o.face) CS.drawFace(g, x, y - r * .05, r * .62, { face: o.face, t: o.t, blink: o.blink });
};

// ---------- bubbles + zoom circles ----------
// thought bubble: CS.thought(g, cx, cy, w, h, [tailX, tailY], k (0..1 grow), drawInside(g))
CS.thought = function (g, cx, cy, w, h, tail, k, inside) {
  if (k <= 0) return; const kk = ease.back(clamp(k));
  for (let i = 0; i < 3; i++) { const p = (i + 1) / 4, kd = clamp(k * 3 - i * .4); if (kd <= 0) continue; CS.circle(g, lerp(tail[0], cx, p * .55), lerp(tail[1], cy + h * .4, p * .7), (12 + i * 9) * kd, "#fff", 6); }
  if (k < .35) return;
  const kb = ease.back(clamp((k - .35) / .65));
  g.save(); g.translate(cx, cy); g.scale(kb, kb);
  const puff = () => { g.beginPath(); const n = 11; for (let i = 0; i < n; i++) { const a0 = i / n * Math.PI * 2, a1 = (i + 1) / n * Math.PI * 2, am = (a0 + a1) / 2; const px = Math.cos(am) * w * .5, py = Math.sin(am) * h * .5; g.arc(px * .92, py * .92, Math.min(w, h) * .2, am - 1.3, am + 1.3); } g.closePath(); };
  puff(); fs(g, "#fff", 8);
  g.save(); g.beginPath(); g.ellipse(0, 0, w * .44, h * .4, 0, 0, 7); g.clip(); if (inside) inside(g); g.restore();
  g.restore(); void kk;
};
CS.speech = function (g, cx, cy, text, k, o = {}) {
  if (k <= 0) return; const kb = ease.back(clamp(k)), size = o.size || 62;
  g.save(); g.font = "700 " + size + "px " + CS.FONT; const tw = Math.max(...String(text).split("\n").map(l => g.measureText(l).width)), lines = String(text).split("\n");
  const w = tw + 80, h = lines.length * size * 1.1 + 56;
  g.translate(cx, cy); g.scale(kb, kb);
  g.beginPath(); g.roundRect(-w / 2, -h / 2, w, h, 36); const tx = o.tail ?? -w * .2; g.moveTo(tx - 24, h / 2 - 2); g.lineTo(tx - 40, h / 2 + 52); g.lineTo(tx + 26, h / 2 - 2); fs(g, o.bg || "#fff", 8);
  g.fillStyle = "#fff"; g.fillRect(tx - 20, h / 2 - 10, 42, 14);
  g.fillStyle = o.fg || INK; g.textAlign = "center"; g.textBaseline = "middle"; lines.forEach((l, i) => g.fillText(l, 0, (i - (lines.length - 1) / 2) * size * 1.1 + 4)); g.restore();
};
// zoom circle (a magnifier into a detail): CS.zoom(g, cx, cy, r, k, drawInside(g, r), {from: [x, y], ring})
CS.zoom = function (g, cx, cy, r, k, inside, o = {}) {
  if (k <= 0) return; const kb = ease.back(clamp(k)), rr = r * kb;
  if (o.from) { g.save(); g.globalAlpha = .9 * clamp(k * 2); g.fillStyle = "rgba(255,255,255,.35)"; g.beginPath(); g.moveTo(o.from[0], o.from[1]); const a = Math.atan2(cy - o.from[1], cx - o.from[0]); g.lineTo(cx + Math.cos(a + Math.PI / 2) * rr, cy + Math.sin(a + Math.PI / 2) * rr); g.lineTo(cx + Math.cos(a - Math.PI / 2) * rr, cy + Math.sin(a - Math.PI / 2) * rr); g.closePath(); g.fill(); g.restore(); CS.circle(g, o.from[0], o.from[1], 26 * kb, null, 7); }
  CS.circle(g, cx, cy, rr + 16, o.ring || "#ffd23a", 9);
  g.save(); g.beginPath(); g.arc(cx, cy, rr, 0, 7); g.clip(); g.translate(cx, cy); g.scale(kb, kb); inside(g, r); g.restore();
  CS.circle(g, cx, cy, rr, null, 9);
};

// ---------- effects ----------
CS.burst = function (g, x, y, r, k, o = {}) {     // comic burst star, k 0..1 life
  if (k <= 0 || k >= 1) return; const kk = ease.back(clamp(k * 3)), fade = clamp((1 - k) * 3), n = o.n || 12;
  g.save(); g.globalAlpha = fade; g.translate(x, y); g.rotate(o.rot || .2); g.scale(kk, kk); g.beginPath();
  for (let i = 0; i <= n * 2; i++) { const a = i / (n * 2) * Math.PI * 2, rr = i % 2 ? r * .55 : r; g.lineTo(Math.cos(a) * rr, Math.sin(a) * rr); }
  g.closePath(); fs(g, o.color || "#ffd23a", 8);
  if (o.text) { g.rotate(-(o.rot || .2)); g.fillStyle = o.fg || INK; g.font = "700 " + (o.size || r * .42) + "px " + CS.FONT; g.textAlign = "center"; g.textBaseline = "middle"; g.fillText(o.text, 0, 4); }
  g.restore();
};
CS.sparkles = function (g, x, y, r, t, k = 1, o = {}) {
  for (let i = 0; i < (o.n || 6); i++) { const a = i / (o.n || 6) * Math.PI * 2 + t * .8, d = r * (.7 + .3 * Math.sin(t * 3 + i)), s = (14 + 8 * Math.sin(t * 6 + i * 2)) * k;
    const px = x + Math.cos(a) * d, py = y + Math.sin(a) * d; g.beginPath(); g.moveTo(px, py - s * 1.6); g.quadraticCurveTo(px, py, px + s * 1.6, py); g.quadraticCurveTo(px, py, px, py + s * 1.6); g.quadraticCurveTo(px, py, px - s * 1.6, py); g.quadraticCurveTo(px, py, px, py - s * 1.6); fs(g, o.color || "#fff38a", 4); }
};
CS.pop = function (g, x, y, text, k, o = {}) {      // "!" "?" "!!" popping over a head
  if (k <= 0 || k >= 1) return; const kk = ease.back(clamp(k * 4)), fade = clamp((1 - k) * 4);
  g.save(); g.globalAlpha = fade; g.translate(x, y - kk * 20); g.scale(kk, kk); g.rotate(o.rot ?? -.12);
  g.font = "700 " + (o.size || 130) + "px " + CS.FONT; g.textAlign = "center"; g.textBaseline = "middle"; g.lineWidth = 18; g.strokeStyle = INK; g.lineJoin = "round"; g.strokeText(text, 0, 0); g.fillStyle = o.color || "#ffd23a"; g.fillText(text, 0, 0); g.restore();
};
CS.speedLines = function (g, cx, cy, t, a = 1, o = {}) {        // radial action lines around a point
  g.save(); g.globalAlpha = a; g.strokeStyle = o.color || "rgba(255,255,255,.8)"; g.lineCap = "round";
  for (let i = 0; i < (o.n || 40); i++) { const ang = rand(i * 3 + Math.floor(t * 12)) * Math.PI * 2, r0 = (o.r0 || 420) + rand(i * 3 + 1) * 200, r1 = r0 + 200 + rand(i) * 500; g.lineWidth = 4 + rand(i * 9) * 8; g.beginPath(); g.moveTo(cx + Math.cos(ang) * r0, cy + Math.sin(ang) * r0); g.lineTo(cx + Math.cos(ang) * r1, cy + Math.sin(ang) * r1); g.stroke(); }
  g.restore();
};
CS.sweat = function (g, x, y, t, s = 1) { const k = (t * 1.5) % 1; CS.drop(g, x, y + k * 40 * s, 13 * s * (1 - k * .3), 5 * s); };
CS.stinkLines = function (g, x, y, t, c = "#7ccf4e") { g.strokeStyle = c; g.lineWidth = 8; g.lineCap = "round"; for (let i = -1; i <= 1; i++) { g.beginPath(); for (let k = 0; k < 1; k += .05) { const yy = y - k * 140, xx = x + i * 50 + Math.sin(k * 9 + t * 5 + i) * 14; k ? g.lineTo(xx, yy) : g.moveTo(xx, yy); } g.stroke(); } };
CS.arrow = function (g, x0, y0, x1, y1, k = 1, o = {}) {
  if (k <= 0) return; const x = lerp(x0, x1, k), y = lerp(y0, y1, k), a = Math.atan2(y1 - y0, x1 - x0);
  g.save(); g.setLineDash(o.dash || []); CS.seg2(g, x0, y0, x, y, o.lw || 12, o.color || INK); g.setLineDash([]);
  g.beginPath(); g.moveTo(x + Math.cos(a) * 30, y + Math.sin(a) * 30); g.lineTo(x + Math.cos(a + 2.4) * 36, y + Math.sin(a + 2.4) * 36); g.lineTo(x + Math.cos(a - 2.4) * 36, y + Math.sin(a - 2.4) * 36); g.closePath(); fs(g, o.color || INK, 0); g.restore();
};
// outlined text (labels, titles) in the world or on top
CS.FONT = "CapFont, 'Fredoka', 'Arial Rounded MT Bold', 'Trebuchet MS', sans-serif";
CS.label = function (g, text, x, y, o = {}) {
  const size = o.size || 80; g.save(); g.translate(x, y); g.rotate(o.rot || 0); g.scale(o.scale || 1, o.scale || 1); g.globalAlpha = o.alpha ?? 1;
  g.font = (o.weight || 700) + " " + size + "px " + CS.FONT; g.textAlign = "center"; g.textBaseline = "middle"; g.lineJoin = "round";
  g.lineWidth = size * (o.stroke ?? .26); g.strokeStyle = o.ink || INK; g.strokeText(text, 0, 0); g.fillStyle = o.color || "#fff"; g.fillText(text, 0, 0); g.restore();
};
})();
