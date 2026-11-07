// Client for Stickman Studio (apps/animation_studio/studio/stickman), through the Next rewrite (/studio-api/stickman/*).
export type Status = "working" | "waiting" | "done" | "error" | "stopped";
export type StageId = "topics" | "brief" | "story" | "roster" | "clips" | "refs" | "scenes" | "animate" | "voice" | "finish";

export interface Topic { title: string; date_place: string; premise: string; opening_visual: string; conflict: string; ending: string; duration_s: number; clips: number; difficulty: "easy" | "medium" | "hard" }
export interface Brief {
  event: string; date: string; location: string; people: string[]; cause: string; turning_point: string; outcome: string;
  facts: { claim: string; confidence: "well-established" | "check" }[]; disputed: string[]; sources_to_check: string[]; dramatization_notes: string[]; verification: "pending";
}
export interface Accent { name: string; hex: string }
export interface StyleInfo { id: string; code: string; name: string; group: string; made_for: string; arc: string; look: string; history: boolean; mode: "director" | "autopilot"; native_audio?: boolean; captions?: boolean }
export interface Character {
  id: string; name: string; role: string; age_presentation: string; head_shape: string; height_heads: number; proportions: string; eyes: string; brows: string; mouth: string;
  hair_or_headwear: string; clothing: string; footwear: string; accents: Accent[]; signature_prop: string; distinguishing_feature: string; planned_damage: string;
}
export interface CharState { id: string; position: string; facing: string; pose: string; expression: string; holds: string; prop_grip: string }
export interface Clip {
  n: number; t0: number; t1: number; location: string; time_of_day: string; chars: CharState[]; opening_setup: string;
  beats: { setup?: string; escalation?: string; payoff?: string; hook?: string; main?: string; reaction?: string; outcome?: string }; camera_move: string; sfx: string[]; music: string; transition: "match" | "cut"; transition_note: string;
  outgoing: { summary: string }; scene_prompt: string; animation_prompt: string; words: { scene: number; animation: number }; narration_warning: string;
  scene?: string | null; video?: string | null; voice?: string | null; engine?: string; video_note?: string; voice_warning?: string; status?: string; version?: number;
}
export interface StoryClip { n: number; t0: number; t1: number; purpose: string; narration: string; main_action: string }
export interface Issue { clip: string; level: "error" | "warn" | "info"; text: string }
export interface Project {
  id: string; title: string; event: string; aspect: string; style?: string; status: Status; stage: StageId; error?: string | null; auto: boolean; clip_count: number; seconds: number;
  topics: { topics: Topic[]; recommended: number; why: string } | null; project: { title: string; date_place: string; premise: string } | null; brief: Brief | null;
  story: { title: string; hook: string; clips: StoryClip[] } | null; roster: Character[] | null; clips: Clip[]; consistency?: string; continuity?: { issues: Issue[] };
  assets: Record<string, string>; log: { t: string; kind: string; text: string }[]; final?: string | null; finalSeconds?: number; thumb?: string | null;
  busy: boolean; stages: { id: StageId; label: string }[]; updatedAt: string;
  bible?: { premise: string; theme: string; audience: string; layout: string; props: { name: string; look: string; rule: string }[]; visual_logic: string[]; music: string; text_policy: string } | null;
}
export interface Summary { id: string; title: string; event: string; status: Status; stage: StageId; seconds: number; aspect: string; final?: string | null; thumb?: string | null; error?: string | null; updatedAt: string }

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let r: Response;
  try {
    r = await fetch(`/studio-api/stickman${path}`, { ...init, headers: init?.body ? { "Content-Type": "application/json" } : undefined });
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

export const stickman = {
  list: () => call<Summary[]>(""),
  get: (id: string) => call<Project>(`/${id}`),
  styles: () => call<{ styles: StyleInfo[]; default: string }>("/styles"),
  create: (b: { event?: string; interest?: string; aspect: string; auto: boolean; style?: string; seconds?: number; voice?: "male" | "female"; models?: Record<string, { model: string }>; local_only?: boolean; crew?: string }) => post<Project>("", b),
  pick: (id: string, index: number) => post<Project>(`/${id}/pick`, { index }),
  moreTopics: (id: string, note: string) => post<Project>(`/${id}/more-topics`, { note }),
  editNarration: (id: string, narration: Record<string, string>) => call<Project>(`/${id}`, { method: "PATCH", body: JSON.stringify({ narration }) }),
  approve: (id: string) => post<Project>(`/${id}/approve`),
  resume: (id: string) => post<Project>(`/${id}/continue`),
  cancel: (id: string) => post<{ ok: true }>(`/${id}/cancel`),
  clipAgain: (id: string, n: number, what: "scene" | "video", note = "") => post<Project>(`/${id}/clips/${n}`, { what, note }),
  remove: (id: string) => call<{ ok: true }>(`/${id}`, { method: "DELETE" }),
  file: (id: string, path: string, v?: string | number) => `/studio-api/stickman/${id}/files/${path}${v !== undefined ? `?v=${encodeURIComponent(String(v))}` : ""}`,
  packageUrl: (id: string) => `/studio-api/stickman/${id}/package`,
};
