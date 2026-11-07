"use client";

/** The tabs over the output side (Storyboard · Shots · Characters · Timeline): the same names in every studio. */
export function OutputTabs<T extends string>({ tabs, active, onChange }: { tabs: { id: T; label: string; count?: number }[]; active: T; onChange: (id: T) => void }) {
  return (
    <div role="tablist" aria-label="Output" data-testid="output-tabs" className="flex flex-nowrap items-center gap-1 overflow-x-auto border-b border-border">
      {tabs.map((t) => (
        <button key={t.id} type="button" role="tab" aria-selected={active === t.id} data-testid={`out-${t.id}`} onClick={() => onChange(t.id)}
          className={`-mb-px shrink-0 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors ${active === t.id ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"}`}>
          {t.label}{typeof t.count === "number" && t.count > 0 && <span className="ml-1.5 text-[11px] text-muted-foreground">{t.count}</span>}
        </button>
      ))}
    </div>
  );
}
