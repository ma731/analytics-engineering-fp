-- Extreme-weather streaks per city, computed with window functions.
--
-- Uses the classic "gaps and islands" pattern: for each event flag, the
-- difference between a global row_number and a per-flag row_number is constant
-- across a contiguous run of identical flag values. Counting rows within that
-- (flag, island) partition gives the length of each consecutive run, which we
-- use to label heatwaves (>=3 hot days), cold snaps (>=3 freezing days) and
-- wet spells (>=2 heavy-rain days).

with daily as (

    select
        location_id,
        city_name,
        country_code,
        weather_date,
        temperature_2m_max,
        temperature_2m_min,
        rain_sum,
        is_hot,
        is_freezing,
        rain_sum >= 20.0 as is_heavy_rain

    from {{ ref('int_city_day_weather') }}

),

islands as (

    select
        *,
        row_number() over (partition by location_id order by weather_date)
        - row_number() over (partition by location_id, is_hot order by weather_date)
            as hot_island,
        row_number() over (partition by location_id order by weather_date)
        - row_number() over (partition by location_id, is_freezing order by weather_date)
            as cold_island,
        row_number() over (partition by location_id order by weather_date)
        - row_number() over (partition by location_id, is_heavy_rain order by weather_date)
            as wet_island

    from daily

),

runs as (

    select
        *,
        count(*) over (partition by location_id, is_hot, hot_island) as hot_run_len,
        count(*) over (partition by location_id, is_freezing, cold_island) as cold_run_len,
        count(*) over (partition by location_id, is_heavy_rain, wet_island) as wet_run_len

    from islands

)

select
    {{ dbt_utils.generate_surrogate_key(['location_id', 'weather_date']) }} as extreme_streak_sk,
    location_id,
    city_name,
    country_code,
    weather_date,
    temperature_2m_max,
    temperature_2m_min,
    rain_sum,
    is_hot,
    is_freezing,
    is_heavy_rain,
    case when is_hot then hot_run_len else 0 end as heat_streak,
    case when is_freezing then cold_run_len else 0 end as cold_streak,
    case when is_heavy_rain then wet_run_len else 0 end as wet_streak,
    (is_hot and hot_run_len >= 3) as in_heatwave,
    (is_freezing and cold_run_len >= 3) as in_cold_snap,
    (is_heavy_rain and wet_run_len >= 2) as in_wet_spell

from runs
