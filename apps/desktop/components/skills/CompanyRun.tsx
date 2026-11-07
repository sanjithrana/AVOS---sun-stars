"use client";

import { useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, ExternalLink, Loader2, RotateCcw, Square, TriangleAlert } from "lucide-react";
import { skills, type Card, type Run, type Scene } from "@/lib/skills";
import { StepTabs, type StepDef, type StepState } from "@/components/workspace/StepTabs";
import { SplitPane } from "@/components/workspace/SplitPane";
import { OutputTabs } from "@/components/workspace/OutputTabs";
import { SaveState } from "@/components/workspace/SaveState";
import { PlanCards } from "@/components/workspace/PlanCards";
import { Timeline, type Lane } from "@/components/workspace/Timeline";

type StepId = "script" | "scenes" | "motion" | "audio" | "final";
type OutId = "storyboard" | "shots" | "characters" | "timeline";
const GROUPS: Record<StepId, { label: string; stages: string[] }> = {
  script: { label: "Script", stages: ["research", "script"] }, scenes: { label: "Scenes", stages: ["cast", "scenes"] }, motion: { label: "Motion", stages: ["animate"] },
  audio: { label: "Audio", stages: ["voice"] }, final: { label: "Final", stages: ["finish"] },
};
const ORDER: StepId[] = ["script", "scenes", "motion", "audio", "final"];

const cardText = (c: Card) => c.type === "title" ? `${c.text} · ${c.years}` : c.type === "stat" ? `${c.value} ${c.unit ?? ""}` : c.type === "vs" ? `${c.left} vs ${c.right}` : c.type === "year" ? `${c.value}` : `${c.text}`;
const box = "rounded-3xl border border-border p-4";
const btn = "inline-flex items-center gap-1.5 rounded-full border border-border px-3 py-1.5 text-xs disabled:opacity-50";
const chip = (on: boolean) => `rounded-full border px-3 py-1.5 text-xs transition-colors ${on ? "border-[rgba(185,172,255,0.7)] bg-[rgba(124,92,255,0.18)] text-foreground" : "border-border text-muted-foreground hover:text-foreground"}`;

function NarrationRow({ sc, busy, onSay }: { sc: Scene; busy: boolean; onSay: (n: number, text: string) => void }) {
  const [text, setText] = useState(sc.narration);                 // the row is re-created (key) when the saved narration changes
  return (
    <li className="rounded-2xl border border-border p-3">
      <p className="text-xs font-semibold">Scene {sc.n} <span className="font-normal text-muted-foreground">· {sc.purpose}</span></p>
      <textarea value={text} onChange={(e) => setText(e.target.value)} rows={3} aria-label={`Narration for scene ${sc.n}`} className="prompt-field mt-2 w-full resize-y rounded-xl border border-border p-2.5 text-sm leading-relaxed" />
      {sc.warning && <p className="mt-1 text-[11px] text-amber-300/90">{sc.warning}</p>}
      {sc.dropped > 0 && <p className="mt-1 text-[11px] text-muted-foreground">{sc.dropped} card(s) left out: their numbers weren&apos;t in the research.</p>}
      {text !== sc.narration && <button type="button" disabled={busy} onClick={() => onSay(sc.n, text)} className="mt-2 rounded-full border border-[rgba(185,172,255,0.6)] px-3 py-1.5 text-xs disabled:opacity-50">Save and re-record</button>}
    </li>
  );
}

/** A Company Story run on the shared workspace: steps on top (Script · Scenes · Motion · Audio · Final), the controls for the step on the left, the
 *  output (preview, Storyboard, Shots, Characters, Timeline) on the right. After the script it pauses for you to review the suggested plan. */
