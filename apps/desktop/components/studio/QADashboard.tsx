"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  AlertOctagon,
  CheckCircle2,
  ClipboardCheck,
  FlaskConical,
  Loader2,
  ShieldAlert,
  ShieldCheck,
  Wrench,
  XCircle,
} from "lucide-react";
import { queryKeys, useShotQA } from "@/hooks/queries";
import { qaApi, shotsApi, ApiError } from "@/lib/api";
import type { RepairRung, Shot } from "@/types";

// Week 3 Day 14 (AVOS-18 s6.3): QA verdict + repair-ladder status for the
// selected shot. Reads GET /shots/{id}/qa via useShotQA(), which SSE's
// QA_PASSED/QA_FAILED/REPAIR_STARTED/REPAIR_ESCALATED/SHOT_APPROVED
// events keep fresh with no polling (see hooks/useLiveProject.ts) - the
// same live-cache pattern as GenerationMonitor.
//
// Week 3 Day 15 adds two things: a "Force fail (test)" toggle, so the
// integration checkpoint can drive a real FAIL (and the repair ladder
// behind it) through this exact UI instead of only a backend fixture -
// the mock generator and the geometry check agree by construction, so
// this is the only honest way to get a FAIL live; and the stubbed final
// gate's "Approve" action once a shot has a genuine PASS.

const RUNG_ORDER: RepairRung[] = ["MICRO", "MACRO", "HUMAN_REQUIRED"];

const RUNG_LABEL: Record<RepairRung, string> = {
  MICRO: "Micro",
  MACRO: "Macro",
  HUMAN_REQUIRED: "Human",
};

const DIMENSION_LABEL: Record<string, string> = {
  visual: "Visual",
  temporal: "Temporal",
  geometry: "Geometry",
  identity: "Identity",
  audio: "Audio",
  prompt_adherence: "Prompt adherence",
};

/** Real dimensions (AVOS-03 v1.1 s15) vs this week's TODO placeholders -
 * mirrors PLACEHOLDER_DIMENSIONS in pipelines/qa/committee.py. */
const REAL_DIMENSIONS = new Set(["visual", "geometry"]);

