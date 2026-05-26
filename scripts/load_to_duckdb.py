#!/usr/bin/env python3
"""Load raw CSV files into DuckDB as tables in a 'raw' schema."""

import duckdb
from pathlib import Path

DATA_DIR = Path("data/raw/open_meteo")
DB_PATH = Path("data/weather_analytics.duckdb")

DB_PATH.parent.mkdir(parents=True, exist_ok=True)

con = duckdb.connect(str(DB_PATH))
con.execute("CREATE SCHEMA IF NOT EXISTS raw")

csv_files = [
    "raw_locations",
    "raw_weather_daily",
    "raw_forecast_daily",
    "raw_air_quality_hourly",
]

for table_name in csv_files:
    csv_path = DATA_DIR / f"{table_name}.csv"
    if csv_path.exists():
        con.execute(f"DROP TABLE IF EXISTS raw.{table_name}")
        con.execute(
            f"CREATE TABLE raw.{table_name} AS SELECT * FROM read_csv_auto('{csv_path.as_posix()}')"
        )
        count = con.execute(f"SELECT count(*) FROM raw.{table_name}").fetchone()[0]
        print(f"Loaded {table_name}: {count} rows")
    else:
        print(f"WARNING: {csv_path} not found, skipping")

con.close()
print("Done!")
