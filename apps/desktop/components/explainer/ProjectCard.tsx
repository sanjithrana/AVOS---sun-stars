"use client";

import Link from "next/link";
import { AlertCircle, CheckCircle2, Film, Hourglass, Loader2 } from "lucide-react";
import { explainer, type Summary } from "@/lib/explainer";

const STATE: Record<string, { label: string; cls: string; icon: typeof Loader2 }> = {
  working: { label: "Working", cls: "text-amber-600", icon: Loader2 },
  waiting: { label: "Needs your OK", cls: "text-sky-600", icon: Hourglass },
  done: { label: "Ready", cls: "text-emerald-600", icon: CheckCircle2 },
  error: { label: "Stopped with an error", cls: "text-red-600", icon: AlertCircle },
  stopped: { label: "Stopped", cls: "text-muted-foreground", icon: AlertCircle },
};

export function ProjectCard({ p }: { p: Summary }) {
  const st = STATE[p.status] ?? STATE.working;
  const Icon = st.icon;
  return (
    <Link href={`/explainer/${p.id}`} className="group animate-in fade-in overflow-hidden rounded-xl border border-border bg-card/50 transition-all duration-300 hover:-translate-y-0.5 hover:border-amber-500/50 hover:shadow-lg">
      <div className="flex aspect-video items-center justify-center overflow-hidden bg-muted">
        {p.thumb ? /* eslint-disable-next-line @next/next/no-img-element */ <img src={explainer.file(p.id, p.thumb)} alt="" className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105" /> : <Film className="h-8 w-8 text-muted-foreground" />}
      </div>
      <div className="space-y-1 p-4">
        <p className="line-clamp-2 font-semibold">{p.title || p.brief}</p>
        <p className={`flex items-center gap-1.5 text-xs ${st.cls}`}><Icon className={`h-3.5 w-3.5 ${p.status === "working" ? "animate-spin" : ""}`} />{st.label}<span className="text-muted-foreground">· {p.seconds}s · {p.aspect}</span></p>
      </div>
    </Link>
  );
}
