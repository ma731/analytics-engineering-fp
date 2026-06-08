-- Incremental: each extraction run appends its forecast snapshot. The unique
-- key includes forecast_extracted_at, so re-running accumulates a forecast
-- history over time rather than overwriting it. On a fresh warehouse this builds
-- the full table; on subsequent runs only newer snapshots are inserted.
{{ config(
    materialized='incremental',
    unique_key='forecast_city_day_sk',
    on_schema_change='append_new_columns'
) }}

with forecast_vs_actual as (

    select * from {{ ref('int_forecast_vs_actual') }}

),

final as (

    select
        {{ dbt_utils.generate_surrogate_key(
            ['location_id', 'forecast_date', 'forecast_extracted_at']
        ) }} as forecast_city_day_sk,
        {{ dbt_utils.generate_surrogate_key(['location_id']) }} as location_sk,
        location_id,
        city_name,
        country_code,
        forecast_date,
        forecast_extracted_at,
        forecast_temp_max,
        forecast_temp_min,
        forecast_temp_mean,
        forecast_precipitation,
        forecast_wind_speed_max,
        actual_temp_max,
        actual_temp_min,
        actual_temp_mean,
        actual_precipitation,
        actual_wind_speed_max,
        temperature_max_error,
        temperature_min_error,
        temperature_mean_error,
        precipitation_error,
        wind_speed_error,
        abs_temperature_error,
        abs_precipitation_error

    from forecast_vs_actual

)

select * from final
{% if is_incremental() %}
where forecast_extracted_at > (select coalesce(max(forecast_extracted_at), '1900-01-01') from {{ this }})
{% endif %}
