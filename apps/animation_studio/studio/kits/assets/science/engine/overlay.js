/* Cartoon Shorts engine: the 2D overlay drawn on top of the 3D picture. Word-by-word captions, title cards, rain.
   Everything here is part of the picture, so Play, Export video and render.mjs all show it. Free from Anylancer.com. */
(function () {
const CS = window.CS = window.CS || {};
const { rand, clamp, ease } = CS;
let cv, g, tex, oScene, oCam, used = false;
const items = [];          // {kind, t0, t1, draw(g, t, k)}
CS.overlayItems = items;

// ---------- layer ----------
const baseStart = CS.start;
CS.start = function (opt) {
  baseStart(opt);
  cv = document.createElement("canvas"); cv.width = CS.W; cv.height = CS.H; g = cv.getContext("2d");
  tex = new THREE.CanvasTexture(cv); tex.colorSpace = THREE.NoColorSpace; tex.minFilter = tex.magFilter = THREE.LinearFilter; tex.generateMipmaps = false;
  const m = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), new THREE.MeshBasicMaterial({ map: tex, transparent: true, depthTest: false, depthWrite: false }));
  m.frustumCulled = false; oScene = new THREE.Scene(); oScene.add(m); oCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
};
const baseRender = CS.renderFrame;
CS.renderFrame = function (f) {
  baseRender(f);
  if (!used) return;
  const r = CS.renderer; r.autoClear = false; r.render(oScene, oCam); r.autoClear = true;
};
// called by the player every frame, after SHORT.frame(t)
CS.overlayDraw = function (t, T) {
  const S = window.SHORT || {};
  if (S.captions && (!caps || caps.T !== T)) buildCaptions(T, S.captions);
  g.clearRect(0, 0, cv.width, cv.height); let drew = false;
  for (const it of items) if (t >= it.t0 && t < it.t1) { it.draw(g, t, CS.seg(t, it.t0, it.t1)); drew = true; }
  if (caps && !titleAt(t)) drew = drawCaption(t) || drew;
  if (S.overlay) drew = S.overlay(g, t, T) !== false || drew;   // your own 2D drawing on top (return false if nothing drawn)
  used = drew; if (drew) tex.needsUpdate = true;
};
const titleAt = t => items.some(it => it.kind === "title" && t >= it.t0 && t < it.t1);

// ---------- text with a thick outline ----------
CS.FONT = "CapFont, 'Fredoka', 'Arial Rounded MT Bold', 'Trebuchet MS', sans-serif";
CS.outlined = function (g, text, x, y, o = {}) {
  const size = o.size || 110; g.font = (o.weight || 700) + " " + size + "px " + (o.font || CS.FONT);
  g.textAlign = o.align || "center"; g.textBaseline = "middle"; g.lineJoin = "round"; g.miterLimit = 2;
  let s = size; const maxW = o.maxW || CS.W * .84, w = g.measureText(text).width;
  if (w > maxW) { s = size * maxW / w; g.font = (o.weight || 700) + " " + s + "px " + (o.font || CS.FONT); }
  g.save(); g.translate(x, y); if (o.scale) g.scale(o.scale, o.scale); if (o.rot) g.rotate(o.rot);
  g.globalAlpha = o.alpha ?? 1;
  g.shadowColor = "rgba(0,0,0,.35)"; g.shadowOffsetY = s * .06; g.shadowBlur = s * .08;
  g.strokeStyle = o.stroke || "#1d1420"; g.lineWidth = s * (o.strokeK || .2); g.strokeText(text, 0, 0);
  g.shadowColor = "transparent"; g.fillStyle = o.color || "#ffffff"; g.fillText(text, 0, 0);
  g.restore(); return s;
};

// ---------- captions: one or two words at a time, timed to the voice ----------
/* SHORT.captions = { y: 1390, size: 112, color: "#fff", star: "#ffd23a",
     subs: {"seventeen thirty": "1730"},     spoken words shown as digits (merged into one caption)
     hide: [[t0, t1]],                       windows with no captions (title cards hide them by themselves)
     upper: false }                          ALL CAPS captions
   In the script, *word* turns a word yellow (the asterisks are not spoken and not shown). */
