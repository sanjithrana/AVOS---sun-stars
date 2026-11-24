"use client";
import type { ReactNode } from "react";

/** A row of picture tiles (like the pickers in other clip makers): the picture shows what you get, the name sits under it. */
function Tiles({ label, value, onChange, items }: { label: string; value: string; onChange: (v: string) => void; items: { id: string; name: string; art: ReactNode }[] }) {
  return (
    <div role="radiogroup" aria-label={label} className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {items.map((it) => {
        const on = it.id === value;
        return (
          <button key={it.id} type="button" role="radio" aria-checked={on} onClick={() => onChange(it.id)}
            className={`flex flex-col overflow-hidden rounded-2xl border-2 text-left transition-all hover:-translate-y-0.5 ${on ? "border-primary bg-[rgba(200,255,58,0.14)] shadow-[0_0_28px_-8px_rgba(200,255,58,0.8)]" : "border-border hover:bg-muted"}`}>
            <span className="tile-dark flex h-28 items-center justify-center">{it.art}</span>
            <span className="px-3 py-2 text-sm font-medium">{it.name}</span>
          </button>
        );
      })}
    </div>
  );
}

const sample = "select-none text-center font-black leading-[1.05] tracking-tight";
const hi = "inline-block px-0.5";

/** Each tile is a phone-shaped colour card with the style drawn on it, like the style pickers in other clip makers. */
const CAPTION_ART: Record<string, { tile: string; art: ReactNode }> = {
  bounce: { tile: "tile-amber", art: <span className={`${sample} text-[15px] text-white`} style={{ textShadow: "0 2px 0 rgba(0,0,0,.55)" }}>THIS IS<br /><span className={`${hi} -rotate-2 scale-110 bg-white text-[#d6155f]`} style={{ textShadow: "none" }}>THE</span> MOMENT</span> },
  hype: { tile: "tile-pink", art: <span className={`${sample} text-[16px] uppercase italic text-white`} style={{ WebkitTextStroke: "1px rgba(0,0,0,.6)", textShadow: "0 3px 0 rgba(0,0,0,.4)" }}>THIS IS <span className="text-yellow-300">THE</span><br />MOMENT</span> },
  clean: { tile: "tile-violet", art: <span className="select-none text-center text-[13px] font-medium leading-tight text-white">this is the<br /><span className="border-b-2 border-white/90">moment</span></span> },
  none: { tile: "tile-dark", art: <span className="select-none text-center text-[12px] text-white/60 line-through decoration-2">no captions</span> },
};

export function CaptionPicker({ value, onChange, options }: { value: string; onChange: (v: string) => void; options: Record<string, string> }) {
  return (
    <div role="radiogroup" aria-label="Caption style" className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {Object.entries(options).map(([id, name]) => {
        const on = id === value, t = CAPTION_ART[id] ?? CAPTION_ART.none;
        return (
          <button key={id} type="button" role="radio" aria-checked={on} onClick={() => onChange(id)}
            className={`group relative flex flex-col overflow-hidden rounded-2xl border-2 text-left transition-all hover:-translate-y-0.5 ${on ? "border-primary shadow-[0_0_28px_-8px_rgba(200,255,58,0.8)]" : "border-transparent"}`}>
            <span className={`${t.tile} flex h-32 items-end justify-center px-3 pb-4`}>{t.art}</span>
            <span className="flex items-center justify-between bg-[#0a0a0d] px-3 py-2 text-sm font-medium text-white">{name}{on && <span className="text-[10px] font-semibold uppercase tracking-widest text-[var(--signal)]">Selected</span>}</span>
          </button>
        );
      })}
    </div>
  );
}

/** A small phone (9:16) with the picture inside, drawn the way each layout frames a wide video. */
function Phone({ children }: { children: ReactNode }) {
  return <span className="relative block h-20 w-11 overflow-hidden border border-white/40 bg-black">{children}</span>;
}
const pic = "bg-gradient-to-br from-fuchsia-500 via-pink-400 to-orange-300";
const LAYOUT_ART: Record<string, ReactNode> = {
  auto: <Phone><span className={`absolute inset-x-0 top-0 h-1/2 ${pic}`} /><span className="absolute inset-x-0 top-1/2 h-1/2 bg-gradient-to-br from-sky-500 to-indigo-400" /><span className="absolute left-1/2 top-1/4 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-yellow-300" /><span className="absolute left-1/2 top-3/4 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-yellow-300" /></Phone>,
  game: <Phone><span className="absolute inset-0 scale-150 bg-gradient-to-br from-emerald-700 to-sky-900 opacity-60 blur-[3px]" /><span className="absolute left-0 right-0 top-1/2 h-9 -translate-y-1/2 bg-gradient-to-br from-emerald-400 via-lime-300 to-sky-500" /><span className="absolute left-1/2 top-1/2 h-1.5 w-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-red-500" /></Phone>,
  blur: <Phone><span className={`absolute inset-0 scale-150 opacity-70 blur-[3px] ${pic}`} /><span className={`absolute left-0 right-0 top-1/2 h-6 -translate-y-1/2 ${pic}`} /></Phone>,
  zoom: <Phone><span className={`absolute left-1/2 top-1/2 h-16 w-16 -translate-x-1/2 -translate-y-1/2 ${pic}`} /></Phone>,
  fill: <Phone><span className={`absolute inset-0 ${pic}`} /><span className="absolute inset-x-1 bottom-2 h-1.5 bg-white/70" /></Phone>,
  centered: <Phone><span className="absolute inset-0 bg-zinc-800" /><span className={`absolute inset-x-1.5 top-1/2 h-6 -translate-y-1/2 rounded ${pic}`} /></Phone>,
  wide: <Phone><span className="absolute inset-0 bg-white" /><span className="absolute inset-x-1.5 top-[22%] h-1 bg-zinc-800" /><span className="absolute inset-x-1.5 top-[28%] h-1 w-2/3 bg-zinc-800" /><span className={`absolute inset-x-1.5 top-[38%] h-6 rounded ${pic}`} /></Phone>,
  split: <Phone><span className="absolute inset-x-0 top-0 h-1/2 bg-gradient-to-br from-amber-400 to-rose-500" /><span className="absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-br from-sky-400 to-indigo-500" /></Phone>,
  pip: <Phone><span className="absolute inset-0 bg-gradient-to-br from-amber-400 to-rose-500" /><span className="absolute right-1 top-2 h-5 w-4 border border-white bg-gradient-to-br from-sky-400 to-indigo-500" /></Phone>,
  trio: <Phone><span className="absolute inset-x-0 top-0 h-1/3 bg-gradient-to-br from-amber-400 to-rose-500" /><span className="absolute inset-x-0 top-1/3 h-1/3 bg-gradient-to-br from-sky-400 to-indigo-500" /><span className="absolute inset-x-0 bottom-0 h-1/3 bg-gradient-to-br from-emerald-400 to-teal-600" /></Phone>,
};

export function LayoutPicker({ value, onChange, options }: { value: string; onChange: (v: string) => void; options: Record<string, string> }) {
  return <Tiles label="Layout" value={value} onChange={onChange} items={Object.entries(options).map(([id, name]) => ({ id, name, art: LAYOUT_ART[id] ?? <Phone><span className={`absolute inset-0 ${pic}`} /></Phone> }))} />;
}
