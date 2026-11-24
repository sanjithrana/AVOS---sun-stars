/* Cartoon Shorts engine: painted textures (flat colour, soft variation, dark seams). Free from Anylancer.com. */
(function () {
const CS = window.CS = window.CS || {};

// ---------- deterministic helpers (shared by every engine file) ----------
CS.rand = function (seed) { let t = (seed * 2654435761 + 0x6D2B79F5) >>> 0; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
CS.clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
CS.lerp = (a, b, k) => a + (b - a) * k;
CS.seg = (t, a, b) => CS.clamp((t - a) / (b - a));
CS.ease = {
  lin: k => k,
  smooth: k => k * k * k * (k * (k * 6 - 15) + 10),            // smootherstep: glides
  inOut: k => k < .5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2,
  out: k => 1 - Math.pow(1 - k, 3),
  in: k => k * k * k,
  back: k => 1 + 2.4 * Math.pow(k - 1, 3) + 1.4 * Math.pow(k - 1, 2),   // overshoot then settle
  spring: k => k >= 1 ? 1 : 1 - Math.exp(-6 * k) * Math.cos(11 * k),
};
CS.noise1 = function (x, seed = 1) { const i = Math.floor(x), f = x - i, u = f * f * (3 - 2 * f); return CS.lerp(CS.rand(i * 13 + seed * 7919), CS.rand((i + 1) * 13 + seed * 7919), u) * 2 - 1; };
CS.hex = function (c) { return typeof c === "number" ? "#" + c.toString(16).padStart(6, "0") : c; };
CS.shade = function (hex, k) {      // k < 0 darker, k > 0 lighter
  const n = parseInt(CS.hex(hex).slice(1), 16); let r = n >> 16, g = (n >> 8) & 255, b = n & 255;
  if (k < 0) { r *= 1 + k; g *= 1 + k; b *= 1 + k; } else { r += (255 - r) * k; g += (255 - g) * k; b += (255 - b) * k; }
  return "rgb(" + [r, g, b].map(v => Math.round(CS.clamp(v, 0, 255))).join(",") + ")";
};

// ---------- painters ----------
const P = CS.paint = {};
const cache = {};
function canvas(w, h) { const c = document.createElement("canvas"); c.width = w; c.height = h; return c; }
P.canvas = canvas;
function speckle(g, w, h, base, n, amp, seed, size = 6) {
  for (let i = 0; i < n; i++) {
    const r = CS.rand(seed + i * 3), x = CS.rand(seed + i * 3 + 1) * w, y = CS.rand(seed + i * 3 + 2) * h;
    g.fillStyle = CS.shade(base, (r - .5) * amp); g.globalAlpha = .55;
    g.beginPath(); g.ellipse(x, y, size * (.5 + r), size * (.35 + r * .5), r * 3, 0, 7); g.fill();
  }
  g.globalAlpha = 1;
}
const PAINTERS = {
  grass(g, w, h, o) {
    const c = o.color || "#6cbf4a"; g.fillStyle = c; g.fillRect(0, 0, w, h);
    speckle(g, w, h, c, 900, .22, 11, 7);
    g.strokeStyle = CS.shade(c, -.22); g.lineWidth = 2;
    for (let i = 0; i < 380; i++) { const x = CS.rand(i * 7 + 1) * w, y = CS.rand(i * 7 + 2) * h; g.beginPath(); g.moveTo(x, y); g.lineTo(x + (CS.rand(i) - .5) * 6, y - 7 - CS.rand(i * 5) * 8); g.stroke(); }
  },
  dirt(g, w, h, o) { const c = o.color || "#c98a55"; g.fillStyle = c; g.fillRect(0, 0, w, h); speckle(g, w, h, c, 700, .25, 21, 8); speckle(g, w, h, CS.shade(c, -.3), 60, .1, 22, 4); },
  sand(g, w, h, o) { const c = o.color || "#d9663a"; g.fillStyle = c; g.fillRect(0, 0, w, h); speckle(g, w, h, c, 900, .18, 31, 6); g.strokeStyle = CS.shade(c, -.12); g.lineWidth = 3; for (let i = 0; i < 14; i++) { const y = CS.rand(i * 9) * h; g.beginPath(); for (let x = 0; x <= w; x += 16) g.lineTo(x, y + Math.sin(x * .03 + i) * 6); g.stroke(); } },
  wheat(g, w, h, o) {
    const c = o.color || "#e8b93c"; g.fillStyle = c; g.fillRect(0, 0, w, h);
    for (let row = 0; row < 16; row++) { const y = row * h / 16; g.fillStyle = CS.shade(c, row % 2 ? -.08 : .04); g.fillRect(0, y, w, h / 32); }
    g.lineWidth = 3;
    for (let i = 0; i < 700; i++) { const x = CS.rand(i * 5 + 3) * w, y = CS.rand(i * 5 + 4) * h, r = CS.rand(i * 5 + 5); g.strokeStyle = CS.shade(c, (r - .5) * .5); g.beginPath(); g.moveTo(x, y); g.lineTo(x + 2, y - 12 - r * 10); g.stroke(); }
  },
  planks(g, w, h, o) {
    const c = o.color || "#b07a45", n = o.n || 6; g.fillStyle = c; g.fillRect(0, 0, w, h);
    for (let i = 0; i < n; i++) {
      const y = i * h / n; g.fillStyle = CS.shade(c, (CS.rand(i * 31) - .5) * .25); g.fillRect(0, y, w, h / n);
      g.strokeStyle = CS.shade(c, -.18); g.lineWidth = 2;
      for (let k = 0; k < 4; k++) { const yy = y + (k + .5) * h / n / 4.4; g.beginPath(); for (let x = 0; x <= w; x += 24) g.lineTo(x, yy + Math.sin(x * .02 + i * 3 + k) * 3); g.stroke(); }
      g.fillStyle = CS.shade(c, -.45); g.fillRect(0, y, w, 4);
      const cut = CS.rand(i * 17) * w; g.fillRect(cut, y, 4, h / n);
    }
  },
  stone(g, w, h, o) {
    const c = o.color || "#b9b2a6"; g.fillStyle = CS.shade(c, -.45); g.fillRect(0, 0, w, h);
    const rows = o.rows || 8, bh = h / rows;
    for (let r = 0; r < rows; r++) for (let x = -(r % 2) * 40; x < w; ) {
      const bw = 60 + CS.rand(r * 50 + x) * 50; g.fillStyle = CS.shade(c, (CS.rand(r * 7 + x * 3) - .5) * .25);
      g.beginPath(); g.roundRect(x + 3, r * bh + 3, bw - 6, bh - 6, 6); g.fill(); x += bw;
    }
  },
  plaster(g, w, h, o) { const c = o.color || "#efe2c8"; g.fillStyle = c; g.fillRect(0, 0, w, h); speckle(g, w, h, c, 300, .12, 41, 18); },
  brick(g, w, h, o) { PAINTERS.stone(g, w, h, { color: o.color || "#b45a3c", rows: o.rows || 12 }); },
  roof(g, w, h, o) {
    const c = o.color || "#c4553a", rows = o.rows || 8; g.fillStyle = CS.shade(c, -.4); g.fillRect(0, 0, w, h);
    for (let r = 0; r < rows; r++) for (let x = (r % 2) * 32 - 32; x < w; x += 64) {
      g.fillStyle = CS.shade(c, (CS.rand(r * 13 + x) - .5) * .2);
      g.beginPath(); g.moveTo(x + 4, r * h / rows); g.lineTo(x + 60, r * h / rows); g.lineTo(x + 60, (r + .9) * h / rows); g.quadraticCurveTo(x + 32, (r + 1.1) * h / rows, x + 4, (r + .9) * h / rows); g.fill();
    }
  },
  marble(g, w, h, o) {
    const a = o.color || "#efe9df", b = o.color2 || "#b7a58f", n = o.n || 4; const s = w / n;
    for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) { g.fillStyle = (i + j) % 2 ? b : a; g.fillRect(i * s, j * s, s, s); }
    g.strokeStyle = "rgba(90,70,60,.18)"; g.lineWidth = 2;
    for (let i = 0; i < 30; i++) { g.beginPath(); let x = CS.rand(i * 3) * w, y = CS.rand(i * 3 + 1) * h; g.moveTo(x, y); for (let k = 0; k < 6; k++) { x += (CS.rand(i * 9 + k) - .3) * 40; y += (CS.rand(i * 11 + k) - .5) * 40; g.lineTo(x, y); } g.stroke(); }
    g.fillStyle = "rgba(60,40,30,.35)"; for (let i = 0; i <= n; i++) { g.fillRect(i * s - 1, 0, 3, h); g.fillRect(0, i * s - 1, w, 3); }
  },
  wallpaper(g, w, h, o) {
    const c = o.color || "#9c2f3a"; g.fillStyle = c; g.fillRect(0, 0, w, h);
    g.fillStyle = CS.shade(c, .12);
    for (let y = 0; y < h; y += 64) for (let x = ((y / 64) % 2) * 32; x < w; x += 64) { g.beginPath(); g.moveTo(x, y - 14); g.quadraticCurveTo(x + 12, y, x, y + 14); g.quadraticCurveTo(x - 12, y, x, y - 14); g.fill(); }
  },
  water(g, w, h, o) {
    const c = o.color || "#3a9ad9"; g.fillStyle = c; g.fillRect(0, 0, w, h);
    g.strokeStyle = CS.shade(c, .45); g.lineWidth = 5; g.lineCap = "round";
    for (let i = 0; i < 40; i++) { const x = CS.rand(i * 3) * w, y = CS.rand(i * 3 + 1) * h, l = 30 + CS.rand(i) * 60; g.beginPath(); g.moveTo(x, y); g.quadraticCurveTo(x + l / 2, y - 6, x + l, y); g.stroke(); }
  },
  metal(g, w, h, o) { const c = o.color || "#7f8a86"; g.fillStyle = c; g.fillRect(0, 0, w, h); speckle(g, w, h, c, 200, .1, 51, 10); g.fillStyle = CS.shade(c, -.35); for (let i = 1; i < 4; i++) g.fillRect(0, i * h / 4, w, 3); for (let i = 0; i < 24; i++) { g.beginPath(); g.arc((i % 6 + .5) * w / 6, (Math.floor(i / 6) + .5) * h / 4 - h / 8 + 10, 4, 0, 7); g.fill(); } },
  wood(g, w, h, o) { const c = o.color || "#8a5a33"; g.fillStyle = c; g.fillRect(0, 0, w, h); g.strokeStyle = CS.shade(c, -.2); g.lineWidth = 2; for (let i = 0; i < 26; i++) { const x = i * w / 26 + CS.rand(i) * 6; g.beginPath(); for (let y = 0; y <= h; y += 20) g.lineTo(x + Math.sin(y * .03 + i) * 4, y); g.stroke(); } },
  flat(g, w, h, o) { g.fillStyle = o.color || "#ccc"; g.fillRect(0, 0, w, h); speckle(g, w, h, o.color || "#ccc", 160, .08, 61, 14); },
};
P.PAINTERS = PAINTERS;
// tex("grass", {color, repeat:[x,y]}) -> cached THREE.CanvasTexture (sRGB, wrapping)
P.tex = function (name, o = {}) {
  const key = name + JSON.stringify(o);
  if (cache[key]) return cache[key];
  const size = o.size || 512, c = canvas(size, size), g = c.getContext("2d");
  (PAINTERS[name] || PAINTERS.flat)(g, size, size, o);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.wrapS = t.wrapT = THREE.RepeatWrapping; t.anisotropy = 4;
  if (o.repeat) t.repeat.set(o.repeat[0], o.repeat[1]);
  return cache[key] = t;
};
// texture from your own drawing: canvasTex(w, h, g => { ... })
P.canvasTex = function (w, h, fn) { const c = canvas(w, h); fn(c.getContext("2d"), w, h); const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t; };
})();
