#!/usr/bin/env python3
"""
Drugs@FDA ingest
================
Takes the FDA "Drugs@FDA Data Files" zip (12 tab-delimited tables), cleans it,
and writes analysis-ready outputs:

    data/raw/drugsfda/<snapshot>/                 original zip + extracted .txt (untouched)
    data/processed/drugsfda/<snapshot>/csv/       UTF-8, comma-separated, trimmed
    data/processed/drugsfda/<snapshot>/parquet/   typed columns (ints, dates)
    data/processed/drugsfda/<snapshot>/drugsfda.sqlite   tables + keys + indexes + views
    data/processed/drugsfda/<snapshot>/data_quality_report.md
    data/processed/drugsfda/latest -> <snapshot>  (symlink / copy marker)

Source: https://www.fda.gov/drugs/drug-approvals-and-databases/drugsfda-data-files
        (zip: https://www.fda.gov/media/89850/download, refreshed every weekday)

Usage:
    python pipeline/drugsfda_ingest.py --zip path/to/drugsatfda.zip
    python pipeline/drugsfda_ingest.py --download            # fetch the current zip from FDA

Cleaning rules (all logged in the quality report):
  * Source is Windows-1252 with CRLF line endings -> decoded and written as UTF-8.
  * Every field is whitespace-trimmed (SubmissionType is space-padded to 10 chars in source).
  * Rows with too many tab-separated fields are repaired by dropping stray empty fields;
    rows that cannot be repaired are written to rejects/ instead of being silently lost.
  * The literal string 'Null' and empty strings become NULL in Parquet/SQLite.
  * 'YYYY-MM-DD 00:00:00' timestamps become dates.
  * ApplNo (6 digits) and ProductNo (3 digits) stay zero-padded strings - they are identifiers.
  * Nothing else is altered; referential gaps that exist in FDA's own data are reported, not dropped.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import re
import shutil
import sqlite3
import sys
import zipfile
from pathlib import Path

import pandas as pd

DRUGSFDA_ZIP_URL = "https://www.fda.gov/media/89850/download"
ROOT = Path(__file__).resolve().parents[1]

# --------------------------------------------------------------------------------------
# Schema: column -> type  (str | int | date).  Primary keys verified against the data.
# --------------------------------------------------------------------------------------
SCHEMA: dict[str, dict] = {
    "Applications": {
        "cols": {"ApplNo": "str", "ApplType": "str", "ApplPublicNotes": "str", "SponsorName": "str"},
        "pk": ["ApplNo"],
    },
    "Products": {
        "cols": {"ApplNo": "str", "ProductNo": "str", "Form": "str", "Strength": "str",
                 "ReferenceDrug": "int", "DrugName": "str", "ActiveIngredient": "str",
                 "ReferenceStandard": "int"},
        "pk": ["ApplNo", "ProductNo"],
    },
    "Submissions": {
        "cols": {"ApplNo": "str", "SubmissionClassCodeID": "int", "SubmissionType": "str",
                 "SubmissionNo": "int", "SubmissionStatus": "str", "SubmissionStatusDate": "date",
                 "SubmissionsPublicNotes": "str", "ReviewPriority": "str"},
        "pk": ["ApplNo", "SubmissionType", "SubmissionNo"],
    },
    "SubmissionPropertyType": {
        "cols": {"ApplNo": "str", "SubmissionType": "str", "SubmissionNo": "int",
                 "SubmissionPropertyTypeCode": "str", "SubmissionPropertyTypeID": "int"},
        "pk": ["ApplNo", "SubmissionType", "SubmissionNo", "SubmissionPropertyTypeID"],
    },
    "ApplicationDocs": {
        "cols": {"ApplicationDocsID": "int", "ApplicationDocsTypeID": "int", "ApplNo": "str",
                 "SubmissionType": "str", "SubmissionNo": "int", "ApplicationDocsTitle": "str",
                 "ApplicationDocsURL": "str", "ApplicationDocsDate": "date"},
        "pk": ["ApplicationDocsID"],
    },
    "Join_Submission_ActionTypes_Lookup": {
        "cols": {"SubmissionType": "str", "j_submissionActionTypeID": "int", "ApplNo": "str",
                 "SubmissionNo": "int", "ActionTypes_LookupID": "int"},
        "pk": ["j_submissionActionTypeID"],
    },
    "MarketingStatus": {
        "cols": {"MarketingStatusID": "int", "ApplNo": "str", "ProductNo": "str"},
        "pk": ["ApplNo", "ProductNo"],
    },
    "TE": {
        # One product can carry several TE codes (e.g. AB1..AB4), so TECode is part of the key.
        "cols": {"ApplNo": "str", "ProductNo": "str", "MarketingStatusID": "int", "TECode": "str"},
        "pk": ["ApplNo", "ProductNo", "MarketingStatusID", "TECode"],
    },
    "ActionTypes_Lookup": {
        "cols": {"ActionTypes_LookupID": "int", "ActionTypes_LookupDescription": "str",
                 "SupplCategoryLevel1Code": "str", "SupplCategoryLevel2Code": "str"},
        "pk": ["ActionTypes_LookupID"],
    },
    "ApplicationsDocsType_Lookup": {
        "cols": {"ApplicationDocsType_Lookup_ID": "int", "ApplicationDocsType_Lookup_Description": "str"},
        "pk": ["ApplicationDocsType_Lookup_ID"],
    },
    "MarketingStatus_Lookup": {
        "cols": {"MarketingStatusID": "int", "MarketingStatusDescription": "str"},
        "pk": ["MarketingStatusID"],
    },
    "SubmissionClass_Lookup": {
        "cols": {"SubmissionClassCodeID": "int", "SubmissionClassCode": "str",
                 "SubmissionClassCodeDescription": "str"},
        "pk": ["SubmissionClassCodeID"],
    },
}

# (child table, child cols, parent table, parent cols) - checked and reported, never enforced
FOREIGN_KEYS = [
    ("Products", ["ApplNo"], "Applications", ["ApplNo"]),
    ("Submissions", ["ApplNo"], "Applications", ["ApplNo"]),
    ("MarketingStatus", ["ApplNo", "ProductNo"], "Products", ["ApplNo", "ProductNo"]),
    ("TE", ["ApplNo", "ProductNo"], "Products", ["ApplNo", "ProductNo"]),
    ("ApplicationDocs", ["ApplNo", "SubmissionType", "SubmissionNo"], "Submissions", ["ApplNo", "SubmissionType", "SubmissionNo"]),
    ("SubmissionPropertyType", ["ApplNo", "SubmissionType", "SubmissionNo"], "Submissions", ["ApplNo", "SubmissionType", "SubmissionNo"]),
    ("Join_Submission_ActionTypes_Lookup", ["ApplNo", "SubmissionType", "SubmissionNo"], "Submissions", ["ApplNo", "SubmissionType", "SubmissionNo"]),
    ("Join_Submission_ActionTypes_Lookup", ["ActionTypes_LookupID"], "ActionTypes_Lookup", ["ActionTypes_LookupID"]),
    ("Submissions", ["SubmissionClassCodeID"], "SubmissionClass_Lookup", ["SubmissionClassCodeID"]),
    ("ApplicationDocs", ["ApplicationDocsTypeID"], "ApplicationsDocsType_Lookup", ["ApplicationDocsType_Lookup_ID"]),
    ("MarketingStatus", ["MarketingStatusID"], "MarketingStatus_Lookup", ["MarketingStatusID"]),
    ("TE", ["MarketingStatusID"], "MarketingStatus_Lookup", ["MarketingStatusID"]),
]

INDEXES = {
    "Products": [["DrugName"], ["ActiveIngredient"]],
    "Submissions": [["SubmissionStatusDate"], ["SubmissionClassCodeID"]],
    "ApplicationDocs": [["ApplNo", "SubmissionType", "SubmissionNo"]],
    "SubmissionPropertyType": [["ApplNo"]],
    "Join_Submission_ActionTypes_Lookup": [["ApplNo", "SubmissionType", "SubmissionNo"]],
    "TE": [["ApplNo", "ProductNo"]],
}

VIEWS = {
    # One row per product with application, sponsor, marketing status and TE codes.
    "v_products": """
        SELECT p.ApplNo, a.ApplType, a.SponsorName, p.ProductNo, p.DrugName, p.ActiveIngredient,
               p.Form, p.Strength, p.ReferenceDrug, p.ReferenceStandard,
               ms.MarketingStatusID, msl.MarketingStatusDescription,
               (SELECT group_concat(TECode, ',') FROM TE t
                 WHERE t.ApplNo = p.ApplNo AND t.ProductNo = p.ProductNo) AS TECodes
        FROM Products p
        LEFT JOIN Applications a           ON a.ApplNo = p.ApplNo
        LEFT JOIN MarketingStatus ms       ON ms.ApplNo = p.ApplNo AND ms.ProductNo = p.ProductNo
        LEFT JOIN MarketingStatus_Lookup msl ON msl.MarketingStatusID = ms.MarketingStatusID
    """,
    # Submissions decoded with class, sponsor and orphan flag.
    "v_submissions": """
        SELECT s.ApplNo, a.ApplType, a.SponsorName, s.SubmissionType, s.SubmissionNo,
               s.SubmissionStatus, s.SubmissionStatusDate, s.ReviewPriority,
               scl.SubmissionClassCode, scl.SubmissionClassCodeDescription,
               EXISTS (SELECT 1 FROM SubmissionPropertyType spt
                        WHERE spt.ApplNo = s.ApplNo AND spt.SubmissionType = s.SubmissionType
                          AND spt.SubmissionNo = s.SubmissionNo
                          AND spt.SubmissionPropertyTypeCode = 'Orphan') AS IsOrphan,
               s.SubmissionsPublicNotes
        FROM Submissions s
        LEFT JOIN Applications a ON a.ApplNo = s.ApplNo
        LEFT JOIN SubmissionClass_Lookup scl ON scl.SubmissionClassCodeID = s.SubmissionClassCodeID
    """,
    # Original approvals only (first approval date per application).
    "v_original_approvals": """
        SELECT s.ApplNo, a.ApplType, a.SponsorName, s.SubmissionStatusDate AS ApprovalDate,
               s.ReviewPriority
        FROM Submissions s
        LEFT JOIN Applications a ON a.ApplNo = s.ApplNo
        WHERE s.SubmissionType = 'ORIG' AND s.SubmissionStatus = 'AP'
    """,
    "v_application_docs": """
        SELECT d.ApplicationDocsID, d.ApplNo, d.SubmissionType, d.SubmissionNo,
               dt.ApplicationDocsType_Lookup_Description AS DocType,
               d.ApplicationDocsTitle, d.ApplicationDocsURL, d.ApplicationDocsDate
        FROM ApplicationDocs d
        LEFT JOIN ApplicationsDocsType_Lookup dt
               ON dt.ApplicationDocsType_Lookup_ID = d.ApplicationDocsTypeID
    """,
}


# --------------------------------------------------------------------------------------
def log(msg: str) -> None:
    print(f"[drugsfda] {msg}", flush=True)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download_zip(dest_dir: Path) -> Path:
    import requests  # only needed for --download
    dest_dir.mkdir(parents=True, exist_ok=True)
    tmp = dest_dir / "drugsatfda_download.zip"
    log(f"downloading {DRUGSFDA_ZIP_URL}")
    headers = {"User-Agent": "Mozilla/5.0 (fda-data-pipeline)"}
    with requests.get(DRUGSFDA_ZIP_URL, headers=headers, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    if not zipfile.is_zipfile(tmp):
        raise SystemExit("Downloaded file is not a zip (FDA may have returned an HTML block page). "
                         "Download it in a browser and pass --zip instead.")
    return tmp


def snapshot_from(zip_path: Path, zf: zipfile.ZipFile) -> str:
    m = re.search(r"(20\d{2})(\d{2})(\d{2})", zip_path.name)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    newest = max(zi.date_time for zi in zf.infolist())
    return dt.date(*newest[:3]).isoformat()


def parse_table(raw: bytes, name: str, expected_cols: list[str], report: dict) -> pd.DataFrame:
    text = raw.decode("cp1252", errors="replace")
    lines = text.replace("\r\n", "\n").split("\n")
    header = [h.strip() for h in lines[0].split("\t")]
    if header != expected_cols:
        raise SystemExit(f"{name}: header changed!\n  expected {expected_cols}\n  got      {header}\n"
                         "FDA changed the file layout - update SCHEMA before loading.")
    rows, repaired, rejected = [], [], []
    for lineno, line in enumerate(lines[1:], start=2):
        if line == "":
            continue
        parts = line.split("\t")
        if len(parts) > len(header):
            fixed = parts[:]
            while len(fixed) > len(header) and "" in fixed[1:-1]:
                fixed.pop(fixed.index("", 1))
            if len(fixed) == len(header):
                repaired.append(lineno)
                parts = fixed
        if len(parts) != len(header):
            rejected.append((lineno, line))
            continue
        rows.append([p.strip() for p in parts])
    df = pd.DataFrame(rows, columns=header, dtype="string")
    nonascii = int(df.apply(lambda s: s.str.contains(r"[^\x00-\x7f]", regex=True, na=False)).any(axis=1).sum())
    report["tables"][name] = {
        "rows": len(df), "repaired_lines": repaired, "rejected_lines": [l for l, _ in rejected],
        "non_ascii_rows": nonascii,
    }
    report["_rejects"][name] = rejected
    return df


def typed(df: pd.DataFrame, cols: dict[str, str]) -> pd.DataFrame:
    out = df.copy()
    for c, t in cols.items():
        s = out[c].replace({"": pd.NA, "Null": pd.NA})
        if t == "int":
            out[c] = pd.to_numeric(s, errors="raise").astype("Int64")
        elif t == "date":
            out[c] = pd.to_datetime(s, format="%Y-%m-%d %H:%M:%S", errors="raise").dt.date
        else:
            out[c] = s.astype("string")
    return out


def check_quality(tables: dict[str, pd.DataFrame], report: dict) -> None:
    for name, spec in SCHEMA.items():
        df = tables[name]
        report["tables"][name]["pk"] = spec["pk"]
        report["tables"][name]["pk_duplicates"] = int(df.duplicated(spec["pk"]).sum())
        report["tables"][name]["exact_duplicate_rows"] = int(df.duplicated().sum())
    fk = []
    for child, ccols, parent, pcols in FOREIGN_KEYS:
        c = tables[child][ccols].dropna()
        p = tables[parent][pcols].drop_duplicates()
        p.columns = ccols
        merged = c.merge(p, on=ccols, how="left", indicator=True)
        orphans = int((merged["_merge"] == "left_only").sum())
        fk.append({"child": child, "cols": ccols, "parent": parent, "checked": len(c), "orphans": orphans})
    report["foreign_keys"] = fk


def write_sqlite(tables: dict[str, pd.DataFrame], path: Path) -> None:
    if path.exists():
        path.unlink()
    con = sqlite3.connect(path)
    sqltype = {"str": "TEXT", "int": "INTEGER", "date": "TEXT"}
    for name, spec in SCHEMA.items():
        cols = ", ".join(f'"{c}" {sqltype[t]}' for c, t in spec["cols"].items())
        pk = ", ".join(f'"{c}"' for c in spec["pk"])
        con.execute(f'CREATE TABLE "{name}" ({cols}, PRIMARY KEY ({pk}))')
        df = tables[name].copy()
        for c, t in spec["cols"].items():
            if t == "date":
                df[c] = df[c].map(lambda d: d.isoformat() if pd.notna(d) else None)
        obj = df.astype(object)
        recs = obj.where(df.notna(), None).values.tolist()
        con.executemany(f'INSERT INTO "{name}" VALUES ({",".join("?" * len(spec["cols"]))})', recs)
        for i, idx in enumerate(INDEXES.get(name, [])):
            con.execute(f'CREATE INDEX "ix_{name}_{i}" ON "{name}" ({", ".join(chr(34)+c+chr(34) for c in idx)})')
        if "ApplNo" in spec["cols"] and spec["pk"][0] != "ApplNo":
            con.execute(f'CREATE INDEX "ix_{name}_applno" ON "{name}" ("ApplNo")')
    for v, sql in VIEWS.items():
        con.execute(f'CREATE VIEW "{v}" AS {sql}')
    con.commit()
    con.execute("VACUUM")
    con.close()


def write_report(report: dict, path: Path) -> None:
    L = [f"# Drugs@FDA data quality report — snapshot {report['snapshot']}", "",
         f"- Source zip: `{report['source_zip']}` (sha256 `{report['source_sha256'][:16]}…`)",
         f"- Processed at: {report['processed_at']} UTC", "",
         "## Tables", "",
         "| Table | Rows | Primary key | PK dups | Repaired lines | Rejected lines | Non-ASCII rows |",
         "|---|---:|---|---:|---|---|---:|"]
    for n, t in report["tables"].items():
        L.append(f"| {n} | {t['rows']:,} | {', '.join(t['pk'])} | {t['pk_duplicates']} | "
                 f"{', '.join(map(str, t['repaired_lines'])) or '—'} | "
                 f"{', '.join(map(str, t['rejected_lines'])) or '—'} | {t['non_ascii_rows']} |")
    L += ["", "Repaired lines had a stray empty tab-separated field which was removed. "
          "Non-ASCII rows are Windows-1252 characters (e.g. curly apostrophes) now stored as UTF-8.", "",
          "## Referential integrity (reported, not enforced)", "",
          "These gaps exist in FDA's published data (e.g. submissions for applications that are no longer "
          "listed). Rows are kept; use LEFT JOINs.", "",
          "| Child | Columns | Parent | Rows checked | Orphans |", "|---|---|---|---:|---:|"]
    for f in report["foreign_keys"]:
        L.append(f"| {f['child']} | {', '.join(f['cols'])} | {f['parent']} | {f['checked']:,} | {f['orphans']:,} |")
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--zip", type=Path, help="path to a Drugs@FDA zip already downloaded")
    g.add_argument("--download", action="store_true", help="download the current zip from fda.gov")
    ap.add_argument("--data-dir", type=Path, default=ROOT / "data", help="root data folder (default: ./data)")
    ap.add_argument("--no-sqlite", action="store_true")
    args = ap.parse_args(argv)

    zip_path = download_zip(args.data_dir / "raw" / "drugsfda" / "_incoming") if args.download else args.zip
    with zipfile.ZipFile(zip_path) as zf:
        snapshot = snapshot_from(zip_path, zf)
        raw_dir = args.data_dir / "raw" / "drugsfda" / snapshot
        raw_dir.mkdir(parents=True, exist_ok=True)
        kept_zip = raw_dir / f"drugsatfda_{snapshot.replace('-', '')}.zip"
        if zip_path.resolve() != kept_zip.resolve():
            shutil.copy2(zip_path, kept_zip)
        members = {Path(n).stem: n for n in zf.namelist() if n.lower().endswith(".txt")}
        missing = set(SCHEMA) - set(members)
        if missing:
            raise SystemExit(f"zip is missing expected tables: {sorted(missing)}")
        extra = set(members) - set(SCHEMA)
        if extra:
            log(f"WARNING: new tables in zip not in SCHEMA (kept in raw only): {sorted(extra)}")
        zf.extractall(raw_dir)
        report = {"snapshot": snapshot, "source_zip": kept_zip.name, "source_sha256": sha256(kept_zip),
                  "processed_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                  "tables": {}, "_rejects": {}}
        raw_tables = {n: parse_table(zf.read(members[n]), n, list(SCHEMA[n]["cols"]), report) for n in SCHEMA}
    if args.download:
        zip_path.unlink(missing_ok=True)

    out = args.data_dir / "processed" / "drugsfda" / snapshot
    for sub in ("csv", "parquet", "rejects"):
        (out / sub).mkdir(parents=True, exist_ok=True)

    tables = {n: typed(df, SCHEMA[n]["cols"]) for n, df in raw_tables.items()}
    check_quality(tables, report)

    for n, df in tables.items():
        df.to_csv(out / "csv" / f"{n}.csv", index=False, encoding="utf-8", quoting=csv.QUOTE_MINIMAL)
        df.to_parquet(out / "parquet" / f"{n}.parquet", index=False)
        rej = report["_rejects"][n]
        if rej:
            (out / "rejects" / f"{n}.rejected.txt").write_text(
                "\n".join(f"{l}\t{t}" for l, t in rej) + "\n", encoding="utf-8")
        log(f"{n:38s} {len(df):>8,} rows")
    if not any(report["_rejects"].values()):
        (out / "rejects").rmdir()

    if not args.no_sqlite:
        write_sqlite(tables, out / "drugsfda.sqlite")
        log(f"sqlite -> {out / 'drugsfda.sqlite'}")

    write_report(report, out / "data_quality_report.md")
    report.pop("_rejects")
    (out / "manifest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (args.data_dir / "processed" / "drugsfda" / "LATEST").write_text(snapshot + "\n")
    log(f"done: snapshot {snapshot} -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
