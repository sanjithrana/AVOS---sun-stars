"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Clapperboard, Landmark, Sparkles } from "lucide-react";
import { HeroWindow } from "@/components/brand/HeroWindow";
import { Orb } from "@/components/brand/Orb";
import { HexMesh } from "@/components/brand/HexMesh";
import { PromptBar } from "@/components/home/PromptBar";
import { AppShell } from "@/components/layout/AppShell";
import { explainer, type Status } from "@/lib/explainer";
import { stickman } from "@/lib/stickman";

const STATUS: Record<Status, string> = { working: "Working", waiting: "Waiting for you", done: "Done", error: "Needs attention", stopped: "Stopped" };
const TONE: Record<string, string> = { working: "text-[#7aa2ff]", waiting: "text-[#d9a64e]", done: "text-[#52c79a]", error: "text-[#e0657c]", stopped: "text-muted-foreground" };

const MAKE = [
  { href: "/explainer", title: "Explainer", icon: Sparkles, text: "One question or an article link becomes a short video: researched script, a presenter, props, voice, captions and music.",
    eg: "Why does a magnet fall slowly through a copper pipe?" },
  { href: "/stickman", title: "Stickman history", icon: Landmark, text: "A historical event told in six stickman clips, with a written package for publishing.",
    eg: "The night the Titanic hit the iceberg" },
  { href: "/animations", title: "Animation and series", icon: Clapperboard, text: "Films and episodes in the style of a reference, with the same characters from one episode to the next.",
    eg: "Episode 3: the neighbours' cat goes missing" },
];

const CREW: [string, string[]][] = [
  ["Script", ["Researcher", "Scriptwriter", "Director", "Cast memory"]],
  ["Design", ["Character designer", "Set and prop designer"]],
  ["Storyboard", ["Storyboard artist", "Key-pose artist", "Continuity checker", "Board builder"]],
  ["Shoot", ["Voice actor", "Animator", "Lip-sync"]],
  ["Finish", ["Composer", "Editor"]],
];

const LEVELS = [
  { name: "Cast", text: "A portrait and a design sheet per character. The look is locked and pasted first into every picture." },
  { name: "World", text: "The empty set and every prop, drawn once and reused in every shot." },
  { name: "Scenes", text: "Each scene on its own board: the shots in order, the action, the camera, the line." },
  { name: "Clips", text: "Each shot from first frame to last frame, with what moves and when." },
];

interface Row { id: string; href: string; kind: string; title: string; status: Status; updatedAt: string; thumb?: string | null }

