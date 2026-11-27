"use client";
import { ExternalLink } from "lucide-react";
import type { Overview } from "@/lib/autoclip";
import { Card } from "./ui";

/** The GTA 6 Clip Kit guide: what the preset does, the seven-day plan, the rules that keep clips up, and the links to the kit's own tool. */
export function Gta6Kit({ ov }: { ov: Overview }) {
  const p = (ov.presets ?? []).find((x) => x.id === "gta6");
  if (!p) return null;
  return (
    <Card title="GTA 6 Clip Kit" hint="One long stream in, up to 15 vertical clips out, with a hook line and the search words in the title.">
      <p className="text-sm text-muted-foreground">Pick <b className="text-foreground">{p.name}</b> under “What kind of video” in Make clips. {p.about}</p>
      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <h3 className="display text-sm">Your first 7 days</h3>
          <ol className="mt-2 space-y-2 text-sm">{p.plan.map(([d, t]) => <li key={d} className="grid grid-cols-[68px_1fr] gap-2"><b className="text-signal">{d}</b><span className="text-muted-foreground">{t}</span></li>)}</ol>
        </div>
        <div>
          <h3 className="display text-sm">Clip the smart way</h3>
          <ul className="mt-2 list-disc space-y-2 pl-5 text-sm text-muted-foreground">{p.rules.map((r) => <li key={r}>{r}</li>)}</ul>
        </div>
      </div>
      <div>
        <h3 className="display text-sm">The kit&apos;s own tool (optional)</h3>
        <p className="mt-1 text-xs text-muted-foreground">AVOS does the same job here. OpenShorts is what the kit recommends if you want a separate app with face tracking and 30+ language dubbing.</p>
        <ul className="mt-2 flex flex-wrap gap-2 text-xs">{p.links.map((l) => <li key={l.url}><a className="inline-flex items-center gap-1 border border-border px-3 py-1.5 hover:border-signal/60" href={l.url} target="_blank" rel="noreferrer">{l.label}<ExternalLink className="h-3 w-3" /></a></li>)}</ul>
      </div>
      <p className="text-[11px] text-muted-foreground">{p.credit} Clip only streams you own or have permission to use.</p>
    </Card>
  );
}
