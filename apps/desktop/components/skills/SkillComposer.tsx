"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Wand2 } from "lucide-react";
import { skills, type SkillInfo } from "@/lib/skills";
import { ModelPicker, NO_CHOICE, choiceBody, type ModelChoice } from "@/components/shared/ModelPicker";

const chip = (on: boolean) => `border px-3.5 py-2 font-mono text-[11px] uppercase tracking-[0.08em] leading-none transition-colors ${on ? "border-[rgba(200,255,58,0.7)] bg-[rgba(200,255,58,0.18)] text-foreground" : "border-border text-muted-foreground hover:text-foreground"}`;

/** One skill's input: the subject, what to make (pictures and video, or prompts only), shape and length. */
const STORY_NOTE = "Research comes from Wikipedia and Wikidata, and every source is listed with the result (Wikidata settles the founding year). "
  + "The script may only use the researched facts: a card whose number isn't in them is dropped, and a narration line with an unchecked number is "
  + "rewritten or cut. The story is told by the one 2D character you pick, placed on a toy-town backdrop in three poses per scene (a cartoon stand-in, "
  + "never a likeness of a real person). Needs an AI writer (Groq or another crew in Models). AI video uses Seedance and needs a fal.ai key with credit "
  + "(Settings): without it the run stops and tells you, instead of quietly using still pictures. Paper puppet is free: the character sways and flips "
  + "between three poses on a slowly pushing paper backdrop.";

const TOY_NOTE = "The compact pod is drawn first, then the transformed toy is drawn from it so finish, colours and table stay the same. The clip is made "
  + "by Seedance 2.0 from both pictures, with its own mechanical sound and no music. Needs a fal.ai key with credit (Settings); without it you get the two "
  + "pictures joined with a camera move.";

