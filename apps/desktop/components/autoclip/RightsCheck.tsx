"use client";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertCircle, AlertTriangle, Ban, ExternalLink, Radio, ShieldCheck } from "lucide-react";
import { autoclip, type RightsCheck as R, type Verdict } from "@/lib/autoclip";
import { Note } from "./ui";

const TAG: Record<Verdict, { label: string; cls: string; Icon: typeof ShieldCheck }> = {
  own: { label: "Yours: safe to clip", cls: "border-signal/85 text-primary", Icon: ShieldCheck },
  "creative-commons": { label: "Creative Commons: reuse allowed, give credit", cls: "border-signal/85 text-primary", Icon: ShieldCheck },
  ask: { label: "The creator owns it: ask first", cls: "border-amber-400/80 text-amber-300", Icon: AlertTriangle },
  unknown: { label: "Can't tell: only your own recordings are safe", cls: "border-amber-400/80 text-amber-300", Icon: AlertCircle },
  blocked: { label: "Not clippable", cls: "border-red-400/80 text-red-300", Icon: Ban },
};
const SITE: Record<string, string> = { youtube: "YouTube", twitch: "Twitch", kick: "Kick", tiktok: "TikTok", instagram: "Instagram", facebook: "Facebook", x: "X", vimeo: "Vimeo", dailymotion: "Dailymotion", rumble: "Rumble", reddit: "Reddit" };
const MINUTES = [10, 20, 30, 60, 120];

export interface PermState { verdict: Verdict | ""; ack: boolean; ok: boolean; live: boolean; minutes: number }

/** Is this link OK to clip, and is it live? Reads the licence, the channel, whether it is private/members-only/paid and whether it is streaming right now.
 *  `onChange` tells the form what to send; the form should only start when `ok` is true. A live link gets "record the next N minutes". */
export function RightsCheck({ url, isFile, onChange }: { url: string; isFile: boolean; onChange: (v: PermState) => void }) {
  const [ack, setAck] = useState(false);
  const [minutes, setMinutes] = useState(20);
  const clean = url.trim();
  const [debounced, setDebounced] = useState("");
  useEffect(() => { const t = setTimeout(() => setDebounced(clean.length > 8 && /^https?:\/\//i.test(clean) ? clean : ""), 700); return () => clearTimeout(t); }, [clean]);
  const q = useQuery<R>({ queryKey: ["autoclip", "rights", debounced], queryFn: () => autoclip.check(debounced), enabled: !!debounced && !isFile, retry: false, staleTime: 600_000 });
  const d = q.data;
  const verdict: Verdict | "" = isFile ? "own" : d?.verdict ?? (q.isError && debounced ? "unknown" : "");
  const live = !isFile && d?.live?.state === "live";
  const safe = (verdict === "own" && !isFile) || verdict === "creative-commons";
  const blocked = verdict === "blocked" || (!!d && d.clippable === false);
  const ok = !blocked && (isFile ? ack : !!verdict && (safe || ack));
  useEffect(() => { onChange({ verdict: isFile ? "ask" : verdict, ack, ok, live, minutes }); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [verdict, ack, ok, isFile, live, minutes]);
  if (isFile) {
    return (
      <div className="space-y-2 border border-border p-3">
        <div className="inline-flex items-center gap-2 text-sm font-medium"><AlertCircle className="h-4 w-4" />Permission</div>
        <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={ack} onChange={(e) => setAck(e.target.checked)} />I made this video, or the owner gave me permission to clip and post it.</label>
      </div>
    );
  }
  if (!debounced) return null;
  if (q.isLoading) return <p className="text-xs text-muted-foreground">Checking this link: who owns it, whether it is public, whether it is live…</p>;
  if (q.isError || !d) {
    return (
      <div className="space-y-2 border border-border p-3">
        <Note tone="warn">Couldn&apos;t check this link ({(q.error as Error | null)?.message ?? "no answer"}). Only continue if it is yours or you have permission.</Note>
        <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={ack} onChange={(e) => setAck(e.target.checked)} />I have permission to clip and post this.</label>
      </div>
    );
  }
  const t = TAG[d.verdict];
  const site = SITE[d.platform] ?? "";
  return (
    <div className={`space-y-2 border p-3 ${d.verdict === "blocked" ? "border-red-400/60" : "border-border"}`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className={`inline-flex items-center gap-1.5 border px-2 py-1 text-xs font-medium ${t.cls}`}><t.Icon className="h-3.5 w-3.5" />{t.label}</span>
        {live && <span className="inline-flex items-center gap-1.5 border border-red-400/80 px-2 py-1 text-xs font-medium text-red-300"><Radio className="h-3.5 w-3.5" />LIVE now</span>}
        {d.live?.state === "past" && <span className="border border-border px-2 py-1 text-xs text-muted-foreground">Finished live stream</span>}
        {d.title && <span className="truncate text-xs text-muted-foreground">{site ? `${site} · ` : ""}{d.title}{d.channel ? ` · ${d.channel}` : ""}</span>}
      </div>
      <p className="text-sm text-muted-foreground">{d.tip}</p>
      {d.notes?.map((n) => <p key={n} className="text-xs text-muted-foreground">• {n}</p>)}
      {d.links.about && <a href={d.links.about} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs underline">Open the creator&apos;s page for clip rules <ExternalLink className="h-3 w-3" /></a>}
      {live && !blocked && (
        <div className="space-y-1 border-t border-border pt-2">
          <div className="text-xs font-medium">Record the next…</div>
          <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Minutes to record">
            {MINUTES.map((m) => <button key={m} type="button" role="radio" aria-checked={minutes === m} onClick={() => setMinutes(m)}
              className={`border px-3 py-1.5 text-xs ${minutes === m ? "border-signal/85 bg-signal/12" : "border-border text-muted-foreground"}`}>{m < 60 ? `${m} min` : `${m / 60} hour${m > 60 ? "s" : ""}`}</button>)}
          </div>
          <p className="text-[11px] text-muted-foreground">Recording takes that long in real time, then the clips are made from it. You can press Stop at any time and keep what was recorded.</p>
        </div>
      )}
      {!safe && !blocked && <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={ack} onChange={(e) => setAck(e.target.checked)} />I have the owner&apos;s permission to clip and post this. Clips will not post to YouTube until this is ticked.</label>}
      <p className="text-[11px] text-muted-foreground">This reads what the site publishes. It is not legal advice, and even Creative Commons needs credit.</p>
    </div>
  );
}
