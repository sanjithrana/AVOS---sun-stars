"use client";
import { QueueVideo } from "@/components/youtube/QueueVideo";

import { Progress } from "@/components/shared/Progress";
import { use, useEffect, useState } from "react";
import Link from "next/link";
import { BackLink } from "@/components/layout/BackLink";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Check, Copy, Download, Loader2, RotateCcw, Square, TriangleAlert } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { skills, type Run, type RunOutput, type StepId } from "@/lib/skills";
import { CompanyRun } from "@/components/skills/CompanyRun";

/**
 * What a run has to show is now described by the run itself (`r.outputs`, from skilllab/routes.py), because this page
 * used to hold one hard-coded list - Mechanical Toy's compact / transformed / video. Every other skill was therefore
 * asked for files it has never had: the cards said "Waiting" forever and the prompt boxes came up empty, while the
 * run underneath was perfectly fine. The list below is only the fallback for an older payload.
 */
const OUT_FALLBACK: RunOutput[] = [
  { key: "compact", step: "compact", title: "Compact device", kind: "image", prompt: "compact" },
  { key: "transformed", step: "transformed", title: "Fully transformed", kind: "image", prompt: "transformed" },
  { key: "video", step: "video", title: "Transformation video", kind: "video", prompt: "video" },
];

function StepDot({ s }: { s?: string }) {
  if (s === "done") return <Check className="h-4 w-4 text-signal" />;
  if (s === "working") return <Loader2 className="h-4 w-4 animate-spin" />;
  if (s === "error") return <TriangleAlert className="h-4 w-4 text-red-400" />;
  return <span className="block h-2 w-2 bg-muted-foreground/40" />;
}

function PromptBox({ run, k, onSave, busy }: { run: Run; k: string; onSave: (text: string) => void; busy: boolean }) {
  const text = (run.prompts as Record<string, string> | undefined)?.[k] ?? "";
  const [draft, setDraft] = useState(text);
  const [copied, setCopied] = useState(false);
  useEffect(() => setDraft(text), [text]);
  const copy = async () => { try { await navigator.clipboard.writeText(draft); setCopied(true); setTimeout(() => setCopied(false), 1500); } catch { /* clipboard blocked */ } };
  return (
    <details className="mt-3 border border-border p-3 text-sm">
      <summary className="cursor-pointer font-medium">Prompt</summary>
      <textarea value={draft} onChange={(e) => setDraft(e.target.value)} rows={8} className="prompt-field mt-2 w-full resize-y border border-border p-3 text-xs leading-relaxed" />
      <div className="mt-2 flex flex-wrap gap-2">
        <button type="button" onClick={copy} className="inline-flex items-center gap-1.5 border border-border px-3 py-1.5 text-xs"><Copy className="h-3.5 w-3.5" />{copied ? "Copied" : "Copy"}</button>
        {draft !== text && <button type="button" disabled={busy} onClick={() => onSave(draft)} className="border border-signal/60 px-3 py-1.5 text-xs disabled:opacity-50">Save and re-make from here</button>}
      </div>
    </details>
  );
}

