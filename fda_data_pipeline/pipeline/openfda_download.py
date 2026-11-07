#!/usr/bin/env python3
"""
openFDA bulk downloader
=======================
Downloads the openFDA bulk files listed on https://open.fda.gov/data/downloads/ using the
machine-readable manifest at https://api.fda.gov/download.json.

    data/openfda/<category>/<endpoint>/<export_date>/raw/*.json.zip      original partitions
    data/openfda/<category>/<endpoint>/<export_date>/ndjson/*.ndjson.gz  one record per line
    data/openfda/<category>/<endpoint>/<export_date>/meta.json           openFDA meta block(s)
    data/openfda/<category>/<endpoint>/LATEST                            newest export date
    data/openfda/download_manifest_<timestamp>.json                      snapshot of FDA manifest
    data/openfda/catalog.csv                                             endpoint / size / records

Re-runs are incremental: partitions already downloaded with the right size are skipped,
and a new export_date from FDA lands in a new folder (old ones are kept until you delete them).

Usage:
    python pipeline/openfda_download.py --list                       # show catalog + sizes
    python pipeline/openfda_download.py --profile drug_no_faers      # see config/openfda.toml
    python pipeline/openfda_download.py --include drug/label drug/ndc
    python pipeline/openfda_download.py --profile all --yes          # everything, no prompt
    python pipeline/openfda_download.py --dry-run --profile all
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import csv
import datetime as dt
import fnmatch
import gzip
import json
import os
import sys
import time
import tomllib
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
UA = {"User-Agent": "fda-data-pipeline/1.0 (+https://open.fda.gov)"}


def log(msg: str) -> None:
    print(f"[openfda] {msg}", flush=True)


def load_config(path: Path) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def fetch_manifest(url: str) -> dict:
    r = requests.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    return r.json()


def flatten_manifest(manifest: dict) -> list[dict]:
    """download.json -> [{key, category, endpoint, export_date, total_records, partitions[], size_mb}]"""
    out = []
    for category, endpoints in manifest.get("results", {}).items():
        if not isinstance(endpoints, dict):
            continue
        for endpoint, info in endpoints.items():
            if not isinstance(info, dict) or "partitions" not in info:
                continue
            parts = info.get("partitions") or []
            out.append({
                "key": f"{category}/{endpoint}",
                "category": category,
                "endpoint": endpoint,
                "export_date": info.get("export_date", "unknown"),
                "total_records": info.get("total_records"),
                "partitions": parts,
                "size_mb": round(sum(float(p.get("size_mb") or 0) for p in parts), 2),
            })
    return sorted(out, key=lambda e: e["key"])


def select(endpoints: list[dict], include: list[str], exclude: list[str]) -> list[dict]:
    keep = [e for e in endpoints if any(fnmatch.fnmatch(e["key"], p) for p in include)]
    return [e for e in keep if not any(fnmatch.fnmatch(e["key"], p) for p in exclude)]


def write_catalog(endpoints: list[dict], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["endpoint", "export_date", "total_records", "partitions", "size_mb"])
        for e in endpoints:
            w.writerow([e["key"], e["export_date"], e["total_records"], len(e["partitions"]), e["size_mb"]])


def partition_path(base: Path, url: str) -> Path:
    # Keep FDA's own sub-path after the endpoint (drug/event has year/quarter sub-folders).
    parts = urlparse(url).path.strip("/").split("/")
    return base.joinpath(*parts[2:]) if len(parts) > 3 else base / parts[-1]


def download_one(url: str, dest: Path, expect_mb: float | None, retries: int = 5) -> str:
    if dest.exists() and zipfile.is_zipfile(dest):
        if not expect_mb or abs(dest.stat().st_size / 1e6 - expect_mb) / max(expect_mb, 0.01) < 0.05:
            return "skipped"
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(1, retries + 1):
        try:
            with requests.get(url, headers=UA, stream=True, timeout=(30, 300)) as r:
                r.raise_for_status()
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
            if not zipfile.is_zipfile(tmp):
                raise IOError("not a valid zip")
            os.replace(tmp, dest)
            return "downloaded"
        except Exception as exc:  # noqa: BLE001
            if attempt == retries:
                tmp.unlink(missing_ok=True)
                raise RuntimeError(f"{url}: {exc}") from exc
            time.sleep(min(60, 2 ** attempt))
    return "failed"


def to_ndjson(zip_path: Path, out_path: Path) -> tuple[int, dict]:
    """Convert one openFDA partition ({meta, results:[...]}) to gzipped NDJSON."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n, meta = 0, {}
    tmp = out_path.with_suffix(".tmp")
    with zipfile.ZipFile(zip_path) as zf, gzip.open(tmp, "wt", encoding="utf-8") as out:
        for name in zf.namelist():
            if not name.endswith(".json"):
                continue
            with zf.open(name) as fh:
                doc = json.load(fh)
            meta = doc.get("meta", meta)
            for rec in doc.get("results", []):
                out.write(json.dumps(rec, ensure_ascii=False, separators=(",", ":")))
                out.write("\n")
                n += 1
    os.replace(tmp, out_path)
    return n, meta


