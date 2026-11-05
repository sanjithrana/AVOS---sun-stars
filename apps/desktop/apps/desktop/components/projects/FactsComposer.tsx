"use client";

// Facts → "New video": an inline composer (same layout as the Animations tab's "New animation" card).
// Topic first; style, length, shape and the text / image / video models as chips; models you added in
// Settings appear under "Your models".
import Link from "next/link";
import { forwardRef, useImperativeHandle, useMemo, useRef, useState, type ReactNode } from "react";
import {
  BookOpen, Clapperboard, Clock, DollarSign, Gauge, Image as ImageIcon, Loader2, Monitor, Mic, Palette, Search, Settings2,
  Sparkles, Video, Wand2,
} from "lucide-react";
import { useModels } from "@/hooks/queries";
import {
  IMAGE_PROVIDERS, IMAGE_TO_VIDEO_PROVIDERS, LLM_PROVIDERS, PREFERENCE_LABEL, STYLE_PRESETS, VIDEO_PROVIDERS, groupOptions,
  type AspectRatio, type CatalogModel, type ModelsStatus, type Preference, type ProjectCreate,
} from "@/types";

const VIDEO_HINTS: Record<string, string> = {
  motion: "Free. Each shot's picture gets a smooth camera move.",
  fal: "Kling clips on fal.ai (FAL_KEY); ~$0.25 per shot.",
  replicate: "AI clips on Replicate (REPLICATE_API_TOKEN).",
  comfyui: "Your GPU's ComfyUI with apps/comfyui_workflows/video.json.",
  local: "Your own video service at VIDEO_SERVICE_URL.",
  "": "No clips: the final render animates each shot's picture.",
  best: "The Model Router picks per shot (Wan 2.2, LTX-2.3…) and where it runs, by your Priority; free camera motion when no model is set up.",
  "wan-2.2": "Wan 2.2 animates each shot's picture.",
  "ltx-2.3": "LTX-2.3 makes each shot follow its part of the narration.",
  "wan-vace": "Wan VACE keeps characters and look consistent between shots.",
  avatar: "A presenter (made once per project) speaks each shot's narration, lip-synced.",
  "longcat-avatar": "LongCat Avatar: a presenter speaks each shot's narration.",
  infinitetalk: "InfiniteTalk: a presenter speaks the narration; built for long takes.",
};

const SUGGEST = [
  "Why the moon changes shape",
  "What would happen if you stopped sleeping for a week",
  "How octopuses see without colour vision",
  "The hidden science of a cup of coffee",
];
const HOW: [typeof Search, string, string][] = [
  [Search, "Research", "Facts gathered and checked for your topic"],
  [BookOpen, "Script & approval", "You approve the script before anything is made"],
  [Mic, "Voice & shots", "Narration, then a picture and clip per shot"],
  [Clapperboard, "Final video", "Captions, music and the finished MP4"],
];

/** "Ready on …" / "Not set up yet: …" + licence for an option backed by a catalog model or one you added. */
export function ModelNote({ modelId, models }: { modelId?: string; models?: ModelsStatus }) {
  if (!modelId) return null;
  const m = models?.models.find((x) => x.id === modelId);
  if (!m) return null;
  const where = m.backend === "gpu" ? "your GPU workers (the router picks GPU and precision)" : m.backend === "comfyui" ? "your GPU server" : m.backend === "fal" ? "fal.ai (paid)" : m.backend === "cloudflare" ? "Cloudflare (free tier)" : m.backend;
  return (
    <span className="block" data-testid={`model-note-${modelId}`}>
      {m.ready ? <span className="text-emerald-500">Ready on {where}.</span> : <span className="text-amber-500">Not set up yet: {m.missing}</span>}{" "}
      <span className={m.commercial === "conditional" ? "text-amber-400" : ""}>
        Licence: {m.license}{m.commercial === "conditional" ? " (conditions for commercial use)" : ""}.
      </span>{" "}
      <Link href={m.custom ? "/settings" : "/models"} className="underline hover:text-foreground">{m.custom ? "Settings" : "Models"}</Link>
    </span>
  );
}

