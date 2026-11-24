/**
 * Square, monospace, upper-case labels — the register the whole interface now uses.
 *
 * The app is square-cornered throughout: panels, cards, chips, inputs and media. The one thing still rounded is the
 * primary action button on each screen, because a single soft shape reads as the thing to press.
 *
 * Within that, two voices:
 *   mono + caps      → what the system is telling you: a model name, a run state, a cost, a category, a format
 *   sentence case    → what a person writes or chooses: titles, descriptions, the text they typed
 *
 * `Tag` is a label, `TagButton` the clickable version for filters, `Stat` a figure with its caps label above.
 * Money, counts and durations use `tabular-nums` so digits line up down a column.
 */
export type TagTone = "plain" | "accent" | "good" | "warn" | "bad" | "muted";

const TONE: Record<TagTone, string> = {
  plain: "border-border text-foreground/85",
  accent: "border-[rgba(200,255,58,0.7)] bg-[rgba(200,255,58,0.12)] text-foreground",
  good: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
  warn: "border-amber-500/40 bg-amber-500/10 text-amber-300",
  bad: "border-red-500/40 bg-red-500/10 text-red-300",
  muted: "border-border/70 text-muted-foreground",
};

export function Tag({ tone = "plain", children, title, className = "" }: {
  tone?: TagTone; children: React.ReactNode; title?: string; className?: string;
}) {
  return (
    <span title={title}
      className={`inline-flex items-center gap-1.5 border px-2 py-[3px] font-mono text-[10px] uppercase tracking-[0.1em] leading-none ${TONE[tone]} ${className}`}>
      {children}
    </span>
  );
}

/** The same register, but clickable — a filter or a mode switch rather than a label. */
export function TagButton({ on, onClick, children, title }: {
  on?: boolean; onClick: () => void; children: React.ReactNode; title?: string;
}) {
  return (
    <button type="button" onClick={onClick} aria-pressed={on} title={title}
      className={`inline-flex items-center gap-1.5 border px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.1em] leading-none transition ${ on ? TONE.accent :"border-border text-muted-foreground hover:border-border hover:text-foreground"}`}>
      {children}
    </button>
  );
}

/**
 * A figure with its label, as a dashboard prints it: small mono caps above, the number below.
 * `mono` is for anything you would compare digit by digit — money, counts, durations.
 */
export function Stat({ label, value, hint, tone = "plain", mono = true, big }: {
  label: string; value: string; hint?: string; tone?: TagTone; mono?: boolean; big?: boolean;
}) {
  const hintTone = tone === "warn" ? "text-amber-400" : tone === "bad" ? "text-red-400"
    : tone === "good" ? "text-emerald-400" : "text-muted-foreground";
  return (
    <div className="border border-border p-4">
      <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">{label}</p>
      <p className={`mt-2 font-semibold ${mono ?"font-mono tabular-nums" :""} ${big ?"text-3xl" :"text-2xl"}`}>{value}</p>
      {hint && <p className={`mt-1 font-mono text-[10px] uppercase tracking-[0.08em] ${hintTone}`}>{hint}</p>}
    </div>
  );
}
