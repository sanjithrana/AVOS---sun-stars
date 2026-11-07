// Mirrors the Animation Studio's Series API (apps/animation_studio/studio/series/routes.py).

export type CharStatus = "drafting" | "redo" | "review" | "approved" | "error";
export type PartStatus = "waiting" | "writing" | "script_review" | "queued" | "rendering" | "board_review" | "review" | "approved" | "error" | "stopped";
export type EpisodeStatus = "outlining" | "outline_review" | "in_production" | "joining" | "done" | "error" | "stopped";
export type Emotion = "neutral" | "happy" | "excited" | "angry" | "sad" | "scared" | "surprised" | "sarcastic" | "worried" | "shout" | "whisper" | "laugh";

export interface ModelInfo { model: string | null; fallback?: boolean; note?: string; prompt?: string; edit?: string; qaRetry?: boolean; driver?: boolean }

// ---------- creative state (agentic_core/creative): scene graph, motion blueprint, Design DNA ----------
export type Vec3 = [number, number, number];
export interface CameraState { position: Vec3; target: Vec3; lens: number }
export interface StageActor { id: string; x: number; z: number; facing: string; pose: string; expression: string; speaking: boolean }
export interface StageProp { name: string; x: number; z: number; held_by: string | null }
export interface StageGraph {
  location: string; time: string; framing: string;
  lighting: { preset: string; key: string; mood: string };
  actors: StageActor[]; props: StageProp[]; camera: CameraState;
}
export interface MotionKey { t: number; action: string; x?: number; z?: number }
export interface Blueprint {
  duration: number;
  camera: { move: string; ease: string; from: CameraState; to: CameraState; shake: number };
  tracks: { target: string; keys: MotionKey[] }[];
  environment: { t: number; text: string }[];
  lipsync: string | null;
}
export interface DesignDNA {
  name: string; medium: string; line: string; shading: string; proportions: string; texture: string; palette: string[]; lighting: string;
  camera: { default_lens: number; angle: string; max_speed: string; allowed_moves: string[] };
  motion: { pacing: string; ease: string; squash_stretch: boolean; holds: boolean; feel: string };
  sound: { ambience: string; music: string; sfx_style: string };
  avoid: string[];
}
export interface QAResult { pass: boolean; checks?: Record<string, { ok: boolean; why: string }>; fix?: string; retried?: boolean; skipped?: string }
export interface SkillInfo { name: string; description: string; used_by: string; path: string; chars: number }

export interface Character {
  id: string;
  name: string;
  role: string;
  age: string;
  gender: "male" | "female" | "other";
  personality: string;
  look: string;
  outfit: string;
  catchphrase?: string;
  voice: { description?: string; sample?: string; sampleText?: string; model?: string; fallback?: boolean; edge?: string; upload?: string; version?: number };
  sheet?: string;
  sheetInfo?: ModelInfo;
  upload?: string;
  status: CharStatus;
  version: number;
  error?: string | null;
  notes?: string[];
  history?: { version: number; sheet?: string; voice?: string; note?: string; at: string }[];
  fromLibrary?: string;
}

export interface Location { id: string; name: string; description: string; plate?: string; status?: string; error?: string }

export interface Beat {
  id?: string;
  type: "line" | "action";
  character?: string;
  text: string;
  emotion?: Emotion;
  action?: string;
  characters?: string[];
  sfx?: string;
  seconds?: number;
  fixed?: boolean;
  shot?: string;
  hint?: Record<string, unknown>;
}
export interface Scene { id?: string; location: string; time: string; characters: string[]; beats: Beat[] }
export interface Script { scenes: Scene[] }

export interface Shot {
  id: string;
  kind: "dialogue" | "action";
  scene: string;
  location: string;
  framing: string;
  subjects: string[];
  camera: string;
  picture: string;
  motion: string;
  sfx: string;
  speaker?: string;
  text?: string;
  emotion?: string;
  seconds: number;
  takes: { voice: number; picture: number; motion: number };
  files: Partial<Record<"line" | "key" | "clip" | "sfx", string>>;
  models: Partial<Record<"line" | "key" | "clip" | "sfx", ModelInfo>>;
  warnings: string[];
  note?: string;
  stage?: StageGraph;
  blueprint?: Blueprint;
  qa?: { key?: QAResult; clip?: QAResult };
  keyOverride?: { source?: string; pending?: string | null; instruction?: string; history?: string[]; keepMotion?: boolean };
  driver?: boolean;
  angle?: string;
  lipsync?: boolean;
  plan?: { model: string; prompt: string; negative?: string };
  fixed?: boolean;
  filmShot?: string;
}

