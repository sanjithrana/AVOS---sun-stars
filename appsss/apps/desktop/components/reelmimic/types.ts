// Shapes of the Animation Studio API (a Python port of ReelMimic's server, see STUDIO_API.md):
// job.json, the project snapshot, live events, plus the multi-provider agents info.
// Ported from reelmimic/app/shared/types.ts and reelmimic/app/web/src/types.ts.

export type AgentKind = "ollama" | "groq" | "gemini" | "openrouter" | "openai" | "anthropic" | "claude" | "codex" | "builtin" | (string & {});   // + text models added in Settings
export type Lang = "zh-TW" | "en" | "zh-CN";

export type Stage =
  | "new" | "analyzing" | "styling" | "styled" | "planning" | "replanning" | "plan_review"
  | "producing" | "critiquing" | "revising" | "needs_input" | "done" | "error";

export const ROUND_KEYS = ["castRounds", "chunkRounds", "finalRounds"] as const;
export type RoundKey = (typeof ROUND_KEYS)[number];
export type Rounds = Record<RoundKey, number>;

export interface Config extends Rounds {
  builders: number;
  maxAgentsGlobal: number;
}

export interface Reference { type: "file" | "url"; src: string }

export interface ChatMessage {
  role: "user" | "agent" | "builder" | "critic" | "system";
  text: string;
  ts: string;
  phase?: string;
  who?: string;
  shot?: string;
  time?: number;
  attachments?: string[];
  notes?: { t: number; text: string }[];
}

export type AgentEvent =
  | { type: "session"; id: string }
  | { type: "text"; text: string }
  | { type: "thinking"; text: string }
  | { type: "tool"; name: string; detail: string }
  | { type: "error"; text: string }
  | { type: "done"; ok: boolean; text: string; cost?: number | null };

export type TurnMarker = { type: "turn"; state: "start" | "end"; phase: string; ok?: boolean };
export type LogEntry = (AgentEvent | TurnMarker) & { who?: string };
export type LogEvent = LogEntry & { ts: string };

export interface NeedRequest { issue: string; kind?: string; why?: string; input?: string; [k: string]: unknown }
export interface Need extends NeedRequest { from: string; at: string }

export type ChunkState =
  | "queued" | "building" | "waiting_cast" | "built" | "reviewing" | "fixing" | "shared_fix"
  | "needs_user" | "passed" | "failed" | "error";

export interface ChunkProgress {
  shots?: string[];
  state: ChunkState;
  round: number;
  fixFirst?: boolean;
  open?: number;
  acceptedByUser?: boolean;
}

export type CastCharState = "queued" | "reviewing" | "fixing" | "waiting_shared" | "needs_user" | "passed" | "failed" | "error";
export interface CastCharProgress { state: CastCharState; round: number; issues?: number }

export interface CastProgress {
  round: number;
  pass: boolean;
  state?: "reviewing" | "fixing" | "passed" | "failed";
  mode?: "parallel";
  lineup?: boolean;
  chars?: Record<string, CastCharProgress>;
  acceptedByUser?: boolean;
}

export interface Pipeline {
  phase?: "setup" | "cast" | "shots" | "assemble" | "final";
  cast?: CastProgress;
  chunks?: Record<string, ChunkProgress>;
  final?: { round: number };
}

export interface EngineSnapshot { engine: string; frozenAt: string; path: string }

export interface Job {
  id: string;
  title: string;
  agent: AgentKind;
  lang: Lang;
  reference: Reference;
  settings: Partial<Rounds>;
  stage: Stage;
  failed?: Stage | null;
  error?: string | null;
  sessionId: string | null;
  sessions: Record<string, string>;
  createdAt: string;
  updatedAt?: string;
  chat: ChatMessage[];
  log: LogEvent[];
  needs: Need[];
  waived: string[];
  provided?: Record<string, string[]>;
  pipeline: Pipeline;
  pendingNotes?: string[];
  retryPending?: boolean;
  approvedAt?: string;
  approvedAtPrev?: boolean;
  approvedPlanVersion?: number | string;
  engineSnapshot?: EngineSnapshot | null;
  userNote?: string | null;
  critiqueRounds?: number;
  lastCritique?: { pass: boolean; must: number; at: string };
}

export type InputKind = "lyrics" | "audio" | "image" | "text" | "other";

export interface RequiredInputSpec {
  id: string;
  kind: InputKind;
  label?: string;
  why?: string;
  file?: string;
  match?: string;
}

export interface RequiredInput extends RequiredInputSpec {
  status: "missing" | "provided" | "waived";
  files: string[];
}

export interface PlanCharacter { id: string; name?: string; file?: string; [k: string]: unknown }

export interface Plan {
  title?: string;
  version?: number | string;
  required_inputs?: RequiredInputSpec[];
  music?: { file?: string; section?: { start_s?: number; end_s?: number } };
  characters?: PlanCharacter[];
  assets?: { status?: string; [k: string]: unknown }[];
  [k: string]: unknown;
}

export interface Issue { issue: string; severity?: "blocker" | "polish" | string; fix?: string; character?: string; what?: string; [k: string]: unknown }

export interface Review {
  pass?: boolean;
  issues?: Issue[];
  needs_user?: NeedRequest[];
  [k: string]: unknown;
}

export interface ProjectSummary {
  id: string;
  title: string;
  stage: Stage;
  agent: AgentKind;
  updatedAt?: string;
  needs: number;
  thumb: string | null;
}