let caps = null;
const norm = w => w.toLowerCase().replace(/[’']/g, "").replace(/[^a-z0-9]+/g, "");
function buildCaptions(T, o) {
  const W = T.words || [], subs = Object.entries(o.subs || {}).map(([k, v]) => [k.split(/\s+/).map(norm).filter(Boolean), v]);
  const toks = [];
  for (let i = 0; i < W.length; i++) {
    let hit = null;
    for (const [ks, v] of subs) if (ks.length && ks.every((x, k) => W[i + k] && W[i + k].n === x)) { hit = [ks.length, v]; break; }
    if (hit) { const last = W[i + hit[0] - 1]; toks.push({ text: hit[1] + ((last.w.match(/[.?!]+$/) || [""])[0]), star: /\*/.test(W[i].w) || true, start: W[i].start, end: last.end, num: true }); i += hit[0] - 1; continue; }
    const raw = W[i].w, star = /\*/.test(raw);
    let text = raw.replace(/[*“”"‘’…—–,;:()]/g, "").replace(/^'+|'+$/g, "").trim();
    if (!text) continue;
    toks.push({ text, star, start: W[i].start, end: W[i].end });
  }
  // pair tiny words with the next one ("a young", "of the"), like hand-made captions
  const out = [];
  for (let i = 0; i < toks.length; i++) {
    const a = toks[i], b = toks[i + 1];
    if (b && !a.num && !b.num && a.text.length <= 3 && !/[.?!]$/.test(a.text) && b.start - a.end < .3 && (a.text + b.text).length <= 11 && !a.star) { out.push({ text: a.text + " " + b.text, star: b.star, start: a.start, end: b.end }); i++; }
    else out.push(a);
  }
  for (let i = 0; i < out.length; i++) { const n = out[i + 1]; out[i].off = n && n.start - out[i].end < .7 ? n.start : out[i].end + .3; }
  caps = { T, list: out, o };
}
function drawCaption(t) {
  const L = caps.list, o = caps.o;
  if ((o.hide || []).some(([a, b]) => t >= a && t < b)) return false;
  let c = null; for (const x of L) { if (x.start - .04 <= t && t < x.off) c = x; if (x.start > t) break; }
  if (!c) return false;
  const k = clamp((t - c.start + .04) / .12), sc = 1 + (1 - ease.out(k)) * .16;
  CS.outlined(g, o.upper ? c.text.toUpperCase() : c.text, CS.W / 2, o.y || CS.H * .724, { size: o.size || 112, color: c.star ? (o.star || "#ffd23a") : (o.color || "#fff"), scale: sc, maxW: CS.W * .8 });
  return true;
}
CS.captionList = () => caps && caps.list;

// ---------- title cards ("19 YEARS LATER") ----------
// title("19 YEARS\nLATER", t0, t1, {color, size, y, sub}) ; captions hide while it shows. Blur the picture yourself with CS.lens.
CS.title = function (text, t0, t1, o = {}) {
  items.push({ kind: "title", t0, t1, draw(g, t) {
    const kin = ease.back(clamp((t - t0) / .28)), kout = clamp((t1 - t) / .18), lines = String(text).split("\n"), size = o.size || 150, y0 = o.y || CS.H * .45;
    g.save(); g.globalAlpha = (o.dimA ?? .42) * kout; g.fillStyle = o.dim || "#120c1a"; g.fillRect(0, 0, CS.W, CS.H); g.restore();
    lines.forEach((l, i) => CS.outlined(g, l, CS.W / 2, y0 + (i - (lines.length - 1) / 2) * size * 1.05, { size, color: o.color || "#ffd23a", scale: .6 + .4 * kin, alpha: kout, rot: (o.tilt ?? -.03) }));
    if (o.sub) CS.outlined(g, o.sub, CS.W / 2, y0 + lines.length * size * .62 + 40, { size: size * .42, color: "#fff", alpha: kout * clamp((t - t0 - .25) / .2) });
  } });
};

// ---------- rain (screen-space streaks, deterministic) ----------
// rain(t0, t1, {n, speed, angle, color, len, tint})
CS.rain = function (t0, t1, o = {}) {
  const n = o.n || 220, sp = o.speed || 2600, ang = o.angle ?? .18, len = o.len || 80;
  items.push({ kind: "rain", t0, t1, draw(g, t) {
    const fade = clamp((t - t0) / .3) * clamp((t1 - t) / .3);
    if (o.tint !== false) { g.fillStyle = `rgba(20,30,60,${.16 * fade})`; g.fillRect(0, 0, CS.W, CS.H); }
    g.strokeStyle = o.color || "rgba(210,225,255,.55)"; g.lineWidth = o.width || 3; g.globalAlpha = fade; g.beginPath();
    for (let i = 0; i < n; i++) {
      const v = sp * (.75 + rand(i * 3) * .5), y = ((rand(i * 3 + 1) * CS.H * 1.3 + t * v) % (CS.H * 1.3)) - CS.H * .15, x = ((rand(i * 3 + 2) * CS.W * 1.4 + y * Math.tan(ang)) % (CS.W * 1.4)) - CS.W * .2;
      g.moveTo(x, y); g.lineTo(x - Math.sin(ang) * len, y - Math.cos(ang) * len);
    }
    g.stroke(); g.globalAlpha = 1;
  } });
};
// flashAt(t, [t1, t2…], dur): 0..1 lightning flash for CS.lens({flash}) — two quick blinks per strike
CS.flashAt = function (t, times, dur = .28) {
  let f = 0; for (const s of times) { const d = t - s; if (d >= 0 && d < dur) f = Math.max(f, d < .06 ? 1 : d < .1 ? .2 : d < .16 ? .8 : (1 - (d - .16) / (dur - .16)) * .6); }
  return f * .7;
};
// lightning bolt drawn on the overlay: bolt(t0, x, {dur, seed})
CS.bolt = function (t0, x, o = {}) {
  const dur = o.dur || .22, seed = o.seed || 1;
  items.push({ kind: "bolt", t0, t1: t0 + dur, draw(g, t) {
    let px = x, py = o.y0 || 120; g.strokeStyle = "#fffbe0"; g.lineWidth = 9; g.shadowColor = "#bcd4ff"; g.shadowBlur = 30; g.beginPath(); g.moveTo(px, py);
    for (let i = 0; i < 9; i++) { px += (rand(seed * 17 + i) - .5) * 140; py += (o.h || 900) / 9; g.lineTo(px, py); }
    g.stroke(); g.shadowBlur = 0;
  } });
};
})();
