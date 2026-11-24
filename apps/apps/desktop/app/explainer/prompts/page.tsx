"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Check, FlaskConical, Loader2, RotateCcw, Sparkles } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { explainer, type PromptItem, type PromptLibrary } from "@/lib/explainer";

const pct = (n: number) => `${Math.round(n * 100)}%`;

function Bar({ rate, uses }: { rate: number; uses: number }) {
  const good = uses ? 1 - rate : 0;
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-muted" role="img" aria-label={uses ? `${pct(rate)} bad results over ${uses} uses` : "not used yet"}>
      <div className="h-full bg-emerald-500 transition-all duration-500" style={{ width: `${good * 100}%` }} />
    </div>
  );
}

function Card({ it, onLib }: { it: PromptItem; onLib: (l: PromptLibrary) => void }) {
  const [text, setText] = useState<string | null>(null);
  const [msg, setMsg] = useState("");
  const a = it.active;
  const run = useMutation({ mutationFn: (fn: () => Promise<PromptLibrary>) => fn(), onSuccess: (l) => { setText(null); setMsg(l.message ?? ""); onLib(l); }, onError: (e) => setMsg((e as Error).message) });
  const c = it.candidate;
  const flags = Object.entries(a.flags).sort((x, y) => y[1] - x[1]);
  return (
    <article className="rounded-2xl border border-border bg-card/50 p-4 transition-shadow hover:shadow-md md:p-5" data-testid={`prompt-${it.key}`}>
      <header className="flex flex-wrap items-center gap-2">
        <h3 className="text-base font-semibold">{it.title}</h3>
        <span className="rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground">v{a.v}{a.source === "learned" ? " · learned" : a.source === "manual" ? " · yours" : ""}</span>
        {c && <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/15 px-2 py-0.5 text-xs text-amber-700 dark:text-amber-300"><FlaskConical className="h-3 w-3" />testing v{c.v} ({c.uses}/{it.min_uses})</span>}
      </header>
      <p className="mt-1 text-xs text-muted-foreground">{it.help}</p>

      <div className="mt-3 grid gap-3 sm:grid-cols-[1fr_auto] sm:items-center">
        <Bar rate={a.bad_rate} uses={a.uses} />
        <p className="text-xs text-muted-foreground">{a.uses ? `${a.uses} uses · ${pct(a.bad_rate)} bad · 👍 ${a.up} 👎 ${a.down}` : "not used yet"}</p>
      </div>
      {flags.length > 0 && <p className="mt-1 text-xs text-muted-foreground">Problems seen: {flags.map(([f, n]) => `${f.replace(/_/g, " ")} ×${n}`).join(", ")}</p>}

      <textarea value={text ?? a.text} onChange={(e) => setText(e.target.value)} rows={Math.min(10, Math.max(3, Math.ceil(a.text.length / 90)))}
        className="mt-3 w-full resize-y rounded-xl border border-border bg-background p-3 text-sm" aria-label={`${it.title} text`} />
      {it.placeholders.length > 0 && <p className="mt-1 text-xs text-muted-foreground">Keep: {it.placeholders.join(" ")}</p>}

      {c && (
        <div className="mt-3 rounded-xl border border-amber-500/30 bg-amber-500/5 p-3 text-xs">
          <p className="font-medium">Being tested on about half of the next videos — {c.note}</p>
          <p className="mt-1 whitespace-pre-wrap text-foreground/80">{c.text}</p>
          <p className="mt-1 text-muted-foreground">It replaces the main prompt only if it is clearly better after {it.min_uses} uses.</p>
        </div>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button type="button" disabled={run.isPending || text === null || text === a.text} onClick={() => run.mutate(() => explainer.savePrompt(it.key, text ?? ""))}
          className="inline-flex items-center gap-1.5 rounded-full bg-amber-500 px-3 py-1.5 text-sm font-medium text-white transition active:scale-[0.97] disabled:opacity-50">{run.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}Save as my version</button>
        <button type="button" disabled={run.isPending || !!c} onClick={() => run.mutate(() => explainer.improvePrompt(it.key))}
          className="inline-flex items-center gap-1.5 rounded-full border border-border px-3 py-1.5 text-sm transition hover:bg-accent disabled:opacity-50"><Sparkles className="h-4 w-4" />Improve now</button>
        <button type="button" disabled={run.isPending} onClick={() => run.mutate(() => explainer.resetPrompt(it.key))}
          className="inline-flex items-center gap-1.5 rounded-full border border-border px-3 py-1.5 text-sm transition hover:bg-accent disabled:opacity-50"><RotateCcw className="h-4 w-4" />Built-in text</button>
        {msg && <span className="text-xs text-muted-foreground" role="status">{msg}</span>}
      </div>

      {it.versions.length > 1 && (
        <details className="mt-3 text-xs">
          <summary className="cursor-pointer font-medium">History ({it.versions.length} versions)</summary>
          <ul className="mt-2 space-y-1">
            {[...it.versions].reverse().map((v) => (
              <li key={v.v} className="flex flex-wrap items-center gap-2">
                <b>v{v.v}</b><span className="text-muted-foreground">{v.source}{v.note ? ` — ${v.note}` : ""} · {v.uses} uses · {pct(v.bad_rate)} bad</span>
                {v.v !== a.v && <button type="button" disabled={run.isPending} onClick={() => run.mutate(() => explainer.restorePrompt(it.key, v.v))} className="rounded-full border border-border px-2 py-0.5 hover:bg-accent">Use this one</button>}
              </li>
            ))}
          </ul>
        </details>
      )}
    </article>
  );
}

export default function PromptLibraryPage() {
  const qc = useQueryClient();
  const lib = useQuery({ queryKey: ["explainer-prompts"], queryFn: explainer.prompts, retry: false });
  const set = (l: PromptLibrary) => qc.setQueryData(["explainer-prompts"], l);
  const learn = useMutation({ mutationFn: explainer.learnPrompts, onSuccess: set });
  const groups = useMemo(() => {
    const g: Record<string, PromptItem[]> = {};
    for (const it of lib.data?.items ?? []) (g[it.group] ??= []).push(it);
    return g;
  }, [lib.data]);
  return (
    <AppShell header={<span className="text-lg font-semibold">Prompt library</span>}>
      <div className="mx-auto max-w-4xl space-y-8 px-4 py-8 md:px-8">
        <div>
          <Link href="/explainer" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="h-4 w-4" />Explainer</Link>
          <h1 className="mt-2 text-2xl font-semibold">Prompt library</h1>
          <p className="mt-1 text-sm text-muted-foreground">The strong prompts behind every script, picture and clip. Each result is traced back to the prompt version that made it. Dark, blank or repeated pictures, refused prompts, pictures you redo and your 👍/👎 count against a prompt. When one keeps doing badly, an improved version is tried on about half of the next videos, and it only replaces the old one if it is clearly better. Every version is kept; you can edit or restore any of them.</p>
          <button type="button" disabled={learn.isPending} onClick={() => learn.mutate()} className="mt-3 inline-flex items-center gap-1.5 rounded-full border border-border px-3 py-1.5 text-sm transition hover:bg-accent disabled:opacity-50" data-testid="learn-now">
            {learn.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <FlaskConical className="h-4 w-4" />}Check for improvements now</button>
          {lib.data?.message && <p className="mt-2 text-sm" role="status">{lib.data.message}</p>}
        </div>

        {lib.isLoading && <div className="space-y-3" aria-busy="true">{Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-40 animate-pulse rounded-2xl bg-muted" />)}</div>}
        {lib.isError && <p className="rounded-2xl border border-amber-500/40 bg-amber-500/5 p-4 text-sm">{(lib.error as Error).message}</p>}

        {lib.data && lib.data.events.length > 0 && (
          <section aria-label="What it learned">
            <h2 className="text-lg font-semibold">What it learned</h2>
            <ul className="mt-2 space-y-1 text-sm text-muted-foreground">{[...lib.data.events].reverse().map((e, i) => <li key={i}>• {e.text}</li>)}</ul>
          </section>
        )}

        {Object.entries(groups).map(([g, items]) => (
          <section key={g}>
            <h2 className="mb-3 text-lg font-semibold">{g}</h2>
            <div className="space-y-4">{items.map((it) => <Card key={it.key} it={it} onLib={set} />)}</div>
          </section>
        ))}
      </div>
    </AppShell>
  );
}
