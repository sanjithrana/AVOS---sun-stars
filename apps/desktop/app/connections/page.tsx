"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/AppShell";
import { autoclip } from "@/lib/autoclip";
import { Note } from "@/components/autoclip/ui";
import { YouTubeCard } from "@/components/autoclip/YouTubeCard";
import { PlatformCard } from "@/components/connections/PlatformCard";

function Inner() {
  const params = useSearchParams();
  const [origin, setOrigin] = useState("");
  useEffect(() => setOrigin(window.location.origin), []);
  const social = useQuery({ queryKey: ["social", origin], queryFn: () => autoclip.social(origin), enabled: !!origin, retry: false });
  const ov = useQuery({ queryKey: ["autoclip"], queryFn: () => autoclip.overview(), retry: false });
  const ok = params.get("connected"), bad = params.get("error");
  return (
    <AppShell header={<span className="text-lg font-semibold">Connections</span>}>
      <div className="w-full max-w-4xl space-y-6 px-4 py-6 md:px-8">
        <p className="text-sm text-muted-foreground">Connect the accounts clips can be posted to. Each one uses your own developer app, so nothing is shared with a third party and the logins stay on this studio. When an account is connected it shows up as a channel on the <Link href="/youtube" className="underline">YouTube tab</Link>, where you queue and schedule posts.</p>
        {ok && <Note>Connected: {ok}. Open the YouTube tab to queue posts to it.</Note>}
        {bad && <Note tone="err">{bad}</Note>}
        {ov.data && <YouTubeCard ov={ov.data} flash={{}} />}
        {social.isError ? <Note tone="err">{(social.error as Error).message}</Note> : social.data?.platforms.map((p) => <PlatformCard key={p.id} p={p} />)}
      </div>
    </AppShell>
  );
}

export default function ConnectionsPage() {
  return <Suspense fallback={null}><Inner /></Suspense>;
}
