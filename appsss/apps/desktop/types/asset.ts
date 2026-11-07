export type AssetType =
  | "image"
  | "video"
  | "audio"
  | "3d_model"
  | "control_map"
  | "script"
  | "world_state";

export interface AssetMetadata {
  width?: number;
  height?: number;
  duration?: number;
  fps?: number;
  format?: string;
  prompt?: string;
  seed?: number;
  file_size_bytes?: number;
}

export interface Asset {
  asset_id: string;
  project_id: string;
  type: AssetType;
  url: string;
  metadata: AssetMetadata;
  tags: string[];
  embedding_id?: string;
  created_at: string;
}