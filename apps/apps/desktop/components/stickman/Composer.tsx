"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { Loader2, Sparkles } from "lucide-react";
import { stickman } from "@/lib/stickman";
import { ModelPicker, NO_CHOICE, choiceBody, type ModelChoice } from "@/components/shared/ModelPicker";

/** Two ways in: name an event, or leave it empty and pick from eight ideas. Everything else is chosen by the studio. */
export function Composer() {
  const router = useRouter();
  const [event, setEvent] = useState("");
  const [interest, setInterest] = useState("");
  const [aspect, setAspect] = useState("9:16");
  const [auto, setAuto] = useState(false);
  const [pick, setPick] = useState<ModelChoice>(NO_CHOICE);
  const create = useMutation({ mutationFn: stickman.create, onSuccess: (p) => router.push(`/stickman/${p.id}`) });
  const named = event.trim().length > 2;

  return (
    <section className="rounded-3xl border border-border bg-card/50 p-6 md:p-8">
      <h1 className="text-2xl font-bold md:text-3xl">Which moment in history?</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Flat 2D stickman history videos: six 10-second clips, narration, captions, and a full written package (fact brief, character sheets, a prompt for every clip).
        Name an event, or leave the box empty and choose from eight ideas.
      </p>
      <input value={event} onChange={(e) => setEvent(e.target.value)} placeholder="e.g. The Great Stink of London, 1858  (optional)"
        className="mt-5 w-full rounded-2xl border border-border bg-background p-4 text-lg outline-none focus:border-amber-500" data-testid="stickman-event" />
      {!named && (
        <input value={interest} onChange={(e) => setInterest(e.target.value)} placeholder="Any interest to steer the eight ideas? e.g. engineering, women in history, ancient Asia"
          className="mt-3 w-full rounded-2xl border border-border bg-background p-3 text-sm outline-none focus:border-amber-500" />
      )}
      <div className="mt-5">
        <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Shape</p>
        <div className="flex flex-wrap gap-2">
          {[["9:16", "Vertical (Shorts, Reels)"], ["16:9", "Wide (YouTube)"], ["1:1", "Square"]].map(([v, l]) => (
            <button key={v} type="button" onClick={() => setAspect(v)} aria-pressed={aspect === v}
              className={`rounded-full border px-4 py-2 text-sm ${aspect === v ? "border-amber-500 bg-amber-500/15 text-amber-700 dark:text-amber-300" : "border-border hover:bg-accent"}`}>{l}</button>
          ))}
        </div>
      </div>
      <ModelPicker value={pick} onChange={setPick} />

      <label className="mt-5 flex items-start gap-3 rounded-2xl border border-border p-4 text-sm">
        <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} className="mt-1 h-4 w-4" />
        <span><span className="font-medium">Do everything without asking me</span>
          <span className="block text-muted-foreground">Off: you choose the topic and approve the character sheets before any scene or video is made. On: it picks the best idea and goes straight to the video.</span></span>
      </label>
      {create.isError && <p className="mt-4 rounded-2xl border border-red-500/40 bg-red-500/5 p-3 text-sm" role="alert">{(create.error as Error).message}</p>}
      <button type="button" disabled={create.isPending}
        onClick={() => create.mutate({ event: named ? event.trim() : undefined, interest: named ? undefined : interest.trim() || undefined, aspect, auto, ...choiceBody(pick) })}
        className="mt-6 inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-amber-500 to-orange-500 px-6 py-3 font-semibold text-white shadow-lg shadow-amber-500/20 disabled:opacity-50" data-testid="stickman-create">
        {create.isPending ? <Loader2 className="h-5 w-5 animate-spin" /> : <Sparkles className="h-5 w-5" />}{named ? "Make this video" : "Show me eight ideas"}
      </button>
    </section>
  );
}
