"use client";
import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link2, Unplug } from "lucide-react";
import { autoclip, type SocialPlatform } from "@/lib/autoclip";
import { Card, Label, Note, btn, btnPrimary, field } from "@/components/autoclip/ui";

/** One platform: your own developer app (key and secret stay on this studio), then Connect, then the accounts it found. */
export function PlatformCard({ p }: { p: SocialPlatform }) {
  const qc = useQueryClient();
  const [origin, setOrigin] = useState("");
  const [key, setKey] = useState("");
  const [sec, setSec] = useState("");
  const [editing, setEditing] = useState(false);
  useEffect(() => setOrigin(window.location.origin), []);
  const refresh = () => qc.invalidateQueries({ queryKey: ["social"] });
  const save = useMutation({ mutationFn: () => autoclip.socialClient(p.id, key.trim(), sec.trim()), onSuccess: () => { refresh(); setKey(""); setSec(""); setEditing(false); } });
  const connect = useMutation({ mutationFn: () => autoclip.socialConnect(p.id, origin), onSuccess: (r) => { window.location.href = r.url; } });
  const drop = useMutation({ mutationFn: (id: string) => autoclip.socialDisconnect(id), onSuccess: refresh });
  const redirect = p.redirect || `${origin}/studio-api/autoclip/social/${p.id}/callback`;

  if (p.status === "soon") {
    return (
      <Card title={p.name} hint="Not built yet.">
        <p className="text-sm text-muted-foreground">{p.notes.join(" ")}</p>
      </Card>
    );
  }
  return (
    <Card title={p.name} hint={`Posts to: ${p.makes.join(", ")}.`}>
      {p.accounts.map((a) => (
        <div key={a.id} className="flex flex-wrap items-center justify-between gap-3 border border-border p-3">
          <div className="flex min-w-0 items-center gap-3">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            {a.thumb ? <img src={a.thumb} alt="" className="h-9 w-9 object-cover" /> : <div className="h-9 w-9 bg-muted" />}
            <div className="min-w-0"><div className="truncate font-medium">{a.title}</div>
              <div className="text-xs capitalize text-muted-foreground">{a.platform}{a.via ? ` · via ${a.via}` : ""}{a.subs != null ? ` · ${a.subs} followers` : ""}</div></div>
          </div>
          <div className="flex items-center gap-2">
            {a.needs_login && <span className="text-xs text-amber-500">Login expired: connect again</span>}
            <button className={btn} onClick={() => confirm(`Disconnect ${a.title}?`) && drop.mutate(a.id)}><Unplug className="h-4 w-4" />Disconnect</button>
          </div>
        </div>
      ))}
      {p.has_client && !editing ? (
        <div className="flex flex-wrap items-center gap-3">
          <button className={btnPrimary} disabled={!origin || connect.isPending} onClick={() => connect.mutate()}><Link2 className="h-4 w-4" />{p.accounts.length ? "Connect again or add more" : `Connect ${p.name}`}</button>
          <button className={btn} onClick={() => setEditing(true)}>Change app key</button>
        </div>
      ) : (
        <div className="space-y-4">
          <ol className="list-decimal space-y-1 pl-5 text-sm text-muted-foreground">
            {p.steps.map((s, i) => <li key={i}>{s}</li>)}
          </ol>
          <p className="text-sm">Redirect address to add in the developer app: <code className="break-all font-mono">{redirect}</code></p>
          <div className="grid gap-4 md:grid-cols-2">
            <Label text={p.id_label || "Key"}><input className={field} value={key} onChange={(e) => setKey(e.target.value)} autoComplete="off" /></Label>
            <Label text={p.secret_label || "Secret"}><input type="password" className={field} value={sec} onChange={(e) => setSec(e.target.value)} autoComplete="off" /></Label>
          </div>
          {save.isError && <Note tone="err">{(save.error as Error).message}</Note>}
          <div className="flex gap-3">
            <button className={btnPrimary} disabled={!key || !sec || save.isPending} onClick={() => save.mutate()}>Save</button>
            {editing && <button className={btn} onClick={() => setEditing(false)}>Cancel</button>}
          </div>
        </div>
      )}
      {p.notes.map((n, i) => <p key={i} className="text-xs text-muted-foreground">{n}</p>)}
      {connect.isError && <Note tone="err">{(connect.error as Error).message}</Note>}
    </Card>
  );
}
