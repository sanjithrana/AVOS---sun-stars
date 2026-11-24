// Client for Auto Clip (apps/animation_studio/studio/autoclip) through the Next rewrite (/studio-api/autoclip/*).
export interface Clip {
  n: number; start: number; end: number; title: string; description?: string; file?: string; thumb?: string; status?: string;
  captions?: boolean; approved?: boolean; privacy?: string | null; schedule_at?: string | null; youtube_id?: string; posted_at?: string;
  attempts?: number; error?: string; cover?: string; rev?: number; ai_score?: number; reframe?: Scene[] | null; stats?: { views?: number; likes?: number }; moment?: string; hook?: string;
  seo?: SeoPack | null; why?: Record<string, number>;
  exp?: ClipExp | null; retention?: Retention | null; edit?: EditSpec | null; recipe?: Record<string, string | boolean | null> | null;
}
export interface SeoPack { title: string | null; description: string; hashtags: string[]; mentions: string[]; hook: string | null; by: "ai" | "rules"; query?: string;
  sound?: { title: string; artist: string; uses: number; views: number } | null; music_id?: string }
export interface Research { query: string; source: string; analysis: { hashtags: { tag: string; score: number; uses: number }[]; mentions: string[]; sounds: { title: string; artist: string; uses: number; views: number }[]; title_len: number; emoji_share: number; examples: { id: string; title: string; views: number; channel: string }[] } }
export interface EditSpec { style: string; look?: string; peaks?: number[]; zooms: number[][]; stickers: { t0: number; t1: number; kind: string; text: string; word: string }[]; music: { id: string; name: string; mood: string; volume: number } | null; loudness: boolean; opts?: Record<string, string | number | boolean> }
export interface Scene { i: number; t0: number; t1: number; faces: number; layout: string; auto: string; why: string; pinned: boolean; label: string; can: string[] }
export interface JobOpts { count: number; min_seconds: number; max_seconds: number; layout: string; caption: string; quality: string; crew: string; start_min: number | null; end_min: number | null; preset?: string; cap?: CapOpts; brand?: BrandOpts; cap_lang?: string; mode?: string }
/** Caption changes on top of a style. Every field is optional: empty means "the style's own". */
export interface CapOpts { font?: string; size?: number; x?: number; y?: number; upper?: boolean; bold?: boolean; italic?: boolean; outline?: number; shadow?: number; glow?: boolean; text?: string; hi?: string; offset_ms?: number; anim?: string; words?: number; mode?: string }
export interface BrandOpts {
  wm?: { kind: "text" | "logo"; text?: string; pos?: string; size?: number; opacity?: number };
  end?: { on: boolean; text?: string; sub?: string; secs?: number };
  lower?: { on: boolean; name?: string; sub?: string; at?: number; secs?: number };
}
export interface CanvasOpts { bg?: string; color?: string; color2?: string; pad?: number; radius?: number; dim?: number }
export interface CardOpts { name?: string; handle?: string; headline?: string; hook?: string; font?: string; size?: number; verified?: boolean; episode?: string; speakers?: string; likes?: string }
export interface SavedLook { name: string; caption?: string; cap?: CapOpts; brand?: BrandOpts; layout?: string; music?: string; edit?: string; look?: string; cap_lang?: string }
export interface CaptionStyle { label: string; font: string; upper?: boolean; text: string; hi: string; outline?: number; anim: string; words: number; italic?: boolean; size?: number;
  layout?: string; kw?: string; rest?: string; kw_font?: string; kw_italic?: boolean; kw_upper?: boolean; kw_scale?: number; rest_scale?: number;
  box?: string; tiles?: string[]; tile_text?: string; hi_box?: string; underline?: boolean; dim?: number; blur?: number; glow?: string; out?: string; spacing?: number; hi_font?: string; hi_italic?: boolean }
