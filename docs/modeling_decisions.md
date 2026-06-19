# Modeling Decisions

This document explains the grain, structure, and metric choices behind the dbt project.

## Layering

We follow the standard dbt three-layer pattern:

| Layer | Materialization | Responsibility |
|---|---|---|
| **staging** | view | One model per source. Rename to `snake_case`, cast every column to an explicit type, add a surrogate key. Same grain as the raw source — no business logic. |
| **intermediate** | view | Joins, daily aggregation, derived flags, forecast/actual alignment. Prepares the shapes the marts consume. |
| **marts** | table | Star schema: one conformed dimension, grain-explicit facts, and one wide summary table for the dashboard. |

Staging/intermediate are views (cheap, always fresh); marts are tables (fast to query
from Streamlit).

## Grain of each model

| Model | Grain |
|---|---|
| `dim_location` | one row per city |
| `fct_city_weather_day` | one row per city per calendar day |
| `fct_air_quality_city_day` | one row per city per calendar day |
| `fct_forecast_city_day` | one row per city per forecast date per extraction run |
| `mart_city_weather_summary` | one row per city (rolled up over the window) |
| `mart_city_season_summary` | one row per city per meteorological season |
| `mart_extreme_events` | one row per city (extreme-event counts + longest streaks) |

Every fact's grain is enforced with a `unique` + `not_null` test on its surrogate key, and
every fact carries `location_sk` with a `relationships` test back to `dim_location`.

## Why surrogate keys

Each staging model generates a deterministic surrogate key with
`dbt_utils.generate_surrogate_key`. Facts recompute `location_sk` from `location_id` so the
value matches `dim_location.location_sk` exactly. This gives clean, testable foreign-key
relationships without depending on the natural integer IDs from the API.

## Why metrics live in SQL

The comfort logic is defined in the models, not in the dashboard:

- **`is_comfortable`** (`fct_city_weather_day`) — mean temperature between 18 °C and 26 °C
  and the day is not rainy, windy, hot, or freezing.
- **`comfort_score`** (`mart_city_weather_summary`) — `100 × comfortable_days / total_days`.
- **`overall_comfort_index`** — `comfort_score − 0.5 × avg_european_aqi`, so pleasant weather
  is rewarded and poor air quality is penalised.

Keeping these in dbt means the dashboard is a thin presentation layer, the definitions are
tested, and any other consumer (notebook, BI tool) gets the same numbers.

## Why a wide summary mart

`mart_city_weather_summary` denormalizes the per-city weather and air-quality rollups into
one row per city. The dashboard's headline views (KPIs, ranking, map) are then a single
fast read instead of repeated joins/aggregations at render time.

## Forecast vs actual

`int_forecast_vs_actual` aligns forecast snapshots to actuals on `(location_id, date)` and
computes signed and absolute errors; `fct_forecast_city_day` exposes it at the mart layer.
In a single extraction the comparison covers only the date(s) where the forecast horizon and
the past-days actuals window overlap (currently one day per city). Running the extractor on a
schedule accumulates forecast snapshots and grows this fact into a fuller forecast-accuracy
history. The models are built and tested for that workflow.

## Seasonal analysis

Daily weather is pulled for a **full year** (Open-Meteo Archive API), so the data spans all
four seasons. A `season_from_date()` macro classifies each date into its **meteorological**
season (Winter = Dec–Feb, Spring = Mar–May, Summer = Jun–Aug, Autumn = Sep–Nov) — the whole-month
convention used for climate aggregation. `fct_city_weather_day` carries the `season` column, and
`mart_city_season_summary` rolls comfort up to one row per city per season so the dashboard can
compare, e.g., Sevilla's summer vs winter comfort. The macro keeps the rule defined once and
reused, rather than copy-pasted across models.

## Extreme-event streaks (window functions)

`int_weather_extreme_streaks` detects **consecutive** runs of extreme days using the classic
gaps-and-islands pattern: the difference between a global `row_number()` and a per-flag
`row_number()` is constant across a contiguous run of identical flag values, so counting rows
within each `(flag, island)` partition yields the run length. We label a **heatwave** as ≥3
consecutive hot days, a **cold snap** as ≥3 consecutive freezing days, and a **wet spell** as ≥2
consecutive heavy-rain days. `mart_extreme_events` aggregates these to one row per city (event-day
counts and the longest streak of each) — a metric you cannot express with a plain `group by`.

## AQI health bands (seed)

`seeds/aqi_health_bands.csv` encodes the EEA European-AQI health scale (Good / Fair / Moderate /
Poor / Very Poor / Extremely Poor). It is range-joined into `fct_air_quality_city_day`
(`avg_european_aqi` between `aqi_min` and `aqi_max`) to attach a human-readable `aqi_band` and an
ordinal `aqi_band_order`. Keeping the thresholds in a seed means the classification is versioned,
testable (`accepted_values`), and editable without touching SQL.

## Exposure

`models/exposures.yml` declares the Streamlit dashboard as a dbt **exposure** that depends on the
marts it reads. This puts the dashboard in the lineage graph, documents the marts-only contract
(the app never reads raw files), and lets `dbt build --select +exposure:city_comfort_index_dashboard`
rebuild exactly the models the dashboard needs.

## Production-grade testing & governance

The project goes past data tests to also test the *logic* and lock down the *interface*:

- **Unit tests** (`models/unit_tests.yml`) feed mocked input rows to a model and assert its output:
  the `is_comfortable` rule, the `season_from_date` macro, and the heatwave window-function logic.
  These run at build time and need no warehouse data — they catch logic regressions a data test can't.
- **Custom generic test** `non_negative` (`tests/generic/`) is reused across the count columns,
  alongside the two singular tests.
- **Model contracts** enforce column data types on `dim_location`, `mart_city_season_summary`, and
  `mart_extreme_events`, so a schema drift fails the build instead of silently reaching the dashboard.
- **Source freshness** (`extracted_at`) and **persist_docs** (descriptions written into DuckDB) round
  out the governance story.

## Best month & anomalies

`mart_city_month_summary` rolls comfort to one row per city per calendar month, which the planner uses
to name each city's "best month to visit". `mart_temperature_anomaly` compares each day's temperature
to that city's seasonal average with window functions, expressing the deviation as a z-score — the
basis for the "unusually warm/cold days" view. A day is flagged `is_extreme_day` when `|anomaly_z|`
reaches the `extreme_anomaly_stddev` var (`dbt_project.yml`, default 2 standard deviations). Driving
the cutoff off the standard deviation rather than a fixed degree threshold keeps it statistically
meaningful across cities and seasons with different temperature variability, and keeping it in a var
means the rule is defined once and reproducible instead of a magic number copy-pasted into SQL.

## Incremental forecast

`fct_forecast_city_day` is materialized **incremental**, keyed on the extraction timestamp, so each
extraction run appends its forecast snapshot rather than overwriting. A single run behaves like a table;
a scheduled run grows a real forecast-accuracy history.
