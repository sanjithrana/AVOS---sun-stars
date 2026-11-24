"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Brain } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { autoclip } from "@/lib/autoclip";
import { Note } from "@/components/autoclip/ui";
import { Lane } from "@/components/youtube/YtLanes";
import { YtMonitor } from "@/components/youtube/YtMonitor";
import { YtCoach } from "@/components/youtube/YtCoach";
import { YtTests } from "@/components/youtube/YtTests";
import { YtComments } from "@/components/youtube/YtComments";

const LEARN = "__learn";

function Inner() {
  const q = useQuery({ queryKey: ["yt"], queryFn: () => autoclip.yt(), refetchInterval: 5000, retry: false });
  const [pick, setPick] = useState<string>("");
  const tab = q.data;
  const cur = pick === LEARN ? LEARN : (tab?.channels.find((c) => c.id === pick)?.id ?? tab?.channels[0]?.id ?? LEARN);
  const chan = tab?.channels.find((c) => c.id === cur);
  const tabBtn = (on: boolean) => `flex items-center gap-2 border px-4 py-2 text-sm ${on ? "border-[rgba(200,255,58,0.85)] bg-[rgba(200,255,58,0.12)]" : "border-border text-muted-foreground hover:text-foreground"}`;
  return (
    <AppShell header={<span className="text-lg font-semibold">YouTube</span>}>
      <div className="w-full space-y-6 px-4 py-6 md:px-8 2xl:px-12">
        {q.isError ? <Note tone="err">{(q.error as Error).message}</Note> : !tab ? <p className="text-sm text-muted-foreground">Loading…</p> : tab.channels.length === 0 ? (
          <Note>Connect a channel or account first (YouTube, Instagram, Facebook or TikTok): <Link href="/connections" className="underline">open Connections</Link>.</Note>
        ) : (
          <>
            <nav aria-label="Channels" className="flex flex-wrap gap-2">
              {tab.channels.map((c) => (
                <button key={c.id} type="button" className={tabBtn(cur === c.id)} onClick={() => setPick(c.id)}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  {c.thumb ? <img src={c.thumb} alt="" className="h-5 w-5 rounded-full" /> : <span className="h-5 w-5 rounded-full bg-muted" />}
                  {c.title}<span className="text-[10px] uppercase opacity-60">{c.platform || "youtube"}</span>{c.queued > 0 && <span className="bg-primary px-1.5 text-[10px] text-primary-foreground">{c.queued}</span>}
                </button>
              ))}
              <button type="button" className={tabBtn(cur === LEARN)} onClick={() => setPick(LEARN)}><Brain className="h-4 w-4" />Learning</button>
            </nav>
            {chan ? (
              <>
                <Lane key={chan.id} c={chan} tab={tab} />
                <YtMonitor tab={tab} channel={chan.id} />
              </>
            ) : (
              <>
                <Note>
                  <b>Learning</b> is only for YouTube, and all three parts are optional.<br />
                  <b>Coach:</b> looks at the videos you posted and learns which edit choices (captions, colour look, zooms, music) got more views and watch time, then suggests them, or uses them on new clips if you set Auto.<br />
                  <b>Title tests:</b> posts a clip with one title, later tries a second title, and keeps whichever got more views per hour. Off until you switch it on.<br />
                  <b>Comments:</b> reads comments on your clips, flags spam, and writes reply drafts that are only sent when you press Post.
                </Note>
                <YtCoach />
                <YtTests />
                <YtComments />
              </>
            )}
          </>
        )}
      </div>
    </AppShell>
  );
}

/** YouTube: one tab per connected channel (its own queue, times and numbers) and a Learning tab. */
export default function YouTubePage() {
  return <Suspense fallback={null}><Inner /></Suspense>;
}