export function CompanyRun({ run: r }: { run: Run }) {
  const qc = useQueryClient();
  const refresh = () => qc.invalidateQueries({ queryKey: ["skill-run", r.id] });
  const done = (x: Run) => qc.setQueryData(["skill-run", r.id], x);
  const info = useQuery({ queryKey: ["skills-list"], queryFn: skills.list, staleTime: 60000, retry: false });
  const busy = r.busy || r.status === "working";
  const waiting = r.status === "waiting";
  const hasScript = !!r.script?.scenes?.length;
  const planQ = useQuery({ queryKey: ["skill-plan", r.id, r.updatedAt], queryFn: () => skills.plan(r.id), enabled: hasScript, retry: false, staleTime: 5000 });

  const redo = useMutation({ mutationFn: ({ step, n }: { step: string; n?: number }) => skills.redo(r.id, step, n), onSuccess: done });
  const resume = useMutation({ mutationFn: () => skills.resume(r.id), onSuccess: done });
  const stop = useMutation({ mutationFn: () => skills.cancel(r.id), onSuccess: refresh });
  const toPoses = useMutation({ mutationFn: async () => { await skills.setMotion(r.id, "poses"); return skills.resume(r.id); }, onSuccess: done });
  const say = useMutation({ mutationFn: async ({ n, text }: { n: number; text: string }) => { await skills.editNarration(r.id, { [String(n)]: text }); return skills.redo(r.id, "voice"); }, onSuccess: done });
  // a change made while reviewing only saves; after the video exists it saves and makes the affected steps again
  const change = useMutation({
    mutationFn: async (c: { motion?: "video" | "poses"; character?: string; voice?: "male" | "female" }) => {
      let x = c.motion ? await skills.setMotion(r.id, c.motion) : c.character ? await skills.setCharacter(r.id, c.character) : await skills.setVoice(r.id, c.voice!);
      if (x.status !== "waiting" && !x.busy && x.status !== "working") x = await skills.resume(r.id);
      return x;
    }, onSuccess: done,
  });
  const saving = redo.isPending || resume.isPending || say.isPending || change.isPending || toPoses.isPending;
  const err = redo.error || resume.error || say.error || change.error || toPoses.error;

  const R = r.research;
  const scenes = useMemo(() => r.script?.scenes ?? [], [r.script]);
  const cid = r.characters?.founder ?? r.cast?.founder ?? "";
  const chars = info.data?.skills.find((s) => s.id === "company-story")?.characters ?? [];
  const me = chars.find((c) => c.id === cid);

  // steps
  const stState = (id: StepId): StepState => {
    const g = GROUPS[id].stages;
    const s = g.map((x) => r.steps?.[x]?.status);
    if (s.includes("error")) return "error";
    if (waiting && g.includes(r.stage)) return "waiting";
    if (s.includes("working") || (busy && g.includes(r.stage))) return "working";
    return g.every((x) => r.steps?.[x]?.status === "done") ? "done" : "todo";
  };
  const steps: StepDef[] = ORDER.map((id) => ({ id, label: GROUPS[id].label, state: stState(id), locked: r.media === "prompts" && id !== "script" && stState(id) === "todo" }));
  const current: StepId = r.status === "done" && r.media === "media" ? "final" : (ORDER.find((id) => GROUPS[id].stages.includes(r.stage)) ?? "script");
  const [pick, setPick] = useState<StepId | null>(null);
  const [lastStage, setLastStage] = useState(r.stage);
  if (r.stage !== lastStage) { setLastStage(r.stage); setPick(null); }       // follow the run to its next step unless the person is looking elsewhere
  const step = pick ?? current;

  // output
  const [out, setOut] = useState<OutId>("storyboard");
  const [sel, setSel] = useState<number | null>(null);
  const video = useRef<HTMLVideoElement>(null);
  const [time, setTime] = useState(0);
  const seek = (t: number) => { setTime(t); if (video.current) { video.current.currentTime = t; } };
  const v = `${r.version ?? 1}-${r.updatedAt}`;
  const total = r.finalSeconds || r.seconds || scenes.length * 10 || 30;
  const each = scenes.length ? total / scenes.length : 10;

  const lanes: Lane[] = useMemo(() => {
    const L: Lane[] = [{ id: "scenes", label: "Scenes", clips: [] }, { id: "poses", label: "Poses", clips: [] }, { id: "voice", label: "Narration", clips: [] }, { id: "cards", label: "Cards", clips: [] }, { id: "music", label: "Music", clips: [{ start: 0, end: total, label: "light underscore", tone: "muted" }] }];
    scenes.forEach((sc, i) => {
      const a = i * each;
      L[0].clips.push({ start: a, end: a + each, label: `${sc.n}. ${sc.purpose}`, tone: sc.video ? "primary" : "muted", title: sc.narration });
      const names = sc.pose_names?.length ? sc.pose_names : sc.poses ?? [];
      names.forEach((nm, k) => L[1].clips.push({ start: a + (each * k) / names.length, end: a + (each * (k + 1)) / names.length, label: nm, tone: "green" }));
      if (sc.voice_seconds) L[2].clips.push({ start: a, end: Math.min(a + sc.voice_seconds, a + each), label: `line ${sc.n}`, tone: "primary", title: sc.narration });
      const slot = (each - 0.6) / Math.max(1, sc.cards.length);                       // card timings are approximate: shared evenly over the scene so the labels stay readable
      sc.cards.forEach((c, k) => L[3].clips.push({ start: a + 0.3 + k * slot, end: a + 0.3 + (k + 1) * slot, label: cardText(c), tone: "amber" }));
    });
    return L;
  }, [scenes, each, total]);

  const stageLabel = r.stages.find((s) => s.id === r.stage)?.label;
  const motionNow = r.motion === "poses" ? "poses" : "video";

  // ---------------- left: the controls for the step
  const sceneStatus = (sc: Scene) => (sc.video ? "clip ready" : sc.picture ? "picture ready" : "waiting");
  const left = (
    <div className="space-y-4">
      <section className={box} data-testid="skill-workflow">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0"><p className="text-xs text-muted-foreground">Company Story</p><h1 className="mt-0.5 text-lg font-semibold leading-tight">{r.title}</h1></div>
          <SaveState saving={saving} />
        </div>
        {(r.motion || r.characters?.founder) && <p className="mt-2 text-[11px] text-muted-foreground">2D · {motionNow === "poses" ? "paper puppet (free)" : "AI video"}{me ? ` · ${me.name}` : ""}</p>}
        {r.status === "error" && <p className="mt-3 rounded-xl border border-red-500/40 bg-red-500/5 p-3 text-xs" role="alert">{r.error}</p>}
        {r.status === "error" && r.motion === "video" && /video/i.test(r.error ?? "") && <button type="button" disabled={toPoses.isPending} onClick={() => toPoses.mutate()} className={`${btn} mt-2`}>Use the free paper puppet instead</button>}
        {err && <p className="mt-3 text-xs text-red-400" role="alert">{(err as Error).message}</p>}
        <div className="mt-3 flex flex-wrap gap-2">
          {busy ? <button type="button" onClick={() => stop.mutate()} className={btn}><Square className="h-3.5 w-3.5" />Stop</button>
            : r.status === "stopped" || r.status === "error" ? <button type="button" onClick={() => resume.mutate()} className="rounded-full bg-primary px-4 py-2 text-sm font-semibold text-white">Continue</button>
            : r.status === "done" && r.media === "prompts" ? <button type="button" onClick={() => redo.mutate({ step: "cast" })} className="rounded-full bg-primary px-4 py-2 text-sm font-semibold text-white">Make the video</button>
            : null}
        </div>
      </section>

      {waiting && planQ.data && (
        <PlanCards plan={planQ.data} busy={saving} approving={resume.isPending}
          onCharacter={(id) => change.mutate({ character: id })} onMotion={(m) => change.mutate({ motion: m })} onVoice={(x) => change.mutate({ voice: x })} onApprove={() => resume.mutate()} />
      )}

      {step === "script" && (
        <>
          {!!scenes.length && (
            <section className={box}>
              <div className="flex items-center justify-between gap-2"><h2 className="text-sm font-semibold">Narration</h2>
                {!busy && r.media === "media" && <button type="button" onClick={() => redo.mutate({ step: "script" })} className={btn}><RotateCcw className="h-3.5 w-3.5" />New script</button>}</div>
              <ul className="mt-3 space-y-3">{scenes.map((sc) => <NarrationRow key={`${sc.n}-${sc.narration}`} sc={sc} busy={busy || say.isPending || waiting} onSay={(n, t) => say.mutate({ n, text: t })} />)}</ul>
              {waiting && <p className="mt-2 text-[11px] text-muted-foreground">You can edit a line now; its voice is recorded after you approve.</p>}
            </section>
          )}
          {R && (
            <details className={`${box} text-sm`} data-testid="skill-research" open={!scenes.length}>
              <summary className="cursor-pointer font-semibold">Research with sources</summary>
              <dl className="mt-3 space-y-2 text-[13px]">
                {R.founded && <div><dt className="text-xs text-muted-foreground">Founded</dt><dd>{R.founded}{R.founder ? ` · ${R.founder}` : ""}</dd></div>}
                {R.origin && <div><dt className="text-xs text-muted-foreground">How it began</dt><dd>{R.origin}</dd></div>}
                {R.home && <div><dt className="text-xs text-muted-foreground">Home</dt><dd>{R.home}</dd></div>}
                {R.parent && <div><dt className="text-xs text-muted-foreground">Parent company</dt><dd>{R.parent}</dd></div>}
                {R.about && <div><dt className="text-xs text-muted-foreground">Wikidata says</dt><dd>{R.about}</dd></div>}
              </dl>
              {!!R.story_moments?.length && <><h3 className="mt-4 text-xs text-muted-foreground">The story</h3>
                <ol className="mt-1 space-y-2 text-[13px]">{R.story_moments.map((m, i) => <li key={i}><b>{m.year ? `${m.year} · ` : ""}{m.title}</b>{m.kind && <span className="text-[11px] text-muted-foreground"> · {m.kind}</span>}<span className="block text-muted-foreground">{m.what}</span></li>)}</ol></>}
              {!!R.milestones.length && <><h3 className="mt-4 text-xs text-muted-foreground">How it grew</h3>
                <ol className="mt-1 space-y-1.5 text-[13px]">{R.milestones.map((m, i) => <li key={i} className="flex gap-3"><b className="w-10 shrink-0 tabular-nums">{m.year}</b><span>{m.event}</span></li>)}</ol></>}
              {!!R.numbers.length && <><h3 className="mt-4 text-xs text-muted-foreground">Checked numbers</h3>
                <ul className="mt-1 space-y-1 text-[13px]">{R.numbers.map((n, i) => <li key={i}><b>{n.value}</b> {n.label}{n.year ? ` (${n.year})` : ""}</li>)}</ul></>}
              {!!R.how_it_works.length && <><h3 className="mt-4 text-xs text-muted-foreground">How it works</h3>
                <ul className="mt-1 list-disc space-y-1 pl-5 text-[13px]">{R.how_it_works.map((x, i) => <li key={i}>{x}</li>)}</ul></>}
              {!!R.rivals.length && <p className="mt-4 text-[13px]"><span className="text-xs text-muted-foreground">Rivals </span>{R.rivals.join(", ")}</p>}
              {!!R.unknowns.length && <p className="mt-3 text-[12px] text-muted-foreground">Unclear in the sources: {R.unknowns.join(" · ")}</p>}
              <h3 className="mt-4 text-xs text-muted-foreground">Sources</h3>
              <ul className="mt-1 space-y-1 text-[13px]">{R.sources.map((s) => <li key={s.url}><a href={s.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 underline decoration-muted-foreground/50 underline-offset-2 hover:text-foreground">{s.title}<ExternalLink className="h-3 w-3" /></a></li>)}</ul>
            </details>
          )}
        </>
      )}

      {step === "scenes" && (
        <>
          <section className={box} data-testid="character-picker">
            <h2 className="text-sm font-semibold">Character</h2>
            <p className="mt-1 text-[11px] text-muted-foreground">One ready-made 2D character stands in every scene. Changing it places the new one on the same backdrops.</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {chars.map((c) => (
                <button key={c.id} type="button" disabled={busy || saving} title={c.about} aria-pressed={c.id === cid} onClick={() => c.id !== cid && change.mutate({ character: c.id })}
                  className={`flex w-24 flex-col items-center gap-1 rounded-2xl border p-1.5 text-[11px] disabled:opacity-60 ${c.id === cid ? "border-[rgba(185,172,255,0.8)] bg-[rgba(124,92,255,0.18)]" : "border-border"}`}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={skills.character(`${c.id}_2d.jpg`)} alt={c.name} className="h-24 w-full rounded-xl bg-muted object-contain" /><span className="text-center leading-tight">{c.name}</span>
                </button>
              ))}
            </div>
          </section>
          <section className={box}>
            <h2 className="text-sm font-semibold">Scene pictures</h2>
            <ul className="mt-3 space-y-2">{scenes.map((sc) => (
              <li key={sc.n} className="flex items-center gap-3 rounded-xl bg-muted/50 p-2.5 text-[12px]">
                <span className="min-w-0 flex-1"><b>{sc.n}. {sc.purpose}</b><span className="block truncate text-muted-foreground">{sc.place || sc.setting} · {sceneStatus(sc)}</span></span>
                {!busy && r.media === "media" && sc.picture && <button type="button" onClick={() => redo.mutate({ step: "scenes", n: sc.n })} className={btn}><RotateCcw className="h-3.5 w-3.5" />New picture</button>}
              </li>))}</ul>
          </section>
        </>
      )}

      {step === "motion" && (
        <section className={box}>
          <h2 className="text-sm font-semibold">Motion</h2>
          <div className="mt-3 flex flex-wrap gap-2">
            {(info.data?.skills.find((s) => s.id === "company-story")?.motions ?? []).map(([m, l]) => <button key={m} type="button" disabled={busy || saving} aria-pressed={motionNow === m} onClick={() => m !== motionNow && change.mutate({ motion: m as "video" | "poses" })} className={chip(motionNow === m)}>{l}</button>)}
          </div>
          <p className="mt-2 text-[11px] text-muted-foreground">{motionNow === "video" ? "Seedance makes one clip per scene and uses your fal.ai credit; the run stops with a message if there is none." : "Free: the paper-cut character sways and flips between three poses over a slowly pushing backdrop; cards and numbers animate."}</p>
          <ul className="mt-3 space-y-1.5">{scenes.map((sc) => <li key={sc.n} className="flex justify-between rounded-xl bg-muted/50 px-3 py-2 text-[12px]"><span>Scene {sc.n} · camera {sc.move}</span><span className="text-muted-foreground">{sc.video ? "done" : r.steps?.animate?.status === "working" ? "making…" : "waiting"}</span></li>)}</ul>
          {r.steps?.animate?.note && <p className="mt-2 text-[11px] text-amber-300/90">{r.steps.animate.note}</p>}
        </section>
      )}

      {step === "audio" && (
        <section className={box}>
          <h2 className="text-sm font-semibold">Narration and music</h2>
          <div className="mt-3 flex flex-wrap gap-2">
            {([["male", "Warm male"], ["female", "Clear female"]] as const).map(([x, l]) => <button key={x} type="button" disabled={busy || saving} aria-pressed={(r.voice ?? "male") === x} onClick={() => x !== (r.voice ?? "male") && change.mutate({ voice: x })} className={chip((r.voice ?? "male") === x)}>{l}</button>)}
          </div>
          <p className="mt-2 text-[11px] text-muted-foreground">{planQ.data?.audio.narration_note ?? ""}. A light underscore plays under the voice, never louder than it.</p>
          {r.steps?.voice?.note && <p className="mt-1 text-[11px] text-amber-300/90">{r.steps.voice.note}</p>}
          <ul className="mt-3 space-y-2">{scenes.map((sc) => (
            <li key={sc.n} className="rounded-xl bg-muted/50 p-2.5 text-[12px]"><b>Line {sc.n}</b> <span className="text-muted-foreground">{sc.voice_seconds ? `${sc.voice_seconds}s` : ""}</span>
              {sc.voice ? <audio controls preload="none" src={skills.file(r.id, sc.voice, v)} className="mt-1 h-8 w-full" /> : <span className="block text-muted-foreground">not recorded yet</span>}</li>))}</ul>
        </section>
      )}

      {step === "final" && (
        <section className={box}>
          <h2 className="text-sm font-semibold">Final video</h2>
          {r.video ? <div className="mt-3 flex flex-wrap gap-2"><a href={skills.file(r.id, r.video, r.updatedAt)} download className={btn}><Download className="h-3.5 w-3.5" />Download MP4</a>
            {!busy && <button type="button" onClick={() => redo.mutate({ step: "script" })} className={btn}><RotateCcw className="h-3.5 w-3.5" />New script</button>}</div>
            : <p className="mt-2 text-xs text-muted-foreground">Not made yet.</p>}
          {!!r.finalSeconds && <p className="mt-2 text-[11px] text-muted-foreground">{Math.round(r.finalSeconds)} seconds · {scenes.length} scenes</p>}
        </section>
      )}

      <details className="rounded-3xl border border-border p-4 text-xs text-muted-foreground">
        <summary className="cursor-pointer text-sm text-foreground">Activity</summary>
        <ul className="mt-2 space-y-1">{r.log.slice(-20).map((l, i) => <li key={i} className={l.kind === "error" ? "text-red-400" : ""}>{l.text}</li>)}</ul>
      </details>
    </div>
  );

  // ---------------- right: the output
  const aspectCls = r.aspect === "9:16" ? "aspect-[9/16] max-h-[70vh]" : r.aspect === "1:1" ? "aspect-square max-h-[70vh]" : "aspect-video";
  const right = (
    <div className="min-w-0 space-y-4" data-testid="skill-output">
      <section className={box}>
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-sm font-semibold">Preview{r.finalSeconds ? <span className="font-normal text-muted-foreground"> · {Math.round(r.finalSeconds)} s</span> : null}</h2>
          {r.video && <a href={skills.file(r.id, r.video, r.updatedAt)} download className={btn}><Download className="h-3.5 w-3.5" />Download</a>}
        </div>
        <div className={`mx-auto mt-3 overflow-hidden rounded-2xl bg-muted ${aspectCls}`}>
          {r.video ? <video ref={video} key={r.updatedAt} src={skills.file(r.id, r.video, r.updatedAt)} controls playsInline onTimeUpdate={(e) => setTime(e.currentTarget.currentTime)} className="h-full w-full object-contain" />
            : <span className="flex h-full flex-col items-center justify-center gap-2 p-6 text-center text-sm text-muted-foreground">{busy ? <><Loader2 className="h-6 w-6 animate-spin" />{stageLabel}…</>
              : waiting ? "Review the plan on the left, then approve to make the video." : r.media === "prompts" ? "Research and script only. Press Make the video when you're happy with it." : "Not made yet"}</span>}
        </div>
      </section>

      <OutputTabs<OutId> tabs={[{ id: "storyboard", label: "Storyboard", count: scenes.length }, { id: "shots", label: "Shots", count: scenes.length }, { id: "characters", label: "Characters", count: 1 }, { id: "timeline", label: "Timeline" }]} active={out} onChange={setOut} />

      {out === "storyboard" && (scenes.length ? (
        <ul className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
          {scenes.map((sc) => (
            <li key={sc.n} className={`cursor-pointer rounded-3xl border p-3 transition-colors ${sel === sc.n ? "border-[rgba(185,172,255,0.8)]" : "border-border"}`} onClick={() => { setSel(sc.n); setOut("shots"); }}>
              <div className={`overflow-hidden rounded-2xl bg-muted ${r.aspect === "9:16" ? "aspect-[9/16]" : r.aspect === "1:1" ? "aspect-square" : "aspect-video"}`}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                {sc.picture ? <img src={skills.file(r.id, sc.picture, `${sc.version ?? 1}-${r.updatedAt}`)} alt={`Scene ${sc.n}`} className="h-full w-full object-cover" /> : <span className="flex h-full items-center justify-center text-xs text-muted-foreground">{r.steps?.scenes?.status === "working" ? "Drawing…" : "Not drawn yet"}</span>}
              </div>
              <p className="mt-2 text-sm font-semibold">{sc.n}. {sc.purpose}</p>
              <p className="mt-1 line-clamp-3 text-[12px] leading-snug text-muted-foreground">{sc.narration}</p>
              <div className="mt-2 flex flex-wrap gap-1.5">{sc.cards.map((c, i) => <span key={i} className="rounded-full border border-border px-2 py-0.5 text-[10px]"><span className="text-muted-foreground">{c.type}</span> {cardText(c)}</span>)}</div>
            </li>
          ))}
        </ul>
      ) : <p className="rounded-2xl border border-dashed border-border p-10 text-center text-sm text-muted-foreground">The storyboard appears here as soon as the script is written.</p>)}

      {out === "shots" && (
        <ul className="space-y-3">
          {scenes.filter((sc) => sel === null || sc.n === sel).map((sc) => (
            <li key={sc.n} className="rounded-3xl border border-border p-3">
              <div className="flex items-center justify-between gap-2"><p className="text-sm font-semibold">Shot {sc.n} <span className="font-normal text-muted-foreground">· {sc.purpose}</span></p>
                <span className="text-[11px] text-muted-foreground">{sceneStatus(sc)}</span></div>
              {sc.video ? <video src={skills.file(r.id, sc.video, `${sc.version ?? 1}-${r.updatedAt}`)} controls muted playsInline className="mt-2 w-full rounded-xl bg-black" />
                : !!sc.pose_pics?.length && <div className="mt-2 grid grid-cols-3 gap-1.5">{sc.pose_pics.map((f, i) => /* eslint-disable-next-line @next/next/no-img-element */
                  <img key={f} src={skills.file(r.id, f, `${sc.version ?? 1}-${r.updatedAt}`)} alt={`Scene ${sc.n} pose ${i + 1}`} className="aspect-video w-full rounded-lg object-cover" />)}</div>}
              <p className="mt-2 text-[12px] text-muted-foreground">Poses: {(sc.pose_names?.length ? sc.pose_names : sc.poses ?? []).join(" → ")} · camera: {sc.move}{sc.rival ? " · rivalry scene" : ""}</p>
            </li>
          ))}
          {sel !== null && <button type="button" onClick={() => setSel(null)} className={btn}>Show all shots</button>}
          {!scenes.length && <p className="rounded-2xl border border-dashed border-border p-10 text-center text-sm text-muted-foreground">Shots appear here once the script is written.</p>}
        </ul>
      )}

      {out === "characters" && (
        <div className="grid gap-4 md:grid-cols-2">
          {chars.map((c) => {
            const on = c.id === cid;
            return (
              <section key={c.id} className={`rounded-3xl border p-4 ${on ? "border-[rgba(185,172,255,0.8)]" : "border-border opacity-70"}`}>
                <div className="flex gap-4">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={skills.character(`${c.id}_2d.jpg`)} alt={c.name} className="h-40 w-28 shrink-0 rounded-2xl bg-muted object-contain" />
                  <div className="min-w-0"><p className="text-sm font-semibold">{c.name}{on && <span className="ml-2 rounded-full bg-primary/20 px-2 py-0.5 text-[10px] font-medium">in this video</span>}</p>
                    <p className="mt-1 text-[12px] text-muted-foreground">{c.about}</p>
                    {on && <p className="mt-2 text-[12px] text-muted-foreground">On screen in {scenes.length || "every"} scenes. A cartoon stand-in for the founder, never a real person&apos;s face.</p>}
                    {!on && !busy && !waiting && r.media === "media" && <button type="button" onClick={() => change.mutate({ character: c.id })} className={`${btn} mt-3`}>Use this character</button>}</div>
                </div>
              </section>
            );
          })}
        </div>
      )}

      {out === "timeline" && (scenes.length ? <Timeline duration={total} lanes={lanes} time={time} onSeek={seek} /> : <p className="rounded-2xl border border-dashed border-border p-10 text-center text-sm text-muted-foreground">The timeline fills in as scenes are made. Card timings are approximate.</p>)}
    </div>
  );

  return (
    <div className="w-full px-4 py-5 md:px-8 2xl:px-12">
      <div className="mb-5 flex flex-wrap items-center gap-3">
        <div className="min-w-0 flex-1"><StepTabs steps={steps} active={step} onChange={(id) => setPick(id as StepId)} /></div>
        {r.status === "error" && <span className="inline-flex items-center gap-1.5 text-xs text-red-400"><TriangleAlert className="h-4 w-4" />Stopped with a problem</span>}
      </div>
      <SplitPane left={left} right={right} />
    </div>
  );
}
