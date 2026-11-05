export type HumanGateType = "script_approval" | "shot_approval" | "final_approval";

export type HumanGateStatus = "pending" | "approved" | "rejected";

export interface ScriptScene {
  index: number;
  narration: string;
  visual_description: string;
  estimated_seconds: number;
}

export interface ScriptValidationIssue {
  severity: "error" | "warning";
  message: string;
}

export interface ScriptPayload {
  project_id: string;
  topic: string;
  scenes: ScriptScene[];
  total_estimated_seconds: number;
  model: string;
  validation_issues?: ScriptValidationIssue[];
}

export interface HumanGate {
  id: string;
  project_id: string;
  gate_type: HumanGateType;
  status: HumanGateStatus;
  // Typed loosely since payload shape depends on gate_type; narrow with
  // `payload as ScriptPayload` when gate_type === "script_approval".
  payload: ScriptPayload | Record<string, unknown>;
  comment: string | null;
  decided_by: string | null;
  created_at: string;
  decided_at: string | null;
}

export interface HumanGateDecisionInput {
  decided_by: string;
  comment?: string;
}