export interface FontItem { name: string; mine: boolean; file: string }
export interface WhisperModel { label: string; mb: number; ram_gb: number; speed: number; note: string }
export interface SystemInfo { cpus: number; ram_gb: number; disk_free_gb: number; whisper: boolean; whisper_model: string; whisper_pick: string; faces: boolean; encoder: string; busy: string[] }
export interface Job {
  id: string; title: string; status: "working" | "done" | "error" | "stopped"; stage: string; error?: string | null; createdAt?: string; updatedAt?: string;
  source: { kind: string; url?: string; name?: string; minutes?: number; section?: [number, number] }; permission?: "own" | "cc" | "granted" | "unconfirmed" | "blocked"; opts: JobOpts; auto?: boolean; clips: Clip[]; busy: boolean;
  progress?: { pct: number | null; text: string } | null; research?: Research[];
  stages: { id: string; label: string }[]; steps: Record<string, { status: string; note?: string; started?: number; secs?: number | null }>; log: { t: string; kind: string; text: string }[];
}
export interface JobRow { id: string; title: string; status: string; stage: string; createdAt?: string; updatedAt?: string; clips: number; posted: number; error?: string | null }
export interface Channel { id: string; title: string; thumb?: string; subs?: string | number; connected?: string; needs_login?: boolean; revenue_scope?: boolean }
export interface Autopilot { enabled: boolean; paused: boolean; review_first: boolean; per_day: number; min_gap_minutes: number; hours: [number, number]; privacy: string; channel: string; auto_make: boolean; make_per_video: number }
export interface Settings {
  rights_ack: boolean; autopilot: Autopilot; watch: { channel_id: string; name?: string }[]; tz_offset_minutes: number; notice?: string | null;
  defaults: { cap?: CapOpts; brand?: BrandOpts; cap_lang?: string; whisper_model?: string; count: number; min_seconds: number; max_seconds: number; layout: string; caption: string; quality: string; crew: string; edit: string; zoom: boolean; stickers: boolean; look: string; fx: boolean; sfx: boolean; progress: boolean; loudness: boolean; music: string; music_volume: number; coach: boolean; hype_only: boolean; hype_level: string };
  experiments?: { enabled: boolean; window_hours: number; thumbnails: boolean };
}
export interface Preset {
  id: string; name: string; tag: string; about: string; moments: string[]; plan: [string, string][]; rules: string[]; links: { label: string; url: string }[];
  defaults: { count: number; min_seconds: number; max_seconds: number; caption: string; layout: string }; credit: string;
}
export interface Overview {
  presets?: Preset[];
  settings: Settings; channels: Channel[]; jobs: JobRow[]; google: { has_client: boolean };
  autopilot: { recent: number; per_day: number; in_hours: boolean; notice?: string | null; waiting: number; running: boolean };
  capabilities: { ffmpeg: boolean; yt_dlp: boolean; whisper: boolean; layouts: Record<string, string>; captions: Record<string, string>; reframe: { ready: boolean; opencv: boolean; model: boolean; fix: string }; edit_styles?: Record<string, string>; looks?: Record<string, string>; moods?: Record<string, string>;
    caption_styles?: Record<string, CaptionStyle>; anims?: Record<string, string>; fonts?: FontItem[]; whisper_models?: Record<string, WhisperModel>; whisper_pick?: string;
    templates?: Record<string, string>; backgrounds?: Record<string, string>; caption_modes?: Record<string, string>;
    template_info?: Record<string, { label: string; cat: string; desc: string; card: boolean }>; template_cats?: Record<string, string>; card_fonts?: string[] };
}
export interface Crew { id: string; label: string; tier: "local" | "free" | "paid" | "custom"; ready: boolean; detail: string; fix?: string; model?: string; models?: string[]; needsKey?: boolean; hasKey?: boolean; vision?: boolean; visionModel?: string }
export interface CrewInfo { default: string; agents: Crew[]; pulls?: Record<string, { status: string; done: boolean; error?: string; pct?: number }> }
export type Verdict = "own" | "creative-commons" | "ask" | "unknown" | "blocked";
export interface RightsCheck {
  verdict: Verdict; clippable: boolean; platform: string; live?: { state: "live" | "upcoming" | "processing" | "past" } | null; tip: string; notes?: string[]; title: string; channel: string; license?: string; thumbnail?: string; duration?: number | null;
  links: { channel?: string; about?: string };
}
export interface YtPost {
  id: string; src: { jid?: string; n?: number; upload?: string }; channel: string; channel_title: string; title: string; description: string; privacy: string;
  at: string | null; status: "queued" | "posting" | "posted" | "failed" | "cancelled"; error?: string | null; note?: string | null; hold?: boolean; youtube_id?: string; url?: string | null;
  posted_at?: string; scheduled_for?: string | null; thumb_status?: string; stats?: { views?: number; likes?: number; comments?: number; removed?: boolean; privacy?: string; at?: string };
  thumb?: { jid?: string; name?: string; upload?: string } | null;
}
export interface YtChannel { id: string; platform?: string; can_schedule?: boolean; own_plan?: boolean; plan?: YtPlan; title: string; thumb?: string; needs_login?: boolean; subs?: number; queued: number; posted: number; failed: number; views: number; likes: number; comments: number; next: string | null }
export interface YtLib { jid: string; n: number; title: string; job_title: string; thumb?: string; permission: string; allowed: boolean; queued: boolean; duration?: number }
export interface YtUpload { id: string; title: string; ack: boolean; thumb: boolean }
export interface YtPlan { per_day: number; min_gap_minutes: number; hours: [number, number]; privacy: string; ahead_hours?: number }
export interface SocialAccount { id: string; platform: string; title: string; thumb?: string; subs?: number | null; connected?: string; needs_login: boolean; via?: string }
export interface SocialPlatform { id: string; name: string; status: "ready" | "soon"; makes: string[]; id_label?: string; secret_label?: string; steps: string[]; notes: string[]; has_client: boolean; accounts: SocialAccount[]; redirect: string }
export interface SocialView { platforms: SocialPlatform[]; youtube: { has_client: boolean; channels: { id: string; title: string }[] } }
export interface YtTab { plan: YtPlan; posts: YtPost[]; channels: YtChannel[]; library: YtLib[]; uploads: YtUpload[]; google: { has_client: boolean }; rights_ack: boolean; tz_offset_minutes: number; now: string }
export interface ClipExp { phase: "A" | "B" | "done"; t0: string; window_h: number; title_a: string; title_b: string | null; style_a: string; style_b: string; switched_at?: string; notes?: string[];
  result: { winner: string | null; kept?: string; note: string; views_a?: number; views_b?: number; rate_a?: number; rate_b?: number; z?: number } | null }
