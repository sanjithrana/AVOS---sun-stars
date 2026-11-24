"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Film } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { SkillGrid } from "@/components/skills/SkillGrid";
import { SkillComposer } from "@/components/skills/SkillComposer";
import { AgentSkills } from "@/components/skills/AgentSkills";
import { skills } from "@/lib/skills";
import { ListChecks, Type as TypeIcon, Video } from "lucide-react";
import { Lit, PageHero } from "@/components/brand/PageHero";

const LABEL: Record<string, string> = { working: "Working", done: "Ready", error: "Stopped with an error", stopped: "Stopped" };
const KEY = "avos.skills.pick";

/** Skills: pick a skill on the left, name a subject on the right; your runs below. */
export default function SkillsHome() {
  const q = useQuery({ queryKey: ["skills"], queryFn: skills.list, refetchInterval: 5000, retry: false });
  const [pick, setPick] = useState("");
  useEffect(() => {
    if (pick || !q.data?.skills.length) return;
    let saved = "";
    try { saved = localStorage.getItem(KEY) || ""; } catch { /* storage blocked */ }
    setPick(q.data.skills.some((s) => s.id === saved) ? saved : q.data.skills[0].id);
  }, [q.data, pick]);
  const choose = (id: string) => {
    setPick(id);
    try { localStorage.setItem(KEY, id); } catch { /* storage blocked */ }
    // The composer is above the grid, so a pick made halfway down the page would otherwise change something the
    // person cannot see.
    try { window.scrollTo({ top: 0, behavior: "smooth" }); } catch { /* older browser */ }
  };
  const cur = q.data?.skills.find((s) => s.id === pick) ?? null;
  const runs = q.data?.runs ?? [];

  return (
    <AppShell header={<span className="text-lg font-semibold">Skills</span>}>
      <div className="w-full space-y-10 px-4 py-6 md:px-8 2xl:px-12">
        <PageHero eyebrow="Skills" title={<>Pick a skill. <Lit>Get a finished video.</Lit></>}
          blurb="Each skill is a ready-made way to make one kind of video: a company story, a toy that builds itself, a recipe in anime style and more."
          steps={[{ icon: ListChecks, t: "Choose a skill", d: "Search the grid below." }, { icon: TypeIcon, t: "Name the subject", d: "A company, a product, a dish." }, { icon: Video, t: "Review and publish", d: "Approve the plan, then it renders." }]} />
        {/* The chosen skill first, then everything else underneath. With seventy-one skills a sidebar list is
            unreadable; a grid of covers you can search and filter is not. */}
        <div className="min-w-0"><SkillComposer skill={cur} /></div>

        <section>
          <h2 className="mb-4 text-lg font-semibold">All skills</h2>
          {q.isError ? <p className="border border-border p-4 text-sm text-muted-foreground">{(q.error as Error).message}</p>
            : <SkillGrid items={q.data?.skills ?? []} value={pick} onChange={choose} loading={q.isLoading} />}
        </section>

        <AgentSkills />

        <section>
          <h2 className="mb-4 text-lg font-semibold">Your runs</h2>
          {!runs.length ? <p className="text-sm text-muted-foreground">Nothing yet.</p>
            : <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 2xl:grid-cols-6">
                {runs.map((r) => (
                  <Link key={r.id} href={`/skills/${r.id}`} className="overflow-hidden border border-border bg-card hover:border-[rgba(200,255,58,0.5)]">
                    <div className="flex aspect-[3/4] items-center justify-center bg-muted">
                      {r.thumb ? /* eslint-disable-next-line @next/next/no-img-element */ <img src={skills.file(r.id, r.thumb, r.updatedAt)} alt="" className="h-full w-full object-cover" /> : <Film className="h-8 w-8 text-muted-foreground" />}
                    </div>
                    <div className="p-3"><p className="line-clamp-2 text-sm font-semibold">{r.title}</p><p className="text-xs text-muted-foreground">{LABEL[r.status]}{r.media === "prompts" ? " · prompts" : ""}</p></div>
                  </Link>
                ))}
              </div>}
        </section>
      </div>
    </AppShell>
  );
}
