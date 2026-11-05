"use client";

// "Review the shots before the final video" (generation limits → review_shots): the workflow pauses after QA and
// repairs; check or edit shots on the right, then render.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Film, Loader2, XCircle } from "lucide-react";
import { queryKeys } from "@/hooks/queries";
import { gatesApi } from "@/lib/api";
import type { HumanGate } from "@/types";

interface ReviewRow { shot_id: string; shot_index?: number; status: string; repairs?: number; score?: number | null; failing?: string[] }

export function ShotsReview({ gate, onSelectShot }: { gate: HumanGate; onSelectShot: (id: string) => void }) {
  const qc = useQueryClient();
  const payload = gate.payload as { shots?: ReviewRow[]; passed?: number; total?: number };
  const rows = payload.shots ?? [];
  const decide = useMutation({
    mutationFn: (approve: boolean) => (approve ? gatesApi.approve : gatesApi.reject)(gate.id, { decided_by: "studio-user" }),
    onSettled: () => {
      qc.invalidateQueries({ queryKey: queryKeys.gates(gate.project_id) });
      qc.invalidateQueries({ queryKey: queryKeys.project(gate.project_id) });
      qc.invalidateQueries({ queryKey: queryKeys.jobs(gate.project_id) });
    },
  });
  return (
    <div className="rounded-2xl border border-amber-500/30 bg-card p-5" data-testid="shots-review">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold text-foreground">Review the shots</h2>
        <span className="rounded-full border border-amber-500/30 bg-amber-500/20 px-2.5 py-0.5 text-xs font-medium text-amber-700 dark:text-amber-300">
          {payload.passed ?? 0} of {payload.total ?? rows.length} passed QA
        </span>
      </div>
      <p className="mb-3 text-xs text-muted-foreground">
        Every shot was checked by the QA agent, and failed ones were repaired automatically. Look through them (click
        one to see and edit it on the right), then render the final video.
      </p>
      <ul className="mb-4 grid gap-1.5 sm:grid-cols-2">
        {rows.map((r) => (
          <li key={r.shot_id}>
            <button onClick={() => onSelectShot(r.shot_id)} className="flex w-full items-center gap-2 rounded-lg border border-border px-3 py-2 text-left text-sm hover:border-amber-500/40">
              <Film className="h-4 w-4 text-muted-foreground" />
              <span className="flex-1">Shot {(r.shot_index ?? 0) + 1}</span>
              {r.status === "PASS" ? (
                <span className="flex items-center gap-1 text-xs text-emerald-600 dark:text-emerald-400"><CheckCircle2 className="h-3.5 w-3.5" />PASS{r.repairs ? ` after ${r.repairs} repair${r.repairs > 1 ? "s" : ""}` : ""}</span>
              ) : r.status === "NEEDS_REVIEW" ? (
                <span className="flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400"><AlertTriangle className="h-3.5 w-3.5" />needs you{r.failing?.length ? ` (${r.failing.join(", ")})` : ""}</span>
              ) : (
                <span className="text-xs text-muted-foreground">{r.status.toLowerCase()}</span>
              )}
            </button>
          </li>
        ))}
      </ul>
      <div className="flex flex-wrap gap-2">
        <button onClick={() => decide.mutate(true)} disabled={decide.isPending} data-testid="review-render"
          className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-amber-500/20 hover:from-amber-600 hover:to-orange-600 disabled:opacity-50">
          {decide.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}Render the final video
        </button>
        <button onClick={() => decide.mutate(false)} disabled={decide.isPending}
          className="inline-flex items-center gap-1.5 rounded-xl border border-border px-4 py-2 text-sm text-foreground hover:bg-muted disabled:opacity-50">
          <XCircle className="h-4 w-4" />Stop here
        </button>
      </div>
      {decide.error && <p className="mt-2 text-xs text-red-400">{(decide.error as Error).message}</p>}
    </div>
  );
}
