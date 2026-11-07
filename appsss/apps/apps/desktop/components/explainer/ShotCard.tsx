"use client";

import { useState } from "react";
import { Camera, Clapperboard, ImageIcon, Loader2, RefreshCw, ThumbsDown, ThumbsUp } from "lucide-react";
import { FadeImg } from "./FadeImg";
import { ENGINE_LABEL, TYPE_LABEL, explainer, type Engine, type Project, type Shot } from "@/lib/explainer";

interface Props {
  p: Project;
  shot: Shot;
  editable: boolean;
  onEdit: (patch: Partial<Shot>) => void;
  onAgain: (what: "picture" | "clip", note: string, extra?: { prompt?: string; anim?: string }) => void;
  onRate?: (up: boolean, note: string) => void;
  busy: boolean;
}

/** One shot: what we see, what the voice says, which engine makes it and why, the picture and the clip. */
export function ShotCard({ p, shot, editable, onEdit, onAgain, onRate, busy }: Props) {
  const [note, setNote] = useState("");
  const [pp, setPp] = useState<string | null>(null);
  const [ap, setAp] = useState<string | null>(null);
  const engine = (shot.force ?? shot.engine) as Engine | null;
  return (
    <article id={`shot-card-${shot.id}`} className="scroll-mt-24 animate-in fade-in slide-in-from-bottom-1 rounded-2xl border border-border bg-card/50 p-4 transition-all duration-300 hover:border-amber-500/30 hover:shadow-md md:p-5" data-testid={`shot-${shot.id}`}>
      <header className="flex flex-wrap items-center gap-2">
        <span className="rounded-lg bg-amber-500/15 px-2 py-1 text-xs font-bold text-amber-700 dark:text-amber-300">{shot.id}</span>
        <span className="text-sm font-semibold">{TYPE_LABEL[shot.shot_type] ?? shot.shot_type}</span>
        <span className="text-xs text-muted-foreground">{shot.seconds}s · {shot.camera.type.replace(/_/g, " ")}, {shot.camera.movement.replace(/_/g, " ")}</span>
        {shot.speaker && <span className="rounded-full border border-amber-500/40 px-2.5 py-1 text-xs" title="This character speaks the line in their own voice">{shot.speaker} speaks</span>}
        {engine && <span className="ml-auto rounded-full border border-border px-2.5 py-1 text-xs" title={shot.engine_why}>{ENGINE_LABEL[engine]}</span>}
      </header>

      <div className="mt-4 grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,220px)]">
        <div className="space-y-3">
          <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground">Voice says
            <textarea value={shot.narration} disabled={!editable} rows={2} onChange={(e) => onEdit({ narration: e.target.value })}
              className="mt-1 w-full resize-none rounded-xl border border-border bg-background p-3 text-sm normal-case tracking-normal text-foreground disabled:opacity-80" />
          </label>
          <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground">We see
            <textarea value={shot.action} disabled={!editable} rows={2} onChange={(e) => onEdit({ action: e.target.value })}
              className="mt-1 w-full resize-none rounded-xl border border-border bg-background p-3 text-sm normal-case tracking-normal text-foreground disabled:opacity-80" />
          </label>
          {editable && (
            <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground">Made with
              <select value={shot.force ?? "auto"} onChange={(e) => onEdit({ force: e.target.value === "auto" ? undefined : (e.target.value as Engine) })}
                className="mt-1 w-full rounded-xl border border-border bg-background p-2.5 text-sm normal-case tracking-normal text-foreground">
                <option value="auto">Automatic (best available)</option>
                <option value="ai_video">AI video</option>
                <option value="blender">3D (Blender)</option>
                <option value="still">Picture + camera move</option>
              </select>
            </label>
          )}
          <dl className="grid gap-x-4 gap-y-2 rounded-xl border border-border bg-background/60 p-3 text-xs sm:grid-cols-2" data-testid={`film-${shot.id}`}>
            {([["camera", "Camera", shot.cam_note || `${shot.camera.type.replace(/_/g, " ")}, ${shot.camera.movement.replace(/_/g, " ")}, ${shot.camera.lens_mm}mm`],
               ["lighting", "Lighting", shot.lighting], ["mood", "Mood", shot.mood || shot.emotion], ["audio", "Audio", shot.audio || shot.sfx]] as const).map(([k, label, val]) => (
              <div key={k} className="min-w-0">
                <dt className="font-semibold uppercase tracking-wider text-amber-700 dark:text-amber-300">{label}</dt>
                {editable && k !== "camera" ? (
                  <dd><input value={(k === "audio" ? shot.audio : shot[k as "lighting" | "mood"]) ?? ""} onChange={(e) => onEdit({ [k]: e.target.value } as Partial<Shot>)}
                    className="mt-0.5 w-full rounded-md border border-border bg-background px-2 py-1 text-xs" /></dd>
                ) : <dd className="mt-0.5 text-foreground/90">{val || "—"}</dd>}
              </div>
            ))}
          </dl>
          {shot.engine_why && <p className="text-xs text-muted-foreground">Why: {shot.engine_why}</p>}
          {shot.info?.note && <p className="text-xs text-amber-700 dark:text-amber-300">Note: {shot.info.note}</p>}
        </div>

        <div className="grid grid-cols-2 gap-2 md:grid-cols-1">
          {shot.frame ? <div className="overflow-hidden rounded-xl"><FadeImg src={explainer.file(p.id, shot.frame, String(shot.version))} alt={`${shot.id} storyboard`} className="w-full" /></div>
            : <div style={{ aspectRatio: p.aspect === "16:9" ? "16 / 9" : p.aspect === "1:1" ? "1 / 1" : "9 / 16" }} className={`flex items-center justify-center rounded-xl bg-muted text-muted-foreground ${busy ? "animate-pulse" : ""}`}><ImageIcon className="h-6 w-6" /></div>}
          {shot.clip && <video src={explainer.file(p.id, shot.clip, String(shot.version))} controls muted playsInline preload="metadata" className="w-full animate-in fade-in rounded-xl bg-black duration-500" />}
        </div>
      </div>

      {shot.pic_prompt && (
        <details className="mt-3 rounded-xl border border-border p-3 text-xs" data-testid={`prompts-${shot.id}`}>
          <summary className="cursor-pointer font-medium">Prompts for this shot{shot.mood ? ` · ${shot.mood}` : ""}</summary>
          <label className="mt-2 block font-semibold uppercase tracking-wider text-muted-foreground">Picture prompt
            <textarea value={pp ?? shot.pic_prompt} onChange={(e) => setPp(e.target.value)} rows={5} disabled={editable}
              className="mt-1 w-full resize-y rounded-lg border border-border bg-background p-2 text-xs normal-case tracking-normal text-foreground" />
          </label>
          <label className="mt-2 block font-semibold uppercase tracking-wider text-muted-foreground">Motion prompt (for the video model)
            <textarea value={ap ?? shot.anim_prompt ?? ""} onChange={(e) => setAp(e.target.value)} rows={4} disabled={editable}
              className="mt-1 w-full resize-y rounded-lg border border-border bg-background p-2 text-xs normal-case tracking-normal text-foreground" />
          </label>
          {!editable && (
            <div className="mt-2 flex flex-wrap gap-2">
              <button type="button" disabled={busy || pp === null} onClick={() => { onAgain("picture", "", { prompt: pp ?? undefined }); setPp(null); }} className="rounded-full border border-border px-3 py-1.5 transition hover:bg-accent disabled:opacity-50">Redraw with this picture prompt</button>
              <button type="button" disabled={busy || ap === null} onClick={() => { onAgain("clip", "", { anim: ap ?? undefined }); setAp(null); }} className="rounded-full border border-border px-3 py-1.5 transition hover:bg-accent disabled:opacity-50">Remake the clip with this motion</button>
            </div>
          )}
        </details>
      )}

      {!editable && shot.frame && (
        <footer className="mt-4 flex flex-wrap items-center gap-2">
          <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="What should change? (optional)" className="min-w-0 flex-1 rounded-xl border border-border bg-background px-3 py-2 text-sm" />
          {onRate && (
            <span className="inline-flex items-center gap-1" role="group" aria-label="Rate this picture" title="Teaches the prompt library what works">
              <button type="button" disabled={busy || !!shot.rating} onClick={() => onRate(true, "")} aria-pressed={shot.rating === "up"} data-testid={`rate-up-${shot.id}`}
                className={`rounded-xl border border-border p-2 transition hover:bg-accent disabled:opacity-50 ${shot.rating === "up" ? "bg-emerald-500/20" : ""}`}><ThumbsUp className="h-4 w-4" /><span className="sr-only">Good picture</span></button>
              <button type="button" disabled={busy || !!shot.rating} onClick={() => { onRate(false, note); setNote(""); }} aria-pressed={shot.rating === "down"} data-testid={`rate-down-${shot.id}`}
                className={`rounded-xl border border-border p-2 transition hover:bg-accent disabled:opacity-50 ${shot.rating === "down" ? "bg-red-500/20" : ""}`}><ThumbsDown className="h-4 w-4" /><span className="sr-only">Bad picture</span></button>
            </span>
          )}
          <button type="button" disabled={busy} onClick={() => { onAgain("picture", note); setNote(""); }} className="inline-flex items-center gap-1.5 rounded-full border border-border px-3 py-2 text-sm transition active:scale-[0.97] hover:bg-accent disabled:opacity-50"><Camera className="h-4 w-4" />New picture</button>
          {shot.clip && <button type="button" disabled={busy} onClick={() => onAgain("clip", "")} className="inline-flex items-center gap-1.5 rounded-full border border-border px-3 py-2 text-sm hover:bg-accent disabled:opacity-50">{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}Make clip again</button>}
        </footer>
      )}
      {editable && <p className="mt-3 flex items-center gap-1.5 text-xs text-muted-foreground"><Clapperboard className="h-3.5 w-3.5" />{shot.characters.length ? "Presenter on screen" : "No people in this shot"}{shot.props.length ? ` · ${shot.props.join(", ")}` : ""}</p>}
    </article>
  );
}
