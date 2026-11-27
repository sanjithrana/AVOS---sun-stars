"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Clapperboard, Landmark, Scissors, Sparkles, type LucideIcon } from "lucide-react";
import { PromptBar } from "@/components/home/PromptBar";
import { SetupCard } from "@/components/home/SetupCard";
import { AppShell } from "@/components/layout/AppShell";
import { EMPTY_ACTIVITY, ago, fetchActivity, type ActivityItem } from "@/lib/activity";
import { explainer } from "@/lib/explainer";

/** What each studio makes, drawn in the shape it comes out in. */
const STUDIOS: { href: string; name: string; does: string; shape: "9/16" | "16/9"; icon: LucideIcon; sample: string }[] = [
  { href: "/explainer", name: "Explainer", does: "A question or an article becomes a researched video with a presenter, voice, captions and music.", shape: "16/9", icon: Sparkles, sample: "Why does a magnet fall slowly through a copper pipe?" },
  { href: "/autoclip", name: "Auto Clip", does: "A long video or stream becomes captioned Shorts, ready to post on a schedule.", shape: "9/16", icon: Scissors, sample: "Paste a podcast or stream link" },
  { href: "/stickman", name: "Stickman", does: "A moment in history told in six stickman scenes, with a title and description to publish.", shape: "9/16", icon: Landmark, sample: "The night the Titanic hit the iceberg" },
  { href: "/animations", name: "Animation", does: "Films and series episodes in the look of a reference, with the same characters every episode.", shape: "16/9", icon: Clapperboard, sample: "Episode 3: the neighbours’ cat goes missing" },
];

const STATE: Record<string, string> = { running: "Working", waiting: "Needs you", error: "Failed", done: "Done", stopped: "Stopped" };

function Frame({ shape, children }: { shape: "9/16" | "16/9"; children?: React.ReactNode }) {
  return (
    <div className={`marks relative overflow-hidden border border-border bg-background text-muted-foreground ${shape === "9/16" ? "aspect-[9/16] h-full" : "aspect-video w-full"}`}>
      {children}
    </div>
  );
}

/** What each studio hands back, drawn small in code: a title card, a captioned Short, a stickman scene, a strip of frames. */
function Preview({ id, sample }: { id: string; sample: string }) {
  if (id === "/explainer") return (
    <Frame shape="16/9">
      <div className="absolute inset-0 flex flex-col justify-between p-4">
        <span className="font-mono text-[10px] tabular">00:04 / 00:30</span>
        <p className="max-w-[80%] font-[family-name:var(--font-display)] text-[15px] leading-tight text-foreground">{sample}</p>
        <div className="h-[2px] w-full bg-border"><div className="h-full w-[14%] bg-[var(--room)]" /></div>
      </div>
    </Frame>
  );
  if (id === "/autoclip") return (
    <Frame shape="9/16">
      <div className="absolute inset-x-0 top-0 flex h-[42%] items-end justify-center bg-muted">
        <span className="mb-0 h-[46%] w-[46%] rounded-t-full bg-muted-foreground/35" aria-hidden />
      </div>
      <p className="absolute inset-x-2 top-[44%] text-center text-[10px] font-semibold uppercase leading-tight text-foreground">he did <span className="text-[var(--room)]">not</span> see that</p>
      <div className="absolute inset-x-0 bottom-0 h-[44%] bg-[repeating-linear-gradient(135deg,transparent_0_6px,color-mix(in_oklab,var(--foreground)_6%,transparent)_6px_7px)]" />
    </Frame>
  );
  if (id === "/stickman") return (
    <Frame shape="9/16">
      <svg viewBox="0 0 90 160" className="absolute inset-0 h-full w-full" aria-hidden fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <line x1="0" y1="118" x2="90" y2="118" strokeWidth="1" opacity=".5" />
        <circle cx="40" cy="70" r="7" className="text-foreground" stroke="currentColor" />
        <path d="M40 77 V98 M40 84 L30 92 M40 84 L52 78 M40 98 L32 117 M40 98 L48 117" className="text-foreground" stroke="currentColor" />
        <path d="M60 118 L66 96 L74 118" stroke="var(--room)" />
      </svg>
      <span className="absolute bottom-4 right-4 font-mono text-[10px] tabular">3 of 6</span>
    </Frame>
  );
  return (
    <Frame shape="16/9">
      <div className="absolute inset-0 grid grid-cols-3 gap-px bg-border p-0">
        {["12", "13", "14"].map((n, i) => (
          <div key={n} className="relative bg-background">
            <span className="absolute left-1.5 top-1 font-mono text-[9px] tabular">{n}</span>
            <span className={`absolute bottom-[22%] left-1/2 h-5 w-5 -translate-x-1/2 rounded-full ${i === 1 ? "bg-[var(--room)]" : "bg-muted-foreground/40"}`} aria-hidden />
          </div>
        ))}
      </div>
      <span className="absolute inset-x-3 bottom-2 truncate text-[10px]">{sample}</span>
    </Frame>
  );
}

