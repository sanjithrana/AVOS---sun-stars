"use client";

import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, Download, ExternalLink, Loader2, RotateCcw, Square, TriangleAlert } from "lucide-react";
import { skills, type Card, type Run, type Scene } from "@/lib/skills";

function Dot({ s }: { s?: string }) {
  if (s === "done") return <Check className="h-4 w-4 text-[var(--signal)]" />;
  if (s === "working") return <Loader2 className="h-4 w-4 animate-spin" />;
  if (s === "error") return <TriangleAlert className="h-4 w-4 text-red-400" />;
  return <span className="block h-2 w-2 rounded-full bg-muted-foreground/40" />;
}

const cardText = (c: Card) => c.type === "title" ? `${c.text} · ${c.years}` : c.type === "stat" ? `${c.value} ${c.unit ?? ""}` : c.type === "vs" ? `${c.left} vs ${c.right}` : c.type === "year" ? `${c.value}` : `${c.text}`;

function SceneCard({ run, sc, busy, onRedo, onSay }: { run: Run; sc: Scene; busy: boolean; onRedo: (step: string, n: number) => void; onSay: (n: number, text: string) => void }) {
  const [text, setText] = useState(sc.narration);
  useEffect(() => setText(sc.narration), [sc.narration]);
  const v = `${sc.version ?? 1}-${run.updatedAt}`;
  return (
    <li className="rounded-3xl border border-border p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-semibold">Scene {sc.n} <span className="font-normal text-muted-foreground">· {sc.purpose}</span></p>
        {!busy && run.media === "media" && sc.picture && <button type="button" onClick={() => onRedo("scenes", sc.n)} className="inline-flex shrink-0 items-center gap-1 rounded-full border border-border px-3 py-1 text-xs"><RotateCcw className="h-3.5 w-3.5" />New picture</button>}
      </div>
      <div className={`mt-3 overflow-hidden rounded-2xl bg-muted ${run.aspect === "9:16" ? "aspect-[9/16]" : run.aspect === "1:1" ? "aspect-square" : "aspect-video"}`}>
        {sc.video ? <video src={skills.file(run.id, sc.video, v)} controls playsInline muted className="h-full w-full object-cover" />
          /* eslint-disable-next-line @next/next/no-img-element */
          : sc.picture ? <img src={skills.file(run.id, sc.picture, v)} alt={`Scene ${sc.n}`} className="h-full w-full object-cover" />
          : <span className="flex h-full items-center justify-center text-xs text-muted-foreground">{run.steps?.scenes?.status === "working" ? "Drawing…" : run.media === "prompts" ? "Script only" : "Waiting"}</span>}
      </div>
      {!sc.video && (sc.pose_pics?.length ?? 0) > 1 && (
        <div className="mt-2 grid grid-cols-3 gap-1.5">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          {sc.pose_pics!.map((f, i) => <img key={f} src={skills.file(run.id, f, v)} alt={`Scene ${sc.n} pose ${i + 1}`} className="aspect-video w-full rounded-lg object-cover" />)}
        </div>)}
      <div className="mt-3 flex flex-wrap gap-1.5">
        {sc.cards.map((c, i) => <span key={i} className="rounded-full border border-border px-2.5 py-0.5 text-[11px]"><span className="text-muted-foreground">{c.type}</span> {cardText(c)}</span>)}
      </div>
      <textarea value={text} onChange={(e) => setText(e.target.value)} rows={3} className="prompt-field mt-3 w-full resize-y rounded-xl border border-border p-3 text-sm leading-relaxed" aria-label={`Narration for scene ${sc.n}`} />
      {sc.warning && <p className="mt-1 text-[11px] text-amber-300/90">{sc.warning}</p>}
      {sc.dropped > 0 && <p className="mt-1 text-[11px] text-muted-foreground">{sc.dropped} card(s) left out: their numbers weren&apos;t in the research.</p>}
      {text !== sc.narration && <button type="button" disabled={busy} onClick={() => onSay(sc.n, text)} className="mt-2 rounded-full border border-[rgba(185,172,255,0.6)] px-3 py-1.5 text-xs disabled:opacity-50">Save and re-record</button>}
    </li>
  );
}

