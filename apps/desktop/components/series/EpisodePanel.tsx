"use client";
/* eslint-disable @next/next/no-img-element -- pictures come from the Animation Studio service */
// One episode: outline approval, then part by part: script (edit / approve / rewrite) → render → watch (approve / redo
// shots) → the next part; finally the joined episode.
import { useState } from "react";
import { AlertTriangle, CheckCircle2, ChevronDown, Clock, Download, Loader2, MessageSquare, Mic, Play, RefreshCw, Video, Wand2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { modelLabel, seriesApi } from "./api";
import { field, type Act } from "./shared";
import { ShotTools } from "./ShotTools";
import { Storyboard } from "./Storyboard";
import { Timeline } from "./Timeline";
import type { Beat, Emotion, Episode, Part, Script, SeriesSnapshot, Shot } from "./types";

const EMOTIONS: Emotion[] = ["neutral", "happy", "excited", "angry", "sad", "scared", "surprised", "sarcastic", "worried", "shout", "whisper", "laugh"];
const PART_CHIP: Record<string, [string, string]> = {
  waiting: ["Later", "bg-muted text-muted-foreground"], writing: ["Writing…", "bg-blue-500/15 text-blue-700 dark:text-blue-300"],
  script_review: ["Script: waiting for you", "bg-amber-500/15 text-amber-700 dark:text-amber-300"], queued: ["Queued", "bg-blue-500/15 text-blue-700 dark:text-blue-300"],
  rendering: ["Rendering…", "bg-blue-500/15 text-blue-700 dark:text-blue-300"], review: ["Watch and approve", "bg-amber-500/15 text-amber-700 dark:text-amber-300"],
  board_review: ["Storyboard: waiting for you", "bg-amber-500/15 text-amber-700 dark:text-amber-300"],
  approved: ["Approved", "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300"], error: ["Failed", "bg-red-500/15 text-red-700 dark:text-red-300"],
  stopped: ["Stopped", "bg-red-500/15 text-red-700 dark:text-red-300"],
};
export const fmt = (sec?: number) => (sec === undefined ? "" : `${Math.floor(sec / 60)}:${String(Math.round(sec % 60)).padStart(2, "0")}`);

export function EpisodePanel({ sid, snap, ep, act, pending }: { sid: string; snap: SeriesSnapshot; ep: Episode; act: Act; pending: string | null }) {
  const [note, setNote] = useState("");
  const stuck = ep.status === "error" || ep.status === "stopped" || ep.parts.some((p) => p.status === "error" || p.status === "stopped");
  const done = ep.parts.filter((p) => p.status === "approved").length;
  return (
    <div className="space-y-4 rounded-xl border border-border bg-card/30 p-5" data-testid={`episode-${ep.id}`}>
      <div className="flex flex-wrap items-center gap-3">
        <b className="text-lg text-foreground">Episode {ep.number}: {ep.outline?.title || ep.title}</b>
        <span className="text-sm text-muted-foreground">{ep.targetMinutes} min · {done}/{ep.parts.length} parts approved{ep.source === "script" ? " · your script" : ""}</span>
        <span className="grow" />
        {stuck && !snap.busy && <Button size="sm" variant="outline" onClick={() => act("resume", () => seriesApi.resume(sid, ep.id))} data-testid="resume"><RefreshCw />Resume</Button>}
      </div>
      {ep.outline?.logline && <p className="text-sm text-muted-foreground">{ep.outline.logline}</p>}
      {ep.error && <p className="text-sm text-red-600 dark:text-red-400">{ep.error}</p>}
      {ep.status === "outlining" && <p className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />Writing the outline…</p>}

      {ep.status === "outline_review" && (
        <div className="space-y-3 rounded-xl border border-amber-500/40 bg-amber-500/5 p-4" data-testid="outline-review">
          <b className="text-sm text-foreground">The outline: approve it, or ask for changes</b>
          <ol className="space-y-2 text-sm">
            {ep.parts.map((p) => (
              <li key={p.index}><b className="text-foreground">Part {p.index} · {p.minutes} min:</b> <span className="text-muted-foreground">{p.summary}</span>
                {p.endsWith && <span className="text-muted-foreground"> <i>Ends with: {p.endsWith}</i></span>}</li>
            ))}
          </ol>
          <input className={field} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Changes: e.g. more Papa in part 2, end on a cliffhanger" data-testid="outline-note" />
          <div className="flex gap-2">
            <Button size="sm" onClick={() => act("outline", () => seriesApi.approveOutline(sid, ep.id))} disabled={!!pending} data-testid="approve-outline"><CheckCircle2 />Approve the outline</Button>
            <Button size="sm" variant="outline" disabled={!note.trim()} onClick={() => { void act("outline", () => seriesApi.redoOutline(sid, ep.id, note)); setNote(""); }}><Wand2 />Outline again</Button>
          </div>
        </div>
      )}

      {ep.status === "done" && ep.video && (
        <div className="space-y-2" data-testid="episode-video">
          <video controls className="aspect-video w-full rounded-xl bg-black" src={seriesApi.file(sid, ep.video, ep.seconds)} />
          <div className="flex flex-wrap gap-4">
            <a className="inline-flex items-center gap-1 text-sm text-amber-600 hover:underline" href={seriesApi.file(sid, ep.video)} download={`episode-${ep.number}.mp4`}><Download className="h-4 w-4" />Download the episode ({fmt(ep.seconds)})</a>
            <a className="inline-flex items-center gap-1 text-sm text-amber-600 hover:underline" href={seriesApi.exportUrl(sid, ep.id)} data-testid="export-project"><Download className="h-4 w-4" />Project files (.zip)</a>
          </div>
        </div>
      )}

      {ep.status !== "outlining" && ep.status !== "outline_review" && (
        <div className="space-y-3">
          {ep.parts.map((p) => <PartCard key={p.index} sid={sid} snap={snap} ep={ep} p={p} act={act} pending={pending} />)}
        </div>
      )}
    </div>
  );
}

function PartCard({ sid, snap, ep, p, act, pending }: { sid: string; snap: SeriesSnapshot; ep: Episode; p: Part; act: Act; pending: string | null }) {
  const active = ["script_review", "board_review", "review", "rendering", "queued", "writing", "error", "stopped"].includes(p.status);
  const [open, setOpen] = useState<boolean | null>(null);
  const isOpen = open ?? active;
  const [t, c] = PART_CHIP[p.status] ?? [p.status, "bg-muted text-muted-foreground"];
  const work = snap.series.work;
  const mine = snap.busy && (work.label || "").includes(`part ${p.index}`);
  return (
    <div className="rounded-xl border border-border bg-background/60" data-testid={`part-${p.index}`}>
      <button className="flex w-full flex-wrap items-center gap-3 p-3 text-left" onClick={() => setOpen(!isOpen)}>
        <b className="text-sm text-foreground">Part {p.index}</b>
        <span className="text-xs text-muted-foreground"><Clock className="mr-1 inline h-3 w-3" />{p.minutes} min{p.seconds ? ` · ${fmt(p.seconds)} rendered` : p.scriptSeconds ? ` · ~${fmt(p.scriptSeconds)} written` : ""}</span>
        <span className={`rounded-md px-2 py-0.5 text-[11px] font-medium ${c}`} data-testid="part-status">{t}</span>
        {(p.status === "rendering" || p.status === "writing") && <Loader2 className="h-4 w-4 animate-spin text-amber-500" />}
        <span className="grow truncate text-xs text-muted-foreground">{p.summary}</span>
        <ChevronDown className={`h-4 w-4 transition ${isOpen ? "rotate-180" : ""}`} />
      </button>
      {isOpen && (
        <div className="space-y-4 border-t border-border p-4">
          {p.error && <p className="flex items-start gap-2 text-sm text-red-600 dark:text-red-400"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />{p.error}</p>}
          {mine && work.step && (
            <div>
              <p className="text-sm text-muted-foreground">{work.step}{work.total ? ` · ${work.done}/${work.total}` : ""}</p>
              {!!work.total && <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted"><div className="h-full bg-amber-500 transition-all" style={{ width: `${Math.round((100 * (work.done || 0)) / work.total)}%` }} /></div>}
            </div>
          )}
          {p.status === "script_review" && p.script && <ScriptReview key={`${p.version}-${p.index}`} sid={sid} snap={snap} ep={ep} p={p} act={act} pending={pending} />}
          {p.status === "board_review" && <Storyboard sid={sid} snap={snap} ep={ep} part={p} act={act} pending={pending} />}
          {(p.status === "review" || p.status === "approved") && p.video && <PartReview sid={sid} snap={snap} ep={ep} p={p} act={act} pending={pending} />}
          {p.status !== "script_review" && p.script && !["review", "approved", "board_review"].includes(p.status) && <ScriptView snap={snap} script={p.script} />}
          {p.memory?.summary && <p className="text-xs text-muted-foreground"><b>Remembered:</b> {p.memory.summary}</p>}
        </div>
      )}
    </div>
  );
}

function speakerName(snap: SeriesSnapshot, id?: string) {
  return snap.series.characters.find((c) => c.id === id)?.name ?? id ?? "";
}

export function ScriptView({ snap, script }: { snap: SeriesSnapshot; script: Script }) {
  return (
    <div className="max-h-80 space-y-3 overflow-y-auto text-sm">
      {script.scenes.map((sc, i) => (
        <div key={sc.id ?? i}>
          <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Scene {i + 1} · {snap.series.locations.find((l) => l.id === sc.location)?.name ?? sc.location} · {sc.time}</div>
          {sc.beats.map((b, k) => b.type === "line" ? (
            <p key={b.id ?? k}><b className="text-foreground">{speakerName(snap, b.character)}</b>{b.emotion && b.emotion !== "neutral" ? <span className="text-muted-foreground"> ({b.emotion})</span> : null}: {b.text}</p>
          ) : <p key={b.id ?? k} className="italic text-muted-foreground">[{b.text}]{b.sfx ? ` 🔊 ${b.sfx}` : ""}</p>)}
        </div>
      ))}
    </div>
  );
}

function ScriptReview({ sid, snap, ep, p, act, pending }: { sid: string; snap: SeriesSnapshot; ep: Episode; p: Part; act: Act; pending: string | null }) {
  const [script, setScript] = useState<Script>(() => JSON.parse(JSON.stringify(p.script)) as Script);
  const [dirty, setDirty] = useState(false);
  const [note, setNote] = useState("");
  const approvedCast = snap.series.characters.filter((c) => c.status === "approved");
  const prevOk = p.index === 1 || ep.parts[p.index - 2]?.status === "approved";
  const setBeat = (si: number, bi: number, patch: Partial<Beat>) => {
    const next = { scenes: script.scenes.map((sc, i) => i !== si ? sc : { ...sc, beats: sc.beats.map((b, k) => (k !== bi ? b : { ...b, ...patch })) }) };
    setScript(next);
    setDirty(true);
  };
  const removeBeat = (si: number, bi: number) => {
    setScript({ scenes: script.scenes.map((sc, i) => (i !== si ? sc : { ...sc, beats: sc.beats.filter((_, k) => k !== bi) })) });
    setDirty(true);
  };
  const lines = script.scenes.reduce((n, sc) => n + sc.beats.filter((b) => b.type === "line").length, 0);
  return (
    <div className="space-y-3" data-testid="script-review">
      <p className="text-sm text-muted-foreground">Read part {p.index}&apos;s script. Change any line, emotion or action, then approve it to render. {lines} lines · about {fmt(p.scriptSeconds)}.</p>
      <div className="max-h-[32rem] space-y-4 overflow-y-auto pr-1">
        {script.scenes.map((sc, si) => (
          <div key={sc.id ?? si} className="space-y-2">
            <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Scene {si + 1} · {snap.series.locations.find((l) => l.id === sc.location)?.name ?? sc.location} · {sc.time}</div>
            {sc.beats.map((b, bi) => (
              <div key={b.id ?? bi} className="flex flex-wrap items-start gap-2" data-testid="beat">
                {b.type === "line" ? (
                  <>
                    <select className="w-28 rounded-lg border border-border bg-background px-2 py-1.5 text-sm" value={b.character} onChange={(e) => setBeat(si, bi, { character: e.target.value })}>
                      {approvedCast.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                    </select>
                    <select className="w-28 rounded-lg border border-border bg-background px-2 py-1.5 text-sm" value={b.emotion ?? "neutral"} onChange={(e) => setBeat(si, bi, { emotion: e.target.value as Emotion })}>
                      {EMOTIONS.map((x) => <option key={x}>{x}</option>)}
                    </select>
                    <input className="min-w-48 flex-1 rounded-lg border border-border bg-background px-2 py-1.5 text-sm" value={b.text} onChange={(e) => setBeat(si, bi, { text: e.target.value })} data-testid="line-text" />
                  </>
                ) : (
                  <>
                    <span className="w-28 py-1.5 text-xs font-medium text-muted-foreground">ACTION</span>
                    <input className="min-w-48 flex-1 rounded-lg border border-border bg-background px-2 py-1.5 text-sm italic" value={b.text} onChange={(e) => setBeat(si, bi, { text: e.target.value })} />
                    <input className="w-48 rounded-lg border border-border bg-background px-2 py-1.5 text-xs" value={b.sfx ?? ""} placeholder="sound" onChange={(e) => setBeat(si, bi, { sfx: e.target.value })} />
                  </>
                )}
                <button className="px-1 py-1.5 text-xs text-muted-foreground hover:text-red-500" title="Remove" onClick={() => removeBeat(si, bi)}>✕</button>
              </div>
            ))}
          </div>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3">
        {dirty && <Button size="sm" variant="outline" onClick={() => { void act("save-script", () => seriesApi.saveScript(sid, ep.id, p.index, script)); setDirty(false); }} data-testid="save-script">Save my edits</Button>}
        <Button size="sm" disabled={dirty || !prevOk || !!pending} onClick={() => act("approve-script", () => seriesApi.approveScript(sid, ep.id, p.index))} data-testid="approve-script">
          <Play />Approve and render part {p.index}
        </Button>
        {!prevOk && <span className="text-xs text-muted-foreground">Approve part {p.index - 1} first.</span>}
        <input className={`${field} w-auto min-w-64 flex-1`} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Or ask for a rewrite: e.g. funnier, shorter lines, more Papa" data-testid="script-note" />
        <Button size="sm" variant="outline" disabled={!note.trim()} onClick={() => { void act("rewrite", () => seriesApi.redoScript(sid, ep.id, p.index, note)); setNote(""); }} data-testid="rewrite-script"><Wand2 />Rewrite</Button>
      </div>
    </div>
  );
}

export function PartReview({ sid, snap, ep, p, act, pending }: { sid: string; snap: SeriesSnapshot; ep: Episode; p: Part; act: Act; pending: string | null }) {
  const [sel, setSel] = useState<string[]>([]);
  const [open, setOpen] = useState<string | null>(null);
  const opened = (p.shots ?? []).find((x) => x.id === open);
  const [what, setWhat] = useState<string[]>(["picture", "motion"]);
  const [note, setNote] = useState("");
  const shots = p.shots ?? [];
  const warned = shots.filter((s) => s.warnings.length);
  const toggle = (id: string) => setSel(sel.includes(id) ? sel.filter((x) => x !== id) : [...sel, id]);
  const fallbacks = Array.from(new Set(shots.flatMap((s) => Object.values(s.models).filter((m) => m?.fallback).map((m) => m!.model ?? "none"))));
  return (
    <div className="space-y-4" data-testid="part-review">
      {opened && <ShotTools sid={sid} snap={snap} ep={ep} part={p} shot={opened} act={act} onClose={() => setOpen(null)} />}
      <Timeline sid={sid} snap={snap} part={p} video={seriesApi.file(sid, p.video, p.renderedAt)} onOpen={(id) => setOpen(id)} />
      <div className="flex flex-wrap gap-2 text-[11px]">
        <span className="rounded-lg bg-muted px-2 py-0.5 text-muted-foreground">{shots.length} shots · {fmt(p.seconds)}</span>
        <span className="rounded-lg bg-muted px-2 py-0.5 text-muted-foreground">music: {modelLabel(p.musicInfo?.model ?? null)}</span>
        {warned.length > 0 && <span className="rounded-lg bg-amber-500/15 px-2 py-0.5 text-amber-700 dark:text-amber-300">{warned.length} shot(s) with a warning</span>}
        {fallbacks.length > 0 && <span className="rounded-lg bg-amber-500/15 px-2 py-0.5 text-amber-700 dark:text-amber-300">fallbacks used: {fallbacks.map(modelLabel).join(", ")}</span>}
      </div>
      {p.status === "review" && (
        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-amber-500/40 bg-amber-500/5 p-3">
          <Button size="sm" onClick={() => act("approve-part", () => seriesApi.approvePart(sid, ep.id, p.index))} disabled={!!pending} data-testid="approve-part">
            <CheckCircle2 />Approve part {p.index}{p.index < ep.parts.length ? ` and write part ${p.index + 1}` : " and finish the episode"}
          </Button>
          <span className="text-xs text-muted-foreground">or pick shots below to redo</span>
        </div>
      )}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4" data-testid="shots">
        {shots.map((s) => <ShotTile key={s.id} sid={sid} snap={snap} s={s} v={p.renderedAt} selected={sel.includes(s.id)} onToggle={p.status === "review" ? () => toggle(s.id) : undefined} onOpen={() => setOpen(s.id)} />)}
      </div>
      {p.status === "review" && sel.length > 0 && (
        <div className="space-y-2 rounded-xl border border-border p-3" data-testid="redo-panel">
          <b className="text-sm text-foreground">Redo {sel.length} shot{sel.length > 1 ? "s" : ""}</b>
          <div className="flex flex-wrap gap-3 text-sm">
            {(["picture", "motion", "voice"] as const).map((w) => (
              <label key={w} className="flex items-center gap-1"><input type="checkbox" checked={what.includes(w)} onChange={() => setWhat(what.includes(w) ? what.filter((x) => x !== w) : [...what, w])} />{w}</label>
            ))}
          </div>
          <input className={field} value={note} onChange={(e) => setNote(e.target.value)} placeholder="What to change: e.g. Papa should look angrier, the room is too dark" data-testid="redo-shot-note" />
          <Button size="sm" variant="outline" disabled={!what.length} data-testid="redo-shots"
            onClick={() => { void act("redo-shots", () => seriesApi.redoPart(sid, ep.id, p.index, { shots: sel, what, note })); setSel([]); setNote(""); }}>
            <RefreshCw />Redo the selected shots
          </Button>
        </div>
      )}
    </div>
  );
}

function ShotTile({ sid, snap, s, v, selected, onToggle, onOpen }: { sid: string; snap: SeriesSnapshot; s: Shot; v?: string; selected: boolean; onToggle?: () => void; onOpen: () => void }) {
  return (
    <div className={`overflow-hidden rounded-xl border bg-card/40 ${selected ? "border-amber-500 ring-2 ring-amber-500/40" : "border-border"}`} data-testid={`shot-${s.id}`}>
      <button className="relative block aspect-video w-full bg-muted/40" onClick={onToggle} disabled={!onToggle} title={onToggle ? "Select to redo" : ""}>
        {s.files.key && <img src={seriesApi.file(sid, s.files.key, `${v}-${s.takes?.picture}`)} alt={s.picture} className="h-full w-full object-cover" />}
        <span className="absolute left-1 top-1 rounded bg-black/60 px-1.5 py-0.5 text-[10px] text-white">{s.id} · {s.framing} · {s.seconds.toFixed(1)}s</span>
        {s.warnings.length > 0 && <AlertTriangle className="absolute right-1 top-1 h-4 w-4 text-amber-400" />}
      </button>
      <div className="space-y-1 p-2 text-xs">
        {s.kind === "dialogue" ? (
          <p className="line-clamp-2"><Mic className="mr-1 inline h-3 w-3 text-amber-500" /><b>{speakerName(snap, s.speaker)}:</b> {s.text}</p>
        ) : <p className="line-clamp-2 italic text-muted-foreground"><Video className="mr-1 inline h-3 w-3" />{s.motion}</p>}
        <p className="text-[10px] text-muted-foreground">{[s.models.line && `voice ${modelLabel(s.models.line.model)}`, s.models.key && `picture ${modelLabel(s.models.key.model)}`,
          s.models.clip && `motion ${modelLabel(s.models.clip.model)}`, s.models.sfx?.model && `sound ${modelLabel(s.models.sfx.model)}`].filter(Boolean).join(" · ")}</p>
        {s.warnings.map((w) => <p key={w} className="text-[10px] text-amber-700 dark:text-amber-300">{w}</p>)}
        {s.note && <p className="text-[10px] text-muted-foreground"><MessageSquare className="mr-1 inline h-3 w-3" />{s.note}</p>}
        {(s.keyOverride || s.driver || s.qa?.key?.retried) && <p className="text-[10px] text-amber-700 dark:text-amber-300">{[s.keyOverride?.source === "upload" && "your picture",
          s.keyOverride?.history?.length && `edited: ${s.keyOverride.history.at(-1)}`, s.driver && "your motion", s.qa?.key?.retried && "redrawn after QA"].filter(Boolean).join(" · ")}</p>}
        <button className="text-[11px] font-medium text-amber-600 hover:underline" onClick={onOpen} data-testid="open-shot">Open · Director · tools</button>
      </div>
    </div>
  );
}
