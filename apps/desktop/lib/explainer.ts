// Client for the Explainer Studio (apps/animation_studio/studio/explainer). Calls go through the Next rewrite
// (/studio-api/explainer/*), so the browser stays same-origin.
export type Engine = "ai_video" | "blender" | "still" | "lipsync" | "upload";
export type Status = "working" | "waiting" | "done" | "error" | "stopped";
export type StageId = "plan" | "design" | "board" | "shoot" | "finish";

export interface Shot {
  id: string; index: number; shot_type: string; seconds: number; narration: string; action: string;
  characters: string[]; props: string[]; camera: { type: string; movement: string; lens_mm: number };
  physics: boolean; visualization: { cross_section: boolean; force_arrows: boolean }; sfx: string;
  engine: Engine | null; engine_why: string; force?: Engine; status: string; version: number;
  speaker?: string; angle?: string; composition?: string; objective?: string; performance?: string; end_state?: string; continuity?: string; gaps?: string[]; scene?: number; scene_title?: string; mood?: string; emotion?: string; rating?: "up" | "down" | null; qc?: string[]; lighting?: string; audio?: string; cam_note?: string; pic_prompt?: string; anim_prompt?: string;
  frame?: string | null; end_frame?: string | null; clip?: string | null; info?: { note?: string; model?: string; fallback?: boolean; mode?: string };
  continuity_check?: { same: boolean; differences?: string; redrawn?: boolean } | null;
}
export interface Item { id: string; name: string; look: string; voice?: string; role?: string; memory?: string }
export type AgentState = "waiting" | "working" | "done" | "skipped" | "off" | "error";
export interface Agent { id: string; name: string; stage: StageId; does: string; on: boolean; state: AgentState; progress: [number, number] | null; output: string }
export interface Boards { cast: Record<string, string>; world: string | null; scenes: Record<string, string>; clips: Record<string, string> }
export interface CastMember { id: string; name: string; look: string; identity: string; voice: string; seed: number; portrait?: string; sheet?: string; frames: string[]; projects: string[]; approved: boolean; updated: string }
export interface Research {
  status: "ok" | "skipped"; reason: string; topic: string; sources: { title: string; url: string }[];
  facts: { fact: string; source: { title: string; url: string } }[]; questions: string[]; misconceptions: string[]; unknowns: string[];
}
export interface Plan { title: string; hook: string; music: string; characters: Item[]; props: Item[]; world: { name: string; look: string }; shots: Shot[]; aspect: string;
  logline?: string; palette?: { name: string; hex: string }[]; camera_language?: string; lighting_note?: string; sound_design?: string; note?: string }
export interface Project {
  id: string; brief: string; title: string; seconds: number; aspect: string; language: string; crew: string; auto: boolean; voice: string;
  status: Status; stage: StageId; error?: string | null; plan: Plan | null; assets: Record<string, string>; log: { t: string; kind: string; text: string }[];
  final?: string | null; finalSeconds?: number; thumb?: string | null; contact?: string | null; board?: string | null; board_error?: string | null; research?: Research | null; source?: { title: string; url: string; words: number } | null; busy: boolean; totalSeconds: number; stages: { id: StageId; label: string }[];
  caps?: { ai_video: boolean; blender: boolean; lipsync?: boolean }; updatedAt: string; createdAt: string;
  agents?: Agent[]; boards?: Boards | null; vision_check?: boolean;
}
export interface Skill {
  id: string; name: string; stage: StageId; does: string; optional: boolean; on: boolean; ready: boolean; ready_note: string;
  prompts: { key: string; title: string }[]; uses: number; bad_rate: number; ok: number; fail: number; last_error: string; weakest: string | null;
}
export interface Voice { id: string; name: string; locale: string; language: string; dialect: string; gender: string; tags: string[] }
export interface Summary { id: string; title: string; brief: string; status: Status; stage: StageId; seconds: number; aspect: string; final?: string | null; thumb?: string | null; error?: string | null; updatedAt: string }
export interface PromptVersion { v: number; text: string; source: string; note: string; created: string; uses: number; bad: number; up: number; down: number; bad_rate: number; flags: Record<string, number>; examples: { outcome: string; flags: string[]; note: string; prompt: string }[] }
export interface PromptItem {
  key: string; title: string; group: string; help: string; placeholders: string[]; min_uses: number;
  active: PromptVersion; candidate: PromptVersion | null;
  versions: { v: number; source: string; note: string; created: string; uses: number; bad_rate: number; up: number; down: number }[];
}
export interface PromptLibrary { items: PromptItem[]; events: { t: string; text: string }[]; message?: string }
export interface Capabilities { ai_video: boolean; blender: boolean; voice: boolean; music: boolean; hint: string | null; aspects: string[]; languages: { code: string; name: string }[] }

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let r: Response;
  try {
    r = await fetch(`/studio-api/explainer${path}`, { ...init, headers: init?.body ? { "Content-Type": "application/json" } : undefined });
  } catch {
    throw new Error("The studio service is not running. Start it with: docker compose up -d animation-studio");
  }
  const text = await r.text();
  let data: unknown = null;
  try { data = text ? JSON.parse(text) : null; } catch { /* not JSON */ }
  if (!r.ok) throw new Error((data as { error?: string } | null)?.error || `The studio answered ${r.status}. Is it running?`);
  return data as T;
}

const post = <T,>(path: string, body?: unknown) => call<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

