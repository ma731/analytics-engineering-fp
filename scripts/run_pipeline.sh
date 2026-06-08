#!/usr/bin/env bash
# Run the full pipeline end-to-end: extract -> load -> dbt build.
#
# Usage:
#   bash scripts/run_pipeline.sh                 # extract (5 cities) + load + build
#   bash scripts/run_pipeline.sh --skip-extract  # reuse existing CSVs, just load + build
#
# Works on Linux, macOS, and Windows (Git Bash). dbt reads profiles.yml from the
# project root via DBT_PROFILES_DIR.
set -euo pipefail

cd "$(dirname "$0")/.."
export DBT_PROFILES_DIR="$PWD"

# Prefer the uv-managed environment if present, so the script works the same in
# CI and on a teammate's clean checkout.
if command -v uv >/dev/null 2>&1; then
    RUN="uv run"
else
    RUN=""
fi

if [ "${1:-}" != "--skip-extract" ]; then
    echo ">> Extracting from Open-Meteo (5 rubric cities)..."
    $RUN python scripts/extract_open_meteo.py \
        --cities Madrid Barcelona Valencia Sevilla Bilbao
else
    echo ">> Skipping extraction, reusing existing CSVs in data/raw/open_meteo/."
fi

echo ">> Loading CSVs into DuckDB..."
$RUN python scripts/load_to_duckdb.py

echo ">> Installing dbt packages..."
$RUN dbt deps

echo ">> Building dbt models + running tests..."
$RUN dbt build

echo ">> Done. Launch the dashboard with:"
echo "   $RUN streamlit run streamlit_app/app.py"
