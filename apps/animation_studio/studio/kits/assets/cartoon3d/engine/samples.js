/* Cartoon Shorts engine: recorded sounds (laugh, laugh2, gasp, murmur, cheer, ooh, moo, moo2), packed into the player by pack.py.
   Use them like any effect: A.sfx("laugh", T.w("laughed"), .9, {dur: 2.5}). Opt: rate (pitch/speed), offset, dur, fade.
   Made with ElevenLabs Sound Effects for this kit; free to use in your videos. Free from Anylancer.com. */
(function () {
const CS = window.CS = window.CS || {};
const A = CS.audio; A.buffers = A.buffers || {};
A.loadSamples = async function () {
  const B = window.CS_SAMPLES || {};
  for (const k in B) {
    if (A.buffers[k]) continue;
    try { A.buffers[k] = await A.decode(B[k]); } catch (e) { console.warn("sample", k, e); continue; }
    A.SFX[k] = (ctx, out, t, v, p) => {
      const s = ctx.createBufferSource(); s.buffer = A.buffers[k]; if (p.rate) s.playbackRate.value = p.rate;
      const g = ctx.createGain(), dur = p.dur || A.buffers[k].duration, f = p.fade ?? .25;
      g.gain.setValueAtTime(v * 2.2, t); g.gain.setValueAtTime(v * 2.2, t + Math.max(0, dur - f)); g.gain.linearRampToValueAtTime(0.0001, t + dur);
      s.connect(g); g.connect(out); s.start(t, p.offset || 0); s.stop(t + dur + .05);
    };
  }
};
})();
