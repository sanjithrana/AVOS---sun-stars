"use client";
/* eslint-disable @next/next/no-img-element -- pictures come from the Animation Studio service */
// The whole film (or part) on one timeline, lane by lane, from the same motion blueprints the models are told:
// shots, camera, each character's timed actions, effects, dialogue, sound effects, ambience and music. With the
// rendered video it follows playback; before that, a GSAP playhead previews the timing.
import { useEffect, useMemo, useRef, useState } from "react";
import gsap from "gsap";
import { Pause, Play } from "lucide-react";
import { seriesApi } from "./api";
import { moveLabel, starts } from "./Storyboard";
import type { Part, SeriesSnapshot } from "./types";

interface Item { at: number; len: number; label: string; tone?: "a" | "b" | "c" | "d"; shot?: string; dot?: boolean }
const TONE = { a: "bg-amber-500/80 text-black", b: "bg-sky-500/70 text-white", c: "bg-emerald-500/70 text-white", d: "bg-fuchsia-500/60 text-white" };

/** "water dripping at 0.5s; splash at 1.9s" → [{t, text}] (no time → the whole shot). */
export function sfxMarks(text: string): { t: number | null; text: string }[] {
  return (text || "").split(";").map((x) => x.trim()).filter(Boolean).map((x) => {
    const m = x.match(/^(.*?)\s+at\s+(\d+(?:\.\d+)?)\s*s$/i);
    return m ? { t: Number(m[2]), text: m[1] } : { t: null, text: x };
  });
}

