"use client";
import type { ReactNode } from "react";

export const field = "h-10 w-full border border-border bg-transparent px-3 text-sm outline-none focus:border-primary";
export const btn = "inline-flex h-10 items-center justify-center gap-2 border border-border px-4 text-sm transition-colors hover:bg-muted disabled:opacity-50";
export const btnPrimary = "inline-flex h-10 items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50";

export function Card({ title, hint, children, right }: { title: string; hint?: string; children: ReactNode; right?: ReactNode }) {
  return (
    <section className="overflow-hidden rounded-2xl border border-border bg-card text-card-foreground">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-3">
        <div><h2 className="display text-lg">{title}</h2>{hint && <p className="text-xs text-muted-foreground">{hint}</p>}</div>
        {right}
      </header>
      <div className="space-y-4 p-4">{children}</div>
    </section>
  );
}

export function Label({ children, text, hint }: { children: ReactNode; text: string; hint?: string }) {
  return <label className="block space-y-1"><span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{text}</span>{children}{hint && <span className="block text-xs text-muted-foreground">{hint}</span>}</label>;
}

export function Switch({ on, onChange, label, hint, disabled }: { on: boolean; onChange: (v: boolean) => void; label: string; hint?: string; disabled?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div><div className="text-sm font-medium">{label}</div>{hint && <div className="text-xs text-muted-foreground">{hint}</div>}</div>
      <button type="button" role="switch" aria-checked={on} aria-label={label} disabled={disabled} onClick={() => onChange(!on)}
        className={`relative mt-1 h-6 w-11 shrink-0 border transition-colors disabled:opacity-40 ${on ? "border-primary bg-primary" : "border-border bg-muted"}`}>
        <span className={`absolute top-0.5 h-4 w-4 bg-white transition-all ${on ? "left-6" : "left-0.5"}`} />
      </button>
    </div>
  );
}

export function Note({ tone = "info", children }: { tone?: "info" | "warn" | "err"; children: ReactNode }) {
  const c = tone === "err" ? "border-red-500/60" : tone === "warn" ? "border-amber-400/70" : "border-border";
  return <p className={`border ${c} px-3 py-2 text-sm text-muted-foreground`}>{children}</p>;
}

export const mmss = (s: number) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;
