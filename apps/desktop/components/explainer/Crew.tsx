"use client";

import { useEffect, useState } from "react";

import { CheckCircle2, CircleDashed, CircleSlash, Loader2, AlertCircle, MinusCircle } from "lucide-react";
import type { Agent, AgentState, Project, StageId } from "@/lib/explainer";

const STAGE_NAME: Record<StageId, string> = { plan: "Script", design: "Design", board: "Storyboard", shoot: "Shoot", finish: "Finish" };
const ORDER: StageId[] = ["plan", "design", "board", "shoot", "finish"];

const ICON: Record<AgentState, { el: typeof CheckCircle2; tone: string; word: string }> = {
  done: { el: CheckCircle2, tone: "text-[#52c79a]", word: "Done" },
  working: { el: Loader2, tone: "text-[var(--signal)] animate-spin", word: "Working" },
  waiting: { el: CircleDashed, tone: "text-muted-foreground", word: "Waiting" },
  skipped: { el: MinusCircle, tone: "text-[#d9a64e]", word: "Skipped" },
  off: { el: CircleSlash, tone: "text-muted-foreground", word: "Off" },
  error: { el: AlertCircle, tone: "text-[#e0657c]", word: "Needs attention" },
};

/** Every agent on this video, grouped by stage: what it does, where it is, and what it made. */
export function Crew({ p, onPick }: { p: Project; onPick: (a: Agent) => void }) {
  const agents = p.agents ?? [];
  const [open, setOpen] = useState(true);
  useEffect(() => { if (window.matchMedia("(max-width: 767px)").matches) setOpen(false); }, []);   // phones start folded
  if (!agents.length) return null;
  const done = agents.filter((a) => a.state === "done").length;
  const working = agents.filter((a) => a.state === "working");
  return (
    <section className="crew rounded-2xl border border-border p-4 md:p-5" data-testid="crew">
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open} data-testid="crew-toggle" className="flex w-full flex-wrap items-baseline justify-between gap-2 text-left">
        <h2 className="text-base font-semibold">The crew</h2>
        <span className="text-xs text-muted-foreground">{done} of {agents.length} agents finished{open ? "" : " · show"}</span>
      </button>
      {working.length > 0 && !open && <p className="mt-2 text-xs text-[var(--signal)]">Working now: {working.map((a) => a.name).join(", ")}</p>}
      <div hidden={!open} className="mt-4 grid gap-4 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-5">
        {ORDER.map((st) => {
          const list = agents.filter((a) => a.stage === st);
          if (!list.length) return null;
          return (
            <div key={st} className="min-w-0">
              <p className="mb-2 text-[11px] font-medium text-muted-foreground">{STAGE_NAME[st]}</p>
              <ul className="space-y-2">
                {list.map((a) => {
                  const I = ICON[a.state] ?? ICON.waiting;
                  const pct = a.progress && a.progress[1] ? Math.round((a.progress[0] / a.progress[1]) * 100) : null;
                  return (
                    <li key={a.id}>
                      <button type="button" onClick={() => onPick(a)} data-testid={`agent-${a.id}`} title={a.does}
                        className={`agent w-full rounded-xl border px-3 py-2.5 text-left transition ${a.state === "working" ? "border-[rgba(185,172,255,0.55)] bg-[rgba(124,92,255,0.10)]" : "border-border"} ${a.state === "off" ? "opacity-55" : ""}`}>
                        <span className="flex items-center gap-2">
                          <I.el className={`h-4 w-4 shrink-0 ${I.tone}`} aria-label={I.word} />
                          <span className="truncate text-sm font-medium">{a.name}</span>
                        </span>
                        {pct !== null && (
                          <span className="mt-2 block h-1 overflow-hidden rounded-full bg-muted" aria-hidden>
                            <span className="block h-full rounded-full bg-primary transition-[width] duration-700" style={{ width: `${pct}%` }} />
                          </span>
                        )}
                        <span className="mt-1.5 block text-[11px] leading-snug text-muted-foreground">{a.output || a.does}</span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          );
        })}
      </div>
    </section>
  );
}
