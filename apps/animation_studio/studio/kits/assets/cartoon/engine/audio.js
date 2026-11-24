/* Cartoon Shorts engine: sound. Voice + a synthesized music bed + sound effects, all made in the page with Web Audio,
   so the Play button, the Export button and render.mjs all hear exactly the same mix. Free from Anylancer.com. */
(function () {
const CS = window.CS = window.CS || {};
const { rand } = CS;
const A = CS.audio = { voice: null, cues: [], musicPlan: null, levels: { voice: 1, music: .06, sfx: .36 } };
const mtof = m => 440 * Math.pow(2, (m - 69) / 12);

// ---------- story API ----------
// music({style:'march'|'sneak'|'folk'|'whimsy'|'tense', bpm, key (midi root), sections:[{at, style|'stop'|'drone'}], end, gain})
A.music = function (o) { A.musicPlan = o; };
// sfx(name, t, gain = 1, opt) e.g. sfx('whoosh', T.w('army') - .1)
A.sfx = function (name, t, gain = 1, opt = {}) { if (t != null && isFinite(t)) A.cues.push({ name, t, gain, opt }); };
A.reset = function () { A.cues = []; A.musicPlan = null; };

// ---------- building blocks ----------
let NOISE = new WeakMap();
function noiseBuf(ctx) { if (NOISE.has(ctx)) return NOISE.get(ctx); const b = ctx.createBuffer(1, ctx.sampleRate * 2, ctx.sampleRate), d = b.getChannelData(0); for (let i = 0; i < d.length; i++) d[i] = rand(i + 99) * 2 - 1; NOISE.set(ctx, b); return b; }
function env(ctx, g, t, a, d, peak, sus = 0, rel = .05) { g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(peak, t + a); g.gain.exponentialRampToValueAtTime(Math.max(peak * sus, 1e-4), t + a + d); g.gain.linearRampToValueAtTime(0, t + a + d + rel); }
function osc(ctx, out, type, f, t, dur, vol, o = {}) {
  const s = ctx.createOscillator(), g = ctx.createGain(); s.type = type; s.frequency.setValueAtTime(f, t);
  if (o.to) s.frequency.exponentialRampToValueAtTime(o.to, t + (o.glide || dur));
  if (o.detune) s.detune.value = o.detune;
  if (o.vib) { const l = ctx.createOscillator(), lg = ctx.createGain(); l.frequency.value = o.vib[0]; lg.gain.value = o.vib[1]; l.connect(lg); lg.connect(s.frequency); l.start(t); l.stop(t + dur + .2); }
  let node = s; if (o.lp || o.bp) { const f2 = ctx.createBiquadFilter(); f2.type = o.bp ? "bandpass" : "lowpass"; f2.frequency.value = o.bp || o.lp; f2.Q.value = o.q || .8; s.connect(f2); node = f2; }
  node.connect(g); g.connect(out); env(ctx, g, t, o.a ?? .005, o.d ?? dur, vol, o.s ?? 0, o.r ?? .05); s.start(t); s.stop(t + dur + (o.r ?? .05) + .3);
}
function noise(ctx, out, t, dur, vol, o = {}) {
  const s = ctx.createBufferSource(); s.buffer = noiseBuf(ctx); s.loop = true; const f = ctx.createBiquadFilter(); f.type = o.type || "bandpass"; f.frequency.setValueAtTime(o.f || 1000, t); f.Q.value = o.q || 1;
  if (o.to) f.frequency.exponentialRampToValueAtTime(o.to, t + (o.glide || dur));
  const g = ctx.createGain(); s.connect(f); f.connect(g); g.connect(out); env(ctx, g, t, o.a ?? .005, o.d ?? dur, vol, o.s ?? 0, o.r ?? .05);
  s.start(t, rand(t * 100) * 1.5); s.stop(t + dur + .4);
}

// ---------- instruments ----------
const INST = {
  kick: (c, o, t, v) => { osc(c, o, "sine", 130, t, .28, v, { to: 42, glide: .12 }); },
  snare: (c, o, t, v) => { noise(c, o, t, .16, v * .6, { f: 1800, q: .7 }); osc(c, o, "triangle", 190, t, .08, v * .4); },
  hat: (c, o, t, v) => { noise(c, o, t, .04, v * .35, { type: "highpass", f: 7000 }); },
  brush: (c, o, t, v) => { noise(c, o, t, .12, v * .25, { f: 4000, q: .5, a: .02 }); },
  stomp: (c, o, t, v) => { osc(c, o, "sine", 90, t, .18, v, { to: 50 }); noise(c, o, t, .05, v * .3, { f: 400 }); },
  timp: (c, o, t, v, m) => { osc(c, o, "sine", mtof(m), t, 1.2, v, { to: mtof(m) * .97 }); noise(c, o, t, .1, v * .2, { f: 300 }); },
  tuba: (c, o, t, v, m, d) => { osc(c, o, "square", mtof(m), t, d * .8, v * .5, { lp: 420, a: .015, s: .6, d: d * .5 }); },
  bass: (c, o, t, v, m, d) => { osc(c, o, "triangle", mtof(m), t, d, v, { a: .005, d: d * .9, s: .3 }); },
  pizz: (c, o, t, v, m) => { osc(c, o, "triangle", mtof(m), t, .22, v, { d: .2 }); osc(c, o, "sine", mtof(m) * 2, t, .1, v * .3); },
  pluck: (c, o, t, v, m) => { osc(c, o, "sawtooth", mtof(m), t, .35, v * .35, { lp: 2400, d: .3 }); osc(c, o, "triangle", mtof(m), t, .4, v * .5, { d: .38 }); },
  brass: (c, o, t, v, m, d) => { for (const dt of [-7, 7]) osc(c, o, "sawtooth", mtof(m), t, d, v * .22, { lp: 1600, detune: dt, a: .03, d, s: .7, r: .08 }); },
  stab: (c, o, t, v, m) => { for (const dt of [-6, 6]) osc(c, o, "sawtooth", mtof(m), t, .14, v * .2, { lp: 2000, detune: dt, a: .01, d: .12 }); },
  whistle: (c, o, t, v, m, d) => { osc(c, o, "sine", mtof(m), t, d, v * .5, { a: .03, d, s: .8, vib: [5.5, 4], r: .06 }); osc(c, o, "sine", mtof(m) * 2, t, d, v * .08, { a: .03, d, s: .8 }); },
  fiddle: (c, o, t, v, m, d) => { osc(c, o, "sawtooth", mtof(m), t, d, v * .22, { lp: 2600, a: .05, d, s: .8, vib: [5.8, 5], r: .1 }); },
  glock: (c, o, t, v, m) => { osc(c, o, "sine", mtof(m), t, .9, v * .5, { d: .85 }); osc(c, o, "sine", mtof(m) * 2.76, t, .3, v * .15, { d: .28 }); },
  pad: (c, o, t, v, m, d) => { for (const dt of [-9, 0, 9]) osc(c, o, "sawtooth", mtof(m), t, d, v * .08, { lp: 900, detune: dt, a: .4, d, s: .9, r: .5 }); },
  drone: (c, o, t, v, m, d) => { for (const dt of [-5, 5]) osc(c, o, "sawtooth", mtof(m), t, d, v * .12, { lp: 300, detune: dt, a: .6, d, s: 1, r: .6 }); },
};
const SCALE = { major: [0, 2, 4, 5, 7, 9, 11], minor: [0, 2, 3, 5, 7, 8, 10] };
const PROG = { major: [[0, 4], [3, 5], [4, 7], [0, 4]], minor: [[0, 3], [5, 8], [3, 6], [4, 7]] };
// style -> per-bar note events [time offset in beats, inst, midi, beats, vel]
function barEvents(style, bar, root) {
  const ev = [], minor = style === "sneak" || style === "tense", sc = SCALE[minor ? "minor" : "major"], ch = (PROG[minor ? "minor" : "major"])[bar % 4];
  const deg = d => root + sc[((d % 7) + 7) % 7] + 12 * Math.floor(d / 7), crd = ch[0];
  const tri = [deg(crd), deg(crd + 2), deg(crd + 4)];
  const mel = k => { const r = rand(Math.floor(bar / 2) * 31 + k + (bar % 2 ? 0 : 0)); return deg(crd + [0, 2, 4, 7, 4, 2][Math.floor(r * 6)] + 7); };
  if (style === "march") {
    ev.push([0, "tuba", tri[0] - 24, 1, .9], [2, "tuba", tri[0] - 17, 1, .8], [1, "stab", tri[1], .5, .7], [3, "stab", tri[2], .5, .7]);
    ev.push([0, "kick", 0, 1, .7], [2, "kick", 0, 1, .6], [1, "snare", 0, 1, .55], [3, "snare", 0, 1, .55]);
    if (bar % 4 === 3) ev.push([3.5, "snare", 0, .5, .4], [3.75, "snare", 0, .5, .45]);
    if (bar % 2 === 0) [0, 1, 1.5, 2, 3].forEach((b, k) => ev.push([b, "whistle", mel(k), b === 3 ? 1 : .5, .55]));
    else [0, 2].forEach((b, k) => ev.push([b, "whistle", mel(k + 3), 1.5, .5]));
  } else if (style === "sneak") {
    const walk = [0, 1, 2, 3, 4, 3, 2, 1]; walk.forEach((s, i) => ev.push([i * .5, "pizz", deg(crd + s) - 12, .5, i % 2 ? .55 : .75]));
    [.5, 1.5, 2.5, 3.5].forEach(b => ev.push([b, "brush", 0, .5, .6])); [1, 3].forEach(b => ev.push([b, "snare", 0, .5, .15]));
    if (bar % 2 === 1) ev.push([2, "glock", mel(1), 1, .35], [3, "glock", mel(2), 1, .3]);
    ev.push([0, "pad", tri[0], 4, .5]);
  } else if (style === "folk") {
    ev.push([0, "stomp", 0, 1, .7], [2, "stomp", 0, 1, .6], [1, "hat", 0, 1, .5], [3, "hat", 0, 1, .5]);
    [0, 1, 2, 3].forEach(b => ev.push([b, "pluck", b % 2 ? tri[1] : tri[0] - 12, 1, .55], [b + .5, "pluck", tri[2], .5, .35]));
    if (bar % 2 === 0) [0, .5, 1, 2, 2.5, 3].forEach((b, k) => ev.push([b, "fiddle", mel(k), .5, .5])); else ev.push([0, "fiddle", mel(5), 2, .5], [2, "fiddle", mel(6), 2, .45]);
  } else if (style === "whimsy") {
    [0, 1, 2, 3].forEach(b => ev.push([b, "pizz", b % 2 ? tri[2] - 12 : tri[0] - 12, 1, .6]));
    [0, .5, 1.5, 2, 3].forEach((b, k) => ev.push([b, "glock", mel(k), .5, .4])); ev.push([0, "pad", tri[0], 4, .5]);
  } else if (style === "tense") {
    ev.push([0, "drone", tri[0] - 24, 4, .9]); [0, 1, 2, 3].forEach(b => ev.push([b, "pizz", tri[0] - 12, .5, .35]));
    if (bar % 2) ev.push([3.5, "timp", tri[0] - 24, .5, .5]);
  } else if (style === "drone") ev.push([0, "drone", root - 24, 4, .8]);
  return ev;
}

// ---------- sound effects ----------
const SFX = {
  whoosh: (c, o, t, v, p) => noise(c, o, t, p.dur || .45, v * .8, { f: 300, to: 2600, glide: (p.dur || .45) * .6, q: 1.2, a: (p.dur || .45) * .5, d: (p.dur || .45) * .5 }),
  swish: (c, o, t, v) => noise(c, o, t, .18, v * .6, { f: 1500, to: 5000, q: 1.5, a: .06, d: .12 }),
  pop: (c, o, t, v) => osc(c, o, "sine", 520, t, .09, v * .8, { to: 1300, glide: .06 }),
  boing: (c, o, t, v) => osc(c, o, "sine", 180, t, .55, v * .8, { to: 360, glide: .5, vib: [16, 40] }),
  thunk: (c, o, t, v) => { osc(c, o, "sine", 140, t, .22, v, { to: 48, glide: .15 }); noise(c, o, t, .05, v * .4, { f: 800 }); },
  step: (c, o, t, v) => { osc(c, o, "sine", 110, t, .08, v * .5, { to: 60 }); noise(c, o, t, .04, v * .2, { f: 600 }); },
  ting: (c, o, t, v) => { INST.glock(c, o, t, v * 1.4, 91); INST.glock(c, o, t + .08, v, 96); },
  magic: (c, o, t, v) => { [84, 88, 91, 96, 100].forEach((m, i) => INST.glock(c, o, t + i * .06, v * .9, m)); },
  sting: (c, o, t, v) => { osc(c, o, "sine", 55, t, 1.4, v, { to: 40 }); noise(c, o, t, .3, v * .4, { f: 200, type: "lowpass" }); for (const m of [50, 51, 57]) INST.brass(c, o, t, v * 1.2, m, 1.1); },
  crash: (c, o, t, v, p) => { noise(c, o, t, p.dur || 1.3, v, { type: "lowpass", f: 5000, to: 300, d: p.dur || 1.3 }); osc(c, o, "sine", 60, t, .6, v * .8, { to: 35 }); },
  bang: (c, o, t, v) => { noise(c, o, t, .35, v, { type: "lowpass", f: 3000, to: 200, d: .35 }); osc(c, o, "sine", 90, t, .3, v, { to: 40 }); },
  boom: (c, o, t, v) => { noise(c, o, t, 1.2, v * .9, { type: "lowpass", f: 900, to: 80, d: 1.2 }); osc(c, o, "sine", 60, t, 1, v, { to: 28 }); },
  rattle: (c, o, t, v, p) => { const n = p.n || 8; for (let i = 0; i < n; i++) { const tt = t + i * (p.gap || .09); noise(c, o, tt, .05, v * .7, { f: 1400, q: .8 }); osc(c, o, "sine", 120, tt, .06, v * .5, { to: 60 }); } },
  squawk: (c, o, t, v, p) => { const f = p.f || 330; osc(c, o, "sawtooth", f, t, .32, v * .45, { to: f * 1.5, glide: .12, vib: [28, 30], bp: 1300, q: 2, a: .02, d: .3 }); },
  boomdrum: (c, o, t, v) => { for (let i = 0; i < 3; i++) osc(c, o, "sine", 70, t + i * .18, .14, v * .7, { to: 55 }); },
  oink: (c, o, t, v) => { for (let i = 0; i < 2; i++) osc(c, o, "sawtooth", 210, t + i * .2, .16, v * .6, { to: 300, glide: .07, bp: 900, q: 4, a: .01, d: .15 }); },
  crowd: (c, o, t, v, p) => { const d = p.dur || 2; noise(c, o, t, d, v * .35, { f: 650, q: .6, a: .4, d, s: .9, r: .4 }); for (let i = 0; i < d * 6; i++) noise(c, o, t + i / 6, .15, v * .12 * rand(i + t), { f: 800 + rand(i) * 900, q: 3 }); },
  gasp: (c, o, t, v) => noise(c, o, t, .3, v * .4, { f: 1800, to: 2600, q: 2, a: .05, d: .25 }),
  creak: (c, o, t, v) => osc(c, o, "sawtooth", 80, t, .7, v * .35, { to: 120, glide: .7, bp: 700, q: 8, vib: [9, 6], a: .05 }),
  paper: (c, o, t, v) => { for (let i = 0; i < 3; i++) noise(c, o, t + i * .07, .06, v * .5, { type: "highpass", f: 3000 }); },
  engine: (c, o, t, v, p) => { const d = p.dur || 2; osc(c, o, "sawtooth", 55, t, d, v * .25, { lp: 300, vib: [12, 6], a: .2, d, s: .9, r: .3 }); osc(c, o, "square", 110, t, d, v * .06, { lp: 500, a: .2, d, s: .9 }); },
  splash: (c, o, t, v) => noise(c, o, t, .7, v * .8, { type: "lowpass", f: 2400, to: 400, d: .7 }),
  bell: (c, o, t, v) => { for (const [m, k] of [[1, 1], [2.4, .4], [3.9, .25], [5.4, .15]]) osc(c, o, "sine", 440 * m, t, 2.2, v * .3 * k, { d: 2.1 }); },
  drumroll: (c, o, t, v, p) => { const d = p.dur || 1, n = Math.round(d * 22); for (let i = 0; i < n; i++) noise(c, o, t + i / 22, .05, v * (.2 + .6 * i / n), { f: 1900 }); },
  snore: (c, o, t, v, p) => { const d = p.dur || 2.4; for (let i = 0; i < d / 1.2; i++) noise(c, o, t + i * 1.2, .7, v * .35, { type: "lowpass", f: 500, a: .35, d: .35 }); },
  kaching: (c, o, t, v) => { INST.glock(c, o, t, v * 1.5, 96); noise(c, o, t, .2, v * .3, { type: "highpass", f: 5000 }); },
  slideup: (c, o, t, v) => osc(c, o, "sine", 400, t, .5, v * .5, { to: 1600, glide: .45, vib: [7, 15], a: .03 }),
  slidedown: (c, o, t, v) => osc(c, o, "sine", 1500, t, .55, v * .5, { to: 300, glide: .5, vib: [7, 15], a: .03 }),
  click: (c, o, t, v) => noise(c, o, t, .02, v * .6, { type: "highpass", f: 2500 }),
  tick: (c, o, t, v, p) => { const n = p.n || 4; for (let i = 0; i < n; i++) noise(c, o, t + i * (p.gap || .25), .02, v * .5, { f: 3000, q: 4 }); },
  horn: (c, o, t, v) => { for (const f of [330, 415]) osc(c, o, "square", f, t, .35, v * .2, { lp: 1500, a: .02, d: .33 }); },
  cannon: (c, o, t, v) => SFX.boom(c, o, t, v),
  hit: (c, o, t, v) => { osc(c, o, "sine", 80, t, .5, v, { to: 35 }); noise(c, o, t, .12, v * .5, { type: "lowpass", f: 1500 }); },
  wind: (c, o, t, v, p) => { const d = p.dur || 3; noise(c, o, t, d, v * .25, { f: 500, to: 900, glide: d, q: .7, a: d * .3, d, s: .8, r: .5 }); },
  waves: (c, o, t, v, p) => { const d = p.dur || 4; for (let i = 0; i < d / 1.6; i++) noise(c, o, t + i * 1.6, 1.4, v * .3, { type: "lowpass", f: 900, a: .6, d: .8 }); },
  birds: (c, o, t, v, p) => { for (let i = 0; i < (p.n || 4); i++) osc(c, o, "sine", 2400 + rand(i + t) * 900, t + i * .21, .09, v * .25, { to: 3600, glide: .06 }); },
  flap: (c, o, t, v, p) => { for (let i = 0; i < (p.n || 6); i++) noise(c, o, t + i * .09, .06, v * .4, { f: 500, q: .8 }); },
};
A.SFX = SFX; A.INST = INST;

// ---------- scheduling ----------
// build(ctx, dest, ctxStart, from): schedules everything from story time `from` at context time ctxStart
A.build = function (ctx, dest, ctxStart = 0, from = 0, dur = 60) {
  const L = A.levels;
  const master = ctx.createGain(); master.gain.value = .9;
  const comp = ctx.createDynamicsCompressor(); comp.threshold.value = -8; comp.ratio.value = 6; comp.attack.value = .003; comp.release.value = .15;
  master.connect(comp); comp.connect(dest);
  const busM = ctx.createGain(), busS = ctx.createGain(), busV = ctx.createGain();
  busM.gain.value = L.music * (A.musicPlan?.gain ?? 1); busS.gain.value = L.sfx; busV.gain.value = L.voice;
  busM.connect(master); busS.connect(master); busV.connect(master);
  const at = t => ctxStart + (t - from);
  if (A.voice && from < A.voice.duration) { const s = ctx.createBufferSource(); s.buffer = A.voice; s.connect(busV); s.start(ctxStart, from); }
  const M = A.musicPlan;
  if (M) {
    const bpm = M.bpm || 112, beat = 60 / bpm, bar = beat * 4, root = M.key ?? 58, end = Math.min(M.end ?? dur, dur);
    const secs = (M.sections || [{ at: 0, style: M.style }]).slice().sort((a, b) => a.at - b.at);
    const styleAt = t => { let s = M.style; for (const x of secs) if (t >= x.at - 1e-3) s = x.style; return s; };
    const t0 = M.start || 0;
    for (let b = 0; t0 + b * bar < end; b++) {
      const tb = t0 + b * bar, st = styleAt(tb);
      if (st === "stop") continue;
      for (const [ob, inst, m, len, vel] of barEvents(st, b, root)) {
        const t = tb + ob * beat; if (t < from - .01 || t >= end) continue;
        const stNow = styleAt(t); if (stNow === "stop" || stNow !== st) continue;
        INST[inst](ctx, busM, at(t), vel * .5, m, len * beat);
      }
    }
    // fade the bed out at the end
    busM.gain.setValueAtTime(busM.gain.value, Math.max(ctxStart, at(end - 1.2))); busM.gain.linearRampToValueAtTime(0.0001, Math.max(ctxStart + .01, at(end)));
  }
  for (const q of A.cues) if (q.t >= from - .01 && q.t < dur && SFX[q.name]) SFX[q.name](ctx, busS, at(q.t), q.gain, q.opt || {});
  return master;
};
// real-time playback (Play / Export). Returns {ctx, startedAt, stream?}
let live = null;
A.play = function (from = 0, dur = 60, wantStream = false) {
  A.stop();
  const ctx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 48000 });
  let dest = ctx.destination, streamDest = null;
  if (wantStream) { streamDest = ctx.createMediaStreamDestination(); const split = ctx.createGain(); split.connect(ctx.destination); split.connect(streamDest); dest = split; }
  const startAt = ctx.currentTime + .08;
  A.build(ctx, dest, startAt, from, dur);
  live = { ctx, startAt, from, stream: streamDest && streamDest.stream };
  return live;
};
A.now = function () { return live ? live.from + (live.ctx.currentTime - live.startAt) : 0; };
A.stop = function () { if (live) { try { live.ctx.close(); } catch (e) {} live = null; } };
// offline render for render.mjs -> base64 WAV (16-bit stereo 48 kHz)
A.renderWav = async function (dur) {
  const sr = 48000, ctx = new OfflineAudioContext(2, Math.ceil(dur * sr), sr);
  A.build(ctx, ctx.destination, 0, 0, dur);
  const buf = await ctx.startRendering();
  const n = buf.length, data = new DataView(new ArrayBuffer(44 + n * 4)), ch = [buf.getChannelData(0), buf.getChannelData(1)];
  const ws = (o, s) => { for (let i = 0; i < s.length; i++) data.setUint8(o + i, s.charCodeAt(i)); };
  ws(0, "RIFF"); data.setUint32(4, 36 + n * 4, true); ws(8, "WAVEfmt "); data.setUint32(16, 16, true); data.setUint16(20, 1, true); data.setUint16(22, 2, true);
  data.setUint32(24, sr, true); data.setUint32(28, sr * 4, true); data.setUint16(32, 4, true); data.setUint16(34, 16, true); ws(36, "data"); data.setUint32(40, n * 4, true);
  for (let i = 0, o = 44; i < n; i++) for (let c = 0; c < 2; c++, o += 2) data.setInt16(o, Math.max(-1, Math.min(1, ch[c][i])) * 32767, true);
  const bytes = new Uint8Array(data.buffer); let s = ""; const CH = 0x8000;
  for (let i = 0; i < bytes.length; i += CH) s += String.fromCharCode.apply(null, bytes.subarray(i, i + CH));
  return btoa(s);
};
// decode an mp3/wav (ArrayBuffer or base64) to an AudioBuffer
A.decode = async function (data) {
  if (typeof data === "string") { const bin = atob(data); const u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i); data = u.buffer; }
  const ctx = new OfflineAudioContext(2, 48000, 48000); return await ctx.decodeAudioData(data);
};
})();
