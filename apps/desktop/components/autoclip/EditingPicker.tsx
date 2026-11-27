"use client";
import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Music, Trash2, Upload } from "lucide-react";
import { autoclip, type Overview } from "@/lib/autoclip";
import { Label, Note, Switch, btn, field } from "./ui";

export interface EditOpts { edit: string; zoom: boolean; stickers: boolean; look: string; fx: boolean; sfx: boolean; progress: boolean; loudness: boolean; music: string; music_volume: number; coach: boolean }

/** The colour looks as small swatches: the gradient hints at what the filter does to the picture. */
export const LOOK_ART: Record<string, string> = {
  none: "linear-gradient(135deg,#6b7280,#9ca3af)", clean: "linear-gradient(135deg,#3b82f6,#f8fafc)", cinematic: "linear-gradient(135deg,#0e7490,#f59e0b)",
  vivid: "linear-gradient(135deg,#ec4899,#22d3ee,#facc15)", warm: "linear-gradient(135deg,#f97316,#fde68a)", cool: "linear-gradient(135deg,#1d4ed8,#a5f3fc)",
  mono: "linear-gradient(135deg,#000,#fff)", film: "linear-gradient(135deg,#78716c,#d6c9a8)",
};
export function LookPicker({ value, onChange, looks }: { value: string; onChange: (v: string) => void; looks: Record<string, string> }) {
  return (
    <div role="radiogroup" aria-label="Colour look" className="grid grid-cols-4 gap-2 sm:grid-cols-8">
      {Object.entries(looks).map(([k, label]) => (
        <button key={k} type="button" role="radio" aria-checked={value === k} title={label} onClick={() => onChange(k)}
          className={`overflow-hidden border-2 text-left transition ${value === k ? "border-primary" : "border-border hover:border-muted-foreground"}`}>
          <span className="block h-10 w-full" style={{ background: LOOK_ART[k] ?? LOOK_ART.none }} />
          <span className="block px-1.5 py-1 text-[11px] capitalize">{k === "none" ? "Original" : k}</span>
        </button>))}
    </div>
  );
}

