import { api } from "./core";
import type { DownloadJob, DownloadOptions, FolderListing } from "@/types";

const q = (o: Record<string, string | undefined | null>) => {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(o)) if (v) p.set(k, v);
  const s = p.toString();
  return s ? `?${s}` : "";
};

/** Model downloads from Hugging Face to this PC or a GPU worker (api/src/routes/downloads.py). */
export const downloadsApi = {
  options: (model: string, where = "local", path?: string | null) =>
    api.get<DownloadOptions>(`/downloads/models/${encodeURIComponent(model)}${q({ where, path })}`),
  browse: (where = "local", path?: string | null) => api.get<FolderListing>(`/downloads/browse${q({ where, path })}`),
  mkdir: (where: string, path: string, name: string) => api.post<{ path: string }>("/downloads/mkdir", { where, path, name }),
  start: (body: { model: string; variant: string; extras: string[]; where: string; path: string | null }) =>
    api.post<DownloadJob>("/downloads", body),
  list: () => api.get<DownloadJob[]>("/downloads"),
  cancel: (where: string, id: string) => api.delete<{ ok: boolean }>(`/downloads/${encodeURIComponent(where)}/${encodeURIComponent(id)}`),
};
