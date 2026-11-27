"use client";
import { Scissors, Send, Type } from "lucide-react";
import { Lit, PageHero } from "@/components/brand/PageHero";

const WORDS = ["Smart moments", "Word-by-word captions", "9:16 vertical", "Blurred, zoomed or filled", "Review first or fully automatic", "Posts to YouTube Shorts", "Tracks views and earnings"];

/** The top of the Auto Clip page: what it does at a glance, where clips come from and go, and a ticker of what you get. */
export function Hero() {
  return (
    <div className="space-y-4">
      <PageHero eyebrow="Auto Clip" title={<>One long video, <Lit>a week of Shorts</Lit></>}
        blurb="Drop a video or a link. Auto Clip picks the best moments, cuts them for phones, adds captions, and can post them to your channel while you sleep."
        steps={[
          { icon: Scissors, t: "Find the moments", d: "Loud, lively parts of your video, snapped to full sentences." },
          { icon: Type, t: "Cut and caption", d: "Vertical 9:16 clips with big burned-in captions." },
          { icon: Send, t: "Post on autopilot", d: "Connect YouTube, set the rules, and it posts and tracks for you." },
        ]} />
      <div className="flex flex-wrap items-center justify-between gap-x-8 gap-y-3 border-y border-border py-4">
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2"><span className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Clips from</span>
          {["Your upload", "YouTube link", "Any public video link"].map((x) => <span key={x} className="text-sm font-semibold">{x}</span>)}</div>
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2"><span className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Posts to</span>
          <span className="text-sm font-semibold">YouTube Shorts</span></div>
      </div>
      <div className="marquee py-1" aria-hidden>
        {[0, 1].map((k) => (
          <ul key={k} className="font-display">
            {WORDS.map((w) => <li key={w} className="display whitespace-nowrap text-xl text-[rgba(255,255,255,0.14)] md:text-3xl">{w} <span className="text-signal">✦</span></li>)}
          </ul>
        ))}
      </div>
    </div>
  );
}
