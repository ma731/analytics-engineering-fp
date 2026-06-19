-- =============================================================================
-- mart_extreme_events
-- Extreme-weather event summary per city.
-- Grain: one row per city, aggregated over the full date range.
-- Counts single-day extremes (hot/freezing/heavy-rain) and multi-day extremes
-- (heatwave/cold-snap/wet-spell days), plus the longest consecutive streak of
-- each, derived from int_weather_extreme_streaks using window functions.
-- =============================================================================

with streaks as (

    -- Per-day extreme flags, consecutive-run lengths (heat_streak/cold_streak/
    -- wet_streak), and in_heatwave/in_cold_snap/in_wet_spell booleans, computed
    -- with the gaps-and-islands window-function pattern
    select * from {{ ref('int_weather_extreme_streaks') }}

),

final as (

    select
        -- Derive location_sk from location_id to enable joins with dim_location
        {{ dbt_utils.generate_surrogate_key(['location_id']) }} as location_sk,
        location_id,
        city_name,
        country_code,
        count(*) as total_days,

        -- Single-day extreme: any day crossing the hot threshold, including
        -- isolated days that aren't part of a qualifying heatwave run
        count(*) filter (where is_hot) as hot_days,
        -- Multi-day extreme: days inside a run of >=3 consecutive hot days
        -- (a subset of hot_days)
        count(*) filter (where in_heatwave) as heatwave_days,
        -- Longest consecutive hot-day run for the city. This is the longest
        -- run length regardless of the 3-day heatwave threshold, so it can be
        -- < 3 (and heatwave_days = 0) if the city never had a qualifying run
        max(heat_streak) as longest_heatwave,

        -- Single-day extreme: any day crossing the freezing threshold
        count(*) filter (where is_freezing) as freezing_days,
        -- Multi-day extreme: days inside a run of >=3 consecutive freezing days
        count(*) filter (where in_cold_snap) as cold_snap_days,
        -- Longest consecutive freezing-day run; same caveat as longest_heatwave
        max(cold_streak) as longest_cold_snap,

        -- Single-day extreme: days with >=20mm of rain. A wet spell is a run
        -- of >=2 consecutive heavy-rain days
        count(*) filter (where is_heavy_rain) as heavy_rain_days,
        max(wet_streak) as longest_wet_spell

    from streaks
    group by location_id, city_name, country_code

)

select * from final
