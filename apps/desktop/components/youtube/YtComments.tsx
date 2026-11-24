"use client";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, MessageSquare, RefreshCw } from "lucide-react";
import { autoclip, type CommentRow, type CommentsView } from "@/lib/autoclip";
import { Card, Note, btn, btnPrimary } from "@/components/autoclip/ui";

const TABS: [string, string][] = [["new", "To answer"], ["spam", "Flagged"], ["answered", "Answered"], ["dismissed", "Dismissed"]];

function Row({ c, onView }: { c: CommentRow; onView: (v: CommentsView) => void }) {
  const [text, setText] = useState(c.draft?.text ?? "");
  const [err, setErr] = useState("");
  const run = useMutation({ mutationFn: (f: () => Promise<CommentsView>) => f(), onSuccess: (v) => { setErr(""); onView(v); }, onError: (e) => setErr((e as Error).message) });
  return (
    <li className="space-y-2 p-3 text-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span><span className="font-medium">{c.author}</span> <span className="text-xs text-muted-foreground">on “{c.video_title}” · {c.likes} likes</span></span>
        {c.why && <span className="text-xs text-amber-400">Flagged: {c.why}</span>}
        {c.request && !c.why && <span className="text-xs text-primary">Request: {c.request}</span>}
      </div>
      <p className="whitespace-pre-wrap break-words">{c.text}</p>
      {c.status === "new" && (
        <div className="space-y-2">
          <textarea className="min-h-[64px] w-full border border-border bg-transparent p-2 text-sm outline-none focus:border-primary" value={text} onChange={(e) => setText(e.target.value)} placeholder="Write a reply" aria-label="Reply" />
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" className={btnPrimary} disabled={run.isPending || !text.trim()} onClick={() => run.mutate(() => autoclip.commentReply(c.id, text))}>Post reply</button>
            <button type="button" className={btn} disabled={run.isPending} onClick={() => run.mutate(async () => { const v = await autoclip.commentDraft(c.id); setText(v.items.find((x) => x.id === c.id)?.draft?.text ?? text); return v; })}>New draft</button>
            <button type="button" className={btn} disabled={run.isPending} onClick={() => run.mutate(() => autoclip.commentAct(c.id, "dismiss"))}>Dismiss</button>
            {c.draft && <span className="text-xs text-muted-foreground">Draft by {c.draft.by === "ai" ? "your AI helper" : "a template"}. Nothing is sent until you press Post.</span>}
          </div>
        </div>
      )}
      {c.status === "spam" && (
        <div className="flex flex-wrap gap-2">
          <button type="button" className={btn} disabled={run.isPending} onClick={() => run.mutate(() => autoclip.commentAct(c.id, "hold"))}>Hold on YouTube</button>
          <button type="button" className={btn} disabled={run.isPending} onClick={() => run.mutate(() => autoclip.commentAct(c.id, "release"))}>Not spam</button>
          <button type="button" className={btn} disabled={run.isPending} onClick={() => run.mutate(() => autoclip.commentAct(c.id, "dismiss"))}>Dismiss</button>
        </div>
      )}
      {c.status === "answered" && c.replied && <p className="text-xs text-muted-foreground">You replied: {c.replied}</p>}
      {err && <Note tone="err">{err}</Note>}
    </li>
  );
}

/** Comments on your posted clips: new ones to answer (with drafts you approve), spam set aside, and what viewers keep asking for. */
export function YtComments() {
  const qc = useQueryClient();
  const [tab, setTab] = useState("new");
  const q = useQuery({ queryKey: ["autoclip", "comments"], queryFn: () => autoclip.comments(), retry: false });
  const set = (v: CommentsView) => qc.setQueryData(["autoclip", "comments"], v);
  const sync = useMutation({ mutationFn: () => autoclip.commentsSync(), onSuccess: set });
  const d = q.data;
  const rows = (d?.items ?? []).filter((c) => c.status === tab || (tab === "dismissed" && c.status === "held"));
  const reconnect = sync.data?.sync?.needs_reconnect ?? [];
  return (
    <Card title="Comments" hint="Read, answer and clean up comments on your clips. Replies are drafts until you post them." right={
      <button type="button" className={btn} disabled={sync.isPending} onClick={() => sync.mutate()}>{sync.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}Check comments</button>}>
      {q.isError && <Note tone="err">{(q.error as Error).message}</Note>}
      {sync.isError && <Note tone="err">{(sync.error as Error).message}</Note>}
      {reconnect.length > 0 && <Note tone="warn">A channel was connected before comments were allowed. Disconnect it and connect it again (YouTube tab, top), then check again.</Note>}
      {d && d.ideas.length > 0 && (
        <div className="border border-border p-3">
          <div className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">What viewers keep asking for</div>
          <ul className="space-y-1 text-sm">{d.ideas.map((i) => <li key={i.idea}><span className="font-medium">{i.idea}</span> <span className="text-xs text-muted-foreground">· asked {i.count}×{i.likes ? `, ${i.likes} likes` : ""} · “{i.examples[0]}”</span></li>)}</ul>
        </div>
      )}
      {d && (
        <>
          <div role="tablist" className="flex flex-wrap gap-2">
            {TABS.map(([k, l]) => <button key={k} type="button" role="tab" aria-selected={tab === k} onClick={() => setTab(k)} className={`border px-3 py-1.5 text-sm ${tab === k ? "border-[rgba(200,255,58,0.85)] bg-[rgba(200,255,58,0.12)]" : "border-border text-muted-foreground"}`}>{l} {d.counts[k] ? `(${d.counts[k]})` : ""}</button>)}
          </div>
          {rows.length === 0 ? <p className="flex items-center gap-2 text-sm text-muted-foreground"><MessageSquare className="h-4 w-4" />{d.last_sync ? "Nothing here." : "Press “Check comments” to read the comments on your latest clips."}</p> : <ul className="divide-y divide-border border border-border">{rows.map((c) => <Row key={c.id + c.status} c={c} onView={set} />)}</ul>}
          <p className="text-xs text-muted-foreground">Spam is flagged by plain rules (links, “sub4sub”, contact numbers, money pitches, shouting, copy-pasted text). Checked automatically every few hours once you have used this once.</p>
        </>
      )}
    </Card>
  );
}
