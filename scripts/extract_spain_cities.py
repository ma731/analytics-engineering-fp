#!/usr/bin/env python3
"""Reproducible Open-Meteo extraction for the 58 cities in spain_cities.csv.

Writes the same raw CSV schema the dbt sources expect:
  - raw_locations.csv          (one row per city)
  - raw_weather_daily.csv      (ONE FULL YEAR of daily weather, Archive API)
  - raw_forecast_daily.csv     (7-day forecast, Forecast API)
  - raw_air_quality_hourly.csv (recent hourly air quality, Air Quality API)

Run from the repo root:  python scripts/extract_spain_cities.py
"""
from __future__ import annotations

import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
WEATHER_START, WEATHER_END = "2025-06-08", "2026-06-07"   # one full year
AQI_PAST_DAYS = 92

DAILY_VARS = ["temperature_2m_max", "temperature_2m_min", "temperature_2m_mean",
              "precipitation_sum", "rain_sum", "snowfall_sum", "wind_speed_10m_max"]
AQI_VARS = ["pm10", "pm2_5", "carbon_monoxide", "nitrogen_dioxide", "ozone", "european_aqi"]
OUT = Path("data/raw/open_meteo")
OUT.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "CityComfortIndex/1.0 (student project)"}


def get(url, params, retries=4):
    q = "&".join(f"{k}={v}" for k, v in params.items())
    for attempt in range(retries):
        try:
            with urlopen(Request(f"{url}?{q}", headers=UA), timeout=60) as r:
                return json.load(r)
        except Exception:
            time.sleep(2 ** attempt)
    raise RuntimeError(f"failed: {url}")


def daily_rows(payload, loc, src, ts, datekey="date"):
    d = payload.get("daily", {})
    out = []
    for i, day in enumerate(d.get("time", [])):
        row = {"source_name": src, "extracted_at": ts, "location_id": loc["location_id"],
               "city_name": loc["city_name"], "country_code": "ES", datekey: day,
               "latitude": loc["latitude"], "longitude": loc["longitude"], "timezone": loc["timezone"]}
        for v in DAILY_VARS:
            row[v] = d.get(v, [None] * (i + 1))[i]
        out.append(row)
    return out


def write_csv(path, rows):
    if not rows:
        path.write_text("", encoding="utf-8"); return
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)


def main():
    ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    cities = list(csv.DictReader(open("spain_cities.csv", encoding="utf-8")))
    locations, weather, forecast, aqi = [], [], [], []
    for idx, c in enumerate(cities, start=1):
        loc = {"location_id": 900000 + idx, "city_name": c["city_name"],
               "latitude": float(c["latitude"]), "longitude": float(c["longitude"]),
               "timezone": c["timezone"]}
        locations.append({"location_id": loc["location_id"], "city_name": c["city_name"],
                          "country": "Spain", "country_code": "ES", "admin1": c["province"],
                          "latitude": c["latitude"], "longitude": c["longitude"],
                          "timezone": c["timezone"], "elevation": c["elevation_m"],
                          "population": c["population"], "extracted_at": ts})
        base = {"latitude": loc["latitude"], "longitude": loc["longitude"], "timezone": "auto"}
        # year of daily weather (archive)
        wy = get(ARCHIVE_URL, {**base, "start_date": WEATHER_START, "end_date": WEATHER_END,
                               "daily": ",".join(DAILY_VARS)})
        weather += daily_rows(wy, loc, "archive_weather", ts, "date")
        time.sleep(0.3)
        # 7-day forecast
        fc = get(FORECAST_URL, {**base, "forecast_days": 7, "daily": ",".join(DAILY_VARS)})
        forecast += daily_rows(fc, loc, "forecast", ts, "date")
        time.sleep(0.3)
        # recent hourly air quality
        aq = get(AIR_QUALITY_URL, {**base, "past_days": AQI_PAST_DAYS, "hourly": ",".join(AQI_VARS)})
        h = aq.get("hourly", {})
        for i, t in enumerate(h.get("time", [])):
            row = {"source_name": "air_quality", "extracted_at": ts, "location_id": loc["location_id"],
                   "city_name": c["city_name"], "country_code": "ES", "timestamp": t,
                   "latitude": loc["latitude"], "longitude": loc["longitude"], "timezone": loc["timezone"]}
            for v in AQI_VARS:
                row[v] = h.get(v, [None] * (i + 1))[i]
            aqi.append(row)
        time.sleep(0.3)
        print(f"  [{idx:2d}/{len(cities)}] {c['city_name']}".encode("ascii", "replace").decode())
    write_csv(OUT / "raw_locations.csv", locations)
    write_csv(OUT / "raw_weather_daily.csv", weather)
    write_csv(OUT / "raw_forecast_daily.csv", forecast)
    write_csv(OUT / "raw_air_quality_hourly.csv", aqi)
    print(f"DONE locations={len(locations)} weather={len(weather)} forecast={len(forecast)} aqi={len(aqi)}")


if __name__ == "__main__":
    sys.exit(main())
