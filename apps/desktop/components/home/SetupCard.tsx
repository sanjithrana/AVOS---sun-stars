"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Clapperboard, Image as ImageIcon, KeyRound, Mic, PenLine, type LucideIcon } from "lucide-react";

/** What each saved key does right now (apps/animation_studio/studio/setup.py). */
export interface SetupPlan {
  level: "starter" | "good" | "best";
  roles: { role: "writer" | "pictures" | "video" | "voice"; title: string; uses: string; note: string; ok: boolean | null }[];
  tips: { id: string; title: string; text: string }[];
}

async function fetchSetup(): Promise<SetupPlan> {
  const r = await fetch("/studio-api/setup", { cache: "no-store" });
  if (!r.ok) throw new Error(`setup ${r.status}`);
  return r.json();
}

const ICON: Record<string, LucideIcon> = { writer: PenLine, pictures: ImageIcon, video: Clapperboard, voice: Mic };
const LEVEL: Record<SetupPlan["level"], string> = {
  starter: "Running on free fallbacks",
  good: "Good: one more key gets the best output",
  best: "Best output: writing and video are both set up",
};

/** Home: which provider writes, draws, films and speaks with the keys you saved, and the one key that would help most. */
export function SetupCard() {
  const q = useQuery({ queryKey: ["setup"], queryFn: fetchSetup, retry: false, refetchInterval: 30000 });
  if (!q.data) return null;
  const p = q.data;
  return (
    <section className="lg:col-span-12" aria-labelledby="home-setup" data-testid="home-setup">
      <div className="flex flex-wrap items-baseline justify-between gap-2 px-5 pb-3 pt-6 md:px-6">
        <h2 id="home-setup" className="flex items-center gap-2 text-[15px]"><KeyRound className="h-4 w-4 text-[var(--room)]" strokeWidth={1.5} />Your setup</h2>
        <span className="text-[12.5px] text-muted-foreground">{LEVEL[p.level]}</span>
      </div>
      <div className="grid border-t border-border lg:grid-cols-12">
        <ul className="grid grid-cols-1 gap-px bg-border sm:grid-cols-2 lg:col-span-8 xl:grid-cols-4">
          {p.roles.map((r) => {
            const Icon = ICON[r.role] ?? PenLine;
            return (
              <li key={r.role} className="bg-card p-5">
                <p className="flex items-center gap-2 text-[12.5px] text-muted-foreground">
                  <Icon className="h-4 w-4" strokeWidth={1.5} />{r.title}
                  <span className={`ml-auto h-2 w-2 rounded-full ${r.ok ? "bg-emerald-500" : r.ok === false ? "bg-[#f87171]" : "bg-[#e5a50a]"}`}
                    title={r.ok ? "Set up" : "Works, but a key would make it better"} />
                </p>
                <p className="mt-2 text-[15px] font-medium">{r.uses}</p>
                <p className="mt-1 text-[12.5px] leading-relaxed text-muted-foreground">{r.note}</p>
              </li>
            );
          })}
        </ul>
        <div className="flex flex-col gap-4 border-t border-border p-5 lg:col-span-4 lg:border-l lg:border-t-0 md:p-6">
          {p.tips.length ? p.tips.map((t) => (
            <div key={t.id}>
              <p className="text-[13.5px] font-medium">{t.title}</p>
              <p className="mt-1 text-[12.5px] leading-relaxed text-muted-foreground">{t.text}</p>
            </div>
          )) : (
            <p className="text-[13px] text-muted-foreground">Every role has a provider. Use the Test button beside each key in Settings if a job ever stops.</p>
          )}
          <Link href="/settings#keys" className="mt-auto inline-flex items-center gap-1.5 text-[12.5px] font-medium text-[var(--room)] hover:underline hover:underline-offset-4">
            Open API keys<ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      </div>
    </section>
  );
}
