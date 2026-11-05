"""A small S3 client (AWS Signature V4 over httpx) for the Asset Registry: works with MinIO, AWS S3, Cloudflare R2,
Backblaze B2 and other S3-compatible stores. No boto3 needed.

    c = S3Client(endpoint="http://minio:9000", bucket="avos-assets", access_key=..., secret_key=..., region="us-east-1")
    c.put("ab/abcd.png", data, "image/png");  c.get("ab/abcd.png");  c.head("ab/abcd.png");  c.ensure_bucket()
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
from urllib.parse import quote, urlparse

import httpx


def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


class S3Error(RuntimeError):
    pass


class S3Client:
    def __init__(self, *, endpoint: str, bucket: str, access_key: str, secret_key: str, region: str = "us-east-1",
                 timeout: float = 120.0) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.bucket, self.access_key, self.secret_key, self.region = bucket, access_key, secret_key, region
        self.host = urlparse(self.endpoint).netloc
        self.client = httpx.Client(timeout=timeout)

    # path-style addressing: <endpoint>/<bucket>/<key> (what MinIO expects; AWS supports it too)
    def _path(self, key: str | None) -> str:
        return f"/{self.bucket}" + (f"/{quote(key, safe='/~')}" if key else "")

    def headers(self, method: str, path: str, payload: bytes = b"", *, now: dt.datetime | None = None,
                extra: dict[str, str] | None = None, query: str = "") -> dict[str, str]:
        now = now or dt.datetime.now(dt.timezone.utc)
        amz_date, day = now.strftime("%Y%m%dT%H%M%SZ"), now.strftime("%Y%m%d")
        payload_hash = hashlib.sha256(payload).hexdigest()
        hdrs = {"host": self.host, "x-amz-content-sha256": payload_hash, "x-amz-date": amz_date,
                **{k.lower(): v for k, v in (extra or {}).items()}}
        signed = ";".join(sorted(hdrs))
        canonical = "\n".join([method, path, query, "".join(f"{k}:{str(hdrs[k]).strip()}\n" for k in sorted(hdrs)),
                               signed, payload_hash])
        scope = f"{day}/{self.region}/s3/aws4_request"
        to_sign = "\n".join(["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(canonical.encode()).hexdigest()])
        k = _sign(_sign(_sign(_sign(("AWS4" + self.secret_key).encode(), day), self.region), "s3"), "aws4_request")
        sig = hmac.new(k, to_sign.encode(), hashlib.sha256).hexdigest()
        out = {k2: v for k2, v in hdrs.items() if k2 != "host"}
        out["Authorization"] = (f"AWS4-HMAC-SHA256 Credential={self.access_key}/{scope}, SignedHeaders={signed}, "
                                f"Signature={sig}")
        return out

    def _req(self, method: str, key: str | None, payload: bytes = b"", extra: dict[str, str] | None = None) -> httpx.Response:
        path = self._path(key)
        return self.client.request(method, self.endpoint + path, content=payload or None,
                                   headers=self.headers(method, path, payload, extra=extra))

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        r = self._req("PUT", key, data, {"content-type": content_type})
        if r.status_code >= 300:
            raise S3Error(f"S3 PUT {key}: {r.status_code} {r.text[:300]}")

    def get(self, key: str) -> bytes:
        r = self._req("GET", key)
        if r.status_code >= 300:
            raise S3Error(f"S3 GET {key}: {r.status_code} {r.text[:300]}")
        return r.content

    def head(self, key: str) -> bool:
        r = self._req("HEAD", key)
        if r.status_code == 404:
            return False
        if r.status_code >= 300:
            raise S3Error(f"S3 HEAD {key}: {r.status_code}")
        return True

    def ensure_bucket(self) -> None:
        r = self._req("HEAD", None)
        if r.status_code == 404:
            body = b""
            extra = None
            if self.region != "us-east-1":
                body = (f'<CreateBucketConfiguration xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
                        f"<LocationConstraint>{self.region}</LocationConstraint></CreateBucketConfiguration>").encode()
                extra = {"content-type": "application/xml"}
            c = self._req("PUT", None, body, extra)
            if c.status_code >= 300 and "BucketAlreadyOwnedByYou" not in c.text:
                raise S3Error(f"Can't create bucket {self.bucket}: {c.status_code} {c.text[:300]}")
        elif r.status_code >= 300:
            raise S3Error(f"Can't reach bucket {self.bucket} at {self.endpoint}: HTTP {r.status_code}")
