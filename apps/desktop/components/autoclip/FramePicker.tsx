"use client";
import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { autoclip, type CanvasOpts, type CardOpts, type Overview } from "@/lib/autoclip";
import { Label, Note, field } from "./ui";

/** A tiny phone for each template: page colour, the header block, the clip box. */
const ART: Record<string, { bg: string; ink: string; mark?: string; card?: string; clip: string; chrome?: "phone" | "term" | "pill" | "quote" | "comment" }> = {
  none: { bg: "linear-gradient(#333,#111)", ink: "transparent", clip: "inset-x-0 top-[30%] h-[40%]" },
  x_light: { bg: "#fff", ink: "#0F1419", mark: "#1D9BF0", clip: "inset-x-[5%] top-[40%] h-[22%] rounded-md" },
  x_dark: { bg: "#000", ink: "#E7E9EA", mark: "#1D9BF0", clip: "inset-x-[5%] top-[40%] h-[22%] rounded-md" },
  linkedin: { bg: "#F3F2EF", ink: "#191919", mark: "#0A66C2", clip: "inset-x-[5%] top-[40%] h-[22%] rounded" },
  threads: { bg: "#101010", ink: "#F3F5F7", mark: "#0095F6", clip: "inset-x-[5%] top-[40%] h-[22%] rounded-md" },
  yt_banner: { bg: "#0F0F0F", ink: "#F1F1F1", mark: "#FF0033", clip: "inset-x-[5%] top-[40%] h-[22%] rounded-md" },
  comment: { bg: "linear-gradient(#141821,#07080B)", ink: "#F1F1F1", mark: "#3EA6FF", card: "#1F1F1F", chrome: "comment", clip: "inset-x-[5%] top-[42%] h-[22%] rounded-md" },
  tiktok_hook: { bg: "linear-gradient(135deg,#6b7280,#1f2937)", ink: "#000", card: "#fff", clip: "inset-x-0 top-[38%] h-[26%]" },
  breaking: { bg: "linear-gradient(#8B0000,#140000)", ink: "#fff", card: "#000", mark: "#E10600", clip: "inset-x-[4%] top-[38%] h-[24%] rounded" },
  podcast: { bg: "linear-gradient(#3b2a1a,#111)", ink: "#fff", clip: "inset-x-0 top-0 h-[70%]" },
  podcast_show: { bg: "#121214", ink: "#fff", mark: "#C8FF3A", chrome: "pill", clip: "inset-x-[5%] top-[40%] h-[22%] rounded-md" },
  quote: { bg: "#0B0B0F", ink: "#F5F1E8", mark: "#C8FF3A", chrome: "quote", clip: "inset-x-[5%] top-[46%] h-[22%] rounded" },
  phone: { bg: "#15161C", ink: "#fff", chrome: "phone", clip: "inset-x-[6%] top-[38%] h-[22%] rounded-md" },
  glow: { bg: "linear-gradient(#2A1460,#0D0820)", ink: "#fff", mark: "#B794FF", card: "rgba(255,255,255,.1)", chrome: "quote", clip: "inset-x-[5%] top-[46%] h-[22%] rounded-md" },
  terminal: { bg: "#070B11", ink: "#D7E3F4", mark: "#4FD1C5", card: "#0E1621", chrome: "term", clip: "inset-x-[5%] top-[46%] h-[22%] rounded" },
};

function Mini({ id }: { id: string }) {
  const a = ART[id] ?? ART.none;
  return (
    <span className="relative mx-auto block aspect-[9/16] w-full max-w-[86px] overflow-hidden" style={{ background: a.bg }}>
      {a.chrome === "phone" && <><span className="absolute inset-[3%] border-2 border-zinc-600" /><span className="absolute left-1/2 top-[5%] h-[3%] w-[30%] -translate-x-1/2 rounded-full bg-black" /></>}
      {(a.chrome === "comment" || a.chrome === "term" || (a.card && !a.chrome)) && <span className="absolute inset-x-[6%] top-[14%] h-[20%] rounded" style={{ background: a.card }} />}
      {a.chrome === "term" && <span className="absolute left-[10%] top-[16%] flex gap-0.5">{["#FF5F57", "#FEBC2E", "#28C840"].map((c) => <i key={c} className="block h-1 w-1 rounded-full" style={{ background: c }} />)}</span>}
      {a.chrome === "pill" && <span className="absolute left-[7%] top-[16%] flex gap-0.5"><i className="block h-1.5 w-4 rounded-sm bg-white" /><i className="block h-1.5 w-3 rounded-sm" style={{ background: a.mark }} /></span>}
      {a.chrome === "quote" && <span className="absolute left-[7%] top-[12%] text-[14px] leading-none" style={{ color: a.mark }}>“</span>}
      {a.mark && !a.chrome && <span className="absolute left-[7%] top-[17%] h-2.5 w-2.5 rounded-full" style={{ background: a.mark }} />}
      {id !== "none" && id !== "podcast" && <><span className="absolute left-[7%] right-[10%] top-[26%] h-[2.5%]" style={{ background: a.ink, opacity: 0.85 }} /><span className="absolute left-[7%] right-[35%] top-[31%] h-[2.5%]" style={{ background: a.ink, opacity: 0.85 }} /></>}
      <span className={`absolute bg-[#9d9ea8] ${a.clip}`} />
    </span>
  );
}

