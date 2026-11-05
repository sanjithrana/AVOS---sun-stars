"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Loader2, Sparkles, TriangleAlert } from "lucide-react";
import { explainer, type Voice } from "@/lib/explainer";
import { VoicePicker } from "./VoicePicker";
import { StylePicker } from "./StylePicker";
import { ModelPicker, NO_CHOICE, choiceBody, type ModelChoice } from "@/components/shared/ModelPicker";

const LENGTHS = [15, 30, 45, 60];
const EXAMPLES = ["Why can a straw go through a potato?", "What happens if you drop a magnet down a copper pipe?", "How does a plane stay in the air?"];

/** The whole input: one idea. Everything else (style, characters, shots, models, voice) is chosen by the studio. */
export function Composer() {
  const router = useRouter();
  const [brief, setBrief] = useState("");
  const [seconds, setSeconds] = useState(30);
  const [aspect, setAspect] = useState("9:16");
  const [mode2, setMode2] = useState<"ask" | "auto" | null>(null);          // Autopilot: you choose before anything starts
  const auto = mode2 === "auto";
  const [research, setResearch] = useState(true);
  const [from, setFrom] = useState<"idea" | "article">("idea");
  const [url, setUrl] = useState("");
  const [mode, setMode] = useState("summarize");
  const [styleId, setStyleId] = useState("auto");
  const [voice, setVoice] = useState<Voice | null>(null);
  const styles = useQuery({ queryKey: ["explainer-styles"], queryFn: explainer.styles, retry: false, staleTime: 600000 });
  const preview = useMutation({ mutationFn: () => explainer.articlePreview(url.trim()) });
  const [pick, setPick] = useState<ModelChoice>(NO_CHOICE);
  const caps = useQuery({ queryKey: ["explainer-caps"], queryFn: explainer.caps, retry: false });
  const body = choiceBody(pick);
  const est = useQuery({ queryKey: ["explainer-estimate", seconds, JSON.stringify(body)], queryFn: () => explainer.estimate({ seconds, models: body.models, local_only: body.local_only }), retry: false, staleTime: 30000 });
  const input = from === "idea" ? brief.trim().length >= 3 : /^https?:\/\//i.test(url.trim());
  const ready = input && mode2 !== null;
  const create = useMutation({ mutationFn: explainer.create, onSuccess: (p) => router.push(`/explainer/${p.id}`) });

  return (
    <section className="composer rounded-3xl border border-border p-5 sm:p-8">
      <h1 className="display text-3xl md:text-4xl">What should the video explain?</h1>
      <p className="mt-1 text-sm text-muted-foreground">Type one idea. The studio writes the script, designs the presenter and props, picks a way to make each shot, adds voice and captions, and gives you one finished video.</p>
      <div className="mt-5 inline-flex rounded-xl border border-border p-1 text-sm" role="tablist" aria-label="Start from">
        {([["idea", "An idea"], ["article", "An article link"]] as const).map(([v, l]) => (
          <button key={v} type="button" role="tab" aria-selected={from === v} onClick={() => setFrom(v)} data-testid={`explainer-from-${v}`}
            className={`rounded-lg px-4 py-1.5 transition-colors ${from === v ? "bg-amber-500 text-white" : "text-muted-foreground hover:bg-accent"}`}>{l}</button>
        ))}
      </div>
      {from === "article" ? (
        <div className="mt-3 space-y-3">
          <div className="flex gap-2">
            <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://example.com/article" inputMode="url"
              className="min-w-0 flex-1 rounded-xl border border-border bg-background p-4 outline-none focus:border-amber-500" data-testid="explainer-url" />
            <button type="button" disabled={!ready || preview.isPending} onClick={() => preview.mutate()}
              className="rounded-xl border border-border px-4 text-sm transition hover:bg-accent disabled:opacity-50">{preview.isPending ? "Reading…" : "Preview"}</button>
          </div>
          {preview.isError && <p className="text-sm text-red-600" role="alert">{(preview.error as Error).message}</p>}
          {preview.data && (
            <div className="animate-in fade-in rounded-xl border border-border p-4 text-sm">
              <p className="font-semibold">{preview.data.title}</p>
              <p className="text-xs text-muted-foreground">{preview.data.words} words · about {preview.data.readMinutes} min to read</p>
              <p className="mt-2 line-clamp-4 text-muted-foreground">{preview.data.excerpt}</p>
            </div>
          )}
          <div className="flex flex-wrap gap-2">
            {[["summarize", "Summarize"], ["explain", "Explain simply"], ["story", "As a story"], ["highlights", "Key points"]].map(([v, l]) => (
              <button key={v} type="button" onClick={() => setMode(v)} aria-pressed={mode === v}
                className={`rounded-md border px-3 py-1 text-xs transition-colors ${mode === v ? "border-amber-500 bg-amber-500/15" : "border-border hover:bg-accent"}`}>{l}</button>
            ))}
          </div>
          <p className="text-xs text-muted-foreground">The script uses only facts from the article. This needs an AI script writer (Ollama or Groq under Models).</p>
        </div>
      ) : (
      <>
      <textarea
        value={brief}
        onChange={(e) => setBrief(e.target.value)}
        placeholder="One idea, or a full brief: title, duration, style, narration style and numbered scenes. The studio follows what you write."
        rows={5}
        className="prompt-field mt-5 w-full resize-none rounded-2xl border border-border p-4 text-base leading-relaxed outline-none sm:text-lg"
        data-testid="explainer-brief"
      />
      <div className="mt-2 flex flex-wrap gap-2">
        {EXAMPLES.map((x) => (
          <button key={x} type="button" onClick={() => setBrief(x)} className="rounded-full border border-border px-3 py-1 text-xs text-muted-foreground transition-colors hover:text-foreground">{x}</button>
        ))}
      </div>

      </>
      )}

      <div className="mt-6 grid gap-5 sm:grid-cols-2">
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Length</p>
          <div className="flex flex-wrap gap-2">
            {LENGTHS.map((n) => (
              <button key={n} type="button" onClick={() => setSeconds(n)} aria-pressed={seconds === n}
                className={`rounded-lg border px-4 py-2 text-sm ${seconds === n ? "border-amber-500 bg-amber-500/15 text-amber-700 dark:text-amber-300" : "border-border hover:bg-accent"}`}>{n} s</button>
            ))}
          </div>
        </div>
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Shape</p>
          <div className="flex flex-wrap gap-2">
            {[["9:16", "Vertical (Shorts, Reels)"], ["16:9", "Wide (YouTube)"], ["1:1", "Square"]].map(([v, l]) => (
              <button key={v} type="button" onClick={() => setAspect(v)} aria-pressed={aspect === v}
                className={`rounded-lg border px-4 py-2 text-sm ${aspect === v ? "border-amber-500 bg-amber-500/15 text-amber-700 dark:text-amber-300" : "border-border hover:bg-accent"}`}>{l}</button>
            ))}
          </div>
        </div>
      </div>

      <p className="mb-2 mt-6 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Look</p>
      <StylePicker styles={styles.data ?? [{ id: "auto", name: "Auto" }]} value={styleId} onChange={setStyleId} />
      <VoicePicker value={voice} onChange={setVoice} />

      {from === "idea" && (
        <label className="mt-6 flex items-start gap-3 rounded-xl border border-border p-4 text-sm" data-testid="research-toggle">
          <input type="checkbox" checked={research} onChange={(e) => setResearch(e.target.checked)} className="mt-1 h-4 w-4" />
          <span>
            <span className="font-medium">Check the facts first</span>
            <span className="block text-muted-foreground">Looks the topic up on Wikipedia, keeps each fact with its source link, and the script may only use those facts. Short ideas only; if the web is unreachable it is skipped and you are told why.</span>
          </span>
        </label>
      )}

      <fieldset className="mt-3" data-testid="autopilot-choice">
        <legend className="text-sm font-medium">Autopilot: how should it run? <span className="font-normal text-muted-foreground">(pick one to start)</span></legend>
        <div className="mt-2 grid gap-3 sm:grid-cols-2">
          {([
            ["ask", "Ask me at each step", "It researches, writes the script and builds the story, then stops for your OK on the script, the characters and backgrounds, and the scene storyboard. After that it makes the voices, video, lip-sync and music by itself."],
            ["auto", "Fully automatic", "No stops. Idea in, finished video out. You review the result and rate it, and the prompts learn from that."],
          ] as const).map(([id, title, text]) => (
            <label key={id} className={`cursor-pointer rounded-xl border p-4 text-sm transition-colors ${mode2 === id ? "border-amber-500 bg-amber-500/10" : "border-border hover:bg-accent"}`}>
              <input type="radio" name="autopilot" value={id} checked={mode2 === id} onChange={() => setMode2(id)} className="sr-only" data-testid={`autopilot-${id}`} />
              <span className="font-medium">{title}</span>
              <span className="mt-1 block text-muted-foreground">{text}</span>
            </label>
          ))}
        </div>
      </fieldset>

      <ModelPicker value={pick} onChange={setPick} />

      {est.data && (
        <p className="mt-4 rounded-xl border border-border p-3 text-sm" data-testid="explainer-estimate">
          <b>Estimated cost: {est.data.usd_high === 0 ? "free" : `about $${est.data.usd_low.toFixed(2)}–$${est.data.usd_high.toFixed(2)}`}</b>
          <span className="block text-xs text-muted-foreground">{est.data.shots} shots · {est.data.video_shots} AI video clips. {est.data.note}</span>
        </p>
      )}

      {caps.data?.hint && (
        <p className="mt-4 flex items-start gap-2 rounded-xl border border-amber-500/40 bg-amber-500/5 p-3 text-sm text-amber-800 dark:text-amber-200">
          <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />{caps.data.hint}
        </p>
      )}
      {caps.isError && <p className="mt-4 rounded-xl border border-amber-500/40 bg-amber-500/5 p-3 text-sm">{(caps.error as Error).message}</p>}
      {create.isError && <p className="mt-4 rounded-xl border border-red-500/40 bg-red-500/5 p-3 text-sm text-red-700 dark:text-red-300" role="alert">{(create.error as Error).message}</p>}

      <button type="button" disabled={!ready || create.isPending}
        onClick={() => create.mutate({ ...(from === "article" ? { url: url.trim(), mode } : { brief: brief.trim(), research }), seconds, aspect, auto, style_id: styleId, ...(voice ? { voice_id: voice.id, language: voice.locale.split("-")[0] } : {}), ...body })}
        className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-full bg-primary px-8 py-3.5 font-semibold text-white transition-all duration-200 active:scale-[0.98] disabled:opacity-50 sm:w-auto"
        data-testid="explainer-create">
        {create.isPending ? <Loader2 className="h-5 w-5 animate-spin" /> : <Sparkles className="h-5 w-5" />} Make my video
      </button>
    </section>
  );
}
