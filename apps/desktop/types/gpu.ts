// Mirrors /api/v1/gpu (api/src/routes/gpu.py) and the GPU worker's GET /status (apps/gpu_worker/worker/app.py).

export type Preference = "quality" | "balanced" | "speed" | "cost";

export interface GenerationLimits {
  preference: Preference;
  max_cost_per_shot: number | null;
  max_seconds_per_shot: number | null;
  max_attempts: number;
  quality_threshold: number;
  allow_hosted: boolean;
  auto_qa: boolean;
  review_shots: boolean;
  preferred_model?: string | null;
  fallback_model?: string | null;
}

export interface WorkerGpu {
  name?: string;
  vram_gb?: number;
  free_vram_gb?: number;
  used_vram_gb?: number;
  temperature_c?: number | null;
  utilization?: number | null;
  compute_capability?: string;
  driver?: string;
  cuda?: string;
  fake?: boolean;
}

export interface WorkerAdapter {
  ready: boolean;
  why: string | null;
  models: string[];
  precisions: string[];
  attention: string;
  offload?: boolean;
}

export interface LoadedModel {
  model: string;
  adapter: string;
  precision: string;
  vram_gb: number;
  last_used: number;
  uses: number;
  pinned: boolean;
}

export interface WorkerJob {
  id: string;
  status: string;
  progress: number;
  step: string;
  model: string;
  adapter: string;
  precision: string;
}

export interface QueuedJob { id: string; model: string; task: string; priority: number; tag: string | null; precision: string }

export interface GpuWorker {
  id: string;
  name: string;
  url: string;
  online: boolean;
  error: string | null;
  enabled: boolean;
  cost_per_hour: number;
  cost_per_hour_setting?: number | null;
  gpu?: WorkerGpu | Record<string, never>;
  supports?: Record<string, boolean>;
  adapters?: Record<string, WorkerAdapter>;
  loaded_models?: LoadedModel[];
  queue_depth?: number;
  running?: (WorkerJob & { tag?: string | null; priority?: number }) | null;
  queue?: QueuedJob[];
  models_dir?: string;
  status?: string;
  avg_job_seconds?: number | null;
  worker_version?: string;
  summary?: string;
}

export interface GpuJobRow {
  id: string;
  project_id: string | null;
  shot_id: string | null;
  version: number | null;
  task: "image" | "video" | "avatar" | string;
  model: string;
  backend: string;
  worker_id: string | null;
  worker_name: string | null;
  gpu: string | null;
  adapter: string | null;
  precision: string | null;
  attention: string | null;
  offload: boolean;
  warm: boolean;
  where: string;
  units: number;
  status: "queued" | "running" | "done" | "error" | string;
  progress: number;
  step: string | null;
  est_seconds: number | null;
  est_cost: number | null;
  score: number | null;
  reasons: string[] | null;
  gpu_seconds: number | null;
  wall_seconds: number | null;
  cost_usd: number | null;
  qa_score: number | null;
  error: string | null;
  created_at: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface GpuOverview {
  workers: GpuWorker[];
  limits: GenerationLimits;
  preferences: Preference[];
  totals: { runs: number; done: number; failed: number; gpu_seconds: number; cost_usd: number };
  jobs: GpuJobRow[];
  modelBackend: string;
  tokenSet: boolean;
}

export interface Placement {
  model: string;
  model_name: string;
  backend: string;
  worker_id: string | null;
  worker_name: string | null;
  gpu: string | null;
  adapter: string | null;
  precision: string | null;
  attention: string | null;
  offload: boolean;
  warm: boolean;
  vram_gb: number | null;
  est_seconds: number;
  est_cost: number;
  quality: number;
  score: number;
  reasons: string[];
  where: string;
}

export interface RoutePlan {
  request: Record<string, unknown>;
  policy: GenerationLimits;
  placements: Placement[];
  rejected: { model: string; backend: string; worker?: string; adapter?: string; why: string }[];
}

export interface LearnedRow {
  model: string;
  where: string;
  runs: number;
  ok: number;
  unit_seconds: number | null;
  avg_qa: number | null;
  used_for_routing: boolean;
}

export const PREFERENCE_LABEL: Record<Preference, string> = {
  balanced: "Balanced",
  quality: "Best quality",
  speed: "Fastest",
  cost: "Cheapest",
};
