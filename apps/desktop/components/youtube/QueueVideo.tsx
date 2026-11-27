"use client";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ListPlus } from "lucide-react";
import { autoclip } from "@/lib/autoclip";

/** "Add to a channel queue" for any finished video made in the studio (Skills, Stickman, Explainer, Films). The file is copied into the post queue as your own upload. */
export function QueueVideo({ url, title, className = "", full = false }: { url: string; title: string; className?: string; full?: boolean }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [sel, setSel] = useState<Set<string>>(new Set());
  const yt = useQuery({ queryKey: ["yt"], queryFn: () => autoclip.yt(), retry: false, enabled: open });
  const go = useMutation({
    mutationFn: async () => {
      const r = await fetch(url);
      if (!r.ok) throw new Error("Could not read the video file.");
      const blob = await r.blob();
      const fd = new FormData();
      fd.append("file", new File([blob], `${(title || "video").replace(/[^\w .-]+/g, "").trim() || "video"}.mp4`, { type: "video/mp4" }));
      fd.append("ack", "true");                                   // made in this studio
      const up = await autoclip.ytUpload(fd);
      return autoclip.ytAdd({ items: [{ upload: up.id }], channels: [...sel], mode: "auto" });
    },
    onSuccess: (t) => { qc.setQueryData(["yt"], t); setSel(new Set()); },
  });
  const chans = yt.data?.channels ?? [];
  return (
    <span className={`${full ? "flex w-full" : "inline-flex"} flex-col gap-2 align-top ${className}`}>
      <button type="button" onClick={() => setOpen(!open)} className={`inline-flex h-9 items-center justify-center gap-2 whitespace-nowrap border border-border px-3 text-sm hover:bg-muted ${full ? "w-full" : ""}`}><ListPlus className="h-4 w-4 shrink-0" />{full ? "Add to queue" : "Add to a channel queue"}</button>
      {open && (
        <span className={`flex flex-col gap-2 border border-border p-3 text-sm ${full ? "w-full" : "max-w-md"}`}>
          {yt.isLoading ? <span className="text-xs text-muted-foreground">Loading…</span> : chans.length === 0 ? (
            <span className="text-xs text-muted-foreground">Connect a channel first (Connections in the sidebar).</span>
          ) : (
            <>
              <span className="flex flex-wrap gap-2">
                {chans.map((c) => (
                  <button key={c.id} type="button" aria-pressed={sel.has(c.id)} onClick={() => { const x = new Set(sel); x.has(c.id) ? x.delete(c.id) : x.add(c.id); setSel(x); }}
                    className={`border px-3 py-1.5 ${sel.has(c.id) ? "border-signal/85 bg-signal/12" : "border-border text-muted-foreground"}`}>
                    {c.title}<span className="ml-1.5 text-[10px] uppercase opacity-70">{c.platform || "youtube"}</span>
                  </button>
                ))}
              </span>
              <button type="button" disabled={sel.size === 0 || go.isPending} onClick={() => go.mutate()} className="h-9 border border-signal/85 bg-signal/12 px-3 disabled:opacity-50">
                {go.isPending ? "Adding…" : `Add to ${sel.size || ""} queue${sel.size === 1 ? "" : "s"}`}
              </button>
            </>
          )}
          {go.isSuccess && <span className="text-xs text-primary">Added. Set the time on the YouTube tab, under that channel.</span>}
          {go.isError && <span className="text-xs text-red-400">{(go.error as Error).message}</span>}
        </span>
      )}
    </span>
  );
}
