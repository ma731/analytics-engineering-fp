#!/usr/bin/env python3
"""Extract Open-Meteo data for the weather-analytics project (Role 1 — Data Platform Lead).

The script writes four CSV files into ``--output-dir`` (default
``data/raw/open_meteo``), which are then loaded into DuckDB by
``scripts/load_to_duckdb.py``:

- raw_locations.csv
- raw_weather_daily.csv
- raw_forecast_daily.csv
- raw_air_quality_hourly.csv

Engineering features expected of the Data Platform Lead:

- **Idempotent CSV outputs** — re-running overwrites the four CSVs; the column
  schema is stable so the downstream ``stg_*`` models never break.
- **Structured logging** — progress is emitted to stderr as JSON lines, so the
  output is greppable in CI and in ``run_pipeline.sh``.
- **Resilient HTTP** — transient 5xx responses and network errors are retried
  with exponential backoff.
- **Snapshot mode** — ``--snapshot-mode`` additionally appends a timestamped
  Parquet partition per run, preserving every ``extracted_at`` so the
  forecast-vs-actual analysis can compare historical forecast runs.

It uses the Python standard library for HTTP. If ``certifi`` is installed the
script uses it to avoid certificate issues on some local Python installs.
"""

from __future__ import annotations

import argparse
import csv
import json
import ssl
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

DEFAULT_CITIES = [
    "Madrid", "Barcelona", "Valencia", "Sevilla", "Bilbao",
    "Toledo", "Albacete", "Ciudad Real", "Cuenca", "Guadalajara",
    "Almería", "Cádiz", "Córdoba", "Granada", "Huelva", "Jaén", "Málaga",
    "Huesca", "Teruel", "Zaragoza",
    "Oviedo", "Palma de Mallorca",
    "San Sebastián", "Vitoria-Gasteiz", "Santander",
    "Ávila", "Burgos", "León", "Palencia", "Salamanca",
    "Segovia", "Soria", "Valladolid", "Zamora",
    "Girona", "Lleida", "Tarragona",
    "Badajoz", "Cáceres",
    "A Coruña", "Lugo", "Ourense", "Pontevedra",
    "Logroño", "Murcia", "Pamplona",
    "Alicante", "Castellón de la Plana",
    "Las Palmas de Gran Canaria", "Santa Cruz de Tenerife",
    "Ceuta", "Melilla",
]
DEFAULT_DAILY_WEATHER_VARIABLES = [
    "temperature_2m_max",
    "temperature_2m_min",
    "temperature_2m_mean",
    "precipitation_sum",
    "rain_sum",
    "snowfall_sum",
    "wind_speed_10m_max",
]
DEFAULT_AIR_QUALITY_VARIABLES = [
    "pm10",
    "pm2_5",
    "carbon_monoxide",
    "nitrogen_dioxide",
    "ozone",
    "european_aqi",
]


def log_event(event: str, **fields: Any) -> None:
    """Emit a single structured (JSON line) log record to stderr."""
    record = {"event": event, **fields}
    print(json.dumps(record, ensure_ascii=False), file=sys.stderr, flush=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract location, weather, forecast, and air quality data from Open-Meteo."
    )
    parser.add_argument(
        "--cities",
        nargs="+",
        default=DEFAULT_CITIES,
        help="City names to search in the Open-Meteo Geocoding API.",
    )
    parser.add_argument(
        "--past-days",
        type=int,
        default=30,
        help="Number of recent past days to extract from the Forecast API. Maximum is 92.",
    )
    parser.add_argument(
        "--forecast-days",
        type=int,
        default=7,
        help="Number of future forecast days to extract. Maximum is 16.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/raw/open_meteo",
        help="Directory where CSV files will be written.",
    )
    parser.add_argument(
        "--pause-seconds",
        type=float,
        default=0.25,
        help="Small pause between API calls.",
    )
    parser.add_argument(
        "--snapshot-mode",
        action="store_true",
        help=(
            "In addition to the CSVs, append a timestamped Parquet partition per "
            "run under <output-dir>/snapshots/, preserving forecast history."
        ),
    )
    args = parser.parse_args(argv)
    if not 0 <= args.past_days <= 92:
        parser.error("--past-days must be between 0 and 92.")
    if not 1 <= args.forecast_days <= 16:
        parser.error("--forecast-days must be between 1 and 16.")
    return args


