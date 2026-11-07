"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/AppShell";
import { Composer } from "@/components/explainer/Composer";
import { ProjectCard } from "@/components/explainer/ProjectCard";
import { explainer } from "@/lib/explainer";

export default function ExplainerHome() {
  const list = useQuery({ queryKey: ["explainer-list"], queryFn: explainer.list, refetchInterval: 4000, retry: false });
  return (
    <AppShell header={<div className="flex w-full items-center justify-between gap-3"><span className="text-lg font-semibold">Explainer Studio</span>
      <span className="flex gap-2"><Link href="/explainer/skills" className="rounded-full border border-border px-3 py-1.5 text-sm transition hover:bg-accent" data-testid="skills-link">Skills</Link>
      <Link href="/explainer/prompts" className="rounded-full border border-border px-3 py-1.5 text-sm transition hover:bg-accent" data-testid="prompt-library-link">Prompt library</Link></span></div>}>
      <div className="mx-auto max-w-4xl space-y-10 px-4 py-8 md:px-8">
        <Composer />
        <section>
          <h2 className="mb-4 text-lg font-semibold">Your videos</h2>
          {list.isLoading ? (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3" aria-busy="true">{Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-48 animate-pulse rounded-2xl bg-muted" />)}</div>
          ) : list.isError ? (
            <p className="rounded-2xl border border-amber-500/40 bg-amber-500/5 p-4 text-sm" data-testid="explainer-offline">{(list.error as Error).message}</p>
          ) : !list.data?.length ? (
            <p className="text-sm text-muted-foreground">Nothing yet. Your first idea goes in the box above.</p>
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">{list.data.map((p) => <ProjectCard key={p.id} p={p} />)}</div>
          )}
        </section>
      </div>
    </AppShell>
  );
}