const put = <T,>(path: string, body?: unknown) => call<T>(path, { method: "PUT", body: JSON.stringify(body ?? {}) });

export const explainer = {
  prompts: () => call<PromptLibrary>("/prompts"),
  savePrompt: (key: string, text: string) => put<PromptLibrary>(`/prompts/${key}`, { text }),
  restorePrompt: (key: string, v: number) => post<PromptLibrary>(`/prompts/${key}/restore`, { v }),
  resetPrompt: (key: string) => post<PromptLibrary>(`/prompts/${key}/reset`),
  improvePrompt: (key: string, project?: string) => post<PromptLibrary>(`/prompts/${key}/improve`, { project }),
  learnPrompts: () => post<PromptLibrary>("/prompts/learn"),
  masterPrompt: (id: string, scene?: number) => call<{ text: string; scenes: number[] }>(`/${id}/master-prompt${scene ? `?scene=${scene}` : ""}`),
  skills: () => call<{ skills: Skill[]; message?: string }>("/skills"),
  setSkill: (id: string, on: boolean) => call<{ skills: Skill[] }>(`/skills/${id}`, { method: "PUT", body: JSON.stringify({ on }) }),
  improveSkill: (id: string) => post<{ skills: Skill[]; message?: string }>(`/skills/${id}/improve`),
  redoAsset: (id: string, key: string, note = "") => post<Project>(`/${id}/assets/redo`, { key, note }),
  rate: (id: string, sid: string, up: boolean, note = "") => post<Project>(`/${id}/shots/${sid}/rate`, { up, note }),
  list: () => call<Summary[]>(""),
  memory: () => call<{ cast: CastMember[] }>("/memory"),
  forget: (mid: string) => call<{ cast: CastMember[] }>(`/memory/${mid}`, { method: "DELETE" }),
  memoryFile: (mid: string, name: string, v?: string) => `/studio-api/explainer/memory/${mid}/${name}${v ? `?v=${encodeURIComponent(v)}` : ""}`,
  caps: () => call<Capabilities>("/capabilities"),
  get: (id: string) => call<Project>(`/${id}`),
  voices: (language = "") => call<Voice[]>(`/voices${language ? `?language=${encodeURIComponent(language)}` : ""}`),
  voicePreview: (voice: string) => `/studio-api/explainer/voices/preview?voice=${encodeURIComponent(voice)}`,
  styles: () => call<{ id: string; name: string }[]>("/styles"),
  articlePreview: (url: string) => post<{ title: string; words: number; readMinutes: number; excerpt: string }>("/article/preview", { url }),
  estimate: (b: { seconds: number; models?: Record<string, { model: string }>; local_only?: boolean }) => post<{ usd_low: number; usd_high: number; shots: number; pictures: number; video_shots: number; note: string }>("/estimate", b),
  create: (b: { research?: boolean; brief?: string; url?: string; mode?: string; style_id?: string; voice_id?: string; language?: string; seconds: number; aspect: string; auto: boolean; style?: string; voice?: string; models?: Record<string, { model: string }>; local_only?: boolean; crew?: string }) => post<Project>("", b),
  patch: (id: string, b: Record<string, unknown>) => call<Project>(`/${id}`, { method: "PATCH", body: JSON.stringify(b) }),
  approve: (id: string) => post<Project>(`/${id}/approve`),
  direct: (id: string, note: string, scope: "story" | "look") => post<Project>(`/${id}/direct`, { note, scope }),
  storyboardSheet: (id: string) => post<Project>(`/${id}/storyboard-sheet`, {}),
  redoPlan: (id: string, note: string) => post<Project>(`/${id}/redo-plan`, { note }),
  resume: (id: string) => post<Project>(`/${id}/continue`),
  cancel: (id: string) => post<{ ok: true }>(`/${id}/cancel`),
  shotAgain: (id: string, sid: string, what: "picture" | "clip", note = "", engine?: Engine, extra?: { prompt?: string; anim?: string }) => post<Project>(`/${id}/shots/${sid}`, { what, note, engine, ...extra }),
  remove: (id: string) => call<{ ok: true }>(`/${id}`, { method: "DELETE" }),
  shotPack: (id: string) => `/studio-api/explainer/${id}/shot-pack`,
  picturePrompts: (id: string) => `/studio-api/explainer/${id}/picture-prompts.txt`,
  useClip: async (id: string, sid: string, file: File) => {
    const r = await fetch(`/studio-api/explainer/${id}/shots/${sid}/clip`, { method: "POST", body: file, headers: { "Content-Type": file.type || "video/mp4" } });
    const d = await r.json().catch(() => null);
    if (!r.ok) throw new Error(d?.error || `The studio answered ${r.status}.`);
    return d as Project;
  },
  finish: (id: string) => post<Project>(`/${id}/finish`),
  file: (id: string, path: string, v?: string) => `/studio-api/explainer/${id}/files/${path}${v ? `?v=${encodeURIComponent(v)}` : ""}`,
};

export const ENGINE_LABEL: Record<Engine, string> = { ai_video: "AI video", blender: "3D (Blender)", still: "Picture + camera move", lipsync: "Talking (lip-sync)", upload: "Your clip" };
export const TYPE_LABEL: Record<string, string> = {
  presenter: "Presenter", demonstration: "Demonstration", macro_close_up: "Macro close-up", scientific_cutaway: "Science cutaway",
  result: "Result", reaction: "Reaction", establishing: "Establishing",
};