def get_ssl_context() -> ssl.SSLContext:
    try:
        import certifi
    except ImportError:
        return ssl.create_default_context()

    return ssl.create_default_context(cafile=certifi.where())


def get_json(url: str, params: dict[str, Any], retries: int = 4) -> dict[str, Any]:
    """Fetch JSON from Open-Meteo with exponential backoff on transient failures.

    Retries on 5xx responses and on network-level ``URLError`` (DNS/timeout).
    4xx responses are re-raised immediately — they will not succeed on retry.
    """
    query_string = urlencode(params, doseq=True)
    request = Request(
        f"{url}?{query_string}",
        headers={"User-Agent": "dbt-ie-open-meteo-assignment/1.0"},
    )

    for attempt in range(retries):
        try:
            with urlopen(request, timeout=30, context=get_ssl_context()) as response:
                payload = response.read().decode("utf-8")
            return json.loads(payload)
        except HTTPError as exc:
            if exc.code < 500 or attempt == retries - 1:
                raise
            wait = 2 ** attempt
            log_event("http_retry", url=url, status=exc.code, attempt=attempt + 1, wait_s=wait)
            time.sleep(wait)
        except URLError as exc:
            if attempt == retries - 1:
                raise
            wait = 2 ** attempt
            log_event("network_retry", url=url, reason=str(exc.reason), attempt=attempt + 1,
                      wait_s=wait)
            time.sleep(wait)

    # Unreachable: the loop either returns or re-raises on the final attempt.
    raise RuntimeError(f"Exhausted retries fetching {url}")


def geocode_city(city: str) -> dict[str, Any]:
    data = get_json(
        GEOCODING_URL,
        {
            "name": city,
            "count": 1,
            "language": "en",
            "format": "json",
        },
    )
    results = data.get("results", [])
    if not results:
        raise ValueError(f"No geocoding result found for city: {city}")

    result = results[0]
    return {
        "location_id": result.get("id"),
        "city_name": result.get("name"),
        "country": result.get("country"),
        "country_code": result.get("country_code"),
        "admin1": result.get("admin1"),
        "latitude": result.get("latitude"),
        "longitude": result.get("longitude"),
        "timezone": result.get("timezone"),
        "elevation": result.get("elevation"),
        "population": result.get("population"),
    }


def build_daily_rows(
    payload: dict[str, Any],
    location: dict[str, Any],
    extracted_at: str,
    source_name: str,
) -> list[dict[str, Any]]:
    daily = payload.get("daily", {})
    dates = daily.get("time", [])
    rows = []

    for index, day in enumerate(dates):
        row = {
            "source_name": source_name,
            "extracted_at": extracted_at,
            "location_id": location["location_id"],
            "city_name": location["city_name"],
            "country_code": location["country_code"],
            "date": day,
            "latitude": payload.get("latitude"),
            "longitude": payload.get("longitude"),
            "timezone": payload.get("timezone"),
        }
        for variable, values in daily.items():
            if variable == "time":
                continue
            row[variable] = values[index]
        rows.append(row)

    return rows


def build_hourly_rows(
    payload: dict[str, Any],
    location: dict[str, Any],
    extracted_at: str,
    source_name: str,
) -> list[dict[str, Any]]:
    hourly = payload.get("hourly", {})
    timestamps = hourly.get("time", [])
    rows = []

    for index, timestamp in enumerate(timestamps):
        row = {
            "source_name": source_name,
            "extracted_at": extracted_at,
            "location_id": location["location_id"],
            "city_name": location["city_name"],
            "country_code": location["country_code"],
            "timestamp": timestamp,
            "latitude": payload.get("latitude"),
            "longitude": payload.get("longitude"),
            "timezone": payload.get("timezone"),
        }
        for variable, values in hourly.items():
            if variable == "time":
                continue
            row[variable] = values[index]
        rows.append(row)

    return rows


def fetch_recent_weather(
    location: dict[str, Any], past_days: int, extracted_at: str
) -> list[dict[str, Any]]:
    payload = get_json(
        FORECAST_URL,
        {
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "past_days": past_days,
            "forecast_days": 1,
            "daily": ",".join(DEFAULT_DAILY_WEATHER_VARIABLES),
            "timezone": location["timezone"] or "auto",
        },
    )
    return build_daily_rows(payload, location, extracted_at, "recent_weather")


