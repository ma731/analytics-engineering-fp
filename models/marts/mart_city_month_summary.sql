-- =============================================================================
-- mart_city_month_summary
-- Monthly comfort summary per city.
-- Grain: one row per city per calendar month (1–12).
--
-- Two partial Junes (2025 and 2026) collapse into a single "typical June"
-- because the grain is month number, not year-month. This gives up to 12 rows
-- per city — the basis for the "best month to visit" picker.
-- =============================================================================
 
with weather as (
 
    -- Daily weather observations with comfort/condition flags
    select * from {{ ref('fct_city_weather_day') }}
 
),
 
final as (
 
    select
        -- Surrogate key scoped to city + month number (not year-month)
        {{ dbt_utils.generate_surrogate_key(['location_id', 'extract(month from weather_date)']) }}
            as city_month_sk,
        {{ dbt_utils.generate_surrogate_key(['location_id']) }} as location_sk,
        location_id,
        city_name,
        country_code,
        cast(extract(month from weather_date) as integer) as month_num,  -- 1–12
        strftime(weather_date, '%B') as month_name,                       -- e.g. "January"
        season,
 
        -- Data coverage for this city-month bucket
        count(*) as total_days,
 
        -- Temperature summaries
        round(avg(temperature_2m_mean), 1) as avg_temperature_c,
        round(avg(temperature_2m_max), 1)  as avg_max_temperature_c,
 
        -- Total accumulated rainfall/snowfall for the month
        round(sum(precipitation_sum), 1) as total_precipitation_mm,
 
        -- Day-type counts: comfortable_days feeds the comfort_score numerator
        -- below (total_days above is the denominator); rainy/hot/freezing_days
        -- are standalone descriptive counts, not part of the score formula
        count(*) filter (where is_comfortable) as comfortable_days,
        count(*) filter (where is_rainy)        as rainy_days,
        count(*) filter (where is_hot)          as hot_days,
        count(*) filter (where is_freezing)     as freezing_days,
 
        -- Comfort score: percentage of days meeting the comfortable criteria.
        -- nullif guards against divide-by-zero on empty city-month buckets.
        round(
            100.0 * count(*) filter (where is_comfortable) / nullif(count(*), 0),
            1
        ) as comfort_score
 
    from weather
    -- Group by month number AND month name + season so those non-aggregated
    -- columns are available in SELECT without violating GROUP BY rules
    group by
        location_id,
        city_name,
        country_code,
        extract(month from weather_date),
        strftime(weather_date, '%B'),
        season
 
)
 
select * from final
