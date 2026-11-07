// Mirrors /api/v1/downloads (api/src/routes/downloads.py) and agentic_core/model_fabric/downloads.py.

export interface ModelFile {
  id: string;
  repo: string;
  path: string;
  folder: string;
  name: string;
  size: number;
  label?: string | null;
  recommended?: boolean;
  url: string;
  present?: boolean;
}

export interface DownloadVariant {
  key: string;
  label: string;
  files: ModelFile[];
  size: number;
  total: number;
  default: boolean;
  complete?: boolean;
}

export interface DownloadOptions {
  model: string;
  name: string;
  verified: boolean;
  template: string | null;
  notes: string | null;
  variants: DownloadVariant[];
  shared: ModelFile[];
  optional: ModelFile[];
  recommended: string;
  where: string;
  dest: string | null;
}

export interface FolderListing {
  path: string | null;
  parent: string | null;
  dirs: { name: string; path: string }[];
  roots: string[];
  free: number | null;
  writable: boolean;
  looks_like_models?: boolean;
  default?: string;
}

export interface DownloadJob {
  id: string;
  label: string;
  model: string | null;
  variant: string | null;
  dest: string;
  status: "queued" | "running" | "done" | "error" | "cancelled" | string;
  error: string | null;
  total: number;
  done: number;
  progress: number;
  speed: number;
  eta: number | null;
  where: string;
  where_name?: string;
  created_at: number;
  files: { name: string; folder: string; size: number | null; done: number; status: string; error: string | null }[];
}