export function SkillComposer({ skill }: { skill: SkillInfo | null }) {
  const router = useRouter();
  const [subject, setSubject] = useState("");
  const [media, setMedia] = useState<"media" | "prompts">("media");
  const [aspect, setAspect] = useState("9:16");
  const [seconds, setSeconds] = useState(15);
  const [pick, setPick] = useState<ModelChoice>(NO_CHOICE);
  const [voice, setVoice] = useState<"male" | "female">("male");
  const [style, setStyle] = useState("2d");
  const [motion, setMotion] = useState("video");
  const [hands, setHands] = useState("gloved");
  const [cast, setCast] = useState<{ founder: string }>({ founder: "executive" });
  const [review, setReview] = useState(true);
  useEffect(() => {
    if (skill) {
      setAspect(skill.aspect); setSeconds(skill.default_seconds);
      if (skill.styles) setStyle(skill.styles[0][0]);
      if (skill.motions) setMotion(skill.motions[0][0]);
      if (skill.hands) setHands(skill.hands[0][0]);
      if (skill.default_cast) setCast(skill.default_cast);
    }
  }, [skill]);
  const create = useMutation({ mutationFn: skills.create, onSuccess: (r) => router.push(`/skills/${r.id}`) });
  const ok = subject.trim().length > 1 && !!skill;

  const length = skill?.lengths?.find((l) => l.seconds === seconds);
  const story = skill?.kind === "story";
  const motions = skill?.motions ?? [];                      // a skill can offer motion without being a story (ASMR Cooking)
  const handChoices = skill?.hands ?? [];                    // ASMR Cooking: gloved or bare
  const makes = skill?.make ?? [["media", "Pictures and video"], ["prompts", "Prompts only"]];
  if (!skill) return <section className="composer border border-border p-8 text-sm text-muted-foreground">Pick a skill on the left.</section>;
  // Each skill's own note, with the two whose INFO lives in files this overlay does not ship falling back to the
  // text they have always had. Without this every non-story skill announced itself as a transformation toy.
  const note = skill.note
    || (story ? STORY_NOTE : skill.id === "mechanical-toy" ? TOY_NOTE : "");
  return (
    <section className="composer border border-border p-5 sm:p-8" data-testid="skill-composer">
      <p className="text-xs text-muted-foreground">Skill <b className="text-foreground">{skill.name}</b> · {skill.group}</p>
      {/* The headline is the skill's own `made_for`. It used to be a two-way guess -- Company Story's line, or
          Mechanical Toy's for everything else -- so ASMR Cooking, ASMR Cutting and Motion Graphics all announced
          themselves as a transformation toy. */}
      <h1 className="display mt-2 text-3xl md:text-4xl">{skill.made_for || skill.about}</h1>
      <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted-foreground">{skill.about}</p>

      <ol className="mt-5 grid gap-2 sm:grid-cols-3">
        {skill.outputs.map((o, i) => (
          <li key={o} className="border border-border px-4 py-3 text-sm"><span className="text-muted-foreground">{i + 1}.</span> {o}</li>
        ))}
      </ol>

      <label htmlFor="skill-subject" className="field-label mb-2 mt-6 block">{story ? "Company or industry" : "Subject"}</label>
      <textarea id="skill-subject" value={subject} onChange={(e) => setSubject(e.target.value)} rows={3} data-testid="skill-subject" placeholder={skill.input}
        className="prompt-field w-full resize-y border border-border p-4 text-base leading-relaxed outline-none" />
      <div className="mt-2 flex flex-wrap gap-2">
        {skill.examples.map((x) => (
          <button key={x} type="button" onClick={() => setSubject(x)} className="border border-border px-3 py-1 text-xs text-muted-foreground hover:text-foreground">{x}</button>
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
            {[["9:16", "9:16 Portrait"], ["1:1", "1:1 Square"], ["16:9", "16:9 Landscape"]].filter(([v]) => !skill.aspects || skill.aspects.includes(v)).map(([v, l]) => (
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
          {story && length && <p className="mt-1.5 text-[11px] text-muted-foreground">{length.scenes} scenes of {length.each} seconds{length.scenes > 12 ? " \u00b7 a long one: that is one picture and one clip per scene" : ""}.</p>}
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

      {story && skill.styles && (
        <div className="mt-6 space-y-5" data-testid="story-options">
          <div className="grid gap-5">
            {skill.styles.length > 1 && <div>
              <p className="field-label mb-2">Look</p>
              <div className="flex flex-wrap gap-2">
                {skill.styles.map(([v, l]) => <button key={v} type="button" onClick={() => setStyle(v)} aria-pressed={style === v} className={chip(style === v)}>{l}</button>)}
              </div>
            </div>}
            <div>
              <p className="field-label mb-2">{skill.motions_label ?? "Motion"}</p>
              <div className="flex flex-wrap gap-2">
                {(skill.motions ?? []).map(([v, l]) => <button key={v} type="button" onClick={() => setMotion(v)} aria-pressed={motion === v} className={chip(motion === v)}>{l}</button>)}
              </div>
            </div>
          </div>
          {media === "media" && (
            <label className="flex cursor-pointer items-start gap-3 border border-border p-3 text-sm" data-testid="review-toggle">
              <input type="checkbox" checked={review} onChange={(e) => setReview(e.target.checked)} className="mt-1 h-4 w-4 accent-[var(--primary)]" />
              <span><b>Let me review the plan first</b><span className="block text-xs text-muted-foreground">After the script, the run pauses and shows the suggested character, storyboard, motion and voice. Change what you like, then approve. Nothing is drawn or spent before you do.</span></span>
            </label>)}
          <div>
            <p className="field-label mb-2">Character</p>
            <div className="flex flex-wrap gap-2">
              {(skill.characters ?? []).map((c) => {
                const on = cast.founder === c.id;
                return (
                  <button key={c.id} type="button" title={c.about} aria-pressed={on} onClick={() => setCast({ founder: c.id })}
                    className={`flex w-32 flex-col items-center gap-1 border p-2 text-[11px] transition-colors ${on ?"border-[rgba(200,255,58,0.8)] bg-[rgba(200,255,58,0.18)]" :"border-border"}`}>
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={skills.character(`${c.id}_2d.jpg`)} alt={c.name} className="h-36 w-full bg-muted object-contain" />
                    <span className="text-center leading-tight">{c.name}</span>
                    <span className="text-center text-[10px] leading-tight text-muted-foreground">{c.about}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {skill.slow && <p className="mt-5 border border-amber-400/70 p-3 text-xs leading-relaxed text-muted-foreground"><b className="text-foreground">{skill.slow_label ?? "Slow, best quality"}.</b> {skill.slow}.</p>}
      {skill.engine && <EngineNotice />}

      {note && (
      <p className="mt-5 border border-[rgba(200,255,58,0.35)] p-3 text-xs leading-relaxed text-muted-foreground">{note}</p>)}

      {handChoices.length > 1 && (
        <div className="mt-6" data-testid="hand-options">
          <p className="field-label mb-2">{skill.hands_label ?? "Hands"}</p>
          <div className="flex flex-wrap gap-2">
            {handChoices.map(([v, l]) => <button key={v} type="button" onClick={() => setHands(v)} aria-pressed={hands === v} className={chip(hands === v)}>{l}</button>)}
          </div>
        </div>)}

      {!story && motions.length > 1 && (
        <div className="mt-6" data-testid="motion-options">
          <p className="field-label mb-2">{skill.motions_label ?? "Motion"}</p>
          <div className="flex flex-wrap gap-2">
            {motions.map(([v, l]) => <button key={v} type="button" onClick={() => setMotion(v)} aria-pressed={motion === v} className={chip(motion === v)}>{l}</button>)}
          </div>
        </div>)}

      <ModelPicker value={pick} onChange={setPick} />
      {create.isError && <p className="mt-4 border border-red-500/40 bg-red-500/5 p-3 text-sm" role="alert">{(create.error as Error).message}</p>}
      <button type="button" disabled={!ok || create.isPending} data-testid="skill-create"
        onClick={() => create.mutate({ skill: skill.id, subject: subject.trim(), media, aspect, seconds, voice, ...(story ? { style, motion, characters: cast, review: media === "media" && review } : motions.length ? { motion } : {}), ...(handChoices.length ? { hands } : {}), ...choiceBody(pick) })}
        className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-full bg-primary px-8 py-3.5 font-semibold text-white disabled:opacity-50 sm:w-auto">
        {create.isPending ? <Loader2 className="h-5 w-5 animate-spin" /> : <Wand2 className="h-5 w-5" />}{skill.cta?.[media === "prompts" ? 0 : 1]
          ?? (story ? (media === "prompts" ? "Research and write the script" : "Research and make the video")
          : skill.kind === "recipe" ? (media === "prompts" ? "Write the recipe and the shot list" : "Write the recipe and make the video")
          : skill.id === "mechanical-toy" ? (media === "prompts" ? "Write the three prompts" : "Make the toy")
          : media === "prompts" ? "Write the prompts" : "Make it")}
      </button>
    </section>
  );
}

/** The kit skills draw every frame in a built-in browser. This says whether it is installed and installs it (one time, about 300 MB). */
function EngineNotice() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["kit-engine"], queryFn: skills.engine, refetchInterval: 5000, retry: false });
  const install = useMutation({ mutationFn: skills.installEngine, onSuccess: () => qc.invalidateQueries({ queryKey: ["kit-engine"] }) });
  if (!q.data || q.data.ready) return null;
  const busy = q.data.installing || install.isPending;
  return (
    <div className="mt-5 border border-amber-400/70 p-3 text-xs leading-relaxed text-muted-foreground" role="status">
      <p>The video engine is not installed yet (missing: {q.data.missing.join(", ")}). {q.data.fix}</p>
      <button type="button" disabled={busy} onClick={() => install.mutate()} className="mt-2 inline-flex items-center gap-2 border border-border px-3 py-1.5 text-foreground disabled:opacity-60">
        {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}{busy ? "Installing… (a few minutes)" : "Install it now"}
      </button>
    </div>
  );
}
