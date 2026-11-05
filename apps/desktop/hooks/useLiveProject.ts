"use client";

import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { subscribeToEvents } from "@/lib/events";
import { queryKeys } from "@/hooks/queries";
import type { AVOSEvent, DecisionTraceEntry } from "@/types";

export interface LiveNotice {
  id: string;
  kind: "info" | "warning";
  text: string;
}

/**
 * One SSE subscription per page. Server events update the React Query
 * cache directly, so every component re-renders from live data with no
 * polling loop (Week 2: "live updates via SSE instead of polling").
 *
 * - AGENT_ACTION_RECORDED appends the trace entry (no refetch needed)
 * - JOB/PROJECT/GATE events invalidate the affected queries
 * - BUDGET_* events surface as notices
 *
 * Pass no projectId to follow every project (Dashboard).
 */
export function useLiveProject(projectId?: string) {
  const queryClient = useQueryClient();
  const [connected, setConnected] = useState(false);
  const [notices, setNotices] = useState<LiveNotice[]>([]);

  useEffect(() => {
    const invalidate = (key: readonly unknown[]) =>
      queryClient.invalidateQueries({ queryKey: key });

    const handle = (event: AVOSEvent) => {
      const pid = event.project_id ?? projectId ?? "";

      switch (event.event_type) {
        case "AGENT_ACTION_RECORDED": {
          const entry = event.payload as unknown as DecisionTraceEntry;
          queryClient.setQueryData<DecisionTraceEntry[]>(queryKeys.trace(pid), (prev) =>
            prev && !prev.some((e) => e.id === entry.id) ? [...prev, entry] : prev
          );
          invalidate(queryKeys.project(pid)); // budget_spent changed
          break;
        }
        case "JOB_STATUS_CHANGED": {
          const jobId = String((event.payload as { job_id?: string }).job_id ?? "");
          invalidate(queryKeys.jobs(pid));
          if (jobId) invalidate(queryKeys.job(jobId));
          break;
        }
        case "HUMAN_GATE_OPENED":
        case "HUMAN_GATE_DECIDED":
        case "SCRIPT_GENERATED":
        case "SCRIPT_APPROVED":
          invalidate(queryKeys.gates(pid));
          break;
        case "AUDIO_GENERATED":
          invalidate(queryKeys.jobs(pid));
          break;
        case "SHOT_CREATED":
        case "CONTINUITY_CHECKED":
        case "BLENDER_RENDERED":
        case "VIDEO_GENERATED": {
          invalidate(queryKeys.shots(pid));
          const shotId = (event.payload as { shot_id?: string }).shot_id;
          if (shotId) invalidate(queryKeys.shot(shotId));
          break;
        }
        case "QA_PASSED":
        case "QA_FAILED":
        case "REPAIR_STARTED":
        case "REPAIR_ESCALATED":
        case "SHOT_APPROVED": {
          // QA committee verdicts, repair-ladder progress, and the
          // stubbed final gate's approval all live under
          // queryKeys.qa(shotId) — QADashboard.tsx reads that key via
          // useShotQA(), so this is what makes the dashboard (verdict,
          // rung, and the Approve affordance) update live with no
          // polling and no reload.
          const shotId = (event.payload as { shot_id?: string }).shot_id;
          if (shotId) {
            invalidate(queryKeys.qa(shotId));
            invalidate(queryKeys.shot(shotId));
          }
          invalidate(queryKeys.shots(pid));
          break;
        }
        case "VIDEO_ASSEMBLED":
          // The final MP4 is ready; it shows up in the job's output.
          invalidate(queryKeys.jobs(pid));
          invalidate(queryKeys.project(pid));
          break;
        case "GPU_JOB_QUEUED":
        case "GPU_JOB_STARTED":
        case "GPU_JOB_PROGRESS":
        case "GPU_JOB_COMPLETED":
        case "GPU_JOB_FAILED":
          invalidate(queryKeys.gpuJobs(pid || undefined));
          invalidate(queryKeys.gpuJobs(undefined));
          break;
        case "BUDGET_WARNING":
        case "BUDGET_EXCEEDED": {
          const p = event.payload as { budget_spent?: number; budget_limit?: number };
          setNotices((prev) => [
            ...prev.slice(-4),
            {
              id: event.event_id,
              kind: "warning",
              text:
                event.event_type === "BUDGET_EXCEEDED"
                  ? `Budget exceeded: $${p.budget_spent?.toFixed(2)} of $${p.budget_limit?.toFixed(2)}`
                  : `Budget warning: $${p.budget_spent?.toFixed(2)} of $${p.budget_limit?.toFixed(2)} used`,
            },
          ]);
          break;
        }
      }

      if (event.event_type === "PROJECT_CREATED" || event.event_type === "PROJECT_STATUS_CHANGED") {
        invalidate(queryKeys.projects);
        invalidate(queryKeys.project(pid));
      }
      if (event.event_type === "JOB_STATUS_CHANGED") {
        invalidate(queryKeys.project(pid));
      }
    };

    const unsubscribe = subscribeToEvents(handle, {
      projectId,
      onOpen: () => setConnected(true),
      onError: () => setConnected(false),
    });

    return () => {
      unsubscribe();
      setConnected(false);
    };
  }, [projectId, queryClient]);

  return { connected, notices };
}
