"use client";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Loader2 } from "lucide-react";
import { autoclip } from "@/lib/autoclip";
import { Note, btnPrimary } from "./ui";

/** The one video you just started: working, then "Your video is ready". Everything you have made lives in the Library. */
export function Started({ id }: { id: string }) {
  const q = useQuery({ queryKey: ["autoclip", "job", id], queryFn: () => autoclip.job(id), refetchInterval: (s) => (s.state.data?.busy ? 2000 : false), retry: false });
  const j = q.data;
  if (!j) return null;
  if (j.status === "done") {
    return (
      <div className="flex flex-wrap items-center justify-between gap-3 border border-primary bg-[rgba(200,255,58,0.12)] px-4 py-3">
        <span className="inline-flex items-center gap-2 text-sm font-medium"><CheckCircle2 className="h-4 w-4 text-primary" />Your video was ready: {j.clips.length} clip{j.clips.length === 1 ? "" : "s"} from “{j.title}”.</span>
        <span className="flex gap-2"><Link href={`/autoclip?open=${id}`} className={btnPrimary}>Open your clips</Link><Link href="/library?studio=autoclip" className="inline-flex h-10 items-center border border-border px-4 text-sm hover:bg-muted">Library</Link></span>
      </div>
    );
  }
  if (j.status === "error" || j.status === "stopped") return <Note tone="err">{j.error || "That run stopped."} You can retry it from the Library.</Note>;
  const last = j.log[j.log.length - 1];
  return (
    <div className="flex items-center gap-3 border border-border px-4 py-3 text-sm">
      <Loader2 className="h-4 w-4 animate-spin text-primary" />
      <span>Making your clips: {j.stages.find((s) => s.id === j.stage)?.label ?? "working"}. You can leave this page; the result will appear in your Library.{last ? ` (${last.text})` : ""}</span>
    </div>
  );
}
