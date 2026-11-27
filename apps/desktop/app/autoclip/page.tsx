"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { BackLink } from "@/components/layout/BackLink";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { autoclip } from "@/lib/autoclip";
import { MakeClips } from "@/components/autoclip/MakeClips";
import { StatusBar } from "@/components/autoclip/StatusBar";
import { Explore } from "@/components/autoclip/Explore";
import { JobView } from "@/components/autoclip/JobList";
import { Started } from "@/components/autoclip/Started";
import { YouTubeCard } from "@/components/autoclip/YouTubeCard";
import { AutopilotCard } from "@/components/autoclip/AutopilotCard";
import { ResultsCard } from "@/components/autoclip/ResultsCard";
import { LiveWatch } from "@/components/autoclip/LiveWatch";
import { Note } from "@/components/autoclip/ui";

function Inner() {
  const params = useSearchParams();
  const router = useRouter();
  const open = params.get("open") || "";
  const v0 = params.get("view");
  const view = v0 === "live" ? "live" : v0 === "explore" ? "explore" : v0 === "channel" || params.get("connected") || params.get("error") ? "channel" : "clips";   // back from Google sign-in: show the channel
  const picked = params.get("url") || "";
  const flash = { connected: params.get("connected") || undefined, error: params.get("error") || undefined };
  const q = useQuery({ queryKey: ["autoclip"], queryFn: autoclip.overview, refetchInterval: 4000, retry: false });
  const [fresh, setFresh] = useState("");
  return (
    <AppShell header={<span className="text-lg font-semibold">Auto Clip</span>}>
      <div className="w-full space-y-8 px-4 py-6 md:px-8 2xl:px-12">
        {q.isError ? <Note tone="err">{(q.error as Error).message}</Note> : !q.data ? <p className="text-sm text-muted-foreground">Loading…</p> : open ? (
          // Opened from the Library (or the "ready" message): just that video's clips.
          <>
            <BackLink direct href="/library?studio=autoclip" className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="h-4 w-4" />Auto Clip library</BackLink>
            <JobView id={open} ov={q.data} onGone={() => router.replace("/library?studio=autoclip")} />
            <Link href="/autoclip" className="inline-block text-sm underline">Make more clips</Link>
          </>
        ) : (
          <>
            <nav aria-label="Auto Clip" className="-mt-2 flex flex-wrap gap-6 border-b border-border">
              {([["clips", "Make clips", "/autoclip"], ["explore", "Explore trending", "/autoclip?view=explore"], ["live", "Live streamers", "/autoclip?view=live"], ["channel", "Channel and autopilot", "/autoclip?view=channel"]] as const).map(([k, label, href]) => (
                <Link key={k} href={href} scroll={false} aria-current={view === k ? "page" : undefined}
                  className={`relative -mb-px inline-flex h-10 items-center border-b-2 text-[13.5px] transition-colors ${view === k ? "border-signal text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"}`}>{label}</Link>
              ))}
            </nav>
            {view === "live" ? <LiveWatch /> : view === "explore" ? <Explore onPick={(u) => router.push(`/autoclip?url=${encodeURIComponent(u)}`)} /> : view === "channel" ? (
              <>
                <YouTubeCard ov={q.data} flash={flash} />
                <AutopilotCard ov={q.data} />
                <ResultsCard />
              </>
            ) : (
              <>
                {fresh && <Started id={fresh} />}
                <MakeClips key={picked} ov={q.data} onMade={setFresh} initialUrl={picked} />
              </>
            )}
          </>
        )}
      </div>
      <StatusBar />
    </AppShell>
  );
}

/** Auto Clip: long video in, captioned vertical clips out. Finished videos live in the Library; connect YouTube and let autopilot post and track them here. */
export default function AutoClipPage() {
  return <Suspense fallback={null}><Inner /></Suspense>;
}
