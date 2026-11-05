"use client";
/* eslint-disable @next/next/no-img-element -- pictures come from the Animation Studio service */
// One film, stage by stage: 1 breakdown → 2 characters & world (approve / redesign / from the library) →
// 3 storyboard (approve before anything moves) → 4 motion timeline → 5 prompts → 6 render (redo any shot) →
// 7 edit bay (the master, the sound, every project file).
import Link from "next/link";
import { useState } from "react";
import { CheckCircle2, Clapperboard, Download, FileJson, Film, Loader2, Play, RefreshCw, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { modelLabel, seriesApi } from "@/components/series/api";
import { DnaPanel } from "@/components/series/DnaPanel";
import { fmt, PartReview } from "@/components/series/EpisodePanel";
import { LibraryAdd } from "@/components/series/Library";
import { ModelChoices } from "@/components/series/ModelChoices";
import { AddCharacter, CharacterCard, useAct, useSeries, WorkBar } from "@/components/series/SeriesPage";
import { ShotTools } from "@/components/series/ShotTools";
import { Storyboard } from "@/components/series/Storyboard";
import { Timeline } from "@/components/series/Timeline";
import type { FilmStage, StageKey } from "@/components/series/types";
import { BreakdownPanel } from "./BreakdownPanel";

const DOT: Record<FilmStage["state"], string> = {
  done: "bg-emerald-500 text-white", working: "bg-blue-500 text-white animate-pulse", yours: "bg-amber-500 text-black ring-4 ring-amber-500/30",
  next: "bg-muted text-muted-foreground", waiting: "bg-muted text-muted-foreground",
};

export function FilmPage({ id }: { id: string }) {
  const q = useSeries(id);
  const { act, err, pending } = useAct(id);
  const [openShot, setOpenShot] = useState<string | null>(null);

  if (q.isError) return <main className="p-8"><Link href="/animations/films" className="text-sm hover:underline">← Films</Link><p className="mt-4 text-muted-foreground">{(q.error as Error).message}</p></main>;
  if (!q.data) return <main className="space-y-4 p-8"><div className="h-10 w-80 animate-pulse rounded-xl bg-muted/40" /><div className="h-64 animate-pulse rounded-xl bg-muted/40" /></main>;
  const snap = q.data;
  const s = snap.series;
  const bd = s.breakdown;
  const stages = snap.film?.stages ?? [];
  const st = (k: StageKey) => stages.find((x) => x.key === k)?.state ?? "waiting";
  const ep = snap.episodes[0];
  const part = ep?.parts[0];
  const allApproved = s.characters.length > 0 && s.characters.every((c) => c.status === "approved");
  const opened = part?.shots?.find((x) => x.id === openShot);
  const animated = part && ["review", "approved"].includes(part.status) && part.video;

  return (
    <main className="mx-auto max-w-7xl space-y-6 p-4 md:p-8" data-testid="film-page">
      {opened && ep && part && <ShotTools sid={id} snap={snap} ep={ep} part={part} shot={opened} act={act} onClose={() => setOpenShot(null)} />}
      <div>
        <Link href="/animations/films" className="text-xs text-muted-foreground hover:underline">← Films</Link>
        <div className="mt-1 flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-bold text-foreground md:text-3xl">{s.title}</h1>
          <span className="rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground">{snap.language.name}</span>
          <span className="rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground">{s.format.aspect}</span>
          {bd?.duration ? <span className="rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground">{bd.duration.toFixed(1)} s · {bd.shots?.length} shots</span> : null}
        </div>
        {s.logline && <p className="mt-2 max-w-4xl text-muted-foreground">{s.logline}</p>}
      </div>

      <ol className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7" data-testid="film-stages">
        {stages.map((x, i) => (
          <li key={x.key}>
            <a href={`#stage-${x.key}`} className="flex items-center gap-2 rounded-xl border border-border bg-card/40 p-2 text-xs hover:border-amber-500" data-testid={`stage-${x.key}`} data-state={x.state}>
              <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-bold ${DOT[x.state]}`}>{x.state === "done" ? "✓" : i + 1}</span>
              <span className="min-w-0"><b className="block truncate text-foreground">{x.label}</b>
                <span className="text-[10px] text-muted-foreground">{x.state === "yours" ? "waiting for you" : x.state === "working" ? "working…" : x.state === "done" ? "done" : "later"}</span></span>
            </a>
          </li>
        ))}
      </ol>

      <WorkBar snap={snap} onStop={() => act("stop", () => seriesApi.cancel(id))} />
      {err && <p className="rounded-xl border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-700 dark:text-red-300" data-testid="film-action-error">{err}</p>}

      <Stage n={1} id="breakdown" title="Breakdown: your prompt, read into a timed shot list" state={st("breakdown")}>
        <BreakdownPanel key={`${bd?.status}-${(bd as { at?: string })?.at}-${(bd as { edited?: string })?.edited}`} sid={id} snap={snap} act={act} pending={pending} />
        {snap.film?.breakdownChanged && part && (
          <p className="mt-3 flex flex-wrap items-center gap-2 rounded-xl border border-amber-500/40 bg-amber-500/5 p-3 text-sm" data-testid="breakdown-changed">
            The breakdown changed since the storyboard was drawn.
            <Button size="sm" variant="outline" disabled={snap.busy || !allApproved} onClick={() => act("storyboard", () => seriesApi.storyboard(id))} data-testid="update-storyboard"><RefreshCw />Update the storyboard</Button>
          </p>
        )}
      </Stage>

      {bd?.status === "approved" && (
        <Stage n={2} id="lock" title="Characters & world: the consistency lock" state={st("lock")}>
          <ModelChoices sid={id} act={act} />
          <div className="mt-4"><DnaPanel sid={id} dna={s.dna} act={act} /></div>
          <p className="my-4 text-sm text-muted-foreground">Approve each character (sheet + voice) or redesign it with a note. Approved characters can be saved to your library and cast in other films.</p>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2" data-testid="characters">
            {s.characters.map((c) => <CharacterCard key={c.id} sid={id} c={c} act={act} pending={pending} />)}
            <AddCharacter sid={id} act={act} />
            <LibraryAdd sid={id} act={act} have={s.characters.map((c) => c.fromLibrary ?? "").filter(Boolean)} />
          </div>
          {s.locations.length > 0 && (
            <div className="mt-6">
              <h3 className="mb-2 text-sm font-semibold text-foreground">World references</h3>
              <div className="flex gap-3 overflow-x-auto pb-2">
                {s.locations.map((l) => (
                  <div key={l.id} className="w-64 shrink-0 overflow-hidden rounded-xl border border-border bg-card/40" data-testid={`location-${l.id}`}>
                    <div className="aspect-video bg-muted/40">{l.plate ? <img src={seriesApi.file(id, l.plate)} alt={l.name} className="h-full w-full object-cover" /> :
                      <div className="flex h-full items-center justify-center text-xs text-muted-foreground">{l.status === "error" ? "couldn't paint" : <Loader2 className="h-5 w-5 animate-spin" />}</div>}</div>
                    <div className="flex items-center justify-between gap-2 p-2">
                      <span className="truncate text-sm text-foreground" title={l.description}>{l.name}</span>
                      <button className="text-xs text-muted-foreground hover:text-foreground" title="Paint again" onClick={() => act("place", () => seriesApi.redoLocation(id, l.id, ""))}><RefreshCw className="h-3.5 w-3.5" /></button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
          {!ep && (
            <div className="mt-4 flex flex-wrap items-center gap-3 rounded-xl border border-amber-500/40 bg-amber-500/5 p-3">
              <Button disabled={!allApproved || snap.busy || !!pending} onClick={() => act("storyboard", () => seriesApi.storyboard(id))} data-testid="make-storyboard">
                <Clapperboard />Lock the look and draw the storyboard
              </Button>
              <span className="text-xs text-muted-foreground">{allApproved ? "One clean frame per shot, from the approved sheets and world." : "Approve every character first."}</span>
            </div>
          )}
        </Stage>
      )}

      {part && (
        <Stage n={3} id="storyboard" title="Storyboard → motion → prompts" state={st("storyboard")}>
          {(part.status === "rendering" || part.status === "queued") && !part.boardApprovedAt && (
            <p className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin text-amber-500" />Drawing the frames{snap.series.work.total ? ` · ${snap.series.work.done}/${snap.series.work.total}` : ""}…</p>
          )}
          {part.status === "board_review" && <Storyboard sid={id} snap={snap} ep={ep} part={part} act={act} pending={pending} />}
          {part.boardApprovedAt && part.storyboard && (
            <p className="flex items-center gap-2 text-sm text-muted-foreground"><CheckCircle2 className="h-4 w-4 text-emerald-500" />Storyboard approved ·
              <a className="text-amber-600 hover:underline" href={seriesApi.file(id, part.storyboard)} target="_blank" rel="noreferrer">collage_master.png</a></p>
          )}
          {(part.shots?.length ?? 0) > 0 && !animated && (
            <div className="mt-4" id="stage-motion">
              <h3 className="mb-2 text-sm font-semibold text-foreground">Motion timeline (from the blueprints: click a shot to direct it)</h3>
              <Timeline sid={id} snap={snap} part={part} onOpen={(x) => setOpenShot(x)} />
            </div>
          )}
          {(part.status === "error" || part.status === "stopped") && (
            <p className="mt-3 text-sm text-red-600 dark:text-red-400">{part.error}
              {!snap.busy && <Button size="sm" variant="outline" className="ml-2" onClick={() => act("resume", () => seriesApi.resume(id, ep.id))} data-testid="resume"><RefreshCw />Resume</Button>}</p>
          )}
        </Stage>
      )}

      {part?.boardApprovedAt && (
        <Stage n={6} id="render" title="Render: every shot its own clip" state={st("render")}>
          {(part.status === "rendering" || part.status === "queued") && (
            <div className="space-y-2">
              <p className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin text-amber-500" />{snap.series.work.step ?? "Animating"}{snap.series.work.total ? ` · ${snap.series.work.done}/${snap.series.work.total}` : ""}</p>
              {!!snap.series.work.total && <div className="h-1.5 overflow-hidden rounded-full bg-muted"><div className="h-full bg-amber-500 transition-all" style={{ width: `${Math.round((100 * (snap.series.work.done ?? 0)) / snap.series.work.total)}%` }} /></div>}
            </div>
          )}
          {animated && ep && <PartReview sid={id} snap={snap} ep={ep} p={part} act={act} pending={pending} />}
        </Stage>
      )}

      {animated && ep && (
        <Stage n={7} id="edit" title="Edit bay: the master, the sound, the project files" state={st("edit")}>
          <div className="space-y-3">
            {ep.status === "done" && ep.video ? (
              <video controls className="aspect-video w-full rounded-xl bg-black" src={seriesApi.file(id, ep.video, ep.seconds)} data-testid="film-video" />
            ) : <p className="text-sm text-muted-foreground">Approve the render above to master the film (the parts are joined, the story memory saved).</p>}
            <div className="flex flex-wrap gap-2 text-[11px]">
              <span className="rounded-lg bg-muted px-2 py-0.5 text-muted-foreground">music: {modelLabel(part.musicInfo?.model ?? null)}{part.sound?.music ? ` · “${part.sound.music}”` : ""}</span>
              {Object.entries(part.ambienceInfo ?? {}).map(([k, v]) => <span key={k} className="rounded-lg bg-muted px-2 py-0.5 text-muted-foreground">ambience {k}: {modelLabel(v?.model ?? null)}</span>)}
              <span className="rounded-lg bg-muted px-2 py-0.5 text-muted-foreground">loudness −16 LUFS</span>
            </div>
            <div className="flex flex-wrap gap-3">
              {ep.video && <a className="inline-flex items-center gap-1 rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-accent" href={seriesApi.file(id, ep.video)} download={`${s.title}.mp4`}><Film className="h-4 w-4" />final_master.mp4 ({fmt(ep.seconds)})</a>}
              <a className="inline-flex items-center gap-1 rounded-lg border border-amber-500/60 px-3 py-1.5 text-sm text-amber-700 hover:bg-amber-500/10 dark:text-amber-300" href={seriesApi.exportUrl(id, ep.id)} data-testid="export-project">
                <Download className="h-4 w-4" />Project files (.zip)</a>
            </div>
            <p className="flex items-start gap-2 text-xs text-muted-foreground"><FileJson className="mt-0.5 h-4 w-4 shrink-0" />
              script.json · breakdown.json · consistency_manifest.json · storyboard/collage_master.png + frames · motion_blueprint.json · prompts/shot_NN.txt · renders/clip_NN.mp4 · audio · final/final_master.mp4 + audio_mix.wav</p>
          </div>
        </Stage>
      )}
      {!part && bd?.status === "approved" && !allApproved && (
        <p className="flex items-center gap-2 text-sm text-muted-foreground"><Users className="h-4 w-4" />Next: approve the characters, then the storyboard is drawn.</p>
      )}
      {snap.busy && !part && bd?.status !== "analyzing" && <p className="flex items-center gap-2 text-sm text-muted-foreground"><Play className="h-4 w-4" />{s.work.label}</p>}
    </main>
  );
}

function Stage({ n, id, title, state, children }: { n: number; id: string; title: string; state: string; children: React.ReactNode }) {
  return (
    <section id={`stage-${id}`} className={`scroll-mt-20 rounded-xl border p-4 md:p-5 ${state === "yours" ? "border-amber-500/60" : "border-border"} bg-card/20`} data-testid={`film-stage-${id}`}>
      <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold text-foreground">
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-amber-500 text-sm font-bold text-black">{n}</span>{title}
      </h2>
      {children}
    </section>
  );
}
