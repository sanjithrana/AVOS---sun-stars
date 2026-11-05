"use client";

import { FadeImg } from "./FadeImg";
import { explainer, type Project, type Shot } from "@/lib/explainer";

/** Bring a shot card into view by scrolling ONLY the page's own scroll area (scrollIntoView would also shift the whole
 *  window, which pushed the app frame up and left a black gap at the bottom). */
const pick = (id: string) => {
  const el = document.getElementById(`shot-card-${id}`);
  const box = el?.closest("[data-scroll-root]") as HTMLElement | null;
  if (!el || !box) return;
  const top = el.getBoundingClientRect().top - box.getBoundingClientRect().top + box.scrollTop - box.clientHeight / 2 + el.clientHeight / 2;
  box.scrollTo({ top: Math.max(0, top), behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
};

function Thumb({ p, s, className = "" }: { p: Project; s: Shot; className?: string }) {
  return s.frame ? <FadeImg src={explainer.file(p.id, s.frame, String(s.version))} alt={`${s.id}`} className={`h-full w-full object-cover ${className}`} />
    : <div className="flex h-full w-full items-center justify-center bg-muted text-[10px] text-muted-foreground">{s.id}</div>;
}

/** Scenes: the shots grouped the way the director planned them. */
export function Scenes({ p, shots }: { p: Project; shots: Shot[] }) {
  const groups = shots.reduce<Record<number, Shot[]>>((m, s) => { (m[s.scene ?? 1] ??= []).push(s); return m; }, {});
  return (
    <div className="space-y-3" data-testid="view-scenes">
      {Object.entries(groups).map(([n, list]) => (
        <section key={n} className="rounded-xl border border-border bg-card/50 p-3">
          <h3 className="text-sm font-semibold">Scene {n}{list[0].scene_title ? <span className="font-normal text-muted-foreground"> — {list[0].scene_title}</span> : null}
            <span className="ml-2 text-xs font-normal text-muted-foreground">{list.reduce((a, s) => a + s.seconds, 0).toFixed(1)}s{list[0].mood ? ` · ${list[0].mood}` : ""}</span></h3>
          <div className="mt-2 flex gap-2 overflow-x-auto pb-1">
            {list.map((s) => (
              <button key={s.id} type="button" onClick={() => pick(s.id)} className="w-28 shrink-0 text-left transition hover:-translate-y-0.5">
                <div className="aspect-video overflow-hidden rounded-lg border border-border"><Thumb p={p} s={s} /></div>
                <p className="mt-1 truncate text-[11px] text-muted-foreground">{s.id} · {s.seconds}s</p>
              </button>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

/** Timeline: every shot as wide as it lasts, with the final video above. */
export function Timeline({ p, shots, onPick }: { p: Project; shots: Shot[]; onPick?: (id: string) => void }) {
  const total = shots.reduce((a, s) => a + s.seconds, 0) || 1;
  return (
    <div className="space-y-3" data-testid="view-timeline">
      {p.final && <video src={explainer.file(p.id, p.final, p.updatedAt)} controls playsInline className="max-h-72 rounded-xl bg-black" />}
      <div className="overflow-x-auto rounded-xl border border-border bg-card/50 p-3">
        <div className="flex h-20 min-w-[640px] gap-0.5">
          {shots.map((s) => (
            <button key={s.id} type="button" onClick={() => (onPick ? onPick(s.id) : pick(s.id))} title={`${s.id} · ${s.seconds}s · ${s.narration}`}
              style={{ flexBasis: `${(s.seconds / total) * 100}%` }} className="relative min-w-0 overflow-hidden rounded-md border border-border transition hover:border-amber-500">
              <Thumb p={p} s={s} />
              <span className="absolute bottom-0 left-0 bg-black/70 px-1 text-[10px] text-white">{s.id}</span>
            </button>
          ))}
        </div>
        <div className="mt-1 flex min-w-[640px] justify-between text-[10px] text-muted-foreground"><span>0s</span><span>{(total / 2).toFixed(0)}s</span><span>{total.toFixed(1)}s</span></div>
        <div className="mt-2 flex h-6 min-w-[640px] items-center rounded-md bg-violet-500/20 px-2 text-[11px] text-violet-700 dark:text-violet-300">♪ voice and music</div>
      </div>
    </div>
  );
}
