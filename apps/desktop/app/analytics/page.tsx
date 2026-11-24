"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { money, usage, type Bucket } from "@/lib/usage";
import { Stat, TagButton } from "@/components/ui/Tag";

const SPANS: [number, string][] = [[7, "7 days"], [30, "30 days"], [90, "90 days"], [365, "A year"]];

/** Analytics: what the models actually cost, so a nine-dollar run is visible before the bill is. */
export default function Analytics() {
  const [days, setDays] = useState(30);
  const q = useQuery({ queryKey: ["usage", days], queryFn: () => usage.summary(days), refetchInterval: 20000, retry: false });
  const d = q.data;
  const peak = Math.max(1, ...(d?.by_day ?? []).map((x) => x.cost));

  return (
    <AppShell header={<span className="text-lg font-semibold">Analytics</span>}>
      <div className="w-full space-y-8 px-4 py-6 md:px-8 2xl:px-12">
        <div className="flex flex-wrap items-center gap-2">
          {SPANS.map(([n, l]) => (
            <TagButton key={n} on={days === n} onClick={() => setDays(n)}>{l}</TagButton>
          ))}
        </div>

        {q.isError ? <p className="border border-border p-6 text-sm text-muted-foreground">{(q.error as Error).message}</p>
          : q.isLoading ? <p className="text-sm text-muted-foreground">Reading the ledger…</p>
          : !d || !d.total.calls ? (
            <div className="border border-border p-8">
              <p className="text-sm">Nothing recorded yet.</p>
              <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
                Every picture, clip and writer call made from now on is written to the ledger. Runs from before this
                version are not in it — the ledger did not exist then. The two free skills, Motion Graphics and ASMR
                Cutting, will show here as calls that cost nothing, which is the point.
              </p>
            </div>
          ) : (
          <>
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              <Stat label={`Spent · last ${d.days} days`} value={money(d.total.cost)} hint="estimated from list prices" big />
              <Stat label="Model calls" value={String(d.total.calls)} hint={`${d.total.free} free`} />
              <Stat label="Not priced" value={String(d.total.unpriced)} tone={d.total.unpriced ? "warn" : "plain"}
                hint={d.total.unpriced ? "not in the total" : "all priced"} />
              <Stat label="Failed calls" value={String(d.total.failed)} tone={d.total.failed ? "bad" : "plain"}
                hint={d.total.failed ? "usually still billed" : "none"} />
            </div>

            {d.by_day.length > 1 && (
              <section className="border border-border p-5">
                <h2 className="mb-4 font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">By day</h2>
                <div className="flex h-36 items-end gap-1">
                  {d.by_day.map((x) => (
                    <div key={x.day} className="group relative flex-1" title={`${x.day}: ${money(x.cost)} over ${x.calls} calls`}>
                      <div className="w-full bg-[rgba(200,255,58,0.55)] transition group-hover:bg-[rgba(200,255,58,0.9)]"
                        style={{ height: `${Math.max(2, (x.cost / peak) * 100)}%` }} />
                    </div>
                  ))}
                </div>
                <div className="mt-2 flex justify-between text-[11px] text-muted-foreground">
                  <span>{d.by_day[0]?.day}</span><span>peak {money(peak)}</span><span>{d.by_day[d.by_day.length - 1]?.day}</span>
                </div>
              </section>
            )}

            <div className="grid gap-4 lg:grid-cols-3">
              <Table title="By model" rows={d.by_model} unitLabel />
              <Table title="By skill" rows={d.by_skill} />
              <Table title="By kind" rows={d.by_kind} />
            </div>

            <section className="border border-border p-5">
              <h2 className="mb-3 font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">Most recent calls</h2>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="text-muted-foreground"><tr>
                    <th className="pb-2 pr-4 font-medium">When</th><th className="pb-2 pr-4 font-medium">Kind</th>
                    <th className="pb-2 pr-4 font-medium">Model</th><th className="pb-2 pr-4 font-medium">Amount</th>
                    <th className="pb-2 pr-4 font-medium">Skill</th><th className="pb-2 font-medium">Cost</th>
                  </tr></thead>
                  <tbody>
                    {d.recent.map((r, i) => (
                      <tr key={i} className="border-t border-border/60">
                        <td className="py-1.5 pr-4 text-muted-foreground">{r.at.slice(5, 16).replace("T", " ")}</td>
                        <td className="py-1.5 pr-4">{r.kind}</td>
                        <td className="py-1.5 pr-4">{r.model}{!r.ok && <span className="ml-2 text-red-400">failed</span>}</td>
                        <td className="py-1.5 pr-4 text-muted-foreground"><span className="font-mono">{r.units} {r.unit}{r.units === 1 ? "" : "s"}</span></td>
                        <td className="py-1.5 pr-4 text-muted-foreground">{r.skill || "—"}</td>
                        <td className="py-1.5 font-mono tabular-nums">{r.priced ? money(r.cost) : <span className="text-muted-foreground">not priced</span>}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <p className="flex max-w-3xl gap-2 text-xs leading-relaxed text-muted-foreground">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{d.note}</span>
            </p>
          </>)}
      </div>
    </AppShell>
  );
}

function Table({ title, rows, unitLabel }: { title: string; rows: Bucket[]; unitLabel?: boolean }) {
  const top = Math.max(1, ...rows.map((r) => r.cost));
  return (
    <section className="border border-border p-5">
      <h2 className="mb-3 font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">{title}</h2>
      {!rows.length ? <p className="text-xs text-muted-foreground">Nothing yet.</p> : (
        <ul className="space-y-2.5">
          {rows.map((r) => (
            <li key={r.name}>
              <div className="flex items-baseline justify-between gap-3 text-xs">
                <span className="truncate" title={r.name}>{r.name}</span>
                <span className="shrink-0 font-mono tabular-nums">{money(r.cost)}</span>
              </div>
              <div className="mt-1 h-1 overflow-hidden bg-muted">
                <div className="h-full bg-[rgba(200,255,58,0.6)]" style={{ width: `${(r.cost / top) * 100}%` }} />
              </div>
              <p className="mt-1 text-[11px] text-muted-foreground">
                {r.calls} call{r.calls === 1 ? "" : "s"}{unitLabel && r.units ? ` · ${r.units} units` : ""}
                {r.unpriced ? ` · ${r.unpriced} not priced` : ""}{r.failed ? ` · ${r.failed} failed` : ""}
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
