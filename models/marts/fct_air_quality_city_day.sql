-- =============================================================================
-- fct_air_quality_city_day
-- Fact table for daily air quality measurements per city.
-- Grain: one row per city per day.
-- Joins daily air quality aggregates with AQI health band thresholds so each
-- row carries a human-readable band label (e.g. "Good", "Moderate", "Poor").
-- =============================================================================
 
with air_quality as (
 
    -- Daily-aggregated air quality metrics (averages, max, p95) from the
    -- intermediate layer. Source data is hourly sensor readings.
    select * from {{ ref('int_air_quality_daily') }}
 
),
 
bands as (
 
    -- Static seed/lookup table mapping AQI numeric ranges to health band labels
    -- and a sort order for ranking bands from best to worst.
    select * from {{ ref('aqi_health_bands') }}
 
),
 
final as (
 
    select
        air_quality.air_quality_daily_sk as air_quality_city_day_sk,
        -- Derive location_sk from location_id to enable joins with dim_location
        {{ dbt_utils.generate_surrogate_key(['air_quality.location_id']) }} as location_sk,
        air_quality.location_id,
        air_quality.city_name,
        air_quality.country_code,
        air_quality.air_quality_date,
 
        -- Particulate matter metrics (PM10 and PM2.5)
        -- PM2.5 is the finer, more health-relevant particle fraction
        air_quality.avg_pm10,
        air_quality.max_pm10,
        air_quality.p95_pm10,
        air_quality.avg_pm2_5,
        air_quality.max_pm2_5,
        air_quality.p95_pm2_5,
 
        -- Gas pollutant metrics
        air_quality.avg_carbon_monoxide,
        air_quality.max_carbon_monoxide,
        air_quality.avg_nitrogen_dioxide,
        air_quality.max_nitrogen_dioxide,
        air_quality.avg_ozone,
        air_quality.max_ozone,
 
        -- European AQI composite score (aggregates all pollutants into one index)
        air_quality.avg_european_aqi,
        air_quality.max_european_aqi,
        air_quality.p95_european_aqi,
        air_quality.hourly_readings_count,
 
        -- AQI band label and sort order, determined by a range join:
        -- the row from `bands` whose [aqi_min, aqi_max) bracket contains avg_european_aqi
        bands.aqi_band,
        bands.band_order as aqi_band_order
 
    from air_quality
    -- Range join: match each day's average AQI to exactly one health band bucket
    left join bands
        on air_quality.avg_european_aqi >= bands.aqi_min
        and air_quality.avg_european_aqi < bands.aqi_max
 
)
 
select * from final
 