"use client";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link2, Unplug } from "lucide-react";
import { autoclip, type Overview } from "@/lib/autoclip";
import { Card, Label, Note, btn, btnPrimary, field } from "./ui";

/** Connect your own YouTube channel through your own Google Cloud client. Tokens stay on the studio, never in the page. */
export function YouTubeCard({ ov, flash }: { ov: Overview; flash: { connected?: string; error?: string } }) {
  const qc = useQueryClient();
  const [origin, setOrigin] = useState("");
  const [cid, setCid] = useState("");
  const [sec, setSec] = useState("");
  const [editing, setEditing] = useState(false);
  useEffect(() => setOrigin(window.location.origin), []);
  const redirect = useQuery({ queryKey: ["autoclip", "redirect", origin], queryFn: () => autoclip.redirect(origin), enabled: !!origin, retry: false });
  const refresh = (o: Overview) => qc.setQueryData(["autoclip"], o);
  const save = useMutation({ mutationFn: () => autoclip.setClient(cid.trim(), sec.trim()), onSuccess: (o) => { refresh(o); setCid(""); setSec(""); setEditing(false); } });
  const connect = useMutation({ mutationFn: () => autoclip.connect(origin), onSuccess: (r) => { window.location.href = r.url; } });
  const drop = useMutation({ mutationFn: (id: string) => autoclip.disconnect(id), onSuccess: () => qc.invalidateQueries({ queryKey: ["autoclip"] }) });
  const has = ov.google.has_client;
  return (
    <Card title="YouTube" hint="Connect your channel so clips can be posted and measured.">
      {flash.connected && <Note>Connected. Next, open Autopilot below and choose how much it may do on its own.</Note>}
      {flash.error && <Note tone="err">{flash.error}</Note>}
      {ov.channels.map((c) => (
        <div key={c.id} className="flex flex-wrap items-center justify-between gap-3 border border-border p-3">
          <div className="flex min-w-0 items-center gap-3">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            {c.thumb && <img src={c.thumb} alt="" className="h-9 w-9 object-cover" />}
            <div className="min-w-0"><div className="truncate font-medium">{c.title}</div>
              <div className="text-xs text-muted-foreground">{c.subs != null ? `${c.subs} subscribers · ` : ""}{c.revenue_scope ? "earnings access granted" : "no earnings access"}</div></div>
          </div>
          <div className="flex items-center gap-2">
            {c.needs_login && <span className="text-xs text-amber-500">Login expired: connect again</span>}
            <button className={btn} onClick={() => confirm(`Disconnect ${c.title}?`) && drop.mutate(c.id)}><Unplug className="h-4 w-4" />Disconnect</button>
          </div>
        </div>
      ))}
      {has && !editing ? (
        <div className="flex flex-wrap items-center gap-3">
          <button className={btnPrimary} disabled={!origin || connect.isPending} onClick={() => connect.mutate()}><Link2 className="h-4 w-4" />{ov.channels.length ? "Connect another channel" : "Connect YouTube"}</button>
          <button className={btn} onClick={() => setEditing(true)}>Change Google client</button>
        </div>
      ) : (
        <div className="space-y-4">
          <ol className="list-decimal space-y-1 pl-5 text-sm text-muted-foreground">
            <li>In Google Cloud Console, create a project and enable <b>YouTube Data API v3</b> and <b>YouTube Analytics API</b>.</li>
            <li>Set up the OAuth consent screen and add yourself as a user. Publish it (“In production”); in Testing mode Google logins can expire after a few days.</li>
            <li>Create credentials: <b>OAuth client ID</b>, type <b>Web application</b>.</li>
            <li>Add this as an Authorised redirect URI: <code className="break-all font-mono text-foreground">{redirect.data?.redirect ?? `${origin}/studio-api/autoclip/youtube/callback`}</code></li>
            <li>Paste the client ID and secret here. They are stored on this studio only.</li>
          </ol>
          <div className="grid gap-4 md:grid-cols-2">
            <Label text="Client ID"><input className={field} value={cid} onChange={(e) => setCid(e.target.value)} placeholder="….apps.googleusercontent.com" autoComplete="off" /></Label>
            <Label text="Client secret"><input type="password" className={field} value={sec} onChange={(e) => setSec(e.target.value)} autoComplete="off" /></Label>
          </div>
          {save.isError && <Note tone="err">{(save.error as Error).message}</Note>}
          <div className="flex gap-3">
            <button className={btnPrimary} disabled={!cid || !sec || save.isPending} onClick={() => save.mutate()}>Save</button>
            {editing && <button className={btn} onClick={() => setEditing(false)}>Cancel</button>}
          </div>
        </div>
      )}
      {connect.isError && <Note tone="err">{(connect.error as Error).message}</Note>}
    </Card>
  );
}
