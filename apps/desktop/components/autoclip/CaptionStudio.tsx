"use client";
import { useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronUp, RotateCcw, Upload, X } from "lucide-react";
import { autoclip, type CapOpts, type CaptionStyle, type FontItem, type Overview } from "@/lib/autoclip";
import { Label, Note, Switch, btn, field } from "./ui";

export interface CaptionValue { caption: string; cap: CapOpts; cap_lang: string; whisper_model: string }

const SAMPLE = ["this", "changed", "everything"];
const GRID: { id: string; x: number; y: number; label: string }[] = [
  { id: "tl", x: 0.3, y: 0.2, label: "Top left" }, { id: "tc", x: 0.5, y: 0.2, label: "Top" }, { id: "tr", x: 0.7, y: 0.2, label: "Top right" },
  { id: "ml", x: 0.3, y: 0.5, label: "Middle left" }, { id: "mc", x: 0.5, y: 0.5, label: "Middle" }, { id: "mr", x: 0.7, y: 0.5, label: "Middle right" },
  { id: "bl", x: 0.3, y: 0.77, label: "Bottom left" }, { id: "bc", x: 0.5, y: 0.77, label: "Bottom (default)" }, { id: "br", x: 0.7, y: 0.77, label: "Bottom right" },
];
const LANGS: Record<string, string> = { auto: "As spoken", roman: "Hinglish (Hindi in Roman letters)", english: "English (translated)" };

/** @font-face rules so the style samples are drawn in the same fonts the clips are rendered with. */
function FontFaces({ fonts }: { fonts: FontItem[] }) {
  const css = fonts.filter((f) => f.file).map((f) => `@font-face{font-family:"${f.name.replace(/"/g, "")}";src:url("${autoclip.fontUrl(f.file)}");font-display:swap}`).join("\n");
  return <style>{css}</style>;
}

function Sample({ st, cap, big = false }: { st: CaptionStyle; cap?: CapOpts; big?: boolean }) {
  const c = cap ?? {};
  const upper = c.upper ?? !!st.upper;
  const text = c.text || st.text;
  const hi = c.hi || (st.hi === "cycle" ? "#FFE000" : st.hi);
  const ol = Math.max(0, Math.min(8, (c.outline ?? st.outline ?? 4) / (big ? 1.5 : 2.2)));
  const glow = c.glow === false ? "" : (st.glow || (c.glow ? hi : ""));
  const lay = st.layout || "line";
  const scale = ((c.size ?? 100) / 100) * (big ? 1.6 : 1) * Math.min(1.25, Math.max(0.7, (st.size ?? 0.047) / 0.047));
  const words = SAMPLE.slice(0, Math.max(1, Math.min(3, c.words ?? st.words)));
  const kw = words.reduce((k, w, i) => (w.length > words[k].length ? i : k), 0);
  const spoken = Math.min(1, words.length - 1);
  const font = (f?: string) => `"${f || c.font || st.font}", Poppins, system-ui, sans-serif`;
  const base: React.CSSProperties = {
    fontFamily: font(), fontSize: 17 * scale, lineHeight: 1.1, fontWeight: (c.bold ?? true) ? 800 : 500, fontStyle: (c.italic ?? st.italic) ? "italic" : "normal",
    textTransform: upper ? "uppercase" : "none", color: text, letterSpacing: st.spacing ? st.spacing / 2 : undefined,
    WebkitTextStroke: ol && !st.box && !st.tiles ? `${ol}px ${st.out || "#000"}` : undefined, paintOrder: "stroke fill",
    textShadow: glow ? `0 0 8px ${glow}, 0 0 14px ${glow}` : "0 2px 2px rgba(0,0,0,.7)",
  };
  const word = (i: number) => {
    const isK = ["top", "bottom", "mid", "inline", "cascade"].includes(lay) && i === kw;
    const s: React.CSSProperties = {};
    if (["top", "bottom", "mid", "inline", "cascade"].includes(lay)) {
      s.color = isK ? (st.kw || hi) : (st.rest || text);
      s.fontSize = 17 * scale * (isK ? (st.kw_scale ?? 1.5) * 0.75 : Math.max(0.62, st.rest_scale ?? 0.55));
      if (isK && st.kw_font) s.fontFamily = font(st.kw_font);
      if (isK && st.kw_italic) s.fontStyle = "italic";
      if (isK && st.kw_upper) s.textTransform = "uppercase";
    } else if (i === spoken) {
      s.color = st.hi === "cycle" && !c.hi ? "#3ce05a" : hi;
      if (st.underline) s.textDecoration = "underline";
      if (st.hi_font) s.fontFamily = font(st.hi_font);
      if (st.hi_italic) s.fontStyle = "italic";
    } else if (st.dim) s.opacity = 1 - st.dim / 255;
    if (st.tiles?.length) { s.background = st.tiles[i % st.tiles.length]; s.color = st.tile_text || text; s.padding = "0 4px"; s.WebkitTextStroke = "0"; if (i === spoken && st.tiles.length === 1) s.color = hi; }
    else if (st.hi_box && i === spoken) { s.background = st.hi_box; s.color = hi; s.padding = "0 4px"; s.WebkitTextStroke = "0"; }
    if (i !== spoken && st.blur) s.filter = `blur(${st.blur / 3}px)`;
    return <span key={i} style={s}>{words[i]}</span>;
  };
  let rows: number[][] = [words.map((_, i) => i)];
  const rest = words.map((_, i) => i).filter((i) => i !== kw);
  if (lay === "top") rows = [[kw], rest];
  else if (lay === "bottom") rows = [rest, [kw]];
  else if (lay === "mid") rows = [rest.filter((i) => i < kw), [kw], rest.filter((i) => i > kw)].filter((r) => r.length);
  else if (lay === "each" || lay === "cascade") rows = (lay === "cascade" ? [kw, ...rest] : words.map((_, i) => i)).map((i) => [i]);
  else if (lay === "two" && words.length > 2) rows = [[0, 1], [2]];
  return (
    <span style={{ ...base, background: st.box, padding: st.box ? "3px 8px" : undefined, display: "inline-block" }} className="select-none text-center">
      {rows.filter((r) => r.length).map((r, ri) => <span key={ri} className="block">{r.map((i, k) => <span key={i}>{word(i)}{k < r.length - 1 ? " " : ""}</span>)}</span>)}
    </span>
  );
}

