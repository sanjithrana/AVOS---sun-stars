"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Film } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Composer } from "@/components/stickman/Composer";
import { SkillsPanel } from "@/components/stickman/SkillsPanel";
import { stickman } from "@/lib/stickman";

const LABEL: Record<string, string> = { working: "Working", waiting: "Needs your OK", done: "Ready", error: "Stopped with an error", stopped: "Stopped" };
const KEY = "avos.stickman.skill";

/** Stickman Studio: the skills on the left (scroll to see all), the brief on the right, your videos below. */
export default function StickmanHome() {
  const list = useQuery({ queryKey: ["stickman-list"], queryFn: stickman.list, refetchInterval: 4000, retry: false });
  const styles = useQuery({ queryKey: ["stickman-styles"], queryFn: stickman.styles, retry: false, staleTime: 600000 });
  const [style, setStyle] = useState<string>("");
  useEffect(() => {
    if (style || !styles.data) return;
    let saved = "";
    try { saved = localStorage.getItem(KEY) || ""; } catch { /* storage blocked */ }
    setStyle(styles.data.styles.some((s) => s.id === saved) ? saved : styles.data.default);
  }, [styles.data, style]);
  const choose = (id: string) => { setStyle(id); try { localStorage.setItem(KEY, id); } catch { /* ignore */ } };
  const cur = styles.data?.styles.find((s) => s.id === style) ?? null;

  return (
    <AppShell header={<span className="text-lg font-semibold">Stickman Studio</span>}>
      <div className="w-full space-y-10 px-4 py-6 md:px-8 2xl:px-12">
        <div className="lg:grid lg:grid-cols-[minmax(280px,340px)_minmax(0,1fr)] lg:gap-6 2xl:grid-cols-[380px_minmax(0,1fr)]">
          <div className="mb-6 h-[60vh] lg:sticky lg:top-0 lg:mb-0 lg:h-[calc(100dvh-8.5rem)]">
            {styles.isError ? <p className="rounded-3xl border border-border p-4 text-sm text-muted-foreground">{(styles.error as Error).message}</p>
              : <SkillsPanel styles={styles.data?.styles ?? []} value={style} onChange={choose} loading={styles.isLoading} />}
          </div>
          <div className="min-w-0"><Composer style={cur} /></div>
        </div>

        <section>
          <h2 className="mb-4 text-lg font-semibold">Your videos</h2>
          {list.isError ? <p className="rounded-xl border border-amber-500/40 bg-amber-500/5 p-4 text-sm" data-testid="stickman-offline">{(list.error as Error).message}</p>
            : !list.data?.length ? <p className="text-sm text-muted-foreground">Nothing yet.</p>
            : <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
                {list.data.map((p) => (
                  <Link key={p.id} href={`/stickman/${p.id}`} className="overflow-hidden rounded-2xl border border-border bg-card hover:border-[rgba(185,172,255,0.5)]">
                    <div className="flex aspect-video items-center justify-center bg-muted">
                      {p.thumb ? /* eslint-disable-next-line @next/next/no-img-element */ <img src={stickman.file(p.id, p.thumb)} alt="" className="h-full w-full object-cover" /> : <Film className="h-8 w-8 text-muted-foreground" />}
                    </div>
                    <div className="p-4"><p className="line-clamp-2 font-semibold">{p.title}</p><p className="text-xs text-muted-foreground">{LABEL[p.status]} · {p.seconds}s · {p.aspect}</p></div>
                  </Link>
                ))}
              </div>}
        </section>
      </div>
    </AppShell>
  );
}
