"use client";
import { useQuery } from "@tanstack/react-query";
import { autoclip } from "@/lib/autoclip";

/** A thin bar along the bottom: is it working, this machine, the speech model, face tracking, the encoder. */
export function StatusBar() {
  const q = useQuery({ queryKey: ["autoclip", "system"], queryFn: autoclip.system, refetchInterval: 15_000, retry: false });
  const s = q.data;
  const dot = (ok: boolean) => <span className={`inline-block h-2 w-2 rounded-full ${ok ? "bg-[var(--signal,#c8ff3a)]" : "bg-amber-400"}`} />;
  if (q.isError) return <div className="sticky bottom-0 z-10 border-t border-border bg-background/95 px-4 py-1.5 text-xs text-amber-300 backdrop-blur">The studio service is not answering.</div>;
  if (!s) return null;
  const items: React.ReactNode[] = [
    <span key="st" className="inline-flex items-center gap-1.5">{dot(true)}{s.busy.length ? `Working on ${s.busy.length} video${s.busy.length > 1 ? "s" : ""}` : "Ready"}</span>,
    <span key="hw">{s.cpus} cores · {s.ram_gb} GB RAM · {s.disk_free_gb} GB free</span>,
    <span key="wh" className={s.whisper ? "" : "text-amber-300"}>{s.whisper ? `Speech model: ${s.whisper_model}${s.whisper_model !== s.whisper_pick ? ` (best here: ${s.whisper_pick})` : ""}` : "No speech model: install faster-whisper"}</span>,
    <span key="fc" className={s.faces ? "" : "text-amber-300"}>Face tracking {s.faces ? "ready" : "off"}</span>,
    <span key="en">Encoder: {s.encoder}</span>,
  ];
  return (
    <div className="sticky bottom-0 z-10 flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-border bg-background/95 px-4 py-1.5 text-xs text-muted-foreground backdrop-blur">
      {items.map((x, i) => <span key={i} className="inline-flex items-center gap-4">{i > 0 && <span className="h-3 w-px bg-border" />}{x}</span>)}
    </div>
  );
}
