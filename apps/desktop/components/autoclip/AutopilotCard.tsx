"use client";
import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { PauseCircle, PlayCircle } from "lucide-react";
import { autoclip, type Autopilot, type Overview, type Settings } from "@/lib/autoclip";
import { Card, Label, Note, Switch, btn, btnPrimary, field } from "./ui";

const CHAN = /UC[\w-]{20,24}/;

/** The setting that lets Auto Clip post without a person. Everything is off until you turn it on. */
export function AutopilotCard({ ov }: { ov: Overview }) {
  const qc = useQueryClient();
  const s = ov.settings;
  const [ap, setAp] = useState<Autopilot>(s.autopilot);
  const [rights, setRights] = useState(s.rights_ack);
  const [watch, setWatch] = useState(s.watch.map((w) => w.channel_id).join("\n"));
  useEffect(() => { setAp(s.autopilot); setRights(s.rights_ack); }, [s.autopilot, s.rights_ack]);
  const up = <K extends keyof Autopilot>(k: K, v: Autopilot[K]) => setAp((x) => ({ ...x, [k]: v }));
  const save = useMutation({
    mutationFn: () => {
      const ids = watch.split(/[\s,]+/).map((x) => x.match(CHAN)?.[0]).filter((x): x is string => !!x);
      const body: Partial<Settings> = { rights_ack: rights, autopilot: ap, watch: [...new Set(ids)].map((channel_id) => ({ channel_id, name: s.watch.find((w) => w.channel_id === channel_id)?.name })) };
      return autoclip.saveSettings(body);
    },
    onSuccess: (o) => qc.setQueryData(["autoclip"], o),
  });
  const pause = useMutation({ mutationFn: (p: boolean) => autoclip.pause(p), onSuccess: (o) => qc.setQueryData(["autoclip"], o) });
  const connected = ov.channels.length > 0;
  const live = s.autopilot.enabled && !s.autopilot.paused;
  const state = !s.autopilot.enabled ? "Off" : s.autopilot.paused ? "Paused" : !s.rights_ack ? "On, waiting for your rights confirmation" : !connected ? "On, waiting for a channel" : "Running";
  const st = ov.autopilot;
  return (
    <Card title="Autopilot" hint="Post and measure without a person pressing buttons. Everything here is off until you turn it on."
      right={<span className={`border px-2 py-1 text-xs ${live && s.rights_ack && connected ? "border-primary text-primary" : "border-border text-muted-foreground"}`}>{state}</span>}>
      {s.notice && <Note tone="warn">{s.notice}</Note>}
      <Switch on={rights} onChange={setRights} label="I own this content or have permission to clip and post it"
        hint="Required before anything is posted, by hand or by autopilot. Re-uploading other people's videos can get your channel struck." />
      <Switch on={ap.enabled} onChange={(v) => up("enabled", v)} label="Autopilot" hint="Posts approved clips on the schedule below, then tracks views and earnings." />
      <Switch on={!ap.review_first} onChange={(v) => up("review_first", !v)} label="Fully automatic (no review)"
        hint={ap.review_first ? "Off: you tick “Approved” on each clip first. Safest." : "On: new clips are approved and posted without anyone looking at them."} />
      <Switch on={ap.auto_make} onChange={(v) => up("auto_make", v)} label="Make clips from watched channels"
        hint="When a channel in the list below uploads, Auto Clip downloads it and cuts clips. Needs yt-dlp, and YouTube may block downloads." />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Label text="Posts per day"><input type="number" min={1} max={20} className={field} value={ap.per_day} onChange={(e) => up("per_day", +e.target.value)} /></Label>
        <Label text="Minutes between posts"><input type="number" min={10} max={1440} className={field} value={ap.min_gap_minutes} onChange={(e) => up("min_gap_minutes", +e.target.value)} /></Label>
        <Label text="Post from hour"><input type="number" min={0} max={23} className={field} value={ap.hours[0]} onChange={(e) => up("hours", [+e.target.value, ap.hours[1]])} /></Label>
        <Label text="…until hour"><input type="number" min={0} max={23} className={field} value={ap.hours[1]} onChange={(e) => up("hours", [ap.hours[0], +e.target.value])} /></Label>
        <Label text="Visibility when posted" hint="Private lets you check on YouTube first.">
          <select className={field} value={ap.privacy} onChange={(e) => up("privacy", e.target.value)}><option value="private">Private</option><option value="unlisted">Unlisted</option><option value="public">Public</option></select>
        </Label>
        <Label text="Channel to post to">
          <select className={field} value={ap.channel} onChange={(e) => up("channel", e.target.value)}>
            <option value="">First connected channel</option>{ov.channels.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
          </select>
        </Label>
        <Label text="Clips per watched video"><input type="number" min={1} max={10} className={field} value={ap.make_per_video} onChange={(e) => up("make_per_video", +e.target.value)} /></Label>
      </div>
      <Label text="Watch these channels (IDs starting UC, one per line)" hint="Only new uploads are used. The first look records what exists and makes nothing.">
        <textarea className={field + " h-24 py-2 font-mono"} value={watch} onChange={(e) => setWatch(e.target.value)} placeholder="UCxxxxxxxxxxxxxxxxxxxxxx" />
      </Label>
      {ap.enabled && !ap.review_first && <Note tone="warn">Fully automatic mode will publish clips nobody has looked at. Keep visibility on Private until you trust the results.</Note>}
      {save.isError && <Note tone="err">{(save.error as Error).message}</Note>}
      <div className="flex flex-wrap items-center gap-3">
        <button className={btnPrimary} disabled={save.isPending} onClick={() => save.mutate()}>{save.isPending ? "Saving…" : "Save autopilot settings"}</button>
        {s.autopilot.enabled && (
          <button className={btn} disabled={pause.isPending} onClick={() => pause.mutate(!s.autopilot.paused)}>
            {s.autopilot.paused ? <><PlayCircle className="h-4 w-4" />Resume</> : <><PauseCircle className="h-4 w-4" />Pause everything</>}
          </button>
        )}
        <span className="text-xs text-muted-foreground">{st.recent}/{st.per_day} posted in the last 24h · {st.waiting} waiting · {st.in_hours ? "inside" : "outside"} posting hours</span>
      </div>
    </Card>
  );
}
