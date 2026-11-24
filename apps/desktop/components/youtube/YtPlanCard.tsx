"use client";
import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { autoclip, type YtTab } from "@/lib/autoclip";
import { Card, Label, Note, btnPrimary, field } from "@/components/autoclip/ui";

/** The auto-time settings: how many a day, from when to when, how far apart. "Automatic times" in the next card uses these. */
export function YtPlanCard({ tab }: { tab: YtTab }) {
  const qc = useQueryClient();
  const p = tab.plan;
  const [f, setF] = useState({ per_day: p.per_day, gap: p.min_gap_minutes, a: p.hours[0], b: p.hours[1], privacy: p.privacy });
  useEffect(() => setF({ per_day: p.per_day, gap: p.min_gap_minutes, a: p.hours[0], b: p.hours[1], privacy: p.privacy }), [p.per_day, p.min_gap_minutes, p.hours, p.privacy]);
  const save = useMutation({ mutationFn: () => autoclip.ytPlan({ per_day: f.per_day, min_gap_minutes: f.gap, hours: [f.a, f.b], privacy: f.privacy }), onSuccess: (t) => qc.setQueryData(["yt"], t) });
  const dirty = f.per_day !== p.per_day || f.gap !== p.min_gap_minutes || f.a !== p.hours[0] || f.b !== p.hours[1] || f.privacy !== p.privacy;
  const hours = Array.from({ length: 25 }, (_, i) => i);
  const fmt = (h: number) => `${String(h % 24).padStart(2, "0")}:00`;
  return (
    <Card title="Default posting times" hint="Used by every channel that has no times of its own (set them in the channel cards above). Times are in your clock.">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <Label text="Posts per day, per channel"><input type="number" min={1} max={20} className={field} value={f.per_day} onChange={(e) => setF({ ...f, per_day: +e.target.value })} /></Label>
        <Label text="Not closer than (minutes)"><input type="number" min={10} max={1440} step={10} className={field} value={f.gap} onChange={(e) => setF({ ...f, gap: +e.target.value })} /></Label>
        <Label text="From"><select className={field} value={f.a} onChange={(e) => setF({ ...f, a: +e.target.value })}>{hours.slice(0, 24).map((h) => <option key={h} value={h}>{fmt(h)}</option>)}</select></Label>
        <Label text="To"><select className={field} value={f.b} onChange={(e) => setF({ ...f, b: +e.target.value })}>{hours.map((h) => <option key={h} value={h}>{h === 24 ? "24:00" : fmt(h)}</option>)}</select></Label>
        <Label text="Default visibility"><select className={field} value={f.privacy} onChange={(e) => setF({ ...f, privacy: e.target.value })}><option value="private">Private</option><option value="unlisted">Unlisted</option><option value="public">Public</option></select></Label>
      </div>
      <p className="text-xs text-muted-foreground">Example: {f.per_day} a day between {fmt(f.a)} and {fmt(f.b)} puts one post in the middle of each {f.per_day === 1 ? "window" : `${Math.round(((f.b > f.a ? f.b : f.b + 24) - f.a) / f.per_day * 10) / 10}-hour slice`}. Private is safest while you test.</p>
      {save.isError && <Note tone="err">{(save.error as Error).message}</Note>}
      <button type="button" className={btnPrimary} disabled={!dirty || save.isPending} onClick={() => save.mutate()}>{save.isPending ? "Saving…" : "Save times"}</button>
    </Card>
  );
}