type Opt = { value: string; label: string; group: string; model?: string };

function Chip({ icon, label, children }: { icon: ReactNode; label: string; children: ReactNode }) {
  return (
    <label className="flex min-w-0 items-center gap-2 rounded-xl border border-border bg-background px-3 py-2 text-sm transition-colors focus-within:border-amber-500/50 focus-within:ring-2 focus-within:ring-amber-500/30">
      <span className="flex shrink-0 items-center gap-1.5 text-muted-foreground">{icon}<span className="text-xs">{label}</span></span>
      {children}
    </label>
  );
}

const selectClass = "min-w-0 flex-1 cursor-pointer truncate bg-transparent text-sm text-foreground focus:outline-none [&>optgroup]:bg-background [&>option]:bg-background";

function Select({ id, value, onChange, options, label }: { id: string; value: string; onChange: (v: string) => void; options: Opt[]; label: string }) {
  return (
    <select id={id} aria-label={label} value={value} onChange={(e) => onChange(e.target.value)} className={selectClass}>
      {groupOptions(options).map(([group, opts]) => (
        <optgroup key={group} label={group}>
          {opts.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </optgroup>
      ))}
    </select>
  );
}

export interface FactsComposerHandle { focus: () => void }

interface Props {
  onSubmit: (data: ProjectCreate) => void | Promise<void>;
  isSubmitting?: boolean;
  error?: string | null;
}

export const FactsComposer = forwardRef<FactsComposerHandle, Props>(function FactsComposer({ onSubmit, isSubmitting = false, error }, ref) {
  const [topic, setTopic] = useState("");
  const [name, setName] = useState("");
  const [duration, setDuration] = useState("30");
  const [aspectRatio, setAspectRatio] = useState<AspectRatio>("9:16");
  const [budget, setBudget] = useState("");
  const [llmProvider, setLlmProvider] = useState("");
  // Best quality by default: the best open model per picture and per shot (on your GPU server or fal.ai), falling
  // back to the free picture chain and camera motion when none is set up, so every project still ends in a video.
  const [imageProvider, setImageProvider] = useState("best");
  const [videoProvider, setVideoProvider] = useState("best");
  const [stylePreset, setStylePreset] = useState("viral_3d");
  // Model Fabric priority for this project ("" = the defaults on the GPU page)
  const [priority, setPriority] = useState("");
  const [reviewShots, setReviewShots] = useState(false);
  const topicRef = useRef<HTMLTextAreaElement>(null);
  useImperativeHandle(ref, () => ({ focus: () => { topicRef.current?.scrollIntoView({ behavior: "smooth", block: "center" }); topicRef.current?.focus(); } }));
  const { data: models } = useModels();

  // models added on the Settings page join the pickers
  const custom = useMemo(() => (models?.models ?? []).filter((m: CatalogModel) => m.custom), [models]);
  const mine = (tasks: string[]): Opt[] => custom.filter((m) => tasks.includes(m.task)).map((m) => ({ value: m.id, label: `${m.name} (yours)`, group: "Your models (Settings)", model: m.id }));
  const llmOptions: Opt[] = [...LLM_PROVIDERS.map((p) => ({ ...p, group: "Built in" })), ...mine(["llm"])];
  const imageOptions: Opt[] = [...IMAGE_PROVIDERS, ...mine(["image"])];
  const videoOptions: Opt[] = [...VIDEO_PROVIDERS.filter((p) => !("hidden" in p)), ...mine(["video", "avatar"])];
  const imageOpt = imageOptions.find((p) => p.value === imageProvider);
  const videoOpt = videoOptions.find((p) => p.value === videoProvider);
  const customVideo = custom.find((m) => m.id === videoProvider);

  const durationNum = Number.parseInt(duration, 10);
  const budgetNum = budget.trim() === "" ? null : Number.parseFloat(budget);
  const durationValid = Number.isFinite(durationNum) && durationNum >= 5 && durationNum <= 300;
  const budgetValid = budgetNum === null || (Number.isFinite(budgetNum) && budgetNum > 0);
  const canSubmit = topic.trim().length > 0 && durationValid && budgetValid && !isSubmitting;

  const submit = () => {
    if (!canSubmit) return;
    onSubmit({
      name: (name.trim() || topic.trim()).slice(0, 255),
      topic: topic.trim(),
      duration: durationNum,
      aspect_ratio: aspectRatio,
      budget_limit: budgetNum,
      llm_provider: llmProvider || null,
      image_provider: imageProvider || null,
      video_provider: videoProvider || null,
      style_preset: stylePreset,
      generation_policy: priority || reviewShots
        ? { ...(priority ? { preference: priority as Preference } : {}), ...(reviewShots ? { review_shots: true } : {}) }
        : null,
    });
  };

  return (
    <div>
      <form
        onSubmit={(e) => { e.preventDefault(); submit(); }}
        className="rounded-2xl border border-border bg-card/50 p-4 transition-colors focus-within:border-amber-500/40 md:p-5"
        data-testid="facts-composer"
      >
        <textarea
          ref={topicRef}
          id="topic"
          aria-label="Topic"
          rows={3}
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit(); }}
          placeholder="What's your video about? A topic, a question, a fact… e.g. Why the moon changes shape"
          className="block w-full resize-none rounded-xl border border-border bg-background px-4 py-3 text-[15px] leading-relaxed text-foreground placeholder:text-muted-foreground focus:border-amber-500/50 focus:outline-none"
        />

        <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-4">
          <Chip icon={<Palette className="h-4 w-4" />} label="Style">
            <select id="style-preset" aria-label="Style" value={stylePreset} onChange={(e) => setStylePreset(e.target.value)} className={selectClass}>
              {STYLE_PRESETS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
            </select>
          </Chip>
          <Chip icon={<Clock className="h-4 w-4" />} label="Length">
            <input id="duration" aria-label="Duration (sec)" type="number" min={5} max={300} value={duration} onChange={(e) => setDuration(e.target.value)}
              className={`w-16 bg-transparent text-sm focus:outline-none ${durationValid ? "text-foreground" : "text-red-400"}`} />
            <span className="text-xs text-muted-foreground">sec</span>
          </Chip>
          <Chip icon={<Monitor className="h-4 w-4" />} label="Shape">
            <select id="aspect-ratio" aria-label="Aspect ratio" value={aspectRatio} onChange={(e) => setAspectRatio(e.target.value as AspectRatio)} className={selectClass}>
              <option value="9:16">9:16 Shorts</option>
              <option value="16:9">16:9 YouTube</option>
              <option value="1:1">1:1 Square</option>
            </select>
          </Chip>
          <Chip icon={<DollarSign className="h-4 w-4" />} label="Budget">
            <input id="budget" aria-label="Budget limit (USD)" type="number" min={0} step="0.01" placeholder="no limit" value={budget} onChange={(e) => setBudget(e.target.value)}
              className={`w-full bg-transparent text-sm placeholder:text-muted-foreground focus:outline-none ${budgetValid ? "text-foreground" : "text-red-400"}`} />
          </Chip>
        </div>

        <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-4">
          <Chip icon={<Wand2 className="h-4 w-4" />} label="Text AI">
            <Select id="llm-provider" label="Text AI" value={llmProvider} onChange={setLlmProvider} options={llmOptions} />
          </Chip>
          <Chip icon={<ImageIcon className="h-4 w-4" />} label="Pictures">
            <Select id="image-provider" label="Image" value={imageProvider} onChange={setImageProvider} options={imageOptions} />
          </Chip>
          <Chip icon={<Video className="h-4 w-4" />} label="Video">
            <Select id="video-provider" label="Video" value={videoProvider} onChange={setVideoProvider} options={videoOptions} />
          </Chip>
          <Chip icon={<Gauge className="h-4 w-4" />} label="Priority">
            <select id="priority" aria-label="Priority" value={priority} onChange={(e) => setPriority(e.target.value)} className={selectClass} title="How the router trades quality, speed and cost for each shot">
              <option value="">Default (GPU page)</option>
              {(Object.keys(PREFERENCE_LABEL) as Preference[]).map((p) => <option key={p} value={p}>{PREFERENCE_LABEL[p]}</option>)}
            </select>
          </Chip>
        </div>

        <div className="mt-2 space-y-1 px-1 text-xs text-muted-foreground">
          <p data-testid="video-provider-hint">
            {VIDEO_HINTS[videoProvider] ?? (customVideo ? `${customVideo.name}: your ${customVideo.task === "avatar" ? "presenter" : "video"} model from Settings.` : "")}
            {(IMAGE_TO_VIDEO_PROVIDERS.includes(videoProvider) || customVideo) && !imageProvider ? " Pictures: free auto (Cloudflare, then Pollinations) unless you pick one." : ""}
          </p>
          {videoOpt?.model && <ModelNote modelId={videoOpt.model} models={models} />}
          {imageOpt?.model && <span data-testid="image-provider-hint"><ModelNote modelId={imageOpt.model} models={models} /></span>}
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-border pt-4">
          <input id="name" aria-label="Project title (optional)" value={name} onChange={(e) => setName(e.target.value)} placeholder="Title (optional, defaults to the topic)"
            className="min-w-0 flex-1 rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-amber-500/50 focus:outline-none sm:max-w-xs" />
          <label className="flex items-center gap-2 rounded-xl px-2 py-2 text-sm text-muted-foreground" title="Pause after QA so you can check (and edit) every shot before the final video is made">
            <input type="checkbox" className="h-4 w-4 accent-amber-500" checked={reviewShots} onChange={(e) => setReviewShots(e.target.checked)} data-testid="review-shots" />
            Review shots first
          </label>
          <Link href="/settings" className="flex items-center gap-1.5 rounded-xl px-3 py-2 text-sm text-muted-foreground hover:bg-muted hover:text-foreground">
            <Settings2 className="h-4 w-4" /> Keys, GPU &amp; your models
          </Link>
          <span className="flex-1" />
          <button
            type="submit"
            disabled={!canSubmit}
            className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-amber-500/25 transition-all hover:from-amber-600 hover:to-orange-600 disabled:cursor-not-allowed disabled:from-muted disabled:to-muted disabled:text-muted-foreground disabled:shadow-none"
          >
            {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            Create Project
          </button>
        </div>
        {error && <p role="alert" className="mt-3 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400">{error}</p>}
      </form>

      <p className="mt-3 text-center text-xs text-muted-foreground">
        {!topic.trim() ? "Write a topic to start" : "Research and the script come first — you approve before anything is generated"} · Ctrl+Enter to create
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        {SUGGEST.map((s) => (
          <button key={s} type="button" onClick={() => { setTopic(s); topicRef.current?.focus(); }}
            className="rounded-xl border border-border px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:border-amber-500/40 hover:text-foreground">
            {s}
          </button>
        ))}
      </div>
      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {HOW.map(([Icon, t, d], i) => (
          <div key={t} className="flex gap-3 rounded-xl border border-border bg-card/30 p-3">
            <span className="flex h-8 w-8 flex-none items-center justify-center rounded-lg bg-amber-500/10 text-amber-500"><Icon className="h-4 w-4" /></span>
            <span className="min-w-0"><b className="block text-sm font-semibold text-foreground">{i + 1}. {t}</b><span className="text-xs text-muted-foreground">{d}</span></span>
          </div>
        ))}
      </div>
    </div>
  );
});