export default function RunPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["skill-run", id], queryFn: () => skills.get(id), refetchInterval: (x)=> (x.state.data?.busy || x.state.data?.status === "working" ? 2000 : false), retry: false });
  const done = (r: Run) => qc.setQueryData(["skill-run", id], r);
  const redo = useMutation({ mutationFn: (step: StepId) => skills.redo(id, step), onSuccess: done });
  const resume = useMutation({ mutationFn: () => skills.resume(id), onSuccess: done });
  const stop = useMutation({ mutationFn: () => skills.cancel(id), onSuccess: () => qc.invalidateQueries({ queryKey: ["skill-run", id] }) });
  const save = useMutation({
    mutationFn: async ({ k, step, text }: { k: string; step: StepId; text: string }) => { await skills.editPrompts(id, { [k]: text }); return skills.redo(id, step); },
    onSuccess: done,
  });
  const r = q.data;
  const busy = !!r?.busy || r?.status === "working";
  const v = r?.version ?? 1;

  return (
    <AppShell header={<BackLink direct href="/skills" className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="h-4 w-4" />Skills</BackLink>}>
      {q.isError ? <p className="m-8 border border-red-500/40 p-4 text-sm">{(q.error as Error).message}</p> : !r ? <p className="m-8 text-sm text-muted-foreground">Loading…</p> : r.skill === "company-story" ? <CompanyRun run={r} /> : (
        <div className="w-full px-4 py-6 md:px-8 lg:grid lg:grid-cols-[minmax(280px,360px)_minmax(0,1fr)] lg:gap-6 2xl:px-12">
          <aside className="mb-6 space-y-4 lg:sticky lg:top-0 lg:mb-0 lg:self-start">
            <section className="border border-border p-5" data-testid="skill-workflow">
              <p className="text-xs text-muted-foreground">{r.skillName ?? "Skill"}</p>
              <h1 className="mt-1 text-xl font-semibold">{r.title}</h1>
              <ol className="mt-4 space-y-3">
                {r.stages.filter((s, i) => r.media === "media" || i === 0).map((s) => {
                  const st = r.steps?.[s.id];
                  return (
                    <li key={s.id} className="flex gap-3">
                      <span className="mt-0.5 flex h-5 w-5 items-center justify-center"><StepDot s={st?.status} /></span>
                      <span className="min-w-0 text-sm"><span className="block">{s.label}</span>
                        {st?.model && <span className="block text-[11px] text-muted-foreground">{st.model}</span>}
                        {st?.note && <span className="block text-[11px] text-amber-300/90">{st.note}</span>}</span>
                    </li>
                  );
                })}
              </ol>
              {busy && <div className="mt-4"><Progress pct={r.progress?.pct} text={r.progress?.text ?? r.log[r.log.length - 1]?.text} since={r.createdAt} /></div>}
              {r.status === "error" && <p className="mt-4 border border-red-500/40 bg-red-500/5 p-3 text-xs" role="alert">{r.error}</p>}
              <div className="mt-4 flex flex-wrap gap-2">
                {busy ? <button type="button" onClick={() => stop.mutate()} className="inline-flex items-center gap-1.5 border border-border px-4 py-2 text-sm"><Square className="h-3.5 w-3.5" />Stop</button>
                  : r.status !== "done" ? <button type="button" onClick={() => resume.mutate()} className="rounded-full bg-primary px-4 py-2 text-sm font-semibold text-white">Continue</button>
                  : r.media === "prompts" && r.stages[1] ? <button type="button" onClick={() => redo.mutate(r.stages[1].id)} className="rounded-full bg-primary px-4 py-2 text-sm font-semibold text-white">Make the pictures and video</button> : null}
              </div>
            </section>
            {r.lock && (
              <section className="border border-border p-5 text-sm">
                <h2 className="font-semibold">Design lock</h2>
                <dl className="mt-3 space-y-2 text-[13px]">
                  <div><dt className="text-xs text-muted-foreground">Compact form</dt><dd>{r.lock.form}</dd></div>
                  <div><dt className="text-xs text-muted-foreground">Finish</dt><dd>{r.lock.finish}</dd></div>
                  <div><dt className="text-xs text-muted-foreground">Palette</dt><dd>{r.lock.palette}</dd></div>
                  <div><dt className="text-xs text-muted-foreground">Hidden until it opens</dt><dd>{r.lock.hidden.join(", ")}</dd></div>
                </dl>
                <h3 className="mt-4 text-xs text-muted-foreground">Deployment order</h3>
                <ol className="mt-1 list-decimal space-y-1 pl-5 text-[13px]">{r.lock.sequence.map((x, i) => <li key={i}>{x}</li>)}</ol>
              </section>
            )}
            <details className="border border-border p-5 text-xs text-muted-foreground">
              <summary className="cursor-pointer text-sm text-foreground">Activity</summary>
              <ul className="mt-2 space-y-1">{r.log.slice(-20).map((l, i) => <li key={i} className={l.kind === "error" ? "text-red-400" : ""}>{l.text}</li>)}</ul>
            </details>
          </aside>

          <div className="grid min-w-0 gap-5 md:grid-cols-2 2xl:grid-cols-3" data-testid="skill-output">
            {(r.outputs?.length ? r.outputs : OUT_FALLBACK).map((o) => {
              const file = o.file ?? (o.key === "video" ? r.video : undefined);
              const working = r.steps?.[o.step]?.status === "working";
              return (
                <section key={o.key} className="border border-border p-4">
                  <div className="flex items-center justify-between gap-2">
                    <h2 className="font-semibold">{o.title}</h2>
                    {file && !busy && r.media === "media" && <button type="button" onClick={() => redo.mutate(o.step)} title="Make this again (and what comes after it)" className="inline-flex items-center gap-1 border border-border px-3 py-1 text-xs"><RotateCcw className="h-3.5 w-3.5" />Again</button>}
                  </div>
                  <div className={`mt-3 flex items-center justify-center overflow-hidden bg-muted ${r.aspect ==="16:9" ?"aspect-video" : r.aspect ==="1:1" ?"aspect-square" :"aspect-[9/16]"}`}>
                    {file ? (o.kind === "video"
                      ? <video key={`${file}-${v}`} src={skills.file(r.id, file, `${v}-${r.updatedAt}`)} controls playsInline className="h-full w-full object-contain" />
                      /* eslint-disable-next-line @next/next/no-img-element */
                      : <img src={skills.file(r.id, file, `${v}-${r.updatedAt}`)} alt={o.title} className="h-full w-full object-cover" />)
                      : <span className="flex flex-col items-center gap-2 p-6 text-center text-xs text-muted-foreground">{working ? <><Loader2 className="h-6 w-6 animate-spin" />Making it…</> : r.media === "prompts" ? "Prompt only" : "Waiting"}</span>}
                  </div>
                  {file && <a href={skills.file(r.id, file)} download className="mt-2 inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"><Download className="h-3.5 w-3.5" />Download</a>}
                  {file && o.kind === "video" && o.key === (r.outputs?.length ? r.outputs : OUT_FALLBACK).slice(-1)[0].key && <div className="mt-2"><QueueVideo url={skills.file(r.id, file)} title={r.title || "video"} /></div>}
                  {o.prompt && (r.prompts as Record<string, string> | undefined)?.[o.prompt] !== undefined && (
                    <PromptBox run={r} k={o.prompt} busy={busy || save.isPending}
                      onSave={(text) => save.mutate({ k: o.prompt as string, step: o.step, text })} />)}
                </section>
              );
            })}
          </div>
        </div>
      )}
    </AppShell>
  );
}
