// Mirrors packages/contracts/shotspec.py, world_state.py and shot_api.py.

export type ShotSpecStatus =
  | "DRAFT"
  | "PLANNED"
  | "BLENDER_READY"
  | "GENERATING"
  | "QA_PENDING"
  | "PASSED"
  | "FAILED"
  | "REPAIRING"
  | "APPROVED";

export type ShotType = "wide" | "medium" | "close_up" | "insert";

export interface CharacterState {
  clothing: string | null;
  position: string | null;
  emotion: string | null;
  props: string[];
}

export interface ObjectState {
  state: string | null;
  position: string | null;
}

export interface EnvironmentState {
  location: string | null;
  time_of_day: string | null;
  weather: string | null;
}

export interface WorldState {
  project_id: string;
  version: number;
  characters: Record<string, CharacterState>;
  objects: Record<string, ObjectState>;
  environment: EnvironmentState;
  style: string | null;
}

export interface WorldStateResponse {
  project_id: string;
  version: number;
  state: WorldState;
  source_shot_id: string | null;
}

export interface Camera {
  shot_type: ShotType;
  angle: string;
  movement: string;
  lens_mm: number;
}

export interface Lighting {
  key: string;
  mood: string;
}

export interface StateChange {
  entity_type: "character" | "object" | "environment";
  entity: string | null;
  field: string;
  value: unknown;
  reason: string;
}

export interface ShotContent {
  beat_label: string;
  start_time: number;
  end_time: number;
  narration: string;
  scene_index: number | null;
  description: string;
  camera: Camera;
  lighting: Lighting;
  style: string | null;
  characters: Record<string, CharacterState>;
  objects: Record<string, ObjectState>;
  environment: EnvironmentState;
  state_changes: StateChange[];
  scene_change: boolean;
  requires_physics: boolean;
  /** exact prompt written in the Studio (replaces the compiled one) */
  prompt?: string | null;
  /** regenerations of this shot with nothing else changed */
  take?: number;
}

/** POST /shots/{id}/edit body: only these fields can be changed in the Studio. */
export interface ShotEdit {
  description?: string;
  prompt?: string | null;
  camera?: Partial<{ shot_type: string; angle: string; movement: string; lens_mm: number }>;
  environment?: Partial<{ location: string; time_of_day: string; weather: string }>;
  lighting?: Partial<{ key: string; mood: string }>;
  new_take?: boolean;
}

/** GET /shots/{id}/regenerate */
export interface RegenStatus {
  state: "idle" | "running" | "done" | "error";
  step?: "saved" | "physics" | "visuals" | "final" | "done";
  version?: number;
  error?: string | null;
}

export interface ContinuityViolation {
  code: string;
  severity: "error" | "warning";
  entity: string | null;
  field: string | null;
  expected: unknown;
  actual: unknown;
  message: string;
}

export interface ContinuityReport {
  passed: boolean;
  world_state_version: number;
  violations: ContinuityViolation[];
}

export interface VideoCandidate {
  index: number;
  asset_id: string;
  thumbnail_asset_id: string;
  /** The AI/motion clip, when the project's video provider made one (candidate 1 only). */
  render_asset_id?: string | null;
  seed: number;
  params_hash: string;
}

export interface VideoGeneration {
  video_generation_id: string;
  idempotency_key: string;
  status: string;
  cached: boolean;
  candidates: VideoCandidate[];
}

export interface ShotVersion {
  shotspec_id: string;
  version: number;
  parent_version: number | null;
  status: ShotSpecStatus | string;
  content: ShotContent;
  content_hash: string;
  created_by: string;
  created_at: string;
  continuity: ContinuityReport | null;
  physics_proxy_asset_id: string | null;
  video_generation_asset_id: string | null;
  video_generation: VideoGeneration | null;
}

export interface Shot {
  id: string;
  project_id: string;
  shot_index: number;
  status: ShotSpecStatus | string;
  current_version: number;
  beat_label: string;
  start_time: number;
  end_time: number;
  created_at: string;
  updated_at: string;
  spec: ShotVersion;
}

export interface ShotAsset {
  asset_id: string;
  asset_type: string;
  content_hash: string;
  parent_asset: string | null;
  metadata: Record<string, unknown>;
}

export interface ShotDetail extends Shot {
  versions: ShotVersion[];
  physics_assets: ShotAsset[];
}
