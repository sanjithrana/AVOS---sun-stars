"use client";
// The series' Design DNA (look, camera grammar, motion grammar, sound): every prompt is compiled from it. Edit it,
// or rebuild it from the style pictures. Below it: the agents' SKILL.md files.
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BookOpen, ChevronDown, Dna, RefreshCw, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { seriesApi } from "./api";
import { field, type Act } from "./shared";
import { EASES, MOVES } from "./stage";
import type { DesignDNA } from "./types";

const TEXT: [keyof DesignDNA, string][] = [["medium", "Medium"], ["line", "Line"], ["shading", "Shading"], ["proportions", "Proportions"],
  ["texture", "Texture"], ["lighting", "Lighting"]];

export function DnaPanel({ sid, dna, act }: { sid: string; dna?: DesignDNA; act: Act }) {
  const [open, setOpen] = useState(false);
  const [d, setD] = useState<DesignDNA | null>(null);
  const cur = d ?? dna;
  const skills = useQuery({ queryKey: ["series", "skills"], queryFn: seriesApi.skills, enabled: open, staleTime: 60_000 });
  const set = (patch: Partial<DesignDNA>) => setD({ ...(cur as DesignDNA), ...patch });
  return (
    <div className="rounded-xl border border-border bg-card/30" data-testid="dna-panel">
      <button className="flex w-full items-center gap-2 p-4 text-left" onClick={() => setOpen(!open)}>
        <Dna className="h-4 w-4 text-amber-500" /><b className="text-sm text-foreground">Design DNA</b>
        <span className="truncate text-sm text-muted-foreground">{dna ? `${dna.medium} · ${dna.line}` : "written with the cast"}</span>
        <span className="flex gap-1">{(dna?.palette ?? []).map((c) => <i key={c} className="h-4 w-4 rounded" style={{ background: c }} title={c} />)}</span>
        <span className="grow" /><ChevronDown className={`h-4 w-4 transition ${open ? "rotate-180" : ""}`} />
      </button>
      {open && cur && (
        <div className="space-y-4 border-t border-border p-4 text-sm">
          <p className="text-xs text-muted-foreground">One look for every shot: the prompt compiler adds this to every picture and motion prompt. Changes apply to shots drawn from now on.</p>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            {TEXT.map(([k, label]) => (
              <label key={k} className="text-xs text-muted-foreground">{label}
                <input className={`${field} mt-1`} value={String(cur[k] ?? "")} onChange={(e) => set({ [k]: e.target.value } as Partial<DesignDNA>)} data-testid={`dna-${k}`} /></label>
            ))}
            <label className="text-xs text-muted-foreground">Palette (hex, comma separated)
              <input className={`${field} mt-1`} value={cur.palette.join(", ")} onChange={(e) => set({ palette: e.target.value.split(/[,\s]+/).filter(Boolean) })} /></label>
            <label className="text-xs text-muted-foreground">Motion feel
              <input className={`${field} mt-1`} value={cur.motion.feel} onChange={(e) => set({ motion: { ...cur.motion, feel: e.target.value } })} /></label>
            <label className="text-xs text-muted-foreground">Pacing / ease
              <span className="mt-1 flex gap-2"><input className={field} value={cur.motion.pacing} onChange={(e) => set({ motion: { ...cur.motion, pacing: e.target.value } })} />
                <select className={field} value={cur.motion.ease} onChange={(e) => set({ motion: { ...cur.motion, ease: e.target.value } })}>{EASES.map((x) => <option key={x}>{x}</option>)}</select></span></label>
            <label className="text-xs text-muted-foreground">Default lens (mm)
              <input type="number" className={`${field} mt-1`} value={cur.camera.default_lens} onChange={(e) => set({ camera: { ...cur.camera, default_lens: Number(e.target.value) } })} /></label>
            <label className="text-xs text-muted-foreground">Music
              <input className={`${field} mt-1`} value={cur.sound.music} onChange={(e) => set({ sound: { ...cur.sound, music: e.target.value } })} /></label>
            <label className="text-xs text-muted-foreground">Ambience
              <input className={`${field} mt-1`} value={cur.sound.ambience} onChange={(e) => set({ sound: { ...cur.sound, ambience: e.target.value } })} /></label>
            <label className="text-xs text-muted-foreground">Sound effects style
              <input className={`${field} mt-1`} value={cur.sound.sfx_style} onChange={(e) => set({ sound: { ...cur.sound, sfx_style: e.target.value } })} /></label>
          </div>
          <div className="text-xs text-muted-foreground">Camera moves this series uses (none ticked = all):
            <div className="mt-1 flex flex-wrap gap-2">{MOVES.map((m) => (
              <label key={m} className="flex items-center gap-1"><input type="checkbox" checked={cur.camera.allowed_moves.includes(m)}
                onChange={() => set({ camera: { ...cur.camera, allowed_moves: cur.camera.allowed_moves.includes(m) ? cur.camera.allowed_moves.filter((x) => x !== m) : [...cur.camera.allowed_moves, m] } })} />{m.replace(/_/g, " ")}</label>))}</div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" disabled={!d} onClick={() => { void act("dna", () => seriesApi.edit(sid, { dna: d })); setD(null); }} data-testid="dna-save"><Save />Save the DNA</Button>
            <Button size="sm" variant="outline" onClick={() => act("dna", () => seriesApi.rebuildDna(sid))}><RefreshCw />Rebuild from the style pictures</Button>
          </div>
          <div className="border-t border-border pt-3" data-testid="skills">
            <b className="flex items-center gap-2 text-foreground"><BookOpen className="h-4 w-4 text-amber-500" />Agent skills</b>
            <p className="mt-1 text-xs text-muted-foreground">Each AI role reads its SKILL.md as its instructions. Edit them in <code>{skills.data?.dir ?? "apps/skills"}</code> to change how AVOS writes, directs and checks; no restart needed.</p>
            <ul className="mt-2 grid grid-cols-1 gap-1 text-xs md:grid-cols-2">
              {(skills.data?.skills ?? []).map((k) => <li key={k.name}><code className="text-amber-700 dark:text-amber-300">{k.name}</code> · {k.description}</li>)}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
