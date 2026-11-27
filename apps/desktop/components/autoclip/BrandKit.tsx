"use client";
import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronUp, Save, Trash2, Upload } from "lucide-react";
import { autoclip, type BrandOpts, type SavedLook } from "@/lib/autoclip";
import { Label, Note, Switch, btn, field } from "./ui";

const POS = ["tl", "tc", "tr", "ml", "mc", "mr", "bl", "bc", "br"];
const POS_NAME: Record<string, string> = { tl: "Top left", tc: "Top", tr: "Top right", ml: "Left", mc: "Centre", mr: "Right", bl: "Bottom left", bc: "Bottom", br: "Bottom right" };

/** Watermark (your @handle or logo), a lower-third name tag and a "follow" end card, burned into every clip. */
export function BrandKit({ v, set }: { v: BrandOpts; set: (b: BrandOpts) => void }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [ver, setVer] = useState(String(Date.now()));
  const fileRef = useRef<HTMLInputElement>(null);
  const q = useQuery({ queryKey: ["autoclip", "brands"], queryFn: autoclip.brands });
  const up = useMutation({ mutationFn: (f: File) => autoclip.logoAdd(f), onSuccess: () => { setVer(String(Date.now())); qc.invalidateQueries({ queryKey: ["autoclip", "brands"] }); set({ ...v, wm: { ...(v.wm ?? {}), kind: "logo", pos: v.wm?.pos ?? "tr", size: 18, opacity: 85 } }); } });
  const del = useMutation({ mutationFn: autoclip.logoDel, onSuccess: () => { qc.invalidateQueries({ queryKey: ["autoclip", "brands"] }); if (v.wm?.kind === "logo") set({ ...v, wm: undefined }); } });
  const wm = v.wm;
  const kind = wm?.kind ?? "none";
  const setWm = (p: Partial<NonNullable<BrandOpts["wm"]>>) => set({ ...v, wm: { kind: "text", pos: "br", size: 100, opacity: 75, ...(wm ?? {}), ...p } as NonNullable<BrandOpts["wm"]> });
  const on = !!(wm || v.end?.on || v.lower?.on);
  const pill = (x: boolean) => `border px-3 py-1.5 text-sm ${x ? "border-signal/85 bg-signal/12" : "border-border text-muted-foreground hover:text-foreground"}`;
  return (
    <div className="border border-border">
      <button type="button" onClick={() => setOpen(!open)} className="flex w-full items-center justify-between px-3 py-2 text-sm font-medium">
        <span>Branding: watermark, name tag, end card{on && <span className="ml-2 text-xs text-primary">on</span>}</span>
        {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
      </button>
      {open && (
        <div className="space-y-5 border-t border-border p-3">
          <div className="space-y-2">
            <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Watermark on every clip</span>
            <div className="flex flex-wrap gap-2">
              <button type="button" className={pill(kind === "none")} onClick={() => set({ ...v, wm: undefined })}>None</button>
              <button type="button" className={pill(kind === "text")} onClick={() => setWm({ kind: "text", size: 100 })}>Text</button>
              <button type="button" className={pill(kind === "logo")} onClick={() => (q.data?.has_logo ? setWm({ kind: "logo", size: 18 }) : fileRef.current?.click())}>Logo</button>
            </div>
            <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) up.mutate(f); e.target.value = ""; }} />
            {kind === "text" && <input className={field} placeholder="@yourhandle" maxLength={40} value={wm?.text ?? ""} onChange={(e) => setWm({ text: e.target.value })} />}
            {kind === "logo" && (
              <div className="flex items-center gap-3">
                {q.data?.has_logo && <img src={autoclip.logoUrl(ver)} alt="Your logo" className="h-12 max-w-[140px] border border-border bg-[repeating-conic-gradient(#333_0_25%,#222_0_50%)] bg-[length:12px_12px] object-contain p-1" />}
                <button type="button" className={btn} onClick={() => fileRef.current?.click()} disabled={up.isPending}><Upload className="h-4 w-4" />{q.data?.has_logo ? "Replace" : "Upload"} logo</button>
                {q.data?.has_logo && <button type="button" className={btn} onClick={() => del.mutate()} aria-label="Remove logo"><Trash2 className="h-4 w-4" /></button>}
              </div>
            )}
            {up.isError && <Note tone="err">{(up.error as Error).message}</Note>}
            {wm && (
              <div className="grid gap-4 sm:grid-cols-[auto_1fr_1fr]">
                <div className="grid w-28 grid-cols-3 gap-1">
                  {POS.map((p) => <button key={p} type="button" title={POS_NAME[p]} aria-label={POS_NAME[p]} aria-pressed={(wm.pos ?? "br") === p} onClick={() => setWm({ pos: p })}
                    className={`h-8 border ${(wm.pos ?? "br") === p ? "border-primary bg-signal/25" : "border-border hover:bg-muted"}`} />)}
                </div>
                <Label text={`Size: ${wm.size ?? (kind === "logo" ? 18 : 100)}%`} hint={kind === "logo" ? "Share of the clip's width." : "100% is small and readable."}>
                  <input type="range" min={kind === "logo" ? 6 : 50} max={kind === "logo" ? 45 : 250} value={wm.size ?? (kind === "logo" ? 18 : 100)} onChange={(e) => setWm({ size: +e.target.value })} className="w-full" />
                </Label>
                <Label text={`Opacity: ${wm.opacity ?? 75}%`}><input type="range" min={10} max={100} value={wm.opacity ?? 75} onChange={(e) => setWm({ opacity: +e.target.value })} className="w-full" /></Label>
              </div>
            )}
            {wm && (wm.pos ?? "br").endsWith("r") && <p className="text-xs text-amber-300">YouTube&apos;s like and share buttons sit on the right edge; top left or top right is the safest spot.</p>}
          </div>
          <div className="space-y-2">
            <Switch on={!!v.lower?.on} onChange={(x) => set({ ...v, lower: { name: "", sub: "", at: 0.6, secs: 3, ...(v.lower ?? {}), on: x } })} label="Name tag (lower third)" hint="Slides in near the start: who is talking." />
            {v.lower?.on && (
              <div className="grid gap-3 sm:grid-cols-4">
                <Label text="Name"><input className={field} maxLength={30} value={v.lower.name ?? ""} onChange={(e) => set({ ...v, lower: { ...v.lower!, name: e.target.value } })} /></Label>
                <Label text="Under it"><input className={field} maxLength={40} placeholder="comedian, streamer…" value={v.lower.sub ?? ""} onChange={(e) => set({ ...v, lower: { ...v.lower!, sub: e.target.value } })} /></Label>
                <Label text="Shows at (s)"><input type="number" min={0} step={0.5} className={field} value={v.lower.at ?? 0.6} onChange={(e) => set({ ...v, lower: { ...v.lower!, at: +e.target.value } })} /></Label>
                <Label text="For (s)"><input type="number" min={1} max={10} className={field} value={v.lower.secs ?? 3} onChange={(e) => set({ ...v, lower: { ...v.lower!, secs: +e.target.value } })} /></Label>
              </div>
            )}
          </div>
          <div className="space-y-2">
            <Switch on={!!v.end?.on} onChange={(x) => set({ ...v, end: { text: "Follow for more", sub: "", secs: 2, ...(v.end ?? {}), on: x } })} label="End card" hint="The last seconds darken and show your call to action." />
            {v.end?.on && (
              <div className="grid gap-3 sm:grid-cols-3">
                <Label text="Big text"><input className={field} maxLength={40} placeholder="Follow @yourhandle" value={v.end.text ?? ""} onChange={(e) => set({ ...v, end: { ...v.end!, text: e.target.value } })} /></Label>
                <Label text="Small text"><input className={field} maxLength={50} placeholder="for part 2" value={v.end.sub ?? ""} onChange={(e) => set({ ...v, end: { ...v.end!, sub: e.target.value } })} /></Label>
                <Label text="Seconds"><input type="number" min={1} max={5} step={0.5} className={field} value={v.end.secs ?? 2} onChange={(e) => set({ ...v, end: { ...v.end!, secs: +e.target.value } })} /></Label>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/** Saved looks: caption style + changes, branding, layout, music and grade under one name, applied in one click. */
export function SavedLooks({ current, apply }: { current: Omit<SavedLook, "name">; apply: (l: SavedLook) => void }) {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["autoclip", "brands"], queryFn: autoclip.brands });
  const [name, setName] = useState("");
  const save = useMutation({ mutationFn: () => autoclip.brandSave({ ...current, name }), onSuccess: (r) => { qc.setQueryData(["autoclip", "brands"], { ...(q.data ?? { has_logo: false }), brands: r.brands }); setName(""); } });
  const del = useMutation({ mutationFn: (n: string) => autoclip.brandDel(n), onSuccess: (r) => qc.setQueryData(["autoclip", "brands"], { ...(q.data ?? { has_logo: false }), brands: r.brands }) });
  const looks = q.data?.brands ?? [];
  return (
    <div className="space-y-2 border border-border p-3">
      <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Saved looks</span>
      {looks.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {looks.map((l) => (
            <span key={l.name} className="inline-flex items-center border border-border">
              <button type="button" className="px-3 py-1.5 text-sm hover:bg-muted" onClick={() => apply(l)} title="Use this look">{l.name}</button>
              <button type="button" className="border-l border-border px-2 py-1.5 text-muted-foreground hover:text-foreground" aria-label={`Delete ${l.name}`} onClick={() => del.mutate(l.name)}><Trash2 className="h-3.5 w-3.5" /></button>
            </span>
          ))}
        </div>
      ) : <p className="text-xs text-muted-foreground">Save the caption style, branding, layout, music and grade you set below as one look, then use it for each channel in one click.</p>}
      <div className="flex gap-2">
        <input className={field} placeholder="Name this look, e.g. GTA clips" maxLength={40} value={name} onChange={(e) => setName(e.target.value)} />
        <button type="button" className={btn} disabled={!name.trim() || save.isPending} onClick={() => save.mutate()}><Save className="h-4 w-4" />Save current</button>
      </div>
      {save.isError && <Note tone="err">{(save.error as Error).message}</Note>}
    </div>
  );
}
