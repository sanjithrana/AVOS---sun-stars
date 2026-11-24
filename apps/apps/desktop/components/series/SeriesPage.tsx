"use client";
/* eslint-disable @next/next/no-img-element -- pictures come from the Animation Studio service */
// One series: what's running, which models each step uses, the characters to approve, places, and the episodes.
import Link from "next/link";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle, BookUser, CheckCircle2, ChevronDown, Clapperboard, Cpu, Film, ImagePlus, Loader2, Mic, Pencil, Plus, RefreshCw, Square, Upload, Users, Wand2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { modelLabel, seriesApi } from "./api";
import { DnaPanel } from "./DnaPanel";
import { EpisodePanel } from "./EpisodePanel";
import { LibraryAdd } from "./Library";
import { ModelChoices } from "./ModelChoices";
import { field, type Act } from "./shared";
import type { Character, Readiness, SeriesSnapshot } from "./types";

export const WORKING = new Set(["drafting", "redo", "writing", "queued", "rendering", "outlining", "joining"]);

export function useSeries(id: string) {
  return useQuery({
    queryKey: ["series", id],
    queryFn: () => seriesApi.get(id),
    retry: false,
    refetchInterval: (q) => {
      const d = q.state.data;
      if (!d) return 3000;
      const live = d.busy || d.series.characters.some((c) => WORKING.has(c.status)) ||
        d.episodes.some((e) => WORKING.has(e.status) || e.parts.some((p) => WORKING.has(p.status)));
      return live ? 1500 : 6000;
    },
  });
}

/** Run an API call for one series / film: a returned snapshot replaces the page's data, errors show above the page. */
export function useAct(id: string) {
  const qc = useQueryClient();
  const [err, setErr] = useState<string | null>(null);
  const [pending, setPending] = useState<string | null>(null);
  const act: Act = async (label, fn) => {
    setPending(label);
    setErr(null);
    try {
      const r = await fn();
      if (r && typeof r === "object" && "series" in (r as object)) qc.setQueryData(["series", id], r);
      else await qc.invalidateQueries({ queryKey: ["series", id] });
      await qc.invalidateQueries({ queryKey: ["series", "library"] });
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setPending(null);
    }
  };
  return { act, err, pending };
}

