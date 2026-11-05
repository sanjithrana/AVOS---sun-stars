"use client";
// Stage 1: the AI's reading of your prompt, as an editable production breakdown: what it detected, the characters
// (their identity), the world, every timed shot (camera, angle, lens, timed actions, dialogue, sounds), the audio
// map and the continuity rules. Edit it as a table or as JSON, read the prompt again with a note, then approve.
import { useMemo, useState } from "react";
import { BookUser, Braces, CheckCircle2, Clapperboard, Clock, Loader2, Music2, Plus, RefreshCw, Save, Trash2, Users, Wand2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { seriesApi } from "@/components/series/api";
import { useLibrary } from "@/components/series/Library";
import { field, type Act } from "@/components/series/shared";
import { EASES, FRAMINGS, MOVES } from "@/components/series/stage";
import type { BdShot, Breakdown, SeriesSnapshot } from "@/components/series/types";

const ANGLES = ["eye level", "low angle", "high angle", "overhead"];
const EMOTIONS = ["neutral", "happy", "excited", "angry", "sad", "scared", "surprised", "sarcastic", "worried", "shout", "whisper", "laugh"];
const small = "rounded-lg border border-border bg-background px-2 py-1 text-xs text-foreground";
const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v)) as T;

export const eventsText = (s: BdShot) => s.events.map((e) => `${e.t.toFixed(1)} ${e.who ? `${e.who}: ` : ""}${e.action}`).join("\n");
export const sfxText = (s: BdShot) => s.sfx.map((e) => `${e.t !== null && e.t !== undefined ? `${e.t.toFixed(1)} ` : ""}${e.sound}`).join("; ");

export function parseEvents(text: string, names: string[]): BdShot["events"] {
  return text.split("\n").map((l) => l.trim()).filter(Boolean).map((l) => {
    const m = l.match(/^(\d+(?:\.\d+)?)\s*s?\s+(.*)$/);
    const t = m ? Number(m[1]) : 0;
    const rest = m ? m[2] : l;
    const w = rest.match(/^([^:]{1,30}):\s*(.+)$/);
    const who = w && names.some((n) => n.toLowerCase() === w[1].trim().toLowerCase()) ? names.find((n) => n.toLowerCase() === w[1].trim().toLowerCase())! : null;
    return { t, who, action: who && w ? w[2] : rest };
  });
}

export function parseSfx(text: string): BdShot["sfx"] {
  return text.split(";").map((x) => x.trim()).filter(Boolean).map((x) => {
    const m = x.match(/^(\d+(?:\.\d+)?)\s*s?\s+(.+)$/);
    return m ? { t: Number(m[1]), sound: m[2] } : { t: null, sound: x };
  });
}

function retimed(bd: Breakdown): Breakdown {
  let t = 0;
  const shots = bd.shots.map((s) => {
    const d = Math.max(0.5, Math.min(15, s.end - s.start));
    const out = { ...s, start: Math.round(t * 100) / 100, end: Math.round((t + d) * 100) / 100 };
    t += d;
    return out;
  });
  return { ...bd, shots, duration: Math.round(t * 100) / 100 };
}

