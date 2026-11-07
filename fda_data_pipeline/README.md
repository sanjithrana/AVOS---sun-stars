# FDA data pipeline

Two FDA sources, one folder:

| Source | What it is | Status in this folder |
|---|---|---|
| **Drugs@FDA data files** — [fda.gov](https://www.fda.gov/drugs/drug-approvals-and-databases/drugsfda-data-files) | 12 tab-delimited tables: applications, products, submissions, approval documents, TE codes, marketing status | ✅ **Loaded** — snapshot **2026-11-05** (raw + cleaned CSV / Parquet / SQLite) |
| **openFDA bulk downloads** — [open.fda.gov](https://open.fda.gov/data/downloads/) | All openFDA datasets: drug (event/FAERS, label, NDC, Drugs@FDA, enforcement, shortages), device (510k, PMA, event, recall, UDI, …), food, animal & vet, tobacco, cosmetics, NSDE, substance/UNII, CRLs | ⬇️ **Downloader ready** — run it on a machine with internet access (see below) |

## Folder layout

```
fda_data_pipeline/
├── README.md
├── requirements.txt
├── config/openfda.toml               which openFDA datasets to pull (profiles)
├── pipeline/
│   ├── drugsfda_ingest.py            Drugs@FDA zip → clean CSV / Parquet / SQLite + QA report
│   ├── openfda_download.py           openFDA manifest → partitions → NDJSON
│   └── run_all.sh                    refresh both in one go (cron-friendly)
├── docs/drugsfda_data_dictionary.md  tables, columns, keys, joins, views
└── data/
    ├── raw/drugsfda/2026-11-05/                original FDA zip + 12 .txt files (untouched)
    ├── processed/drugsfda/2026-11-05/
    │   ├── csv/            12 tables, UTF-8, comma-separated
    │   ├── parquet/        12 tables, typed (Int64, date32)
    │   ├── drugsfda.sqlite tables + primary keys + indexes + 4 views
    │   ├── data_quality_report.md
    │   └── manifest.json   row counts, checksum, repairs
    ├── processed/drugsfda/LATEST               → "2026-11-05"
    └── openfda/                                filled by openfda_download.py
```

## Quick start

```bash
pip install -r requirements.txt          # Python 3.11+

# Drugs@FDA — already loaded; to refresh with today's FDA file:
python pipeline/drugsfda_ingest.py --download
#   or, if fda.gov blocks scripted downloads on your network:
python pipeline/drugsfda_ingest.py --zip ~/Downloads/drugsatfda20261106.zip

# openFDA — see what's available and how big it is first
python pipeline/openfda_download.py --list
python pipeline/openfda_download.py --profile drug_no_faers      # all drug data except FAERS
python pipeline/openfda_download.py --profile all --yes          # everything (hundreds of GB)
python pipeline/openfda_download.py --include drug/label device/510k

# both at once
./pipeline/run_all.sh                 # default profile: drug_no_faers
./pipeline/run_all.sh all
```

## Using the data

```python
import pandas as pd
products = pd.read_parquet("data/processed/drugsfda/2026-11-05/parquet/Products.parquet")
```
```sql
-- sqlite3 data/processed/drugsfda/2026-11-05/drugsfda.sqlite
SELECT * FROM v_products WHERE ActiveIngredient LIKE '%ATORVASTATIN%';
SELECT substr(ApprovalDate,1,4) AS yr, COUNT(*) FROM v_original_approvals
 WHERE ApplType = 'NDA' GROUP BY yr ORDER BY yr DESC;
```
```sql
-- DuckDB straight off the files (openFDA NDJSON too)
SELECT * FROM 'data/processed/drugsfda/2026-11-05/parquet/Submissions.parquet' LIMIT 10;
SELECT openfda.brand_name, effective_time FROM read_ndjson_auto('data/openfda/drug/label/*/ndjson/*.ndjson.gz') LIMIT 10;
```

## Drugs@FDA snapshot 2026-11-05 — row counts

| Table | Rows |
|---|---:|
| Applications | 29,444 |
| Products | 51,975 |
| Submissions | 194,421 |
| SubmissionPropertyType | 321,980 |
| ApplicationDocs | 81,479 |
| Join_Submission_ActionTypes_Lookup | 210,286 |
| MarketingStatus | 52,586 |
| TE | 26,841 |
| ActionTypes_Lookup / ApplicationsDocsType_Lookup / MarketingStatus_Lookup / SubmissionClass_Lookup | 59 / 62 / 5 / 28 |

## What the cleaning does (and doesn't)

- FDA ships Windows-1252 text with CRLF line endings → converted to UTF-8 (19 Submissions notes contain curly quotes).
- All fields trimmed; `SubmissionType` is space-padded to 10 characters in the source.
- 1 malformed line (`ApplicationDocs` line 78679, stray tab) repaired; unrepairable lines would go to `rejects/` rather than disappear.
- `Null` literals and blanks → NULL; `YYYY-MM-DD 00:00:00` → date.
- `ApplNo` / `ProductNo` stay zero-padded strings.
- `TE` key includes `TECode` — a product can carry several codes (AB1…AB4).
- **Not changed:** FDA's own referential gaps (e.g. 5,377 submissions whose ApplNo isn't in Applications). They're counted in `data_quality_report.md`; use LEFT JOINs.
- If FDA changes a file's columns, the ingest stops with a clear error instead of loading misaligned data.

## openFDA notes

- The downloader reads FDA's live manifest (`https://api.fda.gov/download.json`), so it always gets the current partition list and picks up new datasets automatically.
- Re-runs are incremental: finished partitions are skipped; a failed run can just be re-run.
- Each new FDA `export_date` goes in its own folder; `LATEST` in each endpoint folder points to the newest complete one.
- `drug/event` (FAERS) and `device/event` (MAUDE) are very large (on the order of 100+ GB zipped together). Check `--list` and disk space first. The script asks for confirmation above 20 GB unless `--yes` is passed.
- openFDA records are nested JSON; the NDJSON output keeps that structure (one record per line), ready for BigQuery, DuckDB, Spark or `pandas.read_json(lines=True)`.
