// Mirrors packages/contracts/event.py (Event envelope + EventType).

export type EventType =
  | "PROJECT_CREATED"
  | "SCRIPT_GENERATED"
  | "SCRIPT_APPROVED"
  | "AUDIO_GENERATED"
  | "HUMAN_GATE_OPENED"
  | "HUMAN_GATE_DECIDED"
  | "AGENT_ACTION_RECORDED"
  | "JOB_STATUS_CHANGED"
  | "PROJECT_STATUS_CHANGED"
  | "BUDGET_WARNING"
  | "BUDGET_EXCEEDED"
  | "SHOT_CREATED"
  | "CONTINUITY_CHECKED"
  | "BLENDER_RENDERED"
  | "VIDEO_GENERATED"
  | "QA_PASSED"
  | "QA_FAILED"
  | "REPAIR_STARTED"
  | "REPAIR_ESCALATED"
  | "SHOT_APPROVED"
  | "VIDEO_ASSEMBLED"
  | "GPU_JOB_QUEUED"
  | "GPU_JOB_STARTED"
  | "GPU_JOB_PROGRESS"
  | "GPU_JOB_COMPLETED"
  | "GPU_JOB_FAILED";

/** Every event type the UI listens for over SSE. */
export const LIVE_EVENT_TYPES: ReadonlyArray<EventType> = [
  "PROJECT_CREATED",
  "SCRIPT_GENERATED",
  "SCRIPT_APPROVED",
  "AUDIO_GENERATED",
  "HUMAN_GATE_OPENED",
  "HUMAN_GATE_DECIDED",
  "AGENT_ACTION_RECORDED",
  "JOB_STATUS_CHANGED",
  "PROJECT_STATUS_CHANGED",
  "BUDGET_WARNING",
  "BUDGET_EXCEEDED",
  "SHOT_CREATED",
  "CONTINUITY_CHECKED",
  "BLENDER_RENDERED",
  "VIDEO_GENERATED",
  "QA_PASSED",
  "QA_FAILED",
  "REPAIR_STARTED",
  "REPAIR_ESCALATED",
  "SHOT_APPROVED",
  "VIDEO_ASSEMBLED",
  "GPU_JOB_QUEUED",
  "GPU_JOB_STARTED",
  "GPU_JOB_PROGRESS",
  "GPU_JOB_COMPLETED",
  "GPU_JOB_FAILED",
];

export interface AVOSEvent<T = Record<string, unknown>> {
  event_id: string;
  event_type: EventType | string;
  timestamp: string;
  organization_id: string;
  project_id: string | null;
  correlation_id: string;
  causation_id: string | null;
  payload: T;
}