export function BreakdownPanel({ sid, snap, act, pending }: { sid: string; snap: SeriesSnapshot; act: Act; pending: string | null }) {
  const s = snap.series;
  const src = s.breakdown;
  const [bd, setBd] = useState<Breakdown | null>(() => (src?.shots ? clone(src) : null));
  const [dirty, setDirty] = useState(false);
  const [json, setJson] = useState<string | null>(null);
  const [jsonErr, setJsonErr] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [prompt, setPrompt] = useState(s.prompt ?? "");
  const [showPrompt, setShowPrompt] = useState(false);
  const lib = useLibrary();
  const approved = src?.status === "approved";
  const [open, setOpen] = useState(!approved);
  const names = useMemo(() => (bd?.characters ?? []).map((c) => c.name), [bd]);

  if (!src || src.status === "analyzing") return (
    <p className="flex items-center gap-2 rounded-xl border border-border p-4 text-sm text-muted-foreground" data-testid="breakdown-working">
      <Loader2 className="h-4 w-4 animate-spin text-amber-500" />Reading your prompt: story, characters, world, timed shots, camera, sound…
    </p>
  );
  if (src.status === "error" || !bd) return (
    <div className="space-y-2 rounded-xl border border-red-500/40 bg-red-500/5 p-4">
      <p className="text-sm text-red-700 dark:text-red-300">{src.error || "The prompt couldn't be read."}</p>
      <textarea className={`${field} min-h-32 font-mono text-xs`} value={prompt} onChange={(e) => setPrompt(e.target.value)} />
      <Button size="sm" onClick={() => act("reanalyze", () => seriesApi.redoBreakdown(sid, note, prompt))}><RefreshCw />Read it again</Button>
    </div>
  );

  const set = (next: Breakdown) => { setBd(next); setDirty(true); };
  const shot = (i: number, patch: Partial<BdShot>) => set({ ...bd, shots: bd.shots.map((x, k) => (k === i ? { ...x, ...patch } : x)) });
  const total = bd.shots.reduce((a, x) => a + (x.end - x.start), 0) || 1;
  const d = src.detected;
  const save = () => act("save-breakdown", () => seriesApi.saveBreakdown(sid, retimed(bd))).then(() => setDirty(false));

  return (
    <div className="space-y-4" data-testid="breakdown">
      <div className="flex flex-wrap items-center gap-2">
        {d && [
          [d.story, "Story"], [d.characters > 0, `${d.characters} character${d.characters === 1 ? "" : "s"}`], [d.locations > 0, `${d.locations} place${d.locations === 1 ? "" : "s"}`],
          [d.shots > 0, `${d.shots} timed shots · ${d.seconds}s`], [d.camera > 0, `${d.camera} camera directions`], [d.dialogue > 0, `${d.dialogue} lines`],
          [d.sounds > 0, `${d.sounds} sounds`], [d.music, "music"], [d.rules > 0, `${d.rules} continuity rules`],
        ].map(([ok, label]) => (
          <span key={String(label)} className={`rounded-full px-2 py-0.5 text-[11px] ${ok ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300" : "bg-muted text-muted-foreground"}`}>{ok ? "✓" : "–"} {label}</span>
        ))}
        <span className="grow" />
        {approved && <Button size="sm" variant="ghost" onClick={() => setOpen(!open)} data-testid="breakdown-toggle">{open ? "Hide" : "Show / edit"} the breakdown</Button>}
      </div>

      <div className="flex h-8 overflow-hidden rounded-lg border border-border" data-testid="breakdown-bar" title="The film's shots in time">
        {bd.shots.map((x, i) => (
          <div key={x.id} className={`flex items-center overflow-hidden whitespace-nowrap border-r border-black/30 px-1 text-[10px] ${i % 2 ? "bg-amber-500/60" : "bg-amber-500/35"}`} style={{ width: `${(100 * (x.end - x.start)) / total}%` }}
            title={`${x.start}–${x.end}s · ${x.title}`}>{String(i + 1).padStart(2, "0")} {x.title}</div>
        ))}
      </div>

      {open && (
        <>
          <section className="space-y-2">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-foreground"><Users className="h-4 w-4 text-amber-500" />Characters: their identity is locked from this</h3>
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {bd.characters.map((c, i) => (
                <div key={i} className="space-y-1.5 rounded-xl border border-border bg-card/40 p-3" data-testid={`bd-char-${i}`}>
                  <div className="flex gap-2">
                    <input className={`${field} font-semibold`} value={c.name} onChange={(e) => set({ ...bd, characters: bd.characters.map((x, k) => (k === i ? { ...x, name: e.target.value } : x)) })} />
                    <button className="px-1 text-muted-foreground hover:text-red-500" title="Remove" onClick={() => set({ ...bd, characters: bd.characters.filter((_, k) => k !== i) })}><Trash2 className="h-4 w-4" /></button>
                  </div>
                  {(["look", "outfit", "props", "personality", "voice"] as const).map((k) => (
                    <textarea key={k} className={`${field} min-h-9 text-xs`} placeholder={k} value={c[k] ?? ""} onChange={(e) => set({ ...bd, characters: bd.characters.map((x, j) => (j === i ? { ...x, [k]: e.target.value } : x)) })} />
                  ))}
                  {(lib.data?.length ?? 0) > 0 && (
                    <label className="flex items-center gap-2 text-xs text-muted-foreground"><BookUser className="h-3.5 w-3.5" />Use from your library
                      <select className={small} value={c.library ?? ""} onChange={(e) => set({ ...bd, characters: bd.characters.map((x, j) => (j === i ? { ...x, library: e.target.value || undefined } : x)) })} data-testid="bd-library">
                        <option value="">— draw a new one —</option>{lib.data!.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
                      </select>
                    </label>
                  )}
                </div>
              ))}
              <button className="rounded-xl border border-dashed border-border p-3 text-sm text-muted-foreground hover:border-amber-500"
                onClick={() => set({ ...bd, characters: [...bd.characters, { name: `Character ${bd.characters.length + 1}`, look: "", outfit: "", props: "", personality: "", voice: "", gender: "other", age: "", actions: [] }] })}>
                <Plus className="mr-1 inline h-4 w-4" />Add a character
              </button>
            </div>
          </section>

          <section className="space-y-2">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-foreground"><Clapperboard className="h-4 w-4 text-amber-500" />World</h3>
            {bd.locations.map((l, i) => (
              <div key={i} className="flex gap-2">
                <input className={`${field} w-48`} value={l.name} onChange={(e) => set({ ...bd, locations: bd.locations.map((x, k) => (k === i ? { ...x, name: e.target.value } : x)) })} />
                <input className={field} value={l.description} placeholder="environment, materials, atmosphere, light" onChange={(e) => set({ ...bd, locations: bd.locations.map((x, k) => (k === i ? { ...x, description: e.target.value } : x)) })} />
              </div>
            ))}
            <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
              <input className={field} value={bd.style} placeholder="Style: 3D Pixar-style, cinematic lighting…" onChange={(e) => set({ ...bd, style: e.target.value })} />
              <input className={field} value={bd.tone} placeholder="Tone" onChange={(e) => set({ ...bd, tone: e.target.value })} />
            </div>
          </section>

          <section className="space-y-2">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-foreground"><Clock className="h-4 w-4 text-amber-500" />Shots ({bd.shots.length} · {total.toFixed(1)}s)</h3>
            <div className="space-y-2" data-testid="bd-shots">
              {bd.shots.map((x, i) => (
                <div key={x.id + i} className="grid grid-cols-1 gap-2 rounded-xl border border-border bg-card/30 p-3 lg:grid-cols-[11rem_1fr_1fr]" data-testid={`bd-shot-${i}`}>
                  <div className="space-y-1.5">
                    <div className="flex items-center gap-1">
                      <b className="rounded bg-amber-500 px-1.5 text-xs text-black">{String(i + 1).padStart(2, "0")}</b>
                      <span className="text-xs text-muted-foreground">{x.start.toFixed(1)}–{x.end.toFixed(1)}s</span>
                      <span className="grow" />
                      <button className="text-muted-foreground hover:text-red-500" title="Remove the shot" onClick={() => set({ ...bd, shots: bd.shots.filter((_, k) => k !== i) })}><Trash2 className="h-3.5 w-3.5" /></button>
                    </div>
                    <label className="flex items-center gap-1 text-[11px] text-muted-foreground">length
                      <input type="number" min={0.5} max={15} step={0.5} className={`${small} w-16`} value={Math.round((x.end - x.start) * 100) / 100} data-testid="bd-dur"
                        onChange={(e) => shot(i, { end: x.start + Math.max(0.5, Number(e.target.value) || 0.5) })} />s</label>
                    <select className={`${small} w-full`} value={x.framing} onChange={(e) => shot(i, { framing: e.target.value })}>{FRAMINGS.map((f) => <option key={f}>{f}</option>)}</select>
                    <select className={`${small} w-full`} value={x.angle} onChange={(e) => shot(i, { angle: e.target.value })}>{ANGLES.map((f) => <option key={f}>{f}</option>)}</select>
                    <select className={`${small} w-full`} value={x.camera} onChange={(e) => shot(i, { camera: e.target.value })} data-testid="bd-camera">{MOVES.map((f) => <option key={f} value={f}>{f.replace(/_/g, " ")}</option>)}</select>
                    <div className="flex gap-1">
                      <select className={`${small} w-full`} value={x.ease ?? ""} onChange={(e) => shot(i, { ease: e.target.value || undefined })}><option value="">ease</option>{EASES.map((f) => <option key={f}>{f}</option>)}</select>
                      <input className={`${small} w-16`} type="number" placeholder="mm" value={x.lens ?? ""} onChange={(e) => shot(i, { lens: e.target.value ? Number(e.target.value) : undefined })} />
                    </div>
                    <select className={`${small} w-full`} value={x.location} onChange={(e) => shot(i, { location: e.target.value })}>{bd.locations.map((l) => <option key={l.name}>{l.name}</option>)}</select>
                    {x.transition !== "cut" && <span className="text-[10px] text-muted-foreground">{x.transition}</span>}
                  </div>
                  <div className="space-y-1.5">
                    <input className={`${field} text-xs font-semibold`} value={x.title} onChange={(e) => shot(i, { title: e.target.value })} />
                    <textarea className={`${field} min-h-16 text-xs`} value={x.action} placeholder="What happens" onChange={(e) => shot(i, { action: e.target.value })} data-testid="bd-action" />
                    <textarea className={`${field} min-h-9 text-xs`} value={x.picture} placeholder="The first frame (what the storyboard frame shows)" onChange={(e) => shot(i, { picture: e.target.value })} />
                    <div className="flex flex-wrap gap-1">
                      {names.map((n) => (
                        <button key={n} className={`rounded-full px-2 py-0.5 text-[11px] ${x.characters.includes(n) ? "bg-amber-500 text-black" : "bg-muted text-muted-foreground"}`}
                          onClick={() => shot(i, { characters: x.characters.includes(n) ? x.characters.filter((c) => c !== n) : [...x.characters, n] })}>{n}</button>
                      ))}
                    </div>
                  </div>
                  <div className="space-y-1.5">
                    <TextList label="Timed actions (seconds from the shot's start, “1.6 Wolf: hits the puddle”)" value={eventsText(x)} onSave={(v) => shot(i, { events: parseEvents(v, names) })} testid="bd-events" />
                    {x.dialogue.map((ln, k) => (
                      <div key={k} className="flex gap-1">
                        <select className={small} value={ln.character} onChange={(e) => shot(i, { dialogue: x.dialogue.map((y, j) => (j === k ? { ...y, character: e.target.value } : y)) })}>{names.map((n) => <option key={n}>{n}</option>)}</select>
                        <select className={small} value={ln.emotion} onChange={(e) => shot(i, { dialogue: x.dialogue.map((y, j) => (j === k ? { ...y, emotion: e.target.value } : y)) })}>{EMOTIONS.map((n) => <option key={n}>{n}</option>)}</select>
                        <input className={`${small} min-w-0 flex-1`} value={ln.text} onChange={(e) => shot(i, { dialogue: x.dialogue.map((y, j) => (j === k ? { ...y, text: e.target.value } : y)) })} />
                        <button className="text-muted-foreground hover:text-red-500" onClick={() => shot(i, { dialogue: x.dialogue.filter((_, j) => j !== k) })}><Trash2 className="h-3.5 w-3.5" /></button>
                      </div>
                    ))}
                    {names.length > 0 && <button className="text-[11px] text-amber-600 hover:underline" onClick={() => shot(i, { dialogue: [...x.dialogue, { character: x.characters[0] ?? names[0], text: "", emotion: "neutral" }] })}>+ a line of dialogue</button>}
                    <TextList label="Sounds (“1.9 splash; engine hum”)" value={sfxText(x)} onSave={(v) => shot(i, { sfx: parseSfx(v) })} single testid="bd-sfx" />
                  </div>
                </div>
              ))}
              <button className="w-full rounded-xl border border-dashed border-border p-2 text-sm text-muted-foreground hover:border-amber-500" data-testid="bd-add-shot"
                onClick={() => { const last = bd.shots[bd.shots.length - 1]; const st = last ? last.end : 0;
                  set({ ...bd, shots: [...bd.shots, { id: `sh${bd.shots.length + 1}`, start: st, end: st + 2, title: `Shot ${bd.shots.length + 1}`, location: bd.locations[0]?.name ?? "", framing: "medium", angle: "eye level", camera: "static", characters: [], picture: "", action: "", events: [], dialogue: [], sfx: [], transition: "cut" }] }); }}>
                <Plus className="mr-1 inline h-4 w-4" />Add a shot
              </button>
            </div>
          </section>

          <section className="grid grid-cols-1 gap-2 md:grid-cols-2">
            <label className="text-xs text-muted-foreground"><Music2 className="mr-1 inline h-3.5 w-3.5" />Music
              <input className={`${field} mt-1`} value={bd.audio.music} onChange={(e) => set({ ...bd, audio: { ...bd.audio, music: e.target.value } })} /></label>
            <label className="text-xs text-muted-foreground">Ambience
              <input className={`${field} mt-1`} value={bd.audio.ambience} onChange={(e) => set({ ...bd, audio: { ...bd.audio, ambience: e.target.value } })} /></label>
            <label className="text-xs text-muted-foreground md:col-span-2">Continuity rules (one per line)
              <textarea className={`${field} mt-1 min-h-14`} value={bd.rules.join("\n")} onChange={(e) => set({ ...bd, rules: e.target.value.split("\n") })} /></label>
          </section>

          {json !== null && (
            <div className="space-y-1">
              <textarea className={`${field} min-h-64 font-mono text-[11px]`} value={json} onChange={(e) => setJson(e.target.value)} data-testid="bd-json" />
              {jsonErr && <p className="text-xs text-red-600">{jsonErr}</p>}
              <Button size="sm" variant="outline" onClick={() => { try { set(JSON.parse(json) as Breakdown); setJson(null); setJsonErr(null); } catch (e) { setJsonErr((e as Error).message); } }}>Use this JSON</Button>
            </div>
          )}
        </>
      )}

      <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3">
        {dirty && <Button size="sm" variant="outline" onClick={save} data-testid="save-breakdown"><Save />Save my edits</Button>}
        {!approved && <Button size="sm" disabled={dirty || !!pending || snap.busy} onClick={() => act("approve-breakdown", () => seriesApi.approveBreakdown(sid))} data-testid="approve-breakdown">
          <CheckCircle2 />Approve the breakdown: draw the characters and the world</Button>}
        {open && <Button size="sm" variant="ghost" onClick={() => { setJson(json === null ? JSON.stringify(bd, null, 1) : null); setJsonErr(null); }} data-testid="bd-json-toggle"><Braces />JSON</Button>}
        <Button size="sm" variant="ghost" onClick={() => setShowPrompt(!showPrompt)}><Wand2 />Prompt</Button>
      </div>
      {showPrompt && (
        <div className="space-y-2 rounded-xl border border-border p-3">
          <textarea className={`${field} min-h-40 font-mono text-xs`} value={prompt} onChange={(e) => setPrompt(e.target.value)} data-testid="bd-prompt" />
          <input className={field} value={note} onChange={(e) => setNote(e.target.value)} placeholder="A note for the analyst: e.g. split shot 5 into a wide and a close-up" data-testid="bd-note" />
          <Button size="sm" variant="outline" disabled={snap.busy} onClick={() => { void act("reanalyze", () => seriesApi.redoBreakdown(sid, note, prompt !== s.prompt ? prompt : undefined)); setNote(""); }} data-testid="bd-reanalyze">
            <RefreshCw />Read the prompt again</Button>
          <p className="text-[11px] text-muted-foreground">Reading again replaces the breakdown (your table edits are lost unless saved into the prompt).</p>
        </div>
      )}
    </div>
  );
}

function TextList({ label, value, onSave, single, testid }: { label: string; value: string; onSave: (v: string) => void; single?: boolean; testid?: string }) {
  const [v, setV] = useState(value);
  const [focus, setFocus] = useState(false);
  const shown = focus ? v : value;
  const props = { className: `${field} text-xs ${single ? "" : "min-h-14"}`, value: shown, placeholder: label, title: label, "data-testid": testid,
    onFocus: () => { setV(value); setFocus(true); }, onBlur: () => { setFocus(false); if (v !== value) onSave(v); } };
  return single ? <input {...props} onChange={(e) => setV(e.target.value)} /> : <textarea {...props} onChange={(e) => setV(e.target.value)} />;
}
