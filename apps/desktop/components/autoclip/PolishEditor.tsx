"use client";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Wand2 } from "lucide-react";
import { autoclip, type Clip, type Job } from "@/lib/autoclip";
import { LookPicker, MusicPicker } from "./EditingPicker";
import { Note, Switch, btn, btnPrimary } from "./ui";

/** Re-render one clip with different effects: no new download, no new transcript. */
export function PolishEditor({ jobId, clip, onDone, styles, looks }: { jobId: string; clip: Clip; onDone: (j: Job) => void; styles: Record<string, string>; looks: Record<string, string> }) {
  const e = clip.edit;
  const [open, setOpen] = useState(false);
  const [v, setV] = useState({ edit: e?.style ?? "off", zoom: !!e?.zooms?.length || !e, stickers: !!e?.stickers?.length || !e, look: e?.look ?? "clean", fx: !!e?.peaks?.length || !e, sfx: Boolean(e?.opts?.sfx ?? true), progress: Boolean(e?.opts?.progress ?? false), music: String(e?.opts?.music ?? "none"), music_volume: Number(e?.opts?.music_volume ?? 0.14) });
  const go = useMutation({ mutationFn: (seed?: number) => autoclip.polish(jobId, clip.n, { ...v, ...(seed ? { seed } : {}) }), onSuccess: onDone });
  const set = <K extends keyof typeof v>(k: K, x: (typeof v)[K]) => setV((s) => ({ ...s, [k]: x }));
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <button type="button" className="inline-flex items-center gap-1 underline" onClick={() => setOpen(!open)}><Wand2 className="h-3 w-3" />{open ? "Hide editing" : "Edit effects"}</button>
        {e ? <span>{styles[e.style]?.split(":")[0] ?? e.style} · {e.zooms.length} zooms · {e.stickers.length} callouts{e.peaks?.length ? ` · ${e.peaks.length} hype hits` : ""}{e.music ? ` · ${e.music.name}` : ""}</span> : <span>No effects on this clip</span>}
      </div>
      {open && (
        <div className="space-y-3 border border-border p-3">
          <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Edit style">
            {[["off", "No effects"], ...Object.entries(styles)].map(([k, l]) => <button key={k} type="button" role="radio" aria-checked={v.edit === k} onClick={() => set("edit", k)} className={`border px-3 py-1.5 text-sm ${v.edit === k ? "border-signal/85 bg-signal/12" : "border-border text-muted-foreground"}`}>{l.split(":")[0]}</button>)}
          </div>
          <LookPicker value={v.look} onChange={(x) => set("look", x)} looks={looks} />
          <div className="grid gap-3 sm:grid-cols-2"><Switch on={v.zoom} onChange={(x) => set("zoom", x)} label="Zooms" /><Switch on={v.stickers} onChange={(x) => set("stickers", x)} label="Callouts" /><Switch on={v.fx} onChange={(x) => set("fx", x)} label="Hype effects" /><Switch on={v.sfx} onChange={(x) => set("sfx", x)} label="Sound effects" /><Switch on={v.progress} onChange={(x) => set("progress", x)} label="Progress bar" /></div>
          <MusicPicker value={v.music} onChange={(x) => set("music", x)} compact />
          <div className="flex flex-wrap gap-2">
            <button type="button" className={btnPrimary} disabled={go.isPending} onClick={() => go.mutate(undefined)}>{go.isPending ? "Rendering…" : "Apply and re-render"}</button>
            <button type="button" className={btn} disabled={go.isPending} onClick={() => go.mutate(Math.floor(Math.random() * 9999) + 1)}>Shuffle music and zooms</button>
          </div>
          {go.isError && <Note tone="err">{(go.error as Error).message}</Note>}
        </div>
      )}
    </div>
  );
}