export function Timeline({ sid, snap, part, video, onOpen }: { sid: string; snap: SeriesSnapshot; part: Part; video?: string | null; onOpen?: (shot: string) => void }) {
  const shots = useMemo(() => part.shots ?? [], [part.shots]);
  const t0 = useMemo(() => starts(shots), [shots]);
  const total = Math.max(0.1, shots.reduce((a, s) => a + s.seconds, 0));
  const names = Object.fromEntries(snap.series.characters.map((c) => [c.id, c.name]));
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const vid = useRef<HTMLVideoElement>(null);
  const tween = useRef<gsap.core.Tween | null>(null);
  const clock = useRef({ t: 0 });

  useEffect(() => () => { tween.current?.kill(); }, []);
  const play = () => {
    if (video && vid.current) { if (vid.current.paused) void vid.current.play(); else vid.current.pause(); return; }
    if (playing) { tween.current?.pause(); setPlaying(false); return; }
    clock.current.t = t >= total - 0.05 ? 0 : t;
    tween.current?.kill();
    tween.current = gsap.to(clock.current, { t: total, duration: total - clock.current.t, ease: "none", onUpdate: () => setT(clock.current.t), onComplete: () => setPlaying(false) });
    setPlaying(true);
  };
  const seek = (x: number) => {
    const nt = Math.max(0, Math.min(total, x * total));
    setT(nt);
    if (vid.current) vid.current.currentTime = nt;
    tween.current?.kill();
    setPlaying(false);
  };

  const lanes = useMemo(() => {
    const out: { name: string; items: Item[] }[] = [];
    out.push({ name: "Camera", items: shots.map((s, i) => ({ at: t0[i], len: s.seconds, label: `${s.framing}${s.angle && s.angle !== "eye level" ? ", " + s.angle : ""} · ${moveLabel(s.blueprint?.camera.move ?? s.camera)}`, tone: "b", shot: s.id })) });
    const cast = Array.from(new Set(shots.flatMap((s) => s.subjects ?? [])));
    for (const cid of cast) {
      const items: Item[] = [];
      shots.forEach((s, i) => {
        const keys = s.blueprint?.tracks.find((tr) => tr.target === cid)?.keys ?? [];
        keys.forEach((k, j) => {
          const end = j + 1 < keys.length ? keys[j + 1].t : s.seconds;
          items.push({ at: t0[i] + k.t, len: Math.max(0.15, end - k.t), label: k.action, tone: "c", shot: s.id });
        });
        if (!keys.length && (s.subjects ?? []).includes(cid)) items.push({ at: t0[i], len: s.seconds, label: s.speaker === cid ? "speaks" : "in shot", tone: "c", shot: s.id });
      });
      out.push({ name: names[cid] ?? cid, items });
    }
    const fx: Item[] = [];
    shots.forEach((s, i) => (s.blueprint?.environment ?? []).forEach((e) => fx.push({ at: t0[i] + e.t, len: 0.4, label: e.text, tone: "d", dot: true, shot: s.id })));
    if (fx.length) out.push({ name: "Effects", items: fx });
    out.push({ name: "Dialogue", items: shots.flatMap((s, i) => (s.kind === "dialogue" ? [{ at: t0[i], len: s.seconds, label: `${names[s.speaker ?? ""] ?? ""}: ${s.text ?? ""}`, tone: "a" as const, shot: s.id }] : [])) });
    out.push({ name: "Sound FX", items: shots.flatMap((s, i) => sfxMarks(s.sfx).map((m) => (m.t === null ? { at: t0[i], len: s.seconds, label: m.text, tone: "d" as const, shot: s.id }
      : { at: t0[i] + m.t, len: 0.3, label: m.text, tone: "d" as const, dot: true, shot: s.id }))) });
    const amb: Item[] = [];
    shots.forEach((s, i) => {
      const last = amb[amb.length - 1];
      const text = part.sound?.ambience?.[s.scene] ?? "";
      if (last && last.shot === s.scene) last.len += s.seconds;
      else if (text) amb.push({ at: t0[i], len: s.seconds, label: text, tone: "b", shot: s.scene });
    });
    if (amb.length) out.push({ name: "Ambience", items: amb.map((a) => ({ ...a, shot: undefined })) });
    if (part.sound?.music) out.push({ name: "Music", items: [{ at: 0, len: total, label: part.sound.music, tone: "a" }] });
    return out;
  }, [shots, t0, names, part.sound, total]);

  const pct = (x: number) => `${(100 * x) / total}%`;
  const ticks = Array.from({ length: Math.floor(total) + 1 }, (_, i) => i);
  return (
    <div className="space-y-2" data-testid="timeline">
      {video && <video ref={vid} controls className="aspect-video w-full rounded-xl bg-black" src={video} onTimeUpdate={(e) => setT(e.currentTarget.currentTime)}
        onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} data-testid="part-video" />}
      <div className="overflow-x-auto rounded-xl border border-border bg-card/30 p-2">
        <div className="min-w-[720px]">
          <div className="flex items-center gap-2 pb-1">
            <button className="flex h-7 w-24 shrink-0 items-center justify-center gap-1 rounded-lg border border-border text-xs hover:bg-accent" onClick={play} data-testid="timeline-play">
              {playing ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}{t.toFixed(1)}s
            </button>
            <div className="relative h-5 flex-1 cursor-pointer text-[10px] text-muted-foreground" onClick={(e) => { const r = e.currentTarget.getBoundingClientRect(); seek((e.clientX - r.left) / r.width); }}>
              {ticks.map((i) => <span key={i} className="absolute top-0 -translate-x-1/2" style={{ left: pct(i) }}>{i}s</span>)}
            </div>
          </div>
          <div className="relative">
            <Lane name="Shots">
              {shots.map((s, i) => (
                <button key={s.id} className="absolute top-0 h-full overflow-hidden rounded border border-black/40 bg-muted" style={{ left: pct(t0[i]), width: pct(s.seconds) }}
                  onClick={() => onOpen?.(s.id)} title={`${i + 1}. ${s.picture}`} data-testid={`tl-shot-${s.id}`}>
                  {s.files.key && <img src={seriesApi.file(sid, s.files.key, `${part.boardAt}-${s.takes?.picture}`)} alt="" className="h-full w-full object-cover" />}
                  <span className="absolute left-0.5 top-0.5 rounded bg-black/60 px-1 text-[9px] text-white">{String(i + 1).padStart(2, "0")}</span>
                </button>
              ))}
            </Lane>
            {lanes.map((l) => (
              <Lane key={l.name} name={l.name} small>
                {l.items.map((it, k) => (
                  <button key={k} className={`absolute top-0.5 h-[calc(100%-4px)] overflow-hidden whitespace-nowrap rounded px-1 text-left text-[10px] leading-5 ${TONE[it.tone ?? "a"]} ${it.dot ? "min-w-[6px]" : ""}`}
                    style={{ left: pct(it.at), width: pct(it.len) }} title={`${it.at.toFixed(1)}s · ${it.label}`} onClick={() => it.shot && onOpen?.(it.shot)}>
                    {it.dot ? "●" : it.label}
                  </button>
                ))}
              </Lane>
            ))}
            <div className="pointer-events-none absolute bottom-0 top-0 w-0.5 bg-red-500" style={{ left: `calc(6.5rem + (100% - 6.5rem) * ${t / total})` }} data-testid="playhead" />
          </div>
        </div>
      </div>
    </div>
  );
}

function Lane({ name, small, children }: { name: string; small?: boolean; children: React.ReactNode }) {
  return (
    <div className="flex items-stretch gap-2 border-t border-border/60 py-0.5">
      <span className="w-24 shrink-0 truncate py-1 text-[11px] font-medium text-muted-foreground" title={name}>{name}</span>
      <div className={`relative flex-1 ${small ? "h-6" : "h-14"}`}>{children}</div>
    </div>
  );
}
