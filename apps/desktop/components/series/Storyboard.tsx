"use client";
/* eslint-disable @next/next/no-img-element -- pictures come from the Animation Studio service */
// The storyboard gate (films and series): every shot's first frame and the numbered sheet, approved before anything
// moves. Redraw single frames with a note, open one in the Director / Modify / use your own picture, change the
// camera on many shots at once, read what each video model will be told, then approve → every frame is animated.
import { useMemo, useState } from "react";
import { AlertTriangle, Camera, CheckCircle2, Clapperboard, Maximize2, Mic, RefreshCw, Video, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { modelLabel, seriesApi } from "./api";
import { field, type Act } from "./shared";
import { ShotTools } from "./ShotTools";
import { EASES, MOVES } from "./stage";
import type { Episode, Part, SeriesSnapshot, Shot } from "./types";

const ANGLES = ["eye level", "low angle", "high angle", "overhead"];
export const moveLabel = (m?: string) => (m ?? "static").replace(/_/g, " ");

export function starts(shots: Shot[]): number[] {
  const out: number[] = [];
  let t = 0;
  for (const s of shots) { out.push(t); t += s.seconds; }
  return out;
}

export function Storyboard({ sid, snap, ep, part, act, pending }: { sid: string; snap: SeriesSnapshot; ep: Episode; part: Part; act: Act; pending: string | null }) {
  const shots = useMemo(() => part.shots ?? [], [part.shots]);
  const t0 = useMemo(() => starts(shots), [shots]);
  const [sel, setSel] = useState<string[]>([]);
  const [note, setNote] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const [zoom, setZoom] = useState(false);
  const [cam, setCam] = useState({ move: "", ease: "", lens: "", angle: "" });
  const names = Object.fromEntries(snap.series.characters.map((c) => [c.id, c.name]));
  const opened = shots.find((x) => x.id === open);
  const v = `${part.boardAt}-${part.boards}`;
  const toggle = (id: string) => setSel(sel.includes(id) ? sel.filter((x) => x !== id) : [...sel, id]);
  const total = shots.reduce((a, s) => a + s.seconds, 0);
  const warned = shots.filter((s) => s.warnings?.length || (s.qa?.key && !s.qa.key.pass));
  const camChange = { ...(cam.move ? { move: cam.move } : {}), ...(cam.ease ? { ease: cam.ease } : {}), ...(cam.lens ? { lens: Number(cam.lens) } : {}), ...(cam.angle ? { angle: cam.angle } : {}) };

  return (
    <div className="space-y-4" data-testid="storyboard">
      {opened && <ShotTools sid={sid} snap={snap} ep={ep} part={part} shot={opened} act={act} onClose={() => setOpen(null)} />}
      {zoom && part.storyboard && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 p-4" onClick={() => setZoom(false)}>
          <img src={seriesApi.file(sid, part.storyboard, v)} alt="storyboard" className="max-h-full max-w-full rounded-xl" />
        </div>
      )}
      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-amber-500/40 bg-amber-500/5 p-3">
        <Clapperboard className="h-5 w-5 text-amber-500" />
        <div className="min-w-0 flex-1">
          <b className="text-sm text-foreground">The storyboard: nothing moves until you approve it</b>
          <p className="text-xs text-muted-foreground">{shots.length} frames · {total.toFixed(1)} s · drawn from the approved characters and the world references.
            Redraw any frame, open it in the Director, or change the camera on many at once.</p>
        </div>
        <Button onClick={() => act("approve-board", () => seriesApi.approveBoard(sid, ep.id, part.index))} disabled={!!pending} data-testid="approve-board">
          <CheckCircle2 />Approve the storyboard and animate
        </Button>
      </div>

      {part.storyboard && (
        <button className="group relative block w-full overflow-hidden rounded-xl border border-border bg-black" onClick={() => setZoom(true)} data-testid="storyboard-collage">
          <img src={seriesApi.file(sid, part.storyboard, v)} alt="The numbered storyboard" className="w-full" />
          <span className="absolute right-2 top-2 flex items-center gap-1 rounded bg-black/60 px-2 py-1 text-xs text-white opacity-80 group-hover:opacity-100"><Maximize2 className="h-3 w-3" />collage_master.png</span>
        </button>
      )}

      {warned.length > 0 && <p className="flex items-center gap-2 text-xs text-amber-700 dark:text-amber-300"><AlertTriangle className="h-4 w-4" />{warned.length} frame(s) flagged by the consistency check: look at them before approving.</p>}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5" data-testid="frames">
        {shots.map((s, i) => (
          <div key={s.id} className={`overflow-hidden rounded-xl border bg-card/40 ${sel.includes(s.id) ? "border-amber-500 ring-2 ring-amber-500/40" : "border-border"}`} data-testid={`frame-${s.id}`}>
            <button className="relative block aspect-video w-full bg-muted/40" onClick={() => toggle(s.id)} title="Select to redraw or change the camera">
              {s.files.key && <img src={seriesApi.file(sid, s.files.key, `${v}-${s.takes?.picture}-${s.keyOverride?.history?.length ?? 0}`)} alt={s.picture} className="h-full w-full object-cover" />}
              <span className="absolute left-1 top-1 rounded bg-amber-500 px-1.5 py-0.5 text-[11px] font-bold text-black">{String(i + 1).padStart(2, "0")}</span>
              <span className="absolute bottom-1 left-1 rounded bg-black/65 px-1.5 py-0.5 text-[10px] text-white">{t0[i].toFixed(1)}–{(t0[i] + s.seconds).toFixed(1)}s</span>
              {s.qa?.key && !s.qa.key.pass && <AlertTriangle className="absolute right-1 top-1 h-4 w-4 text-amber-400" />}
            </button>
            <div className="space-y-1 p-2 text-[11px]">
              <p className="text-muted-foreground"><Camera className="mr-1 inline h-3 w-3" />{s.framing}{s.angle && s.angle !== "eye level" ? ` · ${s.angle}` : ""} · {moveLabel(s.blueprint?.camera.move ?? s.camera)}{s.stage ? ` · ${s.stage.camera.lens}mm` : ""}</p>
              {s.kind === "dialogue" ? <p className="line-clamp-2"><Mic className="mr-1 inline h-3 w-3 text-amber-500" /><b>{names[s.speaker ?? ""]}:</b> {s.text}</p>
                : <p className="line-clamp-2 italic text-muted-foreground"><Video className="mr-1 inline h-3 w-3" />{s.motion}</p>}
              {s.plan && <p className="text-[10px] text-muted-foreground">will animate with {modelLabel(s.plan.model)}{s.kind === "dialogue" && s.lipsync === false ? " (line over the action)" : ""}</p>}
              <button className="text-[11px] font-medium text-amber-600 hover:underline" onClick={() => setOpen(s.id)} data-testid="open-frame">Open · Director · edit</button>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <div className="space-y-2 rounded-xl border border-border p-3" data-testid="redraw-panel">
          <b className="flex items-center gap-2 text-sm text-foreground"><RefreshCw className="h-4 w-4" />Redraw {sel.length ? `${sel.length} selected frame${sel.length > 1 ? "s" : ""}` : "frames (select them above)"}</b>
          <input className={field} value={note} onChange={(e) => setNote(e.target.value)} placeholder="What to change: e.g. the rabbit is smaller, the road is wetter, warmer light" data-testid="redraw-note" />
          <div className="flex gap-2">
            <Button size="sm" variant="outline" disabled={!sel.length} data-testid="redraw-frames"
              onClick={() => { void act("redraw", () => seriesApi.redoPart(sid, ep.id, part.index, { shots: sel, what: ["picture"], note })); setSel([]); setNote(""); }}>
              <RefreshCw />Redraw
            </Button>
            {sel.length > 0 && <Button size="sm" variant="ghost" onClick={() => setSel([])}><X />Clear</Button>}
          </div>
        </div>
        <div className="space-y-2 rounded-xl border border-border p-3" data-testid="camera-panel">
          <b className="flex items-center gap-2 text-sm text-foreground"><Camera className="h-4 w-4" />Camera on {sel.length ? `${sel.length} selected shot${sel.length > 1 ? "s" : ""}` : "every shot"}</b>
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            <select className={field} value={cam.move} onChange={(e) => setCam({ ...cam, move: e.target.value })} data-testid="cam-move">
              <option value="">move: keep</option>{MOVES.map((m) => <option key={m} value={m}>{moveLabel(m)}</option>)}
            </select>
            <select className={field} value={cam.ease} onChange={(e) => setCam({ ...cam, ease: e.target.value })}>
              <option value="">ease: keep</option>{EASES.map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
            <input className={field} type="number" min={12} max={200} placeholder="lens mm" value={cam.lens} onChange={(e) => setCam({ ...cam, lens: e.target.value })} data-testid="cam-lens" />
            <select className={field} value={cam.angle} onChange={(e) => setCam({ ...cam, angle: e.target.value })} data-testid="cam-angle">
              <option value="">angle: keep</option>{ANGLES.map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          </div>
          <p className="text-[11px] text-muted-foreground">A new move only changes the motion (no redraw); a new lens or angle redraws those frames.</p>
          <Button size="sm" variant="outline" disabled={!Object.keys(camChange).length} data-testid="cam-apply"
            onClick={() => { void act("camera", () => seriesApi.camera(sid, ep.id, part.index, { ...camChange, ...(sel.length ? { shots: sel } : {}) })); setCam({ move: "", ease: "", lens: "", angle: "" }); }}>
            <Camera />Apply
          </Button>
        </div>
      </div>

      <details className="rounded-xl border border-border p-3 text-xs" data-testid="prompts">
        <summary className="cursor-pointer font-semibold text-foreground">Stage 5 · what each model will be told (compiled from the frame, the sheets, the world and the motion blueprint)</summary>
        <div className="mt-2 space-y-3">
          {shots.map((s, i) => (
            <div key={s.id}>
              <b>Shot {String(i + 1).padStart(2, "0")} · picture: {modelLabel(s.models.key?.model)} · motion: {modelLabel(s.plan?.model ?? s.models.clip?.model)}</b>
              <p className="mt-1 whitespace-pre-wrap text-muted-foreground">{s.plan?.prompt ?? s.models.clip?.prompt ?? "—"}</p>
            </div>
          ))}
        </div>
      </details>
    </div>
  );
}
