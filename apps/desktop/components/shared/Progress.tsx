"use client";
import { useEffect, useState } from "react";

/** A live bar for long work: a real percentage when the service knows one, an animated stripe when it does not,
 *  one line saying what is happening, and a clock so a long step never looks frozen. */
export function Progress({ pct, text, since }: { pct?: number | null; text?: string; since?: string }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t); }, []);
  const start = since ? Date.parse(since) : NaN;
  const secs = Number.isFinite(start) ? Math.max(0, Math.round((now - start) / 1000)) : null;
  const clock = secs === null ? "" : `${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, "0")}`;
  const known = typeof pct === "number";
  return (
    <div className="space-y-1.5" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={known ? Math.round(pct as number) : undefined} aria-label={text || "Working"}>
      <div className="relative h-2 overflow-hidden bg-muted">
        {known
          ? <div className="h-full bg-primary transition-[width] duration-700" style={{ width: `${Math.max(2, pct as number)}%` }} />
          : <div className="progress-stripe absolute inset-y-0 w-1/3 bg-primary" />}
      </div>
      <div className="flex items-center justify-between gap-3 text-xs text-muted-foreground">
        <span className="min-w-0 truncate">{known && <b className="mr-2 text-foreground">{Math.round(pct as number)}%</b>}{text || "Working…"}</span>
        {clock && <span className="shrink-0 tabular-nums">{clock} elapsed</span>}
      </div>
    </div>
  );
}
