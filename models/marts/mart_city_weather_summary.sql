-- =============================================================================
-- mart_city_weather_summary
-- Overall weather and air quality summary per city across the full date range.
-- Grain: one row per city.
-- The primary mart for city-level comparisons and rankings. Combines weather
-- comfort metrics with air quality data and computes two composite scores:
--   comfort_score         — weather-only comfort percentage
--   overall_comfort_index — comfort_score penalised by average air quality
-- =============================================================================
 
with weather as (
 
    -- Daily weather observations with comfort/condition flags
    select * from {{ ref('fct_city_weather_day') }}
 
),
 
air_quality as (
 
    -- Daily air quality measurements including the European AQI composite
    select * from {{ ref('fct_air_quality_city_day') }}
 
),
 
locations as (
 
    -- Location dimension for display attributes (city name, country, coordinates)
    select * from {{ ref('dim_location') }}
 
),
 
-- -------------------------------------------------------------------------
-- Step 1: Aggregate weather metrics to city level
-- -------------------------------------------------------------------------
weather_summary as (
 
    select
        location_sk,
        location_id,
        count(*)                                         as total_days,
        min(weather_date)                                as first_date,
        max(weather_date)                                as last_date,
        round(avg(temperature_2m_mean), 1)               as avg_temperature_c,
        round(avg(temperature_2m_max),  1)               as avg_max_temperature_c,
        round(avg(temperature_2m_min),  1)               as avg_min_temperature_c,
        round(sum(precipitation_sum),   1)               as total_precipitation_mm,
        count(*) filter (where is_comfortable)           as comfortable_days,
        count(*) filter (where is_rainy)                 as rainy_days,
        count(*) filter (where is_windy)                 as windy_days,
        count(*) filter (where is_hot)                   as hot_days,
        count(*) filter (where is_freezing)              as freezing_days
 
    from weather
    group by location_sk, location_id
 
),
 
-- -------------------------------------------------------------------------
-- Step 2: Aggregate air quality metrics to city level
-- -------------------------------------------------------------------------
air_quality_summary as (
 
    select
        location_sk,
        round(avg(avg_european_aqi),    1) as avg_air_quality_index,  -- Lower is better
        round(avg(avg_pm2_5),           1) as avg_pm2_5,
        round(max(max_european_aqi),    1) as worst_air_quality_index  -- Single worst day
 
    from air_quality
    group by location_sk
 
),
 
-- -------------------------------------------------------------------------
-- Step 3: Join everything together and compute composite scores
-- -------------------------------------------------------------------------
final as (
 
    select
        -- Location attributes from dimension table
        locations.location_sk,
        locations.location_id,
        locations.city_name,
        locations.country,
        locations.country_code,
        locations.latitude,
        locations.longitude,
        locations.population,
 
        -- Weather coverage window
        weather_summary.total_days,
        weather_summary.first_date,
        weather_summary.last_date,
 
        -- Aggregated weather metrics
        weather_summary.avg_temperature_c,
        weather_summary.avg_max_temperature_c,
        weather_summary.avg_min_temperature_c,
        weather_summary.total_precipitation_mm,
 
        -- Day-type counts
        weather_summary.comfortable_days,
        weather_summary.rainy_days,
        weather_summary.windy_days,
        weather_summary.hot_days,
        weather_summary.freezing_days,
 
        -- Air quality metrics (null when no AQI data exists for a city)
        air_quality_summary.avg_air_quality_index,
        air_quality_summary.avg_pm2_5,
        air_quality_summary.worst_air_quality_index,
 
        -- Comfort score: % of days classified as comfortable (weather only)
        round(
            100.0 * weather_summary.comfortable_days
            / nullif(weather_summary.total_days, 0),
            1
        ) as comfort_score,
 
        -- Overall comfort index: comfort_score minus an air quality penalty.
        -- Penalty = avg AQI × 0.5, coalesced to 0 for cities without AQI data.
        -- Cities with cleaner air score higher at equal weather comfort.
        round(
            (
                100.0 * weather_summary.comfortable_days
                / nullif(weather_summary.total_days, 0)
            )
            - coalesce(air_quality_summary.avg_air_quality_index, 0) * 0.5,
            1
        ) as overall_comfort_index
 
    from locations
    -- Left joins preserve all cities in dim_location even if weather or AQI
    -- data is missing for a given city
    left join weather_summary
        on locations.location_sk = weather_summary.location_sk
    left join air_quality_summary
        on locations.location_sk = air_quality_summary.location_sk
 
)
 
select * from final