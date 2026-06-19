-- =============================================================================
-- fct_forecast_city_day
-- Fact table for forecast accuracy, one row per city per forecast date per
-- extraction snapshot. Accumulates forecast history over time (incremental).
--
-- Materialization strategy — INCREMENTAL (append-only snapshots):
--   Each pipeline run inserts only rows whose forecast_extracted_at is newer
--   than the current table maximum. This preserves the full forecast history
--   rather than overwriting it, enabling analysis of how forecast accuracy
--   evolves as the target date approaches.
--   On a fresh warehouse the full table is built from scratch.
-- =============================================================================
{{ config(
    materialized='incremental',
    unique_key='forecast_city_day_sk',
    on_schema_change='append_new_columns'
) }}
 
with forecast_vs_actual as (
 
    -- Intermediate model that aligns forecast snapshots with observed actuals
    -- and pre-computes signed and absolute error fields for each metric
    select * from {{ ref('int_forecast_vs_actual') }}
 
),
 
final as (
 
    select
        -- Surrogate key includes extraction timestamp so each snapshot of the
        -- same (location, date) pair gets its own row in the history table
        {{ dbt_utils.generate_surrogate_key(
            ['location_id', 'forecast_date', 'forecast_extracted_at']
        ) }} as forecast_city_day_sk,
        {{ dbt_utils.generate_surrogate_key(['location_id']) }} as location_sk,
        location_id,
        city_name,
        country_code,
        forecast_date,           -- The date being predicted
        forecast_extracted_at,   -- When the forecast snapshot was captured
 
        -- Forecast values (what the model predicted)
        forecast_temp_max,
        forecast_temp_min,
        forecast_temp_mean,
        forecast_precipitation,
        forecast_wind_speed_max,
 
        -- Observed actuals (populated once the forecast date has passed)
        actual_temp_max,
        actual_temp_min,
        actual_temp_mean,
        actual_precipitation,
        actual_wind_speed_max,
 
        -- Signed errors (forecast - actual): positive = over-predicted,
        -- negative = under-predicted
        temperature_max_error,
        temperature_min_error,
        temperature_mean_error,
        precipitation_error,
        wind_speed_error,
 
        -- Absolute errors for magnitude-only accuracy metrics (e.g. MAE)
        abs_temperature_error,
        abs_precipitation_error
 
    from forecast_vs_actual
 
)
 
select * from final
 
-- Incremental filter: only process snapshots not yet in the table,
-- defaulting to a far-past sentinel date (1900-01-01) when the table is
-- empty (first run), so every row is included on a fresh build
{% if is_incremental() %}
where forecast_extracted_at > (select coalesce(max(forecast_extracted_at), '1900-01-01') from {{ this }})
{% endif %}
 
