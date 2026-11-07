"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { Loader2, Wand2 } from "lucide-react";
import { skills, type SkillInfo } from "@/lib/skills";
import { ModelPicker, NO_CHOICE, choiceBody, type ModelChoice } from "@/components/shared/ModelPicker";

const chip = (on: boolean) => `rounded-full border px-4 py-2 text-sm transition-colors ${on ? "border-[rgba(185,172,255,0.7)] bg-[rgba(124,92,255,0.18)] text-foreground" : "border-border text-muted-foreground hover:text-foreground"}`;

/** One skill's input: the subject, what to make (pictures and video, or prompts only), shape and length. */
export function SkillComposer({ skill }: { skill: SkillInfo | null }) {
  const router = useRouter();
  const [subject, setSubject] = useState("");
  const [media, setMedia] = useState<"media" | "prompts">("media");
  const [aspect, setAspect] = useState("9:16");
  const [seconds, setSeconds] = useState(15);
  const [pick, setPick] = useState<ModelChoice>(NO_CHOICE);
  const [voice, setVoice] = useState<"male" | "female">("male");
  useEffect(() => { if (skill) { setAspect(skill.aspect); setSeconds(skill.default_seconds); } }, [skill]);
  const create = useMutation({ mutationFn: skills.create, onSuccess: (r) => router.push(`/skills/${r.id}`) });
  const ok = subject.trim().length > 1 && !!skill;

  const story = skill?.kind === "story";
  const makes = skill?.make ?? [["media", "Pictures and video"], ["prompts", "Prompts only"]];
  if (!skill) return <section className="composer rounded-3xl border border-border p-8 text-sm text-muted-foreground">Pick a skill on the left.</section>;
  return (
    <section className="composer rounded-3xl border border-border p-5 sm:p-8" data-testid="skill-composer">
      <p className="text-xs text-muted-foreground">Skill <b className="text-foreground">{skill.name}</b> · {skill.group}</p>
      <h1 className="display mt-2 text-3xl md:text-4xl">{story ? "Tell the story of any company or industry" : "Turn anything into a mechanical transformation toy"}</h1>
      <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted-foreground">{skill.about}</p>

      <ol className="mt-5 grid gap-2 sm:grid-cols-3">
        {skill.outputs.map((o, i) => (
          <li key={o} className="rounded-2xl border border-border px-4 py-3 text-sm"><span className="text-muted-foreground">{i + 1}.</span> {o}</li>
        ))}
      </ol>

      <label htmlFor="skill-subject" className="field-label mb-2 mt-6 block">{story ? "Company or industry" : "Subject"}</label>
      <textarea id="skill-subject" value={subject} onChange={(e) => setSubject(e.target.value)} rows={3} data-testid="skill-subject" placeholder={skill.input}
        className="prompt-field w-full resize-y rounded-2xl border border-border p-4 text-base leading-relaxed outline-none" />
      <div className="mt-2 flex flex-wrap gap-2">
        {skill.examples.map((x) => (
          <button key={x} type="button" onClick={() => setSubject(x)} className="rounded-full border border-border px-3 py-1 text-xs text-muted-foreground hover:text-foreground">{x}</button>
        ))}
      </div>

      <div className="mt-6 grid gap-5 lg:grid-cols-3">
        <div>
          <p className="field-label mb-2">Make</p>
          <div className="flex flex-wrap gap-2">
            {makes.map(([v, l]) => (
              <button key={v} type="button" onClick={() => setMedia(v as "media" | "prompts")} aria-pressed={media === v} className={chip(media === v)}>{l}</button>
            ))}
          </div>
        </div>
        <div>
          <p className="field-label mb-2">Shape</p>
          <div className="flex flex-wrap gap-2">
            {[["9:16", "9:16 Portrait"], ["1:1", "1:1 Square"], ["16:9", "16:9 Landscape"]].map(([v, l]) => (
              <button key={v} type="button" onClick={() => setAspect(v)} aria-pressed={aspect === v} className={chip(aspect === v)}>{l}</button>
            ))}
          </div>
        </div>
        <div>
          <p className="field-label mb-2">{story ? "Video length" : "Clip length"}</p>
          <div className="flex flex-wrap gap-2">
            {skill.seconds.map((n) => (
              <button key={n} type="button" onClick={() => setSeconds(n)} aria-pressed={seconds === n} className={chip(seconds === n)}>{n >= 60 ? `${n / 60} min` : `${n} s`}</button>
            ))}
          </div>
          {story && <p className="mt-1.5 text-[11px] text-muted-foreground">{seconds / 10} scenes of 10 seconds.</p>}
        </div>
        {story && (
          <div>
            <p className="field-label mb-2">Narrator</p>
            <div className="flex flex-wrap gap-2">
              {([["male", "Warm male"], ["female", "Clear female"]] as const).map(([v, l]) => (
                <button key={v} type="button" onClick={() => setVoice(v)} aria-pressed={voice === v} className={chip(voice === v)}>{l}</button>
              ))}
            </div>
          </div>
        )}
      </div>

      {story ? (
      <p className="mt-5 rounded-2xl border border-[rgba(185,172,255,0.35)] p-3 text-xs leading-relaxed text-muted-foreground">
        Research comes from Wikipedia and every source is listed with the result. The script may only use those facts: a card whose number isn&apos;t in the research
        is dropped, and a narration line with an unchecked number is flagged. The founders are original cartoon characters, not likenesses of real people. Needs an AI
        writer (Groq or another crew in Models). Scene motion uses Seedance with a fal.ai key; without it the scenes move with camera moves, while the cards still animate.
      </p>) : (
      <p className="mt-5 rounded-2xl border border-[rgba(185,172,255,0.35)] p-3 text-xs leading-relaxed text-muted-foreground">
        The compact pod is drawn first, then the transformed toy is drawn from it so finish, colours and table stay the same. The clip is made by Seedance 2.0 from both
        pictures, with its own mechanical sound and no music. Needs a fal.ai key with credit (Settings); without it you get the two pictures joined with a camera move.
      </p>)}

      <ModelPicker value={pick} onChange={setPick} />
      {create.isError && <p className="mt-4 rounded-xl border border-red-500/40 bg-red-500/5 p-3 text-sm" role="alert">{(create.error as Error).message}</p>}
      <button type="button" disabled={!ok || create.isPending} data-testid="skill-create"
        onClick={() => create.mutate({ skill: skill.id, subject: subject.trim(), media, aspect, seconds, voice, ...choiceBody(pick) })}
        className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-full bg-primary px-8 py-3.5 font-semibold text-white disabled:opacity-50 sm:w-auto">
        {create.isPending ? <Loader2 className="h-5 w-5 animate-spin" /> : <Wand2 className="h-5 w-5" />}{story ? (media === "prompts" ? "Research and write the script" : "Research and make the video") : media === "prompts" ? "Write the three prompts" : "Make the toy"}
      </button>
    </section>
  );
}
