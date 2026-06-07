"""Unit tests for the pure row-shaping functions in extract_open_meteo.py.

These mock no HTTP — they exercise the parsers that turn Open-Meteo API
payloads into flat CSV-ready rows.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import extract_open_meteo as ex  # noqa: E402

LOCATION = {
    "location_id": 1,
    "city_name": "Madrid",
    "country_code": "ES",
}
EXTRACTED_AT = "2026-06-01T00:00:00+00:00"


def test_build_daily_rows_basic_shape():
    payload = {
        "latitude": 40.4,
        "longitude": -3.7,
        "timezone": "Europe/Madrid",
        "daily": {
            "time": ["2026-05-01", "2026-05-02"],
            "temperature_2m_max": [25.0, 27.5],
            "precipitation_sum": [0.0, 3.2],
        },
    }
    rows = ex.build_daily_rows(payload, LOCATION, EXTRACTED_AT, "recent_weather")

    assert len(rows) == 2
    first = rows[0]
    assert first["location_id"] == 1
    assert first["city_name"] == "Madrid"
    assert first["country_code"] == "ES"
    assert first["date"] == "2026-05-01"
    assert first["source_name"] == "recent_weather"
    assert first["extracted_at"] == EXTRACTED_AT
    assert first["temperature_2m_max"] == 25.0
    assert first["precipitation_sum"] == 0.0
    assert first["latitude"] == 40.4
    # the "time" key must not leak in as a column
    assert "time" not in first


def test_build_daily_rows_aligns_values_by_index():
    payload = {
        "daily": {
            "time": ["2026-05-01", "2026-05-02", "2026-05-03"],
            "temperature_2m_max": [10, 20, 30],
        }
    }
    rows = ex.build_daily_rows(payload, LOCATION, EXTRACTED_AT, "forecast")
    assert [r["temperature_2m_max"] for r in rows] == [10, 20, 30]
    assert [r["date"] for r in rows] == ["2026-05-01", "2026-05-02", "2026-05-03"]


def test_build_daily_rows_empty_payload():
    assert ex.build_daily_rows({}, LOCATION, EXTRACTED_AT, "forecast") == []


def test_build_hourly_rows_basic_shape():
    payload = {
        "latitude": 41.4,
        "longitude": 2.2,
        "timezone": "Europe/Madrid",
        "hourly": {
            "time": ["2026-05-01T00:00", "2026-05-01T01:00"],
            "pm10": [12.0, 13.5],
            "european_aqi": [40, 42],
        },
    }
    rows = ex.build_hourly_rows(payload, LOCATION, EXTRACTED_AT, "air_quality")

    assert len(rows) == 2
    assert rows[0]["timestamp"] == "2026-05-01T00:00"
    assert rows[0]["pm10"] == 12.0
    assert rows[1]["european_aqi"] == 42
    assert rows[0]["source_name"] == "air_quality"
    assert "time" not in rows[0]


def test_default_cities_include_rubric_five():
    for city in ["Madrid", "Barcelona", "Valencia", "Sevilla", "Bilbao"]:
        assert city in ex.DEFAULT_CITIES


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