/** A Company Story run: the workflow and research with sources on the left, the final video and every scene on the right. */
export function CompanyRun({ run: r }: { run: Run }) {
  const qc = useQueryClient();
  const done = (x: Run) => qc.setQueryData(["skill-run", r.id], x);
  const redo = useMutation({ mutationFn: ({ step, n }: { step: string; n?: number }) => skills.redo(r.id, step, n), onSuccess: done });
  const resume = useMutation({ mutationFn: () => skills.resume(r.id), onSuccess: done });
  const stop = useMutation({ mutationFn: () => skills.cancel(r.id), onSuccess: () => qc.invalidateQueries({ queryKey: ["skill-run", r.id] }) });
  const toPoses = useMutation({ mutationFn: async () => { await skills.setMotion(r.id, "poses"); return skills.resume(r.id); }, onSuccess: done });
  const say = useMutation({ mutationFn: async ({ n, text }: { n: number; text: string }) => { await skills.editNarration(r.id, { [String(n)]: text }); return skills.redo(r.id, "voice"); }, onSuccess: done });
  const busy = r.busy || r.status === "working";
  const R = r.research;
  const shown = r.stages.filter((s) => r.media === "media" || ["research", "script"].includes(s.id));

  return (
    <div className="w-full px-4 py-6 md:px-8 lg:grid lg:grid-cols-[minmax(280px,380px)_minmax(0,1fr)] lg:gap-6 2xl:px-12">
      <aside className="mb-6 space-y-4 lg:sticky lg:top-0 lg:mb-0 lg:max-h-[calc(100dvh-8.5rem)] lg:self-start lg:overflow-y-auto">
        <section className="rounded-3xl border border-border p-5" data-testid="skill-workflow">
          <p className="text-xs text-muted-foreground">Company Story</p>
          <h1 className="mt-1 text-xl font-semibold">{r.title}</h1>
          <ol className="mt-4 space-y-3">
            {shown.map((s) => {
              const st = r.steps?.[s.id];
              return (
                <li key={s.id} className="flex gap-3">
                  <span className="mt-0.5 flex h-5 w-5 items-center justify-center"><Dot s={st?.status} /></span>
                  <span className="min-w-0 text-sm"><span className="block">{s.label}</span>
                    {st?.model && <span className="block text-[11px] text-muted-foreground">{st.model}</span>}
                    {st?.note && <span className="block text-[11px] text-amber-300/90">{st.note}</span>}</span>
                </li>
              );
            })}
          </ol>
          {r.status === "error" && <p className="mt-4 rounded-xl border border-red-500/40 bg-red-500/5 p-3 text-xs" role="alert">{r.error}</p>}
          {r.status === "error" && r.motion === "video" && /video/i.test(r.error ?? "") && (
            <button type="button" disabled={toPoses.isPending} onClick={() => toPoses.mutate()} className="mt-2 rounded-full border border-border px-3 py-1.5 text-xs">Use drawn poses instead (free)</button>)}
          {(r.style || r.motion) && <p className="mt-3 text-[11px] text-muted-foreground">{r.style === "3d" ? "3D" : "2D"} · {r.motion === "poses" ? "drawn poses" : "AI video"}</p>}
          <div className="mt-4 flex flex-wrap gap-2">
            {busy ? <button type="button" onClick={() => stop.mutate()} className="inline-flex items-center gap-1.5 rounded-full border border-border px-4 py-2 text-sm"><Square className="h-3.5 w-3.5" />Stop</button>
              : r.status !== "done" ? <button type="button" onClick={() => resume.mutate()} className="rounded-full bg-primary px-4 py-2 text-sm font-semibold text-white">Continue</button>
              : r.media === "prompts" ? <button type="button" onClick={() => redo.mutate({ step: "cast" })} className="rounded-full bg-primary px-4 py-2 text-sm font-semibold text-white">Make the video</button>
              : <button type="button" onClick={() => redo.mutate({ step: "script" })} className="inline-flex items-center gap-1.5 rounded-full border border-border px-4 py-2 text-sm"><RotateCcw className="h-3.5 w-3.5" />New script</button>}
          </div>
        </section>

        {R && (
          <section className="rounded-3xl border border-border p-5 text-sm" data-testid="skill-research">
            <h2 className="font-semibold">Research</h2>
            <dl className="mt-3 space-y-2 text-[13px]">
              {R.founded && <div><dt className="text-xs text-muted-foreground">Founded</dt><dd>{R.founded}{R.founder ? ` · ${R.founder}` : ""}</dd></div>}
              {R.origin && <div><dt className="text-xs text-muted-foreground">How it began</dt><dd>{R.origin}</dd></div>}
              {R.home && <div><dt className="text-xs text-muted-foreground">Home</dt><dd>{R.home}</dd></div>}
              {R.parent && <div><dt className="text-xs text-muted-foreground">Parent company</dt><dd>{R.parent}</dd></div>}
              {R.about && <div><dt className="text-xs text-muted-foreground">Wikidata says</dt><dd>{R.about}</dd></div>}
            </dl>
            {!!R.story_moments?.length && <>
              <h3 className="mt-4 text-xs text-muted-foreground">The story</h3>
              <ol className="mt-1 space-y-2 text-[13px]">{R.story_moments.map((m, i) => (
                <li key={i}><b>{m.year ? `${m.year} · ` : ""}{m.title}</b>{m.kind && <span className="text-[11px] text-muted-foreground"> · {m.kind}</span>}<span className="block text-muted-foreground">{m.what}</span></li>))}</ol>
            </>}
            {!!R.milestones.length && <>
              <h3 className="mt-4 text-xs text-muted-foreground">How it grew</h3>
              <ol className="mt-1 space-y-1.5 text-[13px]">{R.milestones.map((m, i) => <li key={i} className="flex gap-3"><b className="w-10 shrink-0 tabular-nums">{m.year}</b><span>{m.event}</span></li>)}</ol>
            </>}
            {!!R.numbers.length && <>
              <h3 className="mt-4 text-xs text-muted-foreground">Checked numbers</h3>
              <ul className="mt-1 space-y-1 text-[13px]">{R.numbers.map((n, i) => <li key={i}><b>{n.value}</b> {n.label}{n.year ? ` (${n.year})` : ""}</li>)}</ul>
            </>}
            {!!R.how_it_works.length && <>
              <h3 className="mt-4 text-xs text-muted-foreground">How it works</h3>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-[13px]">{R.how_it_works.map((x, i) => <li key={i}>{x}</li>)}</ul>
            </>}
            {!!R.rivals.length && <p className="mt-4 text-[13px]"><span className="text-xs text-muted-foreground">Rivals </span>{R.rivals.join(", ")}</p>}
            {!!R.unknowns.length && <p className="mt-3 text-[12px] text-muted-foreground">Unclear in the sources: {R.unknowns.join(" · ")}</p>}
            <h3 className="mt-4 text-xs text-muted-foreground">Sources</h3>
            <ul className="mt-1 space-y-1 text-[13px]">{R.sources.map((s) => <li key={s.url}><a href={s.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 underline decoration-muted-foreground/50 underline-offset-2 hover:text-foreground">{s.title}<ExternalLink className="h-3 w-3" /></a></li>)}</ul>
          </section>
        )}
        <details className="rounded-3xl border border-border p-5 text-xs text-muted-foreground">
          <summary className="cursor-pointer text-sm text-foreground">Activity</summary>
          <ul className="mt-2 space-y-1">{r.log.slice(-20).map((l, i) => <li key={i} className={l.kind === "error" ? "text-red-400" : ""}>{l.text}</li>)}</ul>
        </details>
      </aside>

      <div className="min-w-0 space-y-6" data-testid="skill-output">
        <section className="rounded-3xl border border-border p-4">
          <div className="flex items-center justify-between gap-2">
            <h2 className="font-semibold">Final video{r.finalSeconds ? <span className="font-normal text-muted-foreground"> · {Math.round(r.finalSeconds)} s</span> : null}</h2>
            {r.video && <a href={skills.file(r.id, r.video)} download className="inline-flex items-center gap-1.5 rounded-full border border-border px-3 py-1 text-xs"><Download className="h-3.5 w-3.5" />Download</a>}
          </div>
          <div className={`mx-auto mt-3 overflow-hidden rounded-2xl bg-muted ${r.aspect === "9:16" ? "aspect-[9/16] max-h-[75vh]" : r.aspect === "1:1" ? "aspect-square max-h-[75vh]" : "aspect-video"}`}>
            {r.video ? <video key={r.updatedAt} src={skills.file(r.id, r.video, r.updatedAt)} controls playsInline className="h-full w-full object-contain" />
              : <span className="flex h-full flex-col items-center justify-center gap-2 text-sm text-muted-foreground">{busy ? <><Loader2 className="h-6 w-6 animate-spin" />{r.stages.find((s) => s.id === r.stage)?.label}…</> : r.media === "prompts" ? "Research and script only. Press Make the video when you're happy with it." : "Not made yet"}</span>}
          </div>
        </section>
        {r.script && (
          <ul className="grid gap-5 md:grid-cols-2 2xl:grid-cols-3">
            {r.script.scenes.map((sc) => <SceneCard key={sc.n} run={r} sc={sc} busy={busy || say.isPending} onRedo={(step, n) => redo.mutate({ step, n })} onSay={(n, text) => say.mutate({ n, text })} />)}
          </ul>
        )}
      </div>
    </div>
  );
}
