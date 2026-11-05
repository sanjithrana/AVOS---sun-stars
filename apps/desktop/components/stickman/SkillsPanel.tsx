"use client";

import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import type { StyleInfo } from "@/lib/stickman";

/* The stickman skills: every look from Stickman Video Director, as cards you pick from. A = Director (clips you can
   regenerate shot by shot), B = Autopilot (a finished narrated video of illustrations with subtle motion). */
export function SkillsPanel({ styles, value, onChange, loading }: { styles: StyleInfo[]; value: string; onChange: (id: string) => void; loading?: boolean }) {
  const [q, setQ] = useState("");
  const [mode, setMode] = useState<"all" | "director" | "autopilot">("all");
  const list = useMemo(() => styles.filter((s) => (mode === "all" || s.mode === mode)
    && (!q.trim() || `${s.code} ${s.name} ${s.made_for}`.toLowerCase().includes(q.trim().toLowerCase()))), [styles, q, mode]);
  return (
    <section className="skills-panel flex h-full min-h-0 flex-col rounded-3xl border border-border" aria-label="Stickman skills" data-testid="stickman-skills">
      <div className="border-b border-border p-4">
        <h2 className="text-base font-semibold">Stickman skills</h2>
        <p className="mt-0.5 text-xs text-muted-foreground">{styles.length} looks from Stickman Video Director. Pick one.</p>
        <label className="relative mt-3 block">
          <span className="sr-only">Search skills</span>
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search, e.g. history, tech, sleep" className="w-full rounded-full border border-border py-2 pl-9 pr-3 text-sm" data-testid="skills-search" />
        </label>
        <div className="mt-3 flex gap-1 rounded-full border border-border p-0.5 text-xs" role="tablist" aria-label="Mode">
          {([["all", "All"], ["director", "A · Director"], ["autopilot", "B · Autopilot"]] as const).map(([v, l]) => (
            <button key={v} type="button" role="tab" aria-selected={mode === v} onClick={() => setMode(v)}
              className={`flex-1 rounded-full px-2 py-1.5 transition-colors ${mode === v ? "bg-[rgba(124,92,255,0.25)] text-foreground" : "text-muted-foreground hover:text-foreground"}`}>{l}</button>
          ))}
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-3" role="radiogroup" aria-label="Look">
        {loading && <p className="p-3 text-sm text-muted-foreground">Loading the skills…</p>}
        {!loading && !list.length && <p className="p-3 text-sm text-muted-foreground">No skill matches “{q}”.</p>}
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
          {list.map((s) => {
            const on = s.id === value;
            return (
              <li key={s.id}>
                <button type="button" role="radio" aria-checked={on} onClick={() => onChange(s.id)} data-testid={`style-${s.id}`}
                  className={`skill-card block w-full overflow-hidden rounded-2xl border text-left transition ${on ? "border-[rgba(185,172,255,0.75)] shadow-[0_0_28px_-6px_rgba(124,92,255,0.95)]" : "border-border"}`}>
                  <span className="relative block">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={`/stickman-styles/${s.id}.jpg`} alt="" loading="lazy" className="aspect-video w-full object-cover" />
                    <span className="absolute left-2 top-2 rounded-full bg-black/75 px-2 py-0.5 text-[11px] font-semibold">{s.code}</span>
                    <span className="absolute right-2 top-2 rounded-full bg-black/75 px-2 py-0.5 text-[10px] text-muted-foreground">{s.mode === "autopilot" ? "Autopilot" : "Director"}</span>
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
        <p className="px-2 pb-1 pt-4 text-[10px] text-muted-foreground">Looks and prompt rules adapted from Stickman Video Director (MIT).</p>
      </div>
    </section>
  );
}
