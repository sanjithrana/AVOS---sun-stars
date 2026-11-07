"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { Loader2, Sparkles } from "lucide-react";
import { stickman, type StyleInfo } from "@/lib/stickman";
import { ModelPicker, NO_CHOICE, choiceBody, type ModelChoice } from "@/components/shared/ModelPicker";

const LENGTHS = { director: [30, 60, 90, 120], autopilot: [60, 120, 180, 300] } as const;
const label = (s: number) => (s < 60 ? `${s} s` : `${s / 60} min`);
const chip = (on: boolean) => `rounded-full border px-4 py-2 text-sm transition-colors ${on ? "border-[rgba(185,172,255,0.7)] bg-[rgba(124,92,255,0.18)] text-foreground" : "border-border text-muted-foreground hover:text-foreground"}`;

/** The brief, the way Stickman Video Director takes it: a topic, a pasted copy or script, or a description of what you need,
 *  plus the requirements (look, shape, length, narrator). The director's treatment comes first, for your approval. */
export function Composer({ style }: { style: StyleInfo | null }) {
  const router = useRouter();
  const [text, setText] = useState("");
  const [interest, setInterest] = useState("");
  const [aspect, setAspect] = useState("9:16");
  const [seconds, setSeconds] = useState(60);
  const [voice, setVoice] = useState<"male" | "female">("male");
  const [auto, setAuto] = useState(false);
  const [pick, setPick] = useState<ModelChoice>(NO_CHOICE);
  const mode = style?.mode ?? "director";
  useEffect(() => { if (!(LENGTHS[mode] as readonly number[]).includes(seconds)) setSeconds(60); }, [mode, seconds]);
  const create = useMutation({ mutationFn: stickman.create, onSuccess: (p) => router.push(`/stickman/${p.id}`) });
  const named = text.trim().length > 2;
  const words = text.trim() ? text.trim().split(/\s+/).length : 0;

  return (
    <section className="composer rounded-3xl border border-border p-5 sm:p-8" data-testid="stickman-composer">
      <p className="text-xs text-muted-foreground">{style ? <>Skill <b className="text-foreground">{style.code} · {style.name}</b> · {mode === "autopilot" ? "B · Autopilot" : "A · Director"}</> : "Pick a skill on the left"}</p>
      <h1 className="display mt-2 text-3xl md:text-4xl">Turn a topic, copy or brief into a stickman video</h1>
      <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
        {mode === "autopilot"
          ? "Autopilot: give it a topic or a brief and get a finished narrated video: illustrations with subtle motion, voiceover, captions and sound. Long-form first."
          : "Director: you get the director's treatment first (story, narration, music). After you approve it, the cast and every 10-second clip, each with its own prompt you can take to Flow, Kling or Runway."}
      </p>

      {style?.native_audio && (
        <p className="mt-4 rounded-2xl border border-[rgba(185,172,255,0.35)] p-3 text-xs leading-relaxed text-muted-foreground" data-testid="native-note">
          This skill works like SJinn&apos;s Amber Noir: a director&apos;s proposal and continuity bible first, then an identity sheet, a location reference and an opening image per clip,
          each checked. Clips are made by Seedance 2.0 from those references with its own narration, music and sound, and joined with no titles or subtitles.
          Needs a fal.ai key with credit (Settings); without it the clips fall back to pictures with camera moves and a separate voice.
        </p>
      )}
      <label htmlFor="stickman-brief" className="field-label mb-2 mt-6 block">Topic, copy or brief</label>
      <textarea id="stickman-brief" value={text} onChange={(e) => setText(e.target.value)} rows={5} data-testid="stickman-event"
        placeholder={style?.history ? "Enter a topic, paste your copy, or describe what you need. e.g. The Great Stink of London, 1858" :
          "Enter a topic, paste your copy, or describe what you need. e.g. Why perfectionism makes you slower, or paste an article or a full script"}
        className="prompt-field w-full resize-y rounded-2xl border border-border p-4 text-base leading-relaxed outline-none" />
      <p className="mt-1.5 text-xs text-muted-foreground">
        {!named ? "Leave it empty and the director suggests eight ideas for this skill." : words > 25 ? `${words} words: treated as your copy; its meaning, names and numbers are kept.` : "A topic: the director researches it and writes the story."}
      </p>
      {!named && (
        <input value={interest} onChange={(e) => setInterest(e.target.value)} placeholder="Steer the eight ideas, e.g. engineering, money habits, ancient Asia"
          className="mt-3 w-full rounded-2xl border border-border p-3 text-sm outline-none" />
      )}

      <div className="mt-6 grid gap-5 lg:grid-cols-3">
        <div>
          <p className="field-label mb-2">Shape</p>
          <div className="flex flex-wrap gap-2">
            {[["9:16", "9:16 Vertical"], ["16:9", "16:9 Landscape"], ["1:1", "1:1 Square"]].map(([v, l]) => (
              <button key={v} type="button" onClick={() => setAspect(v)} aria-pressed={aspect === v} className={chip(aspect === v)}>{l}</button>
            ))}
          </div>
        </div>
        <div>
          <p className="field-label mb-2">Length</p>
          <div className="flex flex-wrap gap-2">
            {LENGTHS[mode].map((n) => (
              <button key={n} type="button" onClick={() => setSeconds(n)} aria-pressed={seconds === n} className={chip(seconds === n)}>{label(n)}</button>
            ))}
          </div>
          <p className="mt-1.5 text-[11px] text-muted-foreground">{seconds / 10} clips of 10 seconds, about {Math.round(seconds * 2.2)} narration words.</p>
        </div>
        <div>
          <p className="field-label mb-2">Narrator</p>
          <div className="flex flex-wrap gap-2">
            {([["male", "Warm male"], ["female", "Clear female"]] as const).map(([v, l]) => (
              <button key={v} type="button" onClick={() => setVoice(v)} aria-pressed={voice === v} className={chip(voice === v)}>{l}</button>
            ))}
          </div>
          <p className="mt-1.5 text-[11px] text-muted-foreground">One frozen voice for every clip.</p>
        </div>
      </div>

      <ModelPicker value={pick} onChange={setPick} />

      <label className="mt-5 flex items-start gap-3 rounded-2xl border border-border p-4 text-sm">
        <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} className="mt-1 h-4 w-4" />
        <span><span className="font-medium">Do everything without asking me</span>
          <span className="block text-muted-foreground">Off: you choose the idea, approve the director&apos;s treatment, then the character sheets, before any scene is made. On: straight to the video.</span></span>
      </label>
      {create.isError && <p className="mt-4 rounded-xl border border-red-500/40 bg-red-500/5 p-3 text-sm" role="alert">{(create.error as Error).message}</p>}
      <button type="button" disabled={create.isPending || !style}
        onClick={() => create.mutate({ event: named ? text.trim() : undefined, interest: named ? undefined : interest.trim() || undefined, aspect, auto, style: style?.id, seconds, voice, ...choiceBody(pick) })}
        className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-full bg-primary px-8 py-3.5 font-semibold text-white disabled:opacity-50 sm:w-auto" data-testid="stickman-create">
        {create.isPending ? <Loader2 className="h-5 w-5 animate-spin" /> : <Sparkles className="h-5 w-5" />}{named ? (auto ? "Make the video" : "Write the director's treatment") : "Show me eight ideas"}
      </button>
    </section>
  );
}
