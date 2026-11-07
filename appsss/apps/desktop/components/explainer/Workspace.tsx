"use client";

import { useState, type ReactNode } from "react";
import { Download } from "lucide-react";
import { FadeImg } from "./FadeImg";
import { ENGINE_LABEL, TYPE_LABEL, explainer, type Engine, type Project, type Shot } from "@/lib/explainer";

export type View = "storyboard" | "shots" | "scenes" | "timeline" | "characters";
export interface Sel { scene: number | null; shot: string | null; char: string | null }
export interface Go { (view: View, patch?: Partial<Sel>): void }

export const TABS: [View, string][] = [["storyboard", "Storyboard"], ["shots", "Shots"], ["characters", "Characters"]];

export interface Scene { n: number; title: string; shots: Shot[]; seconds: number }
export function sceneGroups(shots: Shot[]): Scene[] {
  const m = new Map<number, Shot[]>();
  for (const s of shots) { const n = s.scene ?? 1; m.set(n, [...(m.get(n) ?? []), s]); }
  return [...m.entries()].sort((a, b) => a[0] - b[0]).map(([n, list]) => ({ n, title: list.find((s) => s.scene_title)?.scene_title ?? "", shots: list, seconds: list.reduce((a, s) => a + (s.seconds || 0), 0) }));
}
const uniq = <T,>(xs: T[]) => [...new Set(xs)];
const secs = (n: number) => `${Math.round(n * 10) / 10}s`;

function Thumb({ p, s, className = "" }: { p: Project; s: Shot; className?: string }) {
  return s.frame ? <FadeImg src={explainer.file(p.id, s.frame, String(s.version))} alt={s.id} className={`h-full w-full object-cover ${className}`} />
    : <div className="flex h-full w-full items-center justify-center bg-muted text-[10px] text-muted-foreground">{s.id}</div>;
}

const card = "rounded-xl border border-border bg-card p-4";
const label = "text-[11px] font-semibold uppercase tracking-wider text-muted-foreground";
const chip = (on: boolean) => `shrink-0 rounded-lg border px-3 py-1.5 text-sm transition-colors ${on ? "border-primary bg-accent text-foreground" : "border-border text-muted-foreground hover:bg-secondary"}`;

/** One navigation row for the whole workspace. */
export function Tabs({ view, onView }: { view: View; onView: (v: View) => void }) {
  return (
    <div className="flex flex-nowrap items-center gap-1 overflow-x-auto whitespace-nowrap border-b border-border" role="tablist" aria-label="Workspace" data-testid="view-tabs">
      {TABS.map(([v, l]) => (
        <button key={v} type="button" role="tab" aria-selected={view === v} data-testid={`tab-${v}`} onClick={() => onView(v)}
          className={`-mb-px shrink-0 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors ${view === v ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"}`}>{l}</button>
      ))}
    </div>
  );
}

type Level = "overview" | "cast" | "world" | "scenes" | "clips";
const LEVELS: [Level, string, string][] = [
  ["overview", "Overview", "The whole production on one sheet."],
  ["cast", "Cast", "One board per character: identity portrait, design sheet and the locked look every shot uses."],
  ["world", "World", "The set and every prop, exactly as they appear in the shots."],
  ["scenes", "Scenes", "Scene by scene: the shots in order, with action, camera and the spoken line."],
  ["clips", "Clips", "Clip by clip: first frame to last frame, what moves, the camera and the timing."],
];

function Board({ p, rel, alt }: { p: Project; rel: string; alt: string }) {
  const src = explainer.file(p.id, rel, p.updatedAt);
  return (
    <figure className="group relative">
      <FadeImg src={src} alt={alt} className="w-full rounded-xl border border-border bg-muted" />
      <a href={src} target="_blank" rel="noreferrer" className="absolute right-3 top-3 inline-flex items-center gap-1.5 rounded-full border border-border bg-black/70 px-3 py-1.5 text-xs opacity-0 transition group-hover:opacity-100 focus-visible:opacity-100"><Download className="h-3.5 w-3.5" />Full size</a>
    </figure>
  );
}