def fetch_forecast(
    location: dict[str, Any], forecast_days: int, extracted_at: str
) -> list[dict[str, Any]]:
    payload = get_json(
        FORECAST_URL,
        {
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "forecast_days": forecast_days,
            "daily": ",".join(DEFAULT_DAILY_WEATHER_VARIABLES),
            "timezone": location["timezone"] or "auto",
        },
    )
    return build_daily_rows(payload, location, extracted_at, "forecast")


def fetch_air_quality(location: dict[str, Any], extracted_at: str) -> list[dict[str, Any]]:
    payload = get_json(
        AIR_QUALITY_URL,
        {
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "hourly": ",".join(DEFAULT_AIR_QUALITY_VARIABLES),
            "timezone": location["timezone"] or "auto",
        },
    )
    return build_hourly_rows(payload, location, extracted_at, "air_quality")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if not rows:
        path.write_text("", encoding="utf-8")
        return

    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def snapshot_partition_path(output_dir: Path, source_name: str, extracted_at: str) -> Path:
    """Build the Parquet partition path for one snapshot run.

    Layout: ``<output-dir>/snapshots/<source_name>/extracted_at=<safe-ts>/data.parquet``.
    The colons in the ISO timestamp are replaced so the path is valid on Windows.
    """
    safe_ts = extracted_at.replace(":", "-")
    return output_dir / "snapshots" / source_name / f"extracted_at={safe_ts}" / "data.parquet"


def write_parquet_snapshot(path: Path, rows: list[dict[str, Any]]) -> bool:
    """Append a Parquet partition. Returns True if written, False if skipped.

    Uses pyarrow if available; otherwise logs and skips (CSVs are still the
    authoritative pipeline input, so a missing pyarrow never breaks the run).
    """
    if not rows:
        return False
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        log_event("snapshot_skipped", reason="pyarrow_not_installed", path=str(path))
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), path)
    return True


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output_dir = Path(args.output_dir)
    extracted_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    log_event(
        "extract_start",
        extracted_at=extracted_at,
        city_count=len(args.cities),
        past_days=args.past_days,
        forecast_days=args.forecast_days,
        snapshot_mode=args.snapshot_mode,
    )

    locations: list[dict[str, Any]] = []
    weather_daily_rows: list[dict[str, Any]] = []
    forecast_daily_rows: list[dict[str, Any]] = []
    air_quality_hourly_rows: list[dict[str, Any]] = []

    for city in args.cities:
        try:
            location = geocode_city(city)
        except ValueError as exc:
            log_event("city_skipped", city=city, reason=str(exc))
            continue

        log_event("city_extracting", city=city, location_id=location["location_id"])
        locations.append({**location, "extracted_at": extracted_at})
        time.sleep(args.pause_seconds)

        weather_daily_rows.extend(
            fetch_recent_weather(location, args.past_days, extracted_at)
        )
        time.sleep(args.pause_seconds)

        forecast_daily_rows.extend(fetch_forecast(location, args.forecast_days, extracted_at))
        time.sleep(args.pause_seconds)

        air_quality_hourly_rows.extend(fetch_air_quality(location, extracted_at))
        time.sleep(args.pause_seconds)

    write_csv(output_dir / "raw_locations.csv", locations)
    write_csv(output_dir / "raw_weather_daily.csv", weather_daily_rows)
    write_csv(output_dir / "raw_forecast_daily.csv", forecast_daily_rows)
    write_csv(output_dir / "raw_air_quality_hourly.csv", air_quality_hourly_rows)

    if args.snapshot_mode:
        for source_name, rows in (
            ("raw_weather_daily", weather_daily_rows),
            ("raw_forecast_daily", forecast_daily_rows),
            ("raw_air_quality_hourly", air_quality_hourly_rows),
        ):
            partition = snapshot_partition_path(output_dir, source_name, extracted_at)
            if write_parquet_snapshot(partition, rows):
                log_event("snapshot_written", source=source_name, path=str(partition),
                          rows=len(rows))

    log_event(
        "extract_complete",
        locations=len(locations),
        weather_daily_rows=len(weather_daily_rows),
        forecast_daily_rows=len(forecast_daily_rows),
        air_quality_hourly_rows=len(air_quality_hourly_rows),
        output_dir=str(output_dir),
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
