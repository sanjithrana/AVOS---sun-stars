"use client";

const SWATCH: Record<string, string> = {
  auto: "from-slate-500 to-slate-700", "3d": "from-sky-400 to-fuchsia-500", cinematic: "from-amber-500 to-red-800", photoreal: "from-emerald-500 to-teal-800",
  doc70: "from-yellow-700 to-orange-900", anime: "from-pink-400 to-indigo-500", chalk: "from-emerald-900 to-slate-800", ink: "from-stone-200 to-stone-600", cgi: "from-cyan-400 to-blue-900",
};

/** Looks whose colours are not in the Tailwind build: the exact paper tones, written as a plain CSS gradient. */
const INLINE: Record<string, string> = {
  paper: "linear-gradient(135deg,#efe2c8 0%,#dcb98a 45%,#8a7355 100%)",
};

/** The look of the whole video, as tiles you can see (the choice is added to every picture prompt). */
export function StylePicker({ styles, value, onChange }: { styles: { id: string; name: string }[]; value: string; onChange: (id: string) => void }) {
  return (
    <div className="grid grid-cols-3 gap-2 sm:grid-cols-5" role="radiogroup" aria-label="Look" data-testid="explainer-style">
      {styles.map((s) => (
        <button key={s.id} type="button" role="radio" aria-checked={value === s.id} onClick={() => onChange(s.id)}
          className={`group overflow-hidden rounded-xl border text-left transition-all duration-200 active:scale-[0.97] ${value === s.id ? "border-amber-500 ring-2 ring-amber-500/40" : "border-border hover:border-amber-500/50"}`}>
          <div style={INLINE[s.id] ? { backgroundImage: INLINE[s.id] } : undefined}
            className={`h-12 transition-transform duration-300 group-hover:scale-110 ${INLINE[s.id] ? "" : `bg-gradient-to-br ${SWATCH[s.id] ?? SWATCH.auto}`}`} />
          <p className="px-2 py-1.5 text-xs font-medium">{s.name}</p>
        </button>
      ))}
    </div>
  );
}