/** Storyboard in levels, like a real production: overview, cast, world, scene by scene, clip by clip. */
export function StoryboardView({ p, shots, sheet, go }: { p: Project; shots: Shot[]; sheet: ReactNode; go: Go }) {
  const [level, setLevel] = useState<Level>("overview");
  const b = p.boards;
  const scenes = sceneGroups(shots);
  const chars = p.plan?.characters ?? [];
  const [pick, setPick] = useState<string | null>(null);
  const help = LEVELS.find((l) => l[0] === level)?.[2];
  const empty = <p className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">These boards are laid out when the storyboard is drawn.</p>;
  return (
    <div className="space-y-5" data-testid="view-storyboard">
      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Storyboard level">
        {LEVELS.map(([v, l]) => (
          <button key={v} type="button" role="tab" aria-selected={level === v} data-testid={`level-${v}`} onClick={() => { setLevel(v); setPick(null); }} className={chip(level === v)}>{l}</button>
        ))}
      </div>
      <p className="text-sm text-muted-foreground">{help}</p>
      {level === "overview" && (
        <>
          {sheet}
          <section className="space-y-3">
            {scenes.map((sc) => (
              <div key={sc.n} className={card}>
                <button type="button" onClick={() => { setLevel("scenes"); setPick(String(sc.n)); }} className="text-left text-sm font-semibold hover:text-[var(--signal)]">
                  Scene {sc.n}{sc.title ? <span className="font-normal text-muted-foreground"> — {sc.title}</span> : null}
                  <span className="ml-2 text-xs font-normal text-muted-foreground">{secs(sc.seconds)} · {sc.shots.length} shots</span>
                </button>
                <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
                  {sc.shots.map((s) => (
                    <button key={s.id} type="button" onClick={() => { setLevel("clips"); setPick(s.id); }} className="w-32 shrink-0 text-left">
                      <div className="aspect-video overflow-hidden rounded-lg border border-border"><Thumb p={p} s={s} /></div>
                      <p className="mt-1 truncate text-[11px] text-muted-foreground">{s.id} · {secs(s.seconds)}</p>
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </section>
        </>
      )}
      {level === "cast" && (!b || !Object.keys(b.cast).length ? empty : (
        <div className="space-y-5">
          {chars.filter((c) => b.cast[c.id]).map((c) => (
            <section key={c.id} className="space-y-2">
              <h3 className="flex items-center gap-2 text-sm font-semibold">{c.name}{c.memory && <span className="rounded-full border border-[rgba(185,172,255,0.45)] px-2 py-0.5 text-[10px] font-medium text-[var(--signal)]">Remembered</span>}</h3>
              <Board p={p} rel={b.cast[c.id]} alt={`${c.name}: identity portrait, design sheet and locked look`} />
            </section>
          ))}
        </div>
      ))}
      {level === "world" && (!b?.world ? empty : <Board p={p} rel={b.world} alt="The set and every prop" />)}
      {level === "scenes" && (!b || !Object.keys(b.scenes).length ? empty : (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-2">
            {scenes.map((sc) => <button key={sc.n} type="button" onClick={() => setPick(String(sc.n))} aria-pressed={(pick ?? String(scenes[0]?.n)) === String(sc.n)} className={chip((pick ?? String(scenes[0]?.n)) === String(sc.n))}>Scene {sc.n}{sc.title ? ` · ${sc.title}` : ""}</button>)}
          </div>
          {(() => { const n = pick ?? String(scenes[0]?.n); return b.scenes[n] ? <Board p={p} rel={b.scenes[n]} alt={`Scene ${n} board`} /> : empty; })()}
          <button type="button" onClick={() => go("shots", { scene: Number(pick ?? scenes[0]?.n), shot: null })} className="text-sm text-[var(--signal)] underline-offset-4 hover:underline">Open the shots to edit them</button>
        </div>
      ))}
      {level === "clips" && (!b || !Object.keys(b.clips).length ? empty : (
        <div className="space-y-4">
          <div className="flex gap-2 overflow-x-auto pb-1">
            {shots.map((s) => {
              const on = (pick ?? shots[0]?.id) === s.id;
              return (
                <button key={s.id} type="button" onClick={() => setPick(s.id)} aria-pressed={on} className={`w-28 shrink-0 text-left ${on ? "rounded-xl ring-2 ring-primary" : ""}`}>
                  <div className="aspect-video overflow-hidden rounded-lg border border-border"><Thumb p={p} s={s} /></div>
                  <p className="mt-1 truncate text-[11px] text-muted-foreground">{s.id}{s.end_frame ? " · 2 key poses" : ""}</p>
                </button>
              );
            })}
          </div>
          {(() => { const sid = pick ?? shots[0]?.id; return sid && b.clips[sid] ? <Board p={p} rel={b.clips[sid]} alt={`Clip ${sid}: first frame, last frame and what moves`} /> : empty; })()}
          <button type="button" onClick={() => go("shots", { shot: pick ?? shots[0]?.id })} className="text-sm text-[var(--signal)] underline-offset-4 hover:underline">Open this shot to redraw or change its prompts</button>
        </div>
      ))}
    </div>
  );
}

/** Scenes: pick a scene, see all of it; a shot opens its detail below without leaving the scene. */
export function ScenesView({ p, shots, sel, go, renderShot }: { p: Project; shots: Shot[]; sel: Sel; go: Go; renderShot: (s: Shot) => ReactNode }) {
  const scenes = sceneGroups(shots);
  const sc = scenes.find((x) => x.n === sel.scene) ?? scenes[0];
  if (!sc) return <p className="text-sm text-muted-foreground" data-testid="view-scenes">No scenes yet.</p>;
  const chars = p.plan?.characters ?? [];
  const props = p.plan?.props ?? [];
  const cIds = uniq(sc.shots.flatMap((s) => s.characters));
  const pIds = uniq(sc.shots.flatMap((s) => s.props));
  const shot = sc.shots.find((s) => s.id === sel.shot) ?? null;
  return (
    <div className="space-y-4" data-testid="view-scenes">
      <div className="flex gap-2 overflow-x-auto pb-1">
        {scenes.map((x) => <button key={x.n} type="button" onClick={() => go("scenes", { scene: x.n, shot: null })} aria-pressed={x.n === sc.n} className={chip(x.n === sc.n)}>Scene {x.n}{x.title ? ` · ${x.title}` : ""}</button>)}
      </div>
      <section className={card} data-testid="scene-detail">
        <p className={label}>Scene {String(sc.n).padStart(2, "0")}</p>
        <h2 className="mt-1 text-xl font-semibold">{sc.title || `Scene ${sc.n}`}</h2>
        <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
          <div><dt className={label}>Duration</dt><dd className="mt-0.5">{secs(sc.seconds)}</dd></div>
          <div><dt className={label}>Location</dt><dd className="mt-0.5">{p.plan?.world.name || "-"}</dd></div>
          <div><dt className={label}>Characters</dt><dd className="mt-0.5">{cIds.map((id) => chars.find((c) => c.id === id)?.name ?? id).join(", ") || "-"}</dd></div>
          <div><dt className={label}>Props</dt><dd className="mt-0.5">{pIds.map((id) => props.find((x) => x.id === id)?.name ?? id).join(", ") || "-"}</dd></div>
        </dl>
      </section>
      <section className={card}>
        <h3 className="text-sm font-semibold">Scene storyboard</h3>
        <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {sc.shots.map((s) => (
            <button key={s.id} type="button" onClick={() => go("scenes", { scene: sc.n, shot: s.id })} aria-pressed={sel.shot === s.id}
              className={`text-left ${sel.shot === s.id ? "ring-2 ring-primary rounded-xl" : ""}`}>
              <div className="aspect-video overflow-hidden rounded-lg border border-border"><Thumb p={p} s={s} /></div>
              <p className="mt-1 text-xs"><b>{s.id}</b> · {TYPE_LABEL[s.shot_type] ?? s.shot_type}</p>
              <p className="text-[11px] text-muted-foreground">{secs(s.seconds)}</p>
            </button>
          ))}
        </div>
      </section>
      <section className={card}>
        <h3 className="text-sm font-semibold">Scene direction</h3>
        <ul className="mt-2 space-y-1.5 text-sm text-muted-foreground">
          <li><b className="text-foreground">Objective:</b> {sc.shots.find((s) => s.objective)?.objective || "-"}</li>
          <li><b className="text-foreground">Visual progression:</b> {sc.shots.map((s) => TYPE_LABEL[s.shot_type] ?? s.shot_type).join(" → ")}</li>
          <li><b className="text-foreground">Audio:</b> {uniq(sc.shots.map((s) => s.sfx).filter(Boolean)).join("; ") || (sc.shots.some((s) => s.narration) ? "Voiceover" : "-")}</li>
          <li><b className="text-foreground">Mood:</b> {uniq(sc.shots.map((s) => s.mood).filter(Boolean) as string[]).join("; ") || "-"}</li>
          <li><b className="text-foreground">Continuity:</b> {uniq(sc.shots.map((s) => s.continuity).filter(Boolean) as string[]).join(" ") || "Keep the same characters, set and props."}</li>
        </ul>
      </section>
      {shot && <section aria-label={`Shot ${shot.id}`} data-testid="scene-shot">{renderShot(shot)}</section>}
    </div>
  );
}

/** Characters: the design sheet, who they are, and everywhere they appear. */
export function CharactersView({ p, shots, sel, go }: { p: Project; shots: Shot[]; sel: Sel; go: Go }) {
  const chars = p.plan?.characters ?? [];
  const c = chars.find((x) => x.id === sel.char) ?? chars[0];
  if (!c) return <p className="text-sm text-muted-foreground" data-testid="view-characters">No characters in this video.</p>;
  const img = p.assets[`char:${c.id}`];
  const appears = shots.filter((s) => s.characters.includes(c.id));
  const scenes = uniq(appears.map((s) => s.scene ?? 1));
  return (
    <div className="space-y-4" data-testid="view-characters">
      <div className="flex gap-2 overflow-x-auto pb-1">
        {chars.map((x) => <button key={x.id} type="button" onClick={() => go("characters", { char: x.id })} aria-pressed={x.id === c.id} className={chip(x.id === c.id)}>{x.name}</button>)}
      </div>
      <section className={card}>
        <p className={label}>Character{c.role ? ` · ${c.role}` : ""}</p>
        <h2 className="mt-1 flex items-center gap-2 text-xl font-semibold">{c.name}{c.memory && <span className="rounded-full border border-[rgba(185,172,255,0.45)] px-2 py-0.5 text-[11px] font-medium text-[var(--signal)]" data-testid="char-remembered">Remembered</span>}</h2>
        <p className="mt-2 text-sm text-muted-foreground">{c.look}</p>
        {p.assets[`ref:${c.id}`] && <FadeImg src={explainer.file(p.id, p.assets[`ref:${c.id}`])} alt={`${c.name} identity portrait`} className="mt-3 max-h-80 rounded-lg bg-muted" />}
        {c.voice && <p className="mt-2 text-sm"><b>Voice:</b> <span className="text-muted-foreground">{c.voice}</span></p>}
      </section>
      <section className={card}>
        <h3 className="text-sm font-semibold">Character design sheet</h3>
        {img ? <FadeImg src={explainer.file(p.id, img)} alt={`${c.name} design sheet`} className="mt-3 w-full rounded-lg bg-muted" />
          : <p className="mt-2 text-sm text-muted-foreground">Drawn after you approve the script.</p>}
        <p className="mt-2 text-xs text-muted-foreground">Every shot is drawn from this sheet: turnaround, expressions and costume details.</p>
      </section>
      <section className={card}>
        <h3 className="text-sm font-semibold">Appears in</h3>
        {appears.length === 0 ? <p className="mt-2 text-sm text-muted-foreground">Not in any shot.</p> : (
          <>
            <div className="mt-2 flex flex-wrap gap-2">
              {scenes.map((n) => <button key={n} type="button" onClick={() => go("scenes", { scene: n, shot: null })} className={chip(false)}>Scene {n}</button>)}
            </div>
            <div className="mt-3 grid grid-cols-3 gap-3 sm:grid-cols-4 lg:grid-cols-6">
              {appears.map((s) => (
                <button key={s.id} type="button" onClick={() => go("shots", { scene: s.scene ?? 1, shot: s.id })} className="text-left">
                  <div className="aspect-video overflow-hidden rounded-lg border border-border"><Thumb p={p} s={s} /></div>
                  <p className="mt-1 truncate text-[11px] text-muted-foreground">{s.id}</p>
                </button>
              ))}
            </div>
          </>
        )}
      </section>
      <section className={card}>
        <h3 className="text-sm font-semibold">Consistency</h3>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
          <li>{c.memory ? "Cast memory: this look, seed and portrait are reused in every video with this character." : "Saved to cast memory when you approve the characters, so the next video reuses this exact character."}</li>
          <li>The locked look is placed first in every shot prompt, and the identity portrait is the reference.</li>
          <li>{p.vision_check ? "Every frame was compared with the portrait; drifted frames were redrawn." : "Add a vision model to your AI crew (qwen2.5vl or gemma3) and every frame is compared with the portrait."}</li>
          <li>{p.plan?.palette?.length ? `Shared palette: ${p.plan.palette.map((x) => x.name).join(", ")}.` : "Shots share one palette."}</li>
          <li>A shot whose face drifted can be redrawn on the Shots tab.</li>
        </ul>
      </section>
    </div>
  );
}

/** The right panel changes with the tab. */
export function Context({ view, p, shots, sel, assets }: { view: View; p: Project; shots: Shot[]; sel: Sel; assets: ReactNode }) {
  const scenes = sceneGroups(shots);
  const chars = p.plan?.characters ?? [];
  if (view === "storyboard" || view === "characters" && !chars.length) return <>{assets}</>;
  if (view === "shots") {
    const s = shots.find((x) => x.id === sel.shot);
    if (!s) return <section className={card}><h2 className="text-sm font-semibold">Shot details</h2><p className="mt-2 text-sm text-muted-foreground">Pick a shot to see its references and how it is made.</p></section>;
    const eng = (s.force ?? s.engine) as Engine | null;
    return (
      <section className={card} data-testid="ctx-shot">
        <h2 className="text-sm font-semibold">{s.id} · references</h2>
        <div className="mt-3 aspect-video overflow-hidden rounded-lg border border-border"><Thumb p={p} s={s} /></div>
        <dl className="mt-3 space-y-2 text-sm">
          <div><dt className={label}>Made with</dt><dd>{eng ? ENGINE_LABEL[eng] : "Chosen when it starts"}{s.engine_why ? <span className="block text-xs text-muted-foreground">{s.engine_why}</span> : null}</dd></div>
          <div><dt className={label}>Picture model</dt><dd>{s.info?.model || "-"}{s.info?.note ? <span className="block text-xs text-muted-foreground">{s.info.note}</span> : null}</dd></div>
          <div><dt className={label}>Camera</dt><dd>{s.camera.type.replace(/_/g, " ")}, {s.camera.movement.replace(/_/g, " ")}, {s.camera.lens_mm}mm</dd></div>
          <div><dt className={label}>In the shot</dt><dd>{[...s.characters.map((id) => chars.find((c) => c.id === id)?.name ?? id), ...s.props.map((id) => p.plan?.props.find((x) => x.id === id)?.name ?? id)].join(", ") || "-"}</dd></div>
        </dl>
      </section>
    );
  }
  if (view === "scenes") {
    const sc = scenes.find((x) => x.n === sel.scene) ?? scenes[0];
    if (!sc) return null;
    const cIds = uniq(sc.shots.flatMap((s) => s.characters));
    const pIds = uniq(sc.shots.flatMap((s) => s.props));
    const a = [...cIds.map((id) => ({ key: `char:${id}`, name: chars.find((c) => c.id === id)?.name ?? id, kind: "Character" })), ...pIds.map((id) => ({ key: `prop:${id}`, name: p.plan?.props.find((x) => x.id === id)?.name ?? id, kind: "Prop" })), { key: "world", name: p.plan?.world.name ?? "Set", kind: "Set" }];
    return (
      <section className={card} data-testid="ctx-scene">
        <h2 className="text-sm font-semibold">Scene {sc.n} assets</h2>
        <div className="mt-3 grid grid-cols-2 gap-3">
          {a.map((x) => (
            <figure key={x.key}>
              {p.assets[x.key] ? <FadeImg src={explainer.file(p.id, p.assets[x.key])} alt={x.name} className="w-full rounded-lg bg-muted" /> : <div className="aspect-video rounded-lg bg-muted" />}
              <figcaption className="mt-1 text-xs"><span className="text-muted-foreground">{x.kind}</span><br />{x.name}</figcaption>
            </figure>
          ))}
        </div>
        <p className="mt-3 text-xs text-muted-foreground">Continuity: the same characters, set and props in every shot of this scene.</p>
      </section>
    );
  }
  if (view === "timeline") {
    const total = shots.reduce((t, s) => t + (s.seconds || 0), 0);
    return (
      <section className={card} data-testid="ctx-timeline">
        <h2 className="text-sm font-semibold">Audio and timing</h2>
        <dl className="mt-3 space-y-2 text-sm">
          <div><dt className={label}>Total length</dt><dd>{secs(total)} · {shots.length} shots · {scenes.length} scenes</dd></div>
          <div><dt className={label}>Voice</dt><dd>{p.voice || "Chosen voice"}</dd></div>
          <div><dt className={label}>Music</dt><dd>{p.plan?.music || "-"}</dd></div>
          {p.plan?.sound_design && <div><dt className={label}>Sound design</dt><dd>{p.plan.sound_design}</dd></div>}
        </dl>
      </section>
    );
  }
  const c = chars.find((x) => x.id === sel.char) ?? chars[0];
  return (
    <section className={card} data-testid="ctx-character">
      <h2 className="text-sm font-semibold">{c.name}</h2>
      {p.assets[`char:${c.id}`] && <FadeImg src={explainer.file(p.id, p.assets[`char:${c.id}`])} alt={c.name} className="mt-3 w-full rounded-lg bg-muted" />}
      <p className="mt-2 text-xs text-muted-foreground">{c.look}</p>
      {p.plan?.palette && p.plan.palette.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {p.plan.palette.map((x) => <span key={x.hex} className="inline-flex items-center gap-1.5 rounded-md border border-border px-2 py-1 text-[11px]"><span className="h-3 w-3 rounded-full border border-black/10" style={{ background: x.hex }} />{x.name}</span>)}
        </div>
      )}
    </section>
  );
}
