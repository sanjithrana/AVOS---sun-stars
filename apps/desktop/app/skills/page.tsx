"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Film } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { SkillList } from "@/components/skills/SkillList";
import { SkillComposer } from "@/components/skills/SkillComposer";
import { skills } from "@/lib/skills";

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
  const choose = (id: string) => { setPick(id); try { localStorage.setItem(KEY, id); } catch { /* ignore */ } };
  const cur = q.data?.skills.find((s) => s.id === pick) ?? null;
  const runs = q.data?.runs ?? [];

  return (
    <AppShell header={<span className="text-lg font-semibold">Skills</span>}>
      <div className="w-full space-y-10 px-4 py-6 md:px-8 2xl:px-12">
        <div className="lg:grid lg:grid-cols-[minmax(280px,340px)_minmax(0,1fr)] lg:gap-6 2xl:grid-cols-[380px_minmax(0,1fr)]">
          <div className="mb-6 max-h-[60vh] lg:max-h-none lg:sticky lg:top-0 lg:mb-0 lg:h-[calc(100dvh-8.5rem)]">
            {q.isError ? <p className="rounded-3xl border border-border p-4 text-sm text-muted-foreground">{(q.error as Error).message}</p>
              : <SkillList items={q.data?.skills ?? []} value={pick} onChange={choose} loading={q.isLoading} />}
          </div>
          <div className="min-w-0"><SkillComposer skill={cur} /></div>
        </div>

        <section>
          <h2 className="mb-4 text-lg font-semibold">Your runs</h2>
          {!runs.length ? <p className="text-sm text-muted-foreground">Nothing yet.</p>
            : <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 2xl:grid-cols-6">
                {runs.map((r) => (
                  <Link key={r.id} href={`/skills/${r.id}`} className="overflow-hidden rounded-2xl border border-border bg-card hover:border-[rgba(185,172,255,0.5)]">
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
