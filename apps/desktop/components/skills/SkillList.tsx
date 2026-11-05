"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import type { SkillInfo } from "@/lib/skills";
import { stickman } from "@/lib/stickman";

type Tab = "make" | "stickman";

/** Every skill in one place. "Make here" skills generate in this tab; "Stickman looks" open Stickman Studio with that look picked. */
export function SkillList({ items, value, onChange, loading }: { items: SkillInfo[]; value: string; onChange: (id: string) => void; loading?: boolean }) {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("make");
  const [q, setQ] = useState("");
  const looks = useQuery({ queryKey: ["stickman-styles"], queryFn: stickman.styles, retry: false, staleTime: 600000, enabled: tab === "stickman" });
  const needle = q.trim().toLowerCase();
  const made = useMemo(() => items.filter((s) => !needle || `${s.name} ${s.group} ${s.made_for}`.toLowerCase().includes(needle)), [items, needle]);
  const sticks = useMemo(() => (looks.data?.styles ?? []).filter((s) => !needle || `${s.code} ${s.name} ${s.made_for}`.toLowerCase().includes(needle)), [looks.data, needle]);
  const openLook = (id: string) => { try { localStorage.setItem("avos.stickman.skill", id); } catch { /* storage blocked */ } router.push("/stickman"); };

  return (
    <section className="skills-panel flex h-full min-h-0 flex-col rounded-3xl border border-border" aria-label="Skills" data-testid="skill-list">
      <div className="border-b border-border p-4">
        <h2 className="text-base font-semibold">Skills</h2>
        <p className="mt-0.5 text-xs text-muted-foreground">Name a subject, get finished media. Pick a skill.</p>
        <div className="mt-3 flex gap-1 rounded-full border border-border p-0.5 text-xs" role="tablist" aria-label="Skill group">
          {([["make", "Make here"], ["stickman", "Stickman looks"]] as const).map(([v, l]) => (
            <button key={v} type="button" role="tab" aria-selected={tab === v} onClick={() => setTab(v)} data-testid={`skill-tab-${v}`}
              className={`flex-1 rounded-full px-2 py-1.5 transition-colors ${tab === v ? "bg-[rgba(124,92,255,0.25)] text-foreground" : "text-muted-foreground hover:text-foreground"}`}>{l}</button>
          ))}
        </div>
        <label className="relative mt-3 block">
          <span className="sr-only">Search skills</span>
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search skills" className="w-full rounded-full border border-border py-2 pl-9 pr-3 text-sm" />
        </label>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        {tab === "make" ? (
          <>
            {loading && <p className="p-3 text-sm text-muted-foreground">Loading the skills…</p>}
            {!loading && !made.length && <p className="p-3 text-sm text-muted-foreground">No skill matches “{q}”.</p>}
            <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1" role="radiogroup" aria-label="Skill">
              {made.map((s) => {
                const on = s.id === value;
                return (
                  <li key={s.id}>
                    <button type="button" role="radio" aria-checked={on} onClick={() => onChange(s.id)} data-testid={`skill-${s.id}`}
                      className={`skill-card block w-full overflow-hidden rounded-2xl border text-left transition ${on ? "border-[rgba(185,172,255,0.75)] shadow-[0_0_28px_-6px_rgba(124,92,255,0.95)]" : "border-border"}`}>
                      <span className="relative block">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img src={`/skills/${s.id}.jpg`} alt="" loading="lazy" className="aspect-video w-full object-cover" />
                        <span className="absolute left-2 top-2 rounded-full bg-black/75 px-2 py-0.5 text-[10px]">{s.group}</span>
                      </span>
                      <span className="block px-3 py-2.5">
                        <span className="block text-sm font-medium">{s.name}</span>
                        <span className="mt-0.5 line-clamp-2 block text-[11px] leading-snug text-muted-foreground">{s.made_for}</span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </>
        ) : (
          <>
            {looks.isLoading && <p className="p-3 text-sm text-muted-foreground">Loading the looks…</p>}
            {looks.isError && <p className="p-3 text-sm text-muted-foreground">{(looks.error as Error).message}</p>}
            <p className="px-1 pb-3 text-[11px] text-muted-foreground">These open Stickman Studio with the look picked.</p>
            <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
              {sticks.map((s) => (
                <li key={s.id}>
                  <button type="button" onClick={() => openLook(s.id)} className="skill-card flex w-full items-center gap-3 overflow-hidden rounded-2xl border border-border p-2 text-left">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={`/stickman-styles/${s.id}.jpg`} alt="" loading="lazy" className="h-14 w-24 shrink-0 rounded-xl object-cover" />
                    <span className="min-w-0"><span className="block text-sm font-medium">{s.code} {s.name}</span>
                      <span className="line-clamp-1 block text-[11px] text-muted-foreground">{s.made_for}</span></span>
                  </button>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </section>
  );
}
