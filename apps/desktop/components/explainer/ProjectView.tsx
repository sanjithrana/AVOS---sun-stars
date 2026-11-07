"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ClipboardCopy, Download, RotateCcw, Trash2 } from "lucide-react";
import Link from "next/link";
import { explainer, type Project, type Shot } from "@/lib/explainer";
import { ShotCard } from "./ShotCard";
import { CharactersView, Context, StoryboardView, Tabs, type Sel, type View } from "./Workspace";
import { FadeImg } from "./FadeImg";
import { FloatingAgent } from "./FloatingAgent";

const NEXT_HELP: Record<string, string> = {
  plan: "Read the script and shot list below. Change any line or pick how a shot is made, then approve.",
  design: "These are the characters, set and props every picture is drawn from. Redraw any you don't like, then approve to draw the storyboard.",
  board: "These are the pictures every shot starts from. Redo any you don't like, then approve to make the video.",
};

export function ProjectView({ id }: { id: string }) {
  const router = useRouter();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["explainer", id], queryFn: () => explainer.get(id), refetchInterval: (s) => (s.state.data?.busy || s.state.data?.status === "working" ? 2000 : 6000), retry: false });
  const p = q.data;
  const set = (np: Project) => qc.setQueryData(["explainer", id], np);
  const [draft, setDraft] = useState<Record<string, Partial<Shot>>>({});
  const [view, setView] = useState<View>("shots");
  const [sel, setSel] = useState<Sel>({ scene: null, shot: null, char: null });
  const [started, setStarted] = useState(false);
  const go = (v: View, patch?: Partial<Sel>) => { setSel((s) => ({ ...s, ...patch })); setView(v === "scenes" || v === "timeline" ? "shots" : v); };
  useEffect(() => {
    if (p && !started) { setStarted(true); setView(p.status === "waiting" && p.stage === "plan" ? "shots" : p.status === "waiting" && p.stage === "design" ? "characters" : (p.board || p.contact) ? "storyboard" : "shots"); }
  }, [p, started]);
  const dirty = Object.keys(draft).length > 0;
  const [copied, setCopied] = useState(false);
  useEffect(() => { if (p?.status !== "waiting") setDraft({}); }, [p?.status]);

  const save = useMutation({ mutationFn: (shots: Shot[]) => explainer.patch(id, { plan: { shots } }), onSuccess: (np) => { set(np); setDraft({}); } });
  const approve = useMutation({ mutationFn: async () => {
    if (dirty && p?.plan) await explainer.patch(id, { plan: { shots: p.plan.shots.map((s) => ({ ...s, ...draft[s.id] })) } });
    return explainer.approve(id);
  }, onSuccess: (np) => { set(np); setDraft({}); } });
  const act = useMutation({ mutationFn: (f: () => Promise<Project | { ok: true }>) => f(), onSuccess: (r) => { if ("id" in r) set(r as Project); else qc.invalidateQueries({ queryKey: ["explainer", id] }); } });
  const del = useMutation({ mutationFn: () => explainer.remove(id), onSuccess: () => router.push("/explainer") });

  const shots = useMemo(() => (p?.plan?.shots ?? []).map((s) => ({ ...s, ...draft[s.id] })), [p, draft]);
  if (q.isError) return <p className="m-8 rounded-xl border border-amber-500/40 bg-amber-500/5 p-4 text-sm">{(q.error as Error).message}</p>;
  if (!p) return (
    <div className="mx-auto max-w-4xl space-y-6 px-4 py-8 md:px-8" aria-busy="true">
      <div className="h-8 w-2/3 animate-pulse rounded-lg bg-muted" />
      <div className="h-1.5 animate-pulse rounded-full bg-muted" />
      <div className="grid grid-cols-5 gap-2">{Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-9 animate-pulse rounded-xl bg-muted" />)}</div>
      <div className="h-64 animate-pulse rounded-xl bg-muted" />
    </div>
  );

  const gate = p.status === "waiting" ? (p.stage === "plan" ? "plan" : p.stage === "design" ? "design" : "board") : null;
  const running = p.status === "working";
  const err = act.error || approve.error || save.error;

  const assetsNode = !p.plan ? null : (
            <section data-testid="assets-panel">
              <h2 className="text-lg font-semibold">Characters &amp; world</h2>
              {p.plan.palette && p.plan.palette.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2" data-testid="palette">
                  {p.plan.palette.map((c) => (
                    <span key={c.hex} title={`${c.name} ${c.hex}`} className="inline-flex items-center gap-1.5 rounded-md border border-border px-2 py-1 text-[11px]">
                      <span className="h-3.5 w-3.5 rounded-full border border-black/10" style={{ background: c.hex }} />{c.name}</span>
                  ))}
                </div>
              )}
              <div className="mt-3 grid grid-cols-2 gap-3 xl:grid-cols-1">
                {[...(p.assets.poster ? [{ key: "poster", name: p.plan.title, look: p.plan.logline || "", kind: "Key visual" }] : []), ...p.plan.characters.map((c) => ({ key: `char:${c.id}`, name: c.name, look: c.look, kind: "Character" })),
                  ...p.plan.props.map((x) => ({ key: `prop:${x.id}`, name: x.name, look: x.look, kind: "Prop" })),
                  { key: "world", name: p.plan.world.name, look: p.plan.world.look, kind: "Set" }].map((a) => (
                  <figure key={a.key} className="overflow-hidden rounded-xl border border-border bg-card/50 transition-shadow duration-300 hover:shadow-md">
                    {p.assets[a.key] ? <FadeImg src={explainer.file(id, p.assets[a.key])} alt={a.name} className="w-full bg-muted" />
                      : <div className={`flex aspect-video items-center justify-center bg-muted text-xs text-muted-foreground ${p.stage === "design" && running ? "animate-pulse" : ""}`}>{p.stage === "design" && running ? "Drawing…" : "Drawn after you approve the script"}</div>}
                    <figcaption className="p-3 text-sm"><span className="text-xs uppercase tracking-wider text-muted-foreground">{a.kind}</span><br /><b>{a.name}</b><span className="block text-xs text-muted-foreground">{a.look}</span>
                      {gate === "design" && p.assets[a.key] && (
                        <button type="button" disabled={act.isPending} onClick={() => { const n = window.prompt("What should change? (optional)", "") ?? null; if (n !== null) act.mutate(() => explainer.redoAsset(id, a.key, n)); }}
                          className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1 text-xs hover:bg-accent" data-testid={`redo-${a.key}`}><RotateCcw className="h-3.5 w-3.5" />Redraw</button>
                      )}</figcaption>
                  </figure>
                ))}
              </div>
            </section>
  );

  const shotCard = (s: Shot) => (
    <ShotCard key={s.id} p={p} shot={s} editable={gate === "plan"} busy={running || p.busy}
      onEdit={(patch) => setDraft((d) => ({ ...d, [s.id]: { ...d[s.id], ...patch } }))}
      onAgain={(what, n, extra) => act.mutate(() => explainer.shotAgain(id, s.id, what, n, undefined, extra))}
      onRate={(up, n) => act.mutate(() => explainer.rate(id, s.id, up, n))} />
  );

  const sheetNode = (p.board || p.contact) ? (
            <section>
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-lg font-semibold">{p.board ? "Production storyboard" : "Storyboard"}</h2>
                {!p.board && !running && <button type="button" data-testid="build-sheet" onClick={() => act.mutate(() => explainer.storyboardSheet(id))} disabled={act.isPending} className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-[#8873be] disabled:opacity-50">{act.isPending ? "Building…" : "Build the detailed storyboard sheet"}</button>}
                {p.board && <a href={explainer.file(id, p.board, p.updatedAt)} target="_blank" rel="noreferrer" download={`${p.title || "storyboard"}.png`} className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm transition hover:bg-accent"><Download className="h-4 w-4" />Open full size</a>}
              </div>
              {!p.board && p.board_error && <p className="mt-2 text-sm text-[#b85f6b]" role="alert">The detailed sheet could not be drawn: {p.board_error}</p>}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={explainer.file(id, (p.board || p.contact) as string, p.updatedAt)} alt="Storyboard: key visual, every shot with action, camera, lighting and mood, characters, set and palette" className="mt-3 w-full animate-in fade-in rounded-xl border border-border duration-500" data-testid="storyboard-overview" />
            </section>
  ) : <p className="text-sm text-muted-foreground">The storyboard is drawn after you approve the characters.</p>;

  const gateInfo = gate ? {
    title: gate === "plan" ? "Step 1 of 3: approve the script" : gate === "design" ? "Step 2 of 3: approve the characters and backgrounds" : "Step 3 of 3: approve the storyboard",
    help: NEXT_HELP[gate], pending: approve.isPending, onApprove: () => approve.mutate(),
    action: gate === "plan" ? "Approve and draw the characters" : gate === "design" ? "Approve and draw the storyboard" : "Approve and make the video",
  } : null;
  const shown = view === "scenes" || view === "timeline" ? "shots" : view;

  return (
    <div className="w-full px-4 py-5 animate-in fade-in duration-500 md:px-8 2xl:px-12">
      {/* the agent: a floating window you can drag, resize, fold or close to a button */}
      <FloatingAgent p={p} gate={gateInfo} busy={act.isPending} error={p.status === "error" || p.status === "stopped" ? (p.error || "Stopped.") : null}
        onStop={() => act.mutate(() => explainer.cancel(id))} onContinue={() => act.mutate(() => explainer.resume(id))}
        onDirect={(n, scope) => act.mutate(() => explainer.direct(id, n, scope))} onRewrite={(n) => act.mutate(() => explainer.redoPlan(id, n))} />
      <div>
        {/* the output */}
        <div className="min-w-0 space-y-6">
          <div>
            <Link href="/explainer" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="h-4 w-4" />All videos</Link>
            <div className="mt-2 flex flex-wrap items-start gap-3">
              <div className="w-full min-w-0 sm:w-auto sm:flex-1">
                <h1 className="text-2xl font-bold leading-tight sm:text-3xl" data-testid="explainer-title">{p.title || p.brief}</h1>
                <p className="mt-1 text-xs text-muted-foreground">{p.totalSeconds || p.seconds}s · {p.aspect}{p.plan ? ` · ${p.plan.shots.length} shots` : ""}</p>
                {p.source && <a href={p.source.url} target="_blank" rel="noreferrer" className="text-xs text-[var(--signal)] underline">Source: {p.source.title}</a>}
              </div>
              {p.plan && <button type="button" onClick={async () => { const r = await explainer.masterPrompt(id); await navigator.clipboard.writeText(r.text); setCopied(true); setTimeout(() => setCopied(false), 2500); }}
                className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-sm hover:bg-accent" data-testid="master-prompt" title="One timed multi-shot prompt for Seedance, Kling, Veo and similar tools">
                <ClipboardCopy className="h-4 w-4" />{copied ? "Copied" : "Copy master prompt"}</button>}
              {p.plan && <a href={explainer.picturePrompts(id)} download className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-sm hover:bg-accent" data-testid="picture-prompts"
                title="Every shot's picture prompt as a plain text file, one per paragraph, to paste into any picture model"><Download className="h-4 w-4" />Picture prompts (.txt)</a>}
              {p.plan && shots.some((s) => s.frame) && <a href={explainer.shotPack(id)} download className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-sm hover:bg-accent" data-testid="shot-pack"
                title="First and last frame, motion prompt and timing of every shot, for Kling, Runway, OpenArt and other video sites. Bring the clips back with Use my clip on each shot."><Download className="h-4 w-4" />Shot pack for video sites</a>}
              <button type="button" onClick={() => { if (window.confirm("Delete this video and all its files?")) del.mutate(); }} className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-sm text-muted-foreground hover:bg-accent" aria-label="Delete"><Trash2 className="h-4 w-4" /></button>
            </div>
          </div>

          {gate === "plan" && dirty && (
            <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-[rgba(185,172,255,0.45)] p-3 text-sm">
              <span className="text-muted-foreground">You changed the script.</span>
              <button type="button" onClick={() => save.mutate(shots)} className="rounded-full border border-border px-4 py-1.5 text-sm hover:bg-accent">Save changes</button>
            </div>
          )}
          {err && <p className="rounded-xl border border-red-500/40 bg-red-500/5 p-3 text-sm" role="alert">{(err as Error).message}</p>}

          {p.final && (
            <section className="animate-in fade-in zoom-in-95 rounded-2xl border border-emerald-500/40 bg-emerald-500/5 p-5 duration-500 md:p-6" data-testid="explainer-final">
              <h2 className="text-lg font-semibold">Your video is ready</h2>
              <div className="mt-4 flex flex-col items-stretch gap-4 sm:flex-row sm:items-start">
                <video src={explainer.file(id, p.final, p.updatedAt)} controls playsInline className={`w-full rounded-xl bg-black ${p.aspect === "16:9" ? "" : "max-h-[70vh] sm:w-auto"}`} />
                <div className="space-y-2 text-sm">
                  <p className="text-muted-foreground">{p.finalSeconds}s, with voice and word-by-word captions.</p>
                  {shots.some((s) => s.engine === "still") && (
                    <p className="max-w-md rounded-xl border border-[rgba(185,172,255,0.35)] p-3 text-xs leading-relaxed text-muted-foreground" data-testid="motion-hint">
                      {shots.filter((s) => s.engine === "still").length} shots are animatics (pictures with a camera move), because no video model is ready here.
                      For real motion: download the <a href={explainer.shotPack(id)} download className="text-[var(--signal)] underline">shot pack</a>, make each shot on Kling, Runway or OpenArt from its first and last frame, then press <b>Use my clip</b> on the shot. Or add fal.ai credit in Settings and press Make clip again.
                    </p>
                  )}
                  <a href={explainer.file(id, p.final)} download className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 font-semibold text-white"><Download className="h-4 w-4" />Download MP4</a>
                </div>
              </div>
            </section>
          )}

          <div className="xl:grid xl:grid-cols-[minmax(0,1fr)_340px] xl:gap-6 2xl:grid-cols-[minmax(0,1fr)_400px] 2xl:gap-8">
          <div className="min-w-0 space-y-6">
          {shots.length > 0 && <Tabs view={shown} onView={(v) => setView(v)} />}

          {p.research && shown === "shots" && (
            <details className="rounded-xl border border-border bg-card/50 p-4 text-sm" open={p.research.status === "ok" && !shots.length} data-testid="research-panel">
              <summary className="cursor-pointer text-base font-semibold">
                Research{p.research.status === "ok" ? ` · ${p.research.facts.length} facts from ${p.research.sources.length} sources` : " · skipped"}
              </summary>
              {p.research.status !== "ok" ? (
                <p className="mt-3 text-muted-foreground">The script was written without checked facts: {p.research.reason || "no reason given"}.</p>
              ) : (
                <div className="mt-3 space-y-3">
                  <ul className="space-y-2">
                    {p.research.facts.map((f, i) => (
                      <li key={i} className="flex gap-2"><span className="text-[var(--signal)]">✓</span>
                        <span>{f.fact} <a href={f.source.url} target="_blank" rel="noreferrer" className="whitespace-nowrap text-xs text-muted-foreground underline">{f.source.title}</a></span></li>
                    ))}
                  </ul>
                  {p.research.misconceptions.length > 0 && <p><b>Common mistakes:</b> {p.research.misconceptions.join(" · ")}</p>}
                  {p.research.unknowns.length > 0 && <p><b>Still uncertain:</b> {p.research.unknowns.join(" · ")}</p>}
                </div>
              )}
            </details>
          )}

          {shown === "storyboard" && <StoryboardView p={p} shots={shots} sheet={sheetNode} go={go} />}
          {shown === "characters" && (
            <div className="space-y-6">
              {gate === "design" && assetsNode}
              <CharactersView p={p} shots={shots} sel={sel} go={go} />
            </div>
          )}

          {shots.length > 0 && shown === "shots" && (
            <section>
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-lg font-semibold">{sel.shot ? `Shot ${sel.shot}` : "Shots"}</h2>
                {sel.shot && <button type="button" onClick={() => setSel((s) => ({ ...s, shot: null }))} className="rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-secondary">Show all shots</button>}
              </div>
              <div className="mt-3 space-y-4">
                {shots.filter((s) => !sel.shot || s.id === sel.shot).map((s) => shotCard(s))}
              </div>
            </section>
          )}
          {!shots.length && <p className="rounded-2xl border border-dashed border-border p-10 text-center text-sm text-muted-foreground">The script and shots appear here as the crew writes them.</p>}
          </div>
          <aside className="mt-6 space-y-6 xl:sticky xl:top-4 xl:mt-0 xl:max-h-[calc(100dvh-8rem)] xl:self-start xl:overflow-y-auto">
            {p.plan && <Context view={shown} p={p} shots={shots} sel={sel} assets={assetsNode} />}
          </aside>
          </div>
        </div>
      </div>
    </div>
  );
}
