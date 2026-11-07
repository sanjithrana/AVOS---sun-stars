"use client";

import { Check, Loader2 } from "lucide-react";
import { skills, type Plan } from "@/lib/skills";

const card = "rounded-2xl border border-border p-4";
const chip = (on: boolean) => `rounded-full border px-3 py-1.5 text-xs transition-colors ${on ? "border-[rgba(185,172,255,0.7)] bg-[rgba(124,92,255,0.18)] text-foreground" : "border-border text-muted-foreground hover:text-foreground"}`;

/** The suggested plan after the script: the character, the storyboard, the motion and the audio, each with its Change control. "Approve" is the one button that spends credit. */
export function PlanCards({ plan, busy, onCharacter, onMotion, onVoice, onApprove, approving }: {
  plan: Plan; busy: boolean; approving: boolean;
  onCharacter: (id: string) => void; onMotion: (m: "video" | "poses") => void; onVoice: (v: "male" | "female") => void; onApprove: () => void;
}) {
  return (
    <section className="space-y-3 rounded-3xl border border-[rgba(185,172,255,0.5)] p-4" data-testid="plan-cards" aria-label="Suggested plan">
      <div>
        <p className="text-xs uppercase tracking-wider text-amber-400">Review the plan</p>
        <h2 className="text-lg font-semibold">Here is what will be made</h2>
        <p className="text-xs text-muted-foreground">Worked out from your script. Change anything, then approve. Nothing is drawn or spent before you do.</p>
      </div>

      <div className={card}>
        <h3 className="text-sm font-semibold">1 · Character</h3>
        <div className="mt-2 flex flex-wrap gap-2">
          {plan.characters.map((c) => (
            <button key={c.id} type="button" disabled={busy} onClick={() => onCharacter(c.id)} aria-pressed={c.chosen} title={c.about}
              className={`flex w-24 flex-col items-center gap-1 rounded-2xl border p-1.5 text-[11px] disabled:opacity-60 ${c.chosen ? "border-[rgba(185,172,255,0.8)] bg-[rgba(124,92,255,0.18)]" : "border-border"}`}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={skills.character(`${c.id}_2d.jpg`)} alt={c.name} className="h-24 w-full rounded-xl bg-muted object-contain" />
              <span className="text-center leading-tight">{c.name}</span>
            </button>
          ))}
        </div>
        {plan.characters.find((c) => c.chosen)?.role && <p className="mt-2 text-[11px] text-muted-foreground">{plan.characters.find((c) => c.chosen)?.role}.</p>}
      </div>

      <div className={card}>
        <h3 className="text-sm font-semibold">2 · Storyboard <span className="font-normal text-muted-foreground">· {plan.storyboard.length} scenes</span></h3>
        <ol className="mt-2 space-y-2">
          {plan.storyboard.map((sc) => (
            <li key={sc.n} className="rounded-xl bg-muted/50 p-2.5 text-[12px] leading-snug">
              <b>{sc.n}. {sc.purpose}</b>
              <span className="block text-muted-foreground">{sc.place}{sc.rival ? " · the rivalry scene (banner, VS badge, name tags)" : ""}</span>
              <span className="block text-muted-foreground">Poses: {sc.pose_names.join(" → ") || sc.poses.join(" → ")} · camera: {sc.move}</span>
            </li>
          ))}
        </ol>
      </div>

      <div className={card}>
        <h3 className="text-sm font-semibold">3 · Motion</h3>
        <div className="mt-2 flex flex-wrap gap-2">
          {plan.motion.options.map(([v, l]) => <button key={v} type="button" disabled={busy} onClick={() => onMotion(v as "video" | "poses")} aria-pressed={plan.motion.engine === v} className={chip(plan.motion.engine === v)}>{l}</button>)}
        </div>
        <p className="mt-2 text-[11px] text-muted-foreground">{plan.motion.clips} scenes of {plan.motion.seconds_each} s. {plan.motion.note}</p>
      </div>

      <div className={card}>
        <h3 className="text-sm font-semibold">4 · Audio</h3>
        <div className="mt-2 flex flex-wrap gap-2">
          {([["male", "Warm male"], ["female", "Clear female"]] as const).map(([v, l]) => <button key={v} type="button" disabled={busy} onClick={() => onVoice(v)} aria-pressed={plan.audio.voice === v} className={chip(plan.audio.voice === v)}>{l}</button>)}
        </div>
        <p className="mt-2 text-[11px] text-muted-foreground">{plan.audio.narration_note}. {plan.audio.music}.</p>
      </div>

      <button type="button" disabled={busy || approving} onClick={onApprove} data-testid="approve-plan"
        className="inline-flex w-full items-center justify-center gap-2 rounded-full bg-primary px-6 py-3 text-sm font-semibold text-white disabled:opacity-60">
        {approving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}Approve and make the video
      </button>
    </section>
  );
}
