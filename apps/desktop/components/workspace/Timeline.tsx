"use client";

import { useRef } from "react";

export interface Clip { start: number; end: number; label: string; tone?: "primary" | "amber" | "green" | "muted"; title?: string }
export interface Lane { id: string; label: string; clips: Clip[] }

const TONE: Record<string, string> = {
  primary: "border-[rgba(185,172,255,0.6)] bg-[rgba(124,92,255,0.28)]", amber: "border-amber-400/60 bg-amber-400/20", green: "border-emerald-400/60 bg-emerald-400/20", muted: "border-border bg-muted",
};

/** Lanes on a time axis with a playhead you can click or drag (the same timeline for every studio: video, poses, cards, narration, music). */
export function Timeline({ duration, lanes, time, onSeek }: { duration: number; lanes: Lane[]; time: number; onSeek: (t: number) => void }) {
  const box = useRef<HTMLDivElement>(null);
  const total = Math.max(1, duration);
  const seek = (clientX: number) => {
    const r = box.current?.getBoundingClientRect();
    if (r && r.width > 0) onSeek(Math.min(total, Math.max(0, ((clientX - r.left) / r.width) * total)));
  };
  const step = total > 300 ? 60 : total > 120 ? 30 : total > 60 ? 15 : 10;   // a ten-minute video does not want sixty tick marks
  const ticks = Array.from({ length: Math.floor(total / step) + 1 }, (_, i) => i * step);
  const at = Math.min(100, Math.max(0, (time / total) * 100));
  return (
    <div className="rounded-2xl border border-border p-3" data-testid="timeline">
      <div className="flex gap-3">
        <div className="w-[4.5rem] shrink-0">
          <div className="h-6" />
          {lanes.map((l) => <div key={l.id} className="flex h-9 items-center text-[11px] text-muted-foreground">{l.label}</div>)}
        </div>
        <div ref={box} className="relative min-w-0 flex-1 select-none">
          <div className="relative h-6 cursor-pointer border-b border-border" role="slider" aria-label="Playhead" aria-valuemin={0} aria-valuemax={Math.round(total)} aria-valuenow={Math.round(time)} tabIndex={0}
            onPointerDown={(e) => { (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId); seek(e.clientX); }}
            onPointerMove={(e) => { if (e.buttons) seek(e.clientX); }}
            onKeyDown={(e) => { if (e.key === "ArrowLeft") onSeek(Math.max(0, time - 1)); if (e.key === "ArrowRight") onSeek(Math.min(total, time + 1)); }}>
            {ticks.map((t) => <span key={t} className="absolute top-0 text-[10px] text-muted-foreground" style={{ left: `${(t / total) * 100}%` }}>{t}s</span>)}
          </div>
          {lanes.map((l) => (
            <div key={l.id} className="relative h-9 border-b border-border/60">
              {l.clips.map((c, i) => (
                <button key={i} type="button" title={c.title ?? c.label} onClick={() => onSeek(c.start)}
                  className={`absolute top-1 h-7 overflow-hidden whitespace-nowrap rounded-md border px-1.5 text-left text-[10px] leading-7 ${TONE[c.tone ?? "primary"]}`}
                  style={{ left: `${(c.start / total) * 100}%`, width: `${Math.max(0.8, ((c.end - c.start) / total) * 100)}%` }}>{c.label}</button>
              ))}
            </div>
          ))}
          <div className="pointer-events-none absolute bottom-0 top-0 w-px bg-red-400" style={{ left: `${at}%` }} aria-hidden><span className="absolute -left-1 top-0 h-2 w-2 rounded-full bg-red-400" /></div>
        </div>
      </div>
      <p className="mt-2 text-[11px] text-muted-foreground">Click or drag the ruler to jump the preview; arrow keys move one second. {Math.round(time * 10) / 10}s of {Math.round(total)}s</p>
    </div>
  );
}
