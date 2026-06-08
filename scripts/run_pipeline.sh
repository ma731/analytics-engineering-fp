#!/usr/bin/env bash
# Run the full pipeline: extract -> load -> dbt build.
# Usage: bash scripts/run_pipeline.sh [--skip-extract]
set -euo pipefail

cd "$(dirname "$0")/.."
export DBT_PROFILES_DIR="$PWD"

if [ "${1:-}" != "--skip-extract" ]; then
    echo ">> Extracting from Open-Meteo..."
    python scripts/extract_open_meteo.py
fi

echo ">> Loading CSVs into DuckDB..."
python scripts/load_to_duckdb.py

echo ">> Installing dbt packages..."
dbt deps

echo ">> Building dbt models + running tests..."
dbt build

echo ">> Done. Launch the dashboard with:"
echo "   python -m streamlit run streamlit_app/app.py"
