import Link from "next/link";
import { Mark } from "@/components/layout/Mark";

// What goes in (left) and what comes out (right). These describe the process, so they are not links.
const LEFT = ["Topic research", "Script and scenes", "Camera and lighting"];
const RIGHT = ["Storyboard", "Pictures and clips", "Voice and music"];
const W = 1000, H = 380, YS = [50, 190, 330], C = 190;
const pct = (n: number, of: number) => `${(n / of) * 100}%`;

const pill = "whitespace-nowrap rounded-full border border-border bg-background/60 backdrop-blur px-6 py-3.5 text-sm text-muted-foreground";
const action = `${pill} transition-colors hover:border-foreground/40 hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring`;

/** The production assistant as the reference shows it: inputs on the left, outputs on the right, one centre. */
export function AssistantMap() {
  return (
    <section aria-label="How AVOS works" className="mt-16 md:mt-24">
      {/* wide screens: the graph */}
      <div className="relative mx-auto hidden h-[380px] w-full max-w-5xl md:block">
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="absolute inset-0 h-full w-full text-muted-foreground" aria-hidden>
          {YS.map((y, i) => (
            <g key={y} fill="none" stroke="var(--signal)" strokeOpacity="0.75" strokeWidth="1">
              <path className="avos-draw" pathLength={1} vectorEffect="non-scaling-stroke" style={{ animationDelay: `${i * 140}ms` }} d={`M 280 ${y} C 390 ${y}, 390 ${C}, 500 ${C}`} />
              <path className="avos-draw" pathLength={1} vectorEffect="non-scaling-stroke" style={{ animationDelay: `${i * 140 + 70}ms` }} d={`M 720 ${y} C 610 ${y}, 610 ${C}, 500 ${C}`} />
            </g>
          ))}
        </svg>
        {LEFT.map((label, i) => (
          <span key={label} className={`absolute z-10 -translate-y-1/2 ${pill}`} style={{ right: "72%", top: pct(YS[i], H) }}>{label}</span>
        ))}
        {RIGHT.map((label, i) => (
          <span key={label} className={`absolute z-10 -translate-y-1/2 ${pill}`} style={{ left: "72%", top: pct(YS[i], H) }}>{label}</span>
        ))}
        <Link href="/explainer" className="absolute left-1/2 z-10 flex -translate-x-1/2 -translate-y-1/2 items-center gap-4 rounded-full border border-[var(--signal)]/60 bg-card px-9 py-5 avos-glow transition-colors hover:border-[var(--signal)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
          style={{ top: pct(C, H) }}>
          <Mark className="h-7 w-7" />
          <span className="display whitespace-nowrap text-3xl">Production Assistant</span>
        </Link>
        <div className="absolute left-1/2 z-10 flex -translate-x-1/2 -translate-y-1/2 gap-3" style={{ top: pct(272, H) }}>
          <Link href="/explainer/prompts" className={action}>Skills</Link>
          <Link href="/models" className={action}>Models</Link>
        </div>
      </div>

      {/* phones: the same things as a plain list */}
      <div className="md:hidden">
        <Link href="/explainer" className="flex items-center gap-3 rounded-full border border-border bg-card px-6 py-4">
          <Mark className="h-6 w-6" />
          <span className="display text-2xl">Production Assistant</span>
        </Link>
        <ul className="mt-4 flex flex-wrap gap-2">
          {[...LEFT, ...RIGHT].map((l) => <li key={l} className={pill}>{l}</li>)}
          <li><Link href="/explainer/prompts" className={action}>Skills</Link></li>
          <li><Link href="/models" className={action}>Models</Link></li>
        </ul>
      </div>
    </section>
  );
}