export interface Retention { views: number; avg_view_sec: number; avg_view_pct: number; curve: number[]; at: string }
export interface ReadyRow { id: string; label: string; status: "ok" | "warn" | "fail"; detail: string; fix: string }
export interface Readiness { ok: boolean; blocking: boolean; rows: ReadyRow[]; at: string }
export interface CoachChange { id: string; at: string; kind: "defaults" | "clip"; undone: boolean; jid?: string; n?: number; diff: Record<string, { from: string | boolean | null; to: string | boolean | null }> }
export interface RetentionSummary { n: number; avg_view_pct: number; curve: number[]; early_hold: number; end_hold: number; tips: string[] }
export interface ExpSummary { n: number; wins_b: number; tips: string[]; tests: { jid: string; n: number; a: string; b: string | null; kept: string; winner: string | null; note: string }[]; settings?: { enabled: boolean; window_hours: number; thumbnails: boolean } }
export interface CommentRow { id: string; vid: string; channel: string; author: string; text: string; likes: number; replies: number; at: string; status: "new" | "spam" | "answered" | "dismissed" | "held"; why: string; request: string | null; video_title: string;
  draft: { text: string; by: string } | null; replied?: string }
export interface CommentsView { items: CommentRow[]; counts: Record<string, number>; ideas: { idea: string; count: number; likes: number; examples: string[] }[]; last_sync: string | null; sync?: { new: number; needs_reconnect: string[]; drafted: number } }
export interface MusicTrack { id: string; name: string; mood: string; builtin: boolean; duration?: number }
export interface CoachRow { option: string | boolean; n: number; mean: number | null; score?: number; sd?: number; avg_views?: number | null }
export interface CoachInsights { summary: string; do_more: string[]; avoid: string[]; title_tips: string[]; hashtag_tips: string[]; experiments: string[]; by: "ai" | "rules"; n: number; tables: Record<string, CoachRow[]>; retention?: RetentionSummary | null; experiments?: ExpSummary; best: Record<string, string | boolean>; tags: string[]; at: string }
export interface CoachView { mode: "off" | "suggest" | "auto"; dims: Record<string, boolean>; explore: number; last_run: string | null; insights: CoachInsights | null; labels: Record<string, string>; options: Record<string, (string | boolean)[]>; changes?: CoachChange[]; retention_fetch?: { updated: number; needs_reconnect: string[] } }
export interface Stats {
  posted: { job: string; n: number; title: string; youtube_id: string; posted_at?: string; views?: number; likes?: number; privacy?: string }[];
  views: number; refreshed: number; revenue_28d: unknown; note: string;
}

