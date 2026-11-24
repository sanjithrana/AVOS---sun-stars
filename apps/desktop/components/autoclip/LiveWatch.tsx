"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Radio, Square, Trash2 } from "lucide-react";
import { autoclip, type LiveStreamer } from "@/lib/autoclip";
import { Card, Note, btn, btnPrimary, field } from "./ui";

const blank = (): LiveStreamer => ({ platform: "twitch", handle: "", min_messages: 10, lang: "en", permission: false, on: true });

/** Watch live streamers: records them, counts chat, and turns the moments chat goes wild into clips that wait in the Library. Never posts by itself. */
export function LiveWatch() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["autoclip", "live"], queryFn: autoclip.live, refetchInterval: 5000, retry: false });
  const [rows, setRows] = useState<LiveStreamer[]>([]);
  const [dirty, setDirty] = useState(false);
  useEffect(() => { if (q.data && !dirty) setRows(q.data.streamers.length ? q.data.streamers : [blank()]); }, [q.data, dirty]);
  const set = (t: Parameters<typeof qc.setQueryData>[1]) => qc.setQueryData(["autoclip", "live"], t);
  const save = useMutation({ mutationFn: () => autoclip.liveSave(rows.filter((r) => r.handle.trim())), onSuccess: (t) => { set(t); setDirty(false); } });
  const start = useMutation({ mutationFn: async () => { if (dirty) await autoclip.liveSave(rows.filter((r) => r.handle.trim())); setDirty(false); return autoclip.liveStart(); }, onSuccess: set });
  const stop = useMutation({ mutationFn: autoclip.liveStop, onSuccess: set });
  const edit = (i: number, p: Partial<LiveStreamer>) => { setRows((r) => r.map((x, k) => (k === i ? { ...x, ...p } : x))); setDirty(true); };
  const d = q.data;
  const err = (save.error || start.error || stop.error) as Error | null;
  return (
    <div className="space-y-6">
      <Card title="Watch live streamers" hint="Records each live stream, reads chat, and cuts the moment chat explodes. Clips wait in the Library for your review; nothing is posted by itself."
        right={d && (d.running
          ? <button type="button" className={btn} disabled={stop.isPending} onClick={() => stop.mutate()}><Square className="h-4 w-4" />Stop watching</button>
          : <button type="button" className={btnPrimary} disabled={start.isPending} onClick={() => start.mutate()}><Radio className="h-4 w-4" />{start.isPending ? "Starting…" : "Start watching"}</button>)}>
        {q.isError && <Note tone="err">{(q.error as Error).message}</Note>}
        {d && !d.tools.streamlink && <Note tone="warn">streamlink is not installed in the Auto Clip container yet, so recording cannot start. Run this once, then press Start: <code>docker exec avos-animation-studio pip install streamlink</code></Note>}
        {err && <Note tone="err">{err.message}</Note>}
        <div className="space-y-3">
          {rows.map((r, i) => {
            const live = d?.streamers.find((x) => x.platform === r.platform && x.handle.toLowerCase() === r.handle.toLowerCase());
            return (
              <div key={i} className="space-y-2 border border-border p-3">
                <div className="grid gap-2 md:grid-cols-[9rem_1fr_8rem_8rem_auto]">
                  <select className={field} value={r.platform} onChange={(e) => edit(i, { platform: e.target.value as LiveStreamer["platform"] })} aria-label="Platform"><option value="twitch">Twitch</option><option value="youtube">YouTube</option><option value="kick">Kick</option></select>
                  <input className={field} value={r.handle} placeholder={r.platform === "youtube" ? "@channel" : "channel name"} onChange={(e) => edit(i, { handle: e.target.value })} aria-label="Streamer" />
                  <input className={field} type="number" min={3} max={200} value={r.min_messages} onChange={(e) => edit(i, { min_messages: Number(e.target.value) || 10 })} aria-label="Minimum messages per 5 seconds" title="Minimum chat messages in 5 seconds to count as a spike. Big chats 20 to 25, small ones 6." />
                  <select className={field} value={r.lang} onChange={(e) => edit(i, { lang: e.target.value as "en" | "hi" })} aria-label="Language"><option value="en">English</option><option value="hi">Hindi</option></select>
                  <button type="button" className={btn} onClick={() => { setRows((x) => x.filter((_, k) => k !== i)); setDirty(true); }} aria-label="Remove"><Trash2 className="h-4 w-4" /></button>
                </div>
                <label className="flex items-start gap-2 text-xs text-muted-foreground"><input type="checkbox" className="mt-0.5" checked={r.permission} onChange={(e) => edit(i, { permission: e.target.checked })} />I have this streamer's permission to clip and repost their streams. Without it the clips are still made, but cannot be posted.</label>
                {live && !dirty && <p className="text-xs text-muted-foreground">{live.state === "live" ? `Live since ${live.since ?? ""} · chat ${live.chat ? `${live.rate ?? 0} msgs / 5 s` : "not connected (using loudness)"} · ${live.moments ?? 0} moments` : live.state === "error" ? `Problem: ${live.error}` : d?.running ? "Offline, checking every minute" : "Not watching"}{live.note ? ` · ${live.note}` : ""}</p>}
              </div>
            );
          })}
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" className={btn} onClick={() => { setRows((x) => [...x, blank()]); setDirty(true); }}><Plus className="h-4 w-4" />Add a streamer</button>
          <button type="button" className={btn} disabled={!dirty || save.isPending} onClick={() => save.mutate()}>{save.isPending ? "Saving…" : "Save the list"}</button>
        </div>
        <p className="text-xs text-muted-foreground">Twitch chat is read live. YouTube and Kick streams are recorded too, and moments there are found from loud jumps in the audio. Start with 3 streamers; each live stream uses about 4 to 5 Mbps and 30 GB of disk per day of recording.</p>
      </Card>
      <Card title="Moments caught" hint="Newest first. Each one became a clip job: open it to review, edit and add it to a channel queue.">
        {!d?.moments.length ? <p className="text-sm text-muted-foreground">Nothing yet. Moments appear here while someone you watch is live and chat spikes.</p> : (
          <ul className="divide-y divide-border">
            {d.moments.map((m) => (
              <li key={m.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
                <div><span className="font-medium">{m.streamer.replace(/^[a-z]+-/, "")}</span> <span className="text-muted-foreground">· {m.at.slice(11, 16)} · {m.kind === "chat" ? `${m.count} msgs from ${m.unique} people` : `loud jump (z ${m.audio_z})`}{m.top.length ? ` · ${m.top.join(", ")}` : ""}</span></div>
                <div className="flex items-center gap-3"><span className="font-mono text-xs">{m.score}/10</span>{m.job ? <Link className="underline" href={`/autoclip?open=${m.job}`}>Review clip</Link> : <span className="text-xs text-red-400">{m.error || "not made"}</span>}</div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