export function CaptionStudio({ ov, v, set }: { ov: Overview; v: CaptionValue; set: (p: Partial<CaptionValue>) => void }) {
  const qc = useQueryClient();
  const cap = ov.capabilities;
  const styles = cap.caption_styles ?? {};
  const anims = cap.anims ?? {};
  const fontsQ = useQuery({ queryKey: ["autoclip", "fonts"], queryFn: autoclip.fonts, initialData: cap.fonts ? { fonts: cap.fonts } : undefined });
  const fonts = fontsQ.data?.fonts ?? [];
  const [open, setOpen] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const addFont = useMutation({ mutationFn: (f: File) => autoclip.fontAdd(f), onSuccess: (r) => { qc.setQueryData(["autoclip", "fonts"], { fonts: r.fonts }); setC({ font: r.added }); } });
  const delFont = useMutation({ mutationFn: (file: string) => autoclip.fontDel(file), onSuccess: (r) => { qc.setQueryData(["autoclip", "fonts"], { fonts: r.fonts }); if (!r.fonts.some((f) => f.name === v.cap.font)) setC({ font: undefined }); } });
  const st = styles[v.caption];
  const setC = (p: Partial<CapOpts>) => set({ cap: Object.fromEntries(Object.entries({ ...v.cap, ...p }).filter(([, x]) => x !== undefined && x !== "")) as CapOpts });
  const c = v.cap;
  const edited = Object.keys(c).length > 0;
  const models = cap.whisper_models ?? {};
  const mine = useMemo(() => fonts.filter((f) => f.mine), [fonts]);
  const toggle = (k: "bold" | "italic" | "upper", def: boolean) => setC({ [k]: !(c[k] ?? def) } as Partial<CapOpts>);
  const pill = (on: boolean) => `border px-3 py-1.5 text-sm ${on ? "border-[rgba(200,255,58,0.85)] bg-[rgba(200,255,58,0.12)]" : "border-border text-muted-foreground hover:text-foreground"}`;
  const gridOn = (g: { x: number; y: number }) => Math.abs((c.x ?? 0.5) - g.x) < 0.01 && Math.abs((c.y ?? 0.77) - g.y) < 0.01;
  return (
    <div className="space-y-3">
      <FontFaces fonts={fonts} />
      <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Caption style</span>
      <div role="radiogroup" aria-label="Caption style" className="grid max-h-[520px] grid-cols-2 gap-2 overflow-y-auto pr-1 sm:grid-cols-3 lg:grid-cols-4">
        {Object.entries(styles).map(([id, s]) => {
          const on = id === v.caption;
          return (
            <button key={id} type="button" role="radio" aria-checked={on} onClick={() => set({ caption: id })}
              className={`flex flex-col overflow-hidden rounded-xl border-2 text-left transition-all ${on ? "border-primary shadow-[0_0_24px_-8px_rgba(200,255,58,0.8)]" : "border-border hover:border-white/30"}`}>
              <span className="flex h-24 items-center justify-center overflow-hidden bg-[#0b0b0f] px-2"><Sample st={s} cap={on ? c : undefined} /></span>
              <span className="flex items-center justify-between bg-[#0a0a0d] px-2.5 py-1.5 text-xs font-medium text-white">{s.label}<span className="text-[10px] uppercase tracking-wider text-white/50">{anims[s.anim] ?? ""}</span></span>
            </button>
          );
        })}
        <button type="button" role="radio" aria-checked={v.caption === "none"} onClick={() => set({ caption: "none" })}
          className={`flex flex-col overflow-hidden rounded-xl border-2 text-left ${v.caption === "none" ? "border-primary" : "border-border"}`}>
          <span className="flex h-20 items-center justify-center bg-[#0b0b0f] text-xs text-white/50 line-through">no captions</span>
          <span className="bg-[#0a0a0d] px-2.5 py-1.5 text-xs font-medium text-white">No captions</span>
        </button>
      </div>
      {v.caption !== "none" && st && (
        <div className="border border-border">
          <button type="button" onClick={() => setOpen(!open)} className="flex w-full items-center justify-between px-3 py-2 text-sm font-medium">
            <span>Customise: font, size, position, colours, animation{edited && <span className="ml-2 text-xs text-primary">edited</span>}</span>
            {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
          {open && (
            <div className="space-y-4 border-t border-border p-3">
              <div className="flex items-center justify-center rounded-lg bg-[#0b0b0f] py-6"><Sample st={st} cap={c} big /></div>
              <div className="grid gap-4 sm:grid-cols-2">
                <Label text="Font">
                  <div className="flex gap-2">
                    <select className={field} value={c.font ?? ""} onChange={(e) => setC({ font: e.target.value || undefined })}>
                      <option value="">{st.font} (the style&apos;s own)</option>
                      {fonts.map((f) => <option key={f.name + f.file} value={f.name} style={{ fontFamily: `"${f.name}"` }}>{f.name}{f.mine ? " (yours)" : ""}</option>)}
                    </select>
                    <button type="button" className={btn} title="Upload a .ttf or .otf font" onClick={() => fileRef.current?.click()} disabled={addFont.isPending}><Upload className="h-4 w-4" /></button>
                    <input ref={fileRef} type="file" accept=".ttf,.otf" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) addFont.mutate(f); e.target.value = ""; }} />
                  </div>
                </Label>
                <div className="space-y-1">
                  <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Text</span>
                  <div className="flex flex-wrap gap-2">
                    <button type="button" className={pill(c.bold ?? true)} onClick={() => toggle("bold", true)}>Bold</button>
                    <button type="button" className={pill(c.italic ?? !!st.italic)} onClick={() => toggle("italic", !!st.italic)}>Italic</button>
                    <button type="button" className={pill(c.upper ?? !!st.upper)} onClick={() => toggle("upper", !!st.upper)}>UPPERCASE</button>
                  </div>
                </div>
              </div>
              {mine.length > 0 && (
                <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">Your fonts:{mine.map((f) => <span key={f.file} className="inline-flex items-center gap-1 border border-border px-2 py-0.5">{f.name}<button type="button" aria-label={`Remove ${f.name}`} onClick={() => delFont.mutate(f.file)}><X className="h-3 w-3" /></button></span>)}</div>
              )}
              {addFont.isError && <Note tone="err">{(addFont.error as Error).message}</Note>}
              <div className="grid gap-4 sm:grid-cols-2">
                <Label text={`Size: ${c.size ?? 100}%`} hint="100% is the style's own size. A long line still shrinks to fit the width.">
                  <input type="range" min={50} max={160} step={5} value={c.size ?? 100} onChange={(e) => setC({ size: +e.target.value === 100 ? undefined : +e.target.value })} className="w-full" />
                </Label>
                <Label text={`Words on screen: ${c.words ?? st.words}`}>
                  <input type="range" min={1} max={4} step={1} value={c.words ?? st.words} onChange={(e) => setC({ words: +e.target.value })} className="w-full" />
                </Label>
              </div>
              <div className="grid gap-4 sm:grid-cols-[auto_1fr]">
                <div className="space-y-1">
                  <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Position</span>
                  <div className="grid w-28 grid-cols-3 gap-1">
                    {GRID.map((g) => <button key={g.id} type="button" title={g.label} aria-label={g.label} aria-pressed={gridOn(g)} onClick={() => setC({ x: g.x === 0.5 ? undefined : g.x, y: g.y === 0.77 ? undefined : g.y })}
                      className={`h-8 border ${gridOn(g) ? "border-primary bg-[rgba(200,255,58,0.25)]" : "border-border hover:bg-muted"}`} />)}
                  </div>
                </div>
                <Label text={`Height: ${Math.round((c.y ?? 0.77) * 100)}% down`} hint="YouTube's title and buttons cover the bottom 20% and the right edge: 60–80% down is the safe band.">
                  <input type="range" min={5} max={92} step={1} value={Math.round((c.y ?? 0.77) * 100)} onChange={(e) => setC({ y: +e.target.value / 100 })} className="w-full" />
                </Label>
              </div>
              {ov.capabilities.caption_modes && (
                <div className="space-y-1">
                  <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Caption mode</span>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(ov.capabilities.caption_modes).map(([id, name]) => <button key={id || "def"} type="button" className={pill((c.mode ?? "") === id)} onClick={() => setC({ mode: id || undefined })}>{name}</button>)}
                  </div>
                </div>
              )}
              <div className="space-y-1">
                <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">How the words arrive</span>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(anims).map(([id, name]) => <button key={id} type="button" className={pill((c.anim ?? st.anim) === id)} onClick={() => setC({ anim: id === st.anim ? undefined : id })}>{name}</button>)}
                </div>
              </div>
              <div className="grid gap-4 sm:grid-cols-4">
                <Label text="Words colour"><input type="color" className="h-10 w-full border border-border bg-transparent" value={c.text || st.text} onChange={(e) => setC({ text: e.target.value })} /></Label>
                <Label text="Spoken word colour"><input type="color" className="h-10 w-full border border-border bg-transparent" value={c.hi || (st.hi === "cycle" ? "#FFE000" : st.hi)} onChange={(e) => setC({ hi: e.target.value })} /></Label>
                <Label text={`Outline: ${c.outline ?? st.outline ?? 4}px`}><input type="range" min={0} max={16} value={c.outline ?? st.outline ?? 4} onChange={(e) => setC({ outline: +e.target.value })} className="w-full" /></Label>
                <Label text={`Shadow: ${c.shadow ?? 2}px`}><input type="range" min={0} max={8} value={c.shadow ?? 2} onChange={(e) => setC({ shadow: +e.target.value })} className="w-full" /></Label>
              </div>
              <Switch on={c.glow ?? !!st.glow} onChange={(x) => setC({ glow: x })} label="Glow" hint="A soft glow in the spoken-word colour around the letters." />
              <Label text={`Caption timing: ${(c.offset_ms ?? 0) > 0 ? "+" : ""}${c.offset_ms ?? 0} ms`} hint={(c.offset_ms ?? 0) < 0 ? `Captions appear ${-(c.offset_ms ?? 0)} ms earlier.` : (c.offset_ms ?? 0) > 0 ? `Captions appear ${c.offset_ms} ms later.` : "Captions appear as the word is said."}>
                <input type="range" min={-500} max={500} step={20} value={c.offset_ms ?? 0} onChange={(e) => setC({ offset_ms: +e.target.value || undefined })} className="w-full" />
              </Label>
              {edited && <button type="button" className={btn} onClick={() => set({ cap: {} })}><RotateCcw className="h-4 w-4" />Reset to the style</button>}
            </div>
          )}
        </div>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        <Label text="Caption language" hint={v.cap_lang === "roman" ? "Hindi speech is written the way people type it: \"kuchh nahi\", not Devanagari. English words stay as they are." : v.cap_lang === "english" ? "The speech model translates while it listens. Needs faster-whisper; slower than plain captions." : "Whatever language is spoken."}>
          <select className={field} value={v.cap_lang} onChange={(e) => set({ cap_lang: e.target.value })}>{Object.entries(LANGS).map(([k, n]) => <option key={k} value={k}>{n}</option>)}</select>
        </Label>
        <Label text="Speech model" hint={models[v.whisper_model] ? `${models[v.whisper_model].mb} MB download the first time, needs about ${models[v.whisper_model].ram_gb} GB RAM: ${models[v.whisper_model].note}.` : undefined}>
          <select className={field} value={v.whisper_model} onChange={(e) => set({ whisper_model: e.target.value })}>
            {Object.entries(models).map(([k, m]) => <option key={k} value={k}>{m.label}{k === cap.whisper_pick ? " (recommended for this machine)" : ""}</option>)}
          </select>
        </Label>
      </div>
    </div>
  );
}
