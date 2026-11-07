"use client";

export type ModelChoice = { models: Record<string, { model: string }>; local_only: boolean; crew?: string };
export const NO_CHOICE: ModelChoice = { models: {}, local_only: false };

const PICTURES = [["auto", "Automatic"], ["z-image", "Z-Image"], ["qwen-image", "Qwen-Image"], ["flux-schnell", "FLUX schnell"], ["qwen-image-edit", "Qwen-Image-Edit"]];
const VIDEO = [["auto", "Automatic"], ["ltx-2.3", "LTX-2.3"], ["wan-2.2", "Wan 2.2"], ["off", "No video clips (pictures + camera moves)"]];
const TEXT = [["", "Automatic"], ["ollama", "Ollama (on this PC)"], ["groq", "Groq (cloud)"]];

/** Choose a model for a step and ONLY that model is used. Automatic lets the studio pick (and fall back). */
export function ModelPicker({ value, onChange }: { value: ModelChoice; onChange: (v: ModelChoice) => void }) {
  const set = (step: string, model: string) => onChange({ ...value, models: { ...value.models, [step]: { model } } });
  const sel = "w-full rounded-xl border border-border bg-background px-3 py-2 text-sm";
  const row = (label: string, step: string, opts: string[][]) => (
    <label className="block text-sm">
      <span className="mb-1 block text-xs font-semibold uppercase tracking-wider text-muted-foreground">{label}</span>
      <select className={sel} value={value.models[step]?.model ?? "auto"} onChange={(e) => set(step, e.target.value)} data-testid={`model-${step}`}>
        {opts.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
    </label>
  );
  return (
    <details className="mt-6 rounded-xl border border-border p-4 text-sm">
      <summary className="cursor-pointer font-medium">Models (optional)</summary>
      <p className="mt-2 text-muted-foreground">Pick a model and only that model is used — no silent switch to fal.ai, Cloudflare or another model. If it can’t run, you’ll see exactly why.</p>
      <div className="mt-3 grid gap-3 sm:grid-cols-3">
        {row("Pictures", "pictures", PICTURES)}
        {row("Video", "motion", VIDEO)}
        <label className="block text-sm">
          <span className="mb-1 block text-xs font-semibold uppercase tracking-wider text-muted-foreground">Script writer (text AI)</span>
          <select className={sel} value={value.crew ?? ""} onChange={(e) => onChange({ ...value, crew: e.target.value })} data-testid="model-crew">
            {TEXT.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
      </div>
      <label className="mt-3 flex items-start gap-3">
        <input type="checkbox" checked={value.local_only} onChange={(e) => onChange({ ...value, local_only: e.target.checked })} className="mt-1 h-4 w-4" data-testid="model-local" />
        <span><span className="font-medium">This PC only</span>
          <span className="block text-muted-foreground">Pictures and video may run only on your own GPU worker / ComfyUI — never on fal.ai or Cloudflare. Downloaded models need a GPU worker online; Ollama only writes text.</span></span>
      </label>
    </details>
  );
}

/** What to send to the API: only the parts the person changed. */
export function choiceBody(v: ModelChoice) {
  const models = Object.fromEntries(Object.entries(v.models).filter(([, m]) => m.model !== "auto"));
  return { models, local_only: v.local_only, ...(v.crew ? { crew: v.crew } : {}) };
}
