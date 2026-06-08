#!/usr/bin/env python3
"""Load the raw Open-Meteo CSV files into DuckDB as tables in a ``raw`` schema.

Idempotent: each table is dropped and recreated from its CSV on every run, so
re-running never duplicates rows or leaves stale state. The ``raw`` schema is
the one the dbt sources in ``models/sources.yml`` read from.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

RAW_TABLES = [
    "raw_locations",
    "raw_weather_daily",
    "raw_forecast_daily",
    "raw_air_quality_hourly",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load raw Open-Meteo CSVs into DuckDB.")
    parser.add_argument(
        "--data-dir",
        default="data/raw/open_meteo",
        help="Directory containing the raw_*.csv files.",
    )
    parser.add_argument(
        "--db-path",
        default="data/weather_analytics.duckdb",
        help="Path to the DuckDB database file to create/populate.",
    )
    return parser.parse_args(argv)


def load(data_dir: Path, db_path: Path) -> int:
    """Load every CSV into raw.<table>. Returns the number of tables loaded."""
    db_path.parent.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(str(db_path))
    try:
        con.execute("create schema if not exists raw")
        loaded = 0
        for table_name in RAW_TABLES:
            csv_path = data_dir / f"{table_name}.csv"
            if not csv_path.exists():
                print(f"WARNING: {csv_path} not found, skipping", file=sys.stderr)
                continue
            con.execute(f"drop table if exists raw.{table_name}")
            con.execute(
                f"create table raw.{table_name} as "
                f"select * from read_csv_auto('{csv_path.as_posix()}')"
            )
            count = con.execute(f"select count(*) from raw.{table_name}").fetchone()[0]
            print(f"Loaded raw.{table_name}: {count:,} rows")
            loaded += 1
    finally:
        con.close()
    return loaded


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    data_dir = Path(args.data_dir)
    db_path = Path(args.db_path)

    loaded = load(data_dir, db_path)
    if loaded == 0:
        print(
            f"ERROR: no raw CSVs found in {data_dir}. "
            f"Run scripts/extract_open_meteo.py first.",
            file=sys.stderr,
        )
        return 1
    print(f"Done! Loaded {loaded} table(s) into {db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
