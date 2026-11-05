export type RepairType =
  | "regenerate_shot"
  | "inpaint_region"
  | "adjust_prompt"
  | "rerender_audio"
  | "fix_continuity"
  | "adjust_physics";

export type RepairStatus =
  | "diagnosing"
  | "planning"
  | "executing"
  | "completed"
  | "failed";

export interface RepairAction {
  type: RepairType;
  target_asset_id?: string;
  target_shot_id?: string;
  params: Record<string, unknown>;
}

export interface RepairJob {
  repair_id: string;
  project_id: string;
  shot_id: string;
  qa_report_id: string;
  status: RepairStatus;
  diagnosis: string;
  actions: RepairAction[];
  created_at: string;
  completed_at?: string;
}