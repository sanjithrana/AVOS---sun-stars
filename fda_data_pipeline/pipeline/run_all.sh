#!/usr/bin/env bash
# Refresh everything: Drugs@FDA (download + clean) and openFDA bulk files.
# Usage:  ./pipeline/run_all.sh [openFDA profile]       default profile: drug_no_faers
#         ./pipeline/run_all.sh all                     everything on open.fda.gov (very large)
# Schedule (weekdays, after FDA's morning refresh), e.g. cron:
#   0 14 * * 1-5  cd /path/to/fda_data_pipeline && ./pipeline/run_all.sh >> logs/run.log 2>&1
set -euo pipefail
cd "$(dirname "$0")/.."
PROFILE="${1:-drug_no_faers}"

echo "=== $(date -u +%FT%TZ) Drugs@FDA"
python3 pipeline/drugsfda_ingest.py --download

echo "=== $(date -u +%FT%TZ) openFDA (profile: $PROFILE)"
python3 pipeline/openfda_download.py --profile "$PROFILE" --yes

echo "=== done"
