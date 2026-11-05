"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Loader2, XCircle } from "lucide-react";
import { queryKeys } from "@/hooks/queries";
import { gatesApi } from "@/lib/api";
import type { HumanGate, ScriptPayload } from "@/types";

export function ScriptApproval({ gate }: { gate: HumanGate }) {
  const queryClient = useQueryClient();
  const [comment, setComment] = useState("");
  const script = gate.payload as ScriptPayload;
  const warnings = (script.validation_issues ?? []).filter((i) => i.severity === "warning");

  const decide = useMutation({
    mutationFn: (approve: boolean) => {
      const decision = { decided_by: "studio-user", comment: comment.trim() || undefined };
      return approve ? gatesApi.approve(gate.id, decision) : gatesApi.reject(gate.id, decision);
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.gates(gate.project_id) });
      queryClient.invalidateQueries({ queryKey: queryKeys.project(gate.project_id) });
      queryClient.invalidateQueries({ queryKey: queryKeys.jobs(gate.project_id) });
    },
  });

  return (
    <div className="rounded-2xl border border-amber-500/30 bg-card p-5" data-testid="script-approval">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold text-foreground">Script approval</h2>
        <span className="rounded-full border border-amber-500/30 bg-amber-500/20 px-2.5 py-0.5 text-xs font-medium text-amber-300">
          Awaiting your decision
        </span>
      </div>
      <p className="mb-4 text-xs text-muted-foreground">
        {script.scenes.length} scenes · ~{Math.round(script.total_estimated_seconds)}s · written by{" "}
        {script.model}. The workflow is paused until you decide.
      </p>

      {warnings.length > 0 && (
        <div className="mb-4 space-y-1 rounded-lg border border-amber-500/20 bg-amber-500/5 p-3">
          {warnings.map((w) => (
            <p key={w.message} className="flex items-start gap-2 text-xs text-amber-200">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" /> {w.message}
            </p>
          ))}
        </div>
      )}

      <ol className="mb-4 max-h-72 space-y-2 overflow-y-auto pr-1">
        {script.scenes.map((scene) => (
          <li key={scene.index} className="rounded-lg border border-border bg-muted/60 p-3">
            <div className="mb-1 flex justify-between text-xs">
              <span className="font-medium text-amber-400">Scene {scene.index + 1}</span>
              <span className="text-muted-foreground">~{scene.estimated_seconds.toFixed(1)}s</span>
            </div>
            <p className="text-sm text-foreground">{scene.narration}</p>
            <p className="mt-1 text-xs italic text-muted-foreground">{scene.visual_description}</p>
          </li>
        ))}
      </ol>

      <textarea
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        placeholder="Optional note for the record"
        rows={2}
        className="mb-3 w-full resize-none rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/40"
      />

      <div className="flex gap-3">
        <button
          onClick={() => decide.mutate(true)}
          disabled={decide.isPending}
          className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-green-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-green-700 disabled:opacity-50"
        >
          {decide.isPending && decide.variables ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <CheckCircle2 className="h-4 w-4" />
          )}
          Approve
        </button>
        <button
          onClick={() => decide.mutate(false)}
          disabled={decide.isPending}
          className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-red-500/40 px-4 py-2.5 text-sm font-medium text-red-300 transition-colors hover:bg-red-500/10 disabled:opacity-50"
        >
          {decide.isPending && decide.variables === false ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <XCircle className="h-4 w-4" />
          )}
          Reject
        </button>
      </div>

      {decide.isError && (
        <p className="mt-3 text-xs text-red-400" role="alert">
          {decide.error instanceof Error ? decide.error.message : "Failed to record decision."}
        </p>
      )}
    </div>
  );
}
