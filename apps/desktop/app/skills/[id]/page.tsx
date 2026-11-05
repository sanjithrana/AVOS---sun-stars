"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Check, Copy, Download, Loader2, RotateCcw, Square, TriangleAlert } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { skills, type Run, type StepId } from "@/lib/skills";
import { CompanyRun } from "@/components/skills/CompanyRun";

type PromptKey = "compact" | "transformed" | "video";
const OUT: { key: PromptKey; step: StepId; title: string }[] = [
  { key: "compact", step: "compact", title: "Compact device" },
  { key: "transformed", step: "transformed", title: "Fully transformed" },
  { key: "video", step: "video", title: "Transformation video" },
];

function StepDot({ s }: { s?: string }) {
  if (s === "done") return <Check className="h-4 w-4 text-[var(--signal)]" />;
  if (s === "working") return <Loader2 className="h-4 w-4 animate-spin" />;
  if (s === "error") return <TriangleAlert className="h-4 w-4 text-red-400" />;
  return <span className="block h-2 w-2 rounded-full bg-muted-foreground/40" />;
}

function PromptBox({ run, k, onSave, busy }: { run: Run; k: PromptKey; onSave: (text: string) => void; busy: boolean }) {
  const text = run.prompts?.[k] ?? "";
  const [draft, setDraft] = useState(text);
  const [copied, setCopied] = useState(false);
  useEffect(() => setDraft(text), [text]);
  const copy = async () => { try { await navigator.clipboard.writeText(draft); setCopied(true); setTimeout(() => setCopied(false), 1500); } catch { /* clipboard blocked */ } };
  return (
    <details className="mt-3 rounded-2xl border border-border p-3 text-sm">
      <summary className="cursor-pointer font-medium">Prompt</summary>
      <textarea value={draft} onChange={(e) => setDraft(e.target.value)} rows={8} className="prompt-field mt-2 w-full resize-y rounded-xl border border-border p-3 text-xs leading-relaxed" />
      <div className="mt-2 flex flex-wrap gap-2">
        <button type="button" onClick={copy} className="inline-flex items-center gap-1.5 rounded-full border border-border px-3 py-1.5 text-xs"><Copy className="h-3.5 w-3.5" />{copied ? "Copied" : "Copy"}</button>
        {draft !== text && <button type="button" disabled={busy} onClick={() => onSave(draft)} className="rounded-full border border-[rgba(185,172,255,0.6)] px-3 py-1.5 text-xs disabled:opacity-50">Save and re-make from here</button>}
      </div>
    </details>
  );
}