async function studio<T>(path: string, init?: RequestInit): Promise<T> {
  let r: Response;
  try { r = await fetch(`/studio-api${path}`, { ...init, headers: init?.body ? { "Content-Type": "application/json" } : undefined }); } catch { throw new Error("The studio service is not running."); }
  if (!r.ok) throw new Error(`The studio answered ${r.status}.`);
  return (await r.json()) as T;
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let r: Response;
  try {
    r = await fetch(`/studio-api/autoclip${path}`, { ...init, headers: init?.body && typeof init.body === "string" ? { "Content-Type": "application/json" } : undefined });
  } catch {
    throw new Error("The studio service is not running. Start it with: docker compose up -d animation-studio");
  }
  const text = await r.text();
  let data: unknown = null;
  try { data = text ? JSON.parse(text) : null; } catch { /* not JSON */ }
  if (!r.ok) {
    const d = data as { error?: string; detail?: string } | null;
    throw new Error(d?.error || d?.detail || (r.status === 404 ? "The studio doesn't know Auto Clip yet: install the update and restart animation-studio." : `The studio answered ${r.status}.`));
  }
  return data as T;
}
const send = <T,>(method: string, path: string, body?: unknown) => call<T>(path, { method, body: body === undefined ? undefined : JSON.stringify(body) });

export interface LiveStreamer { id?: string; platform: "twitch" | "youtube" | "kick"; handle: string; min_messages: number; lang: "en" | "hi"; permission: boolean; on: boolean;
  url?: string; state?: "offline" | "live" | "error"; since?: string; rate?: number; chat?: boolean; moments?: number; last?: string; error?: string | null; note?: string }
export interface LiveMoment { id: string; streamer: string; at: string; score: number; kind: string; count: number; unique: number; top: string[]; samples: string[]; audio_z: number; job: string | null; error: string | null }
export interface LiveState { running: boolean; streamers: LiveStreamer[]; tools: { streamlink: boolean; ffmpeg: boolean }; moments: LiveMoment[]; settings: Record<string, number | string> }

export interface ExploreItem { id: string; url: string; title: string; channel: string; thumb: string; views: number; seconds: number; published: string; live: boolean; per_hour?: number }
export interface ExploreList { cat: string; region: string; updated: string; source: string; note?: string; items: ExploreItem[]; cats: Record<string, string>; regions: Record<string, string>; mine?: string[]; watching?: string[]; total?: number; length?: string }

