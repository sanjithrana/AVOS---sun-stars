"use client";

import { useState } from "react";

/* The hero window: a working preview of a project, in the same tabs the Explainer uses.
   Shows your latest project when there is one, otherwise a labelled example. */

export interface HeroProject { title: string; frames: (string | null)[] }

const EXAMPLE: HeroProject = { title: "How coffee reaches your cup", frames: [null, null, null, null, null, null] };
const SCENES = ["The farm at dawn", "Picking cherries", "Drying beds", "The roaster", "Port and ship", "Your morning cup"];
const SHOTS = [
  ["Wide", "Farm at dawn, mist over the rows", "4 s"],
  ["Close", "Hands picking red cherries", "3 s"],
  ["Overhead", "Beans turning on drying beds", "4 s"],
  ["Medium", "Roaster checks the colour", "5 s"],
  ["Wide", "Container ship leaves port", "4 s"],
  ["Close", "Steam rising from the cup", "3 s"],
];
const TABS = ["Storyboard", "Shots", "Timeline"] as const;
const TINTS = ["from-[#3a2bb0]", "from-[#5b3df5]", "from-[#2a1f8a]", "from-[#6a4cff]", "from-[#4333b8]", "from-[#7a5cff]"];

export function HeroWindow({ project }: { project: HeroProject | null }) {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Storyboard");
  const p = project ?? EXAMPLE;
  return (
    <div className="hero-window mx-auto w-full max-w-6xl text-left" data-testid="hero-window">
      <div className="grid overflow-hidden rounded-[1.6rem] border border-[rgba(170,150,255,0.18)] bg-[rgba(8,6,24,0.72)] p-2 backdrop-blur-xl md:grid-cols-[15rem_minmax(0,1fr)]">
        <div className="hidden rounded-2xl bg-[rgba(255,255,255,0.025)] p-4 md:block">
          <p className="text-sm font-medium text-foreground">{project ? "Latest project" : "Example project"}</p>
          <p className="mt-0.5 truncate text-[11px] text-muted-foreground">{p.title}</p>
          <p className="mt-6 text-[11px] text-muted-foreground">Scenes</p>
          <ul className="mt-2 space-y-1 text-[13px]">
            {SCENES.map((s, i) => (
              <li key={s} className={`truncate rounded-lg px-2.5 py-1.5 ${i === 1 ? "bg-[rgba(124,92,255,0.14)] text-foreground" : "text-muted-foreground"}`}>{s}</li>
            ))}
          </ul>
        </div>
        <div className="rounded-2xl bg-[rgba(255,255,255,0.02)]">
          <div className="flex gap-1 border-b border-[rgba(170,150,255,0.12)] p-2" role="tablist">
            {TABS.map((t) => (
              <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}
                className={`rounded-xl px-5 py-2 text-sm transition-colors ${tab === t ? "bg-[rgba(255,255,255,0.07)] text-foreground" : "text-muted-foreground hover:text-foreground"}`}>{t}</button>
            ))}
          </div>
          <div className="min-h-[17rem] p-4">
            {tab === "Storyboard" && (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                {p.frames.slice(0, 6).map((f, i) => (
                  <figure key={i}>
                    <div className={`aspect-video overflow-hidden rounded-xl border border-white/[0.08] bg-gradient-to-br ${TINTS[i]} to-[#05030f]`}>
                      {f && /* eslint-disable-next-line @next/next/no-img-element */ <img src={f} alt="" className="h-full w-full object-cover" />}
                    </div>
                    <figcaption className="mt-1.5 truncate text-[11px] text-muted-foreground">{i + 1}. {SCENES[i]}</figcaption>
                  </figure>
                ))}
              </div>
            )}
            {tab === "Shots" && (
              <ol className="divide-y divide-[rgba(170,150,255,0.10)] text-[13px]">
                {SHOTS.map(([a, d, s], i) => (
                  <li key={i} className="grid grid-cols-[2rem_5rem_minmax(0,1fr)_3rem] items-center gap-2 py-2.5">
                    <span className="text-muted-foreground">{i + 1}</span>
                    <span className="text-[var(--signal)]">{a}</span>
                    <span className="truncate">{d}</span>
                    <span className="text-right text-muted-foreground">{s}</span>
                  </li>
                ))}
              </ol>
            )}
            {tab === "Timeline" && (
              <div className="space-y-3 pt-2 text-[11px] text-muted-foreground">
                {[["Picture", [4, 3, 4, 5, 4, 3], "bg-[rgba(124,92,255,0.45)]"], ["Voice", [7, 9, 7], "bg-[rgba(127,227,255,0.30)]"], ["Music", [23], "bg-[rgba(255,143,210,0.28)]"]].map(([label, parts, tone]) => (
                  <div key={label as string} className="grid grid-cols-[4rem_minmax(0,1fr)] items-center gap-3">
                    <span>{label as string}</span>
                    <div className="flex h-9 gap-1">
                      {(parts as number[]).map((w, i) => <div key={i} style={{ flex: w }} className={`rounded-lg ${tone as string}`} />)}
                    </div>
                  </div>
                ))}
                <p className="pt-3">23 seconds · voice and music mixed at the finish step</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