def process_endpoint(e: dict, data_dir: Path, workers: int, convert: bool, keep_zips: bool) -> dict:
    base = data_dir / e["category"] / e["endpoint"] / e["export_date"]
    raw, nd = base / "raw", base / "ndjson"
    stats = {"endpoint": e["key"], "export_date": e["export_date"], "downloaded": 0, "skipped": 0,
             "failed": [], "records_written": 0}
    jobs = {}
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        for p in e["partitions"]:
            dest = partition_path(raw, p["file"])
            jobs[ex.submit(download_one, p["file"], dest, float(p.get("size_mb") or 0))] = (p, dest)
        for fut in cf.as_completed(jobs):
            p, dest = jobs[fut]
            try:
                stats[fut.result()] += 1
            except Exception as exc:  # noqa: BLE001
                stats["failed"].append(str(exc))
                log(f"  FAILED {exc}")
    log(f"{e['key']}: {stats['downloaded']} downloaded, {stats['skipped']} already present, "
        f"{len(stats['failed'])} failed")

    if convert:
        metas = []
        for p, dest in jobs.values():
            if not dest.exists():
                continue
            rel = dest.relative_to(raw)
            out = nd / rel.parent / (rel.name.replace(".json.zip", "") + ".ndjson.gz")
            if out.exists() and out.stat().st_mtime >= dest.stat().st_mtime:
                continue
            n, meta = to_ndjson(dest, out)
            stats["records_written"] += n
            metas.append({"partition": str(rel), "records": n, "meta": meta})
            if not keep_zips:
                dest.unlink()
        if metas:
            mpath = base / "meta.json"
            merged = {m["partition"]: m for m in (json.loads(mpath.read_text()) if mpath.exists() else [])}
            merged.update({m["partition"]: m for m in metas})
            mpath.write_text(json.dumps(sorted(merged.values(), key=lambda m: m["partition"]), indent=2),
                             encoding="utf-8")
    if not stats["failed"]:
        (data_dir / e["category"] / e["endpoint"] / "LATEST").write_text(e["export_date"] + "\n")
    return stats


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=Path, default=ROOT / "config" / "openfda.toml")
    ap.add_argument("--data-dir", type=Path, default=ROOT / "data" / "openfda")
    ap.add_argument("--profile", help="profile name from the config file")
    ap.add_argument("--include", nargs="+", help="endpoint patterns, e.g. drug/label 'device/*'")
    ap.add_argument("--exclude", nargs="+", default=[])
    ap.add_argument("--list", action="store_true", help="print the catalog and exit")
    ap.add_argument("--dry-run", action="store_true", help="show what would be downloaded")
    ap.add_argument("--yes", action="store_true", help="skip the size confirmation")
    ap.add_argument("--workers", type=int)
    ap.add_argument("--no-ndjson", action="store_true")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    args.data_dir.mkdir(parents=True, exist_ok=True)
    log(f"fetching manifest {cfg['manifest_url']}")
    manifest = fetch_manifest(cfg["manifest_url"])
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (args.data_dir / f"download_manifest_{stamp}.json").write_text(json.dumps(manifest, indent=1))
    endpoints = flatten_manifest(manifest)
    write_catalog(endpoints, args.data_dir / "catalog.csv")

    if args.list:
        print(f"{'endpoint':38s} {'export':>10s} {'records':>13s} {'parts':>6s} {'size_MB':>10s}")
        for e in endpoints:
            print(f"{e['key']:38s} {e['export_date']:>10s} {e['total_records'] or 0:>13,} "
                  f"{len(e['partitions']):>6d} {e['size_mb']:>10,.1f}")
        print(f"{'TOTAL':38s} {'':>10s} {'':>13s} {sum(len(e['partitions']) for e in endpoints):>6d} "
              f"{sum(e['size_mb'] for e in endpoints):>10,.1f}")
        return 0

    if args.include:
        include, exclude = args.include, args.exclude
    else:
        prof = cfg["profiles"][args.profile or cfg.get("default_profile", "all")]
        include, exclude = prof["include"], prof.get("exclude", []) + args.exclude
    chosen = select(endpoints, include, exclude)
    if not chosen:
        log("nothing matched; run --list to see endpoint names")
        return 1
    total_gb = sum(e["size_mb"] for e in chosen) / 1000
    log(f"selected {len(chosen)} endpoints, {sum(len(e['partitions']) for e in chosen)} partitions, "
        f"~{total_gb:,.1f} GB zipped")
    for e in chosen:
        log(f"  {e['key']:38s} {e['export_date']}  {e['size_mb']:>10,.1f} MB")
    if args.dry_run:
        return 0
    if total_gb > cfg.get("confirm_above_gb", 20) and not args.yes:
        if not sys.stdin.isatty() or input(f"Download ~{total_gb:,.1f} GB? [y/N] ").strip().lower() != "y":
            log("aborted (pass --yes to skip this check)")
            return 1

    results = [process_endpoint(e, args.data_dir, args.workers or cfg.get("workers", 4),
                                cfg.get("convert_to_ndjson", True) and not args.no_ndjson,
                                cfg.get("keep_zips", True)) for e in chosen]
    (args.data_dir / f"run_{stamp}.json").write_text(json.dumps(results, indent=2))
    failed = [r for r in results if r["failed"]]
    log(f"done: {len(results) - len(failed)} endpoints complete, {len(failed)} with failures "
        f"(re-run the same command to retry only the missing partitions)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
