"use client";

import { Check, Loader2, Lock, TriangleAlert, Pause } from "lucide-react";

export type StepState = "todo" | "working" | "waiting" | "done" | "error";
export interface StepDef { id: string; label: string; state: StepState; note?: string; locked?: boolean }

const ICON = (s: StepState, locked?: boolean) =>
  locked ? <Lock className="h-3.5 w-3.5" /> : s === "done" ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : s === "working" ? <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
    : s === "error" ? <TriangleAlert className="h-3.5 w-3.5 text-red-400" /> : s === "waiting" ? <Pause className="h-3.5 w-3.5 text-amber-400" /> : null;

/** The row of numbered steps every studio shares (Script · Scenes · Motion · Audio · Final): where you are, what is done, what is running. */
export function StepTabs({ steps, active, onChange }: { steps: StepDef[]; active: string; onChange: (id: string) => void }) {
  return (
    <div role="tablist" aria-label="Steps" data-testid="step-tabs" className="flex flex-nowrap items-center gap-1 overflow-x-auto rounded-full border border-border p-1">
      {steps.map((s, i) => {
        const on = s.id === active;
        return (
          <button key={s.id} type="button" role="tab" aria-selected={on} disabled={s.locked} data-testid={`step-${s.id}`} onClick={() => onChange(s.id)} title={s.note}
            className={`flex shrink-0 items-center gap-2 rounded-full px-4 py-2 text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${on ? "border border-[rgba(185,172,255,0.7)] bg-[rgba(124,92,255,0.18)] text-foreground" : "border border-transparent text-muted-foreground hover:text-foreground"}`}>
            <span className="text-[10px] tabular-nums text-muted-foreground">{String(i + 1).padStart(2, "0")}</span>
            {s.label}
            {ICON(s.state, s.locked)}
          </button>
        );
      })}
    </div>
  );
}
