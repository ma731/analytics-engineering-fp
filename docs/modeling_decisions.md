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
In a single extraction the forecast window (future dates) and the actuals window (past days)
do not overlap, so the fact is empty until forecast snapshots are accumulated over time and
their dates become observed actuals. The models are built and tested for that workflow.
