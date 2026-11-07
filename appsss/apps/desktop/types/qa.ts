export type QADimension =
  | "visual"
  | "physics"
  | "temporal"
  | "fact"
  | "brand"
  | "continuity"
  | "audio_sync"
  | "overall";

export interface QAScore {
  dimension: QADimension;
  score: number; // 0.0 to 1.0
  threshold: number;
  passed: boolean;
  feedback?: string;
}

export interface QAReport {
  report_id: string;
  shot_id?: string;
  project_id: string;
  scores: QAScore[];
  overall_score: number;
  passed: boolean;
  created_at: string;
}