"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FlaskConical } from "lucide-react";
import { autoclip } from "@/lib/autoclip";
import { Card, Note, Switch } from "@/components/autoclip/ui";

/** Title tests: post with title A, switch to B after a window, keep the better one (see experiments.py for exactly how and why it is cautious). */
export function YtTests() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["autoclip", "experiments"], queryFn: () => autoclip.experiments(), retry: false });
  const save = useMutation({
    mutationFn: (b: { enabled?: boolean; window_hours?: number; thumbnails?: boolean }) => autoclip.saveSettings({ experiments: { ...(q.data?.settings ?? { enabled: false, window_hours: 24, thumbnails: false }), ...b } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["autoclip", "experiments"] }),
  });
  const s = q.data?.settings;
  return (
    <Card title="Title tests" hint="Try a second title on each new clip and keep whichever works better.">
      {q.isError && <Note tone="err">{(q.error as Error).message}</Note>}
      {s && (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <Switch on={s.enabled} onChange={(v) => save.mutate({ enabled: v })} label="Test titles on new clips" hint="Needs an AI helper to write the second title" />
            <label className="block text-sm">Each title runs for
              <select className="mt-1 h-10 w-full border border-border bg-transparent px-3 text-sm" value={s.window_hours} onChange={(e) => save.mutate({ window_hours: +e.target.value })} aria-label="Hours per title">
                {[12, 24, 48, 72].map((h) => <option key={h} value={h}>{h} hours</option>)}
              </select>
            </label>
            <Switch on={s.thumbnails} onChange={(v) => save.mutate({ thumbnails: v })} label="Also test covers" hint="YouTube often ignores custom covers on Shorts" />
          </div>
          <p className="text-xs text-muted-foreground">
            How it works: a clip is posted with title A. After the window it switches to B for the same time, then the views per hour are compared. B is kept only if it is clearly better (95% sure, at least 20% more views per hour, at least 100 views). Otherwise A is put back.
            YouTube&apos;s API gives views but not impressions or click-through, and B runs later when views naturally fade, so a win for B is meaningful while &quot;no clear winner&quot; may just be timing.
          </p>
        </>
      )}
      {q.data && q.data.n === 0 && <p className="text-sm text-muted-foreground">No finished tests yet. A test takes two windows after posting.</p>}
      {q.data && q.data.n > 0 && (
        <div className="space-y-2">
          <p className="flex items-center gap-2 text-sm"><FlaskConical className="h-4 w-4" />{q.data.n} finished · the new title won {q.data.wins_b} time{q.data.wins_b === 1 ? "" : "s"}</p>
          {q.data.tips.map((t) => <p key={t} className="text-sm text-primary">{t}</p>)}
          <ul className="divide-y divide-border border border-border text-sm">
            {q.data.tests.map((t) => (
              <li key={`${t.jid}-${t.n}`} className="p-3">
                <div className="grid gap-1 sm:grid-cols-2"><span><span className="text-xs text-muted-foreground">A </span>{t.a}</span><span><span className="text-xs text-muted-foreground">B </span>{t.b}</span></div>
                <div className="mt-1 text-xs text-muted-foreground">Kept {t.kept}: {t.note}</div>
              </li>))}
          </ul>
        </div>
      )}
    </Card>
  );
}