export const autoclip = {
  overview: () => call<Overview>(""),
  job: (id: string) => call<Job>(`/jobs/${id}`),
  make: (form: FormData) => call<Job>("/jobs", { method: "POST", body: form }),
  makeFromLink: (b: Record<string, unknown>) => send<Job>("POST", "/jobs", b),
  run: (id: string, fresh = false) => send<Job>("POST", `/jobs/${id}/run${fresh ? "?fresh=true" : ""}`),
  stop: (id: string) => send<{ ok: boolean }>("POST", `/jobs/${id}/stop`),
  remove: (id: string) => send<{ ok: boolean }>("DELETE", `/jobs/${id}`),
  edit: (id: string, n: number, b: Partial<Pick<Clip, "title" | "description" | "approved" | "privacy" | "schedule_at">>) => send<Job>("PATCH", `/jobs/${id}/clips/${n}`, b),
  post: (id: string, n: number) => send<{ youtube_id: string; url: string; job: Job }>("POST", `/jobs/${id}/clips/${n}/post`),
  saveSettings: (s: Partial<Settings>) => send<Overview>("PUT", "/settings", s),
  pause: (paused: boolean) => send<Overview>("POST", "/pause", { paused }),
  setClient: (client_id: string, client_secret: string) => send<Overview>("POST", "/youtube/client", { client_id, client_secret }),
  connect: (origin: string) => call<{ url: string; redirect: string }>(`/youtube/connect?origin=${encodeURIComponent(origin)}`),
  redirect: (origin: string) => call<{ redirect: string }>(`/youtube/redirect?origin=${encodeURIComponent(origin)}`),
  disconnect: (cid: string) => send<{ ok: boolean }>("DELETE", `/youtube/channels/${encodeURIComponent(cid)}`),
  stats: (refresh = false) => call<Stats>(`/stats${refresh ? "?refresh=true" : ""}`),
  crews: () => studio<CrewInfo>("/agents/info"),
  setCrew: (b: { agent: string; model?: string; visionModel?: string }) => studio<CrewInfo>("/agents/settings", { method: "POST", body: JSON.stringify(b) }),
  pull: (model: string) => studio<{ ok: boolean }>("/agents/pull", { method: "POST", body: JSON.stringify({ model }) }),
  reframe: (id: string, n: number, scenes: Record<string, string>) => send<Job>("POST", `/jobs/${id}/clips/${n}/reframe`, { scenes }),
  check: (url: string) => send<RightsCheck>("POST", "/check", { url }),
  explore: (cat: string, region: string, fresh = false, length = "long") => call<ExploreList>(`/explore?cat=${cat}&region=${region}&length=${length}${fresh ? "&fresh=1" : ""}`),
  exploreAdd: (handle: string) => send<{ mine: string[] }>("POST", "/explore/channels", { handle }),
  exploreDel: (handle: string) => send<{ mine: string[] }>("DELETE", `/explore/channels/${encodeURIComponent(handle)}`),
  repack: (jid: string, n: number) => send<Job>("POST", `/jobs/${jid}/clips/${n}/seo`, { fresh: true }),
  fonts: () => call<{ fonts: FontItem[] }>("/fonts"),
  fontAdd: (f: File) => { const d = new FormData(); d.append("file", f); return call<{ fonts: FontItem[]; added: string }>("/fonts", { method: "POST", body: d }); },
  fontDel: (file: string) => send<{ fonts: FontItem[] }>("DELETE", `/fonts/${encodeURIComponent(file)}`),
  fontUrl: (file: string) => `/studio-api/autoclip/fonts/file/${encodeURIComponent(file)}`,
  logoAdd: (f: File) => { const d = new FormData(); d.append("file", f); return call<{ ok: boolean }>("/brand/logo", { method: "POST", body: d }); },
  logoDel: () => send<{ ok: boolean }>("DELETE", "/brand/logo"),
  logoUrl: (v = "") => `/studio-api/autoclip/brand/logo?v=${v}`,
  canvasAdd: (f: File) => { const d = new FormData(); d.append("file", f); return call<{ ok: boolean }>("/brand/canvas", { method: "POST", body: d }); },
  canvasDel: () => send<{ ok: boolean }>("DELETE", "/brand/canvas"),
  avatarAdd: (f: File) => { const d = new FormData(); d.append("file", f); return call<{ ok: boolean }>("/brand/avatar", { method: "POST", body: d }); },
  brands: () => call<{ brands: SavedLook[]; has_logo: boolean; has_canvas?: boolean; has_avatar?: boolean }>("/brands"),
  brandSave: (b: SavedLook) => send<{ brands: SavedLook[] }>("POST", "/brands", b),
  brandDel: (name: string) => send<{ brands: SavedLook[] }>("DELETE", `/brands/${encodeURIComponent(name)}`),
  system: () => call<SystemInfo>("/system"),
  estimate: (minutes: number, opts: Record<string, unknown>) => send<{ low: number; high: number; clips: number }>("POST", "/estimate", { minutes, opts }),
  social: (origin: string) => call<SocialView>(`/social?origin=${encodeURIComponent(origin)}`),
  socialClient: (platform: string, key: string, secret: string) => send<{ ok: boolean }>("POST", `/social/${platform}/client`, { key, secret }),
  socialConnect: (platform: string, origin: string) => call<{ url: string; redirect: string }>(`/social/${platform}/connect?origin=${encodeURIComponent(origin)}`),
  socialDisconnect: (aid: string) => send<{ ok: boolean }>("DELETE", `/social/accounts/${aid}`),
  yt: (refresh = false) => call<YtTab>(`/youtube/tab${refresh ? "?refresh=true" : ""}`),
  ytPlan: (p: Partial<YtPlan> & { channel?: string; reset?: boolean }) => send<YtTab>("PUT", "/youtube/plan", p),
  ytAdd: (b: { items: ({ jid: string; n: number } | { jid: string; all: true } | { upload: string })[]; channels: string[]; mode: "now" | "schedule" | "auto" | "drip" | "every"; gap_hours?: number; gap_min?: number; gap_max?: number; at?: string; privacy?: string }) => send<YtTab & { made: number }>("POST", "/youtube/posts", b),
  ytEdit: (id: string, b: Partial<Pick<YtPost, "title" | "description" | "privacy">> & { at?: string }) => send<YtTab>("PATCH", `/youtube/posts/${id}`, b),
  ytCancel: (id: string) => send<YtTab>("DELETE", `/youtube/posts/${id}`),
  ytRetry: (id: string) => send<YtTab>("POST", `/youtube/posts/${id}/retry`),
  ytNow: (id: string) => send<YtTab>("POST", `/youtube/posts/${id}/now`),
  ytDrip: (channel?: string) => send<YtTab & { set: number }>("POST", "/youtube/posts/drip", { channel, gap_min: 3, gap_max: 5 }),
  ytPrivacy: (privacy: string, channel?: string) => send<YtTab & { set: number }>("POST", "/youtube/posts/privacy", { privacy, channel }),
  live: () => call<LiveState>("/live"),
  liveSave: (streamers: LiveStreamer[]) => send<LiveState>("PUT", "/live/streamers", { streamers }),
  liveStart: () => send<LiveState>("POST", "/live/start"),
  liveStop: () => send<LiveState>("POST", "/live/stop"),
  ytClear: () => send<YtTab>("POST", "/youtube/posts/clear"),
  confirmPermission: (jid: string) => send<{ id: string; permission: string }>("POST", `/jobs/${jid}/permission`, { ack: true }),
  ytUpload: (f: FormData) => call<YtUpload>("/youtube/uploads", { method: "POST", body: f }),
  ytUploadDelete: (id: string) => send<{ ok: boolean }>("DELETE", `/youtube/uploads/${id}`),
  uploadCover: (id: string) => `/studio-api/autoclip/youtube/uploads/${id}/cover`,
  music: () => call<{ tracks: MusicTrack[]; moods: Record<string, string> }>("/music"),
  musicAdd: (f: FormData) => call<MusicTrack>("/music", { method: "POST", body: f }),
  musicDelete: (id: string) => send<{ ok: boolean }>("DELETE", `/music/${encodeURIComponent(id)}`),
  musicPreview: (id: string) => `/studio-api/autoclip/music/${encodeURIComponent(id)}/preview`,
  polish: (id: string, n: number, b: Record<string, string | number | boolean>) => send<Job>("POST", `/jobs/${id}/clips/${n}/edit`, b),
  coach: () => call<CoachView>("/coach"),
  coachSet: (b: { mode?: string; dims?: Record<string, boolean>; explore?: number }) => send<CoachView>("PUT", "/coach", b),
  coachAnalyse: () => send<CoachView>("POST", "/coach/analyse"),
  coachUndo: (id: string) => send<CoachView>("POST", `/coach/changes/${id}/undo`),
  readiness: () => call<Readiness>("/readiness"),
  experiments: () => call<ExpSummary>("/experiments"),
  comments: () => call<CommentsView>("/comments"),
  commentsSync: () => send<CommentsView>("POST", "/comments/sync"),
  commentDraft: (id: string) => send<CommentsView>("POST", `/comments/${id}/draft`),
  commentReply: (id: string, text: string) => send<CommentsView>("POST", `/comments/${id}/reply`, { text }),
  commentAct: (id: string, action: "dismiss" | "release" | "hold") => send<CommentsView>("POST", `/comments/${id}/${action}`),
  coachApply: () => send<{ applied: Record<string, string | boolean>; settings: Settings }>("POST", "/coach/apply"),
  file: (id: string, path: string, v?: string) => `/studio-api/autoclip/jobs/${id}/file/${path}${v ? `?v=${encodeURIComponent(v)}` : ""}`,
};