export default function RunPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["skill-run", id], queryFn: () => skills.get(id), refetchInterval: (x) => (x.state.data?.busy || x.state.data?.status === "working" ? 2000 : false), retry: false });
  const done = (r: Run) => qc.setQueryData(["skill-run", id], r);
  const redo = useMutation({ mutationFn: (step: StepId) => skills.redo(id, step), onSuccess: done });
  const resume = useMutation({ mutationFn: () => skills.resume(id), onSuccess: done });
  const stop = useMutation({ mutationFn: () => skills.cancel(id), onSuccess: () => qc.invalidateQueries({ queryKey: ["skill-run", id] }) });
  const save = useMutation({
    mutationFn: async ({ k, text }: { k: PromptKey; text: string }) => { await skills.editPrompts(id, { [k]: text }); return skills.redo(id, k); },
    onSuccess: done,
  });
  const r = q.data;
  const busy = !!r?.busy || r?.status === "working";
  const v = r?.version ?? 1;

  return (
    <AppShell header={<Link href="/skills" className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="h-4 w-4" />Skills</Link>}>
      {q.isError ? <p className="m-8 rounded-xl border border-red-500/40 p-4 text-sm">{(q.error as Error).message}</p> : !r ? <p className="m-8 text-sm text-muted-foreground">Loading…</p> : r.skill === "company-story" ? <CompanyRun run={r} /> : (
        <div className="w-full px-4 py-6 md:px-8 lg:grid lg:grid-cols-[minmax(280px,360px)_minmax(0,1fr)] lg:gap-6 2xl:px-12">
          <aside className="mb-6 space-y-4 lg:sticky lg:top-0 lg:mb-0 lg:self-start">
            <section className="rounded-3xl border border-border p-5" data-testid="skill-workflow">
              <p className="text-xs text-muted-foreground">Mechanical Toy</p>
              <h1 className="mt-1 text-xl font-semibold">{r.title}</h1>
              <ol className="mt-4 space-y-3">
                {r.stages.filter((s) => r.media === "media" || s.id === "design").map((s) => {
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
              {r.status === "error" && <p className="mt-4 rounded-xl border border-red-500/40 bg-red-500/5 p-3 text-xs" role="alert">{r.error}</p>}
              <div className="mt-4 flex flex-wrap gap-2">
                {busy ? <button type="button" onClick={() => stop.mutate()} className="inline-flex items-center gap-1.5 rounded-full border border-border px-4 py-2 text-sm"><Square className="h-3.5 w-3.5" />Stop</button>
                  : r.status !== "done" ? <button type="button" onClick={() => resume.mutate()} className="rounded-full bg-primary px-4 py-2 text-sm font-semibold text-white">Continue</button>
                  : r.media === "prompts" ? <button type="button" onClick={() => redo.mutate("compact")} className="rounded-full bg-primary px-4 py-2 text-sm font-semibold text-white">Make the pictures and video</button> : null}
              </div>
            </section>
            {r.lock && (
              <section className="rounded-3xl border border-border p-5 text-sm">
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
            <details className="rounded-3xl border border-border p-5 text-xs text-muted-foreground">
              <summary className="cursor-pointer text-sm text-foreground">Activity</summary>
              <ul className="mt-2 space-y-1">{r.log.slice(-20).map((l, i) => <li key={i} className={l.kind === "error" ? "text-red-400" : ""}>{l.text}</li>)}</ul>
            </details>
          </aside>

          <div className="grid min-w-0 gap-5 md:grid-cols-2 2xl:grid-cols-3" data-testid="skill-output">
            {OUT.map((o) => {
              const file = r[o.key === "video" ? "video" : o.key];
              const working = r.steps?.[o.step]?.status === "working";
              return (
                <section key={o.key} className="rounded-3xl border border-border p-4">
                  <div className="flex items-center justify-between gap-2">
                    <h2 className="font-semibold">{o.title}</h2>
                    {file && !busy && r.media === "media" && <button type="button" onClick={() => redo.mutate(o.step)} title="Make this again (and what comes after it)" className="inline-flex items-center gap-1 rounded-full border border-border px-3 py-1 text-xs"><RotateCcw className="h-3.5 w-3.5" />Again</button>}
                  </div>
                  <div className={`mt-3 flex items-center justify-center overflow-hidden rounded-2xl bg-muted ${r.aspect === "16:9" ? "aspect-video" : r.aspect === "1:1" ? "aspect-square" : "aspect-[9/16]"}`}>
                    {file ? (o.key === "video"
                      ? <video key={`${file}-${v}`} src={skills.file(r.id, file, `${v}-${r.updatedAt}`)} controls playsInline className="h-full w-full object-contain" />
                      /* eslint-disable-next-line @next/next/no-img-element */
                      : <img src={skills.file(r.id, file, `${v}-${r.updatedAt}`)} alt={o.title} className="h-full w-full object-cover" />)
                      : <span className="flex flex-col items-center gap-2 p-6 text-center text-xs text-muted-foreground">{working ? <><Loader2 className="h-6 w-6 animate-spin" />Making it…</> : r.media === "prompts" ? "Prompt only" : "Waiting"}</span>}
                  </div>
                  {file && <a href={skills.file(r.id, file)} download className="mt-2 inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"><Download className="h-3.5 w-3.5" />Download</a>}
                  {r.prompts && <PromptBox run={r} k={o.key} busy={busy || save.isPending} onSave={(text) => save.mutate({ k: o.key, text })} />}
                </section>
              );
            })}
          </div>
        </div>
      )}
    </AppShell>
  );
}
