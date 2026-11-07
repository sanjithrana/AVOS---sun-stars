"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CheckCircle2, Loader2, Sparkles, TriangleAlert } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { explainer, type Skill } from "@/lib/explainer";

const STAGE: Record<string, string> = { plan: "Script", design: "Characters and set", board: "Storyboard", shoot: "Voice and shots", finish: "Final video" };

function Row({ s, onList }: { s: Skill; onList: (l: Skill[], msg?: string) => void }) {
  const [msg, setMsg] = useState("");
  const toggle = useMutation({ mutationFn: () => explainer.setSkill(s.id, !s.on), onSuccess: (r) => onList(r.skills), onError: (e) => setMsg((e as Error).message) });
  const improve = useMutation({ mutationFn: () => explainer.improveSkill(s.id), onSuccess: (r) => { setMsg(r.message ?? ""); onList(r.skills); }, onError: (e) => setMsg((e as Error).message) });
  const runs = s.ok + s.fail;
  return (
    <article className={`rounded-xl border border-border bg-card/50 p-4 md:p-5 ${s.on ? "" : "opacity-60"}`} data-testid={`skill-${s.id}`}>
      <header className="flex flex-wrap items-center gap-2">
        <h2 className="text-base font-semibold">{s.name}</h2>
        <span className="rounded-md border border-border px-2 py-0.5 text-xs text-muted-foreground">{STAGE[s.stage]}</span>
        <span className={`ml-auto inline-flex items-center gap-1 text-xs ${s.ready ? "text-emerald-600" : "text-muted-foreground"}`}>
          {s.ready ? <CheckCircle2 className="h-3.5 w-3.5" /> : <TriangleAlert className="h-3.5 w-3.5" />}{s.ready_note}</span>
      </header>
      <p className="mt-1 text-sm text-muted-foreground">{s.does}</p>
      <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-muted-foreground">
        <span>{runs ? `Worked ${s.ok} of ${runs} times` : "Not used yet"}</span>
        {s.uses > 0 && <span>{Math.round(s.bad_rate * 100)}% weak results over {s.uses} uses</span>}
        {s.prompts.length > 0 && <Link href="/explainer/prompts" className="underline underline-offset-2">{s.prompts.length} prompt{s.prompts.length > 1 ? "s" : ""} it learns</Link>}
        {s.last_error && s.fail > 0 && <span className="text-amber-700 dark:text-amber-300">Last problem: {s.last_error}</span>}
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {s.optional && (
          <button type="button" disabled={toggle.isPending} onClick={() => toggle.mutate()} className="rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-accent" aria-pressed={s.on}>
            {s.on ? "Switch off" : "Switch on"}</button>
        )}
        {s.prompts.length > 0 && (
          <button type="button" disabled={improve.isPending} onClick={() => improve.mutate()} className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-accent">
            {improve.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}Improve now</button>
        )}
      </div>
      {msg && <p className="mt-2 text-xs text-muted-foreground">{msg}</p>}
    </article>
  );
}

export default function SkillsPage() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["explainer-skills"], queryFn: explainer.skills, retry: false });
  const put = (l: Skill[]) => qc.setQueryData(["explainer-skills"], { skills: l });
  return (
    <AppShell header={<span className="text-lg font-semibold">Autopilot skills</span>}>
      <div className="mx-auto max-w-4xl space-y-4 px-4 py-8 md:px-8">
        <Link href="/explainer" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="h-4 w-4" />Explainer Studio</Link>
        <h1 className="text-2xl">One skill for every part of the line</h1>
        <p className="max-w-2xl text-sm text-muted-foreground">Autopilot runs these in order. Your approvals and redos, the picture checks and your ratings teach each skill&apos;s prompts, so the next video starts stronger. Switch off any optional skill you don&apos;t want.</p>
        {q.isLoading && <div className="h-40 animate-pulse rounded-xl bg-muted" />}
        {q.isError && <p className="rounded-xl border border-red-500/40 p-3 text-sm" role="alert">{(q.error as Error).message}</p>}
        {q.data?.skills.map((s) => <Row key={s.id} s={s} onList={put} />)}
      </div>
    </AppShell>
  );
}
