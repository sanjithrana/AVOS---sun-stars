// Series API client: same-origin through the Next rewrite (/studio-api/* → the Animation Studio's /api/*).
import type { Blueprint, Breakdown, LanguageInfo, LibraryCharacter, Script, SeriesSnapshot, SeriesSummary, SkillInfo, StageGraph, StepChoice } from "./types";

async function j<T>(r: Response): Promise<T> {
  const text = await r.text().catch(() => "");
  let d: unknown = {};
  try { d = text ? JSON.parse(text) : {}; } catch { d = {}; }
  if (!r.ok) {
    const msg = (d as { error?: string }).error;
    if (!msg && r.status >= 500) throw new Error("The animation service isn't running. In the apps folder run: docker compose up -d animation-studio");
    throw new Error(msg || r.statusText || `HTTP ${r.status}`);
  }
  return d as T;
}
const base = "/studio-api/series";
const offline = () => { throw new Error("The animation service isn't reachable. In the apps folder run: docker compose up -d animation-studio"); };
const get = <T,>(p: string) => fetch(`${base}${p}`).catch(offline).then((r) => j<T>(r as Response));
const send = <T,>(p: string, method: string, body?: unknown) =>
  fetch(`${base}${p}`, { method, headers: body === undefined ? undefined : { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) }).then((r) => j<T>(r));
const post = <T,>(p: string, body?: unknown) => send<T>(p, "POST", body ?? {});
const form = <T,>(p: string, f: FormData) => fetch(`${base}${p}`, { method: "POST", body: f }).then((r) => j<T>(r));

const ep = (sid: string, eid: string) => `/${sid}/episodes/${eid}`;