export function SeriesPage({ id }: { id: string }) {
  const q = useSeries(id);
  const { act, err, pending } = useAct(id);

  if (q.isError) return <main className="p-8"><Link href="/animations/series" className="text-sm hover:underline">← Series</Link><p className="mt-4 text-muted-foreground">{(q.error as Error).message}</p></main>;
  if (!q.data) return <main className="space-y-4 p-8"><div className="h-10 w-80 animate-pulse rounded-xl bg-muted/40" /><div className="h-64 animate-pulse rounded-2xl bg-muted/40" /></main>;
  const { series: s, episodes } = q.data;
  const approved = s.characters.filter((c) => c.status === "approved").length;
  const openEp = episodes.find((e) => e.status !== "done");

  return (
    <main className="mx-auto max-w-7xl space-y-8 p-4 md:p-8" data-testid="series-page">
      <div>
        <Link href="/animations/series" className="text-xs text-muted-foreground hover:underline">← Series</Link>
        <div className="mt-1 flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-bold text-foreground md:text-3xl">{s.title}</h1>
          <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">{q.data.language.name}</span>
          <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">{s.format.aspect}</span>
          <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">parts: {s.partPlan.join(" → ")} min</span>
        </div>
        {(s.logline || s.premise) && <p className="mt-2 max-w-4xl text-muted-foreground">{s.logline || s.premise}</p>}
      </div>

      <WorkBar snap={q.data} onStop={() => act("stop", () => seriesApi.cancel(id))} />
      {err && <p className="rounded-xl border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-700 dark:text-red-300" data-testid="series-action-error">{err}</p>}
      <ModelChoices sid={id} act={act} />
      <DnaPanel sid={id} dna={s.dna} act={act} />

      <section>
        <h2 className="mb-1 flex items-center gap-2 text-lg font-semibold text-foreground"><Users className="h-5 w-5 text-amber-500" />Characters
          <span className="text-sm font-normal text-muted-foreground">{approved} of {s.characters.length} approved</span></h2>
        <p className="mb-4 text-sm text-muted-foreground">Check each character&apos;s sheet and voice. Approve it, or redo the look or the voice with a note. Only approved characters appear in episodes.</p>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2" data-testid="characters">
          {s.characters.map((c) => <CharacterCard key={c.id} sid={id} c={c} act={act} pending={pending} />)}
          <AddCharacter sid={id} act={act} />
          <LibraryAdd sid={id} act={act} have={s.characters.map((c) => c.fromLibrary ?? "").filter(Boolean)} />
        </div>
      </section>

      {s.locations.length > 0 && (
        <section>
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-foreground"><Clapperboard className="h-5 w-5 text-amber-500" />Places</h2>
          <div className="flex gap-3 overflow-x-auto pb-2">
            {s.locations.map((l) => (
              <div key={l.id} className="w-56 shrink-0 overflow-hidden rounded-xl border border-border bg-card/40" data-testid={`location-${l.id}`}>
                <div className="aspect-video bg-muted/40">{l.plate ? <img src={seriesApi.file(id, l.plate)} alt={l.name} className="h-full w-full object-cover" /> :
                  <div className="flex h-full items-center justify-center text-xs text-muted-foreground">{l.status === "error" ? "couldn't paint" : "painted on first use"}</div>}</div>
                <div className="flex items-center justify-between gap-2 p-2">
                  <span className="truncate text-sm text-foreground" title={l.description}>{l.name}</span>
                  <button className="text-xs text-muted-foreground hover:text-foreground" title="Paint again" onClick={() => act("place", () => seriesApi.redoLocation(id, l.id, ""))}><RefreshCw className="h-3.5 w-3.5" /></button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      <section>
        <h2 className="mb-4 flex flex-wrap items-center gap-2 text-lg font-semibold text-foreground"><Film className="h-5 w-5 text-amber-500" />Episodes
          <label className="ml-auto flex items-center gap-2 text-xs font-normal text-muted-foreground" title="Each part's frames are drawn first; it is animated only after you approve them">
            <input type="checkbox" checked={s.settings.storyboardGate !== false} onChange={(e) => act("gate", () => seriesApi.edit(id, { settings: { storyboardGate: e.target.checked } }))} data-testid="storyboard-gate" />
            Approve a storyboard before animating
          </label></h2>
        <div className="space-y-6">
          {episodes.slice().reverse().map((e) => <EpisodePanel key={e.id} sid={id} snap={q.data} ep={e} act={act} pending={pending} />)}
          {!openEp && <NewEpisode sid={id} act={act} canStart={approved > 0} number={episodes.length + 1} />}
        </div>
      </section>

      {s.story.episodes.length > 0 && (
        <section className="rounded-2xl border border-border bg-card/30 p-5">
          <h3 className="mb-2 font-semibold text-foreground">The story so far</h3>
          <ul className="space-y-1 text-sm text-muted-foreground">{s.story.episodes.map((e) => <li key={e.episode}><b className="text-foreground">Episode {e.episode}:</b> {e.summary}</li>)}</ul>
          {s.story.facts.length > 0 && <p className="mt-2 text-xs text-muted-foreground">Remembered: {s.story.facts.join(" · ")}</p>}
        </section>
      )}
    </main>
  );
}

export function WorkBar({ snap, onStop }: { snap: SeriesSnapshot; onStop: () => void }) {
  const w = snap.series.work || { state: "idle" };
  if (!snap.busy && w.state !== "error" && w.state !== "stopped") return null;
  const pct = w.total ? Math.round((100 * (w.done || 0)) / w.total) : null;
  return (
    <div className={`rounded-2xl border p-4 ${w.state === "error" ? "border-red-500/40 bg-red-500/5" : "border-amber-500/40 bg-amber-500/5"}`} data-testid="work-bar">
      <div className="flex flex-wrap items-center gap-3">
        {snap.busy ? <Loader2 className="h-4 w-4 animate-spin text-amber-500" /> : <AlertTriangle className="h-4 w-4 text-red-500" />}
        <b className="text-sm text-foreground">{snap.busy ? w.label : w.state === "error" ? "Something failed" : "Stopped"}</b>
        {snap.busy && w.step && <span className="text-sm text-muted-foreground">{w.step}{w.total ? ` · ${w.done}/${w.total}` : ""}</span>}
        <span className="grow" />
        {snap.busy && <Button size="sm" variant="outline" onClick={onStop} data-testid="work-stop"><Square />Stop</Button>}
      </div>
      {pct !== null && snap.busy && <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted"><div className="h-full bg-amber-500 transition-all" style={{ width: `${pct}%` }} /></div>}
      {w.error && !snap.busy && <p className="mt-2 text-sm text-red-700 dark:text-red-300">{w.error}</p>}
      {(w.queue?.length ?? 0) > 0 && <p className="mt-2 text-xs text-muted-foreground">Next: {w.queue!.join(" · ")}</p>}
    </div>
  );
}

const STEPS: [keyof Readiness, string, string][] = [
  ["pictures", "Character sheets, places and keyframes", "Qwen-Image-Edit on a GPU worker keeps faces and outfits the same"],
  ["voiceDesign", "Designing each voice", "Indic Parler-TTS (or an Edge voice)"],
  ["lines", "Speaking the lines", "Chatterbox / IndicF5 clone the approved voice"],
  ["lipsync", "Talking shots (lip-sync)", "InfiniteTalk"],
  ["motion", "Action shots", "Wan 2.2 / LTX-2.3"],
  ["sfx", "Sound effects", "HunyuanVideo-Foley"],
  ["music", "Music", "ACE-Step 1.5, or your theme"],
];

export function ReadyPanel({ ready }: { ready: Readiness }) {
  const missing = STEPS.filter(([k]) => !ready[k]);
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-2xl border border-border bg-card/30" data-testid="ready-panel">
      <button className="flex w-full items-center gap-2 p-4 text-left" onClick={() => setOpen(!open)}>
        <Cpu className="h-4 w-4 text-amber-500" />
        <b className="text-sm text-foreground">Models</b>
        <span className="text-sm text-muted-foreground">{missing.length === 0 ? "every step runs on your GPUs" : `${STEPS.length - missing.length} of ${STEPS.length} steps ready on your GPUs`}</span>
        <span className="grow" /><ChevronDown className={`h-4 w-4 transition ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="grid grid-cols-1 gap-2 border-t border-border p-4 text-sm md:grid-cols-2">
          {STEPS.map(([k, name, how]) => {
            const m = ready[k] as string | null;
            const fb = k === "pictures" ? ready.picturesFallback : k === "voiceDesign" || k === "lines" ? (ready.edge ? "Edge voice (online)" : null) : k === "lipsync" || k === "motion" ? "still picture + camera move" : null;
            return (
              <div key={k} className="flex items-start gap-2" data-testid={`ready-${k}`}>
                {m ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" /> : <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />}
                <div><b className="text-foreground">{name}:</b> <span className="text-muted-foreground">{m ? modelLabel(m) : fb ? `fallback: ${modelLabel(fb)}` : "skipped"}</span>
                  {!m && <div className="text-xs text-muted-foreground">Set up {how} (Models page → Download, GPU page → add a worker).</div>}</div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

const STATUS_CHIP: Record<string, [string, string]> = {
  drafting: ["Drafting…", "bg-blue-500/15 text-blue-700 dark:text-blue-300"], redo: ["Redoing…", "bg-blue-500/15 text-blue-700 dark:text-blue-300"],
  review: ["Waiting for you", "bg-amber-500/15 text-amber-700 dark:text-amber-300"], approved: ["Approved", "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300"],
  error: ["Failed", "bg-red-500/15 text-red-700 dark:text-red-300"],
};
export const Chip = ({ s }: { s: string }) => {
  const [t, c] = STATUS_CHIP[s] ?? [s, "bg-muted text-muted-foreground"];
  return <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${c}`} data-testid="status-chip">{t}</span>;
};

export function CharacterCard({ sid, c, act, pending }: { sid: string; c: Character; act: Act; pending: string | null }) {
  const [note, setNote] = useState("");
  const [edit, setEdit] = useState(false);
  const [form, setForm] = useState({ look: c.look, outfit: c.outfit, personality: c.personality, voice: c.voice?.description ?? "", age: c.age });
  const [zoom, setZoom] = useState(false);
  const working = c.status === "drafting" || c.status === "redo";
  const upload = (kind: "picture" | "voice") => (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    const fd = new FormData();
    fd.append(kind, f);
    void act(`upload-${c.id}`, () => seriesApi.uploadCharacter(sid, c.id, fd));
  };
  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-border bg-card/40 p-4" data-testid={`character-${c.id}`}>
      <div className="flex items-center gap-2">
        <b className="text-lg text-foreground">{c.name}</b>
        <span className="text-xs text-muted-foreground">{[c.role, c.age, c.gender !== "other" ? c.gender : ""].filter(Boolean).join(" · ")}</span>
        <span className="grow" />
        {c.version > 0 && <span className="text-[11px] text-muted-foreground">v{c.version}</span>}
        <Chip s={c.status} />
      </div>
      <div className="relative aspect-[16/9] overflow-hidden rounded-xl bg-muted/40">
        {c.sheet ? <img src={seriesApi.file(sid, c.sheet)} alt={`${c.name} character sheet`} className="h-full w-full cursor-zoom-in object-contain" onClick={() => setZoom(true)} data-testid="sheet" /> : null}
        {working && <div className="absolute inset-0 flex items-center justify-center bg-background/60"><Loader2 className="h-6 w-6 animate-spin text-amber-500" /></div>}
      </div>
      {zoom && c.sheet && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-6" onClick={() => setZoom(false)}><img src={seriesApi.file(sid, c.sheet)} alt="" className="max-h-full max-w-full rounded-xl" /></div>}
      {c.voice?.sample && (
        <div className="flex items-center gap-2">
          <Mic className="h-4 w-4 shrink-0 text-amber-500" />
          <audio controls src={seriesApi.file(sid, c.voice.sample)} className="h-8 w-full" data-testid="voice" />
        </div>
      )}
      {c.voice?.sampleText && <p className="text-xs italic text-muted-foreground">“{c.voice.sampleText}”</p>}
      <div className="flex flex-wrap gap-1 text-[11px]">
        {c.sheetInfo && <span className={`rounded-full px-2 py-0.5 ${c.sheetInfo.fallback ? "bg-amber-500/15 text-amber-700 dark:text-amber-300" : "bg-muted text-muted-foreground"}`} title={c.sheetInfo.note}>look: {modelLabel(c.sheetInfo.model)}</span>}
        {c.voice?.model && <span className={`rounded-full px-2 py-0.5 ${c.voice.fallback ? "bg-amber-500/15 text-amber-700 dark:text-amber-300" : "bg-muted text-muted-foreground"}`}>voice: {modelLabel(c.voice.model)}</span>}
      </div>
      {!edit ? (
        <div className="space-y-1 text-sm">
          <p className="text-foreground/90">{c.look}</p>
          {c.outfit && <p className="text-muted-foreground"><b>Outfit:</b> {c.outfit}</p>}
          {c.personality && <p className="text-muted-foreground"><b>Personality:</b> {c.personality}</p>}
          {c.voice?.description && <p className="text-muted-foreground"><b>Voice:</b> {c.voice.description}</p>}
        </div>
      ) : (
        <div className="space-y-2">
          {(["look", "outfit", "personality", "voice", "age"] as const).map((k) => (
            <label key={k} className="block text-xs text-muted-foreground">{k}
              <textarea className={`${field} mt-1 min-h-10`} value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} data-testid={`edit-${k}`} />
            </label>
          ))}
          <div className="flex gap-2">
            <Button size="sm" onClick={() => { setEdit(false); void act(`edit-${c.id}`, () => seriesApi.editCharacter(sid, c.id, form)); }} data-testid="edit-save">Save</Button>
            <Button size="sm" variant="ghost" onClick={() => setEdit(false)}>Cancel</Button>
          </div>
          <p className="text-[11px] text-muted-foreground">Saved changes are used when you redo the look or the voice.</p>
        </div>
      )}
      {c.error && <p className="text-sm text-red-600 dark:text-red-400">{c.error}</p>}
      {!working && (
        <div className="space-y-2 border-t border-border pt-3">
          <input className={field} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Note for a redo: e.g. rounder face, a red cap, a deeper voice" data-testid="redo-note" />
          <div className="flex flex-wrap gap-2">
            {c.status === "review" && <Button size="sm" onClick={() => act(`approve-${c.id}`, () => seriesApi.approveCharacter(sid, c.id))} disabled={!!pending} data-testid="approve-character"><CheckCircle2 />Approve {c.name}</Button>}
            {c.status === "approved" && <Button size="sm" variant="outline" onClick={() => act(`lib-${c.id}`, () => seriesApi.saveToLibrary(sid, c.id))} data-testid="save-library"
              title="Keep this character (sheet + voice) to cast in other films and series"><BookUser />{c.fromLibrary ? "Update in library" : "Save to library"}</Button>}
            <Button size="sm" variant="outline" onClick={() => { void act(`redo-${c.id}`, () => seriesApi.redoCharacter(sid, c.id, "look", note)); setNote(""); }} data-testid="redo-look"><Wand2 />Redo look</Button>
            <Button size="sm" variant="outline" onClick={() => { void act(`redo-${c.id}`, () => seriesApi.redoCharacter(sid, c.id, "voice", note)); setNote(""); }} data-testid="redo-voice"><Mic />Redo voice</Button>
            <Button size="sm" variant="ghost" onClick={() => { setForm({ look: c.look, outfit: c.outfit, personality: c.personality, voice: c.voice?.description ?? "", age: c.age }); setEdit(!edit); }}><Pencil />Edit</Button>
            <label className="inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-lg px-3 text-sm hover:bg-accent" title="Your own drawing of this character: the sheet is drawn from it">
              <ImagePlus className="h-4 w-4" />Picture<input type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={upload("picture")} />
            </label>
            <label className="inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-lg px-3 text-sm hover:bg-accent" title="A recording of the voice you want (10-20 s): every line is cloned from it">
              <Upload className="h-4 w-4" />Voice<input type="file" accept="audio/*" className="hidden" onChange={upload("voice")} />
            </label>
          </div>
        </div>
      )}
    </div>
  );
}

export function AddCharacter({ sid, act }: { sid: string; act: Act }) {
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ name: "", look: "", outfit: "", personality: "", voice: "", age: "", gender: "other" });
  if (!open) return (
    <button className="flex min-h-40 items-center justify-center gap-2 rounded-2xl border border-dashed border-border text-sm text-muted-foreground hover:border-amber-500" onClick={() => setOpen(true)} data-testid="add-character">
      <Plus className="h-4 w-4" />Add a character
    </button>
  );
  return (
    <div className="space-y-2 rounded-2xl border border-border bg-card/40 p-4">
      <input className={field} placeholder="Name" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} data-testid="new-char-name" />
      <div className="grid grid-cols-2 gap-2">
        <input className={field} placeholder="Age" value={f.age} onChange={(e) => setF({ ...f, age: e.target.value })} />
        <select className={field} value={f.gender} onChange={(e) => setF({ ...f, gender: e.target.value })}><option value="other">Gender…</option><option value="male">male</option><option value="female">female</option></select>
      </div>
      <textarea className={`${field} min-h-14`} placeholder="Look: face, hair, body, skin tone, details" value={f.look} onChange={(e) => setF({ ...f, look: e.target.value })} data-testid="new-char-look" />
      <input className={field} placeholder="Outfit" value={f.outfit} onChange={(e) => setF({ ...f, outfit: e.target.value })} />
      <input className={field} placeholder="Personality" value={f.personality} onChange={(e) => setF({ ...f, personality: e.target.value })} />
      <input className={field} placeholder="Voice: e.g. old man, deep, slow, a little hoarse" value={f.voice} onChange={(e) => setF({ ...f, voice: e.target.value })} />
      <div className="flex gap-2">
        <Button size="sm" disabled={!f.name.trim()} onClick={() => { void act("add-character", () => seriesApi.addCharacter(sid, f)); setOpen(false); setF({ name: "", look: "", outfit: "", personality: "", voice: "", age: "", gender: "other" }); }} data-testid="new-char-save"><Plus />Draw and voice</Button>
        <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
      </div>
    </div>
  );
}

function NewEpisode({ sid, act, canStart, number }: { sid: string; act: Act; canStart: boolean; number: number }) {
  const [mode, setMode] = useState<"ai" | "script">("ai");
  const [brief, setBrief] = useState("");
  const [minutes, setMinutes] = useState(10);
  const [script, setScript] = useState("");
  const [title, setTitle] = useState("");
  return (
    <div className="space-y-4 rounded-2xl border border-border bg-card/40 p-5" data-testid="new-episode">
      <div className="flex flex-wrap items-center gap-3">
        <b className="text-foreground">Episode {number}</b>
        <div className="inline-flex rounded-xl border border-border p-0.5 text-sm">
          <button className={`rounded-full px-3 py-1 ${mode === "ai" ? "bg-amber-500 text-white" : "text-muted-foreground"}`} onClick={() => setMode("ai")} data-testid="mode-ai">AI writes it</button>
          <button className={`rounded-full px-3 py-1 ${mode === "script" ? "bg-amber-500 text-white" : "text-muted-foreground"}`} onClick={() => setMode("script")} data-testid="mode-script">My script</button>
        </div>
      </div>
      {!canStart && <p className="text-sm text-amber-700 dark:text-amber-300">Approve at least one character first.</p>}
      <input className={field} placeholder="Title (optional)" value={title} onChange={(e) => setTitle(e.target.value)} />
      {mode === "ai" ? (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
          <textarea className={`${field} min-h-20 md:col-span-3`} placeholder="What happens in this episode? e.g. Bunty breaks the TV remote right before the cricket final and has to hide it from Papa"
            value={brief} onChange={(e) => setBrief(e.target.value)} data-testid="episode-brief" />
          <label className="text-xs text-muted-foreground">Length (minutes)
            <input type="number" min={0.5} max={60} step={0.5} className={`${field} mt-1`} value={minutes} onChange={(e) => setMinutes(Number(e.target.value))} data-testid="episode-minutes" />
          </label>
        </div>
      ) : (
        <div className="space-y-1">
          <textarea className={`${field} min-h-48 font-mono`} value={script} onChange={(e) => setScript(e.target.value)} data-testid="episode-script"
            placeholder={"INT. KITCHEN - MORNING\nBunty: (excited) Mummy, see what I found!\n(Mummy turns around holding a ladle)\nMummy: Put that down. Right now."} />
          <p className="text-[11px] text-muted-foreground">Lines as “Name: what they say” (an emotion in brackets is optional); anything else becomes an action. Your words are kept exactly; it&apos;s split into parts by length.</p>
        </div>
      )}
      <Button disabled={!canStart || (mode === "script" ? !script.trim() : false)} data-testid="episode-start"
        onClick={() => act("new-episode", () => seriesApi.newEpisode(sid, mode === "ai" ? { brief, minutes, title } : { script, minutes: 10, title }))}>
        <Film />{mode === "ai" ? "Outline the episode" : "Use my script"}
      </Button>
    </div>
  );
}
