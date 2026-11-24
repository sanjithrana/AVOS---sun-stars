"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Film, Search } from "lucide-react";
import type { SkillInfo } from "@/lib/skills";
import { Tag, TagButton } from "@/components/ui/Tag";

/**
 * Every skill as a cover card, the way a video library looks.
 *
 * The old single-column list was built when there were five skills. There are seventy-one, so the useful controls are
 * search and category: a grid of covers you can scan beats a list you have to scroll. Covers live at
 * /skills/<id>.jpg; a skill without one gets a lettered tile rather than a broken image.
 */
export function SkillGrid({ items, value, onChange, loading }: {
  items: SkillInfo[]; value: string; onChange: (id: string) => void; loading?: boolean;
}) {
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("");
  const [missing, setMissing] = useState<Record<string, boolean>>({});

  const cats = useMemo(() => {
    const n = new Map<string, number>();
    for (const s of items) n.set(s.group, (n.get(s.group) ?? 0) + 1);
    // AVOS's own groups first, then the film-style categories. Sorting purely by count buries Reels and Food and
    // ASMR behind sixty-six film styles, and those are the skills that render in the container.
    // Own groups, then the three kit groups (story engines, animation styles, 3D styles) in that order, then the film styles.
    const kits = ["Kits · Story engines", "Kits · Animation styles", "Kits · 3D styles"];
    const film = (g: string) => (g.startsWith("Film · ") ? 100 : g.startsWith("Kits · ") ? 1 + kits.indexOf(g) : 0);
    return [...n.entries()].sort((a, b) => film(a[0]) - film(b[0]) || (film(a[0]) < 4 && film(a[0]) > 0 ? 0 : b[1] - a[1]) || a[0].localeCompare(b[0]));
  }, [items]);

  const shown = useMemo(() => {
    const t = q.trim().toLowerCase();
    return items.filter((s) => {
      if (cat && s.group !== cat) return false;
      if (!t) return true;
      return [s.name, s.group, s.made_for, s.about, ...(s.examples ?? [])].join(" ").toLowerCase().includes(t);
    });
  }, [items, q, cat]);

  if (loading) {
    return (
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 2xl:grid-cols-6">
        {Array.from({ length: 12 }, (_, i) => (
          <div key={i} className="overflow-hidden border border-border">
            <div className="aspect-video animate-pulse bg-muted" />
            <div className="space-y-2 p-3"><div className="h-3 w-3/4 animate-pulse bg-muted" /><div className="h-2 w-1/2 animate-pulse bg-muted" /></div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-[220px] flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search skills, looks, what they are good for"
            aria-label="Search skills"
            className="w-full border border-border bg-card py-2.5 pl-10 pr-3 text-sm outline-none placeholder:text-muted-foreground focus:border-[rgba(200,255,58,0.6)]"
          />
        </div>
        <p className="text-xs text-muted-foreground">{shown.length} of {items.length}</p>
        <Link href="/stickman" className="border border-border px-3 py-1.5 text-xs text-muted-foreground hover:border-[rgba(200,255,58,0.5)] hover:text-foreground">
          Stickman looks
        </Link>
      </div>

      <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1">
        <TagButton on={!cat} onClick={() => setCat("")}>All {items.length}</TagButton>
        {cats.map(([g, n]) => (
          <TagButton key={g} on={cat === g} onClick={() => setCat(cat === g ? "" : g)}>{g} {n}</TagButton>))}
      </div>

      {!shown.length ? (
        <p className="border border-border p-6 text-sm text-muted-foreground">
          Nothing matches “{q}”. Try a look (ink, paper, pixel), or what you want it for (explainer, reel, keynote).
        </p>
      ) : (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 2xl:grid-cols-6">
          {shown.map((s) => {
            const on = s.id === value;
            return (
              <button
                key={s.id} type="button" onClick={() => onChange(s.id)} aria-pressed={on} title={s.made_for}
                className={`group overflow-hidden border text-left transition ${ on ?"border-[rgba(200,255,58,0.85)] ring-1 ring-[rgba(200,255,58,0.45)]" :"border-border hover:border-[rgba(200,255,58,0.5)]" }`}
              >
                <div className="relative aspect-video overflow-hidden bg-muted">
                  {missing[s.id] ? (
                    <div className="flex h-full w-full items-center justify-center bg-gradient-to-br from-muted to-card">
                      <span className="text-2xl font-semibold text-muted-foreground">{s.name.slice(0, 1)}</span>
                      <Film className="ml-2 h-5 w-5 text-muted-foreground" />
                    </div>
                  ) : (
                    /* eslint-disable-next-line @next/next/no-img-element */
                    <img
                      src={`/skills/${s.id}.jpg`} alt="" loading="lazy" decoding="async"
                      onError={() => setMissing((m) => ({ ...m, [s.id]: true }))}
                      className="h-full w-full object-cover transition duration-300 group-hover:scale-[1.03]"
                    />
                  )}
                </div>
                <div className="p-3">
                  <p className="line-clamp-1 text-sm font-semibold">{s.name}</p>
                  <p className="line-clamp-2 mt-1 text-xs leading-snug text-muted-foreground">{s.made_for}</p>
                  <div className="mt-2 flex flex-wrap items-center gap-1.5">
                    <Tag tone={on ? "accent" : "muted"}>{s.group.replace("Film · ", "").replace("Kits · ", "")}</Tag>
                    {/* Only a tag that differs between skills earns its place. "Sound" was on all 71. */}
                    {s.slow && <Tag tone="warn" title={s.slow}>{s.slow_label ?? "slow · best quality"}</Tag>}
                    {s.free && <Tag tone="good" title="Drawn in code: no picture or video model, so a run costs nothing">free</Tag>}
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