export const seriesApi = {
  list: () => get<SeriesSummary[]>(""),
  languages: () => get<LanguageInfo[]>("/languages"),
  create: (f: FormData) => form<{ id: string }>("", f),
  get: (sid: string) => get<SeriesSnapshot>(`/${sid}`),
  edit: (sid: string, body: Record<string, unknown>) => send<SeriesSnapshot>(`/${sid}`, "PATCH", body),
  addRefs: (sid: string, f: FormData) => form<SeriesSnapshot>(`/${sid}/refs`, f),
  theme: (sid: string, f: FormData) => form<SeriesSnapshot>(`/${sid}/music`, f),
  addCharacter: (sid: string, body: Record<string, string>) => post<SeriesSnapshot>(`/${sid}/characters`, body),
  editCharacter: (sid: string, cid: string, body: Record<string, string>) => send<SeriesSnapshot>(`/${sid}/characters/${cid}`, "PATCH", body),
  approveCharacter: (sid: string, cid: string) => post<SeriesSnapshot>(`/${sid}/characters/${cid}/approve`),
  redoCharacter: (sid: string, cid: string, what: "look" | "voice" | "both", note: string) => post<SeriesSnapshot>(`/${sid}/characters/${cid}/redo`, { what, note }),
  uploadCharacter: (sid: string, cid: string, f: FormData) => form<SeriesSnapshot>(`/${sid}/characters/${cid}/upload`, f),
  deleteCharacter: (sid: string, cid: string) => send<SeriesSnapshot>(`/${sid}/characters/${cid}`, "DELETE"),
  redoLocation: (sid: string, lid: string, note: string) => post<SeriesSnapshot>(`/${sid}/locations/${lid}/redo`, { note }),
  newEpisode: (sid: string, body: { brief?: string; minutes: number; script?: string; title?: string }) => post<SeriesSnapshot & { episode: string }>(`/${sid}/episodes`, body),
  approveOutline: (sid: string, eid: string) => post<SeriesSnapshot>(`${ep(sid, eid)}/outline/approve`),
  redoOutline: (sid: string, eid: string, note: string) => post<SeriesSnapshot>(`${ep(sid, eid)}/outline/redo`, { note }),
  saveScript: (sid: string, eid: string, n: number, script: Script) => send<SeriesSnapshot>(`${ep(sid, eid)}/parts/${n}/script`, "PUT", { script }),
  approveScript: (sid: string, eid: string, n: number) => post<SeriesSnapshot>(`${ep(sid, eid)}/parts/${n}/script/approve`),
  redoScript: (sid: string, eid: string, n: number, note: string) => post<SeriesSnapshot>(`${ep(sid, eid)}/parts/${n}/script/redo`, { note }),
  approvePart: (sid: string, eid: string, n: number) => post<SeriesSnapshot>(`${ep(sid, eid)}/parts/${n}/approve`),
  redoPart: (sid: string, eid: string, n: number, body: { shots?: string[]; what?: string[]; note?: string }) => post<SeriesSnapshot>(`${ep(sid, eid)}/parts/${n}/redo`, body),
  resume: (sid: string, eid: string) => post<SeriesSnapshot>(`${ep(sid, eid)}/resume`),
  cancel: (sid: string) => post<{ ok: boolean }>(`/${sid}/cancel`),
  skills: () => get<{ dir: string | null; skills: SkillInfo[] }>("/skills"),
  rebuildDna: (sid: string) => post<SeriesSnapshot>(`/${sid}/dna/rebuild`),
  // shot tools
  saveStage: (sid: string, eid: string, n: number, shot: string, stage: StageGraph, blueprint: Blueprint) =>
    send<SeriesSnapshot>(`${ep(sid, eid)}/parts/${n}/shots/${shot}/stage`, "PUT", { stage, blueprint }),
  modifyShot: (sid: string, eid: string, n: number, shot: string, instruction: string, keepMotion: boolean) =>
    post<SeriesSnapshot>(`${ep(sid, eid)}/parts/${n}/shots/${shot}/modify`, { instruction, keepMotion }),
  animateImage: (sid: string, eid: string, n: number, shot: string, f: FormData) => form<SeriesSnapshot>(`${ep(sid, eid)}/parts/${n}/shots/${shot}/image`, f),
  motionDriver: (sid: string, eid: string, n: number, shot: string, f: FormData) => form<SeriesSnapshot>(`${ep(sid, eid)}/parts/${n}/shots/${shot}/driver`, f),
  resetShot: (sid: string, eid: string, n: number, shot: string) => send<SeriesSnapshot>(`${ep(sid, eid)}/parts/${n}/shots/${shot}/override`, "DELETE"),
  // storyboard gate, batch camera, project files
  approveBoard: (sid: string, eid: string, n: number) => post<SeriesSnapshot>(`${ep(sid, eid)}/parts/${n}/board/approve`),
  camera: (sid: string, eid: string, n: number, body: { shots?: string[]; move?: string; ease?: string; lens?: number; angle?: string }) =>
    post<SeriesSnapshot & { changed: string[] }>(`${ep(sid, eid)}/parts/${n}/camera`, body),
  exportUrl: (sid: string, eid: string) => `${base}${ep(sid, eid)}/export`,
  // films
  createFilm: (f: FormData) => form<{ id: string }>("/films", f),
  saveBreakdown: (sid: string, breakdown: Breakdown) => send<SeriesSnapshot>(`/${sid}/breakdown`, "PUT", { breakdown }),
  redoBreakdown: (sid: string, note: string, prompt?: string) => post<SeriesSnapshot>(`/${sid}/breakdown/redo`, { note, ...(prompt ? { prompt } : {}) }),
  approveBreakdown: (sid: string) => post<SeriesSnapshot>(`/${sid}/breakdown/approve`),
  storyboard: (sid: string) => post<SeriesSnapshot>(`/${sid}/film/storyboard`),
  // which model runs each step, and where (your GPU, ComfyUI, fal.ai, Cloudflare…)
  modelChoices: (sid: string) => get<{ steps: StepChoice[]; providers: Record<string, string> }>(`/${sid}/models`),
  setModelChoices: (sid: string, models: Record<string, { model: string; backend: string }>) => send<SeriesSnapshot>(`/${sid}`, "PATCH", { models }),
  // character library
  library: () => get<LibraryCharacter[]>("/library/characters"),
  deleteLibrary: (lid: string) => send<LibraryCharacter[]>(`/library/characters/${lid}`, "DELETE"),
  saveToLibrary: (sid: string, cid: string) => post<SeriesSnapshot>(`/${sid}/characters/${cid}/library`),
  addFromLibrary: (sid: string, lid: string) => post<SeriesSnapshot>(`/${sid}/characters/from-library`, { id: lid }),
  libFile: (p: string, v?: string) => `${base}/${p}${v ? `?v=${encodeURIComponent(v)}` : ""}`,
  // encode each segment; `v` busts the browser cache after a redo
  file: (sid: string, p: string | undefined | null, v?: string | number) =>
    p ? `${base}/${sid}/files/${p.split("/").map(encodeURIComponent).join("/")}${v ? `?v=${encodeURIComponent(String(v))}` : ""}` : "",
};

export const MODEL_LABEL: Record<string, string> = {
  "qwen-image-edit": "Qwen-Image-Edit", "qwen-image": "Qwen-Image", "z-image": "Z-Image", "flux-schnell": "FLUX schnell",
  chatterbox: "Chatterbox", indicf5: "IndicF5", "indic-parler-tts": "Indic Parler-TTS", edge: "Edge voice",
  infinitetalk: "InfiniteTalk", "longcat-avatar": "LongCat Avatar", "wan-2.2": "Wan 2.2", "ltx-2.3": "LTX-2.3",
  "hunyuan-foley": "HunyuanVideo-Foley", "ace-step": "ACE-Step", still: "still + camera move", "your recording": "your recording",
  "your theme": "your theme", "free picture chain": "free picture chain", "wan-vace": "Wan VACE", "wan-2.2-animate": "Wan 2.2 Animate",
};
export const modelLabel = (m?: string | null) => (m ? MODEL_LABEL[m] ?? m : "—");
