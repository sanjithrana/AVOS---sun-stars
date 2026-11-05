"""S3 / MinIO asset storage: our SigV4 signatures match botocore's, and assets round-trip through an S3 server
(moto's, standing in for MinIO). Skipped when moto / botocore aren't installed (they're test-only)."""
import datetime as dt

import pytest

from src.core.assets.s3 import S3Client
from src.core.assets.storage import S3AssetStorage

botocore = pytest.importorskip("botocore")
pytest.importorskip("moto")


def test_signature_matches_botocore():
    from botocore.auth import S3SigV4Auth
    from botocore.awsrequest import AWSRequest
    from botocore.credentials import Credentials

    c = S3Client(endpoint="http://minio:9000", bucket="avos-assets", access_key="AKID", secret_key="SECRET",
                 region="us-east-1")
    for method, key, body, extra in [("PUT", "ab/abc.png", b"hello", {"content-type": "image/png"}),
                                     ("GET", "ab/a b+c.mp4", b"", None), ("HEAD", None, b"", None)]:
        path = c._path(key)
        import hashlib

        req = AWSRequest(method=method, url="http://minio:9000" + path, data=body,
                         headers={**(extra or {}), "x-amz-content-sha256": hashlib.sha256(body).hexdigest()})
        S3SigV4Auth(Credentials("AKID", "SECRET"), "s3", "us-east-1").add_auth(req)
        when = dt.datetime.strptime(req.headers["x-amz-date"], "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc)
        ours = c.headers(method, path, body, now=when, extra=extra)
        assert ours["Authorization"] == req.headers["Authorization"], method


@pytest.fixture(scope="module")
def s3_server():
    from moto.server import ThreadedMotoServer

    server = ThreadedMotoServer(ip_address="127.0.0.1", port=0)
    server.start()
    host, port = server.get_host_and_port()
    yield f"http://{host}:{port}"
    server.stop()


def test_assets_round_trip_through_s3(s3_server, tmp_path):
    client = S3Client(endpoint=s3_server, bucket="avos-test", access_key="test", secret_key="test")
    client.ensure_bucket()
    client.ensure_bucket()                                  # idempotent
    store = S3AssetStorage(str(tmp_path / "cache"), client=client)
    path = store.save("ab" * 32, "png", b"\x89PNG data")
    assert path == f"s3://avos-test/ab/{'ab' * 32}.png"
    assert store.exists("ab" * 32, "png") and not store.exists("cd" * 32, "png")
    (tmp_path / "cache" / f"{'ab' * 32}.png").unlink()      # cache gone (new machine / pruned): read from S3
    assert store.read(path) == b"\x89PNG data"
    assert store.local_path(path).read_bytes() == b"\x89PNG data"
    old = tmp_path / "old.png"
    old.write_bytes(b"legacy")
    assert store.read(str(old)) == b"legacy"               # rows from before the switch still work