function JobRow({ it }: { it: ActivityItem }) {
  const live = it.state === "running";
  return (
    <li>
      <Link href={it.href} className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 px-5 py-3 transition-colors hover:bg-muted focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-ring">
        <span className={live ? "tally" : "inline-block h-[7px] w-[7px] border border-muted-foreground"} data-live={live || undefined} aria-hidden />
        <span className="min-w-0">
          <span className="block truncate text-[13.5px] font-medium">{it.title || "Untitled"}</span>
          <span className="block truncate text-[12px] text-muted-foreground">{it.studio}{it.stage ? `, ${it.stage.toLowerCase()}` : ""}</span>
        </span>
        <span className={`text-[12px] ${it.state === "error" ? "text-destructive" : it.state === "waiting" ? "text-warning" : "text-muted-foreground"}`}>
          {it.state === "running" || it.state === "waiting" ? STATE[it.state] : it.updatedAt ? ago(it.updatedAt) : STATE[it.state]}
        </span>
      </Link>
    </li>
  );
}

/** Home is the studio floor: start something on the left, see what is running on the right, then every room, then your latest work. */
export default function Home() {
  const act = useQuery({ queryKey: ["activity"], queryFn: fetchActivity, retry: false, refetchInterval: 6000 });
  const mem = useQuery({ queryKey: ["cast-memory"], queryFn: explainer.memory, retry: false });
  const a = act.data ?? EMPTY_ACTIVITY;
  const live = a.jobs.filter((j) => j.state === "running" || j.state === "waiting");
  const recent = a.recent.filter((r) => r.thumb || r.video).slice(0, 8);
  const cast = (mem.data?.cast ?? []).filter((m) => m.portrait).slice(0, 5);
  const offline = act.isError ? "The studio engine isn’t answering. Start it with docker compose up, then this page fills in by itself." : null;

  return (
    <AppShell header={<span className="text-muted-foreground">Home</span>}>
      <div className="cut min-h-full border-0 lg:grid-cols-12">
        {/* start */}
        <section className="px-5 pb-8 pt-10 md:px-10 lg:col-span-8 lg:pt-14" aria-labelledby="home-title">
          <h1 id="home-title" className="display max-w-[18ch] text-[2.25rem] md:text-[3rem] xl:text-[3.5rem]">One idea in, a finished video out</h1>
          <p className="mt-4 max-w-[58ch] text-[15px] leading-relaxed text-muted-foreground">Type one idea. The crew writes, designs, shoots and edits it, and stops to check with you after the script, the characters and the storyboard.</p>
          <div className="mt-8"><PromptBar /></div>
        </section>

        {/* running now */}
        <section className="flex min-h-[18rem] flex-col lg:col-span-4" aria-labelledby="home-live">
          <div className="flex items-center justify-between px-5 pb-3 pt-6">
            <h2 id="home-live" className="text-[15px]">On the floor</h2>
            <span className="text-[12px] text-muted-foreground tabular">{a.counts.running} working · {a.counts.waiting} waiting</span>
          </div>
          {offline ? (
            <p className="mx-5 mb-5 border border-border p-4 text-[13px] text-muted-foreground" role="alert" data-testid="home-offline">{offline}</p>
          ) : live.length ? (
            <ul className="divide-y divide-border border-t border-border">{live.slice(0, 7).map((it) => <JobRow key={`${it.studio}-${it.id}`} it={it} />)}</ul>
          ) : (
            <div className="mx-5 mb-5 flex flex-1 flex-col justify-end border border-dashed border-border p-5">
              <p className="text-[13.5px] font-medium">Nothing is running</p>
              <p className="mt-1 text-[13px] text-muted-foreground">Jobs you start show up here with a red light while they work, and stay here if they need an answer from you.</p>
            </div>
          )}
          {a.recent.length > 0 && (
            <>
              <p className="px-5 pb-1 pt-5 text-[12px] text-muted-foreground">Finished lately</p>
              <ul className="divide-y divide-border border-y border-border">{a.recent.slice(0, 4).map((it) => <JobRow key={`r-${it.studio}-${it.id}`} it={it} />)}</ul>
            </>
          )}
        </section>

        {/* which key does what, and the one to add next */}
        <SetupCard />

        {/* the rooms */}
        {STUDIOS.map((s) => (
          <Link key={s.href} href={s.href} data-room={s.href} className="group flex flex-col gap-5 border-t-2 border-t-transparent p-5 hover:border-t-[var(--room)] transition-colors hover:bg-muted focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-ring md:p-6 lg:col-span-3" data-testid={`room-${s.href.slice(1)}`}>
            <div className="flex h-36 items-end justify-center md:h-44"><Preview id={s.href} sample={s.sample} /></div>
            <div>
              <p className="flex items-center gap-2 font-[family-name:var(--font-display)] text-[18px] font-medium tracking-[-0.01em]"><s.icon className="h-4 w-4 text-[var(--room)]" strokeWidth={1.5} />{s.name}</p>
              <p className="mt-1.5 text-[13px] leading-relaxed text-muted-foreground">{s.does}</p>
            </div>
            <span className="mt-auto text-[12.5px] font-medium text-[var(--room)] group-hover:underline group-hover:underline-offset-4">Open {s.name}</span>
          </Link>
        ))}

        {/* latest work */}
        <section className="lg:col-span-9" aria-labelledby="home-work">
          <div className="flex items-baseline justify-between px-5 pb-4 pt-6 md:px-6">
            <h2 id="home-work" className="text-[15px]">Latest work</h2>
            <Link href="/library" className="text-[12.5px] text-muted-foreground hover:text-foreground">Everything in the library</Link>
          </div>
          {recent.length ? (
            <ul className="grid grid-cols-2 gap-px border-t border-border bg-border sm:grid-cols-4">
              {recent.map((it) => (
                <li key={`w-${it.studio}-${it.id}`} className="bg-card">
                  <Link href={it.href} className="group block p-3 focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-ring">
                    <div className="aspect-video overflow-hidden bg-background">
                      {it.thumb && /* eslint-disable-next-line @next/next/no-img-element */ <img src={it.thumb} alt="" className="h-full w-full object-cover" loading="lazy" />}
                    </div>
                    <p className="mt-2 truncate text-[13px] font-medium">{it.title || "Untitled"}</p>
                    <p className="text-[12px] text-muted-foreground">{it.studio}{it.updatedAt ? `, ${ago(it.updatedAt)}` : ""}</p>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="border-t border-border px-5 py-8 text-[13px] text-muted-foreground md:px-6">Finished videos and clips appear here with a picture, newest first.</p>
          )}
        </section>

        {/* cast */}
        <section className="flex flex-col lg:col-span-3" aria-labelledby="home-cast">
          <div className="px-5 pb-4 pt-6">
            <h2 id="home-cast" className="text-[15px]">Your cast</h2>
            <p className="mt-1 text-[13px] leading-relaxed text-muted-foreground">Use a character’s name in a new idea and the same face comes back.</p>
          </div>
          {cast.length ? (
            <ul className="grid grid-cols-3 gap-px border-t border-border bg-border">
              {cast.map((m) => (
                <li key={m.id} className="bg-card p-2">
                  <div className="aspect-[3/4] overflow-hidden bg-background">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={explainer.memoryFile(m.id, m.portrait!, m.updated)} alt={`${m.name}`} className="h-full w-full object-cover" />
                  </div>
                  <p className="mt-1.5 truncate text-[12px]">{m.name}</p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-auto border-t border-border px-5 py-5 text-[13px] text-muted-foreground">Characters from your Explainer videos are kept here.</p>
          )}
        </section>
      </div>
    </AppShell>
  );
}
