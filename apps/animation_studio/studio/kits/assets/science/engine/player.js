/* Cartoon Shorts engine: the player. Play, scrub, load a voiceover, export a video. Keep as is. Free from Anylancer.com. */
(async function () {
const S = window.SHORT; if (!S) { document.getElementById("msg").textContent = "No SHORT found: the story section is missing."; return; }
const fps = S.fps || 30, W = S.width || 1080, H = S.height || 1920;
const stage = document.getElementById("stage"), msg = document.getElementById("msg");
const RENDER = /[?&]render=1/.test(location.search), STILL = /[?&]t=/.test(location.search) && !window.renderFrameDriver;
if (RENDER) document.body.classList.add("render");
CS.start({ canvas: stage, width: W, height: H });
let T, DUR, N;
function prepare(buf) {
  CS.audio.voice = buf || null;
  T = CS.align(S.script || "", buf, S.words || window.SHORT_WORDS);
  DUR = S.duration || ((buf ? buf.duration : T.duration) + (S.tail ?? .8));
  N = Math.round(DUR * fps);
  CS.audio.reset(); if (S.sound) S.sound(CS.audio, T);
  window.CONFIG = { width: W, height: H, fps, duration: N / fps };
  window.TIMING = T;
}
if (CS.audio.loadSamples && !STILL) await CS.audio.loadSamples();
try { await document.fonts.load("700 100px CapFont"); } catch (e) {}
let vb = null;
try {
  if (STILL) vb = null; else if (window.VOICE_B64) vb = await CS.audio.decode(window.VOICE_B64);
  else if (S.voiceFile) { const r = await fetch(S.voiceFile); if (r.ok) vb = await CS.audio.decode(await r.arrayBuffer()); }
} catch (e) { console.warn("voice could not be loaded", e); }
prepare(vb);
await document.fonts.ready;
S.setup(T);
let last = -1;
function draw(t) { t = Math.max(0, Math.min(t, N / fps - 1e-4)); const f = Math.floor(t * fps + 1e-6); S.frame(t, T); if (CS.overlayDraw) CS.overlayDraw(t, T); CS.renderFrame(f); last = t; }
window.renderFrame = f => draw(Math.max(0, Math.min(f, N - 1)) / fps);
window.renderAt = t => draw(t);
window.renderAudio = () => CS.audio.renderWav(N / fps);

// ---------- UI ----------
function fit() { if (RENDER) { stage.style.width = W + "px"; stage.style.height = H + "px"; return; } const s = Math.min(innerWidth / W, (innerHeight - 64) / H) * .96; stage.style.width = W * s + "px"; stage.style.height = H * s + "px"; }
addEventListener("resize", fit); fit();
const scrub = document.getElementById("scrub"), playBtn = document.getElementById("play"), voiceBtn = document.getElementById("voice"), file = document.getElementById("file");
let playing = false, tNow = 0;
function show(t) { tNow = t; draw(t); scrub.value = Math.round(t / (N / fps) * 1000); msg.textContent = t.toFixed(2) + " / " + (N / fps).toFixed(2) + " s"; }
function loop() { if (!playing) return; const t = CS.audio.now(); if (t >= N / fps) { stopPlay(); show(0); return; } show(t); requestAnimationFrame(loop); }
function stopPlay() { playing = false; playBtn.textContent = "Play"; CS.audio.stop(); }
playBtn.onclick = () => { if (playing) return stopPlay(); playing = true; playBtn.textContent = "Pause"; CS.audio.play(tNow >= N / fps - .05 ? 0 : tNow, N / fps); loop(); };
scrub.oninput = () => { if (playing) stopPlay(); show(scrub.value / 1000 * N / fps); };
voiceBtn.textContent = vb ? "Voice loaded" : "Load voice";
voiceBtn.onclick = () => file.click();
async function useFile(f) { try { const b = await CS.audio.decode(await f.arrayBuffer()); stopPlay(); prepare(b); voiceBtn.textContent = "Voice loaded"; show(0); } catch (e) { msg.textContent = "Could not read that audio file."; } }
file.onchange = () => file.files[0] && useFile(file.files[0]);
addEventListener("dragover", e => e.preventDefault()); addEventListener("drop", e => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) useFile(f); });

// Export: plays once in real time and records picture + sound. Keep the tab visible while it records.
document.getElementById("export").onclick = async () => {
  const types = ["video/mp4;codecs=avc1,mp4a.40.2", "video/mp4", "video/webm;codecs=vp9,opus", "video/webm"];
  const type = types.find(x => window.MediaRecorder && MediaRecorder.isTypeSupported(x));
  if (!type) { msg.textContent = "This browser can't record. Open the file in Chrome."; return; }
  stopPlay(); show(0);
  const live = CS.audio.play(0, N / fps, true);
  const stream = new MediaStream([...stage.captureStream(fps).getVideoTracks(), ...live.stream.getAudioTracks()]);
  const rec = new MediaRecorder(stream, { mimeType: type, videoBitsPerSecond: 18e6 });
  const parts = []; rec.ondataavailable = e => e.data.size && parts.push(e.data); const done = new Promise(r => rec.onstop = r);
  rec.start();
  await new Promise(res => { (function step() { const t = CS.audio.now(); if (t >= N / fps) return res(); show(Math.max(0, t)); msg.textContent = "Recording " + Math.round(Math.max(0, t) / (N / fps) * 100) + "% (keep this tab open)"; setTimeout(step, 1000 / fps / 2); })(); });
  rec.stop(); await done; CS.audio.stop();
  const blob = new Blob(parts, { type }), a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = (S.slug || "cartoon-short") + (type.includes("mp4") ? ".mp4" : ".webm");
  document.body.appendChild(a); a.click(); a.remove(); msg.textContent = "Saved " + a.download;
};
const qt = /[?&]t=([\d.]+)/.exec(location.search); show(qt ? +qt[1] : 0); window.ready = true;
})();