export interface Snapshot {
  job: Job;
  brief: string | null;
  report: Record<string, unknown> | null;
  styleMd: string | null;
  route: { engine?: string; [k: string]: unknown } | null;
  plan: Plan | null;
  storyboard: string | null;
  assetsMd: string | null;
  checks: string[];
  video: string | null;
  critique: Record<string, unknown> | null;
  cast: { sheets: string[]; review: Review | null };
  shots: string[];
  production: Record<string, unknown> | null;
  lyrics: unknown;
  requiredInputs: RequiredInput[];
  rounds: { values: Rounds; defaults: Rounds; min: number; max: number };
  inputs: string[];
  engine?: { id: string; label: string } | null;
  finish?: FinishStatus | null;
}

export type ServerEvent = { type: "job"; stage: Stage } | { type: "log"; ev: LogEvent };

export type AgentStatus = Partial<Record<AgentKind, string | null>>;

// ---------- multi-provider crews (GET /api/agents/info) ----------
export type AgentTier = "local" | "free" | "paid" | "custom";
export interface AgentInfo {
  id: AgentKind;
  custom?: boolean;
  label: string;
  tier: AgentTier;
  ready: boolean;
  detail: string;
  fix?: string;
  model?: string;
  models?: string[];
  needsKey?: boolean;
  hasKey?: boolean;
  url?: string;
  vision?: boolean;
  visionModel?: string;
}
export interface PullState { status: string; done: boolean; error?: string; pct?: number }
export type ImageModel = "free" | "best" | "z-image" | "qwen-image" | "flux-schnell" | (string & {});   // + image models added in Settings
export type FinishModel = "wan-vace" | "wan-2.2-animate" | "scail-2" | "ltx-2.3" | (string & {});    // + video models added in Settings
export interface RenderSettings { quality: "720p" | "1080p"; images: "drawn" | "ai"; imagesReady: boolean; imagesDetail: string; imageModel?: ImageModel }
/** One open model from the shared AVOS catalog (agentic_core/models/catalog.json). */
export interface OpenModel {
  id: string; name: string; ready: boolean; custom?: boolean; backend?: string | null; why?: string | null;
  bestFor?: string; license?: string; commercial?: "yes" | "conditional"; price?: string;
}
export interface ModelsInfo { images: OpenModel[]; finish: OpenModel[]; fal: boolean; comfyui: string; catalog: boolean }
export interface AgentsInfo {
  default: AgentKind;
  agents: AgentInfo[];
  pulls: Record<string, PullState>;
  render: RenderSettings;
  models?: ModelsInfo;
}
/** AI finish progress (out/finish.json). */
export interface FinishStatus {
  model: FinishModel; name: string; state: "running" | "done" | "error"; done: number; total: number;
  shots: Record<string, { ok: boolean; error?: string }>; video: string | null; error: string | null;
}
export interface AgentSettingsBody {
  agent?: AgentKind;
  model?: string;
  key?: string;
  url?: string;
  visionModel?: string;
  default?: AgentKind;
  render?: { quality?: RenderSettings["quality"]; images?: RenderSettings["images"]; imageModel?: ImageModel };
  models?: { falKey?: string; comfyuiUrl?: string };
}

// ---------- web-only views of the agent-written JSON ----------
export type Camera = { move: string; lens?: number | string; from?: { fill?: number | null }; to?: { fill?: number | null }; pace?: string };
export type Shot = {
  id: string; start_s?: number; end_s?: number; summary?: string; action?: string; camera?: string | Camera; camera_note?: string;
  ref_shot?: number | string | null; ref_what?: string; transition_in?: string; transition_out?: string; reads?: string[]; text_overlay?: { text: string }[]; assets?: string[];
};
export type PlanAsset = { id: string; file?: string; kind?: string; purpose?: string; status?: string; source?: string; license?: string };
export interface PlanView extends Plan {
  logline?: string; style?: string; engine?: string;
  format?: { width?: number; height?: number; duration_s?: number };
  look?: { palette?: string[]; medium?: string; color_arc?: string };
  borrowed_from_reference?: string[];
  music?: { file?: string; source?: string; bpm?: number; license?: string; section?: { start_s?: number; end_s?: number } };
  style_frames?: string[];
  characters?: (PlanCharacter & { design?: string; arc?: string })[];
  shots?: Shot[];
  assets?: PlanAsset[];
  open_questions?: string[];
  changelog?: string[];
}

export type Report = {
  video: { duration: number; width: number; height: number; fps: number };
  crop?: { w: number; h: number } | null;
  audio?: { bpm?: number; present?: boolean; silent?: boolean };
  pacing?: { count?: number; mean_shot_s?: number; mean_shot_beats?: number };
};
export type Route = { engine?: string; style?: string; medium?: string; confidence?: number; why?: string[] };
export type MustFix = { shot?: string; time?: number | null; issue: string; fix?: string };
export type Critique = { pass?: boolean; summary?: string; scores?: Record<string, number>; must_fix?: (MustFix | null)[] };
export type Production = { characters?: { id: string; name?: string }[] };
export type LyricLine = { start?: number; end?: number; text: string; match: number };
export type Lyrics = { lines?: LyricLine[] };

export type SnapshotView = Omit<Snapshot, "report" | "route" | "plan" | "critique" | "production" | "lyrics"> & {
  report: Report | null; route: Route | null; plan: PlanView | null; critique: Critique | null; production: Production | null; lyrics: Lyrics | null;
};

export type Tag = { shot?: string; time?: number; q?: string };
export type MessageMeta = Pick<ChatMessage, "shot" | "time" | "attachments" | "notes">;
