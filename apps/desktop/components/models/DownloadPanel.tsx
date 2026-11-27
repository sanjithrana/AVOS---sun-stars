"use client";

// Models page → Download: pick where (this PC or a GPU worker), the version (fp8 / bf16 …), extras and the folder,
// then AVOS fetches the model's ComfyUI files from Hugging Face into <folder>/<diffusion_models|text_encoders|vae…>.
import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowUp, Check, CheckCircle2, Download, Folder, FolderOpen, FolderPlus, HardDrive, Loader2, Server, X,
} from "lucide-react";

import { downloadsApi, gpuApi } from "@/lib/api";
import type { CatalogModel, DownloadOptions, FolderListing } from "@/types";

export const gb = (b: number | null | undefined) =>
  b == null ? "—" : b >= 1e9 ? `${(b / 1e9).toFixed(b >= 1e10 ? 0 : 1)} GB` : `${Math.max(1, Math.round(b / 1e6))} MB`;

const input =
  "w-full rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-amber-500/50 focus:outline-none focus:ring-2 focus:ring-amber-500/30";

export function DownloadPanel({ model, onClose, onStarted }: { model: CatalogModel; onClose: () => void; onStarted: () => void }) {
  const qc = useQueryClient();
  const [where, setWhere] = useState("local");
  const [path, setPath] = useState<string | null>(null);   // chosen folder (null = that place's default)
  const [variantPick, setVariant] = useState<string | null>(null);
  const [extrasPick, setExtras] = useState<Set<string> | null>(null);
  const [newFolder, setNewFolder] = useState("");
  const [busy, setBusy] = useState(false), [err, setErr] = useState("");

  const workersQ = useQuery({ queryKey: ["gpu-workers-lite"], queryFn: () => gpuApi.workers(), retry: false, staleTime: 10_000 });
  const optsQ = useQuery({
    queryKey: ["download-options", model.id, where, path],
    queryFn: () => downloadsApi.options(model.id, where, path),
    retry: false,
  });
  const folderQ = useQuery({
    queryKey: ["download-browse", where, path],
    queryFn: () => downloadsApi.browse(where, path),
    retry: false,
  });
  const o: DownloadOptions | undefined = optsQ.data;
  const folder: FolderListing | undefined = folderQ.data;

  // until you pick: the recommended version and the recommended extras
  const variant = variantPick ?? o?.recommended ?? null;
  const extras = useMemo(() => extrasPick ?? new Set((o?.optional ?? []).filter((f) => f.recommended).map((f) => f.id)), [extrasPick, o]);

  const chosen = o?.variants.find((v) => v.key === variant);
  const toGet = useMemo(() => {
    if (!o || !chosen) return 0;
    const fs = [...chosen.files, ...o.shared, ...o.optional.filter((f) => extras?.has(f.id))];
    const seen = new Set<string>();
    return fs.reduce((a, f) => (seen.has(f.id) || f.present ? a : (seen.add(f.id), a + f.size)), 0);
  }, [o, chosen, extras]);
  const dest = path ?? folder?.path ?? o?.dest ?? null;
  const noSpace = folder?.free != null && toGet > folder.free;

  const start = async () => {
    if (!o || !variant) return;
    setBusy(true); setErr("");
    try {
      await downloadsApi.start({ model: model.id, variant, extras: [...(extras ?? [])], where, path: dest });
      await qc.invalidateQueries({ queryKey: ["downloads"] });
      onStarted();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const makeFolder = async () => {
    if (!folder?.path || !newFolder.trim()) return;
    try {
      const r = await downloadsApi.mkdir(where, folder.path, newFolder.trim());
      setNewFolder(""); setPath(r.path);
    } catch (e) {
      setErr((e as Error).message);
    }
  };

  const places = [{ id: "local", name: "This PC", online: true, sub: "where AVOS runs" },
    ...(workersQ.data ?? []).filter((w) => w.enabled).map((w) => ({ id: w.id, name: w.name, online: w.online, sub: w.gpu?.name ?? (w.online ? "GPU worker" : "offline") }))];

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-0 sm:items-center sm:p-4" role="dialog" aria-modal="true" aria-label={`Download ${model.name}`} data-testid="download-panel">
      <div className="flex max-h-[92vh] w-full max-w-3xl flex-col overflow-hidden rounded-t-2xl border border-border bg-card shadow-2xl sm:rounded-xl">
        <div className="flex items-start justify-between gap-3 border-b border-border p-5">
          <div className="min-w-0">
            <h2 className="flex items-center gap-2 text-lg font-semibold text-foreground"><Download className="h-5 w-5 text-amber-500" />Download {model.name}</h2>
            <p className="mt-1 text-xs text-muted-foreground">
              The files ComfyUI needs{o?.template ? ` (official template ${o.template})` : ""}, from Hugging Face, into your models folder.
            </p>
          </div>
          <button className="rounded-lg p-1 text-muted-foreground hover:bg-muted hover:text-foreground" onClick={onClose} aria-label="Close"><X className="h-5 w-5" /></button>
        </div>

        <div className="space-y-5 overflow-y-auto p-5">
          <section>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Where</h3>
            <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Where to download">
              {places.map((p) => (
                <button key={p.id} role="radio" aria-checked={where === p.id} disabled={!p.online} onClick={() => { setWhere(p.id); setPath(null); }} data-testid={`where-${p.id}`}
                  className={`flex items-center gap-2 rounded-xl border px-3 py-2 text-left text-sm disabled:opacity-50 ${where === p.id ? "border-amber-500/60 bg-amber-500/10" : "border-border hover:border-amber-500/30"}`}>
                  {p.id === "local" ? <HardDrive className="h-4 w-4 text-amber-500" /> : <Server className="h-4 w-4 text-amber-500" />}
                  <span><span className="block font-medium text-foreground">{p.name}</span><span className="block text-xs text-muted-foreground">{p.sub}</span></span>
                </button>
              ))}
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              {where === "local"
                ? "Your laptop can\u2019t run these models; download here to keep a copy or to copy them to a GPU machine. To run them, download onto a GPU worker."
                : "Straight onto the GPU machine, into its ComfyUI models folder: ready to run there."}
            </p>
          </section>

          {optsQ.isLoading && <p className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />Checking what&apos;s there…</p>}
          {optsQ.error && <p role="alert" className="text-sm text-red-400">{(optsQ.error as Error).message}</p>}

          {o && (
            <>
              <section>
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Version</h3>
                <div className="space-y-2" role="radiogroup" aria-label="Version">
                  {o.variants.map((v) => (
                    <label key={v.key} data-testid={`variant-${v.key}`}
                      className={`flex cursor-pointer items-start gap-3 rounded-xl border p-3 ${variant === v.key ? "border-amber-500/60 bg-amber-500/5" : "border-border hover:border-amber-500/30"}`}>
                      <input type="radio" name="variant" className="mt-1 accent-amber-500" checked={variant === v.key} onChange={() => setVariant(v.key)} />
                      <span className="min-w-0 flex-1">
                        <span className="flex flex-wrap items-center gap-2 text-sm font-medium text-foreground">
                          {v.label}
                          {v.key === o.recommended && <span className="rounded-md bg-amber-500/15 px-2 py-0.5 text-[11px] text-amber-700 dark:text-amber-300">Recommended for your GPU</span>}
                          {v.complete && <span className="flex items-center gap-1 text-[11px] text-emerald-600 dark:text-emerald-400"><CheckCircle2 className="h-3.5 w-3.5" />Already downloaded here</span>}
                        </span>
                        <span className="block text-xs text-muted-foreground">
                          {gb(v.size)} model{v.files.length > 1 ? ` (${v.files.length} files)` : ""} · {gb(v.total)} with text encoder, VAE and LoRAs
                        </span>
                      </span>
                    </label>
                  ))}
                </div>
                <details className="mt-2 text-xs text-muted-foreground">
                  <summary className="cursor-pointer">Files included with every version ({o.shared.length})</summary>
                  <ul className="mt-1 space-y-0.5">
                    {o.shared.map((f) => <li key={f.id} className="flex justify-between gap-2"><span className="truncate">{f.present ? "✓ " : ""}{f.folder}/{f.name}</span><span>{gb(f.size)}</span></li>)}
                  </ul>
                </details>
              </section>

              {o.optional.length > 0 && (
                <section>
                  <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Extras</h3>
                  {o.optional.map((f) => (
                    <label key={f.id} className="flex items-center gap-2 py-1 text-sm text-foreground">
                      <input type="checkbox" className="accent-amber-500" checked={extras?.has(f.id) ?? false}
                        onChange={(e) => setExtras((s) => { const n = new Set(s ?? []); if (e.target.checked) n.add(f.id); else n.delete(f.id); return n; })} />
                      <span className="flex-1">{f.label ?? f.name}{f.present ? " ✓" : ""}</span>
                      <span className="text-xs text-muted-foreground">{gb(f.size)}</span>
                    </label>
                  ))}
                </section>
              )}
            </>
          )}

          <section>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Folder</h3>
            {folderQ.error && <p className="mb-2 text-xs text-red-400">{(folderQ.error as Error).message}</p>}
            <div className="flex gap-2">
              <button className="rounded-xl border border-border px-2 text-muted-foreground hover:text-foreground disabled:opacity-40" disabled={!folder?.parent} onClick={() => setPath(folder?.parent ?? null)} aria-label="Up one folder"><ArrowUp className="h-4 w-4" /></button>
              <input className={`${input} font-mono text-xs`} value={dest ?? ""} onChange={(e) => setPath(e.target.value)} aria-label="Download folder" data-testid="download-path" spellCheck={false} />
            </div>
            <div className="mt-2 max-h-40 overflow-y-auto rounded-xl border border-border" data-testid="folder-list">
              {(folder?.dirs ?? []).length === 0 && <p className="px-3 py-2 text-xs text-muted-foreground">No sub-folders.</p>}
              {(folder?.dirs ?? []).map((d) => (
                <button key={d.path} onClick={() => setPath(d.path)} className="flex w-full items-center gap-2 border-t border-border px-3 py-1.5 text-left text-sm text-foreground first:border-t-0 hover:bg-muted">
                  <Folder className="h-4 w-4 text-amber-500" />{d.name}
                </button>
              ))}
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <input className={`${input} max-w-[220px]`} placeholder="New folder name" value={newFolder} onChange={(e) => setNewFolder(e.target.value)} aria-label="New folder name" />
              <button className="inline-flex items-center gap-1.5 rounded-xl border border-border px-3 py-2 text-sm text-foreground hover:bg-muted disabled:opacity-50" disabled={!newFolder.trim() || !folder?.path} onClick={makeFolder}><FolderPlus className="h-4 w-4" />Create</button>
              <span className="text-xs text-muted-foreground">
                {folder?.free != null && <>Free: {gb(folder.free)}. </>}
                {folder?.looks_like_models ? <span className="text-emerald-600 dark:text-emerald-400">Looks like a ComfyUI models folder.</span> : "Pick your ComfyUI models folder (the one with diffusion_models, vae…)."}
              </span>
            </div>
            <p className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground"><FolderOpen className="h-3.5 w-3.5" />Files go into {dest ?? "…"}/diffusion_models, /text_encoders, /vae, /loras… (ComfyUI&apos;s layout).</p>
          </section>
          {err && <p role="alert" className="text-sm text-red-400" data-testid="download-error">{err}</p>}
        </div>

        <div className="flex flex-wrap items-center gap-3 border-t border-border p-4">
          <span className="text-sm text-foreground" data-testid="download-size">
            {chosen ? (toGet === 0 ? <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400"><Check className="h-4 w-4" />Everything is already here</span> : <>To download: <b>{gb(toGet)}</b></>) : null}
            {noSpace && <span className="ml-2 text-red-400">Not enough free space</span>}
          </span>
          <span className="flex-1" />
          <button className="rounded-xl px-3 py-2 text-sm text-muted-foreground hover:bg-muted" onClick={onClose}>Cancel</button>
          <button
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary hover:bg-[#dcff7a] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
            disabled={busy || !chosen || !dest || noSpace || toGet === 0} onClick={start} data-testid="download-start">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}Download
          </button>
        </div>
      </div>
    </div>
  );
}
