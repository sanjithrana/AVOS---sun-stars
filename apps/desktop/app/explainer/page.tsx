"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/AppShell";
import { Composer } from "@/components/explainer/Composer";
import { ProjectCard } from "@/components/explainer/ProjectCard";
import { CastMemory } from "@/components/explainer/CastMemory";
import { explainer } from "@/lib/explainer";

export default function ExplainerHome() {
  const list = useQuery({ queryKey: ["explainer-list"], queryFn: explainer.list, refetchInterval: 4000, retry: false });
  return (
    <AppShell header={<div className="flex w-full items-center justify-between gap-3"><span className="whitespace-nowrap text-base font-semibold sm:text-lg">Explainer Studio</span>
      <span className="flex gap-2"><Link href="/explainer/skills" className="whitespace-nowrap rounded-lg border border-border px-3 py-1.5 text-xs transition hover:bg-accent sm:text-sm" data-testid="skills-link">Skills</Link>
      <Link href="/explainer/prompts" className="whitespace-nowrap rounded-lg border border-border px-3 py-1.5 text-xs transition hover:bg-accent sm:text-sm" data-testid="prompt-library-link"><span className="sm:hidden">Prompts</span><span className="hidden sm:inline">Prompt library</span></Link></span></div>}>
      <div className="w-full space-y-10 px-4 py-6 sm:py-8 md:px-10 2xl:px-16">
        <div className="mx-auto max-w-5xl">
        <Composer />
        </div>
        <CastMemory />
        <section>
          <h2 className="mb-4 text-lg font-semibold">Your videos</h2>
          {list.isLoading ? (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4" aria-busy="true">{Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-48 animate-pulse rounded-xl bg-muted" />)}</div>
          ) : list.isError ? (
            <p className="rounded-xl border border-amber-500/40 bg-amber-500/5 p-4 text-sm" data-testid="explainer-offline">{(list.error as Error).message}</p>
          ) : !list.data?.length ? (
            <p className="text-sm text-muted-foreground">Nothing yet. Your first idea goes in the box above.</p>
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">{list.data.map((p) => <ProjectCard key={p.id} p={p} />)}</div>
          )}
        </section>
      </div>
    </AppShell>
  );
}
