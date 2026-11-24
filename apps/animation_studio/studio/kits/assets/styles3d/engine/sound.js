/* SOUND kit v1 (Claude 3D Styles, free from Anylancer.com)
   Every sound is synthesised in code with Web Audio: no files, no downloads, frame-exact.
   A style's sound(k) schedules events on the same clock as the picture:
       k.at(1.2, "pop", { vol: .8, pitch: 1.2, pan: -.3 })
       k.bed("room", 0, 8, { vol: .4 })            // ambience between two times
       k.chords(0, 8, ["C4 E4 G4", "A3 C4 E4"], { bpm: 96, vol: .3 })   // soft music pad
   Live:    const stop = SOUND.live((k) => style.sound(k), fromTime, { voiceover: false })
   Offline: const buf = await SOUND.renderOffline((k) => style.sound(k), duration, 48000, { voiceover: false }); SOUND.wav(buf) -> ArrayBuffer
   Voices: pop click tick tap thud knock wood clay paper whoosh swish rise drop hit boom chime bell glass ping sparkle coin pluck zap bubble spring snap blip type servo
   Beds:   room wind hum neon rain water crowd motor   Music: k.chords / k.note */
(function () {
  const SOUND = (window.SOUND = window.SOUND || {});
  const NOTE = (n) => { if (typeof n === "number") return n; const m = /^([A-G])(#|b)?(-?\d)$/.exec(n.trim()); if (!m) return 440; const st = { C: -9, D: -7, E: -5, F: -4, G: -2, A: 0, B: 2 }[m[1]] + (m[2] === "#" ? 1 : m[2] === "b" ? -1 : 0) + (m[3] - 4) * 12; return 440 * Math.pow(2, st / 12); };
  SOUND.note = NOTE;

  function build(ctx, opts = {}) {
    const vo = !!opts.voiceover, sr = ctx.sampleRate;
    // deterministic noise buffer
    const nb = ctx.createBuffer(1, sr * 2, sr), nd = nb.getChannelData(0); let s = 12345;
    for (let i = 0; i < nd.length; i++) { s = (s * 1103515245 + 12345) & 0x7fffffff; nd[i] = (s / 0x7fffffff) * 2 - 1; }
    // master: fx bus + bed bus + music bus -> compressor -> out ; reverb send
    const comp = ctx.createDynamicsCompressor(); comp.threshold.value = -14; comp.knee.value = 10; comp.ratio.value = 3; comp.attack.value = 0.004; comp.release.value = 0.2;
    const master = ctx.createGain(); master.gain.value = 0.9; comp.connect(master); master.connect(ctx.destination);
    let streamDest = null; if (opts.stream && ctx.createMediaStreamDestination) { streamDest = ctx.createMediaStreamDestination(); master.connect(streamDest); }
    const fx = ctx.createGain(), beds = ctx.createGain(), music = ctx.createGain();
    fx.gain.value = vo ? 0.6 : 1; beds.gain.value = vo ? 0.35 : 1; music.gain.value = vo ? 0.3 : 1;
    [fx, beds, music].forEach((g) => g.connect(comp));
    const verb = ctx.createConvolver(), ir = ctx.createBuffer(2, Math.floor(sr * 2.2), sr);
    for (let c = 0; c < 2; c++) { const d = ir.getChannelData(c); let q = 777 + c * 91; for (let i = 0; i < d.length; i++) { q = (q * 1103515245 + 12345) & 0x7fffffff; d[i] = ((q / 0x7fffffff) * 2 - 1) * Math.pow(1 - i / d.length, 3.2); } }
    verb.buffer = ir; const verbIn = ctx.createGain(); verbIn.gain.value = 0.22; verbIn.connect(verb); verb.connect(comp);

    const out = (bus, t, o) => { // per-voice output: gain -> pan -> bus (+ reverb send)
      const g = ctx.createGain(), p = ctx.createStereoPanner ? ctx.createStereoPanner() : null; g.gain.value = 0;
      if (p) { p.pan.value = Math.max(-1, Math.min(1, o.pan || 0)); g.connect(p); p.connect(bus); if (o.verb !== 0) { const sd = ctx.createGain(); sd.gain.value = o.verb ?? 0.5; p.connect(sd); sd.connect(verbIn); } } else g.connect(bus);
      return g;
    };
    const env = (param, t, a, d, peak, hold = 0) => { param.setValueAtTime(0, t); param.linearRampToValueAtTime(peak, t + a); if (hold) param.setValueAtTime(peak, t + a + hold); param.exponentialRampToValueAtTime(0.0001, t + a + hold + d); param.setValueAtTime(0, t + a + hold + d + 0.01); };
    const osc = (type, f, t, dur, dest) => { const o = ctx.createOscillator(); o.type = type; o.frequency.setValueAtTime(f, t); o.connect(dest); o.start(t); o.stop(t + dur + 0.05); return o; };
    const noise = (t, dur, dest, offset = 0) => { const n = ctx.createBufferSource(); n.buffer = nb; n.loop = true; n.connect(dest); n.start(t, offset % 1.9); n.stop(t + dur + 0.05); return n; };
    const filt = (type, f, q = 1, dest) => { const b = ctx.createBiquadFilter(); b.type = type; b.frequency.value = f; b.Q.value = q; b.connect(dest); return b; };
    let seed = 1; const rnd = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };

    const V = {
      pop(t, o, P) { const g = out(fx, t, o); env(g.gain, t, 0.003, 0.12, 0.5 * o.vol); const x = osc("sine", 700 * P, t, 0.15, g); x.frequency.exponentialRampToValueAtTime(260 * P, t + 0.08); },
      click(t, o, P) { const g = out(fx, t, o); env(g.gain, t, 0.001, 0.03, 0.45 * o.vol); noise(t, 0.05, filt("highpass", 2500 * P, 0.7, g)); },
      tick(t, o, P) { const g = out(fx, t, o); env(g.gain, t, 0.001, 0.04, 0.3 * o.vol); osc("sine", 2400 * P, t, 0.06, g); },
      tap(t, o, P) { const g = out(fx, t, o); env(g.gain, t, 0.001, 0.06, 0.45 * o.vol); noise(t, 0.08, filt("bandpass", 1800 * P, 1.5, g)); osc("sine", 520 * P, t, 0.05, g); },
      thud(t, o, P) { const g = out(fx, t, { verb: 0.2, ...o }); env(g.gain, t, 0.004, 0.3, 0.9 * o.vol); const x = osc("sine", 130 * P, t, 0.35, g); x.frequency.exponentialRampToValueAtTime(48 * P, t + 0.25); const g2 = out(fx, t, o); env(g2.gain, t, 0.002, 0.08, 0.35 * o.vol); noise(t, 0.1, filt("lowpass", 900 * P, 0.7, g2)); },
      knock(t, o, P) { const g = out(fx, t, o); env(g.gain, t, 0.001, 0.09, 0.6 * o.vol); osc("sine", 310 * P, t, 0.1, g); osc("triangle", 690 * P, t, 0.06, g); },
      wood(t, o, P) { const g = out(fx, t, o); env(g.gain, t, 0.001, 0.14, 0.55 * o.vol); const b = filt("bandpass", 900 * P, 6, g); noise(t, 0.04, b); osc("sine", 420 * P, t, 0.12, g); osc("sine", 1130 * P, t, 0.06, g); },
      clay(t, o, P) { const g = out(fx, t, { verb: 0.15, ...o }); env(g.gain, t, 0.01, 0.22, 0.7 * o.vol); const f = filt("lowpass", 1400 * P, 3, g); f.frequency.setValueAtTime(1600 * P, t); f.frequency.exponentialRampToValueAtTime(180 * P, t + 0.2); noise(t, 0.25, f); const x = osc("sine", 110 * P, t, 0.2, g); x.frequency.exponentialRampToValueAtTime(70, t + 0.18); },
      paper(t, o, P) { const d = o.dur || 0.35, g = out(fx, t, o); g.gain.setValueAtTime(0, t); for (let i = 0; i < 9; i++) { const tt = t + (i / 9) * d + rnd() * 0.02; g.gain.setValueAtTime(0.0001, tt); g.gain.linearRampToValueAtTime((0.2 + rnd() * 0.3) * o.vol, tt + 0.004); g.gain.exponentialRampToValueAtTime(0.0001, tt + 0.03); } noise(t, d + 0.05, filt("bandpass", 3800 * P, 0.8, g)); },
      whoosh(t, o, P) { const d = o.dur || 0.6, g = out(fx, t, { verb: 0.3, ...o }); g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(0.55 * o.vol, t + d * 0.55); g.gain.linearRampToValueAtTime(0, t + d); const f = filt("bandpass", 400, 1.4, g); f.frequency.setValueAtTime((o.down ? 3000 : 300) * P, t); f.frequency.exponentialRampToValueAtTime((o.down ? 300 : 2800) * P, t + d); noise(t, d, f, rnd()); },
      swish(t, o, P) { V.whoosh(t, { ...o, dur: o.dur || 0.28 }, P); },
      rise(t, o, P) { const d = o.dur || 1.2, g = out(fx, t, { verb: 0.4, ...o }); g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.35 * o.vol, t + d); g.gain.linearRampToValueAtTime(0, t + d + 0.05); const f = filt("bandpass", 300, 2, g); f.frequency.setValueAtTime(250 * P, t); f.frequency.exponentialRampToValueAtTime(5000 * P, t + d); noise(t, d, f); const x = osc("sawtooth", 110 * P, t, d, filt("lowpass", 1800, 1, g)); x.frequency.exponentialRampToValueAtTime(440 * P, t + d); },
      drop(t, o, P) { const d = o.dur || 0.5, g = out(fx, t, o); env(g.gain, t, 0.01, d, 0.4 * o.vol); const x = osc("sine", 900 * P, t, d, g); x.frequency.exponentialRampToValueAtTime(120 * P, t + d); },
      hit(t, o, P) { V.thud(t, { ...o, vol: o.vol * 1.1 }, P * 0.8); const g = out(fx, t, { verb: 0.6, ...o }); env(g.gain, t, 0.001, 0.4, 0.3 * o.vol); noise(t, 0.4, filt("lowpass", 3500 * P, 0.5, g)); },
      boom(t, o, P) { const g = out(fx, t, { verb: 0.7, ...o }); env(g.gain, t, 0.005, 1.4, 0.95 * o.vol); const x = osc("sine", 90 * P, t, 1.5, g); x.frequency.exponentialRampToValueAtTime(32, t + 1.2); const g2 = out(fx, t, o); env(g2.gain, t, 0.002, 0.7, 0.5 * o.vol); noise(t, 0.8, filt("lowpass", 700, 0.6, g2)); },
      chime(t, o, P) { const f = (o.f ? NOTE(o.f) : 1046) * P, g = out(fx, t, { verb: 0.7, ...o }); env(g.gain, t, 0.002, o.dur || 1.6, 0.28 * o.vol); const c = osc("sine", f, t, 2, g), m = ctx.createOscillator(), mg = ctx.createGain(); m.frequency.value = f * 3.5; mg.gain.setValueAtTime(f * 1.4, t); mg.gain.exponentialRampToValueAtTime(1, t + 1); m.connect(mg); mg.connect(c.frequency); m.start(t); m.stop(t + 2); },
      bell(t, o, P) { V.chime(t, { ...o, f: o.f || "C5", dur: o.dur || 2.4 }, P * 0.5); },
      glass(t, o, P) { const f = (o.f ? NOTE(o.f) : 2100) * P, g = out(fx, t, { verb: 0.6, ...o }); env(g.gain, t, 0.001, 0.9, 0.22 * o.vol); [1, 2.32, 4.25, 6.63].forEach((r, i) => { const gg = ctx.createGain(); gg.gain.value = [1, 0.5, 0.25, 0.12][i]; gg.connect(g); osc("sine", f * r, t, 1, gg); }); },
      ping(t, o, P) { const g = out(fx, t, { verb: 0.5, ...o }); env(g.gain, t, 0.001, 0.35, 0.25 * o.vol); osc("sine", (o.f ? NOTE(o.f) : 1568) * P, t, 0.4, g); },
      sparkle(t, o, P) { for (let i = 0; i < 6; i++) V.ping(t + i * 0.045, { ...o, vol: o.vol * (1 - i * 0.12), f: [2093, 2637, 3136, 2349, 3520, 4186][i] }, P); },
      coin(t, o, P) { const g = out(fx, t, o); g.gain.setValueAtTime(0.18 * o.vol, t); g.gain.setValueAtTime(0.18 * o.vol, t + 0.07); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.4); const x = osc("square", 988 * P, t, 0.45, filt("lowpass", 4000, 1, g)); x.frequency.setValueAtTime(1319 * P, t + 0.07); },
      pluck(t, o, P) { const f = (o.f ? NOTE(o.f) : 523) * P, g = out(music, t, { verb: 0.5, ...o }); env(g.gain, t, 0.003, o.dur || 0.7, 0.3 * o.vol); const lp = filt("lowpass", f * 6, 1, g); lp.frequency.setValueAtTime(f * 8, t); lp.frequency.exponentialRampToValueAtTime(f * 1.5, t + 0.4); osc("triangle", f, t, 1, lp); osc("sine", f * 2, t, 0.4, lp); },
      zap(t, o, P) { const g = out(fx, t, { verb: 0.4, ...o }); env(g.gain, t, 0.002, 0.25, 0.25 * o.vol); const x = osc("sawtooth", 1800 * P, t, 0.3, filt("lowpass", 3000, 2, g)); x.frequency.exponentialRampToValueAtTime(140 * P, t + 0.25); },
      bubble(t, o, P) { const g = out(fx, t, o); env(g.gain, t, 0.002, 0.08, 0.4 * o.vol); const x = osc("sine", 380 * P, t, 0.1, g); x.frequency.exponentialRampToValueAtTime(1300 * P, t + 0.07); },
      spring(t, o, P) { const g = out(fx, t, o); env(g.gain, t, 0.002, 0.45, 0.3 * o.vol); const x = osc("sine", 300 * P, t, 0.5, g), l = ctx.createOscillator(), lg = ctx.createGain(); l.frequency.value = 22; lg.gain.setValueAtTime(140 * P, t); lg.gain.exponentialRampToValueAtTime(5, t + 0.45); l.connect(lg); lg.connect(x.frequency); l.start(t); l.stop(t + 0.5); },
      snap(t, o, P) { const g = out(fx, t, o); env(g.gain, t, 0.0005, 0.025, 0.6 * o.vol); noise(t, 0.04, filt("highpass", 3500 * P, 0.7, g)); },
      blip(t, o, P) { const g = out(fx, t, o); env(g.gain, t, 0.002, 0.08, 0.2 * o.vol); osc("square", (o.f ? NOTE(o.f) : 880) * P, t, 0.1, filt("lowpass", 3000, 1, g)); },
      type(t, o, P) { const n = o.n || 8; for (let i = 0; i < n; i++) V.tap(t + i * (o.gap || 0.07) + rnd() * 0.015, { ...o, vol: o.vol * (0.5 + rnd() * 0.4) }, P * (0.9 + rnd() * 0.3)); },
      servo(t, o, P) { const d = o.dur || 0.4, g = out(fx, t, o); g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(0.16 * o.vol, t + 0.03); g.gain.setValueAtTime(0.16 * o.vol, t + d - 0.05); g.gain.linearRampToValueAtTime(0, t + d); const x = osc("sawtooth", 160 * P, t, d, filt("bandpass", 1200 * P, 3, g)); x.frequency.linearRampToValueAtTime(230 * P, t + d); },
    };
    const BEDS = {
      room(t0, t1, o, P) { const g = out(beds, t0, { verb: 0, ...o }); fadeBed(g, t0, t1, 0.07 * o.vol); noise(t0, t1 - t0, filt("lowpass", 500 * P, 0.5, g)); },
      wind(t0, t1, o, P) { const g = out(beds, t0, { verb: 0, ...o }); fadeBed(g, t0, t1, 0.12 * o.vol); const f = filt("bandpass", 600 * P, 0.8, g), l = ctx.createOscillator(), lg = ctx.createGain(); l.frequency.value = 0.13; lg.gain.value = 350 * P; l.connect(lg); lg.connect(f.frequency); l.start(t0); l.stop(t1 + 0.1); noise(t0, t1 - t0, f); },
      hum(t0, t1, o, P) { const g = out(beds, t0, { verb: 0, ...o }); fadeBed(g, t0, t1, 0.05 * o.vol); const lp = filt("lowpass", 400, 0.7, g); osc("sine", 55 * P, t0, t1 - t0, lp); osc("sine", 110 * P, t0, t1 - t0, lp); },
      neon(t0, t1, o, P) { const g = out(beds, t0, { verb: 0, ...o }); fadeBed(g, t0, t1, 0.025 * o.vol); osc("sawtooth", 120 * P, t0, t1 - t0, filt("bandpass", 1200, 4, g)); },
      rain(t0, t1, o, P) { const g = out(beds, t0, { verb: 0, ...o }); fadeBed(g, t0, t1, 0.09 * o.vol); noise(t0, t1 - t0, filt("highpass", 1500 * P, 0.4, g)); },
      water(t0, t1, o, P) { const g = out(beds, t0, { verb: 0.2, ...o }); fadeBed(g, t0, t1, 0.1 * o.vol); const f = filt("lowpass", 900 * P, 1, g), l = ctx.createOscillator(), lg = ctx.createGain(); l.frequency.value = 0.4; lg.gain.value = 300; l.connect(lg); lg.connect(f.frequency); l.start(t0); l.stop(t1 + 0.1); noise(t0, t1 - t0, f); },
      motor(t0, t1, o, P) { const g = out(beds, t0, { verb: 0, ...o }); fadeBed(g, t0, t1, 0.06 * o.vol); const x = osc("sawtooth", 70 * P, t0, t1 - t0, filt("lowpass", 500, 2, g)); },
      crowd(t0, t1, o, P) { const g = out(beds, t0, { verb: 0.4, ...o }); fadeBed(g, t0, t1, 0.08 * o.vol); noise(t0, t1 - t0, filt("bandpass", 900 * P, 0.6, g)); },
    };
    const fadeBed = (g, t0, t1, v) => { const f = Math.min(0.6, (t1 - t0) / 3); g.gain.setValueAtTime(0, t0); g.gain.linearRampToValueAtTime(v, t0 + f); g.gain.setValueAtTime(v, t1 - f); g.gain.linearRampToValueAtTime(0, t1); };
    const pad = (t, dur, freqs, o) => { const g = out(music, t, { verb: 0.6, ...o }), a = Math.min(0.5, dur / 3); g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(0.09 * o.vol, t + a); g.gain.setValueAtTime(0.09 * o.vol, t + dur - a); g.gain.linearRampToValueAtTime(0, t + dur + 0.2); const lp = filt("lowpass", o.bright || 1600, 0.7, g); freqs.forEach((f, i) => { osc(o.wave || "triangle", f * (1 + (i % 2 ? 0.003 : -0.003)), t, dur + 0.3, lp); }); };
    return { V, BEDS, pad, vo, music, streamDest, ctxTime: () => ctx.currentTime };
  }

  function makeK(ctx, base, from, opts) {
    const B = build(ctx, opts), list = [];
    const k = {
      voiceover: B.vo,
      at(t, name, o = {}) { list.push(() => { if (t < from - 0.01) return; const f = B.V[name]; if (!f) return; f(base + t - from + 0.001, { vol: 1, ...o }, o.pitch || 1); }); return k; },
      bed(name, t0, t1, o = {}) { list.push(() => { const a = Math.max(t0, from); if (t1 <= a + 0.05) return; const f = B.BEDS[name]; if (f) f(base + a - from + 0.001, base + t1 - from, { vol: 1, ...o }, o.pitch || 1); }); return k; },
      /** soft chord pad, one chord per bar: k.chords(0, 8, ["C4 E4 G4", "F3 A3 C4"], { bpm: 90, vol: .8, arp: true }) */
      chords(t0, t1, prog, o = {}) { const bar = (60 / (o.bpm || 90)) * 4; let i = 0; for (let t = t0; t < t1 - 0.05; t += bar, i++) { const ch = prog[i % prog.length].split(/\s+/).map(NOTE), dur = Math.min(bar, t1 - t); list.push(() => { if (t + dur < from) return; const a = Math.max(t, from); B.pad(base + a - from + 0.001, t + dur - a, ch, { vol: 1, ...o }); }); if (o.arp) ch.concat(ch.map((f) => f * 2)).forEach((f, j) => { const tt = t + j * (bar / 8); if (tt < t1) k.at(tt, "pluck", { f, vol: (o.arpVol || 0.35) * (o.vol || 1), pan: ((j % 3) - 1) * 0.3 }); }); } return k; },
      note(t, n, o = {}) { return k.at(t, "pluck", { ...o, f: n }); },
    };
    return { k, B, flush: () => list.forEach((f) => f()) };
  }

  /** play live from time `from`; returns stop(). With { stream: true }, stop.stream is a MediaStream of the mix (for recording) and stop.ctx the AudioContext */
  SOUND.live = (score, from = 0, opts = {}) => {
    const AC = window.AudioContext || window.webkitAudioContext, ctx = new AC({ latencyHint: "interactive" });
    const { k, B, flush } = makeK(ctx, ctx.currentTime + 0.06, from, opts); score(k); flush();
    const stop = () => { try { ctx.close(); } catch (e) {} };
    stop.ctx = ctx; stop.stream = B.streamDest ? B.streamDest.stream : null; stop.dest = B.streamDest; return stop;
  };
  /** render the whole score offline -> AudioBuffer (stereo) */
  SOUND.renderOffline = async (score, duration, sampleRate = 48000, opts = {}) => {
    const ctx = new OfflineAudioContext(2, Math.ceil(duration * sampleRate), sampleRate);
    const { k, flush } = makeK(ctx, 0, 0, opts); score(k); flush(); return ctx.startRendering();
  };
  /** AudioBuffer -> 16-bit WAV ArrayBuffer */
  SOUND.wav = (buf) => {
    const ch = buf.numberOfChannels, n = buf.length, sr = buf.sampleRate, ab = new ArrayBuffer(44 + n * ch * 2), v = new DataView(ab);
    const w = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
    w(0, "RIFF"); v.setUint32(4, 36 + n * ch * 2, true); w(8, "WAVE"); w(12, "fmt "); v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, ch, true); v.setUint32(24, sr, true); v.setUint32(28, sr * ch * 2, true); v.setUint16(32, ch * 2, true); v.setUint16(34, 16, true); w(36, "data"); v.setUint32(40, n * ch * 2, true);
    const data = []; for (let c = 0; c < ch; c++) data.push(buf.getChannelData(c));
    let o = 44; for (let i = 0; i < n; i++) for (let c = 0; c < ch; c++) { const x = Math.max(-1, Math.min(1, data[c][i])); v.setInt16(o, x < 0 ? x * 0x8000 : x * 0x7fff, true); o += 2; }
    return ab;
  };
})();
