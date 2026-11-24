/* Cartoon Shorts engine: voice timing. Lines the script up with the voiceover so every shot lands on its words.
   Exact word timings (ElevenLabs "with timestamps", Whisper...) win; otherwise the phrases are matched to the pauses in the audio. */
(function () {
const CS = window.CS = window.CS || {};
const norm = w => w.toLowerCase().replace(/[’']/g, "").replace(/[^a-z0-9ঀ-৿]+/g, "");
CS.syllables = function (w) {
  w = norm(w); if (!w) return 0; if (/^\d+$/.test(w)) return w.length * 1.5;
  if (/[ঀ-৿]/.test(w)) return Math.max(1, Math.round(w.length / 2));
  const m = w.replace(/e$/, "").match(/[aeiouy]+/g); return Math.max(1, m ? m.length : 1);
};
// split a script into phrases at punctuation (.,!?;:… and dashes)
CS.phrases = function (script) {
  const out = []; const parts = script.replace(/\s+/g, " ").trim().match(/[^.,!?;:…—–]+[.,!?;:…—–]*/g) || [];
  for (let p of parts) { p = p.trim(); if (!p) continue; const words = p.split(" ").filter(w => norm(w)); if (!words.length) { if (out.length) out[out.length - 1].text += p; continue; }
    out.push({ text: p, words, syl: words.reduce((s, w) => s + CS.syllables(w), 0), end: /[.!?…]$/.test(p) ? 2 : /[,;:—–]$/.test(p) ? 1 : 0 }); }
  return out;
};
function speechGaps(buf) {
  const sr = buf.sampleRate, hop = Math.round(sr * .01), n = Math.floor(buf.length / hop), ch = [];
  for (let c = 0; c < buf.numberOfChannels; c++) ch.push(buf.getChannelData(c));
  const rms = new Float32Array(n);
  for (let i = 0; i < n; i++) { let s = 0; for (let j = 0; j < hop; j++) { let v = 0; for (const d of ch) v += d[i * hop + j] || 0; v /= ch.length; s += v * v; } rms[i] = Math.sqrt(s / hop); }
  const sorted = Array.from(rms).sort((a, b) => a - b), lo = sorted[Math.floor(n * .1)], hi = sorted[Math.floor(n * .95)];
  const thr = lo + (hi - lo) * .1;
  const sp = Array.from(rms, v => v > thr);
  for (let i = 0; i < n; i++) if (!sp[i]) { let j = i; while (j < n && !sp[j]) j++; if (j - i < 6 && i > 0 && j < n) for (let k = i; k < j; k++) sp[k] = true; i = j; }   // fill tiny gaps
  let first = sp.indexOf(true), last = sp.lastIndexOf(true); if (first < 0) { first = 0; last = n - 1; }
  const gaps = [];
  for (let i = first; i <= last; i++) if (!sp[i]) { let j = i; while (j <= last && !sp[j]) j++; if (j - i >= 10) gaps.push({ a: i / 100, b: j / 100, len: (j - i) / 100 }); i = j; }
  return { start: first / 100, end: (last + 1) / 100, gaps };
}
function spread(ph, a, b) {   // word times inside a phrase by syllables
  let s = a; const tot = ph.syl || 1; ph.start = a; ph.end = b;
  ph.wt = ph.words.map(w => { const d = (b - a) * CS.syllables(w) / tot; const o = { w, start: s, end: s + d }; s += d; return o; });
}
/* align(script, audioBuffer?, exactWords?) -> T
   T.phrases[i] = {text, start, end, wt:[{w,start,end}]} ; T.p(i) start, T.e(i) end, T.w("phrase words", after) start of those words, T.we(...) their end */
CS.align = function (script, buf, exact) {
  const P = CS.phrases(script); const N = P.length;
  let dur = buf ? buf.duration : 0;
  if (exact && exact.length) {
    const ew = exact.filter(w => norm(w.text || w.word || "")); let k = 0;
    for (const ph of P) {
      ph.wt = ph.words.map(w => { const x = ew[Math.min(k, ew.length - 1)]; k++; return { w, start: x.start, end: x.end }; });
      ph.start = ph.wt[0].start; ph.end = ph.wt[ph.wt.length - 1].end;
    }
    dur = Math.max(dur, ew.length ? ew[ew.length - 1].end : 0);
  } else if (buf) {
    const { start, end, gaps } = speechGaps(buf), M = gaps.length, syl = P.reduce((s, p) => s + p.syl, 0);
    if (M >= N - 1 && N > 1) {
      const rate = (end - start - gaps.reduce((s, g) => s + g.len, 0) * .6) / syl;
      // dp[i][j]: phrases 0..i placed, phrase i ends at gap j
      const INF = 1e9, dp = Array.from({ length: N }, () => new Float64Array(M + 1).fill(INF)), from = Array.from({ length: N }, () => new Int32Array(M + 1).fill(-1));
      const B = j => j === M ? end : gaps[j].a, A = j => j < 0 ? start : gaps[j].b;
      const cost = (i, j0, j1) => {   // phrase i between end of gap j0 and start of gap j1
        const d = B(j1) - A(j0), e = P[i].syl * rate; let c = ((d - e) / Math.max(e, .35)) ** 2;
        for (let k = j0 + 1; k < j1; k++) c += gaps[k].len > .3 ? 1.2 + gaps[k].len * 2 : .25;   // a long pause inside a phrase is unlikely
        if (j1 < M) c -= Math.min(gaps[j1].len, .7) * (P[i].end === 2 ? 1.6 : P[i].end === 1 ? .7 : .1);
        return c;
      };
      for (let j = 0; j < M; j++) dp[0][j] = cost(0, -1, j);
      if (N === 1) dp[0][M] = cost(0, -1, M);
      for (let i = 1; i < N; i++) for (let j = i; j <= (i === N - 1 ? M : M - 1); j++) {
        if (i === N - 1 && j !== M) continue;
        for (let k = i - 1; k < j; k++) { const v = dp[i - 1][k] + cost(i, k, j); if (v < dp[i][j]) { dp[i][j] = v; from[i][j] = k; } }
      }
      let j = M; for (let i = N - 1; i >= 0; i--) { const k = i ? from[i][j] : -1; spread(P[i], A(k), B(j)); j = k; }
    } else {
      let s = start; const syl2 = syl || 1; for (const ph of P) { const d = (end - start) * ph.syl / syl2; spread(ph, s, s + d); s += d; }
    }
  } else {            // no audio: estimate 3.7 words a second plus pauses
    let s = .5; for (const ph of P) { const d = ph.words.length / 3.7; spread(ph, s, s + d); s += d + (ph.end === 2 ? .45 : ph.end === 1 ? .2 : .05); }
    dur = s + .3;
  }
  const allW = []; P.forEach((ph, i) => ph.wt.forEach((w, k) => allW.push(Object.assign({ n: norm(w.w), p: i, k }, w))));
  const T = { phrases: P, words: allW, duration: dur,
    p: i => (P[Math.max(0, Math.min(N - 1, i))] || {}).start || 0,
    e: i => (P[Math.max(0, Math.min(N - 1, i))] || {}).end || 0,
    find(q, after = 0) { const qs = q.split(/\s+/).map(norm).filter(Boolean);
      for (let i = 0; i <= allW.length - qs.length; i++) if (allW[i].start >= after - .001 && qs.every((x, k) => allW[i + k].n === x)) return [allW[i], allW[i + qs.length - 1]];
      console.warn("timing: words not found:", q); return null; },
    w(q, after = 0) { const r = T.find(q, after); return r ? r[0].start : after; },
    we(q, after = 0) { const r = T.find(q, after); return r ? r[1].end : after; },
  };
  return T;
};
})();
