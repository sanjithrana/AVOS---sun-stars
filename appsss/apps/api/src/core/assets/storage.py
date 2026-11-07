"""Where asset bytes live.

- LocalAssetStorage: the assets folder (ASSETS_STORAGE_PATH, the solunex_assets volume). Default.
- S3AssetStorage (ASSETS_STORAGE=s3): S3 / MinIO is the store of record; the local folder is a write-through cache,
  so reads and file responses stay fast. storage_path is s3://<bucket>/<key> for these assets. Set S3_ENDPOINT,
  S3_BUCKET, S3_ACCESS_KEY, S3_SECRET_KEY (and S3_REGION) — docker compose's optional `object-store` service
  (SeaweedFS, `--profile storage`) provides one; MinIO, AWS S3 or Cloudflare R2 work the same.

Old rows with local paths keep working after switching to S3 (both are readable).
"""
import os
from pathlib import Path

from src.config.settings import settings

CONTENT_TYPES = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp", "mp4": "video/mp4",
                 "webm": "video/webm", "wav": "audio/wav", "mp3": "audio/mpeg", "json": "application/json"}


class LocalAssetStorage:
    """
    Local filesystem asset backend (per AVOS-07 §5's "local filesystem
    backend for now").
    """

    def __init__(self, base_dir: str | None = None) -> None:
        self.base_dir = Path(base_dir or settings.assets_storage_path)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, content_hash: str, ext: str, data: bytes) -> str:
        path = self.base_dir / f"{content_hash}.{ext}"
        path.write_bytes(data)
        return str(path)

    def read(self, storage_path: str) -> bytes:
        return Path(storage_path).read_bytes()

    def exists(self, content_hash: str, ext: str) -> bool:
        return (self.base_dir / f"{content_hash}.{ext}").exists()

    def local_path(self, storage_path: str) -> Path | None:
        """A local file with the bytes (for file responses), or None."""
        p = Path(storage_path)
        return p if p.is_file() else None


class S3AssetStorage(LocalAssetStorage):
    def __init__(self, base_dir: str | None = None, client=None) -> None:
        super().__init__(base_dir)
        if client is None:
            from src.core.assets.s3 import S3Client

            client = S3Client(endpoint=os.environ["S3_ENDPOINT"], bucket=os.getenv("S3_BUCKET") or "avos-assets",
                              access_key=os.environ["S3_ACCESS_KEY"], secret_key=os.environ["S3_SECRET_KEY"],
                              region=os.getenv("S3_REGION") or "us-east-1")
            client.ensure_bucket()
        self.s3 = client

    @staticmethod
    def key(content_hash: str, ext: str) -> str:
        return f"{content_hash[:2]}/{content_hash}.{ext}"

    def save(self, content_hash: str, ext: str, data: bytes) -> str:
        super().save(content_hash, ext, data)                       # cache
        key = self.key(content_hash, ext)
        self.s3.put(key, data, CONTENT_TYPES.get(ext, "application/octet-stream"))
        return f"s3://{self.s3.bucket}/{key}"

    def exists(self, content_hash: str, ext: str) -> bool:
        return self.s3.head(self.key(content_hash, ext))

    def _cache_file(self, storage_path: str) -> Path:
        return self.base_dir / storage_path.rsplit("/", 1)[-1]

    def read(self, storage_path: str) -> bytes:
        if not storage_path.startswith("s3://"):
            return super().read(storage_path)
        cached = self._cache_file(storage_path)
        if cached.is_file():
            return cached.read_bytes()
        data = self.s3.get(storage_path.split("/", 3)[3])
        cached.write_bytes(data)
        return data

    def local_path(self, storage_path: str) -> Path | None:
        if not storage_path.startswith("s3://"):
            return super().local_path(storage_path)
        cached = self._cache_file(storage_path)
        if not cached.is_file():
            self.read(storage_path)
        return cached


_default = None


def get_storage():
    """The configured backend (one per process)."""
    global _default
    if _default is None:
        _default = S3AssetStorage() if (os.getenv("ASSETS_STORAGE") or "").lower() in ("s3", "minio") else LocalAssetStorage()
    return _default