/** Home: the promise and the prompt box over a glowing mesh, what you can make, the crew, the storyboard levels, cast memory, then your projects. */
export default function Home() {
  const ex = useQuery({ queryKey: ["explainer-list"], queryFn: explainer.list, refetchInterval: 6000, retry: false });
  const st = useQuery({ queryKey: ["stickman-list"], queryFn: stickman.list, refetchInterval: 6000, retry: false });
  const mem = useQuery({ queryKey: ["cast-memory"], queryFn: explainer.memory, retry: false });
  const rows: Row[] = [
    ...(ex.data ?? []).map((v) => ({ id: v.id, href: `/explainer/${v.id}`, kind: "Explainer", title: v.title || v.brief, status: v.status, updatedAt: v.updatedAt, thumb: v.thumb ? explainer.file(v.id, v.thumb) : null })),
    ...(st.data ?? []).map((v) => ({ id: v.id, href: `/stickman/${v.id}`, kind: "Stickman", title: v.title || v.event, status: v.status, updatedAt: v.updatedAt, thumb: null })),
  ].sort((a, b) => (b.updatedAt || "").localeCompare(a.updatedAt || ""));
  const recent = rows.slice(0, 8);
  const withThumb = rows.filter((r) => r.thumb);
  const latest = withThumb.length ? { title: withThumb[0].title, frames: Array.from({ length: 6 }, (_, i) => withThumb[i]?.thumb ?? null) } : null;
  const active = rows.filter((r) => r.status === "working" || r.status === "waiting").slice(0, 5);
  const loading = ex.isLoading || st.isLoading;
  const offline = ex.isError && st.isError ? (ex.error as Error).message : null;
  const cast = (mem.data?.cast ?? []).filter((m) => m.portrait).slice(0, 6);

  return (
    <AppShell header={<span className="text-sm text-muted-foreground">Production assistant</span>}>
      <div className="w-full px-4 pb-24 md:px-10 2xl:px-16">
        {/* 1. The promise and the one box */}
        <section className="hero-mesh relative -mx-4 flex flex-col items-center overflow-hidden px-4 pb-24 pt-14 text-center md:-mx-10 md:px-10 lg:pt-20 2xl:-mx-16 2xl:px-16">
          <div className="absolute inset-x-0 bottom-0 h-[50%]" aria-hidden><HexMesh /><div className="mesh-edge pointer-events-none absolute inset-0" /></div>
          <div className="mesh-fade pointer-events-none absolute inset-0" aria-hidden />
          <h1 className="display relative max-w-5xl text-5xl md:text-6xl xl:text-7xl">One idea in.<br /><b>A finished video out.</b></h1>
          <p className="relative mt-6 max-w-2xl text-base leading-relaxed text-muted-foreground md:text-lg">
            Fifteen AI agents research, write, design the characters, storyboard every shot, animate, voice, score and edit.
          </p>
          <div className="relative mt-10 flex w-full justify-center"><PromptBar /></div>
        </section>

        {/* 2. What you can make */}
        <section aria-labelledby="home-make" className="mt-4">
          <h2 id="home-make" className="display text-3xl md:text-4xl">What you can make</h2>
          <div className="mt-6 grid gap-4 md:grid-cols-2 lg:grid-cols-[1.25fr_1fr_1fr]">
            {MAKE.map((m, i) => (
              <Link key={m.href} href={m.href} className={`make group relative flex flex-col overflow-hidden rounded-3xl border border-border bg-card p-6 ${i === 0 ? "lg:row-span-1 lg:p-8" : ""}`}>
                <span className="inline-flex h-11 w-11 items-center justify-center rounded-2xl border border-[rgba(185,172,255,0.35)] bg-[rgba(124,92,255,0.14)] transition-shadow group-hover:shadow-[0_0_20px_-2px_rgba(124,92,255,0.9)]"><m.icon className="h-5 w-5 text-[var(--signal)]" strokeWidth={1.5} /></span>
                <p className={`mt-5 font-medium ${i === 0 ? "text-2xl" : "text-xl"}`}>{m.title}</p>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{m.text}</p>
                <p className="mt-auto pt-6 text-[13px] text-foreground/80"><span className="text-muted-foreground">Try: </span>“{m.eg}”</p>
              </Link>
            ))}
          </div>
        </section>

        {/* 3. The crew */}
        <section id="how" aria-labelledby="home-crew" className="mt-24 scroll-mt-24">
          <div className="space-y-8">
            <div className="max-w-2xl">
              <h2 id="home-crew" className="display text-3xl md:text-4xl">Fifteen agents, one line</h2>
              <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
                Each agent does one job and hands its work to the next. The line stops after the script, the characters and the storyboard so you can change anything before it moves on. On every video you can see which agent is working and what it made.
              </p>
            </div>
            <ol className="crew-line grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
              {CREW.map(([stage, names], i) => (
                <li key={stage} className="relative rounded-2xl border border-border p-4">
                  <p className="text-[11px] text-[var(--signal)]">Step {i + 1}</p>
                  <p className="mt-0.5 text-base font-medium">{stage}</p>
                  <ul className="mt-3 space-y-1.5">
                    {names.map((n) => <li key={n} className="text-[13px] text-muted-foreground">{n}</li>)}
                  </ul>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* 4. Storyboard levels + the live window */}
        <section aria-labelledby="home-board" className="hero-scene relative -mx-4 mt-24 px-4 md:-mx-10 md:px-10 2xl:-mx-16 2xl:px-16">
          <div className="text-center">
            <h2 id="home-board" className="display text-3xl md:text-5xl">Storyboards the way studios hand them over</h2>
            <p className="mx-auto mt-4 max-w-2xl text-sm leading-relaxed text-muted-foreground md:text-base">Not one crowded sheet. Four levels, so every model, and you, look at one clear thing at a time.</p>
          </div>
          <ol className="mx-auto mt-10 grid max-w-6xl gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {LEVELS.map((l, i) => (
              <li key={l.name} className="level rounded-2xl border border-border bg-card p-5" style={{ transform: `translateY(${i * 10}px)` }}>
                <p className="text-[11px] text-[var(--signal)]">Level {i + 1}</p>
                <p className="mt-1 text-lg font-medium">{l.name}</p>
                <p className="mt-2 text-[13px] leading-relaxed text-muted-foreground">{l.text}</p>
              </li>
            ))}
          </ol>
          <div className="horizon pointer-events-none relative mt-14 h-24 w-full" aria-hidden />
          <div className="relative -mt-14 w-full"><HeroWindow project={latest} /></div>
        </section>

        {/* 5. Cast memory */}
        <section aria-labelledby="home-memory" className="mt-24 grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)] lg:items-center">
          <div>
            <h2 id="home-memory" className="display text-3xl md:text-4xl">It remembers your characters</h2>
            <p className="mt-4 text-sm leading-relaxed text-muted-foreground md:text-base">
              Every character gets a locked look, its own seed and a clean identity portrait. Use the same name in your next idea and the same character comes back, video after video. With a vision model in your crew, every frame is checked against the portrait and redrawn if the face drifts.
            </p>
            <Link href="/explainer" className="mt-6 inline-flex text-sm text-[var(--signal)] underline-offset-4 hover:underline">See your cast in Explainer</Link>
          </div>
          <ul className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {(cast.length ? cast : Array.from({ length: 4 }, () => null)).map((m, i) => (
              <li key={m?.id ?? i} className="overflow-hidden rounded-2xl border border-border bg-card">
                <div className="aspect-[3/4] bg-gradient-to-b from-[#1b1450] to-black">
                  {m?.portrait && /* eslint-disable-next-line @next/next/no-img-element */ <img src={explainer.memoryFile(m.id, m.portrait, m.updated)} alt={`${m.name} portrait`} className="h-full w-full object-cover" />}
                </div>
                <p className="truncate px-3 py-2 text-[13px]">{m ? m.name : "Your first character"}</p>
              </li>
            ))}
          </ul>
        </section>

        {/* 6. Your projects */}
        <section aria-labelledby="home-videos" className="mt-24">
          <h2 id="home-videos" className="display text-3xl md:text-4xl">Your projects</h2>
          <div className="mt-6">
            {loading ? (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4" aria-busy="true">{[0, 1, 2].map((i) => <div key={i} className="h-28 animate-pulse rounded-3xl bg-white/[0.05]" />)}</div>
            ) : offline ? (
              <p className="rounded-3xl border border-border bg-card p-5 text-sm text-muted-foreground" role="alert" data-testid="home-offline">{offline}</p>
            ) : recent.length === 0 ? (
              <div className="rounded-3xl border border-dashed border-border p-10 text-center text-sm text-muted-foreground">
                No projects yet. <Link href="/explainer" className="text-foreground underline underline-offset-4">Start with one idea.</Link>
              </div>
            ) : (
              <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
                {recent.map((v) => (
                  <li key={`${v.kind}-${v.id}`}>
                    <Link href={v.href} className="group block overflow-hidden rounded-3xl border border-border bg-card focus-visible:outline-2 focus-visible:outline-ring">
                      <div className="aspect-video bg-gradient-to-br from-[#2a1f8a] to-[#05030f]">
                        {v.thumb && /* eslint-disable-next-line @next/next/no-img-element */ <img src={v.thumb} alt="" className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105" />}
                      </div>
                      <div className="p-4">
                        <p className="truncate text-[15px] font-medium">{v.title}</p>
                        <p className="mt-1 text-xs text-muted-foreground">{v.kind} · <span className={TONE[v.status] ?? ""}>{STATUS[v.status] ?? v.status}</span></p>
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>
          {active.length > 0 && (
            <ul className="mt-6 divide-y divide-border overflow-hidden rounded-3xl border border-border bg-card" aria-label="Working now">
              {active.map((v) => (
                <li key={`${v.kind}-${v.id}`}>
                  <Link href={v.href} className="flex items-center justify-between gap-4 px-5 py-3.5 text-sm hover:bg-white/[0.04]">
                    <span className="min-w-0 truncate">{v.title}</span>
                    <span className={`shrink-0 text-xs ${TONE[v.status] ?? ""}`}>{STATUS[v.status]}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* 7. Sign-off */}
        <section className="closing relative mt-24 flex flex-col items-center overflow-hidden rounded-[2rem] border border-border px-6 pb-16 pt-14 text-center">
          <svg className="pointer-events-none absolute inset-x-0 top-0 h-full w-full" viewBox="0 0 1200 600" preserveAspectRatio="xMidYMin slice" aria-hidden>
            {[200, 310, 430, 560].map((r) => <ellipse key={r} cx="600" cy="200" rx={r * 1.6} ry={r} fill="none" stroke="rgba(170,150,255,0.07)" />)}
          </svg>
          <Orb size={190} />
          <h2 className="display relative mt-10 text-3xl md:text-5xl">Ready to make your first video?</h2>
          <p className="relative mx-auto mt-4 max-w-xl text-sm leading-relaxed text-muted-foreground md:text-base">Type one idea. The crew does the rest, and stops to ask you at each step.</p>
          <Link href="/explainer" className="relative mt-8 inline-flex h-12 items-center rounded-full bg-primary px-9 text-sm font-semibold" data-testid="home-start">Start a video</Link>
        </section>
      </div>
    </AppShell>
  );
}
