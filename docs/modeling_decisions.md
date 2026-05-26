# Modeling Decisions

> Owner: Role 3 (Dimensional & Data Quality Lead) with input from Role 2.
> Status: skeleton — fill in by end of Week 1.

## Grain of each fact

| Fact | Grain | Natural key |
|---|---|---|
| `fct_city_weather_day` | one row per `location_sk` per `weather_date` | (`location_sk`, `weather_date`) |
| `fct_air_quality_city_day` | one row per `location_sk` per `air_quality_date` | (`location_sk`, `air_quality_date`) |
| `fct_forecast_city_day` | one row per `location_sk` per `forecast_date` per `extracted_at` | (`location_sk`, `forecast_date`, `extracted_at`) |

## Why we denormalize `mart_city_weather_summary`

_TODO_

## Why we keep `extracted_at` on forecast snapshots

_TODO_ — needed to compute forecast vs actual error across snapshots.

## Why these `is_*` flags

_TODO_ — `is_rainy`, `is_windy`, `is_hot`. Thresholds and units.
