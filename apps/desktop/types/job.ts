// Mirrors packages/contracts/generation.py (GenerateResponse, JobResponse)
// and api/src/domain/jobs/models.py (JobStatus).

export type JobStatus = "queued" | "running" | "completed" | "failed" | "cancelled";

export const TERMINAL_JOB_STATUSES: ReadonlyArray<JobStatus> = [
  "completed",
  "failed",
  "cancelled",
];

export interface GenerateResponse {
  job_id: string;
  project_id: string;
  status: JobStatus;
  workflow_id: string;
}

export interface WordTimestamp {
  word: string;
  start: number;
  end: number;
}

export interface SentenceTimestamp {
  text: string;
  start: number;
  end: number;
  word_count: number;
}

export interface SemanticBeat {
  time: number;
  label: string;
}

/** Output of the generate_audio step (job.output.audio). */
export interface AudioResult {
  asset_id: string;
  content_hash: string;
  cache_hit: boolean;
  format: string;
  duration_seconds: number;
  word_count: number;
  words: WordTimestamp[];
  sentences: SentenceTimestamp[];
  beats: SemanticBeat[];
  model: string;
}

/** Output of the final render step (job.output.final_video). */
export interface FinalVideoResult {
  asset_id: string;
  duration_seconds: number;
  width: number;
  height: number;
  /** Per shot, in order: "clip" (AI video), "image" (animated still) or "card". */
  shot_sources: string[];
  video_provider: string;
  size_bytes: number;
}

export interface JobOutput {
  status?: "COMPLETED" | "REJECTED";
  gate_id?: string;
  research_notes?: string[];
  audio?: AudioResult;
  final_video?: FinalVideoResult;
  warnings?: string[];
  stage_failed?: string;
  [key: string]: unknown;
}

export interface Job {
  id: string;
  project_id: string;
  job_type: string;
  status: JobStatus;
  workflow_id: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  output: JobOutput | null;
  error_message: string | null;
}
