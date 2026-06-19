-- =============================================================================
-- mart_city_season_summary
-- Seasonal comfort and weather summary per city.
-- Grain: one row per city per meteorological season (Spring/Summer/Autumn/Winter).
-- Provides a coarser-grained view than mart_city_month_summary, useful for
-- broad comparisons like "which city has the best summers".
-- =============================================================================
 
with weather as (
 
    -- Daily weather observations with comfort/condition flags and season label
    select * from {{ ref('fct_city_weather_day') }}
 
),
 
final as (
 
    select
        -- Surrogate key scoped to city + season
        {{ dbt_utils.generate_surrogate_key(['location_id', 'season']) }} as city_season_sk,
        {{ dbt_utils.generate_surrogate_key(['location_id']) }} as location_sk,
        location_id,
        city_name,
        country_code,
        season,  -- Winter/Spring/Summer/Autumn, derived by the season_from_date macro
 
        -- Data coverage for this city-season bucket
        count(*) as total_days,
 
        -- Temperature range across the season
        round(avg(temperature_2m_mean), 1) as avg_temperature_c,
        round(avg(temperature_2m_max), 1)  as avg_max_temperature_c,
        round(avg(temperature_2m_min), 1)  as avg_min_temperature_c,
 
        -- Total accumulated precipitation for the season
        round(sum(precipitation_sum), 1) as total_precipitation_mm,
 
        -- Day-type counts for condition analysis
        count(*) filter (where is_comfortable) as comfortable_days,
        count(*) filter (where is_rainy)        as rainy_days,
        count(*) filter (where is_hot)          as hot_days,
        count(*) filter (where is_freezing)     as freezing_days,
 
        -- Comfort score: % of days classified as comfortable within the season.
        -- nullif prevents divide-by-zero for cities with no data in a given season.
        round(
            100.0 * count(*) filter (where is_comfortable) / nullif(count(*), 0),
            1
        ) as comfort_score
 
    from weather
    group by location_id, city_name, country_code, season
 
)
 
select * from final