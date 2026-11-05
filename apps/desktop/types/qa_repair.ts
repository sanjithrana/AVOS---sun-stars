// Mirrors packages/contracts/qa_repair_api.py (Week 3 Day 14).

export type QAVerdict = "PASS" | "FAIL";
export type RepairRung = "MICRO" | "MACRO" | "HUMAN_REQUIRED";

export interface QADimensionScore {
  dimension: string;
  score: number;
  confidence: number | null;
  diagnostics: Record<string, unknown>;
  issues: Record<string, unknown>[];
}

export interface QAResultRecord {
  id: string;
  shot_id: string;
  status: QAVerdict;
  score: number;
  confidence: number | null;
  evidence: Record<string, unknown>;
  dimensions: QADimensionScore[];
  evaluated_at: string;
}

export interface RepairPlanRecord {
  id: string;
  shot_id: string;
  attempt: number;
  rung: RepairRung;
  failure_type: string;
  target_stage: string;
  changes: Record<string, unknown>;
  preserve: string[];
  applied_at: string | null;
  resulting_asset_id: string | null;
}

export interface ShotQAState {
  shot_id: string;
  latest_result: QAResultRecord | null;
  repairs: RepairPlanRecord[];
}