export interface Part {
  index: number;
  minutes: number;
  status: PartStatus;
  summary?: string;
  beats?: string[];
  endsWith?: string;
  script?: Script;
  scriptSeconds?: number;
  shots?: Shot[];
  video?: string;
  seconds?: number;
  renderedAt?: string;
  renders?: number;
  warnings?: number;
  musicInfo?: ModelInfo;
  sound?: { ambience: Record<string, string>; sfx: Record<string, string>; music: string };
  ambienceInfo?: Record<string, ModelInfo>;
  memory?: { summary: string; facts: string[] };
  error?: string | null;
  version?: number;
  stage?: "board" | "all";
  storyboard?: string | null;
  boardAt?: string;
  boardApprovedAt?: string | null;
  boards?: number;
}

export interface Episode {
  id: string;
  number: number;
  title: string;
  brief: string;
  source: "ai" | "script" | "film";
  targetMinutes: number;
  status: EpisodeStatus;
  outline?: { title?: string; logline?: string; fromScript?: boolean };
  parts: Part[];
  video?: string;
  seconds?: number;
  error?: string | null;
}

export interface Work { state: "idle" | "running" | "error" | "stopped"; label?: string | null; step?: string | null; done?: number; total?: number; queue?: string[]; error?: string | null }

export interface Series {
  id: string;
  title: string;
  premise: string;
  language: string;
  languageName: string;
  tone: string;
  logline?: string;
  world?: string;
  crew: string;
  partPlan: number[];
  format: { aspect: string; width: number; height: number; fps: number };
  style: { description?: string; prompt?: string; refs: string[] };
  music: { theme?: string; off?: boolean; style?: string };
  characters: Character[];
  locations: Location[];
  episodes: { id: string; number: number; title: string; status: EpisodeStatus; parts: number; approvedParts: number; video?: string }[];
  story: { episodes: { episode: number; title?: string; summary: string }[]; facts: string[] };
  settings: { autoApproveScripts?: boolean; shotQA?: boolean; storyboardGate?: boolean };
  kind?: "series" | "film";
  prompt?: string;
  breakdown?: Breakdown;
  libraryPicks?: string[];
  dna?: DesignDNA;
  work: Work;
  log?: { t: string; who?: string; text: string }[];
  updatedAt: string;
}

export interface Readiness {
  pictures: string | null;
  picturesFallback: string | null;
  voiceDesign: string | null;
  lines: string | null;
  lipsync: string | null;
  motion: string | null;
  sfx: string | null;
  music: string | null;
  edge: boolean;
  languages: { lines: string[]; design: string[] };
}

export interface SeriesSnapshot {
  series: Series;
  episodes: Episode[];
  busy: boolean;
  ready: Readiness;
  language: { code: string; name: string; script: string; note: string };
  film?: { stages: FilmStage[]; breakdownChanged: boolean };
}

// ---------- films (prompt → animation) ----------
export type StageKey = "breakdown" | "lock" | "storyboard" | "motion" | "prompts" | "render" | "edit";
export interface FilmStage { key: StageKey; label: string; state: "done" | "working" | "yours" | "next" | "waiting" }
export interface BdCharacter { name: string; look: string; outfit: string; props: string; personality: string; voice: string; gender: string; age: string; actions: string[]; library?: string }
export interface BdShot {
  id: string; start: number; end: number; title: string; location: string; framing: string; angle: string; camera: string;
  ease?: string; lens?: number; characters: string[]; picture: string; action: string;
  events: { t: number; who: string | null; action: string }[];
  dialogue: { character: string; text: string; emotion: string }[];
  sfx: { t: number | null; sound: string }[];
  transition: string;
}
export interface Breakdown {
  status?: "analyzing" | "review" | "approved" | "error";
  error?: string | null;
  title: string; logline: string; duration: number; style: string; tone: string;
  characters: BdCharacter[];
  locations: { name: string; description: string }[];
  shots: BdShot[];
  audio: { music: string; ambience: string; events: { t: number; sound: string }[] };
  rules: string[];
  detected?: { story: boolean; characters: number; locations: number; shots: number; camera: number; dialogue: number; sounds: number; music: boolean; rules: number; seconds: number };
  notes?: string[];
}
export interface LibraryCharacter {
  id: string; name: string; look?: string; outfit?: string; personality?: string; gender?: string; age?: string;
  voice?: { description?: string; sampleText?: string; sample?: string }; from?: string; savedAt?: string; sheetUrl: string; voiceUrl: string | null;
}

export interface SeriesSummary {
  id: string;
  kind?: "series" | "film";
  stage?: string | null;
  status?: string | null;
  video?: string | null;
  title: string;
  language: string;
  languageName: string;
  characters: number;
  approved: number;
  episodes: number;
  updatedAt: string;
  thumb?: string | null;
  working: boolean;
}

export interface LanguageInfo { code: string; name: string; script: string; lines: string[]; design: string[]; note: string }

// ---------- your model choices per step (GET /series/{sid}/models) ----------
export interface ModelOption { id: string; name: string; ready: boolean; backend?: string | null; why?: string | null; price?: string;
  backends: Record<string, { label: string; why: string | null }> }
export interface StepChoice { step: string; label: string; model: string; backend: string; options: ModelOption[] }
