"use client";
/* eslint-disable @next/next/no-img-element -- pictures come from the Animation Studio service */
// One shot up close: its picture and clip, what each model was told (the compiled prompts), the QA result, and the
// Genjutsu-style controls: Director (camera / blocking / timeline), Modify (change one thing, keep the rest and the
// motion), Animate my image, Motion from a video, Reset.
import { useState } from "react";
import { CheckCircle2, Clapperboard, ImagePlus, RotateCcw, Video, Wand2, X, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { modelLabel, seriesApi } from "./api";
import { Director } from "./Director";
import { field, type Act } from "./shared";
import type { Episode, Part, SeriesSnapshot, Shot } from "./types";

export function ShotTools({ sid, snap, ep, part, shot, act, onClose }: {
  sid: string; snap: SeriesSnapshot; ep: Episode; part: Part; shot: Shot; act: Act; onClose: () => void;
}) {
  const [director, setDirector] = useState(false);
  const [ins, setIns] = useState("");
  const [keep, setKeep] = useState(true);
  const [motion, setMotion] = useState("");
  const editable = part.status === "review" || part.status === "board_review";
  const board = part.status === "board_review";
  const v = `${part.renderedAt}-${shot.takes?.picture}-${shot.takes?.motion}`;
  const names = Object.fromEntries(snap.series.characters.map((c) => [c.id, c.name]));
  const upload = (kind: "image" | "driver") => (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    const fd = new FormData();
    if (kind === "image") { fd.append("picture", f); if (motion.trim()) fd.append("motion", motion.trim()); }
    else fd.append("video", f);
    void act(`${kind}-${shot.id}`, () => (kind === "image" ? seriesApi.animateImage : seriesApi.motionDriver)(sid, ep.id, part.index, shot.id, fd)).then(onClose);
  };
  if (director) return <Director sid={sid} snap={snap} ep={ep} part={part} shot={shot} act={act} onClose={() => { setDirector(false); onClose(); }} />;
  return (
    <div className="fixed inset-0 z-40 overflow-y-auto bg-background p-3 md:p-6" data-testid="shot-tools">
      <div className="mx-auto max-w-6xl space-y-4">
        <div className="flex flex-wrap items-center gap-3">
          <b className="text-lg text-foreground">Part {part.index} · {shot.id} · {shot.framing} · {shot.seconds.toFixed(1)}s</b>
          <span className="truncate text-sm text-muted-foreground">{shot.kind === "dialogue" ? `${names[shot.speaker ?? ""] ?? ""}: “${shot.text}”` : shot.motion}</span>
          <span className="grow" />
          <Button size="sm" variant="ghost" onClick={onClose} data-testid="shot-tools-close"><X />Close</Button>
        </div>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div className="space-y-2">
            {shot.files.key && <img src={seriesApi.file(sid, shot.files.key, v)} alt={shot.picture} className="w-full rounded-xl border border-border" data-testid="shot-key" />}
            <p className="text-xs text-muted-foreground">Picture: {modelLabel(shot.models.key?.model)}{shot.models.key?.qaRetry ? " · redrawn after QA" : ""}
              {shot.keyOverride?.source === "upload" ? " · your picture" : shot.keyOverride?.history?.length ? ` · edited: ${shot.keyOverride.history.join(" → ")}` : ""}</p>
          </div>
          <div className="space-y-2">
            {board && <p className="rounded-xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">Storyboard frame: it is animated after you approve the storyboard.
              {shot.plan && <span className="mt-2 block text-xs">Motion model: {modelLabel(shot.plan.model)} · camera {shot.blueprint?.camera.move.replace(/_/g, " ")}</span>}</p>}
            {shot.files.clip && <video controls loop className="w-full rounded-xl border border-border bg-black" src={seriesApi.file(sid, shot.files.clip, v)} data-testid="shot-clip" />}
            <p className="text-xs text-muted-foreground">Motion: {modelLabel(shot.models.clip?.model)} · camera {shot.blueprint?.camera.move.replace(/_/g, " ") ?? shot.camera}
              {shot.driver ? " · driven by your video" : ""}{shot.models.clip?.qaRetry ? " · re-animated after QA" : ""}</p>
          </div>
        </div>

        {(shot.qa?.key || shot.qa?.clip) && (
          <div className="flex flex-wrap gap-3 text-xs" data-testid="shot-qa">
            {(["key", "clip"] as const).map((k) => shot.qa?.[k] && (
              <div key={k} className={`rounded-xl border px-3 py-2 ${shot.qa[k]!.pass ? "border-emerald-500/40" : "border-amber-500/50"}`}>
                <b className="mr-2">{k === "key" ? "Picture QA" : "Motion QA"}</b>
                {shot.qa[k]!.pass ? <CheckCircle2 className="inline h-3.5 w-3.5 text-emerald-500" /> : <AlertTriangle className="inline h-3.5 w-3.5 text-amber-500" />}
                {Object.entries(shot.qa[k]!.checks ?? {}).map(([c, r]) => <span key={c} className={`ml-2 ${r.ok ? "text-muted-foreground" : "text-amber-700 dark:text-amber-300"}`}>{c}{r.ok ? " ✓" : `: ${r.why}`}</span>)}
                {shot.qa[k]!.retried && <span className="ml-2 text-muted-foreground">(fixed: {(shot.qa[k] as { first?: { fix?: string } }).first?.fix})</span>}
              </div>
            ))}
          </div>
        )}

        {editable && (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <Tool icon={<Clapperboard className="h-4 w-4" />} title="Director" text="Move the camera, the people and the timing on a 3D stage, preview it, then redo just this shot.">
              <Button size="sm" onClick={() => setDirector(true)} data-testid="open-director"><Clapperboard />Open the stage</Button>
            </Tool>
            <Tool icon={<Wand2 className="h-4 w-4" />} title="Modify shot" text="Change one thing (an object, an outfit, the light) and keep everything else.">
              <input className={field} value={ins} onChange={(e) => setIns(e.target.value)} placeholder="e.g. make the TV remote red; turn the lights off" data-testid="modify-instruction" />
              {!board && <label className="flex items-center gap-2 text-xs text-muted-foreground"><input type="checkbox" checked={keep} onChange={(e) => setKeep(e.target.checked)} />Keep the exact motion of this take (Wan VACE)</label>}
              <Button size="sm" variant="outline" disabled={!ins.trim()} data-testid="modify-go"
                onClick={() => act(`modify-${shot.id}`, () => seriesApi.modifyShot(sid, ep.id, part.index, shot.id, ins.trim(), keep)).then(onClose)}><Wand2 />Change it</Button>
            </Tool>
            <Tool icon={<ImagePlus className="h-4 w-4" />} title={board ? "Use my picture for this frame" : "Animate my image"} text="Your own picture becomes this shot's first frame, animated with the shot's motion and your note.">
              <input className={field} value={motion} onChange={(e) => setMotion(e.target.value)} placeholder="Motion note (optional): she turns and waves" />
              <label className="inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-lg border border-border px-3 text-sm hover:bg-accent" data-testid="animate-image">
                <ImagePlus className="h-4 w-4" />Choose a picture<input type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={upload("image")} />
              </label>
            </Tool>
            <Tool icon={<Video className="h-4 w-4" />} title="Motion from a video" text="Act it out on your phone (or any clip): the character copies the body movement (Wan 2.2 Animate).">
              <label className="inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-lg border border-border px-3 text-sm hover:bg-accent" data-testid="motion-driver">
                <Video className="h-4 w-4" />Choose a video<input type="file" accept="video/*" className="hidden" onChange={upload("driver")} />
              </label>
            </Tool>
            {(shot.keyOverride || shot.driver) && (
              <Tool icon={<RotateCcw className="h-4 w-4" />} title="Back to generated" text="Drop your picture, the edits and the driving video; draw this shot again from the scene.">
                <Button size="sm" variant="ghost" data-testid="reset-shot" onClick={() => act(`reset-${shot.id}`, () => seriesApi.resetShot(sid, ep.id, part.index, shot.id)).then(onClose)}><RotateCcw />Reset this shot</Button>
              </Tool>
            )}
          </div>
        )}

        <details className="rounded-xl border border-border p-3 text-xs" data-testid="shot-prompts">
          <summary className="cursor-pointer font-semibold text-foreground">What the models were told (compiled from the scene graph, the motion blueprint and the Design DNA)</summary>
          {board && shot.plan && <div className="mt-2"><b>Motion (planned) · {modelLabel(shot.plan.model)}</b><p className="mt-1 whitespace-pre-wrap text-muted-foreground">{shot.plan.prompt}</p></div>}
          {(["key", "clip", "line", "sfx"] as const).map((k) => shot.models[k]?.prompt && (
            <div key={k} className="mt-2"><b>{({ key: "Picture", clip: "Motion", line: "Voice", sfx: "Sound" } as const)[k]} · {modelLabel(shot.models[k]?.model)}</b>
              <p className="mt-1 whitespace-pre-wrap text-muted-foreground">{shot.models[k]?.prompt}</p></div>
          ))}
        </details>
      </div>
    </div>
  );
}

function Tool({ icon, title, text, children }: { icon: React.ReactNode; title: string; text: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2 rounded-xl border border-border bg-card/40 p-3">
      <b className="flex items-center gap-2 text-sm text-foreground">{icon}{title}</b>
      <p className="text-xs text-muted-foreground">{text}</p>
      {children}
    </div>
  );
}
