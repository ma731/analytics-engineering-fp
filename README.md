# Open-Meteo Weather Analytics

Final project for **Analytics Engineering @ IE School of Science and Technology**.

An end-to-end analytics pipeline over [Open-Meteo](https://open-meteo.com/) data for
58 Spanish cities (from `spain_cities.csv` — province capitals plus additional major cities):

**Open-Meteo APIs → Python extraction → DuckDB → dbt (staging → intermediate → marts) → Streamlit dashboard.**

![City Comfort Index dashboard](docs/dashboard.png)

**Live dashboard:** https://city-comfort-index.streamlit.app

---

## TL;DR — run it in four commands

```bash
uv sync                                  # install dependencies (or: pip install -e .)
python scripts/load_to_duckdb.py         # load the committed raw CSVs into DuckDB
dbt deps && dbt build                    # build all models + run all tests
python -m streamlit run streamlit_app/app.py   # launch the dashboard
```

The raw CSVs are committed under `data/raw/open_meteo/`, so you can skip extraction and
go straight to `load_to_duckdb.py`. To regenerate them from the live API, see step 1 below.

> **dbt profile:** `profiles.yml` lives in the project root. If dbt can't find the
> profile, run dbt with `--profiles-dir .` or `export DBT_PROFILES_DIR=$PWD` first.

---

## 1. How do I run the extraction?

The extractor pulls from Open-Meteo endpoints (no API key required) and writes four CSVs.

```bash
# Reproducible 58-city extraction (reads spain_cities.csv). Pulls ONE FULL YEAR of
# daily weather from the Archive API, plus recent hourly air quality and a 7-day forecast:
python scripts/extract_spain_cities.py
```

> **About the 58 cities.** The canonical dataset is the **58-city** set committed under
> `data/raw/open_meteo/` (city list in [`spain_cities.csv`](spain_cities.csv)).
> `scripts/extract_spain_cities.py` regenerates it deterministically from that file, so a
> re-extraction reproduces the same cities and a full year of weather (used for the
> four-season analysis). The standard run **skips extraction** and uses the committed CSVs.

Or run the whole pipeline (extract → load → dbt build) in one command:

```bash
bash scripts/run_pipeline.sh              # full run
bash scripts/run_pipeline.sh --skip-extract   # use committed CSVs
```

Output (written to `data/raw/open_meteo/`):

| File | Source endpoint | Grain |
|---|---|---|
| `raw_locations.csv` | `spain_cities.csv` | one row per city |
| `raw_weather_daily.csv` | Archive API (1 year) | one row per city per day |
| `raw_forecast_daily.csv` | Forecast API | one row per city per forecast date per run |
| `raw_air_quality_hourly.csv` | Air Quality API | one row per city per hour |

## 2. How do I load the data?

```bash
python scripts/load_to_duckdb.py
```

This reads `data/raw/open_meteo/*.csv` and registers them as tables in the `raw` schema
of `data/weather_analytics.duckdb`. Re-running it is idempotent (it drops and recreates
each table).

## 3. How do I run dbt?

```bash
dbt deps          # installs dbt_utils, dbt_expectations, dbt_date
dbt build         # runs every model and every test
```

`dbt build` materializes staging and intermediate as **views** and marts as **tables**,
seeds the AQI health bands, then runs the full test suite (PK uniqueness, not-null,
foreign-key relationships, accepted values, range expectations, and two custom singular tests).

Current run: **17 models, 3 unit tests, 1 seed — 146 checks, all green.**

## 4. How do I launch the dashboard?

```bash
python -m streamlit run streamlit_app/app.py
# then open http://localhost:8501
```

The dashboard (the **City Comfort Index**) has a light "brutalist website" design with a sticky nav,
a terracotta hero and an animated weather-chart background. Highlights:

- a **"Find your ideal city" planner** — weight warmth / comfort / clean-air / dry / calm, pick a
  season, optionally avoid heatwave-prone cities, and it ranks all 58 cities with a match score and
  each city's best month;
- a **four-season** comfort comparison, an **extreme-events** view, a **temperature-anomaly** view,
  a **forecast-accuracy** view, and a **data-quality & lineage** panel;
- a City Spotlight photo carousel (with a per-city slogan), an animated comfort **leaderboard**,
  a play-button scatter, a gradient trend, a radar, a heatmap and a map.

It has a city filter (with a "show all 58 cities" toggle), a date filter, dual Spain/Canary live
clocks, and reads **only from the mart models**, never the raw files.

## 5. What final models power the dashboard?

| Mart model | Grain | Used for |
|---|---|---|
| `mart_city_weather_summary` | one row per city | KPI cards, comfort ranking, map |
| `mart_city_season_summary` | one row per city per season | four-season comfort comparison |
| `mart_city_month_summary` | one row per city per month | "best month to visit" in the planner |
| `mart_extreme_events` | one row per city | heatwave / cold-snap / heavy-rain view |
| `mart_temperature_anomaly` | one row per city per day | unusually warm/cold days (z-score) |
| `fct_city_weather_day` | one row per city per day | temperature trend, day-type breakdown, distribution |
| `fct_air_quality_city_day` | one row per city per day | air-quality comparison + EEA health band |

`dim_location` is the conformed dimension every fact joins back to via `location_sk`.

### dbt features used

Beyond the three-layer star schema, the project exercises the dbt toolkit end to end:

- **Seed** — `seeds/aqi_health_bands.csv` (EEA AQI bands), range-joined into the air-quality fact.
- **Macro** — `season_from_date()` classifies each date into its meteorological season.
- **Window functions** — `int_weather_extreme_streaks` (gaps-and-islands streaks) and `mart_temperature_anomaly` (seasonal z-scores).
- **Unit tests** — `models/unit_tests.yml` asserts the `is_comfortable` rule, the season macro, and the heatwave logic with mocked inputs.
- **Custom generic test** — `non_negative` (in `tests/generic/`), reused across the count columns.
- **Model contracts** — enforced column data types on `dim_location`, `mart_city_season_summary`, `mart_extreme_events`.
- **Incremental model** — `fct_forecast_city_day` accumulates forecast snapshots across runs (unique key on the extraction timestamp).
- **Source freshness** — `dbt source freshness` checks `extracted_at`; `persist_docs` writes descriptions into DuckDB.
- **Exposure** — `models/exposures.yml` declares the Streamlit dashboard in the lineage graph, so `dbt build --select +exposure:city_comfort_index_dashboard` rebuilds exactly what it reads.
- **Packages** — `dbt_utils` (surrogate keys), `dbt_expectations` (range tests), `dbt_date`.

### Lineage

The full dbt DAG — sources → staging → intermediate → marts → the dashboard exposure
(regenerate with `dbt docs generate && python scripts/render_lineage_dag.py`):

![dbt lineage DAG](docs/lineage_dag.png)

For the interactive version: `dbt docs generate && dbt docs serve`.

## 6. What modeling choices did we make and why?

Short version below; the full write-up is in [`docs/modeling_decisions.md`](docs/modeling_decisions.md).

- **Three-layer architecture.** Staging (rename + cast, same grain as source) → intermediate
  (joins, daily aggregation, derived flags, forecast alignment) → marts (star schema: one
  conformed `dim_location` + grain-explicit facts + one wide summary).
- **Surrogate keys everywhere** via `dbt_utils.generate_surrogate_key`, so facts reference
  `dim_location.location_sk` and every fact has a `relationships` test back to the dimension.
- **Comfort metrics defined in SQL, not the app.** `is_comfortable`, `comfort_score` and
  `overall_comfort_index` live in the marts so the dashboard stays a thin presentation layer.
- **A wide summary mart** (`mart_city_weather_summary`) denormalizes the per-city rollups so
  the dashboard's headline views are a single fast read.

---

## Project structure

```text
analytics-engineering-fp/
├── data/raw/open_meteo/        # committed raw CSVs (DuckDB file is git-ignored)
├── scripts/
│   ├── extract_spain_cities.py # reproducible 58-city pull (1 year) -> CSVs
│   ├── load_to_duckdb.py       # CSVs -> DuckDB raw schema
│   └── run_pipeline.sh         # extract -> load -> dbt build, one command
├── macros/                     # season_from_date() Jinja macro
├── seeds/                      # aqi_health_bands.csv (EEA AQI bands) + schema
├── models/
│   ├── sources.yml             # 4 registered sources
│   ├── exposures.yml           # dashboard declared as a dbt exposure
│   ├── staging/                # stg_* (4 views) + docs/tests
│   ├── intermediate/           # int_* (4 views) + docs/tests
│   ├── marts/                  # dim/fct/mart (9 tables) + docs/tests
│   └── unit_tests.yml          # dbt unit tests (logic with mocked inputs)
├── tests/                      # 2 singular tests + generic/non_negative.sql
├── streamlit_app/app.py        # City Comfort Index dashboard
├── docs/                       # lineage_dag.png + modeling_decisions.md
├── dbt_project.yml  packages.yml  profiles.yml  pyproject.toml
└── README.md
```

## Testing

Tests cover every category the rubric asks for:

- **Primary keys** — `unique` + `not_null` on every surrogate key (staging → marts).
- **Dates / location keys** — `not_null` on grain columns and foreign keys.
- **Relationships** — every fact has a `relationships` FK test to `dim_location`.
- **Accepted values** — `country_code` restricted to `ES`.
- **Ranges** — `dbt_expectations.expect_column_values_to_be_between` on latitude/longitude,
  temperature, AQI, and comfort score.
- **Custom singular tests** — `assert_aqi_non_negative.sql`,
  `assert_temperature_within_realistic_range.sql`.
- **Custom generic test** — `non_negative` (reusable), applied across the count columns.
- **Unit tests** — `models/unit_tests.yml` checks the transformation logic itself
  (the comfort rule, the season macro, and heatwave detection) with mocked inputs.
- **Model contracts** — enforced column data types on the dimension and key marts.

## Continuous integration

`.github/workflows/ci.yml` runs on every push and PR:

- **pytest** — unit tests for the extraction parsers (`tests_python/`)
- **dbt build** — loads sample data, builds all models, runs all tests
- **lint** — `ruff` for Python, `sqlfluff` for SQL

Pre-commit hooks (`.pre-commit-config.yaml`) run `ruff`, `sqlfluff`, and whitespace
fixers locally — install with `pre-commit install` after `pip install -e ".[dev]"`.

## Deploy to Streamlit Community Cloud

1. Push this repo to GitHub.
2. At [share.streamlit.io](https://share.streamlit.io), create an app pointing at
   `streamlit_app/app.py` on this repo/branch.
3. Set the **custom subdomain** to `city-comfort-index` so the public URL is
   **https://city-comfort-index.streamlit.app** (already linked at the top of this README).

The repo is deploy-ready: `requirements.txt` lists the runtime deps and a prebuilt
`data/weather_analytics.duckdb` is committed, so the app runs on Cloud with no build step.
Every push to the deployed branch auto-redeploys.

## Note — forecast vs actual coverage

`fct_forecast_city_day` aligns forecast snapshots with actuals on `(city, date)`. In a single
extraction the comparison only covers the **overlap day(s)** — the dates that appear in both
the forecast horizon and the past-days actuals window (currently one day per city). Running the
extractor on a schedule accumulates forecast snapshots and grows this fact over time, which is
how a richer forecast-accuracy view is built.

Daily weather covers a **full year** (Archive API) so the four-season comparison and the
extreme-event streaks are meaningful. The Open-Meteo Air Quality API only serves a shorter
recent window (~90 days of hourly readings), so `fct_air_quality_city_day` covers fewer days
than `fct_city_weather_day`, and the air-quality signal in the comfort index is recent rather
than seasonal.

## Tech stack

DuckDB · dbt Core (with `dbt_utils`, `dbt_expectations`, `dbt_date`) · Streamlit · Plotly · Python.