/** Music: none, a mood picked automatically, a built-in loop or one of your own uploads. */
export function MusicPicker({ value, onChange, compact }: { value: string; onChange: (v: string) => void; compact?: boolean }) {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["autoclip", "music"], queryFn: () => autoclip.music(), retry: false });
  const [name, setName] = useState("");
  const [mood, setMood] = useState("upbeat");
  const [ack, setAck] = useState(false);
  const ref = useRef<HTMLInputElement>(null);
  const add = useMutation({
    mutationFn: () => { const f = new FormData(); const file = ref.current?.files?.[0]; if (!file) throw new Error("Choose an audio file."); f.append("file", file); f.append("name", name); f.append("mood", mood); f.append("ack", String(ack)); return autoclip.musicAdd(f); },
    onSuccess: (t) => { qc.invalidateQueries({ queryKey: ["autoclip", "music"] }); onChange(t.id); setName(""); setAck(false); if (ref.current) ref.current.value = ""; },
  });
  const del = useMutation({ mutationFn: (id: string) => autoclip.musicDelete(id), onSuccess: (_r, id) => { qc.invalidateQueries({ queryKey: ["autoclip", "music"] }); if (value === id) onChange("none"); } });
  const tracks = q.data?.tracks ?? [];
  const moods = q.data?.moods ?? {};
  const mine = tracks.filter((t) => !t.builtin);
  return (
    <div className="space-y-3">
      <select className={field} value={value} onChange={(e) => onChange(e.target.value)} aria-label="Music">
        <option value="none">No music</option>
        <option value="auto">Auto: pick a mood that fits each clip</option>
        <optgroup label="Mood (uses your tracks of that mood first)">{Object.entries(moods).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</optgroup>
        <optgroup label="Built-in loops (original, free to use)">{tracks.filter((t) => t.builtin).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</optgroup>
        {mine.length > 0 && <optgroup label="Your tracks">{mine.map((t) => <option key={t.id} value={t.id}>{t.name} · {moods[t.mood] ?? t.mood}</option>)}</optgroup>}
      </select>
      {value !== "none" && !compact && value.startsWith("builtin-") && <audio controls preload="none" className="h-9 w-full" src={autoclip.musicPreview(value)} />}
      {!compact && (
        <details className="border border-border p-3 text-sm">
          <summary className="flex cursor-pointer items-center gap-2"><Music className="h-4 w-4" />Add your own music{mine.length > 0 && ` (${mine.length} saved)`}</summary>
          <div className="mt-3 space-y-3">
            <p className="text-xs text-muted-foreground">Popular songs can&apos;t be added automatically: they belong to their owners, and no platform lets a program take them. Use tracks you have the right to use, such as YouTube Audio Library, Pixabay Music or FreePD (free), or a licensed trending sound you downloaded yourself. Videos using other people&apos;s music are often muted or blocked.</p>
            <div className="grid gap-3 sm:grid-cols-3">
              <input ref={ref} type="file" accept="audio/*" className={field + " py-1.5 sm:col-span-3"} aria-label="Audio file" />
              <input className={field} placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} maxLength={60} aria-label="Track name" />
              <select className={field} value={mood} onChange={(e) => setMood(e.target.value)} aria-label="Mood">{Object.entries(moods).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
              <button type="button" className={btn} disabled={!ack || add.isPending} onClick={() => add.mutate()}><Upload className="h-4 w-4" />{add.isPending ? "Adding…" : "Add track"}</button>
            </div>
            <label className="flex items-start gap-2 text-xs"><input type="checkbox" className="mt-0.5" checked={ack} onChange={(e) => setAck(e.target.checked)} />I have the right to use this track in my videos.</label>
            {add.isError && <Note tone="err">{(add.error as Error).message}</Note>}
            {mine.length > 0 && <ul className="space-y-1">{mine.map((t) => (
              <li key={t.id} className="flex items-center justify-between gap-2 text-xs"><span className="truncate">{t.name} · {t.duration ? `${Math.round(t.duration)}s` : ""}</span>
                <span className="flex items-center gap-2"><audio controls preload="none" className="h-8 w-40" src={autoclip.musicPreview(t.id)} /><button type="button" aria-label={`Delete ${t.name}`} className="p-1 hover:text-red-400" onClick={() => del.mutate(t.id)}><Trash2 className="h-4 w-4" /></button></span>
              </li>))}</ul>}
          </div>
        </details>
      )}
    </div>
  );
}

/** The Editing card inside Make clips. */
export function EditingPicker({ o, set, ov }: { o: EditOpts; set: <K extends keyof EditOpts>(k: K, v: EditOpts[K]) => void; ov: Overview }) {
  const styles = ov.capabilities.edit_styles ?? { classic: "Classic", punchy: "Punchy", clean: "Clean" };
  const off = o.edit === "off";
  return (
    <div className="space-y-3 border border-border p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Editing</span>
        <span className="text-xs text-muted-foreground">Callouts use the Poppins font (OFL)</span>
      </div>
      <div role="radiogroup" aria-label="Edit style" className="flex flex-wrap gap-2">
        {[["off", "No effects"], ...Object.entries(styles)].map(([k, v]) => (
          <button key={k} type="button" role="radio" aria-checked={o.edit === k} onClick={() => set("edit", k)} className={`border px-3 py-2 text-left text-sm transition ${o.edit === k ? "border-signal/85 bg-signal/12" : "border-border text-muted-foreground hover:text-foreground"}`}>{v}</button>
        ))}
      </div>
      {!off && (
        <>
          <Label text="Colour look" hint={ov.capabilities.looks?.[o.look]}><LookPicker value={o.look} onChange={(v) => set("look", v)} looks={ov.capabilities.looks ?? { clean: "Clean", cinematic: "Cinematic", vivid: "Vivid", warm: "Warm", cool: "Cool", mono: "Mono", film: "Film", none: "None" }} /></Label>
          <div className="grid gap-3 sm:grid-cols-2">
            <Switch on={o.zoom} onChange={(v) => set("zoom", v)} label="Zoom effects" hint="Smooth punch-ins on the beats of speech" />
            <Switch on={o.stickers} onChange={(v) => set("stickers", v)} label="Callouts" hint="Designed badges on keywords: “$$$” on money, “WAIT FOR IT”, “INSANE”…" disabled={o.edit === "clean"} />
            <Switch on={o.fx} onChange={(v) => set("fx", v)} label="Hype effects" hint="A flash, shake and glitch on the loudest moments" disabled={o.edit === "clean"} />
            <Switch on={o.sfx} onChange={(v) => set("sfx", v)} label="Sound effects" hint="A pop with each callout, a boom on each hype peak" disabled={o.edit === "clean"} />
            <Switch on={o.progress} onChange={(v) => set("progress", v)} label="Progress bar" hint="A thin bar along the bottom that keeps people watching" />
            <Switch on={o.loudness} onChange={(v) => set("loudness", v)} label="Clean, even voice" hint="Evens out loudness for phones" />
          </div>
        </>
      )}
      <Label text="Music" hint="Plays quietly under the voice and dips while someone talks.">
        <MusicPicker value={o.music} onChange={(v) => set("music", v)} />
      </Label>
      {o.music !== "none" && (
        <Label text={`Music volume: ${Math.round(o.music_volume * 100)}%`}>
          <input type="range" min={4} max={50} value={Math.round(o.music_volume * 100)} onChange={(e) => set("music_volume", +e.target.value / 100)} className="w-full" aria-label="Music volume" />
        </Label>
      )}
      <Switch on={o.coach} onChange={(v) => set("coach", v)} label="Let the coach choose" hint="When the coach is on Auto (YouTube tab), each clip's caption, edit style, effects and music come from what has worked on your channel. Off = exactly what you set here." />
    </div>
  );
}