export interface FrameValue { template: string; canvas: CanvasOpts; card: CardOpts }

export function FramePicker({ ov, v, set }: { ov: Overview; v: FrameValue; set: (p: Partial<FrameValue>) => void }) {
  const info = ov.capabilities.template_info ?? Object.fromEntries(Object.entries(ov.capabilities.templates ?? {}).map(([k, l]) => [k, { label: l, cat: "all", desc: "", card: false }]));
  const cats = ov.capabilities.template_cats ?? { all: "All" };
  const bgs = ov.capabilities.backgrounds ?? {};
  const fonts = ov.capabilities.card_fonts ?? [];
  const qc = useQueryClient();
  const [cat, setCat] = useState("all");
  const [q, setQ] = useState("");
  const brands = useQuery({ queryKey: ["autoclip", "brands"], queryFn: autoclip.brands });
  const bgIn = useRef<HTMLInputElement>(null);
  const avIn = useRef<HTMLInputElement>(null);
  const [avStamp, setAvStamp] = useState(0);
  const up = useMutation({ mutationFn: (f: File) => autoclip.canvasAdd(f), onSuccess: () => { qc.invalidateQueries({ queryKey: ["autoclip", "brands"] }); setC({ bg: "image" }); } });
  const avUp = useMutation({ mutationFn: (f: File) => autoclip.avatarAdd(f), onSuccess: () => { qc.invalidateQueries({ queryKey: ["autoclip", "brands"] }); setAvStamp(Date.now()); } });
  if (!Object.keys(info).length) return null;
  const c = v.canvas;
  const k = v.card;
  const setC = (p: Partial<CanvasOpts>) => set({ canvas: Object.fromEntries(Object.entries({ ...c, ...p }).filter(([, x]) => x !== undefined && x !== "")) as CanvasOpts });
  const setK = (p: Partial<CardOpts>) => set({ card: Object.fromEntries(Object.entries({ ...k, ...p }).filter(([, x]) => x !== undefined && x !== "")) as CardOpts });
  const shown = Object.entries(info).filter(([id, t]) => (cat === "all" || t.cat === cat || id === "none") && (!q || `${t.label} ${t.desc}`.toLowerCase().includes(q.toLowerCase())));
  const cur = info[v.template];
  const pill = (on: boolean) => `px-3 py-1.5 text-xs transition border ${on ? "border-signal/85 bg-signal/15 text-foreground" : "border-border text-muted-foreground hover:text-foreground"}`;
  return (
    <div className="space-y-4 border border-border p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Video template <span className="normal-case text-signal/90">{Object.keys(info).length - 1} styles</span></span>
        <input className={`${field} max-w-[220px]`} placeholder="Search templates" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      <div className="flex flex-wrap gap-2">{Object.entries(cats).map(([id, name]) => <button key={id} type="button" className={pill(cat === id)} onClick={() => setCat(id)}>{name}</button>)}</div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-5" role="radiogroup" aria-label="Template">
        {shown.map(([id, t]) => {
          const on = v.template === id;
          return (
            <button key={id} type="button" role="radio" aria-checked={on} title={t.desc} onClick={() => set({ template: id, canvas: {} })}
              className={`relative space-y-1 border p-1.5 text-left text-xs transition ${on ? "border-signal/85 bg-signal/8" : "border-border text-muted-foreground hover:text-foreground"}`}>
              {on && <span className="absolute right-1 top-1 z-10 bg-signal px-1 text-[9px] font-semibold text-black">ACTIVE</span>}
              <Mini id={id} />
              <span className="block truncate font-medium">{t.label}</span>
              {t.desc && <span className="line-clamp-2 block text-[10px] text-muted-foreground">{t.desc}</span>}
            </button>
          );
        })}
      </div>

      {cur?.card && (
        <div className="space-y-3 border-t border-border pt-3">
          <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{cur.label}: header and frame</span>
          <div className="flex items-center gap-3">
            <span className="flex h-14 w-14 shrink-0 items-center justify-center overflow-hidden rounded-full border border-border bg-muted text-muted-foreground">
              {brands.data?.has_avatar ? <img src={`/studio-api/autoclip/brand/avatar?t=${avStamp}`} alt="Your avatar" className="h-full w-full object-cover" /> : "?"}
            </span>
            <button type="button" className="flex-1 border border-border px-3 py-2 text-xs hover:bg-muted" onClick={() => avIn.current?.click()}>{avUp.isPending ? "Uploading…" : brands.data?.has_avatar ? "Change avatar" : "Upload avatar"}</button>
            <input ref={avIn} type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) avUp.mutate(f); e.target.value = ""; }} />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <Label text="Channel name"><input className={field} value={k.name ?? ""} placeholder="Your channel" onChange={(e) => setK({ name: e.target.value })} /></Label>
            <Label text="Channel handle"><input className={field} value={k.handle ?? ""} placeholder="@yourhandle" onChange={(e) => setK({ handle: e.target.value })} /></Label>
            {v.template === "linkedin" && <Label text="Headline (under your name)"><input className={field} value={k.headline ?? ""} placeholder="Founder at …" onChange={(e) => setK({ headline: e.target.value })} /></Label>}
            {v.template === "comment" && <Label text="Likes on the comment"><input className={field} value={k.likes ?? ""} placeholder="48.2K" onChange={(e) => setK({ likes: e.target.value })} /></Label>}
            {v.template === "podcast_show" && <>
              <Label text="Episode number"><input className={field} value={k.episode ?? ""} placeholder="42" onChange={(e) => setK({ episode: e.target.value })} /></Label>
              <Label text="Speakers"><input className={field} value={k.speakers ?? ""} placeholder="Alex Rivera & Jordan Lee" onChange={(e) => setK({ speakers: e.target.value })} /></Label>
            </>}
          </div>
          <label className="flex items-center justify-between gap-3 text-sm">
            <span>Verified badge</span>
            <input type="checkbox" className="h-5 w-5 accent-signal" checked={k.verified !== false} onChange={(e) => setK({ verified: e.target.checked })} />
          </label>
          <Label text="Post hook / statement">
            <textarea className={`${field} min-h-[72px]`} value={k.hook ?? ""} placeholder="Leave empty: each clip uses its own title as the hook (recommended for a batch)" onChange={(e) => setK({ hook: e.target.value })} />
          </Label>
          <div className="grid gap-3 sm:grid-cols-2">
            <Label text="Font">
              <select className={field} value={k.font ?? ""} onChange={(e) => setK({ font: e.target.value || undefined })}>
                <option value="">Template&apos;s own</option>
                {fonts.map((f) => <option key={f} value={f}>{f}</option>)}
              </select>
            </Label>
            <Label text={`Text size: ${k.size ?? 100}%`}><input type="range" min={60} max={160} step={5} value={k.size ?? 100} onChange={(e) => setK({ size: +e.target.value })} className="w-full" /></Label>
          </div>
        </div>
      )}

      <div className="space-y-3 border-t border-border pt-3">
        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Background canvas</span>
        <div className="grid gap-4 sm:grid-cols-3">
          <Label text="Background">
            <select className={field} value={c.bg ?? ""} onChange={(e) => setC({ bg: e.target.value || undefined })}>
              <option value="">Template&apos;s own</option>
              {Object.entries(bgs).map(([id, name]) => <option key={id} value={id}>{name}</option>)}
            </select>
          </Label>
          {(c.bg === "color" || c.bg === "gradient") && <Label text={c.bg === "gradient" ? "Top colour" : "Colour"}><input type="color" className="h-10 w-full border border-border bg-transparent" value={c.color ?? "#111111"} onChange={(e) => setC({ color: e.target.value })} /></Label>}
          {c.bg === "gradient" && <Label text="Bottom colour"><input type="color" className="h-10 w-full border border-border bg-transparent" value={c.color2 ?? "#000000"} onChange={(e) => setC({ color2: e.target.value })} /></Label>}
          {c.bg === "image" && (
            <div className="space-y-1">
              <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Your picture</span>
              <div className="flex items-center gap-2 text-xs">
                <button type="button" className="border border-border px-3 py-2 hover:bg-muted" onClick={() => bgIn.current?.click()}>{brands.data?.has_canvas ? "Replace" : "Upload"}</button>
                {brands.data?.has_canvas && <span className="text-muted-foreground">uploaded</span>}
                <input ref={bgIn} type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) up.mutate(f); e.target.value = ""; }} />
              </div>
            </div>
          )}
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          <Label text={`Padding: ${c.pad ?? "template"}${c.pad != null ? "%" : ""}`}><input type="range" min={0} max={15} value={c.pad ?? 5} onChange={(e) => setC({ pad: +e.target.value })} className="w-full" /></Label>
          <Label text={`Rounded corners: ${c.radius ?? "template"}${c.radius != null ? "px" : ""}`}><input type="range" min={0} max={80} step={2} value={c.radius ?? 24} onChange={(e) => setC({ radius: +e.target.value })} className="w-full" /></Label>
          <Label text={`Dim background: ${c.dim ?? 0}%`}><input type="range" min={0} max={80} step={5} value={c.dim ?? 0} onChange={(e) => setC({ dim: +e.target.value })} className="w-full" /></Label>
        </div>
      </div>
      {(up.isError || avUp.isError) && <Note tone="err">{((up.error || avUp.error) as Error).message}</Note>}
    </div>
  );
}
