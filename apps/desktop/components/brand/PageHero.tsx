"use client";
import type { ComponentType, ReactNode } from "react";

export interface HeroStep { icon: ComponentType<{ className?: string }>; t: string; d: string }

/** The top of a studio page: a dash label, a heavy headline with one lit phrase and a bar, a line about it, and the steps as a numbered row. */
export function PageHero({ eyebrow, title, blurb, steps, right, compact }: { eyebrow: string; title: ReactNode; blurb?: string; steps?: HeroStep[]; right?: ReactNode; compact?: boolean }) {
  return (
    <section className={`hero-glow relative overflow-hidden rounded-3xl border border-border ${compact ? "p-5 md:p-7" : "p-6 md:p-10"}`}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="eyebrow">{eyebrow}</p>
          <h1 className={`display underbar mt-4 max-w-4xl ${compact ? "text-3xl md:text-4xl" : "text-4xl md:text-6xl"}`}>{title}</h1>
          {blurb && <p className="mt-5 max-w-xl text-sm text-muted-foreground md:text-base">{blurb}</p>}
        </div>
        {right}
      </div>
      {steps && steps.length > 0 && (
        <ol className={`relative mt-9 grid gap-3 ${steps.length >= 3 ? "md:grid-cols-3" : "md:grid-cols-2"}`}>
          {steps.map((s, i) => (
            <li key={s.t} className="flex gap-3 rounded-2xl border border-border bg-[rgba(255,255,255,0.035)] p-4 transition-colors hover:border-[rgba(200,255,58,0.4)]">
              <span className="step-no">{String(i + 1).padStart(2, "0")}</span>
              <span className="min-w-0"><span className="flex items-center gap-2 text-sm font-semibold"><s.icon className="h-4 w-4 text-[var(--signal)]" />{s.t}</span><span className="mt-1 block text-xs text-muted-foreground">{s.d}</span></span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

/** The lit phrase of a headline (gradient text inside .display). */
export const Lit = ({ children }: { children: ReactNode }) => <b>{children}</b>;
