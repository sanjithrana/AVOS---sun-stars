"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Film, Search } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { library, type LibraryItem as Item0 } from "@/lib/activity";

type LibraryItem = Item0 & { createdAt?: string };
import { Tag, type TagTone } from "@/components/ui/Tag";
import { Lit, PageHero } from "@/components/brand/PageHero";
import { QueueVideo } from "@/components/youtube/QueueVideo";

const STATE_LABEL: Record<string, string> = {
  running: "Working", waiting: "Needs you", done: "Ready", error: "Stopped with an error", stopped: "Stopped",
};
const STATE_TONE: Record<string, TagTone> = {
  running: "accent", waiting: "warn", done: "good", error: "bad", stopped: "muted",
};
const STUDIO_LABEL: Record<string, string> = {
  skills: "Skills", explainer: "Explainer", stickman: "Stickman", series: "Animations", films: "Films", autoclip: "Auto Clip",
};

/**
 * Everything every studio has made, in one place.
 *
 * Each studio used to keep its own "Your videos" list, so finding one output meant remembering which studio made it.
 * This is the same data from the activity feed, grouped rather than capped.
 */
export default function LibraryPage() {
  return <Suspense fallback={null}><Library /></Suspense>;
}

const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, "");

function Library() {
  const q = useQuery({ queryKey: ["library"], queryFn: () => library(500), refetchInterval: 10000, retry: false });
  const params = useSearchParams();
  const router = useRouter();
  const path = usePathname();
  const want = params.get("studio") || "";
  const [studio, setStudioState] = useState("");
  useEffect(() => {                                   // ?studio=autoclip opens the Library on that studio's videos (the back link from a studio uses it)
    if (!want || !q.data) return;
    const hit = (q.data.by_studio ?? []).find((s) => norm(s.name) === norm(want) || norm(STUDIO_LABEL[s.name] ?? "") === norm(want));
    setStudioState(hit ? hit.name : "");
  }, [want, q.data]);
  const setStudio = (v: string) => {                  // the filter lives in the address, so the browser's back button returns to it
    setStudioState(v);
    router.replace(v ? `${path}?studio=${encodeURIComponent(v)}` : path, { scroll: false });
  };
  const [state, setState] = useState("");
  const [style, setStyle] = useState("");
  const [text, setText] = useState("");

  const items = useMemo(() => {
    const t = text.trim().toLowerCase();
    return (q.data?.items ?? []).filter((x) =>
      (!studio || x.studio === studio) && (!state || x.state === state) && (!style || x.style === style) &&
      (!t || `${x.title} ${x.studio} ${x.kind} ${x.stage} ${x.style ?? ""}`.toLowerCase().includes(t)));
  }, [q.data, studio, state, style, text]);

  const groups = useMemo(() => {
    const by = new Map<string, LibraryItem[]>();
    for (const x of items) by.set(x.studio, [...(by.get(x.studio) ?? []), x]);
    return [...by.entries()].sort((a, b) => b[1].length - a[1].length);
  }, [items]);

  return (
    <AppShell header={<span className="text-lg font-semibold">Library</span>}>
      <div className="w-full space-y-6 px-4 py-6 md:px-8 2xl:px-12">
        <PageHero compact eyebrow="Library" title={<>Everything you have <Lit>made.</Lit></>} blurb="Videos, films, clips and runs from every studio, in one place." />
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative min-w-[220px] flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Search everything you have made"
              aria-label="Search outputs"
              className="w-full border border-border bg-card py-2.5 pl-10 pr-3 text-sm outline-none placeholder:text-muted-foreground focus:border-[rgba(200,255,58,0.6)]" />
          </div>
          <p className="text-xs text-muted-foreground">{items.length} of {q.data?.total ?? 0}</p>
        </div>

        <div className="flex flex-wrap gap-2">
          <Chip on={!studio} onClick={() => setStudio("")}>All studios</Chip>
          {(q.data?.by_studio ?? []).map((s) => (
            <Chip key={s.name} on={studio === s.name} onClick={() => setStudio(studio === s.name ? "" : s.name)}>
              {STUDIO_LABEL[s.name] ?? s.name} {s.count}
            </Chip>
          ))}
          <span className="mx-1 w-px self-stretch bg-border" />
          {(q.data?.by_state ?? []).map((s) => (
            <Chip key={s.name} on={state === s.name} onClick={() => setState(state === s.name ? "" : s.name)}>
              {STATE_LABEL[s.name] ?? s.name} {s.count}
            </Chip>
          ))}
        </div>

        {(q.data?.by_style ?? []).length > 0 && (
          <div className="flex flex-wrap gap-2" aria-label="Style">
            <Chip on={!style} onClick={() => setStyle("")}>Every style</Chip>
            {(q.data?.by_style ?? []).map((s) => (
              <Chip key={s.name} on={style === s.name} onClick={() => setStyle(style === s.name ? "" : s.name)}>{s.name} {s.count}</Chip>
            ))}
          </div>
        )}

        {q.isError ? <p className="border border-border p-6 text-sm text-muted-foreground">{(q.error as Error).message}</p>
          : q.isLoading ? <p className="text-sm text-muted-foreground">Reading every studio…</p>
          : !items.length ? (
            <p className="border border-border p-8 text-sm text-muted-foreground">
              {q.data?.total ? "Nothing matches those filters." : "Nothing made yet. Whatever you make in any studio shows up here."}
            </p>
          ) : groups.map(([name, list]) => (
            <section key={name}>
              <h2 className="mb-3 text-sm font-semibold">
                {STUDIO_LABEL[name] ?? name} <span className="ml-1 font-normal text-muted-foreground">{list.length}</span>
              </h2>
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 2xl:grid-cols-6">
                {list.map((x) => (
                  <div key={`${x.studio}-${x.id}`} className="flex flex-col overflow-hidden border border-border bg-card transition hover:border-[rgba(200,255,58,0.5)]">
                    <Link href={x.href} className="block">
                      <div className="flex aspect-[3/4] items-center justify-center bg-muted">
                        {x.thumb ? /* eslint-disable-next-line @next/next/no-img-element */
                          <img src={x.thumb} alt="" loading="lazy" className="h-full w-full object-cover" />
                          : <Film className="h-8 w-8 text-muted-foreground" />}
                      </div>
                      <div className="p-3 pb-2">
                        <p className="line-clamp-2 text-sm font-semibold">{x.title}</p>
                        {(x.createdAt || x.updatedAt) && <p className="mt-1 text-xs text-muted-foreground" title={new Date((x.createdAt || x.updatedAt) as string).toLocaleString()}>{stamp((x.createdAt || x.updatedAt) as string)}</p>}
                        <div className="mt-2 flex flex-wrap items-center gap-1.5">
                          <Tag tone={STATE_TONE[x.state] ?? "muted"}>{STATE_LABEL[x.state] ?? x.state}</Tag>
                          {x.style && <Tag tone="accent">{x.style}</Tag>}
                          {x.stage && <Tag tone="muted">{x.stage}</Tag>}
                        </div>
                      </div>
                    </Link>
                    {x.video && <div className="mt-auto px-3 pb-3"><QueueVideo full url={x.video} title={x.title} /></div>}
                  </div>
                ))}
              </div>
            </section>
          ))}
      </div>
    </AppShell>
  );
}

/** "Today, 11:49 AM" / "Yesterday, 6:02 PM" / "Mon 24 Nov, 11:49 AM": when it was made. */
function stamp(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  const t = d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  const day = new Date(); day.setHours(0, 0, 0, 0);
  const diff = Math.round((day.getTime() - new Date(d).setHours(0, 0, 0, 0)) / 86400000);
  if (diff === 0) return `Today, ${t}`;
  if (diff === 1) return `Yesterday, ${t}`;
  return `${d.toLocaleDateString([], { weekday: "short", day: "numeric", month: "short", year: d.getFullYear() !== new Date().getFullYear() ? "numeric" : undefined })}, ${t}`;
}

function Chip({ on, onClick, children }: { on: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" onClick={onClick} aria-pressed={on}
      className={`whitespace-nowrap border px-3 py-1.5 text-xs transition ${on ?"border-[rgba(200,255,58,0.85)] bg-[rgba(200,255,58,0.12)] text-foreground" :"border-border text-muted-foreground hover:text-foreground"}`}>
      {children}
    </button>
  );
}