function RungBadge({ rung, attempt }: { rung: RepairRung; attempt: number }) {
  const color =
    rung === "HUMAN_REQUIRED"
      ? "border-red-500/40 bg-red-500/10 text-red-300"
      : rung === "MACRO"
        ? "border-orange-500/40 bg-orange-500/10 text-orange-300"
        : "border-amber-500/40 bg-amber-500/10 text-amber-300";
  return (
    <span
      data-testid="repair-rung"
      data-rung={rung}
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium ${color}`}
    >
      {rung === "HUMAN_REQUIRED" ? <ShieldAlert className="h-3 w-3" /> : <Wrench className="h-3 w-3" />}
      Attempt {attempt} · {RUNG_LABEL[rung]}
      {rung === "HUMAN_REQUIRED" ? " required" : ""}
    </span>
  );
}

/** Micro -> Macro -> Human ladder (AVOS-03 v1.1 s14), rendered as a
 * 3-step tracker so the current rung is visible at a glance. */
function RepairLadder({ rung }: { rung: RepairRung }) {
  const currentIndex = RUNG_ORDER.indexOf(rung);
  return (
    <div className="flex items-center gap-1" data-testid="repair-ladder">
      {RUNG_ORDER.map((r, i) => (
        <div key={r} className="flex items-center gap-1">
          <span
            className={`rounded-md px-1.5 py-0.5 text-[10px] font-medium ${
              i < currentIndex
                ? "bg-muted text-muted-foreground"
                : i === currentIndex
                  ? r === "HUMAN_REQUIRED"
                    ? "bg-red-500/20 text-red-300"
                    : "bg-amber-500/20 text-amber-300"
                  : "bg-muted/60 text-muted-foreground/60"
            }`}
          >
            {RUNG_LABEL[r]}
          </span>
          {i < RUNG_ORDER.length - 1 && <span className="text-muted-foreground/40">→</span>}
        </div>
      ))}
    </div>
  );
}

export function QADashboard({ shot }: { shot: Shot }) {
  const queryClient = useQueryClient();
  const { data: qaState, isLoading } = useShotQA(shot.id);
  const [forceFail, setForceFail] = useState(false);

  const invalidateShot = () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.qa(shot.id) });
    queryClient.invalidateQueries({ queryKey: queryKeys.shot(shot.id) });
  };
  const runQA = useMutation({
    mutationFn: () => qaApi.runCommittee(shot.id, forceFail),
    onSuccess: invalidateShot,
  });
  const repair = useMutation({
    mutationFn: () => qaApi.repair(shot.id),
    onSuccess: invalidateShot,
  });
  const approve = useMutation({
    mutationFn: () => shotsApi.approve(shot.id),
    onSuccess: invalidateShot,
  });

  const hasCandidates = (shot.spec.video_generation?.candidates.length ?? 0) > 0;
  const latest = qaState?.latest_result ?? null;
  const repairs = qaState?.repairs ?? [];
  const lastRepair = repairs[repairs.length - 1] ?? null;
  // The next attempt's rung is derived the same way the backend does
  // (agents/repair/classifier.py: rung_for_attempt) - attempt 1&2 stay
  // bounded (Micro/Macro), attempt 3+ always escalates to Human.
  const nextAttempt = repairs.length + 1;
  const nextRung: RepairRung = nextAttempt >= 3 ? "HUMAN_REQUIRED" : nextAttempt === 2 ? "MACRO" : "MICRO";
  const canRepair = latest?.status === "FAIL" && lastRepair?.rung !== "HUMAN_REQUIRED";

  return (
    <section className="border-t border-border p-4" data-testid="qa-dashboard">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          <ClipboardCheck className="h-3.5 w-3.5" /> QA Committee
        </h2>
        <div className="flex items-center gap-2">
          <label
            className="flex items-center gap-1.5 text-[11px] text-muted-foreground"
            title="Still runs the real evaluation, then deliberately overrides the verdict to FAIL - for proving the repair ladder live (Day 15 integration checkpoint)."
          >
            <input
              type="checkbox"
              checked={forceFail}
              onChange={(e) => setForceFail(e.target.checked)}
              data-testid="force-fail-toggle"
              className="h-3 w-3 accent-red-500"
            />
            <FlaskConical className="h-3 w-3" /> Force fail (test)
          </label>
          <button
            onClick={() => runQA.mutate()}
            disabled={runQA.isPending || !hasCandidates}
            data-testid="run-qa"
            title={hasCandidates ? undefined : "Generate candidates before running QA."}
            className={`flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-[11px] font-medium disabled:opacity-40 ${
              forceFail
                ? "border-red-500/50 text-red-300 hover:bg-red-500/10"
                : "border-border text-foreground hover:bg-accent"
            }`}
          >
            {runQA.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : <ClipboardCheck className="h-3 w-3" />}
            {runQA.isPending ? "Scoring…" : forceFail ? "Run QA (forced FAIL)" : "Run QA"}
          </button>
        </div>
      </div>

      {isLoading && (
        <p className="text-xs text-muted-foreground">
          <Loader2 className="mr-1.5 inline h-3 w-3 animate-spin" /> Loading QA state…
        </p>
      )}

      {!isLoading && !latest && (
        <p className="text-xs text-muted-foreground" data-testid="qa-empty">
          No QA result yet for this shot.
        </p>
      )}

      {latest && (
        <div className="rounded-lg border border-border bg-card/40 p-3" data-testid="qa-result">
          <div className="flex items-center justify-between gap-3">
            <span
              data-testid="qa-verdict"
              data-verdict={latest.status}
              className={`flex items-center gap-1.5 text-sm font-semibold ${
                latest.status === "PASS" ? "text-green-400" : "text-red-400"
              }`}
            >
              {latest.status === "PASS" ? (
                <CheckCircle2 className="h-4 w-4" />
              ) : (
                <XCircle className="h-4 w-4" />
              )}
              {latest.status === "PASS" ? "Passed" : "Failed"}
              {latest.evidence.forced === true && (
                <span
                  data-testid="qa-forced-badge"
                  className="rounded-full border border-red-500/40 bg-red-500/10 px-1.5 py-0.5 text-[10px] font-normal text-red-300"
                  title="This verdict was deliberately forced for the Day 15 integration checkpoint, not a real failure."
                >
                  forced
                </span>
              )}
            </span>
            <span className="text-xs text-muted-foreground">
              score {latest.score.toFixed(2)}
              {latest.confidence !== null && ` · confidence ${latest.confidence.toFixed(2)}`}
            </span>
          </div>

          <div className="mt-3 grid grid-cols-2 gap-2" data-testid="qa-dimensions">
            {latest.dimensions.map((d) => (
              <div
                key={d.dimension}
                data-testid="qa-dimension"
                data-dimension={d.dimension}
                className="flex items-center justify-between rounded-md border border-border bg-muted/60 px-2 py-1 text-[11px]"
              >
                <span className="text-foreground/90">
                  {DIMENSION_LABEL[d.dimension] ?? d.dimension}
                  {!REAL_DIMENSIONS.has(d.dimension) && (
                    <span className="ml-1 text-muted-foreground/60" title="Placeholder this week - not yet a real check.">
                      (TODO)
                    </span>
                  )}
                </span>
                <span className={d.score >= 0.6 ? "text-green-400" : "text-red-400"}>{d.score.toFixed(2)}</span>
              </div>
            ))}
          </div>

          {/* Repair affordance: attempt number + current rung, live via
              SSE (REPAIR_STARTED/REPAIR_ESCALATED). Only offered on a
              FAIL, and hidden once the ladder has already escalated to
              HUMAN_REQUIRED - a human, not another API call, takes it
              from there (AVOS-03 v1.1 s14.6). */}
          {latest.status === "FAIL" && (
            <div className="mt-3 border-t border-border pt-3" data-testid="repair-panel">
              <div className="flex items-center justify-between gap-3">
                <div className="flex flex-col gap-1.5">
                  {lastRepair ? (
                    <RungBadge rung={lastRepair.rung} attempt={lastRepair.attempt} />
                  ) : (
                    <span className="text-[11px] text-muted-foreground">No repair attempted yet.</span>
                  )}
                  <RepairLadder rung={lastRepair?.rung ?? nextRung} />
                </div>
                {canRepair ? (
                  <button
                    onClick={() => repair.mutate()}
                    disabled={repair.isPending}
                    data-testid="repair-shot"
                    className="flex items-center gap-1.5 rounded-md bg-gradient-to-r from-orange-500 to-red-500 px-2.5 py-1 text-[11px] font-medium text-white disabled:opacity-50"
                  >
                    {repair.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : <Wrench className="h-3 w-3" />}
                    {repair.isPending ? "Repairing…" : `Repair (attempt ${nextAttempt})`}
                  </button>
                ) : (
                  lastRepair?.rung === "HUMAN_REQUIRED" && (
                    <span className="flex items-center gap-1 text-[11px] text-red-400">
                      <AlertOctagon className="h-3.5 w-3.5" /> Escalated to human review
                    </span>
                  )
                )}
              </div>

              {repairs.length > 0 && (
                <ul className="mt-2 space-y-1 text-[11px] text-muted-foreground" data-testid="repair-history">
                  {repairs.map((r) => (
                    <li key={r.id} className="flex justify-between">
                      <span>
                        Attempt {r.attempt} · {RUNG_LABEL[r.rung]} · {r.failure_type}
                      </span>
                      <span>{r.applied_at ? "applied" : "pending"}</span>
                    </li>
                  ))}
                </ul>
              )}

              {repair.isError && (
                <p className="mt-2 text-[11px] text-red-400">
                  {repair.error instanceof ApiError ? repair.error.message : "Repair failed."}
                </p>
              )}
            </div>
          )}

          {/* The stubbed final gate (Week 3 Day 15): a human sign-off on
              a genuine PASS. Final Assembly/FFmpeg doesn't exist yet, so
              this is the whole final stage for now - approving just
              records the decision (SHOT_APPROVED, audited) and moves the
              shot to APPROVED, live via SSE. */}
          {latest.status === "PASS" && (
            <div className="mt-3 border-t border-border pt-3" data-testid="approval-panel">
              {shot.status === "APPROVED" ? (
                <span className="flex items-center gap-1.5 text-[11px] text-green-400">
                  <ShieldCheck className="h-3.5 w-3.5" /> Approved at the final gate.
                </span>
              ) : (
                <div className="flex items-center justify-between gap-3">
                  <span className="text-[11px] text-muted-foreground">
                    Final gate (stubbed ahead of Final Assembly): a human sign-off.
                  </span>
                  <button
                    onClick={() => approve.mutate()}
                    disabled={approve.isPending}
                    data-testid="approve-shot"
                    className="flex items-center gap-1.5 rounded-md bg-gradient-to-r from-green-500 to-emerald-600 px-2.5 py-1 text-[11px] font-medium text-white disabled:opacity-50"
                  >
                    {approve.isPending ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : (
                      <ShieldCheck className="h-3 w-3" />
                    )}
                    {approve.isPending ? "Approving…" : "Approve"}
                  </button>
                </div>
              )}
              {approve.isError && (
                <p className="mt-2 text-[11px] text-red-400">
                  {approve.error instanceof ApiError ? approve.error.message : "Approval failed."}
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {runQA.isError && (
        <p className="mt-2 text-[11px] text-red-400">
          {runQA.error instanceof ApiError ? runQA.error.message : "QA run failed."}
        </p>
      )}
    </section>
  );
}
