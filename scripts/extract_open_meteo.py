#!/usr/bin/env python3
"""Extract starter Open-Meteo data for the group assignment.

The script writes four CSV files:
- raw_locations.csv
- raw_weather_daily.csv
- raw_forecast_daily.csv
- raw_air_quality_hourly.csv

It uses the Python standard library for HTTP requests. If certifi is installed,
the script uses it to avoid certificate issues on some local Python installs.
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
from urllib.parse import urlencode
from urllib.request import Request, urlopen


GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

DEFAULT_CITIES = ["Madrid", "Barcelona", "Valencia", "Sevilla", "Bilbao"]
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


def parse_args() -> argparse.Namespace:
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
    args = parser.parse_args()
    if not 0 <= args.past_days <= 92:
        parser.error("--past-days must be between 0 and 92.")
    if not 1 <= args.forecast_days <= 16:
        parser.error("--forecast-days must be between 1 and 16.")
    return args


def get_json(url: str, params: dict[str, Any]) -> dict[str, Any]:
    query_string = urlencode(params, doseq=True)
    request = Request(
        f"{url}?{query_string}",
        headers={"User-Agent": "dbt-ie-open-meteo-assignment/1.0"},
    )

    with urlopen(request, timeout=30, context=get_ssl_context()) as response:
        payload = response.read().decode("utf-8")

    return json.loads(payload)


def get_ssl_context() -> ssl.SSLContext:
    try:
        import certifi
    except ImportError:
        return ssl.create_default_context()

    return ssl.create_default_context(cafile=certifi.where())


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


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    extracted_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    locations = []
    weather_daily_rows = []
    forecast_daily_rows = []
    air_quality_hourly_rows = []

    for city in args.cities:
        print(f"Extracting {city}...", file=sys.stderr)
        location = geocode_city(city)
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

    print(f"Wrote {len(locations):,} locations", file=sys.stderr)
    print(f"Wrote {len(weather_daily_rows):,} recent daily weather rows", file=sys.stderr)
    print(f"Wrote {len(forecast_daily_rows):,} forecast daily weather rows", file=sys.stderr)
    print(f"Wrote {len(air_quality_hourly_rows):,} air quality hourly rows", file=sys.stderr)
    print(f"Output directory: {output_dir}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
