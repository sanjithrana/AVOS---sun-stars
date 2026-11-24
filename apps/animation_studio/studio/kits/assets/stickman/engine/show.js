/* Stickman Shorts engine: the show. Shot list → camera (push-ins, handheld drift, shakes) → whip / pop / cut transitions
   → 1-2 word captions → vignette, grain and flashes. The player calls CS.frame(t, T) for every frame. Free from Anylancer.com. */
(function () {
const CS = window.CS = window.CS || {};
const { rand, clamp, lerp, ease } = CS;
let main, buf, bg, grain, plan = null;

CS.start = function (opt) {
  CS.W = opt.width; CS.H = opt.height; main = opt.canvas; main.width = CS.W; main.height = CS.H;
  CS.g = main.getContext("2d");
  const mk = () => { const c = document.createElement("canvas"); c.width = CS.W; c.height = CS.H; return c; };
  buf = mk(); bg = mk();
  grain = document.createElement("canvas"); grain.width = grain.height = 256; const gg = grain.getContext("2d"), id = gg.createImageData(256, 256);
  for (let i = 0; i < id.data.length; i += 4) { const v = rand(i * .25 + 3) * 255; id.data[i] = id.data[i + 1] = id.data[i + 2] = v; id.data[i + 3] = 255; }
  gg.putImageData(id, 0, 0);
};
CS.renderFrame = function () {};

// ---------- the plan ----------
function build(T) {
  const S = window.SHORT, list = S.shots(T), out = [];
  list.forEach((sh, i) => {
    let st = i === 0 ? 0 : typeof sh.at === "number" ? sh.at : T.w(sh.at, sh.after || 0) - (sh.lead ?? .06);
    out.push(Object.assign({ i, start: Math.max(0, st), tr: "whip" }, sh));
  });
  const DUR = CS.DUR || T.duration + (S.tail ?? .8);
  out.forEach((s, i) => { s.end = i < out.length - 1 ? out[i + 1].start : DUR; s.dur = Math.max(.01, s.end - s.start); });
  return { T, shots: out, caps: S.captions === false ? null : captions(T, S.captions || {}) };
}
CS.plan = () => plan;
// a sound on every cut: CS.cutSounds(A, T, ["whoosh", "swish"], gain) (pop cuts get a "pop")
CS.cutSounds = function (A, T, names = ["whoosh", "swish"], gain = .4) {
  plan = build(T); plan.shots.slice(1).forEach((s, i) => { if (s.tr === "cut") return; A.sfx(s.tr === "pop" ? "pop" : names[i % names.length], s.start - (s.tr === "pop" ? .02 : .14), gain); });
};
CS.shotAt = function (t) { const L = plan.shots; let i = 0; while (i < L.length - 1 && t >= L[i + 1].start) i++; return L[i]; };

// camera: {from: [x, y, zoom, rotDeg], to: [...], ease} centre of view in design pixels (540, 960 = no move)
function camAt(sh, t) {
  const c = sh.cam || {}, a = c.from || [540, 960, 1, 0], b = c.to || a;
  const k = (ease[c.ease || "smooth"] || ease.smooth)(clamp((t - sh.start) / sh.dur));
  const v = [0, 1, 2, 3].map(j => lerp(a[j] ?? (j === 2 ? 1 : 0), b[j] ?? a[j] ?? (j === 2 ? 1 : 0), k));
  const dr = (c.drift ?? 1) * 7;
  v[0] += CS.noise1(t * .55, 11) * dr; v[1] += CS.noise1(t * .5, 23) * dr; v[3] += CS.noise1(t * .4, 37) * .35 * (c.drift ?? 1);
  for (const [t0, d, amp] of (sh.shake || [])) { const q = t - t0; if (q >= 0 && q < d) { const f = (1 - q / d) * amp; v[0] += (rand(Math.floor(t * 60)) - .5) * f; v[1] += (rand(Math.floor(t * 60) + 7) - .5) * f; v[3] += (rand(Math.floor(t * 60) + 3) - .5) * f * .03; } }
  return v;
}
function renderShot(sh, t, cv) {
  const g = cv.getContext("2d"); g.setTransform(1, 0, 0, 1, 0, 0); g.clearRect(0, 0, CS.W, CS.H);
  const [x, y, z, r] = camAt(sh, t);
  g.save(); g.translate(CS.W / 2, CS.H / 2); g.rotate(r * Math.PI / 180); g.scale(z, z); g.translate(-x, -y);
  const lt = t - sh.start, M = g.getTransform();
  const toScreen = (px, py) => { const p = M.transformPoint(new DOMPoint(px, py)); return [p.x, p.y]; };
  const screen = fn => { g.save(); g.setTransform(1, 0, 0, 1, 0, 0); fn(g); g.restore(); };
  sh.draw(g, { t, lt, k: clamp(lt / sh.dur), dur: sh.dur, T: plan.T, shot: sh, cam: [x, y, z, r], toScreen, screen });
  g.restore();
}

// ---------- one frame ----------
CS.frame = function (t, T) {
  const S = window.SHORT;
  if (!plan || plan.T !== T) plan = build(T);
  const L = plan.shots; let i = 0; while (i < L.length - 1 && t >= L[i + 1].start) i++;
  const sh = L[i], next = L[i + 1], prev = L[i - 1], g = CS.g, W = CS.W, H = CS.H, WIN = .15;
  g.setTransform(1, 0, 0, 1, 0, 0); g.globalAlpha = 1; g.filter = "none";
  let mode = null, k = 0, dir = (i % 2 ? -1 : 1);
  if (next && (next.tr || "whip") !== "cut" && t > next.start - WIN) { mode = next.tr || "whip"; k = (t - (next.start - WIN)) / WIN; dir = ((i + 1) % 2 ? -1 : 1); }        // leaving
  else if (prev && (sh.tr || "whip") !== "cut" && t < sh.start + WIN) { mode = (sh.tr || "whip") + "-in"; k = (t - sh.start) / WIN; }                                    // arriving
  renderShot(sh, t, buf);
  if (!mode) g.drawImage(buf, 0, 0);
  else if (mode === "whip" || mode === "whip-in") {
    const out = mode === "whip", e = out ? ease.in(clamp(k)) : 1 - ease.out(clamp(k)), off = (out ? -1 : 1) * dir * e * W * .55, blur = e * 26;
    g.fillStyle = "#fff"; g.fillRect(0, 0, W, H);
    g.filter = blur > 1 ? `blur(${blur.toFixed(1)}px)` : "none";
    const n = 6; for (let j = 0; j < n; j++) { g.globalAlpha = j === 0 ? 1 : .22; g.drawImage(buf, off - (out ? -1 : 1) * dir * j * e * 60, 0); }
    g.globalAlpha = 1; g.filter = "none";
  } else if (mode === "pop" || mode === "pop-in") {
    const out = mode === "pop", e = out ? ease.in(clamp(k)) : 1 - ease.out(clamp(k)), z = 1 + e * (out ? .35 : .25);
    g.save(); g.translate(W / 2, H / 2); g.scale(z, z); g.translate(-W / 2, -H / 2); g.drawImage(buf, 0, 0); g.restore();
    g.fillStyle = `rgba(255,255,255,${e * .85})`; g.fillRect(0, 0, W, H);
  } else g.drawImage(buf, 0, 0);
  // post
  const v = g.createRadialGradient(W / 2, H * .48, H * .3, W / 2, H * .5, H * .78); v.addColorStop(0, "rgba(20,10,30,0)"); v.addColorStop(1, `rgba(20,10,30,${S.vignette ?? .22})`);
  g.fillStyle = v; g.fillRect(0, 0, W, H);
  g.save(); g.globalAlpha = S.grain ?? .035; g.globalCompositeOperation = "overlay"; const p = g.createPattern(grain, "repeat"), o = Math.floor(rand(Math.floor(t * 30)) * 256);
  g.translate(o, -o); g.fillStyle = p; g.fillRect(-o, o, W + 256, H + 256); g.restore();
  const fl = S.flash ? S.flash(t, T) : 0; if (fl > 0) { g.fillStyle = `rgba(255,255,255,${clamp(fl)})`; g.fillRect(0, 0, W, H); }
  if (S.overlay) S.overlay(g, t, T);
  if (plan.caps) drawCaption(g, t, S.captions || {});
};

// ---------- captions: 1-2 words, lowercase, outlined ----------
function captions(T, o) {
  const subs = Object.entries(o.subs || {}).map(([k, v]) => [k.toLowerCase().split(/\s+/), v]);
  const W = T.words.map(w => ({ raw: w.w, start: w.start, end: w.end, star: /\*/.test(w.w), n: w.n, stop: /[.,!?;:…]$/.test(w.w.replace(/\*/g, "")) }));
  const toks = [];
  for (let i = 0; i < W.length; i++) {
    let hit = null; for (const [ks, v] of subs) if (ks.every((kk, j) => W[i + j] && W[i + j].n === kk.replace(/[^a-z0-9]/g, ""))) { hit = [ks.length, v]; break; }
    if (hit) { const a = W[i], b = W[i + hit[0] - 1]; toks.push({ text: hit[1], start: a.start, end: b.end, star: a.star, stop: b.stop }); i += hit[0] - 1; continue; }
    const w = W[i]; let tx = w.raw.replace(/\*/g, "").replace(/[“”"()]/g, "").replace(/[.,!?;:…—–]+$/g, "").replace(/^[—–-]+/, "");
    if (!o.upper) tx = tx.toLowerCase(); if (tx) toks.push({ text: tx, start: w.start, end: w.end, star: w.star, stop: w.stop });
  }
  const list = [];
  for (let i = 0; i < toks.length; i++) {
    const a = toks[i], b = toks[i + 1];
    if (b && !a.stop && !a.star && !b.star && a.text.length <= 7 && b.text.length <= 7 && (a.text + b.text).length <= 11 && b.start - a.end < .25) { list.push({ text: a.text + " " + b.text, start: a.start, end: b.end }); i++; }
    else list.push({ text: a.text, start: a.start, end: a.end, star: a.star });
  }
  list.forEach((c, i) => { const n = list[i + 1]; c.until = n ? Math.min(n.start, c.end + .55) : c.end + .5; c.start -= .03; });
  return list;
}
function drawCaption(g, t, o) {
  if ((o.hide || []).some(([a, b]) => t >= a && t < b)) return;
  const c = plan.caps.find(c => t >= c.start && t < c.until); if (!c) return;
  const k = clamp((t - c.start) / .12), sc = .82 + .18 * ease.back(k), size = o.size || 104;
  g.save(); g.font = "700 " + size + "px " + CS.FONT; let w = g.measureText(c.text).width; const fit = Math.min(1, (CS.W * .78) / w); g.restore();
  g.save(); g.shadowColor = "rgba(0,0,0,.35)"; g.shadowOffsetY = 8; g.shadowBlur = 0;
  CS.label(g, c.text, CS.W / 2, o.y || 1330, { size, color: c.star ? (o.star || "#ffd23a") : (o.color || "#fff"), scale: sc * fit, stroke: .3 });
  g.restore();
}
CS.captionList = () => plan && plan.caps;
})();
