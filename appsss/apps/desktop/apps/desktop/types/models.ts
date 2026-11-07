// Mirrors GET /api/v1/models (agentic_core/models/catalog.py's status()): the AVOS model catalog with what is ready.

export type ModelTask = "image" | "video" | "avatar" | "control" | "llm";

export interface CatalogModel {
  id: string;
  name: string;
  maker: string;
  task: ModelTask;
  rank: number;
  role: string;
  best_for: string;
  why: string;
  license: string;
  commercial: "yes" | "conditional" | "unknown";
  /** added on the Settings page */
  custom?: boolean;
  kind?: "fal" | "replicate" | "comfyui" | "openai";
  license_note?: string;
  license_url: string;
  inputs: string[];
  size: string;
  fal?: { endpoint: string; audio_endpoint?: string; price: string };
  comfyui?: { workflow: string; template: string };
  cloudflare?: { model: string };
  selfhost?: { repo: string };
  used_in: string[];
  /** backend -> null when usable, else what's missing */
  backends: Record<string, string | null>;
  backend: string | null;
  ready: boolean;
  /** what's missing to run it (null when ready) */
  missing: string | null;
  workflow: string | null;
  /** has a verified file list: the Models page shows a Download button */
  download?: boolean;
  /** Model Fabric routing data: quality, VRAM per precision, speed, strengths */
  fabric?: { quality: number; vram_gb: Record<string, number>; min_vram_gb?: number; strengths?: string[]; adapters?: string[] };
}

export interface ModelsStatus {
  tasks: Record<ModelTask, { label: string; auto: string }>;
  backends: Record<string, { label: string; needs: string; how: string }>;
  models: CatalogModel[];
  settings: { fal: boolean; comfyui: string | null; workflowDir: string; modelBackend: string; gpuWorkers?: number; gpuWorkersOnline?: number };
}

// ---------- Settings page (GET /api/v1/settings) ----------
export interface SettingKey {
  name: string;
  label: string;
  group: string;
  uses: string;
  url: string;
  set: boolean;
  source: "settings" | ".env" | null;
  value: string;
  secret: boolean;
}
export interface CustomModelDef {
  id: string;
  name: string;
  task: "image" | "video" | "avatar" | "llm";
  kind: "fal" | "replicate" | "comfyui" | "openai";
  endpoint?: string;
  base_url?: string;
  model?: string;
  key_env?: string;
  inputs?: Record<string, unknown>;
  output?: string;
  workflow?: string;
  license?: string;
  notes?: string;
}
export interface AppSettings {
  file: string;
  keys: SettingKey[];
  gpu: { comfyui_url: string; model_backend: "auto" | "gpu" | "fal" | "comfyui" };
  models: CustomModelDef[];
  tasks: string[];
  kinds: string[];
  placeholders: Record<string, string>;
  defaultInputs: Record<string, Record<string, unknown>>;
  workflowDir: string;
  workflows: string[];
  uploaded?: { model: string; file: string; placeholders: string[] };
}
