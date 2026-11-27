"use client";
import type { ComponentType, ReactNode } from "react";

export interface HeroStep { icon: ComponentType<{ className?: string }>; t: string; d: string }

/** The top of a studio page, cut into the grid: the headline and its line on the left, anything extra on the right,
 *  and the steps as one ruled row below. The page name is already in the top bar, so the eyebrow is only read by screen readers. */
export function PageHero({ eyebrow, title, blurb, steps, right, compact }: { eyebrow: string; title: ReactNode; blurb?: string; steps?: HeroStep[]; right?: ReactNode; compact?: boolean }) {
  return (
    <section className="border border-border border-t-2 border-t-[var(--room)] bg-card" aria-label={eyebrow}>
      <div className={`flex flex-wrap items-end justify-between gap-6 ${compact ? "px-5 py-6 md:px-6" : "px-5 py-8 md:px-8 md:py-10"}`}>
        <div className="min-w-0">
          <h1 className={`display max-w-3xl ${compact ? "text-[1.75rem] md:text-[2rem]" : "text-[2rem] md:text-[2.75rem]"}`}>{title}</h1>
          {blurb && <p className="mt-3 max-w-[60ch] text-[14px] leading-relaxed text-muted-foreground">{blurb}</p>}
        </div>
        {right}
      </div>
      {steps && steps.length > 0 && (
        <ol className={`grid gap-px border-t border-border bg-border ${steps.length >= 3 ? "md:grid-cols-3" : "md:grid-cols-2"}`}>
          {steps.map((s, i) => (
            <li key={s.t} className="flex gap-3 bg-card px-5 py-4 md:px-6">
              <span className="font-mono text-[12px] text-[var(--room)] tabular">{String(i + 1).padStart(2, "0")}</span>
              <span className="min-w-0"><span className="flex items-center gap-2 text-[13.5px] font-medium"><s.icon className="h-4 w-4 text-[var(--room)]" />{s.t}</span><span className="mt-0.5 block text-[12.5px] text-muted-foreground">{s.d}</span></span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

/** The lit phrase of a headline (gradient text inside .display). */
export const Lit = ({ children }: { children: ReactNode }) => <b>{children}</b>;
