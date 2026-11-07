// Mirrors packages/contracts/project.py (ProjectCreate / ProjectResponse)
// and api/src/domain/projects/status.py (ProjectStatus). Keep in sync.

export type ProjectStatus =
  | "planning"
  | "researching"
  | "awaiting_approval"
  | "generating_audio"
  | "planning_shots"
  | "generating_visuals"
  | "awaiting_review"
  | "rendering_video"
  | "complete"
  | "rejected"
  | "failed";

export type AspectRatio = "9:16" | "16:9" | "1:1";

// Mirrors agentic_core/models/llm/factory.py's KNOWN_PROVIDERS.
// "mock" / null both mean "no explicit choice" - the New Project form's
// default - and route to auto-detect (OpenAI/Groq env key) then Mock.
export const LLM_PROVIDERS = [
  { value: "", label: "Auto (recommended)" },
  { value: "mock", label: "Mock (offline, deterministic)" },
  { value: "openai", label: "OpenAI" },
  { value: "ollama", label: "Ollama (local, free)" },
  { value: "llamacpp", label: "llama.cpp (local GGUF, free)" },
  { value: "groq", label: "Groq (free tier)" },
] as const;

// Mirrors agentic_core/models/image/factory.py's KNOWN_PROVIDERS.
// "model" = an id in agentic_core/models/catalog.json (open models: your GPU server or fal.ai).
export const IMAGE_PROVIDERS = [
  { value: "", label: "Mock (placeholder frames)", group: "Free" },
  { value: "free", label: "Free auto (Cloudflare, then Pollinations)", group: "Free" },
  { value: "pollinations", label: "Pollinations.ai (free, no key)", group: "Free" },
  { value: "cloudflare", label: "Cloudflare Workers AI (free, ~2,000/day)", group: "Free" },
  { value: "local", label: "Self-hosted (Automatic1111/SD WebUI)", group: "Free" },
  { value: "best", label: "Best open model per picture (Z-Image; Qwen-Image for text)", group: "Open models", model: "z-image" },
  { value: "z-image", label: "Z-Image Turbo - characters, scenes, concept art", group: "Open models", model: "z-image" },
  { value: "qwen-image", label: "Qwen-Image - pictures with readable text", group: "Open models", model: "qwen-image" },
  { value: "flux-schnell", label: "FLUX.1 schnell - fast drafts", group: "Open models", model: "flux-schnell" },
  { value: "chain", label: "Auto fallback (free chain, then paid as last resort)", group: "Paid APIs" },
  { value: "replicate", label: "Replicate (paid, ~$0.003/image)", group: "Paid APIs" },
  { value: "stability", label: "Stability AI (paid, ~$0.03/image)", group: "Paid APIs" },
] as const;

// Mirrors agentic_core/models/video/factory.py's KNOWN_PROVIDERS.
// Every option ends in a real MP4 (narration + captions); they differ in
// how each shot moves.
export const VIDEO_PROVIDERS = [
  // Kept so older projects still show their choice; not offered for new ones (AI models give the 3D look now).
  { value: "blender", label: "Blender 3D mannequins (older projects)", group: "Free", hidden: true },
  { value: "motion", label: "Free: AI image + camera motion (no GPU, no key)", group: "Free" },
  { value: "", label: "None - animate the shot images in the final render", group: "Free" },
  { value: "best", label: "Best open model per shot (Wan 2.2; LTX-2.3 for long shots)", group: "Open models: video", model: "wan-2.2" },
  { value: "wan-2.2", label: "Wan 2.2 I2V - animate each shot's picture", group: "Open models: video", model: "wan-2.2" },
  { value: "ltx-2.3", label: "LTX-2.3 - follows the narration audio, long shots", group: "Open models: video", model: "ltx-2.3" },
  { value: "wan-vace", label: "Wan VACE 14B - consistent look between shots", group: "Open models: video", model: "wan-vace" },
  { value: "avatar", label: "Talking presenter (LongCat Avatar; InfiniteTalk for long)", group: "Open models: presenter", model: "longcat-avatar" },
  { value: "longcat-avatar", label: "LongCat Avatar - presenter scene by scene", group: "Open models: presenter", model: "longcat-avatar" },
  { value: "infinitetalk", label: "InfiniteTalk - long lessons and dialogue", group: "Open models: presenter", model: "infinitetalk" },
  { value: "comfyui", label: "ComfyUI on your own GPU - your video.json workflow (free)", group: "Your own server" },
  { value: "local", label: "Custom self-hosted video API (POST /generate)", group: "Your own server" },
  { value: "fal", label: "fal.ai / Kling (paid, ~$0.25 per clip)", group: "Paid APIs" },
  { value: "replicate", label: "Replicate (paid, needs API token)", group: "Paid APIs" },
] as const;

/** Video providers that animate each shot's still, so they need a real
 * image provider (the backend falls back to the free chain). */
export const IMAGE_TO_VIDEO_PROVIDERS: ReadonlyArray<string> = [
  "motion", "fal", "replicate", "comfyui", "best", "wan-2.2", "ltx-2.3", "wan-vace", "avatar", "longcat-avatar", "infinitetalk",
];

/** Options grouped for <optgroup>, keeping their order. */
export function groupOptions<T extends { group: string }>(options: ReadonlyArray<T>): [string, T[]][] {
  const groups = new Map<string, T[]>();
  for (const o of options) groups.set(o.group, [...(groups.get(o.group) ?? []), o]);
  return [...groups.entries()];
}

// Mirrors agentic_core/styles.py's PRESETS: script tone, look, music, captions.
export const STYLE_PRESETS = [
  { value: "viral_3d", label: "Viral 3D facts (realistic 3D characters, hook script, suspense music)" },
  { value: "storybook", label: "Storybook explainer (illustrated, calm, uplifting music)" },
] as const;

/** Exactly what POST /api/v1/projects accepts (extra fields -> 422). */
export interface ProjectCreate {
  name: string;
  topic: string;
  duration: number;
  aspect_ratio: AspectRatio;
  budget_limit?: number | null;
  llm_provider?: string | null;
  image_provider?: string | null;
  video_provider?: string | null;
  style_preset?: string | null;
  /** Model Fabric limits for this project (null = the defaults on the GPU page) */
  generation_policy?: Partial<import("./gpu").GenerationLimits> | null;
}

/** Exactly what the API returns for a project. */
export interface Project {
  id: string;
  name: string;
  topic: string;
  duration_seconds: number;
  aspect_ratio: AspectRatio | string;
  status: ProjectStatus | string;
  budget_limit: number | null;
  budget_spent: number;
  llm_provider: string | null;
  image_provider: string | null;
  video_provider: string | null;
  style_preset?: string | null;
  generation_policy?: Partial<import("./gpu").GenerationLimits> | null;
  created_at: string;
  updated_at: string;
}

export const ACTIVE_PROJECT_STATUSES: ReadonlyArray<string> = [
  "researching",
  "awaiting_approval",
  "generating_audio",
  "planning_shots",
  "generating_visuals",
  "awaiting_review",
  "rendering_video",
];
