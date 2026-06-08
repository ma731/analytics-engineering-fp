"""Unit tests for extract_open_meteo.py.

The HTTP layer is mocked everywhere — no network calls are made. Tests cover the
pure row-shaping parsers, argument validation, the retry/backoff logic, and the
snapshot path helper.
"""

import csv
import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import extract_open_meteo as ex  # noqa: E402

LOCATION = {
    "location_id": 1,
    "city_name": "Madrid",
    "country_code": "ES",
}
EXTRACTED_AT = "2026-06-01T00:00:00+00:00"


# --------------------------------------------------------------------------- #
# Row-shaping parsers
# --------------------------------------------------------------------------- #
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


def test_build_hourly_rows_empty_payload():
    assert ex.build_hourly_rows({}, LOCATION, EXTRACTED_AT, "air_quality") == []


def test_default_cities_include_rubric_five():
    for city in ["Madrid", "Barcelona", "Valencia", "Sevilla", "Bilbao"]:
        assert city in ex.DEFAULT_CITIES


# --------------------------------------------------------------------------- #
# Argument validation
# --------------------------------------------------------------------------- #
def test_parse_args_defaults():
    args = ex.parse_args([])
    assert args.past_days == 30
    assert args.forecast_days == 7
    assert args.snapshot_mode is False
    assert args.output_dir == "data/raw/open_meteo"


def test_parse_args_snapshot_flag():
    args = ex.parse_args(["--snapshot-mode"])
    assert args.snapshot_mode is True


@pytest.mark.parametrize("bad", [["--past-days", "93"], ["--forecast-days", "0"],
                                 ["--forecast-days", "17"]])
def test_parse_args_rejects_out_of_range(bad):
    with pytest.raises(SystemExit):
        ex.parse_args(bad)


# --------------------------------------------------------------------------- #
# HTTP layer: retry / backoff (mocked, no network, no real sleeping)
# --------------------------------------------------------------------------- #
class _FakeResponse:
    def __init__(self, body: str):
        self._body = body.encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_get_json_success(monkeypatch):
    monkeypatch.setattr(ex, "urlopen", lambda *a, **k: _FakeResponse('{"ok": true}'))
    assert ex.get_json("http://x", {"a": 1}) == {"ok": True}


def test_get_json_retries_on_5xx_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def flaky(*_a, **_k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise HTTPError("http://x", 503, "busy", hdrs=None, fp=None)
        return _FakeResponse('{"ok": 1}')

    monkeypatch.setattr(ex, "urlopen", flaky)
    monkeypatch.setattr(ex.time, "sleep", lambda _s: None)  # no real backoff wait
    assert ex.get_json("http://x", {}) == {"ok": 1}
    assert calls["n"] == 2


def test_get_json_does_not_retry_on_4xx(monkeypatch):
    def client_error(*_a, **_k):
        raise HTTPError("http://x", 404, "missing", hdrs=None, fp=None)

    monkeypatch.setattr(ex, "urlopen", client_error)
    with pytest.raises(HTTPError):
        ex.get_json("http://x", {})


def test_get_json_retries_on_network_error_then_raises(monkeypatch):
    monkeypatch.setattr(ex, "urlopen", lambda *_a, **_k: (_ for _ in ()).throw(URLError("down")))
    monkeypatch.setattr(ex.time, "sleep", lambda _s: None)
    with pytest.raises(URLError):
        ex.get_json("http://x", {}, retries=2)


def test_geocode_city_maps_fields(monkeypatch):
    monkeypatch.setattr(ex, "get_json", lambda *a, **k: {
        "results": [{"id": 42, "name": "Madrid", "country": "Spain",
                     "country_code": "ES", "latitude": 40.4, "longitude": -3.7,
                     "timezone": "Europe/Madrid", "elevation": 667, "population": 3000000}]
    })
    loc = ex.geocode_city("Madrid")
    assert loc["location_id"] == 42
    assert loc["timezone"] == "Europe/Madrid"


def test_geocode_city_raises_when_no_results(monkeypatch):
    monkeypatch.setattr(ex, "get_json", lambda *a, **k: {"results": []})
    with pytest.raises(ValueError):
        ex.geocode_city("Atlantis")


# --------------------------------------------------------------------------- #
# IO helpers
# --------------------------------------------------------------------------- #
def test_write_csv_roundtrip(tmp_path):
    rows = [
        {"a": 1, "b": "x"},
        {"a": 2, "b": "y"},
    ]
    out = tmp_path / "nested" / "out.csv"
    ex.write_csv(out, rows)
    with out.open(newline="", encoding="utf-8") as f:
        back = list(csv.DictReader(f))
    assert [r["a"] for r in back] == ["1", "2"]
    assert [r["b"] for r in back] == ["x", "y"]


def test_write_csv_empty_writes_empty_file(tmp_path):
    out = tmp_path / "empty.csv"
    ex.write_csv(out, [])
    assert out.read_text(encoding="utf-8") == ""


def test_snapshot_partition_path_is_windows_safe(tmp_path):
    path = ex.snapshot_partition_path(tmp_path, "raw_forecast_daily", EXTRACTED_AT)
    assert ":" not in path.as_posix().split(str(tmp_path.as_posix()))[-1]
    assert path.name == "data.parquet"
    assert "raw_forecast_daily" in path.as_posix()


def test_log_event_emits_json(capsys):
    ex.log_event("unit_test", city="Madrid", n=3)
    err = capsys.readouterr().err.strip()
    parsed = json.loads(err)
    assert parsed == {"event": "unit_test", "city": "Madrid", "n": 3}


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
